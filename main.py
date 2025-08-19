import os
import logging
from io import BytesIO
from datetime import datetime
import re
import html # បន្ថែម import នេះ
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
    បន្ថែម <br> ចុះបន្ទាត់ តែពេល Marker នៅដើមបន្ទាត់ (Line start) ប៉ុណ្ណោះ
    A. B. ... / ក. ខ. ... / 1. 2. ... / ១. ២. ...
    """
    patterns = [
        r"(?m)^(?:\s*)([A-Z])\.",       # A. B. ...
        r"(?m)^(?:\s*)([ក-ឳ])\.",      # ក. ខ. ...
        r"(?m)^(?:\s*)([0-9]+)\.",      # 1. 2. ...
        r"(?m)^(?:\s*)([១-៩]+)\."       # ១. ២. ...
    ]
    for pattern in patterns:
        text = re.sub(pattern, r"<br>\1.", text)
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

    await update.message.reply_text("⏳ សូមរង់ចាំ... កំពុងបង្កើត PDF")

    try:
        # --- START: កែប្រែតក្កវិជ្ជាត្រង់នេះ ---
        
        # 1. ប្រមូលគ្រប់អត្ថបទដែលបានផ្ញើ បញ្ចូលទៅក្នុង string តែមួយ ដោយបំបែកបន្ទាត់ដោយ (\n)
        full_text = "\n".join(user_data_store[user_id])
        
        # 2. ការពារកូដ HTML ដែលអ្នកប្រើអាចបញ្ចូលដោយចៃដន្យ
        escaped_text = html.escape(full_text)
        
        # 3. ប្រើ function ដែលមានស្រាប់ ដើម្បីបន្ថែម <br> នៅពីមុខបញ្ជីរាយ (ក., A., 1., ១.)
        formatted_with_markers = format_text_with_speaker_markers(escaped_text)
        
        # 4. បំលែងរាល់ការចុះបន្ទាត់ (\n) ទៅជា <br> សម្រាប់ HTML
        html_content = formatted_with_markers.replace('\n', '<br>\n')

        # --- END: កែប្រែតក្កវិជ្ជាត្រង់នេះ ---

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
