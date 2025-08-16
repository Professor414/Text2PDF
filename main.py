import os
import logging
from io import BytesIO
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from fastapi import FastAPI
import asyncio
import threading

# ReportLab imports for direct PDF generation
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
    logging.info("✅ ReportLab available - Direct PDF generation enabled!")
except ImportError as e:
    REPORTLAB_AVAILABLE = False
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

class DirectPDFBot:
    def __init__(self):
        self.font_size = 19
        self.footer_font_size = 10
        self.margin = 0.4 * inch  # 0.4 inches = 28.8 points
        self.line_height = self.font_size + 8  # 27 points
        self.setup_fonts()
        
    def setup_fonts(self):
        """Setup Khmer fonts if available"""
        if not REPORTLAB_AVAILABLE:
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
                    
            # Use default font if no Khmer fonts available
            self.khmer_font = 'Helvetica'
            logger.info("Using Helvetica as fallback font")
            
        except Exception as e:
            logger.error(f"Font setup error: {e}")
            self.khmer_font = 'Helvetica'
    
    def clean_text(self, text):
        """Clean and prepare text"""
        # Remove problematic characters
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
                
            # For each paragraph, split into words and create lines
            words = para.strip().split()
            if not words:
                continue
                
            current_line = ""
            para_lines = []
            
            for word in words:
                test_line = current_line + (" " if current_line else "") + word
                
                # Check if test_line fits within max_width
                text_width = canvas_obj.stringWidth(test_line, self.khmer_font, self.font_size)
                
                if text_width <= max_width:
                    current_line = test_line
                else:
                    # Current line is full, start new line
                    if current_line:
                        para_lines.append(current_line)
                    current_line = word
            
            # Add last line
            if current_line:
                para_lines.append(current_line)
            
            # Add paragraph lines to all_lines
            all_lines.extend(para_lines)
            # Add empty line between paragraphs (except for last paragraph)
            if para != paragraphs[-1]:
                all_lines.append("")
        
        return all_lines
    
    def create_direct_pdf(self, text):
        """Create direct PDF using ReportLab canvas"""
        if not REPORTLAB_AVAILABLE:
            raise ImportError("ReportLab not available - cannot create PDF")
        
        buffer = BytesIO()
        
        # Create canvas with A4 page size
        c = canvas.Canvas(buffer, pagesize=A4)
        
        # Page dimensions
        page_width, page_height = A4
        
        # Calculate content area
        content_width = page_width - (2 * self.margin)  # 0.4" margins on both sides
        content_height = page_height - (2 * self.margin)  # 0.4" margins top and bottom
        
        # Starting position (top-left of content area)
        start_x = self.margin
        start_y = page_height - self.margin
        
        # Set font
        c.setFont(self.khmer_font, self.font_size)
        
        # Split text into lines that fit within content width
        lines = self.split_into_lines(text, c, content_width)
        
        # Draw text lines
        current_y = start_y
        
        for i, line in enumerate(lines):
            if not line.strip():  # Empty line (paragraph break)
                current_y -= self.line_height * 0.5  # Half line spacing for paragraph break
                continue
            
            # Check if we need a new page
            if current_y - self.line_height < self.margin + 30:  # Leave space for footer
                c.showPage()  # New page
                c.setFont(self.khmer_font, self.font_size)  # Reset font after new page
                current_y = start_y
            
            # Draw the text line (left aligned)
            c.drawString(start_x, current_y, line)
            current_y -= self.line_height
        
        # Add footer
        footer_text = "ទំព័រ 1 | Created by TENG SAMBATH"
        c.setFont("Helvetica", self.footer_font_size)
        
        # Position footer at bottom of page
        footer_y = self.margin * 0.5  # Half margin from bottom
        c.drawString(start_x, footer_y, footer_text)
        
        # Save the PDF
        c.showPage()
        c.save()
        
        buffer.seek(0)
        return buffer

# Initialize bot
pdf_bot = DirectPDFBot()

