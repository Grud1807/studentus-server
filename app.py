import logging
import aiohttp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# Твои константы:
TOKEN = "8101750587:AAEoO1Aote7wHIRDADD4kpwFyYOYIkibe_c"
AIRTABLE_URL = "https://api.airtable.com/v0/appTpq4tdeQ27uxQ9/Tasks"
HEADERS = {
    "Authorization": "Bearer patZ7hX8W8F8apmJm.9adf2ed71f8925dd372af08a5b5af2af4b12ead4abc0036be4ea68c43c47a8c4",
    "Content-Type": "application/json"
}

async def airtable_update_task(record_id: str, fields: dict):
    url = f"{AIRTABLE_URL}/{record_id}"
    async with aiohttp.ClientSession() as session:
        async with session.patch(url, json={"fields": fields}, headers=HEADERS) as resp:
            return await resp.json()

# Функция, которая показывает задание с кнопкой подтверждения (пример)
async def show_task_with_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, task_record):
    fields = task_record["fields"]
    record_id = task_record["id"]

    customer_id = int(fields.get('ID заказчика'))
    executor_id = int(fields.get('ID исполнителя'))
    status = fields.get('Статус', 'Новое')

    text = f"Задание:\n{fields.get('Описание', 'нет описания')}\nЦена: {fields.get('Цена', '0')} ₽\nСтатус: {status}"

    # Показываем кнопку только если статус В работе и пользователь заказчик или исполнитель
    user_id = update.effective_user.id
    keyboard = None
    if status == "В работе" and (user_id == customer_id or user_id == executor_id):
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Подтвердить выполнение", callback_data=f"confirm_{record_id}")]]
        )

    await update.message.reply_text(text, reply_markup=keyboard)

# Callback для обработки подтверждений
async def confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await query.message.reply_text("Это бот Studentus.\n\n"
                                  "Вы можете брать задания, подтверждать выполнение и общаться через бота.")

async def my_tasks_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Здесь будет список ваших заданий (реализацию добавим позже).")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "help":
        await help_callback(update, context)
    elif data == "my_tasks":
        await my_tasks_callback(update, context)
    else:
        await query.answer("Неизвестная команда.")

def main():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))  # предполагается, что start у тебя есть
    application.add_handler(CallbackQueryHandler(confirm_callback, pattern=r"confirm_"))
    application.add_handler(CallbackQueryHandler(callback_handler, pattern=r"^(help|my_tasks)$"))

    logging.info("Бот Studentus запущен.")
    application.run_polling()

if __name__ == "__main__":
    main()

