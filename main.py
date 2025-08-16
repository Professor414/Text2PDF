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
    inch = 72  # 1 inch = 72 points
    logging.error("❌ ReportLab not available")

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Environment variables
TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', 8000))

class FinalPDFBot:
    def __init__(self):
        self.font_size = 19
        self.footer_font_size = 10
        self.font_name = 'Helvetica'
        self.khmer_font_name = 'Helvetica'
        # Fixed: Use direct multiplication instead of f-string with backslash
        self.margin_size = 0.4 * inch  # 0.4 inches = 28.8 points
        self.setup_fonts()
        
    def setup_fonts(self):
        """Setup fonts with safe error handling"""
        if not REPORTLAB_AVAILABLE:
            logging.warning("ReportLab not available - using fallback")
            return
            
        try:
            font_paths = [
                'font/Battambang-Regular.ttf',
                'font/KhmerOS.ttf',
                'font/Noto-Sans-Khmer-Regular.ttf'
            ]
            
            for i, font_path in enumerate(font_paths):
                try:
                    if os.path.exists(font_path):
                        font_name = 'KhmerFont' + str(i)
                        pdfmetrics.registerFont(TTFont(font_name, font_path))
                        self.khmer_font_name = font_name
                        logging.info("Loaded Khmer font: " + font_path)
                        return
                except Exception as e:
                    logging.warning("Failed to load " + font_path + ": " + str(e))
                    continue
                    
            # Fallback
            self.font_name = 'Helvetica'
            self.khmer_font_name = 'Helvetica'
            logging.info("Using Helvetica as fallback font")
            
        except Exception as e:
            logging.error("Font setup error: " + str(e))
            self.font_name = 'Helvetica'
            self.khmer_font_name = 'Helvetica'
    
    def contains_khmer(self, text):
        """Check if text contains Khmer characters"""
        khmer_range = range(0x1780, 0x17FF)
        return any(ord(char) in khmer_range for char in text)
    
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
        
        # Basic Unicode normalization
        try:
            import unicodedata
            cleaned = unicodedata.normalize('NFC', cleaned)
        except:
            pass
            
        return cleaned
    
    def split_into_paragraphs(self, text):
        """Split text into paragraphs"""
        # Try double line breaks first
        newline_double = '\n\n'
        if newline_double in text:
            paragraphs = text.split(newline_double)
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
    
    def create_pdf_document(self, text):
        """Create PDF document with 0.4 inch margins and footer only"""
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

# Initialize bot
pdf_bot = FinalPDFBot()

# Create bot application
ptb = Application.builder().updater(None).token(TOKEN).read_timeout(10).get_updates_read_timeout(42).build()

