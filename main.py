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

# --------------------- Environment Variable ---------------------
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("กรุณาตั้งค่า BOT_TOKEN เป็น environment variable ก่อนเริ่มการทำงาน")

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

# --------------------- Session Management ---------------------
SESSIONS_ACTIVE = set()
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
    chunks_sorted = sorted(chunks, key=lambda x: x[0])
    return "\n".join(c[1] for c in chunks_sorted)

def clear_session(chat_id: int):
    """ล้างข้อมูลเซสชันทั้งหมดสำหรับแชทที่กำหนด"""
    SESSIONS_ACTIVE.discard(chat_id)
    # >>>>> THE FINAL FIX IS HERE <<<<<
    # แก้ไขการพิมพ์ผิดจาก `cat_id` เป็น `chat_id` อย่างถูกต้องแล้ว
    chat_chunks.pop(chat_id, None)
    chat_titles.pop(chat_id, None)

# --------------------- Core PDF Generator Function ---------------------
async def generate_and_send_pdf(chat_id: int, html_content: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """สร้าง PDF จาก HTML, ตรวจสอบขนาด, และส่งให้ผู้ใช้"""
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)

        pdf_buffer = BytesIO()
        HTML(string=html_content, base_url=".").write_pdf(pdf_buffer)

        TELEGRAM_LIMIT_BYTES = 50 * 1024 * 1024
        if pdf_buffer.tell() >= TELEGRAM_LIMIT_BYTES:
            size_mb = pdf_buffer.tell() / (1024 * 1024)
            logger.warning(f"PDF size ({size_mb:.2f}MB) exceeds limit for chat {chat_id}")
            await update.message.reply_text(
                f"❌ **ไฟล์ PDF มีขนาดใหญ่เกินไป ({size_mb:.2f} MB)!**\n\nขีดจำกัดของ Telegram คือ 50 MB"
            )
            return

        pdf_buffer.seek(0)
        filename = f"KHMER_PDF_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        await update.message.reply_document(
            document=InputFile(pdf_buffer, filename=filename),
            caption="✅ **ไฟล์ PDF ของคุณพร้อมแล้ว!**"
        )
        logger.info("PDF sent successfully to chat %s", chat_id)

    except Exception:
        logger.error("Generate/Send PDF failed for chat %s:\n%s", chat_id, traceback.format_exc())
        await update.message.reply_text("❌ เกิดปัญหาในการสร้าง/ส่ง PDF! กรุณาลองใหม่อีกครั้ง")

# --------------------- Telegram Handlers ---------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """เริ่มเซสชันใหม่เพื่อรวบรวมข้อความหลายข้อความ"""
    chat_id = update.effective_chat.id
    clear_session(chat_id)
    SESSIONS_ACTIVE.add(chat_id)

    title = _normalize_text(" ".join(context.args)) if context.args else ""
    if title:
        chat_titles[chat_id] = title

    lines = [
        "✅ **เริ่มการรวบรวมข้อความ!**",
        "• ส่งข้อความมาอย่างต่อเนื่อง",
        "• เมื่อเสร็จแล้ว พิมพ์ /done เพื่อแปลงเป็น PDF ไฟล์เดียว"
    ]
    if title:
        lines.insert(1, f"📌 **หัวข้อ:** {html.escape(title)}")
    await update.message.reply_text("\n".join(lines))

async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """สิ้นสุดเซสชัน, รวมข้อความทั้งหมด, และสร้าง PDF"""
    chat_id = update.effective_chat.id
    if chat_id not in SESSIONS_ACTIVE:
        await update.message.reply_text("⚠️ ไม่มีเซสชันการรวบรวมที่กำลังทำงานอยู่ กรุณาใช้ /start ก่อน")
        return

    merged_text = get_merged_text(chat_id)
    title = (chat_titles.get(chat_id) or "").strip()

    if not merged_text and not title:
        await update.message.reply_text("⚠️ ยังไม่มีข้อความสำหรับแปลง")
        return

    blocks = []
    if title:
        blocks.append(f"<h1>{html.escape(title)}</h1><hr>")
    blocks.append(f'<div class="content">{html.escape(merged_text)}</div>')
    final_html = HTML_TEMPLATE.format(content="\n".join(blocks))

    await generate_and_send_pdf(chat_id, final_html, update, context)
    clear_session(chat_id)

async def session_text_collector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """รวบรวมข้อความระหว่างเซสชันที่ทำงานอยู่"""
    chat_id = update.effective_chat.id
    text = update.message.text

    if text.strip().lower() in {"done", "រួច", "រួចហើយ", "finish", "end"}:
        return await done_command(update, context)

    append_chunk(chat_id, text)
    total = len(chat_chunks[chat_id])
    await update.message.reply_text(f"🧩 ได้รับแล้ว ({total})! พิมพ์ /done เมื่อเสร็จสิ้น")

async def single_text_converter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """แปลงข้อความเดียวเป็น PDF โดยตรงเมื่อไม่มีเซสชันทำงานอยู่"""
    chat_id = update.effective_chat.id
    text = _normalize_text(update.message.text)
    
    content = f'<div class="content">{html.escape(text)}</div>'
    final_html = HTML_TEMPLATE.format(content=content)
    await generate_and_send_pdf(chat_id, final_html, update, context)
    
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Error handler ส่วนกลางเพื่อบันทึกข้อผิดพลาดและแจ้งเตือนผู้ใช้"""
    logger.error("Exception while handling an update:", exc_info=context.error)
    tb_string = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))
    logger.error(f"Traceback:\n{tb_string}")

    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "❌ ขออภัย เกิดข้อผิดพลาดทางเทคนิค กรุณาลองใหม่อีกครั้ง"
        )

# --------------------- Application Setup ---------------------
def main():
    """เริ่มการทำงานของบอท"""
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("done", done_command))

    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Chat(chat_id=SESSIONS_ACTIVE),
        session_text_collector
    ))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        single_text_converter
    ))
    
    app.add_error_handler(error_handler)

    logger.info("Bot is starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
