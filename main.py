import os
import logging
from io import BytesIO
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from datetime import datetime
import textwrap

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Environment variables
TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', 8000))

# Register Khmer fonts with multiple options
try:
    font_paths = [
        'font/Battambang-Regular.ttf',
        'font/Battambang-Bold.ttf',
        'font/KhmerOS.ttf',
        'font/Noto-Sans-Khmer-Regular.ttf'
    ]
    
    KHMER_FONT = 'Helvetica'  # Fallback
    HEADER_FONT = 'Helvetica-Bold'  # For header
    
    for i, font_path in enumerate(font_paths):
        try:
            if os.path.exists(font_path):
                font_name = f'Khmer{i}'
                pdfmetrics.registerFont(TTFont(font_name, font_path))
                KHMER_FONT = font_name
                logging.info(f"Loaded Khmer font: {font_path}")
                break
        except Exception as e:
            logging.warning(f"Failed to load font {font_path}: {e}")
            continue
            
    # Try to register bold font for header
    try:
        if os.path.exists('font/Battambang-Bold.ttf'):
            pdfmetrics.registerFont(TTFont('KhmerBold', 'font/Battambang-Bold.ttf'))
            HEADER_FONT = 'KhmerBold'
    except:
        pass
        
except Exception as e:
    logging.error(f"Font loading error: {e}")
    KHMER_FONT = 'Helvetica'
    HEADER_FONT = 'Helvetica-Bold'

# Create bot application
ptb = (
    Application.builder()
    .updater(None)  # ប្រើ webhook, មិនមែន polling
    .token(TOKEN)
    .read_timeout(7)
    .get_updates_read_timeout(42)
    .build()
)

