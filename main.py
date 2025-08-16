import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import logging
from weasyprint import HTML
from io import BytesIO
from datetime import datetime

logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Please set BOT_TOKEN")

HTML_TMPL = '''
<html>
<head>
<meta charset="utf-8">
<style>
    @page {{
        margin-left: 0.25in;
        margin-right: 0.25in;
        margin-top: 0.4in;
        margin-bottom: 0.4in;
    }}
    body {{
        font-family: 'Battambang','Noto Sans Khmer','Khmer OS','Arial',sans-serif;
        font-size: 19px;
        line-height: 2;
    }}
    .footer {{
        color: #666;
        font-size: 10px;
        margin-top: 30px;
    }}
</style>
<link href="https://fonts.googleapis.com/css2?family=Battambang:wght@400;700&display=swap" rel="stylesheet">
</head>
<body>
    <div>{body}</div>
    <div class="footer">ទំព័រ 1 | Created by TENG SAMBATH</div>
</body>
</html>
'''

app = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot PDF Khmer Perfect Shaping (WeasyPrint/HTML to PDF)\n\n• Margins 0.25in, 0.4in\n• Font: Battambang/Brower shaping\n• Footer: 'ទំព័រ 1 | Created by TENG SAMBATH'")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith("/"):
        return
    if len(text) < 3:
        await update.message.reply_text("សូមផ្ញើអក្សរច្រើនជាងនេះ!")
        return
    paragraphs = ['<p>'+line+'</p>' for line in text.replace('\r','').split('\n') if line.strip()]
    html = HTML_TMPL.format(body='\n'.join(paragraphs))
    pdf_buffer = BytesIO()
    HTML(string=html).write_pdf(pdf_buffer)
    pdf_buffer.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"KHMER_BEAUTIFUL_{timestamp}.pdf"
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=pdf_buffer,
        filename=filename,
        caption='✅ PDF Khmer shape correct! Margins 0.25in'
    )

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

if __name__ == "__main__":
    app.run_polling()
