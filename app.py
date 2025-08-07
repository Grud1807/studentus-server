from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import logging

# Конфигурация
BOT_TOKEN = "8101750587:AAEoO1Aote7wHIRDADD4kpwFyYOYIkibe_c"
AIRTABLE_API_KEY = "patZ7hX8W8F8apmJm.9adf2ed71f8925dd372af08a5b5af2af4b12ead4abc0036be4ea68c43c47a8c4"
AIRTABLE_BASE_ID = "appTpq4tdeQ27uxQ9"
AIRTABLE_TABLE_NAME = "Tasks"
AIRTABLE_URL = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://grud1807.github.io"}})
logging.basicConfig(level=logging.INFO)

# ✅ Отправка сообщения в Telegram
def send_telegram_message(user_id, text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": user_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, json=payload)
        logging.info(f"📩 Сообщение пользователю {user_id}: {response.status_code} {response.text}")
    except Exception as e:
        logging.error(f"❌ Ошибка Telegram: {e}")

# ✅ Добавление задания
@app.route("/add-task", methods=["POST"])
def add_task():
    try:
        data = request.json
        logging.info(f"📥 Задание от клиента: {data}")

        subject = data.get("subject", "")
        description = data.get("description", "")
        deadline = data.get("deadline", "")
        user_id = data.get("user_id", "")
        username = data.get("username", "")

        try:
            price = int(data.get("price", 0))
        except ValueError:
            return jsonify({"success": False, "error": "Некорректная цена"}), 400

        airtable_data = {
            "fields": {
                "Предмет": subject,
                "Описание": description,
                "Цена": price,
                "Дедлайн": deadline,
                "ID пользователя": user_id,
                "Пользователь Telegram": username,
                "Статус": "Новое"
            }
        }

        headers = {
            "Authorization": f"Bearer {AIRTABLE_API_KEY}",
            "Content-Type": "application/json"
        }

        response = requests.post(AIRTABLE_URL, headers=headers, json=airtable_data)
        logging.info(f"📤 Ответ Airtable: {response.status_code} {response.text}")

        if response.status_code in [200, 201]:
            send_telegram_message(user_id, "✅ Задание успешно добавлено!\nОжидайте, когда его возьмут в работу.")
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": response.text}), 400
    except Exception as e:
        logging.exception("❌ Ошибка при добавлении")
        return jsonify({"success": False, "error": str(e)}), 500

# ✅ Взятие задания
@app.route("/take-task", methods=["POST"])
def take_task():
    try:
        data = request.json
        record_id = data.get("record_id")
        executor_id = data.get("executor_id")
        executor_username = data.get("executor_username")

        if not record_id or not executor_id:
            return jsonify({"success": False, "error": "Нет данных"}), 400

        headers = {
            "Authorization": f"Bearer {AIRTABLE_API_KEY}",
            "Content-Type": "application/json"
        }

        # Получение задания
        get_resp = requests.get(f"{AIRTABLE_URL}/{record_id}", headers=headers)
        if get_resp.status_code != 200:
            return jsonify({"success": False, "error": "Задание не найдено"}), 404

        task = get_resp.json()["fields"]
        customer_id = task.get("ID пользователя")
        customer_username = task.get("Пользователь Telegram", "неизвестно")
        subject = task.get("Предмет", "")
        description = task.get("Описание", "")
        price = task.get("Цена", "")
        deadline = task.get("Дедлайн", "")

        # Обновляем статус
        update_data = {
            "fields": {
                "Статус": "В работе",
                "ID исполнителя": executor_id,
                "Подтверждение заказчика": "Нет",
                "Подтверждение исполнителя": "Нет"
            }
        }

        patch_resp = requests.patch(f"{AIRTABLE_URL}/{record_id}", headers=headers, json=update_data)
        logging.info(f"📦 Обновляем задание {record_id} | Исполнитель: {executor_username} (ID: {executor_id})")

        if patch_resp.status_code in [200, 201]:
            # Сообщение исполнителю
            send_telegram_message(
                executor_id,
                f"📚 Вы взяли задание:\n\n*{subject}*\n📝 {description}\n💰 {price} ₽\n⏰ Дедлайн: {deadline}\n\n👤 Заказчик: @{customer_username}\n\nПосле выполнения нажмите *'✅ Подтвердить выполнение'*."
            )

            # Сообщение заказчику
            send_telegram_message(
                customer_id,
                f"✅ Ваше задание взяли в работу!\n\n*{subject}*\n📝 {description}\n💰 {price} ₽\n⏰ Дедлайн: {deadline}\n\n👨💻 Исполнитель: @{executor_username}\n\nПосле выполнения нажмите *'✅ Подтвердить выполнение'*."
            )

            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": patch_resp.text}), 400

    except Exception as e:
        logging.exception("❌ Ошибка при взятии задания")
        return jsonify({"success": False, "error": str(e)}), 500

# ✅ Запуск сервера
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
