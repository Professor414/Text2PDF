# main-7.py
import os
import logging
from io import BytesIO
from datetime import datetime
import re
import asyncio

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from weasyprint import HTML

# Logging
logging.basicConfig(level=logging.INFO)

# Token
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("សូមកំណត់ BOT_TOKEN ជា environment variable មុនចាប់ផ្តើម។")

# HTML Template (formatted to follow A/ក/១ style like image A)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="km">
<head>
<meta charset="utf-8">
<title>Khmer PDF</title>
<style>
  @page { size: A4; margin: 20mm 18mm; }
  body { font-family: "Khmer OS Battambang","Khmer OS Content","Noto Sans Khmer",sans-serif;
         line-height: 1.6; font-size: 14pt; color: #111; }
  h1.title { text-align: center; font-weight: 700; font-size: 18pt; margin: 0 0 12px; }
  .content { counter-reset: kh-num; }

  /* Base paragraphs */
  .paragraph { margin: 6px 0; }
  .indent { text-indent: 24px; }

  /* Section header like `A.` (we render marker via ::before) */
  .section { margin: 10px 0 6px; }
  .lead-A { font-weight: 700; }
  .lead-A::before { content: "A. "; font-weight: 700; }

  /* Sub point like `ក.` */
  .point-ka { text-indent: 24px; }
  .point-ka::before {
    content: "ក. ";
    font-weight: 700;
    margin-left: -24px;
    position: relative;
    left: -6px;
  }

  /* Numbered like `១.` (accept 1 or ១ from input; we print Khmer digit) */
  .num-1 { text-indent: 24px; }
  .num-1::before {
    content: "១. ";
    font-weight: 700;
    margin-left: -24px;
    position: relative;
    left: -6px;
  }

  /* Optional highlight (yellow like screenshot) */
  .hl { background: #fff59d; }
</style>
</head>
<body>
  <h1 class="title">ឯកសារ PDF ភាសាខ្មែរ</h1>
  <div class="content">
    {content}
  </div>
</body>
</html>
"""

# In-memory store per user
user_data_store = {}

# Helper: generate PDF safely with timeout
async def safe_generate_pdf(html_str: str, timeout: int = 25) -> bytes:
    loop = asyncio.get_event_loop()
    html = HTML(string=html_str)

    def _render():
        return html.write_pdf()

    return await asyncio.wait_for(loop.run_in_executor(None, _render), timeout=timeout)

# /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data_store[user_id] = []
    await update.message.reply_text(
        "សួស្តី! ផ្ញើអត្ថបទជាបន្ទាត់ៗ។\n"
        "- បន្ទាត់ដែលចង់ជាក្បាល ‘A.’ ចាប់ផ្តើមដោយ: A.\n"
        "- ចំណុច ‘ក.’ ចាប់ផ្តើមដោយ: ក.\n"
        "- លេខ ‘១.’ ចាប់ផ្តើមដោយ: ១. ឬ 1.\n"
        "- បន្ទាត់ធម្មតា នឹងមាន indent ស្រាល។\n"
        "ពេលរួច ប្រើ /done ដើម្បីស្ទង់ជា PDF."
    )

# Receive each text line
async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_data_store:
        user_data_store[user_id] = []
    text = update.message.text or ""
    user_data_store[user_id].append(text)
    await update.message.reply_text("បានរក្សាទុកបន្ទាត់។ ប្រើ /done ប្រសិនបើរួចរាល់។")

# /done -> build HTML -> PDF -> reply
async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        lines = user_data_store.get(user_id, [])
        if not lines:
            await update.message.reply_text("មិនទាន់មានអត្ថបទទេ។ សូមផ្ញើបន្ទាត់មុនសិន។")
            return

        paragraphs = []
        for idx, raw in enumerate(lines):
            text = (raw or "").strip()
            if not text:
                continue

            # Detect and format markers based on the beginning of the line
            if re.match(r'^\s*(A|អ)\s*\.?', text, flags=re.I):   # A.
                clean = re.sub(r'^\s*(A|អ)\s*\.?\s*', '', text, flags=re.I)
                block = f'<p class="paragraph section lead-A">{clean}</p>'
            elif re.match(r'^\s*ក\s*\.?', text):                  # ក.
                clean = re.sub(r'^\s*ក\s*\.?\s*', '', text)
                block = f'<p class="paragraph point-ka">{clean}</p>'
            elif re.match(r'^\s*([១1])\s*\.?', text):             # ១. or 1.
                clean = re.sub(r'^\s*()\s*\.?\s*', '', text)
                block = f'<p class="paragraph num-1">{clean}</p>'
            else:
                block = f'<p class="paragraph indent">{text}</p>'

            paragraphs.append(block)

        html_content = "\n".join(paragraphs)
        final_html = HTML_TEMPLATE.format(content=html_content)

        # Generate PDF with timeout
        pdf_data = await safe_generate_pdf(final_html, timeout=25)
        pdf_buffer = BytesIO(pdf_data)
        pdf_buffer.seek(0)

        # filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"KHMER_PDF_{timestamp}.pdf"

        # Send file
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=filename,
            caption="✅ សូមអបអរ! PDF រួចរាល់"
        )

        # Clear user buffer
        user_data_store[user_id] = []

    except asyncio.TimeoutError:
        await update.message.reply_text("❌ ការបង្កើត PDF យឺតពេលពេក (timeout). សូមព្យាយាមម្ដងទៀត។")
    except Exception as e:
        await update.message.reply_text(f"❌ មានបញ្ហា: {str(e)}")

# Error handler
async def handle_errors(update: object, context: ContextTypes.DEFAULT_TYPE):
    try:
        raise context.error
    except Exception as e:
        logging.error(f"⚠️ Bot error: {e}")
        if isinstance(update, Update) and getattr(update, "effective_message", None):
            await update.effective_message.reply_text("❌ Bot error occurred, but I'm still alive!")

# Keep-alive job
async def keep_alive(context: ContextTypes.DEFAULT_TYPE):
    logging.info("✅ Keep-alive ping... Bot still running!")

async def on_startup(app: Application):
    app.job_queue.run_repeating(keep_alive, interval=300, first=10)

# Build app
app = Application.builder().token(TOKEN).build()
app.post_init = on_startup

# Handlers
app.add_handler(CommandHandler("start", start_command))
app.add_handler(CommandHandler("done", done_command))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text))
app.add_error_handler(handle_errors)

if __name__ == "__main__":
    logging.info("🚀 Bot Running with Speaker Marker + Timeout Protection...")
    app.run_polling()
