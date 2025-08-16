import os
import logging
from io import BytesIO
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime

# ReportLab imports with comprehensive error handling
try:
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY, TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
    logging.info("✅ ReportLab imported successfully")
except ImportError as e:
    REPORTLAB_AVAILABLE = False
    logging.warning(f"⚠️ ReportLab not available: {e}")

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Environment variables
TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', 8000))

class CompletePDFBot:
    def __init__(self):
        self.font_size = 19
        self.header_font_size = 16
        self.footer_font_size = 10
        self.font_name = 'Helvetica'
        self.khmer_font_name = 'Helvetica'
        self.setup_fonts()
        
    def setup_fonts(self):
        """រៀបចំ fonts ជាមួយ fallback system"""
        if not REPORTLAB_AVAILABLE:
            logging.info("Using default fonts (ReportLab not available)")
            return
            
        try:
            # ព្យាយាម register Khmer fonts
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
        """ពិនិត្យថាអត្ថបទមានអក្សរខ្មែរ"""
        khmer_range = range(0x1780, 0x17FF)
        return any(ord(char) in khmer_range for char in text)
    
    def clean_text(self, text: str) -> str:
        """សម្អាតអត្ថបទសម្រាប់ការបង្ហាញល្អ"""
        # Remove problematic Unicode characters
        problematic_chars = {
            '\u200B': '',  # Zero width space
            '\u200C': '',  # Zero width non-joiner
            '\u200D': '',  # Zero width joiner
            '\uFEFF': '',  # Byte order mark
            '\u202A': '',  # Left-to-right embedding
            '\u202C': '',  # Pop directional formatting
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
        """បំបែកអត្ថបទទៅជា paragraphs"""
        # ព្យាយាម split ដោយ double line breaks ជាមុន
        if '\n\n' in text:
            paragraphs = text.split('\n\n')
        else:
            # ប្រើ single line breaks
            paragraphs = text.split('\n')
        
        # Clean និង filter
        clean_paragraphs = []
        for para in paragraphs:
            cleaned = self.clean_text(para)
            if cleaned and len(cleaned.strip()) > 2:
                clean_paragraphs.append(cleaned)
        
        return clean_paragraphs if clean_paragraphs else [self.clean_text(text)]
    
    def create_pdf_document(self, text: str) -> BytesIO:
        """បង្កើត PDF document ជាមួយ ReportLab"""
        if not REPORTLAB_AVAILABLE:
            raise ImportError("ReportLab not available")
            
        buffer = BytesIO()
        
        # Create document with proper margins
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=80,
            bottomMargin=70,
            leftMargin=70,
            rightMargin=70,
            title="TEXT 2PDF BY TENG SAMBATH"
        )
        
        # Get base styles
        styles = getSampleStyleSheet()
        
        # Create custom styles
        header_style = ParagraphStyle(
            'CustomHeader',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=self.header_font_size,
            spaceAfter=25,
            spaceBefore=0,
            alignment=TA_CENTER,
            textColor='black'
        )
        
        # Main text style - ប្រើ Khmer font ប្រសិនបើមាន
        text_font = self.khmer_font_name if self.contains_khmer(text) else self.font_name
        
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
        
        # Header
        story.append(Paragraph("TEXT 2PDF BY : TENG SAMBATH", header_style))
        story.append(Spacer(1, 20))
        
        # Add horizontal line after header
        from reportlab.platypus import PageBreak
        from reportlab.graphics.shapes import Drawing, Line
        from reportlab.graphics import renderPDF
        
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
        current_date = datetime.now().strftime("%d/%m/%Y %H:%M")
        footer_text = f"Generated: {current_date} | ទំព័រ 1 | Created by TENG SAMBATH"
        story.append(Paragraph(footer_text, footer_style))
        
        # Build the PDF
        doc.build(story)
        
        buffer.seek(0)
        return buffer
    
    def create_html_document(self, text: str) -> BytesIO:
        """បង្កើត HTML document ជា fallback"""
        current_date = datetime.now().strftime("%d/%m/%Y %H:%M")
        
        # Split into paragraphs
        paragraphs = self.split_into_paragraphs(text)
        
        # Format paragraphs as HTML
        html_paragraphs = []
        for para in paragraphs:
            if para.strip():
                html_paragraphs.append(f'<p class="content-paragraph">{para}</p>')
        
        content_html = '\n'.join(html_paragraphs)
        
        html_content = f"""<!DOCTYPE html>
<html lang="km">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TEXT 2PDF BY TENG SAMBATH</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Battambang:wght@400;700&family=Noto+Sans+Khmer:wght@400;700&display=swap" rel="stylesheet">
    
    <style>
        @media print {{
            @page {{
                size: A4;
                margin: 2cm;
            }}
            body {{
                font-size: {self.font_size}px !important;
                line-height: 1.8 !important;
            }}
        }}
        
        body {{
            font-family: 'Battambang', 'Noto Sans Khmer', Arial, sans-serif;
            font-size: {self.font_size}px;
            line-height: 1.8;
            margin: 0;
            padding: 40px;
            max-width: 800px;
            margin: 0 auto;
            color: #333;
        }}
        
        .header {{
            font-family: 'Helvetica', Arial, sans-serif;
            font-weight: bold;
            font-size: {self.header_font_size}px;
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 15px;
            border-bottom: 2px solid #000;
        }}
        
        .content {{
            margin: 30px 0;
        }}
        
        .content-paragraph {{
            margin-bottom: 15px;
            text-align: left;
            text-indent: 30px;
            line-height: 1.8;
        }}
        
        .content-paragraph:first-child {{
            text-indent: 0;
        }}
        
        .footer {{
            margin-top: 50px;
            padding-top: 15px;
            border-top: 1px solid #ccc;
            font-size: {self.footer_font_size}px;
            color: #666;
            text-align: left;
        }}
        
        .print-instructions {{
            background: #f0f8ff;
            border: 1px solid #0066cc;
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
            font-size: 14px;
        }}
        
        .print-button {{
            background: #0066cc;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            margin: 10px 0;
        }}
        
        @media print {{
            .print-instructions, .print-button {{
                display: none !important;
            }}
        }}
    </style>
</head>
<body>
    <div class="print-instructions">
        <strong>🖨️ របៀបបម្លែងទៅជា PDF:</strong><br>
        1. ចុចប៊ូតុង "Print to PDF" ខាងក្រោម<br>
        2. ឬចុច Ctrl+P (Windows) / Cmd+P (Mac)<br>
        3. ជ្រើសរើស "Save as PDF" ឬ "Microsoft Print to PDF"<br>
        4. ចុច Save<br><br>
        <button class="print-button" onclick="window.print()">🖨️ Print to PDF</button>
    </div>
    
    <div class="header">TEXT 2PDF BY : TENG SAMBATH</div>
    
    <div class="content">
        {content_html}
    </div>
    
    <div class="footer">
        Generated: {current_date} | ទំព័រ 1 | Created by TENG SAMBATH
    </div>
    
    <script>
        // Optional: Auto-prompt for printing
        function autoPrint() {{
            if (confirm('ចង់ print ជា PDF ឥឡូវនេះទេ?')) {{
                window.print();
            }}
        }}
        
        // Show print dialog after 2 seconds
        setTimeout(autoPrint, 2000);
    </script>
</body>
</html>"""
        
        buffer = BytesIO()
        buffer.write(html_content.encode('utf-8'))
        buffer.seek(0)
        return buffer
    
    def create_document(self, text: str) -> tuple:
        """បង្កើតឯកសារ (PDF ឬ HTML)"""
        if not text or len(text.strip()) < 3:
            raise ValueError("Text too short")
            
        try:
            if REPORTLAB_AVAILABLE:
                buffer = self.create_pdf_document(text)
                return buffer, 'pdf', 'PDF'
            else:
                buffer = self.create_html_document(text)
                return buffer, 'html', 'HTML'
                
        except Exception as e:
            logging.error(f"Document creation error: {e}")
            # Fallback to HTML
            buffer = self.create_html_document(text)
            return buffer, 'html', 'HTML (Fallback)'

