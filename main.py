import os
import logging
from io import BytesIO
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Please set BOT_TOKEN as environment variable.")

FONT_PATH = "font/Battambang-Regular.ttf"  # Or the path where you upload Khmer font

class KhmerPDF:
    def __init__(self):
        from fpdf import FPDF
        self.FPDF = FPDF
        self.left_margin = self.right_margin = 6.35     # 0.25in = 6.35mm
        self.top_margin = self.bottom_margin = 10.16    # 0.4in = 10.16mm
        self.font_size = 19
        self.footer_font_size = 10
        self.font_name = "Battambang"

    def make_pdf(self, text):
        pdf = self.FPDF()
        pdf.add_page()
        # Add Battambang Unicode font
        pdf.add_font(self.font_name, '', FONT_PATH, uni=True)
        pdf.set_font(self.font_name, '', self.font_size)
        pdf.set_left_margin(self.left_margin)
        pdf.set_right_margin(self.right_margin)
        pdf.set_top_margin(self.top_margin)
        pdf.set_auto_page_break(True, margin=self.bottom_margin)
        lines = text.replace('\r\n', '\n').split('\n')
        for idx, line in enumerate(lines):
            pdf.multi_cell(0, 10, line, align='L')
        # Footer
        pdf.set_y(-15)
        pdf.set_font(self.font_name, '', self.footer_font_size)
        pdf.cell(0, 10, 'ទំព័រ 1 | Created by TENG SAMBATH', 0, 0, 'L')
        buffer = BytesIO()
        pdf.output(buffer)
        buffer.seek(0)
        return buffer

pdf_gen = KhmerPDF()

app = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "PDF Khmer Bot (no HTML, no browser convert)\n\n"
        "• OUTPUT: PDF true Khmer\n"
        "• Margins LEFT & RIGHT: 0.25in (6.35mm)\n"
        "• Font: Battambang 19px (.ttf) - Unicode OK\n"
        "• Footer: 'ទំព័រ 1 | Created by TENG SAMBATH'\n"
        "• Send Khmer text to get true PDF!"
    )

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith('/'):
        return
    if len(text) < 3:
        await update.message.reply_text("សូមផ្ញើអត្ថបទយ៉ាងហោចណាស់ 3 តួអក្សរ")
        return
    try:
        pdf_buffer = pdf_gen.make_pdf(text)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"SAMBATH_PDF_{timestamp}.pdf"
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=filename,
            caption="✅ PDF Khmer Unicode (margins 0.25in) created 🚀"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ PDF កំហុស: {e}")

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

if __name__ == "__main__":
    app.run_polling()
