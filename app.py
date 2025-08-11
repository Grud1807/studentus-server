# app.py
import os
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

# ========== Конфигурация ==========
# Предпочтительно задать в Render Dashboard -> Environment
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "patZ7hX8W8F8apmJm.9adf2ed71f8925dd372af08a5b5af2af4b12ead4abc0036be4ea68c43c47a8c4")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "appTpq4tdeQ27uxQ9")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME", "Tasks")  # если таблица называется иначе — измени
BASE_URL = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"

HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type": "application/json"
}

WEBAPP_ALLOWED_ORIGINS = os.getenv("WEBAPP_ALLOWED_ORIGINS", "https://grud1807.github.io")  # поменяй если надо

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# Разрешаем CORS для фронтенда (grud1807.github.io). Если нужно — добавить дополнительные домены.
CORS(app, origins=[origin.strip() for origin in WEBAPP_ALLOWED_ORIGINS.split(",")])

# ========== Утилиты Airtable ==========
def airtable_create_record(fields: dict):
    payload = {"fields": fields}
    r = requests.post(BASE_URL, json=payload, headers=HEADERS)
    r.raise_for_status()
    return r.json()

def airtable_get_record(record_id: str):
    url = f"{BASE_URL}/{record_id}"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.json()

def airtable_list_records():
    # Вернёт все записи (неплохо добавить пагинацию при большом количестве)
    r = requests.get(BASE_URL, headers=HEADERS)
    r.raise_for_status()
    return r.json()

def airtable_update_record(record_id: str, fields: dict):
    url = f"{BASE_URL}/{record_id}"
    payload = {"fields": fields}
    r = requests.patch(url, json=payload, headers=HEADERS)
    r.raise_for_status()
    return r.json()

# ========== API роуты ==========
@app.route("/api/tasks", methods=["GET"])
def api_get_tasks():
    """Возвращает список задач (облегчённый формат)."""
    data = airtable_list_records()
    out = []
    for rec in data.get("records", []):
        f = rec.get("fields", {})
        out.append({
            "record_id": rec.get("id"),
            "Уникальный ID": f.get("Уникальный ID"),
            "ID пользователя": f.get("ID пользователя"),
            "Пользователь Telegram": f.get("Пользователь Telegram"),
            "Предмет": f.get("Предмет"),
            "Описание": f.get("Описание"),
            "Цена": f.get("Цена"),
            "Дедлайн": f.get("Дедлайн"),
            "Статус": f.get("Статус"),
            "Подтверждение исполнителя": f.get("Подтверждение исполнителя"),
            "Подтверждение заказчика": f.get("Подтверждение заказчика"),
            "ID заказчика": f.get("ID заказчика"),
            "ID исполнителя": f.get("ID исполнителя"),
        })
    return jsonify(out), 200

@app.route("/add-task", methods=["POST"])
def api_add_task():
    """
    Ожидает JSON с полями: 
    {
      "Уникальный ID": 123,
      "ID пользователя": 1214806280,
      "Пользователь Telegram": "Nikita_Grud",
      "Предмет": "Физика",
      "Описание": "помогите",
      "Цена": 300,
      "Дедлайн": "2025-08-31",
      "ID заказчика": 1214806280
    }
    """
    data = request.json or {}
    # формируем поля для Airtable с начальными значениями
    fields = {
        "Уникальный ID": data.get("Уникальный ID") or "",
        "ID пользователя": data.get("ID пользователя"),
        "Пользователь Telegram": data.get("Пользователь Telegram"),
        "Предмет": data.get("Предмет"),
        "Описание": data.get("Описание"),
        "Цена": data.get("Цена"),
        "Дедлайн": data.get("Дедлайн"),
        "Статус": "Новое",
        "Подтверждение исполнителя": "Нет",
        "Подтверждение заказчика": "Нет",
        "ID заказчика": data.get("ID заказчика"),
        # "ID исполнителя" останется пустым пока не возьмут в работу
    }
    try:
        rec = airtable_create_record(fields)
    except Exception as e:
        logger.exception("Ошибка создания записи в Airtable")
        return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "ok", "record": rec}), 201

@app.route("/take-task", methods=["POST"])
def api_take_task():
    """
    Ожидает JSON: {"record_id": "<airtable id>", "executor_id": 8073144442, "executor_username": "Studentus_adm"}
    Устанавливает Статус = В работе, ID исполнителя и Исполнитель Telegram (если у тебя такое поле есть).
    """
    data = request.json or {}
    record_id = data.get("record_id")
    executor_id = data.get("executor_id")
    executor_username = data.get("executor_username")
    if not record_id or not executor_id:
        return jsonify({"status": "error", "message": "record_id и executor_id обязательны"}), 400

    try:
        fields = {
            "Статус": "В работе",
            "ID исполнителя": int(executor_id),
            # если есть поле для username — добавь, например "Исполнитель Telegram"
            "Исполнитель Telegram": executor_username
        }
        updated = airtable_update_record(record_id, fields)
    except Exception as e:
        logger.exception("Ошибка при взятии задания")
        return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "ok", "record": updated}), 200

@app.route("/confirm-task", methods=["POST"])
def api_confirm_task():
    """
    Ожидает JSON: {"record_id": "<airtable id>", "role": "customer" | "executor"}
    Обновляет соответствующее поле Подтверждение ... -> "Да"
    """
    data = request.json or {}
    record_id = data.get("record_id")
    role = data.get("role")
    if not record_id or role not in ("customer", "executor"):
        return jsonify({"status": "error", "message": "record_id и role обязательны"}), 400

    try:
        if role == "customer":
            fields = {"Подтверждение заказчика": "Да"}
        else:
            fields = {"Подтверждение исполнителя": "Да"}

        updated = airtable_update_record(record_id, fields)

        # Если оба подтверждения стали Да, ставим Статус = Завершена
        f = updated.get("fields", {})
        cust = f.get("Подтверждение заказчика") == "Да"
        exec_ = f.get("Подтверждение исполнителя") == "Да"
        if cust and exec_:
            airtable_update_record(record_id, {"Статус": "Завершена"})
    except Exception as e:
        logger.exception("Ошибка подтверждения")
        return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "ok", "record": updated}), 200

@app.route("/api/task/<record_id>", methods=["GET"])
def api_get_task(record_id):
    try:
        rec = airtable_get_record(record_id)
    except Exception as e:
        logger.exception("Ошибка чтения записи")
        return jsonify({"status": "error", "message": str(e)}), 500
    return jsonify(rec), 200

# Запуск только локально. Render сам запускает модуль.
if __name__ == "__main__":
    # Порт Render обычно проксирует, но в логах мы видим 5000 — оставляем 0.0.0.0:5000
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
