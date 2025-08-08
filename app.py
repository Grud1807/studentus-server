import logging
import aiohttp
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

TOKEN = "8101750587:AAEoO1Aote7wHIRDADD4kpwFyYOYIkibe_c"
AIRTABLE_URL = "https://api.airtable.com/v0/appTpq4tdeQ27uxQ9/Tasks"
AIRTABLE_API_KEY = "patZ7hX8W8F8apmJm.9adf2ed71f8925dd372af08a5b5af2af4b12ead4abc0036be4ea68c43c47a8c4"
HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type": "application/json"
}

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


async def airtable_update_task(record_id: str, fields: dict):
    """Обновляет запись в Airtable по record_id."""
    url = f"{AIRTABLE_URL}/{record_id}"
    async with aiohttp.ClientSession() as session:
        async with session.patch(url, headers=HEADERS, json={"fields": fields}) as resp:
            return await resp.json()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start с красивыми кнопками."""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Мои задания", callback_data="my_tasks")],
        [InlineKeyboardButton("Помощь", callback_data="help")]
    ])
    await update.message.reply_text(
        "Добро пожаловать в Studentus!\n\n"
        "Выбирайте действие ниже:",
        reply_markup=keyboard
    )


async def confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик подтверждения выполнения задания."""
    query = update.callback_query
    user_id = query.from_user.id
    task_record_id = query.data.split('_')[1]

    # Получаем задачу по record_id
    async with aiohttp.ClientSession() as session:
        url = f"{AIRTABLE_URL}/{task_record_id}"
        async with session.get(url, headers=HEADERS) as resp:
            task_record = await resp.json()

    if "fields" not in task_record:
        await query.answer("Задание не найдено.")
        return

    fields = task_record["fields"]
    customer_id = int(fields.get('ID заказчика'))
    executor_id = int(fields.get('ID исполнителя'))

    if user_id != customer_id and user_id != executor_id:
        await query.answer("Вы не участвуете в этом задании.")
        return

    cust_confirm = fields.get('Подтверждение заказчика', 'Нет')
    exec_confirm = fields.get('Подтверждение исполнителя', 'Нет')

    if user_id == customer_id:
        if cust_confirm == 'Да':
            await query.answer("Вы уже подтвердили выполнение.")
            return
        cust_confirm = 'Да'
    elif user_id == executor_id:
        if exec_confirm == 'Да':
            await query.answer("Вы уже подтвердили выполнение.")
            return
        exec_confirm = 'Да'

    # Обновляем подтверждения
    await airtable_update_task(task_record_id, {
        "Подтверждение заказчика": cust_confirm,
        "Подтверждение исполнителя": exec_confirm
    })

    # Если подтвердил только один — удаляем кнопку и пишем "ждите подтверждения другой стороны"
    if cust_confirm != 'Да' or exec_confirm != 'Да':
        await query.answer("Подтверждение принято! Ждите подтверждения другой стороны.")
        await query.edit_message_reply_markup(reply_markup=None)
        return

    # Если оба подтвердили — меняем статус, уведомляем и убираем кнопки
    await airtable_update_task(task_record_id, {"Статус": "Завершено"})
    await query.edit_message_reply_markup(reply_markup=None)

    await context.bot.send_message(customer_id, "Задание успешно завершено! Спасибо за сотрудничество.")
    await context.bot.send_message(executor_id, "Задание успешно завершено! Хорошая работа!")

    await query.answer("Подтверждение принято! Спасибо.")


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "Это бот Studentus.\n\n"
        "Вы можете брать задания, подтверждать выполнение и общаться через бота."
    )


async def my_tasks_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "Здесь будет список ваших заданий (реализацию добавим позже)."
    )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "help":
        await help_callback(update, context)
    elif data == "my_tasks":
        await my_tasks_callback(update, context)
    elif data.startswith("confirm_"):
        # Подтверждение выполнения задания
        await confirm_callback(update, context)
    else:
        await query.answer("Неизвестная команда.")


def main():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    # Обработчик любых callback с подтверждениями и основными кнопками
    application.add_handler(CallbackQueryHandler(callback_handler))

    logging.info("Бот Studentus запущен.")
    application.run_polling()


if __name__ == "__main__":
    main()