class ImprovedKhmerPDFBot:
    def __init__(self):
        self.khmer_font = KHMER_FONT
        self.header_font = HEADER_FONT
        self.font_size = 19  # កំណត់ទំហំអក្សរ 19
        self.header_font_size = 14
        self.footer_font_size = 10
        
    def contains_khmer(self, text: str) -> bool:
        """ពិនិត្យថាអត្ថបទមានអក្សរខ្មែរឬអត់"""
        khmer_range = range(0x1780, 0x17FF)
        return any(ord(char) in khmer_range for char in text)
    
    def preprocess_khmer_text(self, text: str) -> str:
        """កែលម្អអត្ថបទខ្មែរសម្រាប់ការបង្ហាញត្រឹមត្រូវ"""
        processed_lines = []
        
        for line in text.split('\n'):
            if len(line) > 50:  # បន្ទាត់វែង
                # បំបែកពាក្យវែងៗសម្រាប់អក្សរខ្មែរ
                words = line.split(' ')
                new_words = []
                
                for word in words:
                    if len(word) > 20 and self.contains_khmer(word):
                        # បន្ថែម zero-width space រៀងរាល់ 20 តួអក្សរ
                        chunks = [word[i:i+20] for i in range(0, len(word), 20)]
                        new_words.append('\u200B'.join(chunks))
                    else:
                        new_words.append(word)
                
                processed_lines.append(' '.join(new_words))
            else:
                processed_lines.append(line)
        
        return '\n'.join(processed_lines)
    
    def draw_header(self, canvas_obj, width):
        """គូរ header នៅកំពូលទំព័រ"""
        header_text = "TEXT 2PDF BY : TENG SAMBATH"
        canvas_obj.setFont(self.header_font, self.header_font_size)
        
        # គណនាទីតាំងកណ្តាល
        text_width = canvas_obj.stringWidth(header_text, self.header_font, self.header_font_size)
        x_center = (width - text_width) / 2
        
        # គូរ header
        canvas_obj.drawString(x_center, A4[1] - 30, header_text)
        
        # គូរបន្ទាត់ពីក្រោម header
        canvas_obj.line(50, A4[1] - 45, width - 50, A4[1] - 45)
    
    def draw_footer(self, canvas_obj, width, page_number):
        """គូរ footer នៅបាតទំព័រ"""
        canvas_obj.setFont('Helvetica', self.footer_font_size)
        
        # ថ្ងៃបច្ចុប្បន្ន
        current_date = datetime.now().strftime("%d/%m/%Y %H:%M")
        left_text = f"Generated: {current_date}"
        
        # លេខទំព័រ
        page_text = f"ទំព័រ {page_number}"
        page_width = canvas_obj.stringWidth(page_text, 'Helvetica', self.footer_font_size)
        
        # គូរបន្ទាត់នៅលើ footer
        canvas_obj.line(50, 40, width - 50, 40)
        
        # គូរអត្ថបទ footer
        canvas_obj.drawString(50, 25, left_text)
        canvas_obj.drawString(width - 50 - page_width, 25, page_text)
    
    def create_pdf_from_text(self, text: str) -> BytesIO:
        """បង្កើត PDF ជាមួយការកែលម្អពេញលេញ"""
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        
        width, height = A4
        margin = 60  # បន្ថែម margin សម្រាប់ header/footer
        max_width = width - 2 * margin
        line_height = self.font_size + 8  # ចម្ងាយបន្ទាត់
        
        # កំណត់តំបន់សម្រាប់អត្ថបទ (ទុកកន្លែងសម្រាប់ header/footer)
        text_start_y = height - 70  # ចាប់ផ្តើមបន្ទាប់ពី header
        text_end_y = 60  # បញ្ចប់មុន footer
        
        # កែលម្អអត្ថបទ
        processed_text = self.preprocess_khmer_text(text)
        lines = processed_text.split('\n')
        
        y_position = text_start_y
        page_number = 1
        
        # គូរទំព័រទីមួយ
        self.draw_header(p, width)
        self.draw_footer(p, width, page_number)
        
        p.setFont(self.khmer_font, self.font_size)
        
        for line in lines:
            # ពិនិត្យថាត្រូវការទំព័រថ្មីឬអត់
            if y_position < text_end_y + line_height:
                p.showPage()
                page_number += 1
                
                # គូរ header/footer ទំព័រថ្មី
                self.draw_header(p, width)
                self.draw_footer(p, width, page_number)
                
                p.setFont(self.khmer_font, self.font_size)
                y_position = text_start_y
            
            # ដោះស្រាយបន្ទាត់វែង
            if p.stringWidth(line, self.khmer_font, self.font_size) > max_width:
                # បំបែកបន្ទាត់វែងៗ
                words = line.split(' ')
                current_line = ''
                
                for word in words:
                    test_line = f"{current_line} {word}".strip()
                    
                    if p.stringWidth(test_line, self.khmer_font, self.font_size) <= max_width:
                        current_line = test_line
                    else:
                        # បោះពុម្ពបន្ទាត់បច្ចុប្បន្ន
                        if current_line:
                            p.drawString(margin, y_position, current_line)
                            y_position -= line_height
                            
                            # ពិនិត្យទំព័រថ្មី
                            if y_position < text_end_y + line_height:
                                p.showPage()
                                page_number += 1
                                self.draw_header(p, width)
                                self.draw_footer(p, width, page_number)
                                p.setFont(self.khmer_font, self.font_size)
                                y_position = text_start_y
                        
                        current_line = word
                
                # បោះពុម្ពអត្ថបទនៅសល់
                if current_line:
                    p.drawString(margin, y_position, current_line)
                    y_position -= line_height
            else:
                # បន្ទាត់ធម្មតា
                p.drawString(margin, y_position, line)
                y_position -= line_height
        
        p.save()
        buffer.seek(0)
        return buffer

# ប្រើ bot ដែលបានកែលម្អ
pdf_bot = ImprovedKhmerPDFBot()

# Bot handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = f"""🇰🇭 ជំរាបសួរ! ខ្ញុំជា Text to PDF Bot (កែលម្អថ្មី)

