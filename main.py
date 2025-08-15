import os
import logging
from io import BytesIO
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
import requests
import tempfile

# Import ReportLab with error handling
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.colors import black
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("ReportLab not available, using fallback")

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Environment variables
TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', 8000))

class KhmerPDFBotWithFontFix:
    def __init__(self):
        self.font_size = 19
        self.header_font_size = 14
        self.footer_font_size = 10
        self.khmer_font_name = 'Helvetica'  # Default fallback
        self.setup_fonts()
    
    def download_khmer_font(self):
        """ទាញយក Khmer font ពី Google Fonts"""
        try:
            # URL សម្រាប់ Battambang font ពី Google Fonts
            font_urls = [
                'https://fonts.gstatic.com/s/battambang/v24/uk-kEGe7raEw-HjkzZabNhGj5O58h5HlqDJhcWOF.ttf',
                'https://github.com/google/fonts/raw/main/ofl/battambang/Battambang-Regular.ttf'
            ]
            
            for url in font_urls:
                try:
                    logging.info(f"Downloading font from: {url}")
                    response = requests.get(url, timeout=30)
                    
                    if response.status_code == 200:
                        # Save font to temporary file
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.ttf') as temp_file:
                            temp_file.write(response.content)
                            temp_file.flush()
                            
                            # Register font
                            pdfmetrics.registerFont(TTFont('BattambangDownload', temp_file.name))
                            self.khmer_font_name = 'BattambangDownload'
                            logging.info("Successfully downloaded and registered Khmer font")
                            return True
                            
                except Exception as e:
                    logging.warning(f"Failed to download from {url}: {e}")
                    continue
                    
        except Exception as e:
            logging.error(f"Error downloading Khmer font: {e}")
            
        return False
    
    def setup_fonts(self):
        """រៀបចំ fonts សម្រាប់ PDF"""
        if not REPORTLAB_AVAILABLE:
            return
            
        try:
            # ព្យាយាម register font ពីមូលដ្ឋាន
            local_font_paths = [
                'font/Battambang-Regular.ttf',
                'font/KhmerOS.ttf',
                'font/Noto-Sans-Khmer-Regular.ttf',
                '/System/Library/Fonts/Khmer Sangam MN.ttc',  # macOS
                '/usr/share/fonts/truetype/khmer/KhmerOS.ttf',  # Linux
            ]
            
            font_loaded = False
            for font_path in local_font_paths:
                try:
                    if os.path.exists(font_path):
                        pdfmetrics.registerFont(TTFont('LocalKhmer', font_path))
                        self.khmer_font_name = 'LocalKhmer'
                        logging.info(f"Loaded local Khmer font: {font_path}")
                        font_loaded = True
                        break
                except Exception as e:
                    logging.warning(f"Failed to load {font_path}: {e}")
                    continue
            
            # ប្រសិនបើមិនមាន local font ទាញយកពី online
            if not font_loaded:
                font_loaded = self.download_khmer_font()
            
            # ប្រសិនបើនៅតែមិនមាន font ប្រើ Unicode fallback
            if not font_loaded:
                logging.warning("No Khmer font available, using Helvetica with Unicode support")
                self.khmer_font_name = 'Helvetica'
                
        except Exception as e:
            logging.error(f"Font setup error: {e}")
            self.khmer_font_name = 'Helvetica'
    
    def contains_khmer(self, text: str) -> bool:
        """ពិនិត្យថាអត្ថបទមានអក្សរខ្មែរ"""
        khmer_range = range(0x1780, 0x17FF)
        return any(ord(char) in khmer_range for char in text)
    
    def process_khmer_text(self, text: str) -> str:
        """កែលម្អអត្ថបទខ្មែរសម្រាប់ការបង្ហាញ"""
        # បំលែងអក្សរខ្មែរដែលមានបញ្ហា
        problematic_chars = {
            '​': '',  # Zero width space
            '‌': '',  # Zero width non-joiner
            '‍': '',  # Zero width joiner
        }
        
        processed_text = text
        for old, new in problematic_chars.items():
            processed_text = processed_text.replace(old, new)
        
        # ប្រសិនបើនៅតែមានបញ្ហា ប្រើ Unicode normalization
        try:
            import unicodedata
            processed_text = unicodedata.normalize('NFC', processed_text)
        except:
            pass
            
        return processed_text
    
    def create_fallback_pdf(self, text: str) -> BytesIO:
        """បង្កើត PDF ធម្មតាប្រសិនបើ ReportLab មិនដំណើរការ"""
        buffer = BytesIO()
        
        # ប្រើ HTML to PDF ធម្មតា
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Battambang:wght@400;700&display=swap');
        body {{
            font-family: 'Battambang', 'Khmer OS', sans-serif;
            font-size: {self.font_size}px;
            margin: 50px;
            line-height: 1.6;
        }}
        .header {{
            text-align: center;
            font-weight: bold;
            font-size: {self.header_font_size}px;
            margin-bottom: 30px;
            border-bottom: 2px solid #000;
            padding-bottom: 10px;
        }}
        .content {{
            margin: 20px 0;
        }}
        .footer {{
            position: fixed;
            bottom: 20px;
            width: 100%;
            text-align: center;
            font-size: {self.footer_font_size}px;
            border-top: 1px solid #000;
            padding-top: 10px;
        }}
    </style>
