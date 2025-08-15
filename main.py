import os
import logging
from io import BytesIO
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Environment variables
TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # https://your-app.onrender.com
PORT = int(os.getenv('PORT', 8000))

# Register Khmer font (optional)
try:
    pdfmetrics.registerFont(TTFont('Battambang', 'font/Battambang-Regular.ttf'))
    FONT_NAME = 'Battambang'
    logging.info("Khmer font loaded successfully")
except:
    FONT_NAME = 'Helvetica'
    logging.warning("Using default font - Khmer font not found")

# Create bot application
ptb = (
    Application.builder()
    .updater(None)  # ប្រើ webhook, មិនមែន polling
    .token(TOKEN)
    .read_timeout(7)
    .get_updates_read_timeout(42)
    .build()
)

class TextToPDFBot:
    def create_pdf_from_text(self, text: str) -> BytesIO:
        """បង្កើត PDF ពីអត្ថបទ"""
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        
        width, height = A4
        margin = 50
        font_size = 12
        p.setFont(FONT_NAME, font_size)
        
        # Simple text wrapping
        lines = text.split('\n')
        y_position = height - margin
        
        for line in lines:
            if y_position < margin:
                p.showPage()
                p.setFont(FONT_NAME, font_size)
                y_position = height - margin
            
            # Handle long lines
            if len(line) > 80:
                words = line.split(' ')
                current_line = ''
                for word in words:
                    test_line = current_line + ' ' + word if current_line else word
                    if len(test_line) <= 80:
                        current_line = test_line
                    else:
                        if current_line:
                            p.drawString(margin, y_position, current_line)
                            y_position -= font_size + 4
                            current_line = word
                        if y_position < margin:
                            p.showPage()
                            p.setFont(FONT_NAME, font_size)
                            y_position = height - margin
                
                if current_line:
                    p.drawString(margin, y_position, current_line)
                    y_position -= font_size + 4
            else:
                p.drawString(margin, y_position, line)
                y_position -= font_size + 4
        
        p.save()
        buffer.seek(0)
        return buffer

pdf_bot = TextToPDFBot()

# Bot handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = """🇰🇭 ជំរាបសួរ! ខ្ញុំជា Text to PDF Bot

📝 របៀបប្រើប្រាស់:
• ផ្ញើអត្ថបទខ្មែរមកខ្ញុំ
• ខ្ញុំនឹងបម្លែងវាទៅជាឯកសារ PDF
• ទាញយកឯកសារបាន

🔧 ពាក្យបញ្ជា:
/help - ជំនួយលម្អិត
/start - ចាប់ផ្ដើមម្ដងទៀត"""
    
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """🆘 ជំនួយការប្រើប្រាស់:

1️⃣ ផ្ញើអត្ថបទខ្មែរ ឬ អង់គ្លេសមកខ្ញុំ
2️⃣ រង់ចាំខ្ញុំបម្លែងទៅជា PDF
3️⃣ ទាញយកឯកសារ PDF

✨ លក្ខណៈពិសេស:
• គាំទ្រអត្ថបទវែង
• គាំទ្រអក្សរខ្មែរ
• លេខ PDF លំដាប់

💡 ជំនួយបន្ថែម: @your_support_bot"""
    
    await update.message.reply_text(help_text)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    if user_text.startswith('/'):
        return
    
    # Check text length
    if len(user_text.strip()) < 3:
        await update.message.reply_text("⚠️ សូមផ្ញើអត្ថបទដែលមានយ៉ាងហោចណាស់ 3 តួអក្សរ")
        return
    
    try:
        # Send processing message
        processing_msg = await update.message.reply_text("⏳ កំពុងបម្លែងអត្ថបទទៅជា PDF...")
        
        # Create PDF
        pdf_buffer = pdf_bot.create_pdf_from_text(user_text)
        
        # Send PDF document
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=f"khmer_text_{update.effective_user.id}_{update.message.message_id}.pdf",
            caption="✅ ការបម្លែងអត្ថបទទៅជា PDF បានជោគជ័យ! 🇰🇭\n\n📄 អ្នកអាចទាញយកឯកសារនេះបាន"
        )
        
        # Delete processing message
        await processing_msg.delete()
        
    except Exception as e:
        logging.error(f"Error processing text: {str(e)}")
        await update.message.reply_text(
            f"❌ មានបញ្ហាកើតឡើង: {str(e)}\n\n🔄 សូមព្យាយាមម្ដងទៀត ឬ ទាក់ទងអ្នកគ្រប់គ្រង"
        )

# Add handlers
ptb.add_handler(CommandHandler("start", start_command))
ptb.add_handler(CommandHandler("help", help_command))
ptb.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

# FastAPI app lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    try:
        # Set webhook
        webhook_url = f"{WEBHOOK_URL}/webhook"
        await ptb.bot.set_webhook(webhook_url)
        logging.info(f"Webhook set to: {webhook_url}")
        
        # Start the application
        async with ptb:
            await ptb.start()
            logging.info("Bot started successfully")
            yield
            
    except Exception as e:
        logging.error(f"Error in lifespan: {str(e)}")
        yield
    finally:
        # Stop the application
        try:
            await ptb.stop()
            logging.info("Bot stopped")
        except Exception as e:
            logging.error(f"Error stopping bot: {str(e)}")

# Create FastAPI app
app = FastAPI(
    title="Text to PDF Khmer Bot",
    description="Telegram Bot for converting Khmer text to PDF",
    version="1.0.0",
    lifespan=lifespan
)

@app.post("/webhook")
async def process_update(request: Request):
    """ដោះស្រាយ updates ពី Telegram"""
    try:
        req = await request.json()
        update = Update.de_json(req, ptb.bot)
        await ptb.update_queue.put(update)
        return Response(status_code=200)
    except Exception as e:
        logging.error(f"Webhook error: {str(e)}")
        return Response(status_code=500)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "message": "Text to PDF Bot is running! 🤖",
        "version": "1.0.0",
        "features": ["Khmer text support", "PDF generation", "Webhook enabled"]
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "🇰🇭 Text to PDF Khmer Bot API",
        "status": "running",
        "endpoints": {
            "webhook": "/webhook",
            "health": "/health"
        },
        "bot_info": "Send text to @your_bot_username on Telegram"
    }

@app.get("/info")
async def bot_info():
    """Bot information endpoint"""
    try:
        bot = ptb.bot
        bot_info = await bot.get_me()
        return {
            "bot_name": bot_info.first_name,
            "bot_username": f"@{bot_info.username}",
            "bot_id": bot_info.id,
            "webhook_url": f"{WEBHOOK_URL}/webhook"
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    
    # Log startup information
    logging.info("Starting Text to PDF Khmer Bot...")
    logging.info(f"PORT: {PORT}")
    logging.info(f"WEBHOOK_URL: {WEBHOOK_URL}")
    
    # Run the application
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=PORT,
        log_level="info"
    )
