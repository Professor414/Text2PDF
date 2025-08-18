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

# --------------------- Session State (preserve order) ---------------------
SESSIONS_ACTIVE = set()
# chat_chunks[chat_id] = list of tuples: (seq, ts_iso, text)
chat_chunks: dict[int, list[tuple[int, str, str]]] = defaultdict(list)
chat_titles: dict[int, str] = {}

def _normalize_text(s: str) -> str:
    return (s or "").replace("\r\n", "\n").replace("\r", "\n")

def append_chunk(chat_id: int, text: str):
    """Append chunk with increasing sequence to preserve exact order."""
    t = _normalize_text(text)
    if not t:
        return
    seq = len(chat_chunks[chat_id]) + 1
    ts = datetime.utcnow().isoformat(timespec="seconds")
    chat_chunks[chat_id].append((seq, ts, t))

def get_merged_text(chat_id: int) -> str:
    """Merge by sequence ascending to preserve send order."""
    chunks = chat_chunks.get(chat_id, [])
    # Already in order by construction; sort just in case
    chunks_sorted = sorted(chunks, key=lambda x: x[0])
    return "\n".join(c[1] for c in chunks_sorted)

def clear_session(chat_id: int):
    SESSIONS_ACTIVE.discard(chat_id)
    chat_chunks.pop(chat_id, None)
    chat_titles.pop(chat_id, None)

# --------------------- PDF Generator ---------------------
async def generate_and_send_pdf(chat_id: int, html_content: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)

        pdf_buffer = BytesIO()
        HTML(string=html_content, base_url=".").write_pdf(pdf_buffer)
        pdf_buffer.seek(0)

        size_mb = len(pdf_buffer.getvalue()) / (1024 * 1024)
        logger.info("PDF generated (chat=%s) size=%.2fMB", chat_id, size_mb)

        filename = f"KHMER_PDF_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        await update.message.reply_document(
            document=InputFile(pdf_buffer, filename=filename),
            caption="✅ PDF merged តាមលំដាប់សារ!"
        )
        logger.info("PDF sent (chat=%s)", chat_id)

    except Exception:
        logger.error("Generate/Send PDF failed:\n%s", traceback.format_exc())
        await update.message.reply_text("❌ មានបញ្ហាក្នុងការបង្កើត/ផ្ញើ PDF! សូមព្យាយាមម្ដងទៀត។")

# --------------------- Handlers ---------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start [optional title]
    Reset session, set optional title, begin collecting chunks in order.
    """
    chat_id = update.effective_chat.id
    clear_session(chat_id)
    SESSIONS_ACTIVE.add(chat_id)

    title = _normalize_text(" ".join(context.args)) if context.args else ""
    if title:
        chat_titles[chat_id] = title

    lines = [
        "✅ ចាប់ផ្តើមប្រមូលអត្ថបទ!",
        "• ផ្ញើអត្ថបទជាបន្តបន្ទាប់ (Telegram អាចបែកជាច្រើនសារ).",
        "• ពេលចប់ វាយ /done ដើម្បី merge ទាំងអស់ជា PDF មួយតាមលំដាប់ផ្ញើ។"
    ]
    if title:
        lines.insert(1, f"📌 ក្បាលអត្ថបទ: {html_module.escape(title)}")

    await update.message.reply_text("\n".join(lines))
    logger.info("Session started: chat=%s title_len=%d", chat_id, len(title))

async def collect_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.text is None:
        return
    chat_id = update.effective_chat.id
    text = update.message.text

    # Allow inline finish words
    if text.strip().lower() in {"done", "រួច", "រួចហើយ", "finish", "end"}:
        return await done_command(update, context)

    if chat_id not in SESSIONS_ACTIVE:
        SESSIONS_ACTIVE.add(chat_id)

    append_chunk(chat_id, text)
    total = len(chat_chunks[chat_id])
    await update.message.reply_text(f"🧩 បានទទួល ({total})! សរសេរ /done ពេលរួច។")
    logger.info("Collect: chat=%s chunk=%d len=%d", chat_id, total, len(text))

async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Merge all chunks by sequence and send back as one PDF.
    """
    chat_id = update.effective_chat.id
    if chat_id not in SESSIONS_ACTIVE:
        await update.message.reply_text("⚠️ មិនមានសម័យប្រមូលកំពុងដំណើរការ។ សូមប្រើ /start ជាមុនសិន។")
        return

    merged_text = get_merged_text(chat_id)
    title = (chat_titles.get(chat_id) or "").strip()

    logger.info("DONE: chat=%s title_len=%d text_len=%d chunks=%d",
                chat_id, len(title), len(merged_text), len(chat_chunks.get(chat_id, [])))

    if not merged_text and not title:
        await update.message.reply_text("⚠️ មិនទាន់មានអត្ថបទសម្រាប់ merge ទេ។ សូមផ្ញើអត្ថបទមុន។")
        return

    blocks = []
    if title:
        blocks.append(f"<h1>{html_module.escape(title)}</h1><hr>")
    # Important: one block keeps all line breaks as-is; order preserved by sequence
    blocks.append(f'<div class="content">{merged_text}</div>')
    final_html = HTML_TEMPLATE.format(content="\n".join(blocks))

    await generate_and_send_pdf(chat_id, final_html, update, context)
    clear_session(chat_id)

# --------------------- App wiring ---------------------
def build_app() -> Application:
    app = Application.builder().token(TOKEN).build()
    # Order matters: commands first
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("done", done_command))
    # Collect all text chunks (not commands)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, collect_text))
    return app

if __name__ == "__main__":
    logger.info("Bot starting... Merge-by-order enabled (no size limit in code)")
    application = build_app()
    application.run_polling()