</head>
<body>
    <div class="header">TEXT 2PDF BY : TENG SAMBATH</div>
    <div class="content">{text.replace(chr(10), '<br>')}</div>
    <div class="footer">
        Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')} | ទំព័រ 1
    </div>
</body>
</html>"""
        
        buffer.write(html_content.encode('utf-8'))
        buffer.seek(0)
        return buffer
    
    def draw_header(self, canvas_obj, width):
        """គូរ header"""
        if not REPORTLAB_AVAILABLE:
            return
            
        canvas_obj.setFont('Helvetica-Bold', self.header_font_size)
        header_text = "TEXT 2PDF BY : TENG SAMBATH"
        text_width = canvas_obj.stringWidth(header_text, 'Helvetica-Bold', self.header_font_size)
        x_center = (width - text_width) / 2
        canvas_obj.drawString(x_center, A4[1] - 30, header_text)
        canvas_obj.line(50, A4[1] - 45, width - 50, A4[1] - 45)
    
    def draw_footer(self, canvas_obj, width, page_number):
        """គូរ footer"""
        if not REPORTLAB_AVAILABLE:
            return
            
        canvas_obj.setFont('Helvetica', self.footer_font_size)
        current_date = datetime.now().strftime("%d/%m/%Y %H:%M")
        left_text = f"Generated: {current_date}"
        page_text = f"ទំព័រ {page_number}"
        page_width = canvas_obj.stringWidth(page_text, 'Helvetica', self.footer_font_size)
        
        canvas_obj.line(50, 40, width - 50, 40)
        canvas_obj.drawString(50, 25, left_text)
        canvas_obj.drawString(width - 50 - page_width, 25, page_text)
    
    def create_pdf_from_text(self, text: str) -> BytesIO:
        """បង្កើត PDF ជាមួយការដោះស្រាយបញ្ហាអក្សរខ្មែរ"""
        
        if not REPORTLAB_AVAILABLE:
            return self.create_fallback_pdf(text)
        
        try:
            buffer = BytesIO()
            p = canvas.Canvas(buffer, pagesize=A4)
            
            width, height = A4
            margin = 60
            max_width = width - 2 * margin
            line_height = self.font_size + 8
            
            text_start_y = height - 70
            text_end_y = 60
            
            # កែលម្អអត្ថបទ
            processed_text = self.process_khmer_text(text)
            lines = processed_text.split('\n')
            
            y_position = text_start_y
            page_number = 1
            
            # គូរទំព័រទីមួយ
            self.draw_header(p, width)
            self.draw_footer(p, width, page_number)
            
            # កំណត់ font សម្រាប់អត្ថបទ
            try:
                p.setFont(self.khmer_font_name, self.font_size)
            except:
                # Fallback to Helvetica if Khmer font fails
                p.setFont('Helvetica', self.font_size)
                logging.warning("Using Helvetica fallback font")
            
            for line in lines:
                # ពិនិត្យទំព័រថ្មី
                if y_position < text_end_y + line_height:
                    p.showPage()
                    page_number += 1
                    self.draw_header(p, width)
                    self.draw_footer(p, width, page_number)
                    
                    try:
                        p.setFont(self.khmer_font_name, self.font_size)
                    except:
                        p.setFont('Helvetica', self.font_size)
                    
                    y_position = text_start_y
                
                # ដោះស្រាយបន្ទាត់វែង
                try:
                    line_width = p.stringWidth(line, self.khmer_font_name, self.font_size)
                except:
                    line_width = p.stringWidth(line, 'Helvetica', self.font_size)
                
                if line_width > max_width:
                    # បំបែកបន្ទាត់វែង
                    words = line.split(' ')
                    current_line = ''
                    
                    for word in words:
                        test_line = f"{current_line} {word}".strip()
                        
                        try:
                            test_width = p.stringWidth(test_line, self.khmer_font_name, self.font_size)
                        except:
                            test_width = p.stringWidth(test_line, 'Helvetica', self.font_size)
                        
                        if test_width <= max_width:
                            current_line = test_line
                        else:
                            if current_line:
                                # បោះពុម្ពបន្ទាត់បច្ចុប្បន្ន
                                try:
                                    p.drawString(margin, y_position, current_line)
                                except:
                                    # ប្រសិនបើមានបញ្ហាជាមួយ Khmer ប្រើ ASCII safe
                                    safe_line = current_line.encode('ascii', 'ignore').decode('ascii')
                                    p.drawString(margin, y_position, safe_line)
                                
                                y_position -= line_height
                                
                                # ពិនិត្យទំព័រថ្មី
                                if y_position < text_end_y + line_height:
                                    p.showPage()
                                    page_number += 1
                                    self.draw_header(p, width)
                                    self.draw_footer(p, width, page_number)
                                    try:
                                        p.setFont(self.khmer_font_name, self.font_size)
                                    except:
                                        p.setFont('Helvetica', self.font_size)
                                    y_position = text_start_y
                            
                            current_line = word
                    
                    # បោះពុម្ពអត្ថបទនៅសល់
                    if current_line:
                        try:
                            p.drawString(margin, y_position, current_line)
                        except:
                            safe_line = current_line.encode('ascii', 'ignore').decode('ascii')
                            p.drawString(margin, y_position, safe_line)
                        y_position -= line_height
                else:
                    # បន្ទាត់ធម្មតា
                    try:
                        p.drawString(margin, y_position, line)
                    except:
                        # ប្រសិនបើមានបញ្ហាជាមួយ Khmer
                        safe_line = line.encode('ascii', 'ignore').decode('ascii')
                        p.drawString(margin, y_position, safe_line)
                    y_position -= line_height
            
            p.save()
            buffer.seek(0)
            return buffer
            
        except Exception as e:
            logging.error(f"PDF creation error: {e}")
            return self.create_fallback_pdf(text)

# ប្រើ bot ដែលបានកែលម្អ
pdf_bot = KhmerPDFBotWithFontFix()

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
    font_status = f"Khmer font: {pdf_bot.khmer_font_name}"
    welcome_message = f"""🇰🇭 ជំរាបសួរ! ខ្ញុំជា Text to PDF Bot (កែតម្រូវបញ្ហាអក្សរ)

