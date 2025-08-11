import os
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

# ===== Конфигурация =====
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "patZ7hX8W8F8apmJm.9adf2ed71f8925dd372af08a5b5af2af4b12ead4abc0036be4ea68c43c47a8c4")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "appTpq4tdeQ27uxQ9")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME", "Tasks")
AIRTABLE_URL = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"

# ===== Flask =====
app = Flask(__name__)
CORS(app)  # Разрешаем запросы с фронтенда

logging.basicConfig(level=logging.INFO)


@app.route("/add-task", methods=["POST"])
def add_task():
    try:
        data = request.get_json(force=True)
        logging.info(f"📩 Получены данные: {data}")

        # Проверка обязательных полей
        required_fields = ["user_id", "username", "subject", "description", "price", "deadline"]
        for field in required_fields:
            if not data.get(field):
                return jsonify({"success": False, "error": f"Отсутствует поле: {field}"}), 400

        # Формируем запись в Airtable
        airtable_data = {
            "fields": {
                "ID пользователя": str(data["user_id"]),
                "Пользователь Telegram": str(data["username"]),
                "Предмет": str(data["subject"]),
                "Описание": str(data["description"]),
                "Цена": str(data["price"]),
                "Дедлайн": str(data["deadline"]),
                "Статус": "Новое"
            }
        }

        # Запрос в Airtable
        headers = {
            "Authorization": f"Bearer {AIRTABLE_API_KEY}",
            "Content-Type": "application/json"
        }
        response = requests.post(AIRTABLE_URL, json=airtable_data, headers=headers)

        if response.status_code != 200:
            logging.error(f"❌ Ошибка Airtable {response.status_code}: {response.text}")
            return jsonify({
                "success": False,
                "error": f"Airtable error {response.status_code}",
                "details": response.json()
            }), 500

        logging.info("✅ Задание успешно добавлено в Airtable")
        return jsonify({"success": True, "message": "Задание успешно добавлено!"})

    except Exception as e:
        logging.exception("❌ Ошибка на сервере")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/", methods=["GET"])
def index():
    return jsonify({"message": "Studentus API работает 🚀"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
