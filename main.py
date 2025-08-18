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

# Logging
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
log = logging.getLogger("Text2PDFBot")

# ENV
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("សូមកំណត់ BOT_TOKEN ជា environment variable មុនចាប់ផ្តើម។")

# HTML Template (keep Khmer & line breaks)
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

# -------- Session (preserve send order) --------
SESSIONS = set()
# chat_chunks[chat_id] = [(seq, ts, text), ...]
chat_chunks: dict[int, list[tuple[int, str, str]]] = defaultdict(list)
chat_titles: dict[int, str] = {}

def _norm(s: str) -> str:
    return (s or "").replace("\r\n", "\n").replace("\r", "\n")

def append_chunk(chat_id: int, text: str):
    t = _norm(text)
    if not t:
        return
    seq = len(chat_chunks[chat_id]) + 1
    ts = datetime.utcnow().isoformat(timespec="seconds")
    chat_chunks[chat_id].append((seq, ts, t))
    log.debug("append_chunk: chat=%s seq=%s len=%s", chat_id, seq, len(t))

def merged_text(chat_id: int) -> str:
    chunks = sorted(chat_chunks.get(chat_id, []), key=lambda x: x[0])
    return "\n".join(c[1] for c in chunks)

def clear_session(chat_id: int):
    SESSIONS.discard(chat_id)
    chat_chunks.pop(chat_id, None)
    chat_titles.pop(chat_id, None)

# -------- PDF generator --------
async def send_pdf(chat_id: int, html_content: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)

        buf = BytesIO()
        HTML(string=html_content, base_url=".").write_pdf(buf)
        buf.seek(0)
        size_mb = len(buf.getvalue()) / (1024 * 1024)
        log.info("PDF generated: chat=%s size=%.2fMB", chat_id, size_mb)

        filename = f"KHMER_PDF_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        await update.message.reply_document(
            document=InputFile(buf, filename=filename),
            caption="✅ PDF merged តាមលំដាប់សារ!"
        )
        log.info("PDF sent: chat=%s", chat_id)

    except Exception:
        log.error("Generate/Send PDF failed:\n%s", traceback.format_exc())
        await update.message.reply_text("❌ មានបញ្ហាក្នុងការបង្កើត/ផ្ញើ PDF! សូមព្យាយាមម្ដងទៀត។")

# -------- Handlers --------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    clear_session(chat_id)
    SESSIONS.add(chat_id)

    title = _norm(" ".join(context.args)) if context.args else ""
    if title:
        chat_titles[chat_id] = title

    msg = [
        "✅ ចាប់ផ្តើមប្រមូលអត្ថបទ!",
        "• ផ្ញើអត្ថបទជាបន្តបន្ទាប់ (Telegram អាចបែកជាច្រើនសារ).",
        "• ពេលចប់ វាយ /done ដើម្បី merge ទាំងអស់ជា PDF មួយតាមលំដាប់ផ្ញើ។",
    ]
    if title:
        msg.insert(1, f"📌 ក្បាលអត្ថបទ: {html_module.escape(title)}")

    await update.message.reply_text("\n".join(msg))
    log.info("Session started: chat=%s title_len=%d", chat_id, len(title))

async def collect_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.text is None:
        return
    chat_id = update.effective_chat.id
    text = update.message.text

    # ជួយគាំទ្រពាក្យបញ្ចប់ជាទម្រង់ text ធម្មតា
    if text.strip().lower() in {"done", "រួច", "រួចហើយ", "finish", "end"}:
        return await done_command(update, context)

    if chat_id not in SESSIONS:
        SESSIONS.add(chat_id)

    append_chunk(chat_id, text)
    await update.message.reply_text(f"🧩 បានទទួល ({len(chat_chunks[chat_id])})! សរសេរ /done ពេលរួច។")

async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in SESSIONS:
        await update.message.reply_text("⚠️ សូមប្រើ /start ជាមុនសិន ហើយបន្ទាប់មកផ្ញើអត្ថបទ។")
        return

    text_all = merged_text(chat_id)
    title = (chat_titles.get(chat_id) or "").strip()

    log.info("DONE: chat=%s chunks=%d text_len=%d",
             chat_id, len(chat_chunks.get(chat_id, [])), len(text_all))

    if not text_all and not title:
        await update.message.reply_text("⚠️ មិនទាន់មានអត្ថបទសម្រាប់ merge ទេ។")
        return

    blocks = []
    if title:
        blocks.append(f"<h1>{html_module.escape(title)}</h1><hr>")
    blocks.append(f'<div class="content">{text_all}</div>')
    html_final = HTML_TEMPLATE.format(content="\n".join(blocks))

    await send_pdf(chat_id, html_final, update, context)
    clear_session(chat_id)

# -------- App wiring (order matters!) --------
def build_app() -> Application:
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("done", done_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, collect_text))
    return app

if __name__ == "__main__":
    log.info("Bot starting… Merge-by-order enabled (no size limit in code)")
    application = build_app()
    application.run_polling()
