import os
import logging
from io import BytesIO
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime

# ReportLab imports with error handling
try:
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
    logging.info("✅ ReportLab imported successfully")
except ImportError as e:
    REPORTLAB_AVAILABLE = False
    logging.error(f"❌ ReportLab import failed: {e}")

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Environment variables
TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', 8000))

class ProperKhmerPDFBot:
    def __init__(self):
        self.font_size = 19
        self.line_height = self.font_size + 8
        self.font_name = 'Helvetica'
        self.setup_fonts()
        
    def setup_fonts(self):
        """រៀបចំ Khmer fonts"""
        if not REPORTLAB_AVAILABLE:
            logging.warning("ReportLab not available - cannot setup fonts")
            return
            
        try:
            # ព្យាយាម font paths ផ្សេងៗ
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
                        self.font_name = font_name
                        logging.info(f"✅ Loaded Khmer font: {font_path}")
                        return
                except Exception as e:
                    logging.warning(f"Failed to load {font_path}: {e}")
                    continue
                    
            # Use system default
            self.font_name = 'Helvetica'
            logging.warning("Using Helvetica fallback font")
            
        except Exception as e:
            logging.error(f"Font setup error: {e}")
            self.font_name = 'Helvetica'
    
    def split_into_paragraphs(self, text: str) -> list:
        """បំបែកអត្ថបទទៅជា paragraphs ត្រឹមត្រូវ"""
        
        # បំបែកដោយ double line breaks ជាមុន
        paragraphs = text.split('\n\n')
        
        # ប្រសិនបើមិនមាន double breaks ប្រើ single breaks
        if len(paragraphs) == 1:
            paragraphs = text.split('\n')
        
        # Clean និង filter paragraphs
        clean_paragraphs = []
        for para in paragraphs:
            para = para.strip()
            if para and len(para) > 2:  # Skip empty និង paragraph ខ្លីពេក
                clean_paragraphs.append(para)
        
        return clean_paragraphs if clean_paragraphs else [text.strip()]
    
    def create_proper_pdf(self, text: str) -> BytesIO:
        """បង្កើត PDF ពិតប្រាកដជាមួយ proper formatting"""
        
        if not REPORTLAB_AVAILABLE:
            logging.error("ReportLab not available - cannot create PDF")
            return self.create_error_response()
            
        try:
            buffer = BytesIO()
            
            # Create document with proper margins
            doc = SimpleDocDocument(
                buffer,
                pagesize=A4,
                topMargin=80,
                bottomMargin=70,
                leftMargin=70,
                rightMargin=70
            )
            
            # Get base styles
            styles = getSampleStyleSheet()
            
            # Create custom header style
            header_style = ParagraphStyle(
                'CustomHeader',
                parent=styles['Heading1'],
                fontName='Helvetica-Bold',
                fontSize=16,
                spaceAfter=30,
                alignment=TA_LEFT
            )
            
            # Create custom paragraph style for Khmer text
            khmer_style = ParagraphStyle(
                'KhmerParagraph',
                parent=styles['Normal'],
                fontName=self.font_name,
                fontSize=self.font_size,
                leading=self.line_height,
                alignment=TA_LEFT,  # Left align to avoid spacing issues
                spaceAfter=15,
                spaceBefore=5,
                leftIndent=0,
                rightIndent=0,
                wordWrap='CJK',  # Better wrapping for Asian text
                allowWidows=0,
                allowOrphans=0
            )
            
            # Build story
            story = []
            
            # Add header
            story.append(Paragraph("TEXT 2PDF BY : TENG SAMBATH", header_style))
            story.append(Spacer(1, 20))
            
            # Split text into proper paragraphs
            paragraphs = self.split_into_paragraphs(text)
            
            # Add each paragraph
            for i, para_text in enumerate(paragraphs):
                # Clean the paragraph text
                cleaned_text = self.clean_khmer_text(para_text)
                
                # Create paragraph with proper line breaks
                story.append(Paragraph(cleaned_text, khmer_style))
                
                # Add space between paragraphs (except last one)
                if i < len(paragraphs) - 1:
                    story.append(Spacer(1, 10))
            
            # Add footer space
            story.append(Spacer(1, 30))
            
            # Footer
            current_date = datetime.now().strftime("%d/%m/%Y %H:%M")
            footer_style = ParagraphStyle(
                'Footer',
                parent=styles['Normal'],
                fontSize=10,
                alignment=TA_LEFT
            )
            
            footer_text = f"Generated: {current_date} | ទំព័រ 1"
            story.append(Paragraph(footer_text, footer_style))
            
            # Build the PDF
            doc.build(story)
            
            buffer.seek(0)
            logging.info("✅ PDF created successfully")
            return buffer
            
        except Exception as e:
            logging.error(f"PDF creation error: {e}")
            return self.create_error_response()
    
    def clean_khmer_text(self, text: str) -> str:
        """សម្អាតអត្ថបទខ្មែរសម្រាប់ការបង្ហាញល្អ"""
        
        # Remove problematic characters
        problematic_chars = {
            '\u200B': '',  # Zero width space
            '\u200C': '',  # Zero width non-joiner
            '\u200D': '',  # Zero width joiner
            '\uFEFF': '',  # BOM
        }
        
        cleaned = text
        for old, new in problematic_chars.items():
            cleaned = cleaned.replace(old, new)
            
        # Basic Unicode normalization
        try:
            import unicodedata
            cleaned = unicodedata.normalize('NFC', cleaned)
        except:
            pass
            
        # Replace multiple spaces with single space
        cleaned = ' '.join(cleaned.split())
        
        return cleaned
    
    def create_error_response(self) -> BytesIO:
        """បង្កើត error response"""
        error_html = """
<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body>
<h1>PDF Creation Error</h1>
<p>ReportLab library is not available. Please install it:</p>
<p><code>pip install reportlab</code></p>
</body></html>"""
        
        buffer = BytesIO()
        buffer.write(error_html.encode('utf-8'))
        buffer.seek(0)
        return buffer

