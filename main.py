import os
import logging
from io import BytesIO
from datetime import datetime

from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from weasyprint import HTML

# កំណត់ Logging
logging.basicConfig(level=logging.INFO)

# Variable បរិស្ថាន
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("សូមកំណត់ BOT_TOKEN ជា environment variable មុនចាប់ផ្តើម។")

# HTML Template (Khmer PDF)
# សំខាន់: ប្រើ white-space: pre-wrap ដើម្បីរក្សា newline/space ដើម
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

# ---------------------- ថែម: Session Buffer ----------------------
from collections import defaultdict

def _normalize_text(s: str) -> str:
    # កុំ strip ដើម្បីរក្សា space/newlines ដើម
    return (s or "").replace("\r\n", "\n").replace("\r", "\n")

chat_buffers = defaultdict(list)   # chat_id -> [text, text, ...]
chat_titles  = {}                  # chat_id -> title string (optional)

def append_to_buffer(chat_id: int, text: str):
    t = _normalize_text(text)
    if t:
        chat_buffers[chat_id].append(t)

def get_buffer_text(chat_id: int) -> str:
    parts = chat_buffers.get(chat_id, [])
    return "\n".join(parts) if parts else ""

def clear_session(chat_id: int):
    chat_buffers.pop(chat_id, None)
    chat_titles.pop(chat_id, None)

# ---------------------- កូដដើម (convert_text_to_pdf) ----------------------
# សូមរក្សាទំរង់ function ដើមរបស់អ្នក ប្រសិនបើមាននៅក្នុងឯកសារពេញ
# ខាងក្រោមនេះគឺ handler ដើមតាមដែលអ្នកបានផ្ដល់ (សម្រាប់ single-message → PDF)
async def convert_text_to_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message or update.message.text is None:
            return

        user_text = update.message.text

        # ប្រើទម្រង់ “ប្លុកតែមួយ” ដើម្បីកុំឲ្យបែកជាបន្ទាត់ខ្លីៗ
        blocks = [f'<div class="content">{_normalize_text(user_text)}</div>']
        final_html = HTML_TEMPLATE.format(content="\n".join(blocks))

        # បង្កើត PDF ដោយប្រើ WeasyPrint
        pdf_buffer = BytesIO()
        HTML(string=final_html, base_url=".").write_pdf(pdf_buffer)
        pdf_buffer.seek(0)

        # កំណត់ឈ្មោះ File
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"KHMER_PDF_{timestamp}.pdf"

        # ផ្ញើ PDF ត្រឡប់ (No size limit in code; ផ្ញើជា InputFile ដើម្បីជៀស size error)
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=InputFile(pdf_buffer, filename=filename),
            caption="✅ **សូមអបអរ អត្ថបទរបស់អ្នករួចរាល់!**\n\n"
                    "• សូមរីករាយ! ក្នុងការប្រើប្រាស់ ៖ https://t.me/ts_4699"
        )

        logging.info(f"PDF បង្កើតជោគជ័យសម្រាប់អ្នកប្រើ {update.effective_user.id}")
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logging.error(f"បង្កើត PDF បរាជ័យ: {str(e)}\n{error_details}")
        await update.message.reply_text(
            "❌ **មានបញ្ហាក្នុងការបង្កើត PDF!**\n\n"
            f"**កំហុស:** {str(e)}\n\n"
            "🔄 សូមព្យាយាមម្ដងទៀត ឬ ផ្ញើអត្ថបទខ្លីជាមុន\n"
            "💡 ប្រសិនបើបញ្ហានៅតែកើត សូមទំនាក់ទំនងមកកាន់ខ្ញ\n\n"
            "👨💻 **ជំនួយ: TENG SAMBATH**"
        )