📝 លក្ខណៈពិសេសថ្មី:
• អក្សរខ្មែរទំហំ {pdf_bot.font_size} ហើយមិនដាច់ដៃដាច់ជើង
• Header: TEXT 2PDF BY : TENG SAMBATH
• Footer: លេខទំព័រ + ថ្ងៃខែឆ្នាំ
• Word wrapping ល្អប្រសើរ
• គាំទ្រអត្ថបទវែងច្រើនទំព័រ

🔧 ពាក្យបញ្ជា:
/help - ជំនួយលម្អិត
/start - ចាប់ផ្ដើមម្ដងទៀត

✨ ឥឡូវអ្នកអាចផ្ញើអត្ថបទវែងបានហើយ!"""
    
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = f"""🆘 ជំនួយការប្រើប្រាស់Bot កែលម្អថ្មី:

✨ ការកែលម្អសំខាន់ៗ:
• អក្សរខ្មែរទំហំ {pdf_bot.font_size} ហើយមិនដាច់ដៃដាច់ជើងទៀត
• Header: "TEXT 2PDF BY : TENG SAMBATH"
• Footer: លេខទំព័រ + ថ្ងៃខែឆ្នាំបង្កើត
• Text wrapping អាចដោះស្រាយបន្ទាត់វែង

📝 របៀបប្រើ:
1️⃣ ផ្ញើអត្ថបទខ្មែរ ឬ អង់គ្លេសមកខ្ញុំ
2️⃣ រង់ចាំខ្ញុំបម្លែងទៅជា PDF (មានការកែលម្អ)
3️⃣ ទាញយកឯកសារ PDF ជាមួយ header/footer ស្អាត

💡 ជូនដំណឹង: 
• អាចផ្ញើអត្ថបទវែងបាន (ច្រើនទំព័រ)
• អក្សរខ្មែរនឹងបង្ហាញត្រឹមត្រូវ
• PDF មានរូបរាងវិជ្ជាជីវៈ

👨‍💻 បង្កើតដោយ: TENG SAMBATH"""
    
    await update.message.reply_text(help_text)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    if user_text.startswith('/'):
        return
    
    # ពិនិត្យប្រវែងអត្ថបទ
    if len(user_text.strip()) < 3:
        await update.message.reply_text("⚠️ សូមផ្ញើអត្ថបទដែលមានយ៉ាងហោចណាស់ 3 តួអក្សរ")
        return
    
    try:
        # ផ្ញើសារកំពុងដំណើរការ
        processing_msg = await update.message.reply_text(
            f"⏳ កំពុងបម្លែងអត្ថបទទៅជា PDF...\n"
            f"📄 ទំហំអក្សរ: {pdf_bot.font_size}\n"
            f"👤 Header: TEXT 2PDF BY : TENG SAMBATH\n"
            f"📋 Footer: លេខទំព័រ + ថ្ងៃខែឆ្នាំ"
        )
        
        # បង្កើត PDF ជាមួយការកែលម្អ
        pdf_buffer = pdf_bot.create_pdf_from_text(user_text)
        
        # ផ្ញើឯកសារ PDF
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=f"SAMBATH_PDF_{update.effective_user.id}_{update.message.message_id}.pdf",
            caption=f"""✅ បម្លែងជោគជ័យជាមួយការកែលម្អពេញលេញ! 🇰🇭

📊 លក្ខណៈពិសេស:
• អក្សរខ្មែរទំហំ {pdf_bot.font_size} (មិនដាច់ដៃដាច់ជើង)
• Header: TEXT 2PDF BY : TENG SAMBATH  
• Footer: លេខទំព័រ + ថ្ងៃខែឆ្នាំ
• Word wrapping ល្អប្រសើរ