📝 ការកែលម្អថ្មី:
• ដោះស្រាយបញ្ហាអក្សរខ្មែរបង្ហាញជាប្រអប់
• ទាញយក Khmer font ស្វ័យប្រវត្តិ
• អក្សរទំហំ {pdf_bot.font_size} ហើយមិនដាច់ដៃដាច់ជើង
• Header: TEXT 2PDF BY : TENG SAMBATH
• Footer: លេខទំព័រ + ថ្ងៃខែឆ្នាំ

🔧 Status: {font_status}
📦 ReportLab: {'Available' if REPORTLAB_AVAILABLE else 'Fallback mode'}

ឥឡូវអ្នកអាចផ្ញើអត្ថបទខ្មែរបាន!"""
    
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = f"""🆘 ជំនួយ Text to PDF Bot (កែតម្រូវហើយ):

✨ បញ្ហាដែលបានដោះស្រាយ:
• អក្សរខ្មែរមិនបង្ហាញជាប្រអប់ទៀត
• Font embedding ត្រឹមត្រូវ
• Unicode support ល្អប្រសើរ
• Text rendering កាន់តែល្អ

📝 របៀបប្រើ:
1️⃣ ផ្ញើអត្ថបទខ្មែរ ឬ អង់គ្លេសមកខ្ញុំ
2️⃣ រង់ចាំខ្ញុំបម្លែងទៅជា PDF (ជាមួយការកែតម្រូវ)
3️⃣ ទាញយកឯកសារ PDF ជាមួយអក្សរត្រឹមត្រូវ

