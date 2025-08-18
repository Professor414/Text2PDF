import os
import logging
from io import BytesIO
from datetime import datetime
import re
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
    បន្ថែម <br> (ចុះបន្ទាត់) ពេលជួប Speaker markers
    ឧ. A. B. ... Z. ឬ ក. ខ. គ. ... អ.
    """
    # Regex patterns
    patterns = [
        r"(^|\s)([A-Z])\.",   # A. B. ... Z.
        r"(^|\s)([ក-អ])\."   # ក. ខ. គ. ... អ.
    ]
    for pattern in patterns:
        text = re.sub(pattern, r"<br>\2.", text)
    return text

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

    # កុំអោយអ្នកសង្ស័យថា Bot អត់ដំណើរការ
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

        # PDF generate
        pdf_buffer = BytesIO()
        HTML(string=final_html).write_pdf(pdf_buffer)
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

# Handlers
app.add_handler(CommandHandler("start", start_command))
app.add_handler(CommandHandler("done", done_command))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text))

if __name__ == "__main__":
    logging.info("🚀 Bot Running with Speaker Marker Support...")
    app.run_polling()
