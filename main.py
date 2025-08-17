import os
import logging
import re
from io import BytesIO
from datetime import datetime
from collections import defaultdict

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from weasyprint import HTML
from flask import Flask
from threading import Thread

# --- Web Server (keep original behavior) ---
server = Flask('')

@server.route('/')
def home():
    return "Bot is alive!"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server.run(host='0.0.0.0', port=port)

flask_thread = Thread(target=run_server)
# --- End Web Server ---

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# Env
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("សូមកំណត់ BOT_TOKEN ជា environment variable មុនចាប់ផ្តើម។")

# HTML template (Unicode Khmer safe)
HTML_HEAD = """<!DOCTYPE html><html lang="km"><head><meta charset="utf-8">
<style>
@page { size: A4; margin: 0.4in 0.35in; }
body { font-family: 'Khmer OS Battambang','Noto Sans Khmer','Noto Serif Khmer',sans-serif; font-size: 19px; line-height: 1.6; }
p { margin: 0 0 8px 0; white-space: pre-wrap; }
h1 { font-size: 22px; margin: 0 0 12px 0; }
hr { border: none; border-top: 1px solid #999; margin: 10px 0 16px 0; }
</style></head><body>
"""
HTML_TAIL = "</body></html>"

# -------- Session buffers (no size cap here) --------
chat_buffers = defaultdict(list)   # chat_id -> [text, ...]
chat_titles  = {}                  # chat_id -> title

def _normalize_text(s: str) -> str:
    s = (s or "").replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def append_to_buffer(chat_id: int, text: str):
    t = _normalize_text(text)
    if t:
        chat_buffers[chat_id].append(t)

def get_buffer_text(chat_id: int) -> str:
    parts = chat_buffers.get(chat_id, [])
    return ("\n\n".join(parts)).strip() if parts else ""

def clear_session(chat_id: int):
    chat_buffers.pop(chat_id, None)
    chat_titles.pop(chat_id, None)

# -------------- Handlers --------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start [optional title]
    - Reset session
    - Optionally set document title from args
    """
    chat_id = update.effective_chat.id
    clear_session(chat_id)

    title = ""
    if context.args:
        title = _normalize_text(" ".join(context.args))
        if title:
            chat_titles[chat_id] = title

    msg = [
        "✅ ចាប់ផ្តើមប្រមូលអត្ថបទ!",
        "• ផ្ញើអត្ថបទជាបន្តបន្ទាប់ អាចវែង និងបែកជាច្រើនសារ។",
        "• ពេលចប់ សរសេរ /done ដើម្បីបំលែងជាឯកសារ PDF មួយ។"
    ]
    if title:
        msg.insert(1, f"📌 ក្បាលអត្ថបទ: {title}")

    await update.message.reply_text("\n".join(msg))

async def collect_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Collect all text chunks into buffer until /done.
    Also accept 'done/រួច/finish/end' as inline finish word.
    """
    if not update.message or update.message.text is None:
        return
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    if text.lower() in {"done", "រួច", "រួចហើយ", "finish", "end"}:
        return await done_command(update, context)

    append_to_buffer(chat_id, text)
    total_chars = len(get_buffer_text(chat_id))
    await update.message.reply_text(
        f"🧩 បានបន្ថែម! បច្ចុប្បន្នប្រមូល {total_chars} តួអក្សរ។\n"
        f"➡️ សរសេរ /done ពេលរួច។"
    )

async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Merge all buffered texts (and optional title) → one PDF and send it back.
    Sends as raw bytes to avoid Telegram 'size' mishandling.
    """
    chat_id = update.effective_chat.id
    user_text = get_buffer_text(chat_id)
    title = chat_titles.get(chat_id, "").strip()

    if not user_text and not title:
        return await update.message.reply_text(
            "⚠️ មិនមានអត្ថបទសម្រាប់បំលែងទេ។ ប្រើ /start ហើយផ្ញើអត្ថបទសិន។"
        )

    try:
        # Build final HTML
        blocks = []
        if title:
            blocks.append(f"<h1>{title}</h1><hr>")

        # Split to paragraphs without size limit
        for line in (user_text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            ln = line.strip()
            if ln:
                blocks.append(f"<p>{ln}</p>")

        final_html = HTML_HEAD + ("\n".join(blocks) if blocks else "<p></p>") + HTML_TAIL
        logging.info("HTML length: %s chars, paragraphs: %s", len(final_html), len(blocks))

        # Generate PDF into memory
        pdf_buffer = BytesIO()
        HTML(string=final_html, base_url=".").write_pdf(pdf_buffer)
        pdf_buffer.seek(0)
        pdf_bytes = pdf_buffer.getvalue()
        size_bytes = len(pdf_bytes)

        if size_bytes < 100:
            raise ValueError("Generated PDF is empty. Check fonts/deps.")

        # Telegram can handle big documents; we send raw bytes
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"KHMER_PDF_{ts}.pdf"

        await context.bot.send_document(
            chat_id=chat_id,
            document=pdf_bytes,  # bytes to avoid file-like pointer quirks
            filename=filename
            # avoid long caption to reduce risk of validation quirks
        )

        await update.message.reply_text(f"📄 PDF បានបញ្ជូន! ទំហំ ~{size_bytes/1024/1024:.2f}MB ✅")
        logging.info("PDF sent OK: chat=%s, size=%s bytes", chat_id, size_bytes)
    except Exception as e:
        import traceback
        logging.error("PDF error: %s\n%s", e, traceback.format_exc())
        await update.message.reply_text(f"❌ បញ្ហាបង្កើត/ផ្ញើ PDF: {e}")
    finally:
        clear_session(chat_id)

# -------------- App wiring --------------
app = Application.builder().token(TOKEN).build()

# Order matters: command before text handler
app.add_handler(CommandHandler("start", start_command))
app.add_handler(CommandHandler("done", done_command))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, collect_text))

# -------------- Main --------------
if __name__ == "__main__":
    try:
        logging.info("🚀 កំពុងចាប់ផ្តើម PDF Khmer Bot ...")
        flask_thread.start()
        logging.info("✅ Ready (WeasyPrint HTML→PDF)")

        app.run_polling()
    except Exception as e:
        logging.error("មិនអាចចាប់ផ្តើម Bot បានទេ: %s", e)
        raise
