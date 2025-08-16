import os
import logging
from io import BytesIO
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from fastapi import FastAPI
import asyncio
import threading

# ReportLab imports with complete error handling
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
    logging.info("✅ ReportLab imported successfully")
except ImportError as e:
    REPORTLAB_AVAILABLE = False
    inch = 72  # 1 inch = 72 points (fallback)
    logging.error(f"❌ ReportLab not available: {e}")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
TOKEN = os.getenv('BOT_TOKEN')
PORT = int(os.getenv('PORT', 8000))

if not TOKEN:
    logger.error("BOT_TOKEN environment variable required!")
    exit(1)

class PDFBotWithCustomMargins:
    def __init__(self):
        self.font_size = 19
        self.footer_font_size = 10
        
        # Custom margins as requested
        self.left_margin = 0.25 * inch    # 0.25 inches left
        self.right_margin = 0.25 * inch   # 0.25 inches right
        self.top_margin = 0.4 * inch      # 0.4 inches top
        self.bottom_margin = 0.4 * inch   # 0.4 inches bottom
        
        self.line_height = self.font_size + 8  # 27 points
        self.setup_fonts()
        
    def setup_fonts(self):
        """Setup fonts with error handling"""
        if not REPORTLAB_AVAILABLE:
            self.khmer_font = 'Helvetica'
            return
            
        try:
            # Try to register Khmer fonts
            font_paths = [
                'font/Battambang-Regular.ttf',
                'font/KhmerOS.ttf',
                'font/Noto-Sans-Khmer-Regular.ttf'
            ]
            
            self.khmer_font = None
            for font_path in font_paths:
                try:
                    if os.path.exists(font_path):
                        pdfmetrics.registerFont(TTFont('KhmerFont', font_path))
                        self.khmer_font = 'KhmerFont'
                        logger.info(f"✅ Loaded Khmer font: {font_path}")
                        return
                except Exception as e:
                    logger.warning(f"Failed to load {font_path}: {e}")
                    continue
                    
            # Use default font
            self.khmer_font = 'Helvetica'
            logger.info("Using Helvetica as fallback font")
            
        except Exception as e:
            logger.error(f"Font setup error: {e}")
            self.khmer_font = 'Helvetica'
    
    def clean_text(self, text):
        """Clean text for better display"""
        problematic_chars = {
            '\u200B': '',  # Zero width space
            '\u200C': '',  # Zero width non-joiner
            '\u200D': '',  # Zero width joiner
            '\uFEFF': '',  # Byte order mark
        }
        
        cleaned = text
        for old, new in problematic_chars.items():
            cleaned = cleaned.replace(old, new)
            
        return ' '.join(cleaned.split())
    
    def split_into_lines(self, text, canvas_obj, max_width):
        """Split text into lines that fit within max_width"""
        cleaned_text = self.clean_text(text)
        
        # Split by paragraphs first
        if '\n\n' in cleaned_text:
            paragraphs = cleaned_text.split('\n\n')
        else:
            paragraphs = cleaned_text.split('\n')
        
        all_lines = []
        for para in paragraphs:
            if not para.strip():
                continue
                
            words = para.strip().split()
            if not words:
                continue
                
            current_line = ""
            para_lines = []
            
            for word in words:
                test_line = current_line + (" " if current_line else "") + word
                
                # Check text width
                text_width = canvas_obj.stringWidth(test_line, self.khmer_font, self.font_size)
                
                if text_width <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        para_lines.append(current_line)
                    current_line = word
            
            if current_line:
                para_lines.append(current_line)
            
            all_lines.extend(para_lines)
            
            # Add empty line between paragraphs
            if para != paragraphs[-1]:
                all_lines.append("")
        
        return all_lines
    
    def create_pdf_with_custom_margins(self, text):
        """Create PDF with custom margins: Left=0.25\", Right=0.25\""""
        if not REPORTLAB_AVAILABLE:
            raise ImportError("ReportLab not available - cannot create PDF")
        
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        
        # Page dimensions
        page_width, page_height = A4
        
        # Calculate content area using custom margins
        content_width = page_width - (self.left_margin + self.right_margin)
        content_height = page_height - (self.top_margin + self.bottom_margin)
        
        # Starting position (using left and top margins)
        start_x = self.left_margin
        start_y = page_height - self.top_margin
        
        # Set font
        c.setFont(self.khmer_font, self.font_size)
        
        # Split text into lines
        lines = self.split_into_lines(text, c, content_width)
        
        # Draw text lines
        current_y = start_y
        
        for line in lines:
            if not line.strip():  # Empty line (paragraph break)
                current_y -= self.line_height * 0.5
                continue
            
            # Check if we need a new page
            if current_y - self.line_height < self.bottom_margin + 30:
                c.showPage()
                c.setFont(self.khmer_font, self.font_size)
                current_y = start_y
            
            # Draw the text line (left aligned at left_margin)
            c.drawString(start_x, current_y, line)
            current_y -= self.line_height
        
        # Add footer
        footer_text = "ទំព័រ 1 | Created by TENG SAMBATH"
        c.setFont("Helvetica", self.footer_font_size)
        
        # Position footer at bottom (using left margin)
        footer_y = self.bottom_margin * 0.5
        c.drawString(self.left_margin, footer_y, footer_text)
        
        # Save the PDF
        c.showPage()
        c.save()
        
        buffer.seek(0)
        return buffer

