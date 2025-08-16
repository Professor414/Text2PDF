import os
import logging
from io import BytesIO
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from fastapi import FastAPI
import asyncio
import threading

# FPDF import for direct PDF generation
try:
    from fpdf import FPDF
    PDF_AVAILABLE = True
    logging.info("✅ FPDF imported successfully - Direct PDF generation enabled!")
except ImportError as e:
    PDF_AVAILABLE = False
    logging.error(f"❌ FPDF not available: {e}")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
TOKEN = os.getenv('BOT_TOKEN')
PORT = int(os.getenv('PORT', 8000))

if not TOKEN:
    logger.error("BOT_TOKEN environment variable required!")
    exit(1)

class DirectPDFGenerator:
    def __init__(self):
        self.font_size = 19
        self.footer_font_size = 10
        
        # Custom margins in mm (FPDF uses mm by default)
        self.left_margin = 6.35   # 0.25 inches = 6.35 mm
        self.right_margin = 6.35  # 0.25 inches = 6.35 mm  
        self.top_margin = 10.16   # 0.4 inches = 10.16 mm
        self.bottom_margin = 10.16 # 0.4 inches = 10.16 mm
        
        self.line_height = 8  # Line spacing in mm
        
    def clean_text(self, text):
        """Clean text for PDF generation"""
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
            
        return ' '.join(cleaned.split())
    
    def split_into_paragraphs(self, text):
        """Split text into paragraphs"""
        cleaned_text = self.clean_text(text)
        
        if '\n\n' in cleaned_text:
            paragraphs = cleaned_text.split('\n\n')
        else:
            paragraphs = cleaned_text.split('\n')
        
        clean_paragraphs = []
        for para in paragraphs:
            if para.strip() and len(para.strip()) > 2:
                clean_paragraphs.append(para.strip())
        
        return clean_paragraphs if clean_paragraphs else [cleaned_text]
    
    def create_direct_pdf(self, text):
        """Create direct PDF using FPDF - NO HTML conversion"""
        if not PDF_AVAILABLE:
            raise ImportError("FPDF not available - cannot create direct PDF")
        
        # Create PDF instance
        pdf = FPDF()
        pdf.add_page()
        
        # Set custom margins
        pdf.set_margins(self.left_margin, self.top_margin, self.right_margin)
        pdf.set_auto_page_break(auto=True, margin=self.bottom_margin)
        
        # Add font - try to use Unicode font, fallback to built-in
        try:
            pdf.add_font('DejaVu', '', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', uni=True)
            pdf.set_font('DejaVu', size=self.font_size)
            font_name = 'DejaVu'
        except:
            try:
                # Alternative font paths
                pdf.add_font('Ubuntu', '', '/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf', uni=True)
                pdf.set_font('Ubuntu', size=self.font_size)
                font_name = 'Ubuntu'
            except:
                # Fallback to built-in font
                pdf.set_font('Arial', size=self.font_size)
                font_name = 'Arial'
        
        # Get paragraphs
        paragraphs = self.split_into_paragraphs(text)
        
        # Calculate effective width
        effective_width = pdf.w - self.left_margin - self.right_margin
        
        # Add content paragraphs
        for i, paragraph in enumerate(paragraphs):
            if i > 0:
                # Add spacing between paragraphs
                pdf.ln(self.line_height * 0.5)
            
            # Add paragraph indent for non-first paragraphs
            if i == 0:
                # First paragraph - no indent
                pdf.multi_cell(effective_width, self.line_height, paragraph, align='L')
            else:
                # Other paragraphs - with indent
                indent = 10  # 10mm indent
                pdf.set_x(pdf.get_x() + indent)
                pdf.multi_cell(effective_width - indent, self.line_height, paragraph, align='L')
        
        # Add footer
        pdf.ln(15)  # Space before footer
        pdf.set_font('Arial', size=self.footer_font_size)
        footer_text = "ទំព័រ 1 | Created by TENG SAMBATH"
        pdf.multi_cell(effective_width, 5, footer_text, align='L')
        
        # Output to BytesIO
        buffer = BytesIO()
        pdf_output = pdf.output(dest='S').encode('latin-1')
        buffer.write(pdf_output)
        buffer.seek(0)
        
        return buffer

# Initialize PDF generator
pdf_generator = DirectPDFGenerator()

# Create Telegram application
app = Application.builder().token(TOKEN).build()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "✅ Available" if PDF_AVAILABLE else "❌ Not Available"
    
    welcome_message = f"""🇰🇭 ជំរាបសួរ! DIRECT PDF Bot (NO HTML!)

🎯 **DIRECT PDF Generation:**
• FPDF Library: {status}  
• Output: PDF files ពិតប្រាកដ (NOT HTML!)
• No conversion needed - Direct PDF creation

📐 **Custom Margins:**
• Left Margin: 0.25 inches ({pdf_generator.left_margin}mm)
• Right Margin: 0.25 inches ({pdf_generator.right_margin}mm)
• Top Margin: 0.4 inches ({pdf_generator.top_margin}mm)
• Bottom Margin: 0.4 inches ({pdf_generator.bottom_margin}mm)

✨ **Direct PDF Features:**
• Font Size: {pdf_generator.font_size}px
• No Header (removed)
• Footer: "ទំព័រ 1 | Created by TENG SAMBATH"
• Left alignment
• Auto line wrapping
• Paragraph indentation

📝 **Usage:**
1. ផ្ញើអត្ថបទខ្មែរមកខ្ញុំ
2. ទទួលបាន PDF file ដោយផ្ទាល់
3. ទាញយកហើយប្រើបានភ្លាម - NO conversion needed!

🚫 **NO HTML CONVERSION - Pure PDF Generation!**

👨‍💻 **Direct PDF Solution by: TENG SAMBATH**"""
    
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = f"""🆘 **DIRECT PDF Bot Help:**

🎯 **What's Different:**
• Creates ACTUAL PDF files (not HTML)
• Uses FPDF library for direct generation
• NO browser conversion required
• NO HTML involved at all

📐 **PDF Specifications:**
• Left: 0.25" | Right: 0.25" (as requested)
• Top: 0.4" | Bottom: 0.4"  
• Font: {pdf_generator.font_size}px
• Format: A4 paper size

✅ **Direct PDF Benefits:**
• Instant PDF files
• No conversion steps
• Professional layout
• Custom margins applied directly
• Ready to use immediately

📝 **How it Works:**
1️⃣ You send text
2️⃣ FPDF generates PDF directly  
3️⃣ You get actual PDF file
4️⃣ No HTML, no conversion - just PDF!

👨‍💻 **TENG SAMBATH - Pure PDF Solution**"""
    
    await update.message.reply_text(help_text)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    if user_text.startswith('/'):
        return
        
    # Check PDF library availability
    if not PDF_AVAILABLE:
        await update.message.reply_text("❌ FPDF library not available. Cannot create direct PDF.")
        return
        
    # Validate input
    if len(user_text.strip()) < 3:
        await update.message.reply_text("⚠️ សូមផ្ញើអត្ថបទយ៉ាងហោចណាស់ 3 តួអក្សរ")
        return
    
    try:
        # Send processing message
        processing_msg = await update.message.reply_text(
            f"""⏳ **បង្កើត DIRECT PDF...**

🎯 Engine: FPDF (NO HTML conversion)
📐 Left: 0.25" | Right: 0.25"
📝 Font: {pdf_generator.font_size}px
📄 Output: PDF file ដោយផ្ទាល់
✨ Processing your text..."""
        )
        
        # Create direct PDF
        pdf_buffer = pdf_generator.create_direct_pdf(user_text)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"SAMBATH_DIRECT_{timestamp}.pdf"
        
        # Send PDF document
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=filename,
            caption=f"""✅ **DIRECT PDF ជោគជ័យ!** 🇰🇭

🎊 **NO HTML CONVERSION - Pure PDF!**

📋 **Direct PDF Features:**
• File Type: PDF (NOT HTML!) ✅
• Left Margin: 0.25 inches ✅
• Right Margin: 0.25 inches ✅  
• Font Size: {pdf_generator.font_size}px ✅
• Footer: "ទំព័រ 1 | Created by TENG SAMBATH" ✅

🎯 **Generated Using:**
• FPDF Library - Direct PDF creation
• No browser needed
• No conversion steps
• Instant PDF file

📊 **Technical:**
• Created: {datetime.now().strftime('%d/%m/%Y %H:%M')}
• Method: Direct PDF generation
• Size: A4 with custom margins
• Ready to use immediately!

🚫 **NO HTML - Just Pure PDF!**
👨‍💻 **Direct Solution by: TENG SAMBATH**"""
        )
        
        # Delete processing message
        await processing_msg.delete()
        
        # Log success
        logger.info(f"Direct PDF created for user {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"Error creating direct PDF: {str(e)}")
        await update.message.reply_text(f"❌ មានបញ្ហាកើតឡើង: {str(e)}")

# Add handlers
app.add_handler(CommandHandler("start", start_command))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

# FastAPI for health check
fastapi_app = FastAPI(title="Direct PDF Bot - NO HTML Conversion")

@fastapi_app.get("/")
async def root():
    return {
        "status": "direct_pdf_generation",
        "message": "Direct PDF creation - NO HTML conversion!",
        "library": "FPDF",
        "output": "Pure PDF files",
        "html_conversion": False,
        "margins": {
            "left": "0.25 inches",
            "right": "0.25 inches", 
            "top": "0.4 inches",
            "bottom": "0.4 inches"
        },
        "developer": "TENG SAMBATH"
    }

@fastapi_app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "pdf_generation": "direct",
        "html_involved": False,
        "fpdf_available": PDF_AVAILABLE,
        "conversion_required": False
    }

# Function to run bot
async def run_bot():
    """Run the bot with polling"""
    try:
        logger.info("🚀 Starting DIRECT PDF Bot by TENG SAMBATH...")
        logger.info("📄 Output: Pure PDF files (NO HTML conversion)")
        logger.info(f"✅ FPDF: {'Available' if PDF_AVAILABLE else 'Not Available'}")
        logger.info(f"📐 Margins: Left=0.25\", Right=0.25\"")
        logger.info(f"📝 Font: {pdf_generator.font_size}px")
        logger.info("🎯 Direct PDF generation - NO HTML involved!")
        
        # Use polling
        async with app:
            await app.initialize()
            await app.start()
            await app.updater.start_polling()
            
            # Keep running
            while True:
                await asyncio.sleep(1)
                
    except Exception as e:
        logger.error(f"Bot error: {e}")

def start_bot_thread():
    """Start bot in separate thread"""
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
