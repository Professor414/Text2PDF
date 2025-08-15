import os
import logging
from io import BytesIO
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Environment variables
TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # https://your-app.onrender.com
PORT = int(os.getenv('PORT', 8000))

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
        
        # Simple text wrapping
        lines = text.split('\n')
        y_position = height - margin
        
        for line in lines:
            if y_position < margin:
                p.showPage()
                y_position = height - margin
            
            p.drawString(margin, y_position, line)
            y_position -= font_size + 4
        
        p.save()
        buffer.seek(0)
        return buffer

pdf_bot = TextToPDFBot()

# Bot handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = """
    🇰🇭 សួស្តី! ខ្ញុំជា Text to PDF Bot

    📝 របៀបប្រើប្រាស់:
    • ផ្ញើអត្ថបទមកខ្ញុំ
    • ខ្ញុំនឹងបម្លែងវាទៅជាឯកសារ PDF
    
    /help - ជំនួយ
    """
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = "🆘 ផ្ញើអត្ថបទណាមួយមកខ្ញុំ ហើយខ្ញុំនឹងបម្លែងវាទៅជា PDF!"
    await update.message.reply_text(help_text)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    if user_text.startswith('/'):
        return
    
    try:
        await update.message.reply_text("⏳ កំពុងបម្លែងអត្ថបទទៅជា PDF...")
        
        # បង្កើត PDF
        pdf_buffer = pdf_bot.create_pdf_from_text(user_text)
        
        # ផ្ញើ PDF
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=f"text_{update.effective_user.id}.pdf",
            caption="✅ ការបម្លែងអត្ថបទទៅជា PDF បានជោគជ័យ!"
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ មានបញ្ហាកើតឡើង: {str(e)}")

# Add handlers
ptb.add_handler(CommandHandler("start", start_command))
ptb.add_handler(CommandHandler("help", help_command))
ptb.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

# FastAPI app lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set webhook
    await ptb.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    async with ptb:
        await ptb.start()
        yield
        await ptb.stop()

# Create FastAPI app
app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def process_update(request: Request):
    """ដោះស្រាយ updates ពី Telegram"""
    req = await request.json()
    update = Update.de_json(req, ptb.bot)
    await ptb.update_queue.put(update)
    return Response(status_code=200)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "Bot is running! 🤖"}

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Telegram Bot is running on Render! 🚀"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
