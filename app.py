import os
import logging
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

# ---------------- НАСТРОЙКИ ----------------
AIRTABLE_API_KEY = "patZ7hX8W8F8apmJm.9adf2ed71f8925dd372af08a5b5af2af4b12ead4abc0036be4ea68c43c47a8c4"
AIRTABLE_BASE_ID = "appTpq4tdeQ27uxQ9"
AIRTABLE_TABLE_NAME = "Tasks"
AIRTABLE_URL = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type": "application/json"
}

# ---------------- ЛОГИ ----------------
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ---------------- Flask ----------------
app = Flask(__name__)
# Разрешаем CORS только для твоего фронта
CORS(app, resources={r"/*": {"origins": "https://grud1807.github.io"}})

# ---------- ФУНКЦИИ РАБОТЫ С AIRTABLE ----------
def airtable_create_record(fields):
    """Создание записи в Airtable"""
    response = requests.post(AIRTABLE_URL, headers=HEADERS, json={"fields": fields})
    response.raise_for_status()
    return response.json()

def airtable_update_record(record_id, fields):
    """Обновление записи в Airtable"""
    url = f"{AIRTABLE_URL}/{record_id}"
    response = requests.patch(url, headers=HEADERS, json={"fields": fields})
    response.raise_for_status()
    return response.json()

def airtable_find_task_by_id(unique_id):
    """Поиск задания по уникальному ID"""
    params = {"filterByFormula": f"{{Уникальный ID}}={unique_id}"}
    response = requests.get(AIRTABLE_URL, headers=HEADERS, params=params)
    response.raise_for_status()
    records = response.json().get("records", [])
    return records[0] if records else None

# ---------- API РОУТЫ ----------
@app.route("/")
def home():
    return "App.py работает 🚀"

@app.route("/add-task", methods=["POST"])
def add_task():
    """Добавление нового задания в Airtable"""
    data = request.json
    try:
        fields = {
            "Уникальный ID": int(data["unique_id"]),
            "Предмет": data["subject"],
            "Описание": data["description"],
            "Цена": int(data["price"]),
            "Дедлайн": data["deadline"],
            "ID заказчика": int(data["customer_id"]),
            "Пользователь Telegram": data["customer_tg"],
            "Статус": "Новое",
            "Подтверждение заказчика": "Нет",
            "Подтверждение исполнителя": "Нет",
            "ID исполнителя": "",
            "Исполнитель Telegram": "",
        }
        logging.info(f"Отправляем в Airtable: {fields}")
        record = airtable_create_record(fields)
        return jsonify({"success": True, "id": record.get("id")})

    except requests.exceptions.HTTPError as http_err:
        logging.error(f"Ошибка Airtable HTTP: {http_err.response.text}")
        return jsonify({"success": False, "error": http_err.response.text}), 500
    except Exception as e:
        logging.error(f"Ошибка добавления задания: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/take-task", methods=["POST"])
def take_task():
    """Исполнитель берет задание"""
    data = request.json
    try:
        unique_id = int(data["unique_id"])
        executor_id = int(data["executor_id"])
        executor_tg = data["executor_tg"]

        task = airtable_find_task_by_id(unique_id)
        if not task:
            return jsonify({"success": False, "error": "Задание не найдено"}), 404

        record_id = task["id"]
        airtable_update_record(record_id, {
            "ID исполнителя": executor_id,
            "Исполнитель Telegram": executor_tg,
            "Статус": "В работе"
        })
        return jsonify({"success": True})

    except Exception as e:
        logging.error(f"Ошибка при взятии задания: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/confirm-task", methods=["POST"])
def confirm_task():
    """Подтверждение выполнения задания"""
    data = request.json
    try:
        unique_id = int(data["unique_id"])
        role = data["role"]

        task = airtable_find_task_by_id(unique_id)
        if not task:return jsonify({"success": False, "error": "Задание не найдено"}), 404

        record_id = task["id"]
        fields = task["fields"]

        if role == "executor":
            airtable_update_record(record_id, {"Подтверждение исполнителя": "Да"})
        elif role == "customer":
            airtable_update_record(record_id, {"Подтверждение заказчика": "Да"})

        # Проверка на завершение
        updated_task = airtable_find_task_by_id(unique_id)
        flds = updated_task["fields"]
        if flds.get("Подтверждение исполнителя") == "Да" and flds.get("Подтверждение заказчика") == "Да":
            airtable_update_record(record_id, {"Статус": "Завершена"})

        return jsonify({"success": True})

    except Exception as e:
        logging.error(f"Ошибка при подтверждении: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ---------- ЗАПУСК ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

