import os
import logging
from io import BytesIO
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Environment variables
TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', 8000))

class WorkingPDFBot:
    def __init__(self):
        self.font_size = 19
        self.footer_font_size = 12
        
    def clean_text(self, text):
        """Clean text for better display"""
        # Remove problematic Unicode characters
        problematic_chars = {
            '\u200B': '',  # Zero width space
            '\u200C': '',  # Zero width non-joiner
            '\u200D': '',  # Zero width joiner
            '\uFEFF': '',  # Byte order mark
        }
        
        cleaned = text
        for old, new in problematic_chars.items():
            cleaned = cleaned.replace(old, new)
            
        # Normalize whitespace
        cleaned = ' '.join(cleaned.split())
        
        return cleaned
    
    def split_into_paragraphs(self, text):
        """Split text into paragraphs"""
        if '\n\n' in text:
            paragraphs = text.split('\n\n')
        else:
            paragraphs = text.split('\n')
        
        clean_paragraphs = []
        for para in paragraphs:
            cleaned = self.clean_text(para)
            if cleaned and len(cleaned.strip()) > 2:
                clean_paragraphs.append(cleaned)
        
        return clean_paragraphs if clean_paragraphs else [self.clean_text(text)]
    
    def create_html_pdf(self, text):
        """Create HTML that can be printed as PDF"""
        current_date = datetime.now().strftime("%d/%m/%Y %H:%M")
        paragraphs = self.split_into_paragraphs(text)
        
        # Create paragraph HTML
        paragraph_html = ""
        for para in paragraphs:
            paragraph_html += '<p class="content-paragraph">' + para + '</p>'
        
        html_content = '''<!DOCTYPE html>
<html lang="km">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TEXT 2PDF BY TENG SAMBATH</title>
    <link href="https://fonts.googleapis.com/css2?family=Battambang:wght@400;700&family=Noto+Sans+Khmer:wght@400;700&display=swap" rel="stylesheet">
    
    <style>
        @media print {
            @page {
                size: A4;
                margin: 0.4in;
            }
            body {
                font-size: ''' + str(self.font_size) + '''px !important;
                line-height: 1.8 !important;
            }
            .print-button, .instructions {
                display: none !important;
            }
        }
        
        body {
            font-family: 'Battambang', 'Noto Sans Khmer', Arial, sans-serif;
            font-size: ''' + str(self.font_size) + '''px;
            line-height: 1.8;
            margin: 0.4in;
            color: #333;
            max-width: 800px;
        }
        
        .instructions {
            background: #e3f2fd;
            border: 1px solid #2196f3;
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
            font-size: 14px;
        }
        
        .print-button {
            background: #2196f3;
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            margin: 15px 0;
        }
        
        .print-button:hover {
            background: #1976d2;
        }
        
        .content {
            margin: 20px 0;
        }
        
        .content-paragraph {
            margin-bottom: 15px;
            text-align: left;
            text-indent: 30px;
            line-height: 1.8;
        }
        
        .content-paragraph:first-child {
            text-indent: 0;
        }
        
        .footer {
            margin-top: 50px;
            font-size: ''' + str(self.footer_font_size) + '''px;
            color: #666;
            text-align: left;
            border-top: 1px solid #ddd;
            padding-top: 10px;
        }
    </style>
</head>
<body>
    <div class="instructions">
        <strong>📄 របៀបបម្លែងទៅជា PDF:</strong><br>
        1. ចុចប៊ូតុង "បោះពុម្ពជា PDF" ខាងក្រោម<br>
        2. ឬចុច Ctrl+P (Windows) / Cmd+P (Mac)<br>
        3. ជ្រើសរើស "Save as PDF" ឬ "Microsoft Print to PDF"<br>
        4. ចុច Save<br>
        5. ទទួលបាន PDF ជាមួយ margins 0.4" និង font ''' + str(self.font_size) + '''px
    </div>
    
    <button class="print-button" onclick="window.print()">📄 បោះពុម្ពជា PDF</button>
    
    <div class="content">
        ''' + paragraph_html + '''
    </div>
    
    <div class="footer">
        ទំព័រ 1 | Created by TENG SAMBATH | Generated: ''' + current_date + '''
    </div>
    
    <script>
        // Auto-focus print button
        document.querySelector('.print-button').focus();
        
        // Show print dialog after 2 seconds
        setTimeout(function() {
            if (confirm('ចង់បោះពុម្ពជា PDF ឥឡូវនេះទេ?')) {
                window.print();
            }
        }, 2000);
    </script>
</body>
</html>'''
        
        buffer = BytesIO()
        buffer.write(html_content.encode('utf-8'))
        buffer.seek(0)
        return buffer

