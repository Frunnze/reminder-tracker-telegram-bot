from telegram import (
    Update, ReplyKeyboardMarkup, 
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
    MessageHandler, filters, CallbackQueryHandler
)
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import io
import requests


load_dotenv()
consecutive = 0


MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["Start work", "Stop work"], 
        ["Start break"], 
        ["Common stats"], 
        ["Work done today"]
    ],
    one_time_keyboard=True,
    resize_keyboard=True
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends explanation on how to use the bot."""
    await update.message.reply_text(
        "Hi!",
        reply_markup=MAIN_KEYBOARD
    )


async def alarm(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the alarm message."""
    job = context.job
    chat_id = job.chat_id

    await context.bot.send_message(
        chat_id, 
        text=f"Beep! {job.data} seconds are over!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Stop alarm", callback_data="stop_alarm")]
        ])
    )
    
    # Schedule re-alarm 
    remove_job_if_exists(str(chat_id), context)
    context.job_queue.run_once(alarm, 10, chat_id=chat_id, name=str(chat_id), data=10)


def remove_job_if_exists(name: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True


async def unset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove the job if the user changed their mind."""
    chat_id = update.message.chat_id
    job_removed = remove_job_if_exists(str(chat_id), context)
    text = "Timer successfully cancelled!" if job_removed else "You have no active timer."
    await update.message.reply_text(text)


async def handle_start_work(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        text="Select a duration:", 
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("50 minutes", callback_data="50minutes"), 
                InlineKeyboardButton("90 minutes", callback_data="90minutes")
            ]
        ])
    )


async def handle_start_break(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        text="Select break duration:", 
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("20 minutes", callback_data="20minutes"), 
                InlineKeyboardButton("15 minutes", callback_data="15minutes"),
                InlineKeyboardButton("10 minutes", callback_data="10minutes"),
                InlineKeyboardButton("60 minutes", callback_data="60minutes")
            ]
        ])
    )


async def handle_stop_work(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id

    if context.chat_data.get("work_alarm"):
        remove_job_if_exists(str(chat_id), context)
        await update.message.reply_text(
            "Alarm stopped successfully!"
        )

        # Save work done
        requests.post(
            url=os.getenv("BACK_SERVICE") + "/save-work",
            json={
                "start_time": context.chat_data["start_time"],
                "end_time": datetime.now(ZoneInfo('Europe/Chisinau')).strftime("%Y-%m-%d %H:%M:%S"),
                "type": "work"
            }
        )

        # Send the image as bytes
        response = requests.get(
            url=os.getenv("BACK_SERVICE") + "/get-disk-diagram-for-today"
        )
        if response.content:
            image_bytes = io.BytesIO(response.content)
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=image_bytes
            )
        context.chat_data["work_alarm"] = False
    else:
        await update.message.reply_text(
            "No work started yet!"
        )


async def stop_alarm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global consecutive
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    remove_job_if_exists(str(chat_id), context)
    if context.chat_data.get("work_alarm"):
        # Save work done
        requests.post(
            url=os.getenv("BACK_SERVICE") + "/save-work",
            json={
                "start_time": context.chat_data["start_time"],
                "end_time": context.chat_data["end_time"],
                "type": "work"
            }
        )
        
        # Send the image as bytes
        response = requests.get(
            url=os.getenv("BACK_SERVICE") + "/get-disk-diagram-for-today"
        )
        if response.content:
            image_bytes = io.BytesIO(response.content)
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=image_bytes
            )

        await query.message.reply_text(
            f"Alarm stopped successfully! Consecutive tasks: {consecutive}. \nChoose break duration:",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("20 minutes", callback_data="20minutes"), 
                    InlineKeyboardButton("15 minutes", callback_data="15minutes"),
                    InlineKeyboardButton("10 minutes", callback_data="10minutes"),
                    InlineKeyboardButton("60 minutes", callback_data="60minutes")
                ]
            ])
        )

        context.chat_data["work_alarm"] = False
    else:
        await query.edit_message_text(
            "Alarm stopped successfully!"
        )
        await handle_start_work(update.callback_query, context)


async def set_timer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global consecutive
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    if query.data == "50minutes":
        duration = 50 * 60
        consecutive += 1
        context.chat_data['work_alarm'] = True
    elif query.data == "90minutes":
        duration = 90 * 60
        context.chat_data['work_alarm'] = True
    elif query.data == "20minutes":
        duration = 20 * 60
        context.chat_data['work_alarm'] = False
    elif query.data == "15minutes":
        duration = 15 * 60
        context.chat_data['work_alarm'] = False
    elif query.data == "10minutes":
        duration = 10 * 60
        context.chat_data['work_alarm'] = False
    elif query.data == "60minutes":
        duration = 60 * 60
        consecutive = 0
        context.chat_data['work_alarm'] = False

    # Set the timer
    remove_job_if_exists(str(chat_id), context)
    context.job_queue.run_once(alarm, duration, chat_id=chat_id, name=str(chat_id), data=duration)
    current_time = datetime.now(ZoneInfo('Europe/Chisinau'))
    context.chat_data["start_time"] = current_time.strftime("%Y-%m-%d %H:%M:%S")
    context.chat_data["end_time"] = (current_time + timedelta(seconds=duration)).strftime("%Y-%m-%d %H:%M:%S")
    print(context.chat_data)
    await query.message.edit_text(text="Duration selected.", reply_markup=None)

    if context.chat_data.get('work_alarm'):
        await query.message.reply_text(f"Work alarm started. It will end at {context.chat_data['end_time']}.")
    else:
        await query.message.reply_text(f"Break alarm started. It will end at {context.chat_data['end_time']}.")


async def common_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    avg_day_work = (
        requests
        .get(url=os.getenv("BACK_SERVICE") + "/average-work-time-per-day")
        .json()
        .get("avg_day_work")
    )
    highest_score = (
        requests
        .get(url=os.getenv("BACK_SERVICE") + "/highest-score")
        .json()
        .get("highest_score")
    )
    await update.message.reply_text(
        f"*Stats:*\n" +
        f"*Highest score:* {highest_score:.2f} hours.\n" +
        f"*Daily average work:* {avg_day_work:.2f} hours.",
        parse_mode="Markdown"
        # Daily average work for the last 10 days
        # Daily average work for the last 100 days
        # Most productive intervals of time
    )


async def work_done_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    response = requests.get(os.getenv("BACK_SERVICE") + "/get-disk-diagram-for-today")
    if response.content:
        image_bytes = io.BytesIO(response.content)
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=image_bytes
        )


def main() -> None:
    """Run bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(os.getenv("BOT_TOKEN")).build()

    application.add_handler(CommandHandler(["start", "help"], start))
    application.add_handler(CommandHandler("unset", unset))
    application.add_handler(MessageHandler(filters.Regex("^Start work$"), handle_start_work))
    application.add_handler(MessageHandler(filters.Regex("^Stop work$"), handle_stop_work))
    application.add_handler(MessageHandler(filters.Regex("^Start break$"), handle_start_break))
    application.add_handler(MessageHandler(filters.Regex("^Common stats$"), common_stats))
    application.add_handler(MessageHandler(filters.Regex("^Work done today$"), work_done_today))
    application.add_handler(CallbackQueryHandler(stop_alarm, pattern="^stop_alarm$"))
    application.add_handler(CallbackQueryHandler(set_timer))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()