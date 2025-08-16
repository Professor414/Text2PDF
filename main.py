import os
import logging
from io import BytesIO
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

try:
    from fpdf import FPDF
except ImportError as e:
    raise RuntimeError("You must add 'fpdf2' to requirements.txt!")

logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Please set BOT_TOKEN as env var.")

# ==== Direct PDF Handler ====
class KhmerPDF(FPDF):
    def __init__(self, margin_left=6.35, margin_right=6.35, margin_top=10.16, margin_bottom=10.16):
        super().__init__('P', 'mm', 'A4')
        self.set_auto_page_break(auto=True, margin=margin_bottom)
        self.set_margin(margin_left)
        self.set_left_margin(margin_left)
        self.set_right_margin(margin_right)
        self.set_top_margin(margin_top)
        self.font_size_main = 19
        self.font_size_footer = 10
  
    def header(self):
        # No header
        pass

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "", self.font_size_footer)
        self.cell(0, 10, "ទំព័រ 1 | Created by TENG SAMBATH", 0, 0, "L")

def build_pdf(text):
    margin_left = 6.35   # 0.25in in mm
    margin_right = 6.35
    margin_top = 10.16   # 0.4in in mm
    margin_bottom = 10.16

    # New KhmerPDF object
    pdf = KhmerPDF(margin_left, margin_right, margin_top, margin_bottom)
    pdf.add_page()
    pdf.add_font('DejaVu', '', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', uni=True)
    pdf.set_font("DejaVu", size=19)
    # Clean and split
    lines = [line.strip() for line in text.replace('\r\n', '\n').split('\n') if line.strip()]
    for idx, line in enumerate(lines):
        if idx > 0:
            pdf.ln(3)
        pdf.multi_cell(0, 10, line, align='L')
    # Output to buffer
    buffer = BytesIO()
    pdf.output(buffer)
    buffer.seek(0)
    return buffer

# ==== BOT SECTION ====
app = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🇰🇭 PDF Bot (NO HTML, NO ReportLab)\n\n"
        "• Output: PDF file only, no HTML, no browser convert\n"
        "• Margins LEFT & RIGHT: 0.25 in\n"
        "• Font: DejaVu 19px; Khmer supported (if on server)\n"
        "• Header: (none)\n"
        "• Footer: 'ទំព័រ 1 | Created by TENG SAMBATH'\n\n"
        "មានបញ្ហាអាចសួរបាន!"
    )

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    if user_text.startswith("/"):
        return
    if len(user_text) < 3:
        await update.message.reply_text("សូមផ្ញើអត្ថបទយ៉ាងហោចណាស់ 3 ទៅទីនេះ")
        return
    await update.message.reply_text("⏳ កំពុងបង្កើត PDF...")
    try:
        pdf_buffer = build_pdf(user_text)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"SAMBATH_DIRECT_{timestamp}.pdf"
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=filename,
            caption="✅ PDF file ពិតប្រាកដ (NO HTML, no browser convert, margin left/right 0.25in)!"
        )
    except Exception as err:
        await update.message.reply_text("❌ PDF error: " + str(err))

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

if __name__ == "__main__":
    app.run_polling(stop_signals=None)
