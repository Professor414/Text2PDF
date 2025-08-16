import os
import logging
from io import BytesIO
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime

# ReportLab imports
try:
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
    logging.info("✅ ReportLab imported successfully")
except ImportError as e:
    REPORTLAB_AVAILABLE = False
    logging.error(f"❌ ReportLab not available: {e}")

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Environment variables
TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', 8000))

class PDFOnlyBot:
    def __init__(self):
        self.font_size = 19
        self.footer_font_size = 10
        self.font_name = 'Helvetica'
        self.khmer_font_name = 'Helvetica'
        # All margins set to 0.4 inches
        self.margin_size = 0.4 * inch
        self.setup_fonts()
        
    def setup_fonts(self):
        """Setup fonts with fallback system"""
        if not REPORTLAB_AVAILABLE:
            logging.warning("ReportLab not available - using default fonts")
            return
            
        try:
            # Try to register Khmer fonts
            font_paths = [
                'font/Battambang-Regular.ttf',
                'font/KhmerOS.ttf',
                'font/Noto-Sans-Khmer-Regular.ttf',
                '/usr/share/fonts/truetype/khmer/KhmerOS.ttf'
            ]
            
            for i, font_path in enumerate(font_paths):
                try:
                    if os.path.exists(font_path):
                        font_name = f'KhmerFont{i}'
                        pdfmetrics.registerFont(TTFont(font_name, font_path))
                        self.khmer_font_name = font_name
                        logging.info(f"✅ Loaded Khmer font: {font_path}")
                        return
                except Exception as e:
                    logging.warning(f"Failed to load {font_path}: {e}")
                    continue
                    
            # Fallback to default fonts
            self.font_name = 'Helvetica'
            self.khmer_font_name = 'Helvetica'
            logging.info("Using Helvetica as fallback font")
            
        except Exception as e:
            logging.error(f"Font setup error: {e}")
            self.font_name = 'Helvetica'
            self.khmer_font_name = 'Helvetica'
    
    def contains_khmer(self, text: str) -> bool:
        """Check if text contains Khmer characters"""
        khmer_range = range(0x1780, 0x17FF)
        return any(ord(char) in khmer_range for char in text)
    
    def clean_text(self, text: str) -> str:
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
        
        # Basic Unicode normalization
        try:
            import unicodedata
            cleaned = unicodedata.normalize('NFC', cleaned)
        except:
            pass
            
        return cleaned
    
    def split_into_paragraphs(self, text: str) -> list:
        """Split text into paragraphs"""
        # Try double line breaks first
        if '\n\n' in text:
            paragraphs = text.split('\n\n')
        else:
            # Use single line breaks
            paragraphs = text.split('\n')
        
        # Clean and filter
        clean_paragraphs = []
        for para in paragraphs:
            cleaned = self.clean_text(para)
            if cleaned and len(cleaned.strip()) > 2:
                clean_paragraphs.append(cleaned)
        
        return clean_paragraphs if clean_paragraphs else [self.clean_text(text)]
    
    def create_pdf_document(self, text: str) -> BytesIO:
        """Create PDF document with 0.4\" margins and footer only"""
        if not REPORTLAB_AVAILABLE:
            raise ImportError("ReportLab not available - cannot create PDF")
            
        buffer = BytesIO()
        
        # Create document with 0.4 inch margins on all sides
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=self.margin_size,     # 0.4"
            bottomMargin=self.margin_size,  # 0.4"
            leftMargin=self.margin_size,    # 0.4"
            rightMargin=self.margin_size,   # 0.4"
            title="PDF by TENG SAMBATH"
        )
        
        # Get base styles
        styles = getSampleStyleSheet()
        
        # Choose font based on text content
        text_font = self.khmer_font_name if self.contains_khmer(text) else self.font_name
        
        # Main text style
        main_style = ParagraphStyle(
            'MainText',
            parent=styles['Normal'],
            fontName=text_font,
            fontSize=self.font_size,
            leading=self.font_size + 8,  # Line spacing
            alignment=TA_LEFT,
            spaceAfter=12,
            spaceBefore=0,
            leftIndent=0,
            rightIndent=0,
            firstLineIndent=30,  # Paragraph indent
            wordWrap='CJK',
            allowWidows=1,
            allowOrphans=1
        )
        
        # Footer style
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=self.footer_font_size,
            alignment=TA_LEFT,
            textColor='grey'
        )
        
        # Build document content
        story = []
        
        # NO HEADER - Start directly with content
        
        # Main content paragraphs
        paragraphs = self.split_into_paragraphs(text)
        
        for i, para_text in enumerate(paragraphs):
            if para_text.strip():
                story.append(Paragraph(para_text, main_style))
                
                # Add spacing between paragraphs
                if i < len(paragraphs) - 1:
                    story.append(Spacer(1, 15))
        
        # Footer section
        story.append(Spacer(1, 30))
        footer_text = "ទំព័រ 1 | Created by TENG SAMBATH"
        story.append(Paragraph(footer_text, footer_style))
        
        # Build the PDF
        doc.build(story)
        
        buffer.seek(0)
        return buffer

