import os
import re
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)

BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)

env_file = BASE_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
DATA_DIR = BASE_DIR / os.getenv("DRAWINGS_DIR", "drawings")
DB_PATH = BASE_DIR / os.getenv("DATABASE_PATH", "drawings.db")
DATA_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("structural-drawing-bot")

FLOOR, ELEMENT, ZONE, TITLE, FILE = range(5)
FLOORS = ["B3", "B2", "B1", "Ground", "Mezzanine", "P1", "P2", "P3", "Typical Floor", "Roof", "Other"]
ELEMENTS = [
    "Slab", "Beam", "Column", "Shear Wall", "Drop Panel", "Stairs",
    "Ramp", "Raft/Foundation", "Retaining Wall", "General Notes", "Other"
]
MAIN_MENU = ReplyKeyboardMarkup(
    [["📤 رفع مخطط", "🔎 بحث"], ["🏢 الطوابق", "📚 كل الملفات"], ["ℹ️ مساعدة"]],
    resize_keyboard=True
)

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("""
    CREATE TABLE IF NOT EXISTS drawings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_name TEXT NOT NULL,
        stored_name TEXT NOT NULL UNIQUE,
        floor TEXT NOT NULL,
        element TEXT NOT NULL,
        zone TEXT DEFAULT '',
        title TEXT DEFAULT '',
        file_type TEXT NOT NULL,
        uploaded_by INTEGER,
        uploaded_at TEXT NOT NULL
    )""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_floor_element ON drawings(floor, element)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_title ON drawings(title)")
    con.commit()
    return con

def safe_name(name):
    name = Path(name).name
    cleaned = "".join(c if c.isalnum() or c in "._- " else "_" for c in name)
    return cleaned.strip().replace(" ", "_")[:130] or "drawing"

def chunks(items, n=2):
    return [items[i:i+n] for i in range(0, len(items), n)]

def inline_menu(items, prefix):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(item, callback_data=f"{prefix}:{item}") for item in row]
        for row in chunks(items, 2)
    ])

def floor_keyboard():
    return inline_menu(FLOORS, "floor")

def element_keyboard(floor):
    buttons = []
    for row in chunks(ELEMENTS, 2):
        buttons.append([InlineKeyboardButton(x, callback_data=f"element:{floor}:{x}") for x in row])
    buttons.append([InlineKeyboardButton("📄 كل عناصر هذا الطابق", callback_data=f"allfloor:{floor}")])
    return InlineKeyboardMarkup(buttons)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً بك في مكتبة المخططات الإنشائية للمشروع.\n\n"
        "رتّب ملفات كل طابق واربطها بالعنصر والزون ورقم اللوحة. "
        "البوت يحتفظ بالملفات الأصلية PDF وDWG ولا يحوّلها أو يعدّلها.",
        reply_markup=MAIN_MENU
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "طريقة الاستخدام:\n"
        "• 📤 رفع مخطط: اختَر الطابق والعنصر، ثم أرسل PDF أو DWG كمستند.\n"
        "• 🏢 الطوابق: تصفّح طابقاً ثم اختَر العنصر.\n"
        "• 🔎 بحث: ابحث باسم الملف أو رقم اللوحة أو الزون أو العنصر.\n"
        "• 📚 كل الملفات: عرض أحدث الملفات.\n\n"
        "أوامر: /start /add /search /floors /files /cancel\n"
        "الملفات محفوظة على جهاز/سيرفر التشغيل؛ انسخ مجلدي drawings وملف drawings.db احتياطياً.",
        reply_markup=MAIN_MENU
    )

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("📤 رفع مخطط جديد — اختَر الطابق:", reply_markup=ReplyKeyboardMarkup([["إلغاء"]], resize_keyboard=True))
    await update.message.reply_text("قائمة الطوابق:", reply_markup=MAIN_MENU)
    await update.message.reply_text("اختَر الطابق من الأزرار:", reply_markup=ReplyKeyboardMarkup(chunks(FLOORS, 2) + [["إلغاء"]], resize_keyboard=True, one_time_keyboard=True))
    return FLOOR

async def pick_floor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if value == "إلغاء":
        return await cancel(update, context)
    if value not in FLOORS:
        await update.message.reply_text("اختَر طابقاً من القائمة أو اضغط إلغاء.")
        return FLOOR
    context.user_data["floor"] = value
    await update.message.reply_text("اختَر العنصر الإنشائي:", reply_markup=ReplyKeyboardMarkup(chunks(ELEMENTS, 2) + [["إلغاء"]], resize_keyboard=True, one_time_keyboard=True))
    return ELEMENT

async def pick_element(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if value == "إلغاء":
        return await cancel(update, context)
    if value not in ELEMENTS:
        await update.message.reply_text("اختَر عنصراً من القائمة أو اضغط إلغاء.")
        return ELEMENT
    context.user_data["element"] = value
    await update.message.reply_text("اكتب الزون أو المحاور (مثال ZONE-2 أو Grid A-F)، أو اكتب - إذا لا ينطبق:")
    return ZONE

async def pick_zone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if value == "إلغاء":
        return await cancel(update, context)
    context.user_data["zone"] = "" if value == "-" else value[:100]
    await update.message.reply_text("اكتب رقم اللوحة أو وصفاً مختصراً (مثال B2-BEAM-SD-012)، أو اكتب -:")
    return TITLE

async def pick_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if value == "إلغاء":
        return await cancel(update, context)
    context.user_data["title"] = "" if value == "-" else value[:180]
    await update.message.reply_text("أرسل ملف PDF أو DWG كمستند Document. الملف الأصلي سيُحفظ كما هو.")
    return FILE

async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text and update.message.text.strip() == "إلغاء":
        return await cancel(update, context)
    doc = update.message.document
    if not doc:
        await update.message.reply_text("أرسل ملف PDF أو DWG باستخدام 📎 ثم Document، وليس كصورة.")
        return FILE
    original = doc.file_name or "drawing"
    ext = Path(original).suffix.lower()
    if ext not in (".pdf", ".dwg"):
        await update.message.reply_text("الامتدادات المقبولة في هذه النسخة: .pdf و.dwg. أعد إرسال الملف.")
        return FILE
    try:
        tg_file = await context.bot.get_file(doc.file_id)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        stored = f"{stamp}_{update.effective_user.id}_{safe_name(original)}"
        target = DATA_DIR / stored
        await tg_file.download_to_drive(custom_path=str(target))
        con = db()
        con.execute("""INSERT INTO drawings
        (original_name, stored_name, floor, element, zone, title, file_type, uploaded_by, uploaded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (original, stored, context.user_data["floor"], context.user_data["element"],
         context.user_data.get("zone", ""), context.user_data.get("title", ""),
         ext[1:], update.effective_user.id, datetime.now().isoformat(timespec="seconds")))
        con.commit()
        con.close()
        await update.message.reply_text(
            "✅ أُضيف المخطط بنجاح مع الاحتفاظ بالملف الأصلي.\n\n"
            f"الطابق: {context.user_data['floor']}\nالعنصر: {context.user_data['element']}\n"
            f"الزون/المحاور: {context.user_data.get('zone') or '—'}\n"
            f"رقم اللوحة/الوصف: {context.user_data.get('title') or '—'}\n"
            f"الملف: {original}",
            reply_markup=MAIN_MENU
        )
    except Exception:
        log.exception("Upload failed")
        await update.message.reply_text("تعذّر حفظ الملف. تحقّق من مساحة القرص وحدود حجم الملف وصلاحيات المجلد.", reply_markup=MAIN_MENU)
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("تم إلغاء العملية.", reply_markup=MAIN_MENU)
    return ConversationHandler.END

async def search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["searching"] = True
    await update.message.reply_text("اكتب رقم اللوحة أو الطابق أو العنصر أو الزون أو جزءاً من اسم الملف:", reply_markup=MAIN_MENU)

async def send_rows(message, rows):
    if not rows:
        await message.reply_text("ماكو نتائج مطابقة. جرّب كلمة أقصر أو رقم اللوحة.")
        return
    for row in rows:
        path = DATA_DIR / row["stored_name"]
        caption = (f"📐 {row['original_name']}\nالطابق: {row['floor']} | العنصر: {row['element']}\n"
                   f"الزون/المحاور: {row['zone'] or '—'}\nرقم اللوحة/الوصف: {row['title'] or '—'}\n"
                   f"النوع: {row['file_type'].upper()} | أُضيف: {row['uploaded_at'][:16]}")
        try:
            with open(path, "rb") as f:
                await message.reply_document(document=f, filename=row["original_name"], caption=caption[:1000])
        except FileNotFoundError:
            await message.reply_text(caption + "\n⚠️ سجل الفهرس موجود لكن الملف غير موجود على القرص.")

async def do_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    if q in ("🔎 بحث", "بحث"):
        return await search_start(update, context)
    if context.user_data.pop("searching", False):
        like = f"%{q}%"
        con = db()
        rows = con.execute("""SELECT * FROM drawings WHERE original_name LIKE ? OR floor LIKE ?
            OR element LIKE ? OR zone LIKE ? OR title LIKE ? ORDER BY floor, element, title LIMIT 30""",
            (like, like, like, like, like)).fetchall()
        con.close()
        await send_rows(update.message, rows)
        await update.message.reply_text("انتهى البحث.", reply_markup=MAIN_MENU)
        return
    if q == "📤 رفع مخطط":
        return await add_start(update, context)
    if q == "🏢 الطوابق":
        return await floors(update, context)
    if q == "📚 كل الملفات":
        return await list_files(update, context)
    if q == "ℹ️ مساعدة":
        return await help_cmd(update, context)

async def floors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("اختَر الطابق للتصفح:", reply_markup=floor_keyboard())

async def floor_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("floor:"):
        floor = data.split(":", 1)[1]
        await query.message.reply_text(f"الطابق المحدد: {floor}\nاختَر العنصر:", reply_markup=element_keyboard(floor))
    elif data.startswith("element:"):
        _, floor, element = data.split(":", 2)
        con = db()
        rows = con.execute("SELECT * FROM drawings WHERE floor=? AND element=? ORDER BY title, original_name LIMIT 30", (floor, element)).fetchall()
        con.close()
        await query.message.reply_text(f"نتائج {floor} — {element}:")
        await send_rows(query.message, rows)
    elif data.startswith("allfloor:"):
        floor = data.split(":", 1)[1]
        con = db()
        rows = con.execute("SELECT * FROM drawings WHERE floor=? ORDER BY element, title LIMIT 40", (floor,)).fetchall()
        con.close()
        await query.message.reply_text(f"كل ملفات الطابق {floor}:")
        await send_rows(query.message, rows)

async def list_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    con = db()
    rows = con.execute("SELECT * FROM drawings ORDER BY uploaded_at DESC LIMIT 20").fetchall()
    con.close()
    await update.message.reply_text("أحدث الملفات في المكتبة:")
    await send_rows(update.message, rows)
    await update.message.reply_text("انتهت القائمة.", reply_markup=MAIN_MENU)

async def post_init(app):
    db()
    log.info("Database ready")

def main():
    if not BOT_TOKEN:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN environment variable before running.")
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("add", add_start), MessageHandler(filters.Regex("^📤 رفع مخطط$"), add_start)],
        states={
            FLOOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, pick_floor)],
            ELEMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, pick_element)],
            ZONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, pick_zone)],
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, pick_title)],
            FILE: [MessageHandler(filters.Document.ALL, receive_file), MessageHandler(filters.TEXT & ~filters.COMMAND, receive_file)]
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("^إلغاء$"), cancel)],
        allow_reentry=True
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("add", add_start))
    app.add_handler(CommandHandler("search", search_start))
    app.add_handler(CommandHandler("floors", floors))
    app.add_handler(CommandHandler("files", list_files))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(floor_callback, pattern=r"^(floor|element|allfloor):"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, do_search))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