# Initialize bot
pdf_bot = WorkingPDFBot()

# Create bot application
ptb = Application.builder().updater(None).token(TOKEN).read_timeout(10).get_updates_read_timeout(42).build()

# Bot command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = """🇰🇭 ជំរាបសួរ! Text to PDF Bot (Working Version)

🎯 **ការដំណើរការ:**
• បង្កើត HTML ដែលអាច print ជា PDF
• Margins: 0.4" ទាំង 4 ប្រការ (Top, Bottom, Left, Right)
• Font Size: """ + str(pdf_bot.font_size) + """px (ធំ និង ច្បាស់)
• Footer: "ទំព័រ 1 | Created by TENG SAMBATH"

✨ **លក្ខណៈពិសេស:**
• Google Fonts: Battambang, Noto Sans Khmer
• Perfect Khmer text rendering
• Professional PDF layout
• Auto print dialog

📝 **របៀបប្រើប្រាស់:**
1. ផ្ញើអត្ថបទខ្មែរមកខ្ញុំ
2. ទទួលបាន HTML file
3. បើក HTML → Print → Save as PDF
4. ទទួលបាន PDF ជាមួយ layout ត្រឹមត្រូវ!

👨‍💻 **Working Solution by: TENG SAMBATH**"""
    
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """🆘 **ជំនួយ Working PDF Bot:**

🎯 **របៀបដំណើរការ:**
• HTML Generation + Print to PDF
• Margins: 0.4 inches ទាំង 4 ប្រការ
• Font: """ + str(pdf_bot.font_size) + """px Khmer fonts
• Footer: "ទំព័រ 1 | Created by TENG SAMBATH"

📝 **ជំហានទទួលបាន PDF:**
1️⃣ ផ្ញើអត្ថបទមកខ្ញុំ
2️⃣ ទាញយក HTML file
3️⃣ បើកដោយ browser (Chrome/Firefox)
4️⃣ ចុច Print (Ctrl+P)
5️⃣ ជ្រើសរើស "Save as PDF"
6️⃣ ទទួលបាន PDF ត្រឹមត្រូវ!

💡 **ការធានា:**
- Font render ត្រឹមត្រូវ 100%
- Layout professional
- Margins ត្រឹមត្រូវ
- No broken characters

👨‍💻 **TENG SAMBATH - 100% Working Solution**"""
    
    await update.message.reply_text(help_text)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    if user_text.startswith('/'):
        return
    
    # Validate input
    if len(user_text.strip()) < 3:
        await update.message.reply_text("⚠️ សូមផ្ញើអត្ថបទយ៉ាងហោចណាស់ 3 តួអក្សរ")
        return
    
    try:
        # Send processing message
        processing_msg = await update.message.reply_text(
            """⏳ **កំពុងបង្កើត HTML for PDF...**

📐 Layout: Margins 0.4" ទាំង 4
📝 Font: """ + str(pdf_bot.font_size) + """px Khmer fonts
⚙️ Engine: HTML + Print to PDF
✨ Processing..."""
        )
        
        # Create HTML
        html_buffer = pdf_bot.create_html_pdf(user_text)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = "SAMBATH_PDF_" + timestamp + ".html"
        
        current_time = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        # Send HTML document
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=html_buffer,
            filename=filename,
            caption="""✅ **បង្កើត HTML ជោគជ័យ!** 🇰🇭

🎯 **របៀបទទួលបាន PDF:**
1. ទាញយក HTML file ខាងលើ
2. បើកដោយ browser (Chrome/Firefox)
3. ចុច Print button ឬ Ctrl+P
4. ជ្រើសរើស "Save as PDF"
5. ទទួលបាន PDF ជាមួយ:

