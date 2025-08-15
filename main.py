import os
import logging
from io import BytesIO
from contextlib import asynccontextmanager
from datetime import datetime

# Import FastAPI និង Telegram បមុន
try:
    from fastapi import FastAPI, Request, Response
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
except ImportError as e:
    print(f"Error importing basic modules: {e}")
    exit(1)

# Import ReportLab ជាមួយ error handling
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    print("ReportLab imported successfully")
except ImportError as e:
    print(f"Error importing ReportLab: {e}")
    # Use fallback PDF generation method
    canvas = None
    A4 = (595.27, 841.89)  # A4 size in points

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Environment variables
TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', 8000))

# Simple PDF creation class សម្រាប់ fallback
class SimplePDFBot:
    def __init__(self):
        self.font_size = 19
        
    def create_simple_pdf(self, text: str) -> BytesIO:
        """បង្កើត PDF ធម្មតាបើ ReportLab មិនដំណើរការ"""
        buffer = BytesIO()
        
        # Create basic PDF content
        pdf_content = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj

2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj

3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842]
   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj

4 0 obj
<< /Length {len(text) + 200} >>
stream
BT
/F1 {self.font_size} Tf
50 800 Td
(TEXT 2PDF BY : TENG SAMBATH) Tj
0 -50 Td
({text[:100]}...) Tj
ET
endstream
endobj

5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj

xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000251 00000 n 
0000000456 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
537
%%EOF"""
        
        buffer.write(pdf_content.encode())
        buffer.seek(0)
        return buffer
    
    def create_pdf_from_text(self, text: str) -> BytesIO:
        if canvas is None:
            # Use simple PDF if ReportLab failed
            return self.create_simple_pdf(text)
        
        # Use ReportLab if available
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        
        width, height = A4
        margin = 60
        
        # Header
        p.setFont('Helvetica-Bold', 14)
        header_text = "TEXT 2PDF BY : TENG SAMBATH"
        text_width = p.stringWidth(header_text, 'Helvetica-Bold', 14)
        p.drawString((width - text_width) / 2, height - 30, header_text)
        
        # Main content
        p.setFont('Helvetica', self.font_size)
        lines = text.split('\n')
        y_position = height - 70
        
        for line in lines[:20]:  # Limit lines to prevent errors
            if y_position < 60:
                break
            p.drawString(margin, y_position, line[:80])  # Limit line length
            y_position -= self.font_size + 8
        
        # Footer
        p.setFont('Helvetica', 10)
        p.drawString(50, 25, f"Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        p.drawString(width - 100, 25, "ទំព័រ 1")
        
        p.save()
        buffer.seek(0)
        return buffer

# Use the fallback bot
pdf_bot = SimplePDFBot()

# Create bot application
ptb = (
    Application.builder()
    .updater(None)
    .token(TOKEN)
    .read_timeout(7)
    .get_updates_read_timeout(42)
    .build()
)

# Bot handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "ReportLab available" if canvas else "Using simple PDF fallback"
    welcome_message = f"""🇰🇭 ជំរាបសួរ! ខ្ញុំជា Text to PDF Bot

📝 Status: {status}
• បម្លែងអត្ថបទទៅជា PDF
• Header: TEXT 2PDF BY : TENG SAMBATH
• ទំហំអក្សរ: {pdf_bot.font_size}

/help - ជំនួយលម្អិត"""
    
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """🆘 ជំនួយការប្រើប្រាស់:

1️⃣ ផ្ញើអត្ថបទមកខ្ញុំ
2️⃣ រង់ចាំបម្លែងទៅជា PDF
3️⃣ ទាញយកឯកសារ

👨‍💻 បង្កើតដោយ: TENG SAMBATH"""
    
    await update.message.reply_text(help_text)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    if user_text.startswith('/'):
        return
    
    if len(user_text.strip()) < 3:
        await update.message.reply_text("⚠️ សូមផ្ញើអត្ថបទយ៉ាងហោចណាស់ 3 តួអក្សរ")
        return
    
    try:
        processing_msg = await update.message.reply_text("⏳ កំពុងបម្លែងអត្ថបទទៅជា PDF...")
        
        pdf_buffer = pdf_bot.create_pdf_from_text(user_text)
        
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=f"SAMBATH_PDF_{update.effective_user.id}.pdf",
            caption="✅ បម្លែងជោគជ័យ! 🇰🇭\n👨‍💻 បង្កើតដោយ: TENG SAMBATH"
        )
        
        await processing_msg.delete()
        
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        await update.message.reply_text(f"❌ មានបញ្ហា: {str(e)}")

# Add handlers
ptb.add_handler(CommandHandler("start", start_command))
ptb.add_handler(CommandHandler("help", help_command))
ptb.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

# FastAPI setup
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        await ptb.bot.set_webhook(webhook_url)
        logging.info(f"Webhook set to: {webhook_url}")
        
        async with ptb:
            await ptb.start()
            logging.info("Bot started successfully")
            yield
    except Exception as e:
        logging.error(f"Error in lifespan: {str(e)}")
        yield
    finally:
        try:
            await ptb.stop()
        except Exception as e:
            logging.error(f"Error stopping bot: {str(e)}")

app = FastAPI(
    title="Text to PDF Bot by TENG SAMBATH",
    description="Telegram Bot with PDF generation",
    version="2.1.0",
    lifespan=lifespan
)

@app.post("/webhook")
async def process_update(request: Request):
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
    return {
        "status": "healthy",
        "message": "Text to PDF Bot is running! 🤖",
        "reportlab_status": "available" if canvas else "fallback mode",
        "developer": "TENG SAMBATH"
    }

@app.get("/")
async def root():
    return {
        "message": "🇰🇭 Text to PDF Bot by TENG SAMBATH",
        "status": "running",
        "reportlab": "available" if canvas else "using fallback"
    }

if __name__ == "__main__":
    import uvicorn
    
    print("Starting Text to PDF Bot by TENG SAMBATH...")
    print(f"ReportLab status: {'Available' if canvas else 'Fallback mode'}")
    
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