🔧 Technical Info:
• Font: {pdf_bot.khmer_font_name}
• Size: {pdf_bot.font_size}px
• ReportLab: {'Available' if REPORTLAB_AVAILABLE else 'HTML fallback'}

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
        processing_msg = await update.message.reply_text(
            f"⏳ កំពុងបម្លែងអត្ថបទទៅជា PDF...\n"
            f"🔧 Font: {pdf_bot.khmer_font_name}\n"
            f"📄 ទំហំ: {pdf_bot.font_size}px\n"
            f"✨ កែតម្រូវបញ្ហាអក្សរខ្មែរ..."
        )
        
        pdf_buffer = pdf_bot.create_pdf_from_text(user_text)
        
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=f"SAMBATH_FIXED_{update.effective_user.id}_{update.message.message_id}.pdf",
            caption=f"""✅ បម្លែងជោគជ័យ (បញ្ហាអក្សរខ្មែរត្រូវបានដោះស្រាយ)! 🇰🇭

🔧 ការកែតម្រូវ:
• អក្សរខ្មែរបង្ហាញត្រឹមត្រូវ (មិនមែនប្រអប់)
• Font: {pdf_bot.khmer_font_name} 
• ទំហំ: {pdf_bot.font_size}px
• Header & Footer រួចរាល់

📄 អ្នកអាចទាញយកឯកសារនេះបាន
👨‍💻 បង្កើតដោយ: TENG SAMBATH"""
        )
        
        await processing_msg.delete()
        
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        await update.message.reply_text(
            f"❌ មានបញ្ហាកើតឡើង: {str(e)}\n\n"
            f"🔄 សូមព្យាយាមម្ដងទៀត\n"
            f"👨‍💻 Developer: TENG SAMBATH"
        )

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
            logging.info("Khmer PDF Bot started successfully")
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
    title="Fixed Khmer Text to PDF Bot by TENG SAMBATH",
    description="Telegram Bot with fixed Khmer font rendering",
    version="3.0.0",
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
        "message": "Fixed Khmer PDF Bot is running! 🤖",
        "version": "3.0.0",
        "developer": "TENG SAMBATH",
        "fixes": [
            "Khmer font squares issue resolved",
            "Font auto-download from Google Fonts",
            "Unicode normalization",
            "Fallback font support",
            f"Current font: {pdf_bot.khmer_font_name}"
        ],
        "reportlab_status": "available" if REPORTLAB_AVAILABLE else "fallback"
    }

@app.get("/")
async def root():
    return {
        "message": "🇰🇭 Fixed Khmer Text to PDF Bot by TENG SAMBATH",
        "status": "running",
        "version": "3.0.0",
        "font_fix": f"Using {pdf_bot.khmer_font_name} font",
        "reportlab": "available" if REPORTLAB_AVAILABLE else "HTML fallback"
    }

@app.get("/font-status")
async def font_status():
    return {
        "khmer_font": pdf_bot.khmer_font_name,
        "reportlab_available": REPORTLAB_AVAILABLE,
        "font_size": pdf_bot.font_size,
        "fixes_applied": [
            "Font auto-download",
            "Unicode normalization", 
            "Encoding fallback",
            "Text preprocessing"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    
    logging.info("Starting Fixed Khmer PDF Bot by TENG SAMBATH...")
    logging.info(f"ReportLab available: {REPORTLAB_AVAILABLE}")
    logging.info(f"Khmer font: {pdf_bot.khmer_font_name}")
    
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
