import os
import logging
from io import BytesIO
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime

# ReportLab imports with complete error handling
try:
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.units import inch  # ← Fixed import
    REPORTLAB_AVAILABLE = True
    logging.info("✅ ReportLab imported successfully")
except ImportError as e:
    REPORTLAB_AVAILABLE = False
    inch = 72  # Fallback: 1 inch = 72 points
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

class FixedPDFBot:
    def __init__(self):
        self.font_size = 19
        self.footer_font_size = 10
        self.font_name = 'Helvetica'
        self.khmer_font_name = 'Helvetica'
        # All margins set to 0.4 inches (using safe calculation)
        self.margin_size = 0.4 * inch  # Now inch is always defined
        self.setup_fonts()
        
    def setup_fonts(self):
        """Setup fonts with complete error handling"""
        if not REPORTLAB_AVAILABLE:
            logging.warning("ReportLab not available - PDF generation disabled")
            return
            
        try:
            # Try to register Khmer fonts
            font_paths = [
                'font/Battambang-Regular.ttf',
                'font/KhmerOS.ttf',
                'font/Noto-Sans-Khmer-Regular.ttf'
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
            raise ImportError("ReportLab library not available")
            
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
    
    def create_fallback_response(self, text: str) -> BytesIO:
        """Create fallback response when ReportLab is not available"""
        current_date = datetime.now().strftime("%d/%m/%Y %H:%M")
        
        fallback_content = f"""
PDF Generation Failed - ReportLab Not Available

Text Content:
{text}

Footer: ទំព័រ 1 | Created by TENG SAMBATH
Generated: {current_date}

Please install ReportLab library for PDF generation.
"""
        
        buffer = BytesIO()
        buffer.write(fallback_content.encode('utf-8'))
        buffer.seek(0)
        return buffer

# Initialize bot
pdf_bot = FixedPDFBot()

# Create bot application
ptb = Application.builder().updater(None).token(TOKEN).read_timeout(10).get_updates_read_timeout(42).build()

# Bot command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "✅ Available" if REPORTLAB_AVAILABLE else "❌ Not Available"
    
    welcome_message = f"""🇰🇭 ជំរាបសួរ! Fixed PDF Bot

🔧 **System Status:**
• ReportLab: {status}
• PDF Generation: {'Enabled' if REPORTLAB_AVAILABLE else 'Disabled'}
• Font Size: {pdf_bot.font_size}px

🎯 **Layout Configuration:**
• Margins: 0.4\" all sides
• Header: Removed
• Footer: "ទំព័រ 1 | Created by TENG SAMBATH"

{'📝 ផ្ញើអត្ថបទមកខ្ញុំ!' if REPORTLAB_AVAILABLE else '⚠️ ReportLab library required for PDF generation'}

👨‍💻 **Fixed by: TENG SAMBATH**"""
    
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = f"""🆘 **ជំនួយ Fixed PDF Bot:**

🔧 **System Status:**
• ReportLab: {'Available' if REPORTLAB_AVAILABLE else 'Not Available'}
• inch variable: {'Defined' if 'inch' in globals() else 'Not defined'}
• Margins: 0.4\" (calculated as {pdf_bot.margin_size} points)

{'📝 **Usage:** Send text to generate PDF' if REPORTLAB_AVAILABLE else '⚠️ **Issue:** ReportLab library not installed'}

👨‍💻 **TENG SAMBATH**"""
    
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
        if REPORTLAB_AVAILABLE:
            processing_msg = await update.message.reply_text(
                f"⏳ **កំពុងបង្កើត PDF ជាមួយ margins 0.4\"...**\n"
                f"📐 Layout: No Header + Footer Only\n"
                f"📝 Font: {pdf_bot.font_size}px\n"
                f"⚙️ Engine: ReportLab PDF\n"
                f"✨ Processing..."
            )
            
            # Create PDF
            pdf_buffer = pdf_bot.create_pdf_document(user_text)
            file_ext = "pdf"
            
        else:
            processing_msg = await update.message.reply_text(
                "⚠️ **ReportLab not available - creating fallback response...**"
            )
            
            # Create fallback
            pdf_buffer = pdf_bot.create_fallback_response(user_text)
            file_ext = "txt"
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"SAMBATH_{'PDF' if REPORTLAB_AVAILABLE else 'FALLBACK'}_{timestamp}.{file_ext}"
        
        # Send document
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=filename,
            caption=f"""{'✅ បង្កើត PDF ជោគជ័យ!' if REPORTLAB_AVAILABLE else '⚠️ ReportLab not available'} 🇰🇭

{'🎯 **PDF Features:**' if REPORTLAB_AVAILABLE else '🔧 **System Issue:**'}
{'• Margins: 0.4\" ទាំង 4 ប្រការ ✅' if REPORTLAB_AVAILABLE else '• ReportLab library missing'}
{'• Header: ដកចេញ ✅' if REPORTLAB_AVAILABLE else '• Cannot generate PDF'}
{'• Footer: "ទំព័រ 1 | Created by TENG SAMBATH" ✅' if REPORTLAB_AVAILABLE else '• Fallback text file created'}
{'• Font Size: 19px ✅' if REPORTLAB_AVAILABLE else ''}

📊 **ព័ត៌មាន:**
• Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}
• Engine: {'ReportLab PDF' if REPORTLAB_AVAILABLE else 'Text Fallback'}

👨‍💻 **Created by: TENG SAMBATH**"""
        )
        
        # Delete processing message
        await processing_msg.delete()
        
        # Log success
        logging.info(f"Successfully created {'PDF' if REPORTLAB_AVAILABLE else 'fallback'} for user {update.effective_user.id}")
        
    except Exception as e:
        logging.error(f"Error processing text: {str(e)}")
        await update.message.reply_text(
            f"❌ **មានបញ្ហាកើតឡើង:** {str(e)}\n\n"
            f"🔄 សូមព្យាយាមម្ដងទៀត\n"
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
            logging.info("✅ Fixed PDF Bot started successfully")
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
    title="Fixed PDF Bot by TENG SAMBATH",
    description="PDF generation with proper error handling and fallback support",
    version="FIXED 1.0",
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
        "message": "Fixed PDF Bot running! 🤖",
        "version": "FIXED 1.0",
        "developer": "TENG SAMBATH",
        "system_status": {
            "reportlab_available": REPORTLAB_AVAILABLE,
            "inch_defined": True,  # Now always defined
            "margin_size_points": pdf_bot.margin_size,
            "pdf_generation": "enabled" if REPORTLAB_AVAILABLE else "disabled",
            "fallback_mode": "available" if not REPORTLAB_AVAILABLE else "not needed"
        }
    }

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "🇰🇭 Fixed PDF Bot by TENG SAMBATH",
        "version": "FIXED 1.0",
        "developer": "TENG SAMBATH",
        "fixes_applied": [
            "Fixed inch variable import issue",
            "Added ReportLab availability check",
            "Implemented fallback for missing ReportLab",
            "Proper error handling throughout",
            "Safe margin calculation"
        ],
        "status": "Production ready with error handling"
    }

# Application entry point
if __name__ == "__main__":
    import uvicorn
    
    # Startup logging
    logging.info("🚀 Starting Fixed PDF Bot by TENG SAMBATH...")
    logging.info(f"🔧 ReportLab: {'Available' if REPORTLAB_AVAILABLE else 'Not Available'}")
    logging.info(f"📐 inch variable: {inch} points")
    logging.info(f"📏 Margins: 0.4\" = {pdf_bot.margin_size} points")
    logging.info("✅ All imports handled safely")
    
    # Run the application
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )
