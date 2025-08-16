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
    from reportlab.lib.enums import TA_LEFT
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

class ModifiedMarginsPDFBot:
    def __init__(self):
        self.font_size = 19
        self.footer_font_size = 10
        self.font_name = 'Helvetica'
        self.khmer_font_name = 'Helvetica'
        # Margins ទាំង 4 ជា 0.4 inches
        self.margin_size = 0.4 * inch  # Convert to points (0.4" = 28.8 points)
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
        """បង្កើត PDF document ជាមួយ 0.4" margins និង footer only"""
        if not REPORTLAB_AVAILABLE:
            raise ImportError("ReportLab not available")
            
        buffer = BytesIO()
        
        # Create document ជាមួយ margins 0.4 inches ទាំង 4
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=self.margin_size,      # 0.4"
            bottomMargin=self.margin_size,   # 0.4"
            leftMargin=self.margin_size,     # 0.4"
            rightMargin=self.margin_size,    # 0.4"
            title="TEXT 2PDF BY TENG SAMBATH"
        )
        
        # Get base styles
        styles = getSampleStyleSheet()
        
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
        
        # *** ដក HEADER ចេញ *** (មិនមាន header ទៀត)
        
        # Main content paragraphs
        paragraphs = self.split_into_paragraphs(text)
        
        for i, para_text in enumerate(paragraphs):
            if para_text.strip():
                story.append(Paragraph(para_text, main_style))
                
                # Add spacing between paragraphs
                if i < len(paragraphs) - 1:
                    story.append(Spacer(1, 15))
        
        # Footer section - រក្សាទុក footer ដូចដែលស្នើសុំ
        story.append(Spacer(1, 30))
        footer_text = f"ទំព័រ 1 | Created by TENG SAMBATH"
        story.append(Paragraph(footer_text, footer_style))
        
        # Build the PDF
        doc.build(story)
        
        buffer.seek(0)
        return buffer
    
    def create_html_document(self, text: str) -> BytesIO:
        """បង្កើត HTML document ជា fallback ជាមួយ margins 0.4""""
        
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
    <link href="https://fonts.googleapis.com/css2?family=Battambang:wght@400;700&family=Noto+Sans+Khmer:wght@400;700&display=swap" rel="stylesheet">
    
    <style>
        @media print {{
            @page {{
                size: A4;
                margin: 0.4in;  /* All margins 0.4 inches */
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
            margin: 0.4in;  /* All margins 0.4 inches */
            color: #333;
        }}
        
        /* NO HEADER STYLE - ដក header ចេញ */
        
        .content {{
            margin: 0;  /* ចាប់ផ្តើមពីកំពូល */
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
            font-size: {self.footer_font_size}px;
            color: #666;
            text-align: left;
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
            .print-button {{
                display: none !important;
            }}
        }}
    </style>
</head>
<body>
    <button class="print-button" onclick="window.print()">🖨️ Print to PDF</button>
    
    <!-- NO HEADER - ដក header ចេញ -->
    
    <div class="content">
        {content_html}
    </div>
    
    <div class="footer">
        ទំព័រ 1 | Created by TENG SAMBATH
    </div>
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

# Initialize bot with new configuration
pdf_bot = ModifiedMarginsPDFBot()

# Create bot application
ptb = Application.builder().updater(None).token(TOKEN).read_timeout(10).get_updates_read_timeout(42).build()

# Bot command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = "PDF Generation" if REPORTLAB_AVAILABLE else "HTML with Print to PDF"
    
    welcome_message = f"""🇰🇭 ជំរាបសួរ! Text to PDF Bot (Modified Margins)

🎯 **ការកែតម្រូវថ្មី:**
• Margins: 0.4" ទាំង 4 ប្រការ (Top, Bottom, Left, Right)
• Header: ដកចេញហើយ
• Footer: រក្សាទុក "ទំព័រ 1 | Created by TENG SAMBATH"
• Font Size: {pdf_bot.font_size}px (ធំ និង ច្បាស់)

🔧 **Status:**
• Mode: {mode}
• ReportLab: {'✅ Available' if REPORTLAB_AVAILABLE else '❌ Using HTML'}
• Margins: 0.4 inches ទាំងអស់

📝 **របៀបប្រើ:**
ផ្ញើអត្ថបទខ្មែរមកខ្ញុំ ហើយទទួលបាន PDF ជាមួយ layout ថ្មី!

👨‍💻 **Modified by: TENG SAMBATH**"""
    
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = f"""🆘 **ជំនួយ Modified PDF Bot:**

🔧 **Layout ថ្មី:**
• All Margins: 0.4 inches (28.8 points)
• Header: Removed ✅
• Footer: "ទំព័រ 1 | Created by TENG SAMBATH" ✅
• Font Size: {pdf_bot.font_size}px

📝 **ការប្រើប្រាស់:**
1️⃣ ផ្ញើអត្ថបទខ្មែរមកខ្ញុំ
2️⃣ ទទួលបាន PDF ជាមួយ margins 0.4"
3️⃣ ទាញយកឯកសារ

💡 **ការផ្លាស់ប្តូរ:**
- មិនមាន "TEXT 2PDF BY : TENG SAMBATH" header ទៀត
- Footer នៅមាន: ទំព័រ 1 | Created by TENG SAMBATH  
- Margins តូចជាង (0.4" ជំនួសឱ្យ margins ធម្មតា)

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
        mode = "PDF" if REPORTLAB_AVAILABLE else "HTML"
        processing_msg = await update.message.reply_text(
            f"⏳ **កំពុងបង្កើត {mode} ជាមួយ margins 0.4\"...**\n"
            f"📐 Layout: No Header + Footer Only\n"
            f"📝 Font: {pdf_bot.font_size}px\n"
            f"✨ Processing..."
        )
        
        # Create document
        file_buffer, file_ext, creation_mode = pdf_bot.create_document(user_text)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"SAMBATH_MARGINS_{timestamp}.{file_ext}"
        
        # Send document
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=file_buffer,
            filename=filename,
            caption=f"""✅ **បង្កើត {creation_mode} ជោគជ័យ!** 🇰🇭

🎯 **Layout កែតម្រូវ:**
• Margins: 0.4" ទាំង 4 ប្រការ ✅
• Header: ដកចេញ ✅  
• Footer: "ទំព័រ 1 | Created by TENG SAMBATH" ✅
• Font Size: {pdf_bot.font_size}px (ធំ និង ច្បាស់) ✅

📊 **ព័ត៌មានឯកសារ:**
• File Type: {creation_mode}
• Layout: Clean & Minimal
• Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}

{'📄 **ការប្រើប្រាស់:** ទាញយក PDF ផ្ទាល់!' if file_ext == 'pdf' else '🖨️ **ការប្រើប្រាស់:** បើក HTML → Print → Save as PDF!'}

👨‍💻 **Modified by: TENG SAMBATH**"""
        )
        
        # Delete processing message
        await processing_msg.delete()
        
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

# Add handlers to bot
ptb.add_handler(CommandHandler("start", start_command))
ptb.add_handler(CommandHandler("help", help_command))
ptb.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

# FastAPI application lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        await ptb.bot.set_webhook(webhook_url)
        logging.info(f"✅ Webhook set to: {webhook_url}")
        
        async with ptb:
            await ptb.start()
            logging.info("✅ Modified Margins PDF Bot started successfully")
            yield
            
    except Exception as e:
        logging.error(f"❌ Error in lifespan: {str(e)}")
        yield
    finally:
        try:
            await ptb.stop()
        except Exception as e:
            logging.error(f"❌ Error stopping bot: {str(e)}")

# Create FastAPI application
app = FastAPI(
    title="Modified Margins Text to PDF Bot by TENG SAMBATH",
    description="PDF generation with 0.4\" margins, no header, footer only",
    version="MODIFIED MARGINS 1.0",
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
        "message": "Modified Margins PDF Bot running! 🤖",
        "version": "MODIFIED MARGINS 1.0",
        "developer": "TENG SAMBATH",
        "modifications": {
            "margins": "0.4 inches all sides",
            "header": "Removed",
            "footer": "ទំព័រ 1 | Created by TENG SAMBATH",
            "font_size": f"{pdf_bot.font_size}px"
        },
        "reportlab_available": REPORTLAB_AVAILABLE
    }

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "🇰🇭 Modified Margins Text to PDF Bot",
        "version": "MODIFIED MARGINS 1.0",
        "developer": "TENG SAMBATH",
        "layout_changes": {
            "margins": "0.4\" all sides (Top, Bottom, Left, Right)",
            "header": "Removed completely",
            "footer": "Kept - ទំព័រ 1 | Created by TENG SAMBATH",
            "font_size": f"{pdf_bot.font_size}px"
        },
        "status": "Ready for use"
    }

# Application entry point
if __name__ == "__main__":
    import uvicorn
    
    # Startup logging
    logging.info("🚀 Starting Modified Margins PDF Bot by TENG SAMBATH...")
    logging.info(f"📐 Margins: 0.4\" (Top: 0.4\", Bottom: 0.4\", Left: 0.4\", Right: 0.4\")")
    logging.info("🚫 Header: Removed")
    logging.info("✅ Footer: ទំព័រ 1 | Created by TENG SAMBATH")
    logging.info(f"📏 Font Size: {pdf_bot.font_size}px")
    logging.info(f"🔧 ReportLab: {'Available' if REPORTLAB_AVAILABLE else 'HTML Fallback'}")
    
    # Run the application
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=PORT,
        log_level="info"
    )