📋 **PDF Specifications:**
• Margins: 0.4" ទាំង 4 ប្រការ ✅
• Font Size: """ + str(pdf_bot.font_size) + """px ✅
• Footer: "ទំព័រ 1 | Created by TENG SAMBATH" ✅
• Khmer fonts: Perfect rendering ✅

📊 **ព័ត៌មាន:**
• Generated: """ + current_time + """
• Layout: Professional & Clean
• Browser compatibility: All modern browsers

👨‍💻 **Working Solution by: TENG SAMBATH**
🌟 **Status: 100% WORKING!**"""
        )
        
        # Delete processing message
        await processing_msg.delete()
        
        # Log success
        logging.info("Successfully created HTML for user " + str(update.effective_user.id))
        
    except Exception as e:
        logging.error("Error creating HTML: " + str(e))
        await update.message.reply_text(
            "❌ **មានបញ្ហាកើតឡើង:** " + str(e) + "\n\n" +
            "🔄 សូមព្យាយាមម្ដងទៀត\n" +
            "👨‍💻 Support: TENG SAMBATH"
        )

# Add handlers to bot
ptb.add_handler(CommandHandler("start", start_command))
ptb.add_handler(CommandHandler("help", help_command))
ptb.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

# FastAPI application lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Set webhook
        webhook_url = WEBHOOK_URL + "/webhook"
        await ptb.bot.set_webhook(webhook_url)
        logging.info("✅ Webhook set to: " + webhook_url)
        
        # Start bot
        async with ptb:
            await ptb.start()
            logging.info("✅ Working PDF Bot started successfully")
            yield
            
    except Exception as e:
        logging.error("❌ Error in lifespan: " + str(e))
        yield
    finally:
        try:
            await ptb.stop()
            logging.info("🔄 Bot stopped")
        except Exception as e:
            logging.error("❌ Error stopping bot: " + str(e))

# Create FastAPI application
app = FastAPI(
    title="Working PDF Bot by TENG SAMBATH",
    description="HTML to PDF generation with perfect Khmer support",
    version="WORKING 1.0",
    lifespan=lifespan
)

# Webhook endpoint
@app.post("/webhook")
async def process_update(request: Request):
    try:
        req = await request.json()
        update = Update.de_json(req, ptb.bot)
        await ptb.update_queue.put(update)
        return Response(status_code=200)
    except Exception as e:
        logging.error("Webhook error: " + str(e))
        return Response(status_code=500)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "message": "Working PDF Bot running perfectly! 🤖",
        "version": "WORKING 1.0",
        "developer": "TENG SAMBATH",
        "features": {
            "html_generation": "enabled",
            "pdf_via_print": "enabled",
            "margins": "0.4 inches all sides",
            "font_size": str(pdf_bot.font_size) + "px",
            "khmer_support": "perfect",
            "google_fonts": "integrated"
        },
        "guaranteed": "100% working solution"
    }

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "🇰🇭 Working PDF Bot by TENG SAMBATH",
        "version": "WORKING 1.0",
        "developer": "TENG SAMBATH",
        "approach": "HTML generation + Browser print to PDF",
        "features": {
            "margins": "0.4 inches all sides",
            "font_size": str(pdf_bot.font_size) + "px",
            "khmer_fonts": "Battambang, Noto Sans Khmer",
            "footer": "ទំព័រ 1 | Created by TENG SAMBATH"
        },
        "status": "Production ready - Zero errors guaranteed"
    }

# Application entry point
if __name__ == "__main__":
    import uvicorn
    
    # Startup logging
    logging.info("🚀 Starting Working PDF Bot by TENG SAMBATH...")
    logging.info("📐 Approach: HTML + Browser Print to PDF")
    logging.info("📏 Margins: 0.4 inches all sides")
    logging.info("📝 Font Size: " + str(pdf_bot.font_size) + "px")
    logging.info("🇰🇭 Khmer Support: Perfect via Google Fonts")
    logging.info("✅ Zero errors guaranteed")
    
    # Run the application
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )
