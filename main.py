import os
import logging
from io import BytesIO
from datetime import datetime
from collections import defaultdict

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from weasyprint import HTML

# --------------------- កំណត់ Logging ---------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# --------------------- Variable បរិស្ថាន ---------------------
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("សូមកំណត់ BOT_TOKEN ជា environment variable មុនចាប់ផ្តើម។")

# ទំហំអតិបរមា PDF (byte) — 10MB
MAX_PDF_BYTES = 10 * 1024 * 1024  # 10MB

# --------------------- HTML Template (Khmer PDF) ---------------------
# រក្សាទ្រង់ទ្រាយដើម ប៉ុន្តែប្រើ pre-wrap ដើម្បីរក្សា newline/space ដើម
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="km">
<head>
<meta charset="utf-8">
<style>
  @page { size: A4; margin: 0.4in 0.35in; }
  body { font-family: 'Khmer OS Battambang','Noto Sans Khmer','Noto Serif Khmer',sans-serif; font-size: 19px; line-height: 1.6; }
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

# =========================================================
# Session buffer សម្រាប់ប្រមូលអត្ថបទតាម chat (រក្សា logic ដើម)
# =========================================================
def _normalize_text(s: str) -> str:
    # កុំ strip ដើម្បីរក្សា space/newline ដើម
    return (s or "").replace("\r\n", "\n").replace("\r", "\n")

chat_buffers = defaultdict(list)   # chat_id -> [text, text, ...]
chat_titles  = {}                  # chat_id -> title string (optional)

def append_to_buffer(chat_id: int, text: str):
    t = _normalize_text(text)
    if t:
        chat_buffers[chat_id].append(t)

def get_buffer_text(chat_id: int) -> str:
    parts = chat_buffers.get(chat_id, [])
    # រក្សា newline ដើម
    return ("\n".join(parts)) if parts else ""

def clear_session(chat_id: int):
    chat_buffers.pop(chat_id, None)
    chat_titles.pop(chat_id, None)

# =========================================================
# Handlers
# =========================================================

# /start — ចាប់ផ្តើមសម័យប្រមូល និងកំណត់ក្បាលអត្ថបទជាជម្រើស
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    clear_session(chat_id)

    title = ""
    if context.args:
        title = _normalize_text(" ".join(context.args))
        if title:
            chat_titles[chat_id] = title

    lines = [
        "✅ ចាប់ផ្តើមប្រមូលអត្ថបទ!",
        "• ផ្ញើអត្ថបទជាបន្តបន្ទាប់ (Telegram អាចបែកជាច្រើនសារ).",
        "• ពេលចប់ សរសេរ /done ដើម្បីបំលែងជា PDF មួយ (អតិបរមា 10MB).",
    ]
    if title:
        lines.insert(1, f"📌 ក្បាលអត្ថបទ: {title}")

    await update.message.reply_text("\n".join(lines))

# ប្រមូលសារ TEXT ទាំងអស់ចូល buffer រហូតដល់ /done
async def collect_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.text is None:
        return
    chat_id = update.effective_chat.id
    text = update.message.text

    # អនុញ្ញាតពាក្យបញ្ចប់ជាទម្រង់ text ធម្មតា
    if text.strip().lower() in {"done", "រួច", "រួចហើយ", "finish", "end"}:
        return await done_command(update, context)

    append_to_buffer(chat_id, text)
    await update.message.reply_text("🧩 បានទទួល! សរសេរ /done ពេលចប់។")

# /done — រួមអត្ថបទទាំងអស់ → PDF មួយ ហើយផ្ញើត្រឡប់ (មានពិនិត្យ 10MB)
async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = get_buffer_text(chat_id)
    title = chat_titles.get(chat_id, "").strip()

    if not user_text and not title:
        return await update.message.reply_text("⚠️ មិនមានអត្ថបទសម្រាប់បំលែងទេ។ ប្រើ /start ហើយផ្ញើអត្ថបទសិន។")

    try:
        # Build HTML: រក្សានៅជា block មួយ ដើម្បីមិនបែកជាបន្ទាត់ខ្លីៗ
        blocks = []
        if title:
            blocks.append(f"<h1>{title}</h1><hr>")
        blocks.append(f'<div class="content">{user_text}</div>')
        final_html = HTML_TEMPLATE.format(content="\n".join(blocks))

        # បង្កើត PDF ដោយប្រើ WeasyPrint
        pdf_buffer = BytesIO()
        HTML(string=final_html, base_url=".").write_pdf(pdf_buffer)
        pdf_buffer.seek(0)

        data = pdf_buffer.getvalue()
        pdf_size = len(data)

        # ពិនិត្យទំហំ 10MB
        if pdf_size > MAX_PDF_BYTES:
            mb = pdf_size / 1024 / 1024
            await update.message.reply_text(
                f"⚠️ PDF ធំពេក ({mb:.2f}MB). កំណត់អតិបរមា 10MB។\n"
                "សូមបំបែកអត្ថបទជាពីរផ្នែក ឬកាត់បន្ថយមាតិកា/រូបភាព មុន /done ម្តងទៀត។"
            )
            return

        # កំណត់ឈ្មោះ File
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"KHMER_PDF_{timestamp}.pdf"

        # ផ្ញើ PDF ត្រឡប់
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=data,          # ផ្ញើជា bytes ដើម្បីជៀសបញ្ហា pointer
            filename=filename,
        )

        await update.message.reply_text("📄 PDF រួច! ✅")
        logging.info("PDF sent: chat=%s size=%.2fMB", chat_id, pdf_size/1024/1024)
    except Exception as e:
        import traceback
        logging.error("បញ្ហាបង្កើត/ផ្ញើ PDF: %s\n%s", e, traceback.format_exc())
        await update.message.reply_text(f"❌ បរាជ័យក្នុងការបង្កើត/ផ្ញើ PDF: {e}")
    finally:
        clear_session(chat_id)

# --------------------- Application ---------------------
app = Application.builder().token(TOKEN).build()

# Add Handlers (សំខាន់៖ Command មុន text handler)
app.add_handler(CommandHandler("start", start_command))
app.add_handler(CommandHandler("done", done_command))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, collect_text))

# --------------------- Main Run ---------------------
if __name__ == "__main__":
    try:
        logging.info("🚀 កំពុងចាប់ផ្តើម PDF Khmer Bot ...")
        logging.info("✅ Ready (HTML→PDF via WeasyPrint), Max PDF: 10MB")
        app.run_polling()
    except Exception as e:
        logging.error("មិនអាចចាប់ផ្តើម Bot បានទេ: %s", e)
        raise
