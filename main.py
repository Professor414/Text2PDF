import os
import logging
from io import BytesIO
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from weasyprint import HTML

# Configure logging
logging.basicConfig(level=logging.INFO)

# Environment variable
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Please set BOT_TOKEN as environment variable.")

# HTML Template (Updated formatting)
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="km">
<head>
    <meta charset="utf-8">
    <title>PDF Khmer by TENG SAMBATH</title>
    <style>
        @page {{
            margin-left: 0.35in;
            margin-right: 0.35in;
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
        ទំព័រ 1 | Created by TENG SAMBATH
    </div>
</body>
</html>"""

# Create application
app = Application.builder().token(TOKEN).build()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    await update.message.reply_text(
        "🇰🇭 **PDF Khmer Bot** - Auto PDF Generator\n\n"
        "✅ **Features:**\n"
        "• Auto convert text to PDF (no HTML, no browser)\n" 
        "• Perfect Khmer font shaping\n"
        "• Margins: Left/Right 0.35\", Top/Bottom 0.4\"\n"
        "• Font: 19px Battambang/Noto Sans Khmer\n"
        "• Footer: ទំព័រ 1 | Created by TENG SAMBATH\n\n"
        "📝 **Usage:** Just send any text, get PDF back instantly!\n\n"
        "👨‍💻 **By: TENG SAMBATH**"
    )

async def convert_text_to_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Convert text to PDF and send back"""
    try:
        # Get user text
        user_text = update.message.text.strip()
        
        # Skip commands
        if user_text.startswith('/'):
            return
            
        # Process text into HTML paragraphs
        paragraphs = []
        lines = user_text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        
        for line in lines:
            line = line.strip()
            if line:  # Only add non-empty lines
                paragraphs.append(f"<p>{line}</p>")
        
        # Create HTML content
        html_content = '\n        '.join(paragraphs)
        final_html = HTML_TEMPLATE.format(content=html_content)
        
        # Generate PDF using WeasyPrint
        pdf_buffer = BytesIO()
        HTML(string=final_html).write_pdf(pdf_buffer)
        pdf_buffer.seek(0)
        
        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"KHMER_PDF_{timestamp}.pdf"
        
        # Send PDF to user
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=filename,
            caption="✅ **PDF បង្កើតជោគជ័យ!**\n\n"
                   "📐 Margins: Left/Right 0.35\", Top/Bottom 0.4\"\n"
                   "📝 Font: 19px Khmer fonts with perfect shaping\n"
                   "🎯 Ready to use - no conversion needed!\n\n"
                   "👨‍💻 **Created by: TENG SAMBATH**"
        )
        
        # Log success
        logging.info(f"PDF created successfully for user {update.effective_user.id}")
        
    except Exception as e:
        # Comprehensive error handling
        import traceback
        error_details = traceback.format_exc()
        
        # Log the error
        logging.error(f"PDF generation failed: {str(e)}\n{error_details}")
        
        # Send user-friendly error message
        await update.message.reply_text(
            f"❌ **មានបញ្ហាក្នុងការបង្កើត PDF!**\n\n"
            f"**Error:** {str(e)}\n\n"
            f"🔄 សូមព្យាយាមម្តងទៀត ឬ ផ្ញើអត្ថបទខ្លីៗជាមុន\n"
            f"💡 ប្រសិនបើបញ្ហានៅតែកើត សូមទាក់ទង admin\n\n"
            f"👨‍💻 **Support: TENG SAMBATH**"
        )

# Add handlers
app.add_handler(CommandHandler("start", start_command))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, convert_text_to_pdf))

# Main function
if __name__ == "__main__":
    try:
        logging.info("🚀 Starting PDF Khmer Bot by TENG SAMBATH...")
        logging.info("✅ WeasyPrint PDF generation ready")
        logging.info("📐 Margins: Left/Right 0.35\", Top/Bottom 0.4\"")
        logging.info("📝 Font: 19px Khmer fonts")
        logging.info("🎯 Auto PDF conversion enabled")
        
        # Run bot with polling
        app.run_polling()
        
    except Exception as e:
        logging.error(f"Failed to start bot: {e}")
        raise