# Initialize bot
pdf_bot = PDFBotWithCustomMargins()

# Create Telegram application
app = Application.builder().token(TOKEN).build()

# Bot command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "✅ Available" if REPORTLAB_AVAILABLE else "❌ Not Available"
    
    # Calculate margin values for display
    left_inches = pdf_bot.left_margin / inch
    right_inches = pdf_bot.right_margin / inch
    
    welcome_message = f"""🇰🇭 ជំរាបសួរ! Custom Margins PDF Bot

🎯 **Custom Margin Settings:**
• Left Margin: {left_inches:.2f} inches
• Right Margin: {right_inches:.2f} inches  
• Top Margin: 0.4 inches
• Bottom Margin: 0.4 inches

🔧 **System Status:**
• ReportLab: {status}
• Font Size: {pdf_bot.font_size}px
• Output: PDF files ពិតប្រាកដ

✨ **Features:**
• No Header (removed)
• Footer: "ទំព័រ 1 | Created by TENG SAMBATH"
• Left alignment
• Auto line wrapping
• Professional layout

📝 **Usage:** 
ផ្ញើអត្ថបទខ្មែរមកខ្ញុំ ទទួលបាន PDF ជាមួយ margins ត្រឹមត្រូវ!

👨‍💻 **Custom Margins by: TENG SAMBATH**"""
    
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    left_inches = pdf_bot.left_margin / inch
    right_inches = pdf_bot.right_margin / inch
    
    help_text = f"""🆘 **Custom Margins PDF Bot Help:**

📐 **Margin Specifications:**
• Left: {left_inches:.2f}" (as requested)
• Right: {right_inches:.2f}" (as requested)
• Top: 0.4"
• Bottom: 0.4"

🎯 **PDF Features:**
• Font Size: {pdf_bot.font_size}px
• Alignment: Left
• Header: None
• Footer: "ទំព័រ 1 | Created by TENG SAMBATH"
• Auto text wrapping
• Multi-page support

📝 **How to Use:**
1️⃣ Send Khmer text to me
2️⃣ Get PDF with custom margins
3️⃣ Download and use!

👨‍💻 **TENG SAMBATH - Custom Margins Solution**"""
    
    await update.message.reply_text(help_text)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    if user_text.startswith('/'):
        return
        
    # Check ReportLab availability
    if not REPORTLAB_AVAILABLE:
        await update.message.reply_text("❌ ReportLab library not available. Cannot create PDF.")
        return
        
    # Validate input
    if len(user_text.strip()) < 3:
        await update.message.reply_text("⚠️ សូមផ្ញើអត្ថបទយ៉ាងហោចណាស់ 3 តួអក្សរ")
        return
    
    try:
        # Send processing message
        left_inches = pdf_bot.left_margin / inch
        right_inches = pdf_bot.right_margin / inch
        
        processing_msg = await update.message.reply_text(
            f"""⏳ **កំពុងបង្កើត PDF ជាមួយ Custom Margins...**

📐 Left: {left_inches:.2f}" | Right: {right_inches:.2f}"
📝 Font: {pdf_bot.font_size}px
⚙️ Engine: ReportLab Direct PDF
✨ Processing your text..."""
        )
        
        # Create PDF
        pdf_buffer = pdf_bot.create_pdf_with_custom_margins(user_text)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"SAMBATH_MARGINS_{timestamp}.pdf"
        
        # Send PDF document
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=filename,
            caption=f"""✅ **PDF ជាមួយ Custom Margins ជោគជ័យ!** 🇰🇭

📐 **Custom Margins Applied:**
• Left Margin: {left_inches:.2f} inches ✅
• Right Margin: {right_inches:.2f} inches ✅
• Top Margin: 0.4 inches ✅
• Bottom Margin: 0.4 inches ✅

📋 **PDF Features:**
• Font Size: {pdf_bot.font_size}px ✅
• Header: Removed ✅
• Footer: "ទំព័រ 1 | Created by TENG SAMBATH" ✅
• Left Alignment: Clean & Stable ✅

📊 **Technical Info:**
• Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}
• Engine: ReportLab Direct PDF
• File Type: PDF (not HTML)

👨‍💻 **Custom Margins by: TENG SAMBATH**"""
        )
        
        # Delete processing message
        await processing_msg.delete()
        
        # Log success
        logger.info(f"PDF with custom margins created for user {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"Error creating PDF: {str(e)}")
        await update.message.reply_text(f"❌ មានបញ្ហាកើតឡើង: {str(e)}")

# Add handlers to bot
app.add_handler(CommandHandler("start", start_command))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

# FastAPI for health check and webhook
fastapi_app = FastAPI(title="Custom Margins PDF Bot by TENG SAMBATH")

@fastapi_app.get("/")
async def root():
    return {
        "message": "🇰🇭 Custom Margins PDF Bot by TENG SAMBATH",
        "status": "running",
        "margins": {
            "left": f"{pdf_bot.left_margin/inch:.2f} inches",
            "right": f"{pdf_bot.right_margin/inch:.2f} inches",
            "top": f"{pdf_bot.top_margin/inch:.2f} inches", 
            "bottom": f"{pdf_bot.bottom_margin/inch:.2f} inches"
        },
        "reportlab_available": REPORTLAB_AVAILABLE
    }

@fastapi_app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "pdf_generation": "enabled" if REPORTLAB_AVAILABLE else "disabled",
        "custom_margins": True,
        "left_margin": f"{pdf_bot.left_margin/inch:.2f} inches",
        "right_margin": f"{pdf_bot.right_margin/inch:.2f} inches"
    }

