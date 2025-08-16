import os
import logging
from io import BytesIO
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from weasyprint import HTML

logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Please set BOT_TOKEN as environment variable.")

HTML_TMPL = '''
<!DOCTYPE html>
<html lang="km">
<head>
<meta charset="utf-8">
<title>PDF Khmer by TENG SAMBATH</title>
<style>
    @page {
        margin-left: 0.25in;
        margin-right: 0.25in;
        margin-top: 0.4in;
        margin-bottom: 0.4in;
    }
    body {
        font-family: 'Battambang','Noto Sans Khmer','Khmer OS','Arial',sans-serif;
        font-size: 19px;
        line-height: 2;
        color: #222;
    }
    .footer {
        color: #666;
        font-size: 10px;
        margin-top: 30px;
    }
</style>
<link href="https://fonts.googleapis.com/css2?family=Battambang:wght@400;700&display=swap" rel="stylesheet">
</head>
<body>
<div>{body}</div>
<div class="footer">ទំព័រ 1 | Created by TENG SAMBATH</div>
</body></html>
'''

app = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🇰🇭 PDF Khmer Bot - Auto PDF Shaping (No browser/Print Button)\n\n"
        "• នេះជាប្រព័ន្ធ convert សំណួរទៅ PDF Khmer shaping ស្អាត\n"
        "• Bot នឹងផ្ញើ PDF file ត្រឡប់ជាស្វ័យប្រវត្តិ (គ្មាន HTML, មិនចាំបាច់ print browser)\n"
        "• Margins: 0.25in / 0.4in | Fonts: Battambang/Noto Sans Khmer/KhmerOS"
    )

async def convert_and_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith("/"):
        return
    # ស្វែងរកកំណត់អត្ថបទ (មិនមាន text limit)
    paragraphs = ['<p>' + line + '</p>' for line in text.replace('\r','').split('\n') if line.strip()]
    html = HTML_TMPL.format(body='\n'.join(paragraphs))

    # បម្លែង HTML -> PDF (no browser interaction)
    pdf_buffer = BytesIO()
    HTML(string=html).write_pdf(pdf_buffer)
    pdf_buffer.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"KHMER_AUTO_PDF_{timestamp}.pdf"
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=pdf_buffer,
        filename=filename,
        caption="✅ PDF shaping ស្អាត! មិនចាំបាច់ print browser, ទទួល PDF ភ្លាមៗ (bot auto convert)"
    )

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, convert_and_reply))

if __name__ == "__main__":
    app.run_polling()