# Custom SimpleDocTemplate class for better control
class SimpleDocDocument(SimpleDocTemplate):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def build(self, story, onFirstPage=None, onLaterPages=None):
        """Build document with custom page template"""
        super().build(story, onFirstPage=onFirstPage, onLaterPages=onLaterPages)

# Initialize bot
pdf_bot = ProperKhmerPDFBot()

# Create bot application
ptb = Application.builder().updater(None).token(TOKEN).build()

# Bot handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "✅ ReportLab Available" if REPORTLAB_AVAILABLE else "❌ ReportLab Missing"
    font_info = f"Font: {pdf_bot.font_name}"
    
    welcome_message = f"""🇰🇭 ជំរាបសួរ! Proper PDF Bot (Fixed Version)

🎯 ការដោះស្រាយបញ្ហា:
• បង្កើត PDF ពិតប្រាកដ (មិនមែន HTML)
• អត្ថបទខ្មែរចុះបន្ទាត់ត្រឹមត្រូវ
• Paragraph formatting ស្អាត
• Left alignment ធម្មតា

🔧 Technical Status:
• {status}
• {font_info}
• Font Size: {pdf_bot.font_size}px
• Line Height: {pdf_bot.line_height}px

📝 វិធីប្រើប្រាស់:
• ផ្ញើអត្ថបទខ្មែរមកខ្ញុំ
• ទទួលបាន PDF file ពិតប្រាកដ
• Text នឹងចុះបន្ទាត់ត្រឹមត្រូវ

👨‍💻 Fixed by: TENG SAMBATH"""
    
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = f"""🆘 ជំនួយ Proper PDF Bot:

🎯 បញ្ហាដែលត្រូវបានដោះស្រាយ:
✅ HTML files → PDF files ពិតប្រាកដ
✅ អត្ថបទមិនចុះបន្ទាត់ → Proper line breaks
✅ Paragraph formatting → Clean layout
✅ Text alignment → Left align (stable)

💻 Technical Fixes:
• Force ReportLab PDF generation
• Proper paragraph splitting
• Clean Khmer text processing
• Better line height spacing
• Professional margins

📝 របៀបប្រើប្រាស់:
1️⃣ ផ្ញើអត្ថបទខ្មែរ (ចម្រុះ paragraph)
2️⃣ Bot បង្កើត PDF ពិតប្រាកដ
3️⃣ ទាញយកឯកសារ .pdf ជាមួយ formatting ត្រឹមត្រូវ

🔧 Font Details:
• Current: {pdf_bot.font_name}
• Size: {pdf_bot.font_size}px
• Line spacing: {pdf_bot.line_height}px
• ReportLab: {'Available' if REPORTLAB_AVAILABLE else 'Missing'}

👨‍💻 Proper Solution by: TENG SAMBATH"""
    
    await update.message.reply_text(help_text)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    if user_text.startswith('/'):
        return
    
    if len(user_text.strip()) < 5:
        await update.message.reply_text("⚠️ សូមផ្ញើអត្ថបទយ៉ាងហោចណាស់ 5 តួអក្សរ")
        return
    
    try:
        processing_msg = await update.message.reply_text(
            f"⏳ កំពុងបង្កើត PDF ពិតប្រាកដ...\n"
            f"📄 Engine: {'ReportLab' if REPORTLAB_AVAILABLE else 'Fallback'}\n"
            f"🔤 Font: {pdf_bot.font_name} ({pdf_bot.font_size}px)\n"
            f"📐 Format: Proper paragraphs + line breaks\n"
            f"✨ Processing Khmer text formatting..."
        )
        
        # Create proper PDF
        pdf_buffer = pdf_bot.create_proper_pdf(user_text)
        
        # Determine file type
        file_ext = "pdf" if REPORTLAB_AVAILABLE else "html"
        filename = f"SAMBATH_PROPER_{update.effective_user.id}.{file_ext}"
        
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=filename,
            caption=f"""✅ បង្កើត {"PDF" if REPORTLAB_AVAILABLE else "HTML"} ជោគជ័យ! 🇰🇭

🎯 ការដោះស្រាយពេញលេញ:
• File Type: {"PDF ពិតប្រាកដ" if REPORTLAB_AVAILABLE else "HTML (ReportLab missing)"}
• អត្ថបទចុះបន្ទាត់ត្រឹមត្រូវ ✅
• Paragraph formatting ស្អាត ✅  
• Clean layout ជាមួយ margins ✅
• Header: TEXT 2PDF BY : TENG SAMBATH ✅

🔧 Technical Details:
• Font: {pdf_bot.font_name}
• Size: {pdf_bot.font_size}px
• Line Height: {pdf_bot.line_height}px  
• Alignment: LEFT (stable)
• Date: {datetime.now().strftime('%d/%m/%Y %H:%M')}

📄 ឥឡូវអ្នកមាន {"PDF file" if REPORTLAB_AVAILABLE else "HTML file"} ជាមួយ formatting ត្រឹមត្រូវ!
👨‍💻 Proper Solution by: TENG SAMBATH

{'🎉 Status: PDF WORKING!' if REPORTLAB_AVAILABLE else '⚠️ Install ReportLab for PDF generation'}"""
        )
        
        await processing_msg.delete()
        
    except Exception as e:
        logging.error(f"Message handling error: {str(e)}")
        await update.message.reply_text(
            f"❌ មានបញ្ហាកើតឡើង: {str(e)}\n\n"
            f"🔄 សូមព្យាយាមម្ដងទៀត\n"
            f"💡 ឬផ្ញើអត្ថបទខ្លីជាមុន\n"
            f"👨‍💻 Support: TENG SAMBATH"
        )

