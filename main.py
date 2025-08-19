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

# HTML Template
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="km">
<head>
    <meta charset="utf-8">
    <title>PDF Khmer by TENG SAMBATH</title>
    <style>
        @page {{
            margin-left: 0.40in;
            margin-right: 0.40in;
            margin-top: 0.4in;
            margin-bottom: 0.4in;
        }}
        body {{
            font-family: 'Battambang', 'Noto Sans Khmer', 'Khmer OS', 'Arial', sans-serif;
            font-size: 19px;
            line-height: 2;
            color: #222;
            margin: 0;
            padding: 0;
            word-wrap: break-word;
            overflow-wrap: break-word;
            word-break: keep-all;
        }}
        .content {{
            margin-bottom: 30px;
        }}
        .content p {{
            margin: 0 0 15px 0;
            text-align: left;
        }}
        .footer {{
            color: #666;
            font-size: 10px;
            margin-top: 30px;
            padding-top: 10px;
            border-top: 1px solid #eee;
        }}
    </style>
    <link href="https://fonts.googleapis.com/css2?family=Battambang:wght@400;700&family=Noto+Sans+Khmer:wght@400;700&display=swap" rel="stylesheet">
</head>
<body>
    <div class="content">
        {content}
    </div>
    <div class="footer">
Bot Text2PDF | Teng Sambath
    </div>
</body>
</html>"""

# Application
app = Application.builder().token(TOKEN).build()

# Memory buffer per user
user_data_store = {}

def format_text_with_speaker_markers(text: str) -> str:
    """
    បន្ថែម <br> មុន Speaker markers (A. ក. 1.) ទាំងអស់
    ទោះបីជាមាននៅកណ្តាលប្រយោគក៏ដោយ។
    """
    patterns = [
        r"([A-Z]\.)",     # A. B. ...
        r"([ក-អ]\.)",    # ក. ខ. ...
        r"(\d+\.)"       # 1. 2. ...
    ]
    for pattern in patterns:
        text = re.sub(pattern, r"<br>\1", text)
    return text

async def safe_generate_pdf(html_content: str, timeout: int = 20):
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(lambda: HTML(string=html_content).write_pdf()),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        raise RuntimeError("⏱️ PDF generation timeout!")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data_store[user_id] = []  # reset
    await update.message.reply_text(
        "🇰🇭 BOT បំលែងអត្ថបទទៅជា PDF 🇰🇭 \n\n"
        "📝 សូមផ្ញើអត្ថបទជាផ្នែកៗ (Chunks)\n"
        "➡️ ពេលចប់ សូមវាយ /done ដើម្បីបង្កើត PDF"
    )

async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id not in user_data_store:
        user_data_store[user_id] = []

    if not text.startswith("/"):
        user_data_store[user_id].append(text)
        await update.message.reply_text("📌 អត្ថបទបានរក្សាទុក! បន្តផ្ញើឬវាយ /done ដើម្បីបញ្ចប់។")

async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_data_store or not user_data_store[user_id]:
        await update.message.reply_text("❌ មិនមានអត្ថបទ! សូមផ្ញើអត្ថបទជាមុនសិន។")
        return

    await update.message.reply_text("⏳ សូមរង់ចាំ... កំពុងបង្កើត PDF")

    try:
        # Join all text
        paragraphs = []
        for line in user_data_store[user_id]:
            if line.strip():
                formatted_line = format_text_with_speaker_markers(line.strip())
                paragraphs.append(f"<p>{formatted_line}</p>")

        html_content = "\n        ".join(paragraphs)
        final_html = HTML_TEMPLATE.format(content=html_content)

        # PDF generate with timeout
        pdf_data = await safe_generate_pdf(final_html, timeout=25)
        pdf_buffer = BytesIO(pdf_data)
        pdf_buffer.seek(0)

        # filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"KHMER_PDF_{timestamp}.pdf"

        # send back
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=filename,
            caption="✅ **សូមអបអរ! PDF រួចរាល់**"
        )

        # clear buffer
        user_data_store[user_id] = []

    except Exception as e:
        await update.message.reply_text(f"❌ មានបញ្ហា: {str(e)}")

# Error Handler
async def handle_errors(update: object, context: ContextTypes.DEFAULT_TYPE):
    try:
        raise context.error
    except Exception as e:
        logging.error(f"⚠️ Bot error: {e}")
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text("❌ Bot error occurred, but I'm still alive!")

# Keep alive job
async def keep_alive(context: ContextTypes.DEFAULT_TYPE):
    logging.info("✅ Keep-alive ping... Bot still running!")

job_queue = app.job_queue
job_queue.run_repeating(keep_alive, interval=300, first=10)

# Handlers
app.add_handler(CommandHandler("start", start_command))
app.add_handler(CommandHandler("done", done_command))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text))
app.add_error_handler(handle_errors)

if __name__ == "__main__":
    logging.info("🚀 Bot Running with Speaker Marker + Timeout Protection...")
    app.run_polling()
