import os
import logging
from io import BytesIO
from datetime import datetime
import traceback

from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from weasyprint import HTML

# កំណត់ Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Variable បរិស្ថាន
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("សូមកំណត់ BOT_TOKEN ជា environment variable មុនចាប់ផ្តើម។")

# HTML Template (Khmer PDF)
# សំខាន់៖ ប្រើ Font ដែលយើងនឹងដំឡើងនៅលើ Server (fonts-khmeros)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="km">
<head>
<meta charset="utf-8">
<style>
  @page { size: A4; margin: 0.4in 0.35in; }
  body { 
    font-family: 'Khmer OS Battambang', 'Noto Sans Khmer', 'Noto Serif Khmer', sans-serif; 
    font-size: 19px; 
    line-height: 1.6; 
  }
  .content { white-space: pre-wrap; }
  h1 { font-size: 22px; margin: 0 0 12px 0; }
  hr { border: none; border-top: 1px solid #999; margin: 10px 0 16px 0; }
</style>
</head>
<body>
{content}
</body>
</html>
"""

# ---------------------- Session Management ----------------------
from collections import defaultdict

SESSIONS_ACTIVE = set()
chat_buffers = defaultdict(list)
chat_titles = {}

def _normalize_text(s: str) -> str:
    return (s or "").replace("\r\n", "\n").replace("\r", "\n")

def append_to_buffer(chat_id: int, text: str):
    t = _normalize_text(text)
    if t:
        chat_buffers[chat_id].append(t)

def get_buffer_text(chat_id: int) -> str:
    return "\n".join(chat_buffers.get(chat_id, []))

def clear_session(chat_id: int):
    SESSIONS_ACTIVE.discard(chat_id)
    chat_buffers.pop(chat_id, None)
    chat_titles.pop(chat_id, None)

# ---------------------- PDF Generation Core Function ----------------------
async def generate_and_send_pdf(chat_id: int, html_content: str, context: ContextTypes.DEFAULT_TYPE):
    """
    Core function to generate PDF from HTML, check size, and send.
    """
    try:
        pdf_buffer = BytesIO()
        HTML(string=html_content, base_url=".").write_pdf(pdf_buffer)

        # ពិនិត្យទំហំឯកសារ PDF ធៀបនឹងដែនកំណត់ 50MB របស់ Telegram
        TELEGRAM_LIMIT_BYTES = 50 * 1024 * 1024
        if pdf_buffer.tell() >= TELEGRAM_LIMIT_BYTES:
            pdf_size_mb = pdf_buffer.tell() / (1024 * 1024)
            logger.warning(f"PDF size ({pdf_size_mb:.2f}MB) exceeds limit for chat {chat_id}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"❌ **ឯកសារ PDF មានទំហំធំពេក!**\n\n"
                    f"ទំហំឯកសារគឺ **{pdf_size_mb:.2f} MB** ដែលលើសពីដែនកំណត់ **50 MB** របស់ Telegram។\n\n"
                    "💡 សូមព្យាយាមផ្ញើអត្ថបទខ្លីជាងនេះ ឬ បែងចែកជាផ្នែកៗ។"
                )
            )
            return

        pdf_buffer.seek(0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"KHMER_PDF_{timestamp}.pdf"

        await context.bot.send_document(
            chat_id=chat_id,
            document=InputFile(pdf_buffer, filename=filename),
            caption="✅ **សូមអបអរ អត្ថបទរបស់អ្នករួចរាល់!**\n\n"
                    "• បង្កើតដោយ៖ https://t.me/ts_4699"
        )
        logger.info(f"PDF sent successfully to chat {chat_id}")

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Failed to generate/send PDF for chat {chat_id}: {e}\n{error_details}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "❌ **មានបញ្ហាក្នុងការបង្កើត PDF!**\n\n"
                f"**កំហុស:** `{str(e)}`\n\n"
                "🔄 សូមព្យាយាមម្ដងទៀត។ ប្រសិនបើបញ្ហានៅតែកើតមាន សូមទាក់ទងអ្នកអភិវឌ្ឍន៍។"
            )
        )

# ---------------------- Command and Message Handlers ----------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    clear_session(chat_id)
    SESSIONS_ACTIVE.add(chat_id)

    title = _normalize_text(" ".join(context.args)) if context.args else ""
    if title:
        chat_titles[chat_id] = title

    lines = [
        "✅ **ចាប់ផ្តើមប្រមូលអត្ថបទ!**",
        "• សូមផ្ញើសារជាបន្តបន្ទាប់។",
        "• ពេលរួចរាល់ សូមវាយ /done ដើម្បីបង្កើតជាឯកសារ PDF តែមួយ។",
    ]
    if title:
        lines.insert(1, f"📌 **ក្បាលអត្ថបទ:** {title}")

    await update.message.reply_text("\n".join(lines))

async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in SESSIONS_ACTIVE:
        await update.message.reply_text("⚠️ មិនមានសម័យប្រមូលអត្ថបទដែលកំពុងដំណើរការទេ។ សូមប្រើ /start ជាមុនសិន។")
        return

    full_text = get_buffer_text(chat_id)
    title = chat_titles.get(chat_id, "").strip()

    if not full_text and not title:
        await update.message.reply_text("⚠️ មិនទាន់មានអត្ថបទសម្រាប់បំប្លែងទេ។ សូមផ្ញើអត្ថបទខ្លះមក។")
        return

    blocks = []
    if title:
        blocks.append(f"<h1>{title}</h1><hr>")
    blocks.append(f'<div class="content">{full_text}</div>')
    final_html = HTML_TEMPLATE.format(content="\n".join(blocks))

    await generate_and_send_pdf(chat_id, final_html, context)
    clear_session(chat_id)

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text
    
    # Mode 1: If a session is active, collect text
    if chat_id in SESSIONS_ACTIVE:
        if text.strip().lower() in {"done", "រួច", "រួចហើយ", "finish", "end"}:
            await done_command(update, context)
        else:
            append_to_buffer(chat_id, text)
            await update.message.reply_text("🧩 បានទទួល! បន្តផ្ញើមកទៀត ឬវាយ /done ពេលរួចរាល់។", reply_to_message_id=update.message.message_id)
    # Mode 2: No active session, convert single message directly
    else:
        content = f'<div class="content">{_normalize_text(text)}</div>'
        final_html = HTML_TEMPLATE.format(content=content)
        await generate_and_send_pdf(chat_id, final_html, context)

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("done", done_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    logger.info("🚀 Bot is starting...")
    logger.info("🎯 Modes: single-message -> PDF, or /start.../done -> single PDF")
    
    app.run_polling()

if __name__ == "__main__":
    main()