# Bot command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not REPORTLAB_AVAILABLE:
        await update.message.reply_text("❌ ReportLab library not available. PDF generation disabled.")
        return
        
    # Fixed: Avoid f-string with backslashes
    font_size_text = str(pdf_bot.font_size) + "px"
    
    welcome_message = ("🇰🇭 ជំរាបសួរ! Final PDF Bot\n\n"
                      "🎯 **កំណត់ត្រាចុងក្រោយ:**\n"
                      "• Margins: 0.4\" ទាំង 4 ប្រការ (Top, Bottom, Left, Right)\n"
                      "• Header: ដកចេញហើយ\n"
                      '• Footer: "ទំព័រ 1 | Created by TENG SAMBATH"\n'
                      "• Font Size: " + font_size_text + "\n\n"
                      "🔧 **Status:**\n"
                      "• PDF Generation: ✅ Ready\n"
                      "• Layout: Clean & Professional\n\n"
                      "📝 **របៀបប្រើប្រាស់:**\n"
                      "ផ្ញើអត្ថបទខ្មែរមកខ្ញុំ ទទួលបាន PDF ជាមួយ layout ថ្មី!\n\n"
                      "👨‍💻 **Final Version by: TENG SAMBATH**")
    
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not REPORTLAB_AVAILABLE:
        await update.message.reply_text("❌ ReportLab not available. Cannot generate PDF.")
        return
        
    # Fixed: Avoid f-string with backslashes
    font_size_text = str(pdf_bot.font_size) + "px"
    
    help_text = ("🆘 **ជំនួយ Final PDF Bot:**\n\n"
                "🎯 **Layout Specifications:**\n"
                "• All Margins: 0.4 inches\n"
                "• Header: Removed completely\n"
                '• Footer: "ទំព័រ 1 | Created by TENG SAMBATH"\n'
                "• Font Size: " + font_size_text + "\n"
                "• Alignment: Left\n\n"
                "📝 **Usage:**\n"
                "1️⃣ Send Khmer or English text\n"
                "2️⃣ Receive PDF with 0.4\" margins\n"
                "3️⃣ Download and use\n\n"
                "💡 **Features:**\n"
                "- Professional PDF layout\n"
                "- Clean Khmer text rendering\n"
                "- Proper paragraph formatting\n"
                "- Consistent spacing\n\n"
                "👨‍💻 **TENG SAMBATH**")
    
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
        # Fixed: Avoid f-string with backslashes
        font_size_text = str(pdf_bot.font_size) + "px"
        
        # Send processing message
        processing_msg = await update.message.reply_text(
            ("⏳ **កំពុងបង្កើត PDF ជាមួយ margins 0.4\"...**\n"
             "📐 Layout: No Header + Footer Only\n"
             "📝 Font: " + font_size_text + "\n"
             "⚙️ Engine: ReportLab PDF\n"
             "✨ Processing...")
        )
        
        # Create PDF
        pdf_buffer = pdf_bot.create_pdf_document(user_text)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = "SAMBATH_FINAL_" + timestamp + ".pdf"
        
        # Fixed: Avoid f-string with backslashes
        current_time = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        # Send PDF document
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=filename,
            caption=("✅ **បង្កើត PDF ជោគជ័យ!** 🇰🇭\n\n"
                    "🎯 **Layout ចុងក្រោយ:**\n"
                    "• Margins: 0.4\" ទាំង 4 ប្រការ ✅\n"
                    "• Header: ដកចេញ ✅\n"
                    '• Footer: "ទំព័រ 1 | Created by TENG SAMBATH" ✅\n'
                    "• Font Size: " + font_size_text + " ✅\n\n"
                    "📊 **ព័ត៌មានឯកសារ:**\n"
                    "• File Type: PDF\n"
                    "• Layout: Clean & Professional\n"
                    "• Generated: " + current_time + "\n\n"
                    "📄 **ទាញយក PDF ផ្ទាល់បាន!**\n\n"
                    "👨‍💻 **Created by: TENG SAMBATH**")
        )
        
        # Delete processing message
        await processing_msg.delete()
        
        # Log success
        logging.info("Successfully created PDF for user " + str(update.effective_user.id))
        
    except Exception as e:
        logging.error("Error creating PDF: " + str(e))
        await update.message.reply_text(
            ("❌ **មានបញ្ហាកើតឡើង:** " + str(e) + "\n\n"
             "🔄 សូមព្យាយាមម្ដងទៀត\n"
             "💡 ឬផ្ញើអត្ថបទខ្លីជាមុន\n"
             "👨‍💻 Support: TENG SAMBATH")
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
            logging.info("✅ Final PDF Bot started successfully")
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
    title="Final PDF Bot by TENG SAMBATH",
    description="PDF generation with 0.4 inch margins, no header, footer only",
    version="FINAL 1.0",
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
        "message": "Final PDF Bot running! 🤖",
        "version": "FINAL 1.0",
        "developer": "TENG SAMBATH",
        "specifications": {
            "margins": "0.4 inches all sides",
            "header": "Removed",
            "footer": "ទំព័រ 1 | Created by TENG SAMBATH",
            "font_size": str(pdf_bot.font_size) + "px",
            "pdf_only": True
        },
        "reportlab_available": REPORTLAB_AVAILABLE
    }

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "🇰🇭 Final PDF Bot by TENG SAMBATH",
        "version": "FINAL 1.0",
        "developer": "TENG SAMBATH",
        "features": {
            "margins": "0.4 inches all sides",
            "header": "Removed completely", 
            "footer": "ទំព័រ 1 | Created by TENG SAMBATH",
            "font_size": str(pdf_bot.font_size) + "px",
            "mode": "PDF generation only"
        },
        "status": "Production ready - No f-string backslash errors"
    }

# Application entry point
if __name__ == "__main__":
    import uvicorn
    
    # Startup logging
    logging.info("🚀 Starting Final PDF Bot by TENG SAMBATH...")
    logging.info("📐 Margins: 0.4 inches on all sides")
    logging.info("🚫 Header: Removed")
    logging.info("✅ Footer: ទំព័រ 1 | Created by TENG SAMBATH")
    logging.info("📏 Font Size: " + str(pdf_bot.font_size) + "px")
    logging.info("🔧 ReportLab: " + ("Available" if REPORTLAB_AVAILABLE else "Not Available"))
    logging.info("📄 Mode: PDF Generation Only")
    logging.info("✨ F-string backslash issues: FIXED")
    
    # Run the application
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )
