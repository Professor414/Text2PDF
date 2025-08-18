import os
import logging
from io import BytesIO
from datetime import datetime
import traceback
import html as html_module
from collections import defaultdict

from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ChatAction
from weasyprint import HTML

# --------------------- Logging ---------------------
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("Text2PDFBot")

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
chat_buffers = defaultdict(list)   # chat_id -> [chunk, ...]
chat_titles  = {}                  # chat_id -> title

def _normalize_text(s: str) -> str:
    # រក្សា newline/space ដើម
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

# --------------------- PDF Generator ---------------------
async def generate_and_send_pdf(chat_id: int, html_content: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Build PDF from HTML and send back. No size limit in code.
    """
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)

        pdf_buffer = BytesIO()
        HTML(string=html_content, base_url=".").write_pdf(pdf_buffer)
        pdf_buffer.seek(0)
        size_mb = len(pdf_buffer.getvalue()) / (1024 * 1024)
        logger.info("PDF generated: chat=%s size=%.2fMB", chat_id, size_mb)

        filename = f"KHMER_PDF_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        await update.message.reply_document(
            document=InputFile(pdf_buffer, filename=filename),
            caption="✅ បង្កើត PDF រួចរាល់!"
        )
        logger.info("PDF sent to chat %s", chat_id)

    except Exception:
        logger.error("Generate/Send PDF failed:\n%s", traceback.format_exc())
        await update.message.reply_text(
            "❌ មានបញ្ហាក្នុងការបង្កើត/ផ្ញើ PDF! សូមព្យាយាមម្ដងទៀត ឬ បញ្ជូនអត្ថបទតិចជាង។"
        )

# --------------------- Handlers ---------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start [optional title]
    Reset session, set optional title, begin collecting chunks.
    """
    chat_id = update.effective_chat.id
    clear_session(chat_id)
    SESSIONS_ACTIVE.add(chat_id)

    title = _normalize_text(" ".join(context.args)) if context.args else ""
    if title:
        chat_titles[chat_id] = title

    msg = [
        "✅ ចាប់ផ្តើមប្រមូលអត្ថបទ!",
        "• ផ្ញើអត្ថបទជាបន្តបន្ទាប់ (Telegram អាចបែកជាច្រើនសារ).",
        "• ពេលចប់ វាយ /done ដើម្បីបំលែងជា PDF មួយ។"
    ]
    if title:
        msg.insert(1, f"📌 ក្បាលអត្ថបទ: {html_module.escape(title)}")

    await update.message.reply_text("\n".join(msg))
    logger.info("Session started: chat=%s title_len=%d", chat_id, len(title))

async def collect_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Collect every text chunk until /done.
    """
    if not update.message or update.message.text is None:
        return
    chat_id = update.effective_chat.id
    text = update.message.text

    # inline finish keywords
    if text.strip().lower() in {"done", "រួច", "រួចហើយ", "finish", "end"}:
        return await done_command(update, context)

    if chat_id not in SESSIONS_ACTIVE:
        SESSIONS_ACTIVE.add(chat_id)

    append_to_buffer(chat_id, text)
    await update.message.reply_text("🧩 បានទទួល! សរសេរ /done ពេលរួច។")

async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Merge all buffered text → single PDF and send.
    """
    chat_id = update.effective_chat.id
    if chat_id not in SESSIONS_ACTIVE:
        await update.message.reply_text("⚠️ មិនមានសម័យប្រមូលកំពុងដំណើរការ។ សូមប្រើ /start ជាមុនសិន។")
        return

    full_text = get_buffer_text(chat_id)
    title = (chat_titles.get(chat_id) or "").strip()

    logging.info("DONE called: title_len=%d text_len=%d", len(title), len(full_text))

    if not full_text and not title:
        await update.message.reply_text("⚠️ មិនទាន់មានអត្ថបទសម្រាប់បំលែងទេ។ សូមផ្ញើអត្ថបទមុន។")
        return

    # Build final HTML
    blocks = []
    if title:
        blocks.append(f"<h1>{html_module.escape(title)}</h1><hr>")
    blocks.append(f'<div class="content">{full_text}</div>')
    final_html = HTML_TEMPLATE.format(content="\n".join(blocks))

    await generate_and_send_pdf(chat_id, final_html, update, context)
    clear_session(chat_id)

# --------------------- Application wiring ---------------------
def build_app() -> Application:
    app = Application.builder().token(TOKEN).build()
    # Commands first (important)
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("done", done_command))
    # Collect all text chunks
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, collect_text))
    return app

if __name__ == "__main__":
    logger.info("Bot starting... (No PDF size limit in code)")
    application = build_app()
    application.run_polling()