# Initialize bot
pdf_bot = PDFOnlyBot()

# Create bot application
ptb = Application.builder().updater(None).token(TOKEN).read_timeout(10).get_updates_read_timeout(42).build()

# Bot command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not REPORTLAB_AVAILABLE:
        await update.message.reply_text("❌ ReportLab library not available. PDF generation disabled.")
        return
        
    welcome_message = f"""🇰🇭 ជំរាបសួរ! PDF Bot (Final Version)

🎯 **កំណត់ត្រាថ្មី:**
• Margins: 0.4" ទាំង 4 ប្រការ (Top, Bottom, Left, Right)
• Header: ដកចេញហើយ
• Footer: "ទំព័រ 1 | Created by TENG SAMBATH"
• Font Size: {pdf_bot.font_size}px

🔧 **Status:**
• PDF Generation: ✅ Ready
• Khmer Font: {pdf_bot.khmer_font_name}
• Layout: Clean & Professional

📝 **របៀបប្រើប្រាស់:**
ផ្ញើអត្ថបទខ្មែរមកខ្ញុំ ទទួលបាន PDF ជាមួយ layout ថ្មី!

👨‍💻 **Final Version by: TENG SAMBATH**"""
    
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not REPORTLAB_AVAILABLE:
        await update.message.reply_text("❌ ReportLab not available. Cannot generate PDF.")
        return
        
    help_text = f"""🆘 **ជំនួយ PDF Bot:**

🎯 **Layout Specifications:**
• All Margins: 0.4 inches
• Header: Removed completely
• Footer: "ទំព័រ 1 | Created by TENG SAMBATH"
• Font Size: {pdf_bot.font_size}px
• Alignment: Left

📝 **Usage:**
1️⃣ Send Khmer or English text
2️⃣ Receive PDF with 0.4" margins
3️⃣ Download and use

💡 **Features:**
- Professional PDF layout
- Clean Khmer text rendering
- Proper paragraph formatting
- Consistent spacing

👨‍💻 **TENG SAMBATH**"""
    
    await update.message.reply_text(help_text)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    if user_text.startswith('/'):
        return
    
    # Check if ReportLab is available
    if not REPORTLAB_AVAILABLE:
        await update.message.reply_text("❌ ReportLab library not installed. Cannot create PDF.")
        return
    
    # Validate input
    if len(user_text.strip()) < 3:
        await update.message.reply_text("⚠️ សូមផ្ញើអត្ថបទយ៉ាងហោចណាស់ 3 តួអក្សរ")
        return
    
    try:
        # Send processing message
        processing_msg = await update.message.reply_text(
            f"⏳ **កំពុងបង្កើត PDF ជាមួយ margins 0.4\"...**\n"
            f"📐 Layout: No Header + Footer Only\n"
            f"📝 Font: {pdf_bot.font_size}px\n"
            f"⚙️ Engine: ReportLab PDF\n"
            f"✨ Processing..."
        )
        
        # Create PDF
        pdf_buffer = pdf_bot.create_pdf_document(user_text)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"SAMBATH_PDF_{timestamp}.pdf"
        
        # Send PDF document
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=filename,
            caption=f"""✅ **បង្កើត PDF ជោគជ័យ!** 🇰🇭

🎯 **Layout ថ្មី:**
• Margins: 0.4" ទាំង 4 ប្រការ ✅
• Header: ដកចេញ ✅
• Footer: "ទំព័រ 1 | Created by TENG SAMBATH" ✅
• Font Size: {pdf_bot.font_size}px ✅

📊 **ព័ត៌មានឯកសារ:**
• File Type: PDF
• Layout: Clean & Professional
• Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}

📄 **ទាញយក PDF ផ្ទាល់បាន!**

👨‍💻 **Created by: TENG SAMBATH**"""
        )
        
        # Delete processing message
        await processing_msg.delete()
        
        # Log success
        logging.info(f"Successfully created PDF for user {update.effective_user.id}")
        
    except Exception as e:
        logging.error(f"Error creating PDF: {str(e)}")
        await update.message.reply_text(
            f"❌ **មានបញ្ហាកើតឡើង:** {str(e)}\n\n"
            f"🔄 សូមព្យាយាមម្ដងទៀត\n"
            f"💡 ឬផ្ញើអត្ថបទខ្លីជាមុន\n"
            f"👨‍💻 Support: TENG SAMBATH"
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
        webhook_url = f"{WEBHOOK_URL}/webhook"
        await ptb.bot.set_webhook(webhook_url)
        logging.info(f"✅ Webhook set to: {webhook_url}")
        
        # Start bot
        async with ptb:
            await ptb.start()
            logging.info("✅ PDF Bot started successfully")
            yield
            
    except Exception as e:
        logging.error(f"❌ Error in lifespan: {str(e)}")
        yield
    finally:
        try:
            await ptb.stop()
            logging.info("🔄 Bot stopped")
        except Exception as e:
            logging.error(f"❌ Error stopping bot: {str(e)}")

# Create FastAPI application
app = FastAPI(
    title="PDF Only Bot by TENG SAMBATH",
    description="PDF generation with 0.4\" margins, no header, footer only",
    version="PDF ONLY 1.0",
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
        logging.error(f"Webhook error: {str(e)}")
        return Response(status_code=500)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "message": "PDF Only Bot running! 🤖",
        "version": "PDF ONLY 1.0",
        "developer": "TENG SAMBATH",
        "specifications": {
            "margins": "0.4 inches all sides",
            "header": "Removed",
            "footer": "ទំព័រ 1 | Created by TENG SAMBATH",
            "font_size": f"{pdf_bot.font_size}px",
            "pdf_only": True,
            "html_fallback": False
        },
        "reportlab_available": REPORTLAB_AVAILABLE
    }

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "🇰🇭 PDF Only Bot by TENG SAMBATH",
        "version": "PDF ONLY 1.0",
        "developer": "TENG SAMBATH",
        "features": {
            "margins": "0.4\" all sides (Top, Bottom, Left, Right)",
            "header": "Removed completely",
            "footer": "ទំព័រ 1 | Created by TENG SAMBATH",
            "font_size": f"{pdf_bot.font_size}px",
            "mode": "PDF generation only"
        },
        "status": "Ready for production"
    }

# Application entry point
if __name__ == "__main__":
    import uvicorn
    
    # Startup logging
    logging.info("🚀 Starting PDF Only Bot by TENG SAMBATH...")
    logging.info(f"📐 Margins: 0.4\" on all sides")
    logging.info("🚫 Header: Removed")
    logging.info("✅ Footer: ទំព័រ 1 | Created by TENG SAMBATH")
    logging.info(f"📏 Font Size: {pdf_bot.font_size}px")
    logging.info(f"🔧 ReportLab: {'Available' if REPORTLAB_AVAILABLE else 'Not Available'}")
    logging.info("📄 Mode: PDF Generation Only")
    
    # Run the application
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )
