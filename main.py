import os
import logging
from io import BytesIO
from datetime import datetime
import re
import html
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from weasyprint import HTML

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

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
# <--- ការកែប្រែទី១៖ បន្ថែម read_timeout និង connect_timeout ដើម្បីការពារការផ្តាច់ (Timeout)
app = Application.builder().token(TOKEN).read_timeout(30).connect_timeout(30).build()

# Memory buffer per user
user_data_store = {}

def format_text_for_pdf(text: str) -> str: # <--- ប្តូរឈ្មោះ Function ឱ្យកាន់តែច្បាស់
    """
    បន្ថែម <br> ចុះបន្ទាត់ និង Highlight ពណ៌លឿងនៅពីមុខ Marker
    A. B. ... / ក. ខ. ... / 1. 2. ... / ១. ២. ...
    """
    # <--- ការកែប្រែទី២៖ បន្ថែម <span> សម្រាប់ Highlight ពណ៌លឿង
    highlight_style = 'style="background-color: yellow;"'
    
    patterns = [
        (r"(?m)^(\s*)([A-Z])\.", rf'<br>\1<span {highlight_style}>\2.</span>'),       # A. B. ...
        (r"(?m)^(\s*)([ក-ឳ])\.", rf'<br>\1<span {highlight_style}>\2.</span>'),      # ក. ខ. ...
        (r"(?m)^(\s*)([0-9]+)\.", rf'<br>\1<span {highlight_style}>\2.</span>'),      # 1. 2. ...
        (r"(?m)^(\s*)([១-៩]+)\.", rf'<br>\1<span {highlight_style}>\2.</span>')       # ១. ២. ...
    ]
    
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)
        
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
        full_text = "\n".join(user_data_store[user_id])
        escaped_text = html.escape(full_text)
        
        # ហៅ Function ដែលបានកែប្រែរួច
        formatted_with_markers = format_text_for_pdf(escaped_text)
        
        html_content = formatted_with_markers.replace('\n', '<br>\n')
        final_html = HTML_TEMPLATE.format(content=html_content)

        pdf_buffer = BytesIO()
        HTML(string=final_html).write_pdf(pdf_buffer)
        pdf_buffer.seek(0)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"KHMER_PDF_{timestamp}.pdf"

        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=filename,
            caption="✅ **សូមអបអរ! PDF រួចរាល់**"
        )
        user_data_store[user_id] = []

    except Exception as e:
        logger.error(f"Error creating PDF for user {user_id}: {e}", exc_info=True)
        await update.message.reply_text(f"❌ មានបញ្ហាធ្ងន់ធ្ងរកើតឡើង៖ {str(e)}")

# <--- ការកែប្រែទី៣៖ បន្ថែម Error Handler ដើម្បីការពារ Bot ពីការគាំង (crash)
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    # អ្នកអាចបន្ថែមការส่งข้อความแจ้งเตือนទៅកាន់ ID របស់អ្នកផ្ទាល់នៅត្រង់នេះ
    # if isinstance(context.error, Exception):
    #     await context.bot.send_message(chat_id=YOUR_ADMIN_ID, text=f"Bot error: {context.error}")

# Handlers
app.add_handler(CommandHandler("start", start_command))
app.add_handler(CommandHandler("done", done_command))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text))

# បន្ថែម Error handler ទៅក្នុង Application
app.add_error_handler(error_handler)

if __name__ == "__main__":
    logger.info("🚀 Bot is running with Highlight, Timeout, and Error Handling support...")
    # Polling ជាមួយ Timeout ដែលបានកំណត់
    app.run_polling()