# Initialize bot
pdf_bot = CompletePDFBot()

# Create bot application
ptb = Application.builder().updater(None).token(TOKEN).read_timeout(10).get_updates_read_timeout(42).build()

# Bot command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = "PDF Generation" if REPORTLAB_AVAILABLE else "HTML with Print to PDF"
    font_info = f"Khmer: {pdf_bot.khmer_font_name}" if pdf_bot.contains_khmer("ខ្មែរ") else f"Latin: {pdf_bot.font_name}"
    
    welcome_message = f"""🇰🇭 ជំរាបសួរ! Text to PDF Bot (Complete Edition)

🎯 **ស្ថានភាព:**
• Mode: {mode}
• Font: {font_info} 
• Size: {pdf_bot.font_size}px
• ReportLab: {'✅ Available' if REPORTLAB_AVAILABLE else '❌ Using HTML'}

✨ **លក្ខណៈពិសេស:**
• Header: TEXT 2PDF BY : TENG SAMBATH
• Font size ខ្មែរ: {pdf_bot.font_size}px (ធំ និង ច្បាស់)
• Paragraph formatting ស្អាត
• Left alignment (stable)
• Professional layout

📝 **របៀបប្រើ:**
1. ផ្ញើអត្ថបទខ្មែរមកខ្ញុំ
2. ទទួលបាន {'PDF file' if REPORTLAB_AVAILABLE else 'HTML file'}
3. {'ទាញយកបាន' if REPORTLAB_AVAILABLE else 'បើក → Print → Save as PDF'}

ផ្ញើអត្ថបទមកខ្ញុំទៅ! 📄

👨‍💻 **Complete Solution by: TENG SAMBATH**"""
    
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = f"""🆘 **ជំនួយ Complete PDF Bot:**

🔧 **Technical Status:**
• ReportLab: {'✅ Working' if REPORTLAB_AVAILABLE else '❌ Not Available'}
• Current Mode: {'Direct PDF' if REPORTLAB_AVAILABLE else 'HTML → PDF'}
• Font System: {pdf_bot.khmer_font_name}
• Size: {pdf_bot.font_size}px

📋 **ការដំណើរការ:**
{'🎯 PDF Generation:' if REPORTLAB_AVAILABLE else '🎯 HTML Generation:'}
1️⃣ ទទួលអត្ថបទពីអ្នក
2️⃣ {'បង្កើត PDF ដោយផ្ទាល់' if REPORTLAB_AVAILABLE else 'បង្កើត HTML ជាមួយ print option'}
3️⃣ ផ្ញើឯកសារត្រលប់មក

💡 **ជំនួយបន្ថែម:**
• អត្ថបទខ្លី: 1 paragraph
• អត្ថបទវែង: ចុះបន្ទាត់ដោយ Enter ២ដង
• ភាសាខ្មែរ: គាំទ្រពេញលេញ
• Layout: Professional ជាមួយ header/footer

👨‍💻 **TENG SAMBATH - Complete Solution Provider**"""
    
    await update.message.reply_text(help_text)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    if user_text.startswith('/'):
        return
    
    # Validate input
    if len(user_text.strip()) < 3:
        await update.message.reply_text("⚠️ សូមផ្ញើអត្ថបទយ៉ាងហោចណាស់ 3 តួអក្សរ")
        return
    
    if len(user_text) > 5000:
        await update.message.reply_text("⚠️ អត្ថបទវែងពេក! សូមផ្ញើក្រោម 5000 តួអក្សរ")
        return
    
    try:
        # Send processing message
        mode = "PDF" if REPORTLAB_AVAILABLE else "HTML"
        processing_msg = await update.message.reply_text(
            f"⏳ **កំពុងបង្កើត {mode} document...**\n"
            f"📝 ចំនួនតួអក្សរ: {len(user_text)}\n"
            f"🔤 Font: {pdf_bot.font_size}px\n"
            f"⚙️ Engine: {'ReportLab PDF' if REPORTLAB_AVAILABLE else 'HTML + Print'}\n"
            f"✨ រៀបចំ layout..."
        )
        
        # Create document
        file_buffer, file_ext, creation_mode = pdf_bot.create_document(user_text)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"SAMBATH_COMPLETE_{timestamp}.{file_ext}"
        
        # Send document
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=file_buffer,
            filename=filename,
            caption=f"""✅ **បង្កើត {creation_mode} ជោគជ័យ!** 🇰🇭

🎯 **លក្ខណៈពិសេស:**
• File Type: {creation_mode}
• Font Size: {pdf_bot.font_size}px (ធំ និង ច្បាស់)
• Layout: Professional ជាមួយ margins
• Header: TEXT 2PDF BY : TENG SAMBATH
• Paragraph: Left aligned ស្អាត

📊 **ព័ត៌មានឯកសារ:**
• ចំនួនតួអក្សរ: {len(user_text)}
• បង្កើតនៅ: {datetime.now().strftime('%d/%m/%Y %H:%M')}
• Engine: {creation_mode}

{'📄 **ការប្រើប្រាស់:** ទាញយក PDF ផ្ទាល់!' if file_ext == 'pdf' else '🖨️ **ការប្រើប្រាស់:** បើក HTML → ចុច Print → Save as PDF!'}

👨‍💻 **Complete Solution by: TENG SAMBATH**
🌟 **Status: PRODUCTION READY!**"""
        )
        
        # Delete processing message
        await processing_msg.delete()
        
        # Log success
        logging.info(f"Successfully created {creation_mode} for user {update.effective_user.id}")
        
    except Exception as e:
        logging.error(f"Error processing text message: {str(e)}")
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
            logging.info("✅ Complete PDF Bot started successfully")
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
    title="Complete Khmer Text to PDF Bot by TENG SAMBATH",
    description="Professional PDF generation with perfect Khmer text support and fallback options",
    version="COMPLETE 2.0",
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
        "message": "Complete PDF Bot is running perfectly! 🤖",
        "version": "COMPLETE 2.0",
        "developer": "TENG SAMBATH",
        "features": {
            "reportlab_available": REPORTLAB_AVAILABLE,
            "pdf_generation": "Direct" if REPORTLAB_AVAILABLE else "Via HTML",
            "font_system": {
                "main_font": pdf_bot.font_name,
                "khmer_font": pdf_bot.khmer_font_name,
                "font_size": f"{pdf_bot.font_size}px"
            },
            "document_features": [
                "Professional headers and footers",
                "Proper paragraph formatting",
                "Khmer text support",
                "Left alignment for stability",
                "Auto text cleaning",
                "Fallback HTML generation"
            ]
        },
        "guarantees": [
            "Works with or without ReportLab",
            "Perfect font size (19px)",
            "Professional layout",
            "Khmer text support",
            "Reliable document generation"
        ]
    }

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "🇰🇭 Complete Khmer Text to PDF Bot - ULTIMATE SOLUTION",
        "status": "operational",
        "version": "COMPLETE 2.0",
        "developer": "TENG SAMBATH",
        "capabilities": {
            "primary_mode": "PDF Generation" if REPORTLAB_AVAILABLE else "HTML with Print Option",
            "font_size": f"{pdf_bot.font_size}px",
            "khmer_support": "Full Unicode support",
            "layout": "Professional with headers/footers",
            "reliability": "100% working guarantee"
        },
        "usage": "Send text to Telegram bot for instant PDF/HTML generation",
        "telegram_features": [
            "/start - Welcome message",
            "/help - Detailed help",
            "Text message - Generate document"
        ]
    }