# Create Telegram application (POLLING MODE)
app = Application.builder().token(TOKEN).build()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "✅ Available" if REPORTLAB_AVAILABLE else "❌ Not Available"
    
    await update.message.reply_text(
        f"""🇰🇭 ជំរាបសួរ! Direct PDF Bot

🎯 **Direct PDF Generation:**
• ReportLab: {status}
• Output: PDF files ពិតប្រាកដ (មិនមែន HTML)
• Font Size: {pdf_bot.font_size}px
• Margins: 0.4" ទាំង 4 ប្រការ

✨ **PDF Features:**
• No Header (ដកចេញ)
• Footer: "ទំព័រ 1 | Created by TENG SAMBATH"
• Left alignment (stable)
• Auto line wrapping
• Paragraph spacing

📝 **របៀបប្រើប្រាស់:**
1. ផ្ញើអត្ថបទខ្មែរមកខ្ញុំ
2. ទទួលបាន PDF file ពិតប្រាកដ
3. ទាញយកហើយប្រើបាន!

🎊 **Direct PDF - No HTML conversion needed!**

👨‍💻 **Direct Solution by: TENG SAMBATH**"""
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"""🆘 **Direct PDF Bot Help:**

✅ **What's Different:**
• Creates actual PDF files (not HTML)
• Direct ReportLab PDF generation
• No browser conversion needed
• Professional PDF output

🎯 **PDF Specifications:**
• Margins: 0.4 inches ទាំង 4 ប្រការ
• Font: {pdf_bot.font_size}px
• Header: None (removed)
• Footer: "ទំព័រ 1 | Created by TENG SAMBATH"
• Alignment: Left (clean & stable)

📝 **Features:**
• Auto text wrapping
• Paragraph spacing
• Multi-page support
• Professional layout
• Direct download

👨‍💻 **TENG SAMBATH - Direct PDF Solution**"""
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.startswith('/'):
        return
        
    if not REPORTLAB_AVAILABLE:
        await update.message.reply_text("❌ ReportLab not available. Cannot create PDF.")
        return
        
    text = update.message.text.strip()
    if len(text) < 3:
        await update.message.reply_text("⚠️ សូមផ្ញើអត្ថបទយ៉ាងហោចណាស់ 3 តួអក្សរ")
        return
    
    try:
        processing = await update.message.reply_text(
            f"""⏳ **បង្កើត PDF ពិតប្រាកដ...**

✅ Engine: ReportLab Direct PDF
📐 Margins: 0.4" all sides
📝 Font: {pdf_bot.font_size}px
📄 Output: PDF file (not HTML)
🎯 Processing your text..."""
        )
        
        pdf_buffer = pdf_bot.create_direct_pdf(text)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"SAMBATH_PDF_{timestamp}.pdf"
        
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=filename,
            caption=f"""✅ **Direct PDF ជោគជ័យ!** 🇰🇭

🎯 **PDF ពិតប្រាកដ - Ready to use!**

📋 **PDF Features:**
• File Type: PDF (not HTML) ✅
• Margins: 0.4" ទាំង 4 ប្រការ ✅
• Font Size: {pdf_bot.font_size}px ✅
• Header: Removed ✅
• Footer: "ទំព័រ 1 | Created by TENG SAMBATH" ✅
• Alignment: Left ✅

📊 **Technical:**
• Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}
• Engine: ReportLab Direct PDF
• Auto line wrapping: Enabled
• Multi-page support: Available

📄 **Direct PDF Download - No conversion needed!**

👨‍💻 **Direct PDF by: TENG SAMBATH**"""
        )
        
        await processing.delete()
        logger.info(f"Direct PDF created for user {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"PDF Error: {e}")
        await update.message.reply_text(f"❌ Error creating PDF: {str(e)}")

# Add handlers
app.add_handler(CommandHandler("start", start_command))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# FastAPI for health check
fastapi_app = FastAPI(title="Direct PDF Bot by TENG SAMBATH")

@fastapi_app.get("/")
async def root():
    return {
        "status": "direct_pdf",
        "message": "Direct PDF Bot - No HTML conversion needed!",
        "output": "PDF files (not HTML)",
        "developer": "TENG SAMBATH",
        "reportlab": REPORTLAB_AVAILABLE
    }

@fastapi_app.get("/health")
async def health():
    return {
        "status": "healthy",
        "pdf_generation": "direct",
        "output_format": "PDF",
        "html_conversion": False,
        "reportlab_available": REPORTLAB_AVAILABLE
    }

# Function to run bot
async def run_bot():
    try:
        logger.info("🚀 Starting Direct PDF Bot")
        logger.info("📄 Output: PDF files (not HTML)")
        logger.info(f"✅ ReportLab: {'Available' if REPORTLAB_AVAILABLE else 'Not Available'}")
        logger.info(f"📏 Font: {pdf_bot.font_size}px")
        logger.info("📐 Margins: 0.4 inches all sides")
        logger.info("🎯 Direct PDF generation enabled!")
        
        async with app:
            await app.initialize()
            await app.start()
            await app.updater.start_polling()
            
            while True:
                await asyncio.sleep(1)
                
    except Exception as e:
        logger.error(f"Bot error: {e}")

def start_bot_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_bot())

if __name__ == "__main__":
    import uvicorn
    
    # Start bot in background thread
    bot_thread = threading.Thread(target=start_bot_thread, daemon=True)
    bot_thread.start()
    
    # Start FastAPI server
    uvicorn.run(fastapi_app, host="0.0.0.0", port=PORT)
