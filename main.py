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

# --- ផ្នែក Web Server ដើម្បីឲ្យ Deploy ដំណើរការ ---
server = Flask('')

@server.route('/')
def home():
    return "Bot is alive!"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server.run(host='0.0.0.0', port=port)

flask_thread = Thread(target=run_server)
# --- ចប់ផ្នែក Web Server ---

# កំណត់ Logging
logging.basicConfig(level=logging.INFO)

# Variable បរិស្ថាន
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("សូមកំណត់ BOT_TOKEN ជា environment variable មុនចាប់ផ្តើម។")

# HTML Template (Khmer PDF)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="km">
<head>
<meta charset="utf-8">
<style>
  @page { size: A4; margin: 0.4in 0.35in; }
  body { font-family: 'Khmer OS Battambang','Noto Sans Khmer','Noto Serif Khmer',sans-serif; font-size: 19px; line-height: 1.6; }
  p { margin: 0 0 8px 0; white-space: pre-wrap; }
  h1 { font-size: 22px; margin: 0 0 12px 0; }
  hr { border: none; border-top: 1px solid #999; margin: 10px 0 16px 0; }
</style>
</head>
<body>
{content}
</body>
</html>
"""

# =========================
# Session buffer & helpers
# =========================
chat_buffers = defaultdict(list)      # chat_id -> [text, text, ...]
chat_titles  = {}                     # chat_id -> title string (optional)

def _normalize_text(s: str) -> str:
    s = (s or "").replace('\r\n', '\n').replace('\r', '\n')
    s = re.sub(r'\n{3,}', '\n\n', s)  # កាត់បន្ថយខ្សែទទេ 3+ ជា 2
    return s.strip()

def append_to_buffer(chat_id: int, text: str):
    t = _normalize_text(text)
    if t:
        chat_buffers[chat_id].append(t)

def get_buffer_text(chat_id: int) -> str:
    parts = chat_buffers.get(chat_id, [])
    return ("\n\n".join(parts)).strip() if parts else ""

def clear_session(chat_id: int):
    if chat_id in chat_buffers:
        del chat_buffers[chat_id]
    if chat_id in chat_titles:
        del chat_titles[chat_id]

# =========================
# Handlers
# =========================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start = ចាប់ផ្តើមសម័យប្រមូលអត្ថបទ និងកំណត់ក្បាលអត្ថបទ (optional title)
    ប្រសិនបើអ្នកផ្ដល់ args បន្ទាប់ពី /start នឹងយកជាក្បាលអត្ថបទ
    ឧ: /start ប្រធានបទរឿងអប់រំ
    """
    chat_id = update.effective_chat.id
    clear_session(chat_id)

    # Title ពី arguments បន្ទាប់ពី /start បើមាន
    title = ""
    if context.args:
        title = _normalize_text(" ".join(context.args))
        if title:
            chat_titles[chat_id] = title

    msg_lines = [
        "✅ ចាប់ផ្តើមសម័យប្រមូលអត្ថបទ!",
        "• ផ្ញើអត្ថបទជាបន្តបន្ទាប់ អាចវែង និងបែកជាច្រើនសារ។",
        "• ពេលចប់ សរសេរ /done ដើម្បីបំលែងជាឯកសារ PDF មួយ។"
    ]
    if title:
        msg_lines.insert(1, f"📌 ក្បាលអត្ថបទ: {title}")

    await update.message.reply_text("\n".join(msg_lines))

async def collect_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ប្រមូលសារ TEXT ទាំងអស់ចូល buffer រហូតដល់ /done
    ក៏គាំទ្រ 'done/រួច/រួចហើយ/end/finish' ជា inline សញ្ញាបញ្ចប់
    """
    if not update.message or update.message.text is None:
        return

    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    if text in {"done", "រួច", "រួចហើយ", "end", "finish"}:
        return await done_command(update, context)

    append_to_buffer(chat_id, text)
    total_chars = len(get_buffer_text(chat_id))
    await update.message.reply_text(
        f"🧩 បានបន្ថែម! បច្ចុប្បន្នប្រមូល {total_chars} តួអក្សរ។\n"
        f"➡️ សរសេរ /done ពេលរួច។"
    )

async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /done = បំលែងអត្ថបទទាំងអស់ក្នុង buffer (និង title ប្រសិនបើមាន)
    ជា PDF មួយ ហើយផ្ញើត្រឡប់
    """
    chat_id = update.effective_chat.id
    user_text = get_buffer_text(chat_id)
    title = chat_titles.get(chat_id, "").strip()

    if not user_text and not title:
        return await update.message.reply_text(
            "⚠️ មិនមានអត្ថបទសម្រាប់បំលែងទេ។ ប្រើ /start ដើម្បីចាប់ផ្តើមហើយផ្ញើអត្ថបទ។"
        )

    try:
        # Build HTML
        blocks = []
        if title:
            blocks.append(f"<h1>{title}</h1><hr>")

        for line in (title + ("\n\n" if title and user_text else "") + user_text).split('\n'):
            line = line.strip()
            if line:
                blocks.append(f"<p>{line}</p>")

        html_content = "\n ".join(blocks) if blocks else "<p></p>"
        final_html = HTML_TEMPLATE.format(content=html_content)

        # Generate PDF
        pdf_buffer = BytesIO()
        HTML(string=final_html).write_pdf(pdf_buffer)
        pdf_buffer.seek(0)

        # Send PDF
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"KHMER_PDF_{timestamp}.pdf"

        await context.bot.send_document(
            chat_id=chat_id,
            document=pdf_buffer,
            filename=filename,
            caption="✅ PDF មួយបានបញ្ចប់ (រួមសារ​ទាំងអស់)!"
        )
        await update.message.reply_text("📄 សូមពិនិត្យឯកសារ PDF ដែលបានផ្ញើឡើង!")

        logging.info("PDF sent (chat=%s, chars=%s)", chat_id, len(user_text) + len(title))
    except Exception as e:
        import traceback
        logging.error("PDF error: %s\n%s", e, traceback.format_exc())
        await update.message.reply_text(f"❌ បរាជ័យក្នុងការបង្កើត PDF: {e}")
    finally:
        # Clear session for next round
        clear_session(chat_id)

# =========================
# Application setup
# =========================
app = Application.builder().token(TOKEN).build()

# Add Handlers (សំខាន់: លំដាប់)
app.add_handler(CommandHandler("start", start_command))
app.add_handler(CommandHandler("done", done_command))   # ត្រូវនៅមុន text handler
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, collect_text))

# Main Run
if __name__ == "__main__":
    try:
        logging.info("🚀 កំពុងចាប់ផ្តើម PDF Khmer Bot by TENG SAMBATH...")

        # ចាប់ផ្តើម Web Server នៅក្នុង Thread ដូចដើម
        flask_thread.start()

        logging.info("✅ WeasyPrint PDF generation ready")
        logging.info("📐 Margins: Left/Right 0.35\", Top/Bottom 0.4\"")
        logging.info("📝 Font: 19px Khmer fonts")
        logging.info("🎯 Aggregation with /start → collect → /done")

        # ចាប់ផ្តើម Bot ដូចដើម
        app.run_polling()

    except Exception as e:
        logging.error(f"មិនអាចចាប់ផ្តើម Bot បានទេ: {e}")
        raise