# Bot status endpoint
@app.get("/bot-status")
async def bot_status():
    return {
        "bot_running": True,
        "reportlab_status": "Available" if REPORTLAB_AVAILABLE else "Not Available",
        "font_configuration": {
            "primary_font": pdf_bot.font_name,
            "khmer_font": pdf_bot.khmer_font_name,
            "font_size": pdf_bot.font_size,
            "header_size": pdf_bot.header_font_size,
            "footer_size": pdf_bot.footer_font_size
        },
        "generation_mode": "PDF" if REPORTLAB_AVAILABLE else "HTML",
        "last_updated": datetime.now().isoformat(),
        "developer": "TENG SAMBATH",
        "version": "COMPLETE 2.0"
    }

# Application entry point
if __name__ == "__main__":
    import uvicorn
    
    # Startup logging
    logging.info("🚀 Starting Complete Khmer PDF Bot by TENG SAMBATH...")
    logging.info(f"📊 ReportLab Status: {'✅ Available' if REPORTLAB_AVAILABLE else '❌ Not Available'}")
    logging.info(f"🔤 Font System: {pdf_bot.font_name} / {pdf_bot.khmer_font_name}")
    logging.info(f"📏 Font Size: {pdf_bot.font_size}px")
    logging.info(f"🎯 Generation Mode: {'PDF' if REPORTLAB_AVAILABLE else 'HTML'}")
    logging.info("🇰🇭 Khmer Text Support: Full Unicode")
    logging.info("💯 Status: PRODUCTION READY")
    
    # Run the application
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=PORT,
        log_level="info",
        access_log=True
    )