# ---------------------- ថែម: /start និង /done ----------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start [optional title]
    ចាប់ផ្តើមសម័យប្រមូលអត្ថបទ (សម្រាប់ many-messages → single PDF)
    """
    chat_id = update.effective_chat.id
    clear_session(chat_id)

    # ប្រសិនបើមាន args បន្ទាប់ពី /start នឹងយកជាក្បាលអត្ថបទ
    if context.args:
        title = _normalize_text(" ".join(context.args))
        if title:
            chat_titles[chat_id] = title

    lines = [
        "✅ ចាប់ផ្តើមប្រមូលអត្ថបទ!",
        "• ផ្ញើអត្ថបទជាបន្តបន្ទាប់ (Telegram អាចបែកជាច្រើនសារ).",
        "• ពេលចប់ សរសេរ /done ដើម្បីបំលែងជា PDF មួយ (គ្មានកំណត់ទំហំក្នុងកូដ).",
    ]
    if chat_titles.get(chat_id):
        lines.insert(1, f"📌 ក្បាលអត្ថបទ: {chat_titles[chat_id]}")

    await update.message.reply_text("\n".join(lines))

async def collect_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ប្រមូលសារ TEXT ទាំងអស់ចូល buffer រហូតដល់ /done
    """
    if not update.message or update.message.text is None:
        return
    chat_id = update.effective_chat.id
    text = update.message.text

    # ប្រសិនបើអ្នកវាយ "done/រួច/finish/end" ជា text ធម្មតា ក៏អាចបញ្ចប់បាន
    if text.strip().lower() in {"done", "រួច", "រួចហើយ", "finish", "end"}:
        return await done_command(update, context)

    append_to_buffer(chat_id, text)
    await update.message.reply_text("🧩 បានទទួល! សរសេរ /done ពេលរួច។")

async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    រួមអត្ថបទដែលបានប្រមូល → បង្កើត PDF មួយ និងផ្ញើត្រឡប់
    (No limit size PDF in code)
    """
    chat_id = update.effective_chat.id
    full_text = get_buffer_text(chat_id)
    title = chat_titles.get(chat_id, "").strip()

    if not full_text and not title:
        return await update.message.reply_text("⚠️ មិនទាន់មានអត្ថបទសម្រាប់បំលែងទេ។ ប្រើ /start ហើយផ្ញើអត្ថបទ។")

    try:
        blocks = []
        if title:
            blocks.append(f"<h1>{title}</h1><hr>")
        blocks.append(f'<div class="content">{full_text}</div>')

        final_html = HTML_TEMPLATE.format(content="\n".join(blocks))

        # បង្កើត PDF ដោយប្រើ WeasyPrint
        pdf_buffer = BytesIO()
        HTML(string=final_html, base_url=".").write_pdf(pdf_buffer)
        pdf_buffer.seek(0)

        # កំណត់ឈ្មោះ File
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"KHMER_PDF_{timestamp}.pdf"

        # ផ្ញើជា InputFile (ជៀសបញ្ហា pointer/size)
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=InputFile(pdf_buffer, filename=filename)
        )

        await update.message.reply_text("📄 PDF រួច! ✅")
    except Exception as e:
        import traceback
        logging.error("បញ្ហាបង្កើត/ផ្ញើ PDF: %s\n%s", e, traceback.format_exc())
        await update.message.reply_text(f"❌ បញ្ហាបង្កើត/ផ្ញើ PDF: {e}")
    finally:
        clear_session(chat_id)

# ---------------------- App/Handlers ----------------------
app = Application.builder().token(TOKEN).build()

# Add Handlers ដើម
app.add_handler(CommandHandler("start", start_command))                                # ថែម
app.add_handler(CommandHandler("done", done_command))                                  # ថែម
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, collect_text))         # ថែម (ប្រមូល)
# រក្សាដើម: handler ដើមបំលែងភ្លាមៗ សម្រាប់ករណីអ្នកចង់ប្រើ message តែមួយ
# ប្រសិនបើមិនចង់ឲ្យបញ្ចូលគ្នា អាចដាក់កម្រិត path/condition ផ្សេង
# ទុកនៅចុងក្រោយ ដើម្បីកុំឲ្យទប់ស្កាត់ /start /done
app.add_handler(MessageHandler(filters.COMMAND == False, convert_text_to_pdf))

# Main Run
if __name__ == "__main__":
    try:
        logging.info("🚀 កំពុងចាប់ផ្តើម PDF Khmer Bot by TENG SAMBATH...")
        logging.info("✅ WeasyPrint PDF generation ready (No limit size in code)")
        logging.info("📐 Margins: Left/Right 0.35\", Top/Bottom 0.4\"")
        logging.info("📝 Font: 19px Khmer fonts")
        logging.info("🎯 Modes: single-message → PDF, or /start…/done → single PDF")

        app.run_polling()
    except Exception as e:
        logging.error(f"មិនអាចចាប់ផ្តើម Bot បានទេ: {e}")
        raise
