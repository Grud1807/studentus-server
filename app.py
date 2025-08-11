import logging
from flask import Flask, request, jsonify
import requests
import os
from flask_cors import CORS  # <-- импортируем

app = Flask(__name__)

# Разрешаем CORS для сайта https://grud1807.github.io (твой фронт)
CORS(app, origins=["https://grud1807.github.io"])

# Если хочешь разрешить все (для теста), можно так:
# CORS(app)

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "patZ7hX8W8F8apmJm.9adf2ed71f8925dd372af08a5b5af2af4b12ead4abc0036be4ea68c43c47a8c4")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "appTpq4tdeQ27uxQ9")
AIRTABLE_TABLE_NAME = "Tasks"
AIRTABLE_URL = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"

HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type": "application/json"
}

logging.basicConfig(level=logging.INFO)

def airtable_create_record(fields):
    payload = {"fields": fields}
    r = requests.post(AIRTABLE_URL, json=payload, headers=HEADERS)
    try:
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logging.error(f"Ошибка Airtable (HTTP {r.status_code}): {r.text}")
        raise
    return r.json()

@app.route("/add-task", methods=["POST"])
def api_add_task():
    data = request.get_json()
    logging.info(f"Получены данные для добавления задания: {data}")

    required_fields = ["subject", "description", "price", "deadline", "user_id", "username"]
    missing = [f for f in required_fields if f not in data or data[f] in [None, ""]]
    if missing:
        error_msg = f"Отсутствуют обязательные поля: {', '.join(missing)}"
        logging.error(error_msg)
        return jsonify({"success": False, "error": error_msg}), 400

    try:
        fields = {
            "Предмет": data["subject"],
            "Описание": data["description"],
            "Цена": int(data["price"]),
            "Дедлайн": data["deadline"],
            "ID пользователя": int(data["user_id"]),
            "Пользователь Telegram": data.get("username", ""),
            "Статус": "Новое"
        }

        rec = airtable_create_record(fields)
        logging.info(f"Запись успешно добавлена в Airtable: ID записи {rec.get('id')}")

        return jsonify({"success": True, "id": rec.get("id")})

    except Exception as e:
        logging.exception("Ошибка при создании записи в Airtable")
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
