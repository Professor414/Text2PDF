import os
import logging
from io import BytesIO
from datetime import datetime
from collections import defaultdict  # NEW
import re  # NEW

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from weasyprint import HTML
from flask import Flask
from threading import Thread

# --- ផ្នែក Web Server ដើម្បីឲ្យ Deploy ដំណើរការ ---
server = Flask('')

@server.route('/')
def home():
    return "Bot is alive!"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server.run(host='0.0.0.0', port=port)

flask_thread = Thread(target=run_server)
# --- ចប់ផ្នែក Web Server ---

# កំណត់ Logging
logging.basicConfig(level=logging.INFO)

# Variable បរិស្ថាន
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("សូមកំណត់ BOT_TOKEN ជា environment variable មុនចាប់ផ្តើម។")

# HTML Template (Khmer PDF)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="km">
<head>
<meta charset="utf-8">
<style>
  @page { size: A4; margin: 0.4in 0.35in; }
  body { font-family: 'Khmer OS Battambang','Noto Sans Khmer','Noto Serif Khmer',sans-serif; font-size: 19px; line-height: 1.6; }
  p { margin: 0 0 8px 0; white-space: pre-wrap; }
</style>
</head>
<body>
{content}
</body>
</html>
"""

# =========================
# NEW: Session buffer logic
# =========================
chat_buffers = defaultdict(list)  # chat_id -> [str, str, ...]

def _normalize_text(s: str) -> str:
    s = s.replace('\r\n', '\n').replace('\r', '\n')
    # កាត់បន្ថយខ្សែទទេ 3+ ជា 2
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()

def append_to_buffer(chat_id: int, text: str):
    text = _normalize_text(text)
    if text:
        chat_buffers[chat_id].append(text)

def clear_buffer(chat_id: int):
    if chat_id in chat_buffers:
        del chat_buffers[chat_id]

def get_buffer_text(chat_id: int) -> str:
    parts = chat_buffers.get(chat_id, [])
    return ("\n\n".join(parts)).strip() if parts else ""

# =========================
# Handlers ដើម (ត្រូវមាន start_command ដូចដើម)
# =========================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "សូមស្វាគមន៍!\n"
        "ផ្ញើអត្ថបទមកជាបន្តបន្ទាប់ ហើយពេលរួច សូមសរសេរ /done ដើម្បីបំលែងជា PDF មួយ។"
    )

# =========================
# NEW: Message collector
# =========================
async def collect_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ជំនួសការបំលែងភ្លាមៗ៖ ប្រមូលសារ​ទៅ buffer រហូតដល់ /done
    """
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()

    # បើអ្នកប្រើវាយពាក្យ "រួច" "done" ជាអក្សរ​ធម្មតា ក៏អាចបញ្ចប់បានដែរ
    if text in {"រួច", "រួចហើយ", "done", "finish", "end"}:
        return await done_command(update, context)

    append_to_buffer(chat_id, text)
    total_chars = len(get_buffer_text(chat_id))
    await update.message.reply_text(
        f"✅ បានទទួល! បច្ចុប្បន្នប្រមូល {total_chars} តួអក្សរ.\n"
        f"➡️ ពេលរួច សរសេរ /done ដើម្បីបំលែងជា PDF មួយ។"
    )

# =========================
# NEW: /done command
# =========================
async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    បំលែងអត្ថបទទាំងអស់ក្នុង buffer ជា PDF មួយ បន្ទាប់មកសម្អាត buffer
    """
    chat_id = update.effective_chat.id
    user_text = get_buffer_text(chat_id)

    if not user_text:
        return await update.message.reply_text("⚠️ មិនមានអត្ថបទក្នុង buffer ទេ។ សូមផ្ញើអត្ថបទមុន!")

    try:
        # ប្រែអត្ថបទជាបន្ទាត់ៗ
        paragraphs = []
        lines = user_text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        for line in lines:
            line = line.strip()
            if line:
                paragraphs.append(f"<p>{line}</p>")

        html_content = '\n '.join(paragraphs)
        final_html = HTML_TEMPLATE.format(content=html_content)

        pdf_buffer = BytesIO()
        HTML(string=final_html).write_pdf(pdf_buffer)
        pdf_buffer.seek(0)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"KHMER_PDF_{timestamp}.pdf"

        await context.bot.send_document(
            chat_id=chat_id,
            document=pdf_buffer,
            filename=filename,
            caption="✅ បានរួមសារ Telegram ជា PDF មួយរួចរាល់!"
        )

        logging.info(f"PDF បង្កើតជោគជ័យសម្រាប់ chat {chat_id}")
        await update.message.reply_text("📄 PDF រួច! ✅")
    except Exception as e:
        import traceback
        logging.error(f"បង្កើត PDF បរាជ័យ: {e}\n{traceback.format_exc()}")
        await update.message.reply_text(f"❌ មានបញ្ហាក្នុងការបង្កើត PDF: {e}")
    finally:
        clear_buffer(chat_id)

# =========================
# Application setup ដើម
# =========================
app = Application.builder().token(TOKEN).build()

# Add Handlers
app.add_handler(CommandHandler("start", start_command))

# NEW: បន្ថែមពាក្យបញ្ជា /done
app.add_handler(CommandHandler("done", done_command))  # NEW

# NEW: ប្រមូលសារ text ទាំងអស់ជាទូទៅ
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, collect_text))  # NEW

# Main Run
if __name__ == "__main__":
    try:
        logging.info("🚀 កំពុងចាប់ផ្តើម PDF Khmer Bot by TENG SAMBATH...")

        # ចាប់ផ្តើម Web Server នៅក្នុង Thread (ដើម)
        flask_thread.start()

        logging.info("✅ WeasyPrint PDF generation ready")
        logging.info("📐 Margins: Left/Right 0.35\", Top/Bottom 0.4\"")
        logging.info("📝 Font: 19px Khmer fonts")
        logging.info("🎯 Auto PDF conversion enabled")

        # ចាប់ផ្តើម Bot (ដើម)
        app.run_polling()

    except Exception as e:
        logging.error(f"មិនអាចចាប់ផ្តើម Bot បានទេ: {e}")
        raise
