import json
import logging
import asyncio
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import threading

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
)
from scrapper import get_attendance_report
from model import init_db, save_user, get_user

# Comprehensive MarkdownV2 escaping dictionary
MARKDOWN_ESCAPE_TABLE = str.maketrans({
    '_': '\\_', '*': '\\*', '[': '\\[', ']': '\\]',
    '(': '\\(', ')': '\\)', '~': '\\~', '`': '\\`',
    '>': '\\>', '#': '\\#', '+': '\\+', '-': '\\-',
    '=': '\\=', '|': '\\|', '{': '\\{', '}': '\\}',
    '.': '\\.', '!': '\\!', '%': '\\%'
})

# Thread pool for blocking operations
executor = ThreadPoolExecutor(max_workers=3)

@lru_cache(maxsize=32)
def format_report_for_markdown(report: str) -> str:
    # Legacy function; we'll use format_report instead
    sections = report.split("\n\n")
    formatted = []
    for section in sections:
        if "Hi " in section:
            formatted.append(f"*{section.replace('Hi ', '')}*")
        elif "Total:" in section:
            p = section.split()
            n = p[1].split("/")
            formatted.append(f"*{p[0]}: {n[0]}/{n[1]} ({p[2]})*")
        elif "Today's Attendance:" in section:
            lines = [line for line in section.split("\n") if ":" in line]
            attendance = [f"• {s}: {st}" for s, st in (line.split(':', 1) for line in lines[1:]) if st.strip() in ["P", "A"]]
            if attendance:
                formatted.append(f"{lines[0]}\n" + "\n".join(attendance))
            else:
                formatted.append(lines[0])
        elif "You can skip" in section:
            formatted.append(f"*{section}*")
        elif "Subject-wise Attendance:" in section:
            lines = section.split("\n")
            subjects = []
            for line in lines[1:]:
                if not line.strip():
                    continue
                parts = line.replace("..", " ").split()
                if len(parts) < 2:
                    continue
                i = next((i for i, p in enumerate(parts) if "/" in p), None)
                if i is None:
                    continue
                subject = " ".join(parts[:i])
                attendance = parts[i]
                percentage = parts[i+1] if i+1 < len(parts) else ""
                subjects.append(f"{subject:<20} *{attendance}* {percentage}")
            formatted.append(f"{lines[0]}\n" + "\n".join(subjects))
    return "\n\n".join(formatted)

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = "Add your token here"
bot_app = Application.builder().token(TELEGRAM_TOKEN).build()

init_db()

# Use an asyncio.Queue for attendance requests
request_queue = asyncio.Queue()

# -------------------------------
# Telegram Command and Message Handlers
# -------------------------------
async def start(update: Update, context: CallbackContext):
    msg = (
        "👋 *Welcome to Attendance Bot\\!*\n\n"
        "1️⃣ Set up permanent access:\n"
        "`/set username password keyword`\n\n"
        "2️⃣ One\\-time check:\n"
        "`/check username password`\n\n"
        "3️⃣ Quick access:\n"
        "Send your saved keyword"
    )
    await update.message.reply_text(msg, parse_mode="MarkdownV2")

async def set_credentials(update: Update, context: CallbackContext):
    if len(context.args) != 3:
        await update.message.reply_text(
            "❌ *Invalid Format*\nUse: `/set username password keyword`", 
            parse_mode="MarkdownV2"
        )
        return
    username, password, keyword = context.args
    user_id = str(update.effective_user.id)
    save_user(user_id, username, password, keyword.lower())
    # Escape the exclamation mark by adding a backslash
    await update.message.reply_text(
        f"✅ Account Setup Successful\\! Your keyword: `{keyword}`", 
        parse_mode="MarkdownV2"
    )
    logger.info(f"Saved credentials for user {user_id}")
   
async def check_attendance(update: Update, context: CallbackContext):
    if len(context.args) != 2:
        await update.message.reply_text(
            "❌ *Invalid Format*\n\nUse: `/check username password`", 
            parse_mode="MarkdownV2"
        )
        return
        
    status_msg = await update.message.reply_text(
        "🔄 *Checking Attendance\\.\\.\\.\\.*", 
        parse_mode="MarkdownV2"
    )
    
    try:
        future = asyncio.get_running_loop().create_future()
        await request_queue.put((context.args[0], context.args[1], future))
        report_json = await future
        report = json.loads(report_json)
        
        if "error" in report:
            error_msg = report["error"].translate(MARKDOWN_ESCAPE_TABLE)
            await status_msg.edit_text(
                f"❌ *Error*\n\n_{error_msg}_",
                parse_mode="MarkdownV2"
            )
            return
            
        # Format and escape the report
        formatted_report = format_report(report)
        
        await status_msg.edit_text(
            formatted_report,
            parse_mode="MarkdownV2"
        )
    except Exception as e:
        logger.error(f"Error in check_attendance: {e}")
        await status_msg.edit_text(
            "❌ *Error*\n\n_An unexpected error occurred\\. Please try again\\._",
            parse_mode="MarkdownV2"
        )

