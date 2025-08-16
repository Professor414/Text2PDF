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
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.enums import TA_LEFT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Environment variables
TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', 8000))

class SimpleKhmerLeftAlignBot:
    def __init__(self):
        self.font_size = 19
        self.font_name = 'Helvetica'  # Default safe font
        self.setup_khmer_font()
    
    def setup_khmer_font(self):
        """រៀបចំ Khmer font (simple approach)"""
        if not REPORTLAB_AVAILABLE:
            return
            
        try:
            # ព្យាយាម font paths ផ្សេងៗ
            font_paths = [
                'font/Battambang-Regular.ttf',
                '/usr/share/fonts/truetype/khmer/KhmerOS.ttf',
                '/System/Library/Fonts/Khmer Sangam MN.ttc'
            ]
            
            for font_path in font_paths:
                try:
                    if os.path.exists(font_path):
                        pdfmetrics.registerFont(TTFont('KhmerFont', font_path))
                        self.font_name = 'KhmerFont'
                        logging.info(f"Loaded Khmer font: {font_path}")
                        return
                except Exception as e:
                    logging.warning(f"Failed to load {font_path}: {e}")
                    continue
                    
            # Fallback: ប្រើ default font
            logging.warning("Using Helvetica - Khmer may not display correctly")
            self.font_name = 'Helvetica'
            
        except Exception as e:
            logging.error(f"Font setup error: {e}")
            self.font_name = 'Helvetica'
    
    def create_simple_pdf(self, text: str) -> BytesIO:
        """បង្កើត Simple PDF ជាមួយ Left Alignment"""
        if not REPORTLAB_AVAILABLE:
            return self.create_fallback_html(text)
            
        try:
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, 
                                  topMargin=80, bottomMargin=60,
                                  leftMargin=60, rightMargin=60)
            
            # Get styles
            styles = getSampleStyleSheet()
            
            # Create simple left-aligned style
            left_style = ParagraphStyle(
                'SimpleLeft',
                parent=styles['Normal'],
                fontName=self.font_name,
                fontSize=self.font_size,
                alignment=TA_LEFT,
                leading=self.font_size + 6,
                leftIndent=0,
                rightIndent=0,
                spaceAfter=12,
                wordWrap='CJK'  # Better for Asian text
            )
            
            # Header style
            header_style = ParagraphStyle(
                'Header',
                parent=styles['Normal'],
                fontName='Helvetica-Bold',
                fontSize=16,
                alignment=TA_LEFT,
                spaceAfter=20
            )
            
            # Build content
            story = []
            
            # Add header
            header_text = "TEXT 2PDF BY : TENG SAMBATH"
            story.append(Paragraph(header_text, header_style))
            story.append(Spacer(1, 12))
            
            # Split text into paragraphs
            paragraphs = text.split('\n\n')
            if not paragraphs or (len(paragraphs) == 1 and not paragraphs[0].strip()):
                paragraphs = text.split('\n')
            
            # Add each paragraph with left alignment
            for para_text in paragraphs:
                if para_text.strip():
                    # Clean up text for better rendering
                    cleaned_text = self.clean_khmer_text(para_text.strip())
                    story.append(Paragraph(cleaned_text, left_style))
                    story.append(Spacer(1, 6))
            
            # Footer
            current_date = datetime.now().strftime("%d/%m/%Y %H:%M")
            footer_text = f"Generated: {current_date} | ទំព័រ 1"
            footer_style = ParagraphStyle(
                'Footer',
                parent=styles['Normal'],
                fontSize=10,
                alignment=TA_LEFT
            )
            story.append(Spacer(1, 20))
            story.append(Paragraph(footer_text, footer_style))
            
            # Build PDF
            doc.build(story)
            buffer.seek(0)
            return buffer
            
        except Exception as e:
            logging.error(f"Simple PDF creation error: {e}")
            return self.create_fallback_html(text)
    
    def clean_khmer_text(self, text: str) -> str:
        """សម្អាតអត្ថបទខ្មែរសម្រាប់ការបង្ហាញល្អប្រសើរ"""
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
        
        # Basic normalization
        try:
            import unicodedata
            cleaned = unicodedata.normalize('NFC', cleaned)
        except:
            pass
            
        return cleaned
    
    def create_fallback_html(self, text: str) -> BytesIO:
        """Fallback HTML ប្រសិនបើ ReportLab មិនដំណើរការ"""
        current_date = datetime.now().strftime("%d/%m/%Y %H:%M")
        
        html_content = f"""
<!DOCTYPE html>
<html lang="km">
<head>
    <meta charset="UTF-8">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Battambang&display=swap');
        body {{
            font-family: 'Battambang', Arial, sans-serif;
            font-size: {self.font_size}px;
            line-height: 1.6;
            margin: 60px;
            text-align: left;
        }}
        .header {{
            font-weight: bold;
            font-size: 16px;
            margin-bottom: 30px;
        }}
        .content {{
            margin: 20px 0;
            text-align: left;
        }}
        .footer {{
            margin-top: 40px;
            font-size: 12px;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="header">TEXT 2PDF BY : TENG SAMBATH</div>
    <div class="content">{text.replace(chr(10), '<br>')}</div>
    <div class="footer">Generated: {current_date} | ទំព័រ 1</div>
</body>
</html>"""
        
        buffer = BytesIO()
        buffer.write(html_content.encode('utf-8'))
        buffer.seek(0)
        return buffer

# Initialize bot
pdf_bot = SimpleKhmerLeftAlignBot()

# Create bot application
ptb = Application.builder().updater(None).token(TOKEN).build()

