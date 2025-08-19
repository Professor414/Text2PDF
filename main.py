import os
import re
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from weasyprint import HTML

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Token
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Memory store
user_texts = {}

# Regex detect only line-start patterns
PATTERN = re.compile(r"^(A\.|[ក-ឳ]\.|[0-9១-៩]+\.)", re.MULTILINE)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_texts[update.effective_user.id] = []
    await update.message.reply_text(
        "សួស្តី! ផ្ញើអត្ថបទជាបន្ទាត់ៗ។\n"
        "- បើចង់បានក្បាលប្រធាន ចាប់ផ្តើមជួរដោយ A.\n"
        "- ចំណុច អក្សរខ្មែរ ចាប់ផ្តើមជួរដោយ ក. ខ. គ.…\n"
        "- លេខ ចាប់ផ្តើមជួរដោយ ១. ឬ 1.\n\n"
        "ពេលបញ្ចប់ វាយ /done ដើម្បីទទួល PDF។"
    )

async def save_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in user_texts:
        user_texts[uid] = []
    user_texts[uid].append(update.message.text)
    await update.message.reply_text("📌 អត្ថបទបានរក្សាទុក!")

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in user_texts or not user_texts[uid]:
        await update.message.reply_text("❌ មិនមានអត្ថបទសម្រាប់បំលែងទេ។")
        return

    text = "\n".join(user_texts[uid])

    # Insert <br> only before line-start markers
    formatted_text = PATTERN.sub(r"<br>\1", text)

    # Wrap in HTML
    html_content = f"""
    <html>
    <head>
      <meta charset="utf-8"/>
      <style>
        @font-face {{
          font-family: "NotoSansKhmer";
          src: local("Noto Sans Khmer"), local("Battambang");
        }}
        body {{
          font-family: "NotoSansKhmer", "Battambang", sans-serif;
          font-size: 19px;
          line-height: 2;
          margin: 0.4in;
        }}
        footer {{
          position: fixed;
          bottom: 10px;
          left: 0;
          right: 0;
          text-align: center;
          font-size: 12px;
          color: gray;
        }}
      </style>
    </head>
    <body>
      {formatted_text}
      <footer>Bot Text2PDF | Teng Sambath</footer>
    </body>
    </html>
    """

    # Export to PDF
    filename = f"KHMER_PDF_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    HTML(string=html_content).write_pdf(filename)

    await update.message.reply_document(open(filename, "rb"), filename=filename)

    # Clear memory
    user_texts[uid] = []

def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not set")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_text))

    logger.info("🚀 Bot Running…")
    app.run_polling()

if __name__ == "__main__":
    main()
