import os
import logging
from io import BytesIO
from datetime import datetime

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from weasyprint import HTML

# --------------------- កំណត់ Logging ---------------------
logging.basicConfig(level=logging.INFO)

# --------------------- Variable បរិស្ថាន ---------------------
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("សូមកំណត់ BOT_TOKEN ជា environment variable មុនចាប់ផ្តើម។")

# --------------------- HTML Template (Khmer PDF) ---------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="km">
<head>
<meta charset="utf-8">
<style>
  @page { size: A4; margin: 0.4in 0.35in; }
  body { font-family: 'Khmer OS Battambang','Noto Sans Khmer','Noto Serif Khmer',sans-serif; font-size: 19px; line-height: 1.6; }
  /* សំខាន់៖ រក្សា newline/space ដើម */
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
# NEW: Session buffer សម្រាប់ប្រមូលអត្ថបទតាម chat
# =========================================================
from collections import defaultdict
def _normalize_text(s: str) -> str:
    # កុំ strip ដើម្បីកុំបាត់ space/newline ដែលអ្នកចង់រក្សា
    return (s or "").replace("\r\n", "\n").replace("\r", "\n")

chat_buffers = defaultdict(list)   # chat_id -> [text, text, ...]
chat_titles  = {}                  # chat_id -> title string (optional)

def append_to_buffer(chat_id: int, text: str):
    t = _normalize_text(text)
    if t:
        chat_buffers[chat_id].append(t)

def get_buffer_text(chat_id: int) -> str:
    parts = chat_buffers.get(chat_id, [])
    return ("\n".join(parts)) if parts else ""   # រក្សា newline ដើម

def clear_session(chat_id: int):
    chat_buffers.pop(chat_id, None)
    chat_titles.pop(chat_id, None)

# =========================================================
# Handlers ដើម/ថ្មី
# =========================================================

# NEW: /start — ចាប់ផ្តើមសម័យប្រមូល និងកំណត់ក្បាលអត្ថបទជាជម្រើស
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
        "• ពេលចប់ សរសេរ /done ដើម្បីបំលែងជា PDF មួយ។",
    ]
    if title:
        lines.insert(1, f"📌 ក្បាលអត្ថបទ: {title}")

    await update.message.reply_text("\n".join(lines))

# NEW: ប្រមូលសារ TEXT ទាំងអស់ចូល buffer រហូតដល់ /done
async def collect_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.text is None:
        return
    chat_id = update.effective_chat.id
    text = update.message.text

    # អនុញ្ញាតសញ្ញាបញ្ចប់ជាពាក្យធម្មតា (បើអ្នកវាយ "done"/"រួច")
    if text.strip().lower() in {"done", "រួច", "រួចហើយ", "finish", "end"}:
        return await done_command(update, context)

    append_to_buffer(chat_id, text)
    await update.message.reply_text("🧩 បានទទួល! សរសេរ /done ពេលចប់។")

# NEW: /done — រួមអត្ថបទទាំងអស់ → PDF មួយ ហើយផ្ញើត្រឡប់
async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = get_buffer_text(chat_id)
    title = chat_titles.get(chat_id, "").strip()

    if not user_text and not title:
        return await update.message.reply_text("⚠️ មិនមានអត្ថបទសម្រាប់បំលែងទេ។ ប្រើ /start ហើយផ្ញើអត្ថបទសិន។")

    try:
        # Build HTML តាមរចនាប័ទ្មដើម ប៉ុន្តែរក្សា newline ដើមដោយ pre-wrap
        blocks = []
        if title:
            blocks.append(f"<h1>{title}</h1><hr>")
        # មិនបំបែកជា <p> រាល់បន្ទាត់ទៀតទេ—ដាក់ជា block មួយ
        blocks.append(f'<div class="content">{user_text}</div>')

        final_html = HTML_TEMPLATE.format(content="\n".join(blocks))

        # បង្កើត PDF ដោយប្រើ WeasyPrint (logic ដើម)
        pdf_buffer = BytesIO()
        HTML(string=final_html, base_url=".").write_pdf(pdf_buffer)
        pdf_buffer.seek(0)

        # កំណត់ឈ្មោះ File
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"KHMER_PDF_{timestamp}.pdf"

        # ផ្ញើ PDF ត្រឡប់ (រក្សាទម្រង់ដើម)
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=filename,
            caption="✅ PDF រួមអត្ថបទទាំងអស់រួចរាល់!"
        )

        logging.info(f"PDF បង្កើតជោគជ័យសម្រាប់អ្នកប្រើ {update.effective_user.id}")
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logging.error(f"បង្កើត PDF បរាជ័យ: {str(e)}\n{error_details}")
        await update.message.reply_text(
            "❌ មានបញ្ហាក្នុងការបង្កើត PDF!\n"
            f"កំហុស: {str(e)}\n"
            "សូមព្យាយាមម្ដងទៀត ឬ បញ្ជូនអត្ថបទតិចជាង។"
        )
    finally:
        clear_session(chat_id)

# --------------------- Application ---------------------
app = Application.builder().token(TOKEN).build()

# Add Handlers
# សំខាន់៖ ដាក់ CommandHandler មុន text handler ដើម្បីកុំឲ្យ /done ត្រូវចាប់ដោយ text handler
app.add_handler(CommandHandler("start", start_command))
app.add_handler(CommandHandler("done", done_command))                      # NEW
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, collect_text))  # NEW

# --------------------- Main Run ---------------------
if __name__ == "__main__":
    try:
        logging.info("🚀 កំពុងចាប់ផ្តើម PDF Khmer Bot by TENG SAMBATH...")
        logging.info("✅ WeasyPrint PDF generation ready")
        logging.info("📐 Margins: Left/Right 0.35\", Top/Bottom 0.4\"")
        logging.info("📝 Font: 19px Khmer fonts")
        logging.info("🎯 Aggregation: /start → send texts → /done → single PDF")

        app.run_polling()
    except Exception as e:
        logging.error(f"មិនអាចចាប់ផ្តើម Bot បានទេ: {e}")
        raise