def format_report(report: dict) -> str:
    """Format attendance report with proper MarkdownV2 escaping"""
    formatted = [
        "📊 *Attendance Report*\n",
        f"👋 Roll Number: {report['student_id'].translate(MARKDOWN_ESCAPE_TABLE)}"
    ]
    
    overall_percentage = report['overall_percentage']
    status_icon = "✅" if overall_percentage >= 75 else "❌"
    total_text = f"{report['total_present']}/{report['total_classes']} ({overall_percentage:.2f}%) {status_icon}"
    formatted.append(f"📊 Total: {total_text.translate(MARKDOWN_ESCAPE_TABLE)}")
    
    if 'skippable_hours' in report:
        formatted.append(f"⏱ You can skip {str(report['skippable_hours']).translate(MARKDOWN_ESCAPE_TABLE)} hours and still maintain above 75%")
    elif 'required_hours' in report:
        formatted.append(f"⏱ You need to attend {str(report['required_hours']).translate(MARKDOWN_ESCAPE_TABLE)} hours to maintain above 75%")
    
    if report.get('todays_attendance'):
        formatted.append("🕒 *Today's Attendance:*")
        formatted.extend(f"• {line.translate(MARKDOWN_ESCAPE_TABLE)}" for line in report['todays_attendance'])
    else:
        formatted.append("🕒 No Today's Attendance")
    
    if report.get('subject_attendance'):
        formatted.append("📚 *Subject\\-wise Attendance:*")
        formatted.extend(f"• {line.translate(MARKDOWN_ESCAPE_TABLE)}" for line in report['subject_attendance'])
    
    return "\n\n".join(formatted)

async def handle_message(update: Update, context: CallbackContext):
    user = get_user(str(update.effective_user.id))
    if user and update.message.text.lower() == user[3]:
        status_msg = await update.message.reply_text("🔄 *Fetching\\.\\.\\.*", parse_mode="MarkdownV2")
        try:
            future = asyncio.get_running_loop().create_future()
            await request_queue.put((user[1], user[2], future))
            report_json = await future
            report = json.loads(report_json)
            
            if "error" in report:
                error_msg = report["error"].translate(MARKDOWN_ESCAPE_TABLE)
                await status_msg.edit_text(
                    f"❌ *Error*\n\n_{error_msg}_",
                    parse_mode="MarkdownV2"
                )
                return

            formatted_report = format_report(report)
            
            await status_msg.edit_text(
                formatted_report,
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            logger.error(f"Error in handle_message: {e}")
            await status_msg.edit_text(
                "❌ *Error*\n\n_An unexpected error occurred\\. Please try again\\._",
                parse_mode="MarkdownV2"
            )

# -------------------------------
# Background task to process queued requests
# -------------------------------
async def process_queue():
    while True:
        username, password, future = await request_queue.get()
        try:
            # Await the async get_attendance_report directly
            report = await get_attendance_report(username, password)
            # If report is not a string, convert it to a JSON string
            if not isinstance(report, str):
                report = json.dumps(report)
            future.set_result(report)
        except Exception as e:
            logger.error(f"Error processing queue: {e}")
            future.set_exception(e)
        finally:
            request_queue.task_done()

# -------------------------------
# Create FastAPI app with endpoints
# -------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI"""
    # Startup
    logger.info("Registering Telegram handlers...")
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("set", set_credentials))
    bot_app.add_handler(CommandHandler("check", check_attendance))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Initializing Telegram bot...")
    await bot_app.initialize()
    logger.info("Starting Telegram bot...")
    await bot_app.start()
    logger.info("Running bot polling in background...")
    
    # Start bot polling in a separate thread
    stop_polling = threading.Event()
    
    def run_polling():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(bot_app.updater.start_polling(allowed_updates=Update.ALL_TYPES))
            while not stop_polling.is_set():
                loop.run_until_complete(asyncio.sleep(1))
        except Exception as e:
            logger.error(f"Polling error: {e}")
        finally:
            loop.run_until_complete(bot_app.updater.stop())
            loop.close()
    
    polling_thread = threading.Thread(target=run_polling, daemon=True)
    polling_thread.start()
    
    # Start queue processor
    queue_task = asyncio.create_task(process_queue())
    
    try:
        yield
    finally:
        # Shutdown
        logger.info("Shutting down...")
        stop_polling.set()
        polling_thread.join(timeout=5)
        queue_task.cancel()
        try:
            await asyncio.gather(
                bot_app.stop(),
                bot_app.shutdown(),
                return_exceptions=True
            )
        except Exception as e:
            logger.error(f"Shutdown error: {e}")

def create_fastapi_app() -> FastAPI:
    app_api = FastAPI(lifespan=lifespan)
    
    @app_api.get("/")
    async def index():
        bot_info = await bot_app.bot.get_me()
        return JSONResponse({"status": "online", "bot": bot_info.username})
    
    @app_api.post("/attendance")
    async def attendance_route(request: Request):
        data = await request.json()
        username, password = data.get("username"), data.get("password")
        if not username or not password:
            return JSONResponse({"error": "Missing username or password"}, status_code=400)
        future = asyncio.get_running_loop().create_future()
        await request_queue.put((username, password, future))
        result = await future
        return JSONResponse(json.loads(result))
    
    return app_api

# -------------------------------
# Main entry point
# -------------------------------
if __name__ == "__main__":
    app_api = create_fastapi_app()
    uvicorn.run(app_api, host="0.0.0.0", port=5000, log_level="info")