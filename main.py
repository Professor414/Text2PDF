import os
import logging
from io import BytesIO
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from weasyprint import HTML
from flask import Flask
from threading import Thread

# --- ផ្នែក Web Server ដើម្បីឲ្យ Deploy ដំណើរការ ---
# បង្កើត Flask App
server = Flask('')

# បង្កើត Route មេ ('/')
@server.route('/')
def home():
    return "Bot is alive!"

# បង្កើត Function ដើម្បីឲ្យ Server ដំណើរការ
def run_server():
  port = int(os.environ.get("PORT", 10000))
  server.run(host='0.0.0.0', port=port)

# ដំណើរការ Server នៅក្នុង Thread ផ្សេង
flask_thread = Thread(target=run_server)
# --- ចប់ផ្នែក Web Server ---


# កំណត់ Logging
logging.basicConfig(level=logging.INFO)

# Variable បរិស្ថាន
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("សូមកំណត់ BOT_TOKEN ជា environment variable មុនចាប់ផ្តើម។")

# HTML Template (Khmer PDF)
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

# បង្កើត Bot Application
app = Application.builder().token(TOKEN).build()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ពេលអ្នកចាប់ផ្តើម (/start)"""
    await update.message.reply_text(
        "🇰🇭 BOT បំលែងអត្ថបទទៅជា PDF 🇰🇭 \n\n"
        "📝 របៀបប្រើប្រាស់: ផ្ញើអត្ថបទរបសអ្នកមកកាន់ Bot \n"
        "បន្ទាប់ពីនោះ Bot នឹងផ្ញើ PDF ត្រឡប់ទៅភ្លាមៗ!\n\n"
        "• សូមរីករាយ! ក្នុងការប្រើប្រាស់ ៖ https://t.me/ts_4699"
    )

async def convert_text_to_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """បំលែងអត្ថបទទៅ PDF ហើយផ្ញើត្រឡប់ទៅអ្នកប្រើប្រាស់"""
    try:
        # ទទួលអត្ថបទពីអ្នកប្រើ
        user_text = update.message.text.strip()
        
        # មិនអនុវត្តលើ Command
        if user_text.startswith('/'):
            return
            
        # បំបែកអត្ថបទជាបន្ទាត់ <p>
        paragraphs = []
        lines = user_text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        
        for line in lines:
            line = line.strip()
            if line:  # បន្ថែមតែបន្ទាត់ដែលមានអត្ថបទ
                paragraphs.append(f"<p>{line}</p>")
        
        # បង្កើត HTML
        html_content = '\n        '.join(paragraphs)
        final_html = HTML_TEMPLATE.format(content=html_content)
        
        # បង្កើត PDF ដោយប្រើ WeasyPrint
        pdf_buffer = BytesIO()
        HTML(string=final_html).write_pdf(pdf_buffer)
        pdf_buffer.seek(0)
        
        # កំណត់ឈ្មោះ File
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"KHMER_PDF_{timestamp}.pdf"
        
        # ផ្ញើ PDF ត្រឡប់ទៅអ្នកប្រើ
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=filename,
            caption="✅ **សូមអបអរ អត្ថបទរបស់អ្នករួចរាល់!**\n\n"
                    "• សូមរីករាយ! ក្នុងការប្រើប្រាស់ ៖ https://t.me/ts_4699"
        )
        
        # កត់ត្រា Success
        logging.info(f"PDF បង្កើតជោគជ័យសម្រាប់អ្នកប្រើ {update.effective_user.id}")
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logging.error(f"បង្កើត PDF បរាជ័យ: {str(e)}\n{error_details}")
        
        await update.message.reply_text(
            f"❌ **មានបញ្ហាក្នុងការបង្កើត PDF!**\n\n"
            f"**កំហុស:** {str(e)}\n\n"
            f"🔄 សូមព្យាយាមម្ដងទៀត ឬ ផ្ញើអត្ថបទខ្លីជាមុន\n"
            f"💡 ប្រសិនបើបញ្ហានៅតែកើត សូមទំនាក់ទំនងមកកាន់ខ្ញ\n\n"
            f"👨‍💻 **ជំនួយ: TENG SAMBATH**"
        )

# Add Handlers
app.add_handler(CommandHandler("start", start_command))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, convert_text_to_pdf))

# Main Run
if __name__ == "__main__":
    try:
        logging.info("🚀 កំពុងចាប់ផ្តើម PDF Khmer Bot by TENG SAMBATH...")
        
        # ចាប់ផ្តើម Web Server នៅក្នុង Thread
        flask_thread.start()
        
        logging.info("✅ WeasyPrint PDF generation ready")
        logging.info("📐 Margins: Left/Right 0.35\", Top/Bottom 0.4\"")
        logging.info("📝 Font: 19px Khmer fonts")
        logging.info("🎯 Auto PDF conversion enabled")
        
        # ចាប់ផ្តើម Bot
        app.run_polling()
        
    except Exception as e:
        logging.error(f"មិនអាចចាប់ផ្តើម Bot បានទេ: {e}")
        raise