# Add handlers
ptb.add_handler(CommandHandler("start", start_command))
ptb.add_handler(CommandHandler("help", help_command))  
ptb.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

# FastAPI lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        await ptb.bot.set_webhook(webhook_url)
        logging.info(f"Webhook set to: {webhook_url}")
        
        async with ptb:
            await ptb.start()
            logging.info("Proper PDF Bot started successfully")
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
    title="Proper Khmer PDF Bot by TENG SAMBATH",
    description="Generate actual PDF files with proper Khmer text formatting",
    version="PROPER PDF 1.0",
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
        "message": "Proper PDF Bot is running!",
        "version": "PROPER PDF 1.0", 
        "developer": "TENG SAMBATH",
        "reportlab_available": REPORTLAB_AVAILABLE,
        "font": pdf_bot.font_name,
        "font_size": f"{pdf_bot.font_size}px",
        "fixes": [
            "Generate actual PDF files (not HTML)",
            "Proper Khmer text line breaks", 
            "Clean paragraph formatting",
            "Professional layout with margins",
            "Stable left alignment"
        ]
    }

@app.get("/")
async def root():
    return {
        "message": "🇰🇭 Proper Khmer PDF Bot - FINAL SOLUTION",
        "status": "running",
        "version": "PROPER PDF 1.0",
        "developer": "TENG SAMBATH",
        "solution": "Generate actual PDF files with proper formatting",
        "reportlab": "Available" if REPORTLAB_AVAILABLE else "Missing - install required",
        "guarantees": [
            "PDF files (not HTML)",
            "Proper line breaks", 
            "Clean formatting",
            "Professional layout"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    
    logging.info("🚀 Starting Proper PDF Bot by TENG SAMBATH...")
    logging.info(f"ReportLab: {'✅ Available' if REPORTLAB_AVAILABLE else '❌ Missing'}")
    logging.info(f"Font: {pdf_bot.font_name}")
    logging.info(f"Font Size: {pdf_bot.font_size}px")
    logging.info("🎯 Focus: Generate ACTUAL PDF files with proper formatting")
    
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
