import os
import logging
from io import BytesIO
from datetime import datetime
import traceback
import html
from collections import defaultdict

from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ChatAction

from weasyprint import HTML

# --------------------- Logging ---------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --------------------- ENV ---------------------
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("សូមកំណត់ BOT_TOKEN ជា environment variable មុនចាប់ផ្តើម។")

# --------------------- HTML Template ---------------------
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="km">
<head>
<meta charset="utf-8">
<style>
  @page { size: A4; margin: 0.4in 0.35in; }
  body { font-family: 'Khmer OS Battambang','Noto Sans Khmer','Noto Serif Khmer', sans-serif; font-size: 19px; line-height: 1.6; }
  .content { white-space: pre-wrap; }
  h1 { font-size: 22px; margin: 0 0 12px 0; }
  hr { border: none; border-top: 1px solid #999; margin: 10px 0 16px 0; }
</style>
</head>
<body>
{content}
</body>
</html>"""

# --------------------- Session State ---------------------
SESSIONS_ACTIVE = set()
# chat_chunks[chat_id] = list of tuples: (seq, text)
chat_chunks: dict[int, list[tuple[int, str]]] = defaultdict(list)
chat_titles: dict[int, str] = {}

def _normalize_text(s: str) -> str:
    return (s or "").replace("\r\n", "\n").replace("\r", "\n")

def append_chunk(chat_id: int, text: str):
    t = _normalize_text(text)
    if not t:
        return
    seq = len(chat_chunks.get(chat_id, [])) + 1
    chat_chunks[chat_id].append((seq, t))

def get_merged_text(chat_id: int) -> str:
    chunks = chat_chunks.get(chat_id, [])
    # Sort by sequence number to guarantee order
    chunks_sorted = sorted(chunks, key=lambda x: x[0])
    # FIX: The bug was here. Use c[1] which is the text.
    return "\n".join(c[1] for c in chunks_sorted)

def clear_session(chat_id: int):
    SESSIONS_ACTIVE.discard(chat_id)
    chat_chunks.pop(cat_id, None)
    chat_titles.pop(chat_id, None)

# --------------------- PDF Generator ---------------------
async def generate_and_send_pdf(chat_id: int, html_content: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)

        pdf_buffer = BytesIO()
        HTML(string=html_content, base_url=".").write_pdf(pdf_buffer)

        # Re-add size check for safety
        TELEGRAM_LIMIT_BYTES = 50 * 1024 * 1024
        if pdf_buffer.tell() >= TELEGRAM_LIMIT_BYTES:
            size_mb = pdf_buffer.tell() / (1024 * 1024)
            logger.warning(f"PDF size ({size_mb:.2f}MB) exceeds limit for chat {chat_id}")
            await update.message.reply_text(
                f"❌ **ឯកសារ PDF មានទំហំធំពេក ({size_mb:.2f} MB)!**\n\nដែនកំណត់របស់ Telegram គឺ 50 MB។"
            )
            return

        pdf_buffer.seek(0)
        filename = f"KHMER_PDF_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        await update.message.reply_document(
            document=InputFile(pdf_buffer, filename=filename),
            caption="✅ **ឯកសារ PDF របស់អ្នករួចរាល់ហើយ!**"
        )
        logger.info("PDF sent successfully to chat %s", chat_id)

    except Exception:
        logger.error("Generate/Send PDF failed for chat %s:\n%s", chat_id, traceback.format_exc())
        await update.message.reply_text("❌ មានបញ្ហាក្នុងការបង្កើត/ផ្ញើ PDF! សូមព្យាយាមម្ដងទៀត។")

# --------------------- Handlers ---------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    clear_session(chat_id)
    SESSIONS_ACTIVE.add(chat_id)

    title = _normalize_text(" ".join(context.args)) if context.args else ""
    if title:
        chat_titles[chat_id] = title

    lines = [
        "✅ **ចាប់ផ្តើមប្រមូលអត្ថបទ!**",
        "• ផ្ញើអត្ថបទជាបន្តបន្ទាប់។",
        "• ពេលចប់ វាយ /done ដើម្បីបំប្លែងជា PDF តែមួយ។"
    ]
    if title:
        lines.insert(1, f"📌 **ក្បាលអត្ថបទ:** {html.escape(title)}")
    await update.message.reply_text("\n".join(lines))

async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in SESSIONS_ACTIVE:
        await update.message.reply_text("⚠️ មិនមានសម័យប្រមូលកំពុងដំណើរការទេ។ សូមប្រើ /start ជាមុនសិន។")
        return

    merged_text = get_merged_text(chat_id)
    title = (chat_titles.get(chat_id) or "").strip()

    if not merged_text and not title:
        await update.message.reply_text("⚠️ មិនទាន់មានអត្ថបទសម្រាប់បំប្លែងទេ។")
        return

    blocks = []
    if title:
        blocks.append(f"<h1>{html.escape(title)}</h1><hr>")
    blocks.append(f'<div class="content">{html.escape(merged_text)}</div>')
    final_html = HTML_TEMPLATE.format(content="\n".join(blocks))

    await generate_and_send_pdf(chat_id, final_html, update, context)
    clear_session(chat_id)

async def session_text_collector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text

    if text.strip().lower() in {"done", "រួច", "រួចហើយ", "finish", "end"}:
        return await done_command(update, context)

    append_chunk(chat_id, text)
    total = len(chat_chunks[chat_id])
    await update.message.reply_text(f"🧩 បានទទួល ({total})! វាយ /done ពេលរួចរាល់។")

async def single_text_converter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = _normalize_text(update.message.text)
    
    content = f'<div class="content">{html.escape(text)}</div>'
    final_html = HTML_TEMPLATE.format(content=content)
    await generate_and_send_pdf(chat_id, final_html, update, context)
    
# FIX: Added a global error handler to prevent silent crashes
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)
    tb_string = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))
    logger.error(f"Traceback:\n{tb_string}")

    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "❌ សូមអភ័យទោស មានបញ្ហាបច្ចេកទេសកើតឡើង។ សូមព្យាយាមម្តងទៀត។"
        )

# --------------------- App wiring ---------------------
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("done", done_command))

    # Handler for active sessions: Collects text into the buffer.
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Chat(chat_id=SESSIONS_ACTIVE),
        session_text_collector
    ))

    # Fallback handler for inactive sessions: Converts a single message directly.
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        single_text_converter
    ))
    
    # Register the global error handler
    app.add_error_handler(error_handler)

    logger.info("Bot is starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
