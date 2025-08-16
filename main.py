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
        "🇰🇭 PDF Khmer Bot - Auto PDF Shaping (ស្រេច, មិនចាំបាច់ print/browser)\n\n"
        "• ផ្ញើអត្ថបទ, bot will auto-create PDF (margins 0.25/0.4 in, shaping perfect Khmer)\n"
        "• PDF file sent directly, no HTML/manual steps needed\n"
        "• Footer: ទំព័រ 1 | Created by TENG SAMBATH"
    )

async def convert_and_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip()
        if text.startswith("/"):
            return
        paragraphs = ['<p>' + line + '</p>' for line in text.replace('\r','').split('\n') if line.strip()]
        html = HTML_TMPL.format(body='\n'.join(paragraphs))
        pdf_buffer = BytesIO()
        HTML(string=html).write_pdf(pdf_buffer)
        pdf_buffer.seek(0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"KHMER_AUTO_PDF_{timestamp}.pdf"
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=filename,
            caption="✅ PDF shaping ស្អាត! ទទួល PDF ត្រឡប់មកភ្លាមៗ (bot auto convert)"
        )
    except Exception as e:
        # Error handler: log + tell user
        import traceback
        logging.error("PDF convert failed: %s\n%s", str(e), traceback.format_exc())
        await update.message.reply_text(
            f"❌ មានបញ្ហាក្នុងការបំលែងទៅ PDF!\n\nលម្អិត: {e}"
        )

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, convert_and_reply))

if __name__ == "__main__":
    app.run_polling()