# Webhook endpoint
@fastapi_app.post("/webhook")
async def process_webhook(request):
    try:
        req = await request.json()
        update = Update.de_json(req, app.bot)
        await app.update_queue.put(update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error"}

# Function to run bot
async def run_bot():
    """Run the bot with proper error handling"""
    try:
        logger.info("🚀 Starting Custom Margins PDF Bot by TENG SAMBATH...")
        logger.info(f"📐 Left Margin: {pdf_bot.left_margin/inch:.2f} inches")
        logger.info(f"📐 Right Margin: {pdf_bot.right_margin/inch:.2f} inches")
        logger.info(f"✅ ReportLab: {'Available' if REPORTLAB_AVAILABLE else 'Not Available'}")
        logger.info(f"📝 Font: {pdf_bot.font_size}px")
        logger.info("🎯 Custom margins PDF generation ready!")
        
        # Check for webhook URL
        webhook_url = os.getenv('WEBHOOK_URL')
        if webhook_url:
            # Webhook mode
            logger.info("Using WEBHOOK mode")
            await app.bot.set_webhook(webhook_url + "/webhook")
        else:
            # Polling mode
            logger.info("Using POLLING mode")
            async with app:
                await app.initialize()
                await app.start()
                await app.updater.start_polling()
                
                # Keep running
                while True:
                    await asyncio.sleep(1)
                
    except Exception as e:
        logger.error(f"Bot error: {e}")

def start_bot_thread():
    """Start bot in separate thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_bot())

if __name__ == "__main__":
    import uvicorn
    
    # Start bot in background thread for polling
    if not os.getenv('WEBHOOK_URL'):
        bot_thread = threading.Thread(target=start_bot_thread, daemon=True)
        bot_thread.start()
    
    # Start FastAPI server
    uvicorn.run(fastapi_app, host="0.0.0.0", port=PORT)