# Bot handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    engine = "ReportLab" if REPORTLAB_AVAILABLE else "HTML Fallback"
    font_info = f"Font: {pdf_bot.font_name}"
    
    welcome_message = f"""🇰🇭 ជំរាបសួរ! Simple Text to PDF Bot

✨ Simple Features (Left Align):
• Text alignment: LEFT (មិនមែន justify)
• អក្សរទំហំ: {pdf_bot.font_size}px
• {font_info}
• Header: TEXT 2PDF BY : TENG SAMBATH
• Engine: {engine}

📝 ការប្រែប្រួល:
• គ្មាន text justify (ដែលបង្កបញ្ហា)
• Left align តម្រង់ចោល
• Simple paragraph ធម្មតា
• Clean Khmer text processing

ផ្ញើអត្ថបទមកខ្ញុំ (Left aligned)!"""
    
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = f"""🆘 Simple Help - Left Alignment:

🎯 ការដោះស្រាយ:
• ប្រើ Left Alignment ជំនួសឱ្យ Justify
• មិនបង្ខំ text ឱ្យ "ពន្យាត"
• Simple paragraph style
• Clean text preprocessing

📝 របៀបប្រើ:
1️⃣ ផ្ញើអត្ថបទខ្មែរមកខ្ញុំ
2️⃣ ទទួលបាន PDF ជាមួយ Left alignment
3️⃣ អត្ថបទនឹងតម្រង់ចោលធម្មតា

🔧 Technical:
• Font: {pdf_bot.font_name}
• Size: {pdf_bot.font_size}px  
• Alignment: LEFT (simple)
• ReportLab: {'Available' if REPORTLAB_AVAILABLE else 'HTML mode'}

👨‍💻 Simple Solution by: TENG SAMBATH"""
    
    await update.message.reply_text(help_text)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    if user_text.startswith('/'):
        return
    
    if len(user_text.strip()) < 3:
        await update.message.reply_text("⚠️ សូមផ្ញើអត្ថបទយ៉ាងហោចណាស់ 3 តួអក្សរ")
        return
    
    try:
        processing_msg = await update.message.reply_text(
            f"⏳ កំពុងបង្កើត Simple PDF (Left Aligned)...\n"
            f"📐 Alignment: LEFT (មិនមែន justify)\n"  
            f"🔤 Font: {pdf_bot.font_name}\n"
            f"📏 Size: {pdf_bot.font_size}px\n"
            f"✨ Simple & Clean layout..."
        )
        
        # Generate simple PDF
        pdf_buffer = pdf_bot.create_simple_pdf(user_text)
        
        # Determine file extension
        file_ext = "pdf" if REPORTLAB_AVAILABLE else "html"
        filename = f"SAMBATH_LEFT_{update.effective_user.id}.{file_ext}"
        
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=filename,
            caption=f"""✅ Simple PDF បង្កើតរួចរាល់! 🇰🇭

🎯 Simple Features Applied:
• Text Alignment: LEFT (តម្រង់ឆ្វេង)
• មិនមែន justify (ដែលបង្កបញ្ហា)
• Clean paragraph breaks
• Simple layout ងាយមើល

🔧 Technical Details:
• Font: {pdf_bot.font_name} 
• Size: {pdf_bot.font_size}px
• Engine: {'ReportLab' if REPORTLAB_AVAILABLE else 'HTML'}
• Alignment: LEFT ONLY

📄 ឥឡូវអត្ថបទតម្រង់ឆ្វេងធម្មតា!
👨‍💻 Simple by: TENG SAMBATH

💡 Note: LEFT alignment ធ្វើឱ្យអត្ថបទមិន "រញ៉ែរញ៉ៃ"!"""
        )
        
        await processing_msg.delete()
        
    except Exception as e:
        logging.error(f"Simple PDF error: {str(e)}")
        await update.message.reply_text(
            f"❌ មានបញ្ហាកើតឡើង: {str(e)}\n\n"
            f"🔄 សូមព្យាយាមម្ដងទៀត\n"
            f"👨‍💻 Simple Support: TENG SAMBATH"
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
            logging.info("Simple Left Align Bot started successfully")
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
    title="Simple Left Align Khmer PDF Bot by TENG SAMBATH",
    description="Simple PDF generation with LEFT alignment for Khmer text",
    version="SIMPLE LEFT 1.0",
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
        "status": "simple",
        "message": "Simple Left Align PDF Bot running!",
        "version": "SIMPLE LEFT 1.0",
        "developer": "TENG SAMBATH",
        "approach": "LEFT alignment instead of justify",
        "font": pdf_bot.font_name,
        "reportlab": REPORTLAB_AVAILABLE,
        "solution": "Simple left align to avoid រញ៉ែរញ៉ៃ issues"
    }

@app.get("/")
async def root():
    return {
        "message": "🇰🇭 Simple Left Align Khmer PDF Bot",
        "version": "SIMPLE LEFT 1.0",
        "developer": "TENG SAMBATH", 
        "alignment": "LEFT (មិនមែន justify)",
        "solution": "Simple approach to avoid Khmer text issues",
        "font_size": f"{pdf_bot.font_size}px"
    }

if __name__ == "__main__":
    import uvicorn
    
    logging.info("🚀 Starting Simple Left Align PDF Bot...")
    logging.info(f"Font: {pdf_bot.font_name}")
    logging.info(f"Size: {pdf_bot.font_size}px")
    logging.info("📐 Alignment: LEFT (simple approach)")
    logging.info("🇰🇭 Focus: Avoid រញ៉ែរញ៉ៃ issues!")
    
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