📄 អ្នកអាចទាញយកឯកសារនេះបាន
👨‍💻 បង្កើតដោយ: TENG SAMBATH"""
        )
        
        # លុបសារកំពុងដំណើរការ
        await processing_msg.delete()
        
    except Exception as e:
        logging.error(f"Error processing text: {str(e)}")
        await update.message.reply_text(
            f"❌ មានបញ្ហាកើតឡើង: {str(e)}\n\n"
            f"🔄 សូមព្យាយាមម្ដងទៀត ឬ ទាក់ទងអ្នកគ្រប់គ្រង\n"
            f"👨‍💻 Developer: TENG SAMBATH"
        )

# បន្ថែម handlers
ptb.add_handler(CommandHandler("start", start_command))
ptb.add_handler(CommandHandler("help", help_command))
ptb.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

# FastAPI app lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    """គ្រប់គ្រង application lifecycle"""
    try:
        # កំណត់ webhook
        webhook_url = f"{WEBHOOK_URL}/webhook"
        await ptb.bot.set_webhook(webhook_url)
        logging.info(f"Webhook set to: {webhook_url}")
        
        # ចាប់ផ្តើម application
        async with ptb:
            await ptb.start()
            logging.info("Improved Khmer Bot started successfully")
            yield
            
    except Exception as e:
        logging.error(f"Error in lifespan: {str(e)}")
        yield
    finally:
        # បញ្ចប់ application
        try:
            await ptb.stop()
            logging.info("Bot stopped")
        except Exception as e:
            logging.error(f"Error stopping bot: {str(e)}")

# បង្កើត FastAPI app
app = FastAPI(
    title="Text to PDF Khmer Bot by TENG SAMBATH",
    description="Telegram Bot for converting Khmer text to PDF with improved features",
    version="2.0.0",
    lifespan=lifespan
)

@app.post("/webhook")
async def process_update(request: Request):
    """ដោះស្រាយ updates ពី Telegram"""
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
    """Health check endpoint"""
    return {
        "status": "healthy",
        "message": "Improved Text to PDF Bot is running! 🤖",
        "version": "2.0.0",
        "developer": "TENG SAMBATH",
        "features": [
            f"Khmer font size {pdf_bot.font_size}",
            "Fixed broken Khmer characters", 
            "Header: TEXT 2PDF BY : TENG SAMBATH",
            "Footer with page numbers",
            "Improved text wrapping",
            "Multi-page support"
        ]
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "🇰🇭 Improved Text to PDF Khmer Bot API",
        "status": "running",
        "version": "2.0.0",
        "developer": "TENG SAMBATH",
        "improvements": {
            "font_size": pdf_bot.font_size,
            "header": "TEXT 2PDF BY : TENG SAMBATH",
            "footer": "Page numbers + date",
            "khmer_support": "Fixed broken characters"
        },
        "endpoints": {
            "webhook": "/webhook",
            "health": "/health", 
            "info": "/info"
        }
    }

@app.get("/info")
async def bot_info():
    """ព័ត៌មាន bot"""
    try:
        bot = ptb.bot
        bot_info = await bot.get_me()
        return {
            "bot_name": bot_info.first_name,
            "bot_username": f"@{bot_info.username}",
            "bot_id": bot_info.id,
            "webhook_url": f"{WEBHOOK_URL}/webhook",
            "developer": "TENG SAMBATH",
            "font_size": pdf_bot.font_size,
            "features": "Header, Footer, Fixed Khmer rendering"
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    
    # Log ព័ត៌មានចាប់ផ្តើម
    logging.info("Starting Improved Text to PDF Khmer Bot by TENG SAMBATH...")
    logging.info(f"PORT: {PORT}")
    logging.info(f"WEBHOOK_URL: {WEBHOOK_URL}")
    logging.info(f"Khmer Font: {KHMER_FONT}")
    logging.info(f"Font Size: {pdf_bot.font_size}")
    
    # ដំណើរការ application
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=PORT,
        log_level="info"
    )
