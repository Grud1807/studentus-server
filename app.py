# app.py — Studentus backend (Render)
import os
import logging
from datetime import datetime
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

# ---------------- CONFIG ----------------
# Реальные ключи сразу в коде
AIRTABLE_API_KEY = "patZ7hX8W8F8apmJm.9adf2ed71f8925dd372af08a5b5af2af4b12ead4abc0036be4ea68c43c47a8c4"

# Таблица Tasks
AIRTABLE_BASE_ID_TASKS = "appTpq4tdeQ27uxQ9"
AIRTABLE_URL_TASKS = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID_TASKS}/Tasks"

# Таблица Projects
AIRTABLE_BASE_ID_PROJECTS = "app0YQKcIIvnnxQqj"
AIRTABLE_URL_PROJECTS = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID_PROJECTS}/Projects"

HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type": "application/json"
}

# ---------------- Flask ----------------
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}},
     supports_credentials=True,
     allow_headers="*",
     methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])

# ---------------- Logging ----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ---------------- Helpers ----------------
def safe_int(v, default=None):
    try:
        if v is None or v == "":
            return default
        return int(v)
    except Exception:
        return default

def airtable_create(url, fields: dict):
    payload = {"fields": fields}
    r = requests.post(url, json=payload, headers=HEADERS)
    logging.info(f"Airtable create: url={url} status={r.status_code} body={r.text}")
    if not r.ok:
        r.raise_for_status()
    return r.json()

def airtable_get(url, record_id=None, filter_formula=None, max_records=100):
    if record_id:
        url = f"{url}/{record_id}"
        r = requests.get(url, headers=HEADERS)
        logging.info(f"Airtable get {record_id}: status={r.status_code}")
        if not r.ok:
            r.raise_for_status()
        return r.json()
    else:
        params = {"maxRecords": max_records}
        if filter_formula:
            params["filterByFormula"] = filter_formula
        r = requests.get(url, headers=HEADERS, params=params)
        logging.info(f"Airtable list: url={url} status={r.status_code}")
        if not r.ok:
            r.raise_for_status()
        return r.json()

def airtable_update(url, record_id: str, fields: dict):
    patch_url = f"{url}/{record_id}"
    payload = {"fields": fields}
    r = requests.patch(patch_url, json=payload, headers=HEADERS)
    logging.info(f"Airtable patch {record_id}: status={r.status_code} body={r.text}")
    if not r.ok:
        r.raise_for_status()
    return r.json()

# ---------------- Routes ----------------
@app.route("/", methods=["GET"])
def home():
    return jsonify({"ok": True, "service": "Studentus API"})

# --------- Tasks ---------
@app.route("/add-task", methods=["POST"])
def add_task():
    try:
        data = request.get_json(force=True)
        logging.info(f"POST /add-task payload: {data}")

        required = ["subject", "description", "price", "deadline", "user_id", "username"]
        missing = [k for k in required if not data.get(k)]
        if missing:
            return jsonify({"success": False, "error": f"Отсутствуют поля: {', '.join(missing)}"}), 400

        user_id = safe_int(data.get("user_id"))
        price = safe_int(data.get("price"))
        if user_id is None or price is None:
            return jsonify({"success": False, "error": "user_id и price должны быть числами"}), 400

        fields = {
            "ID пользователя": user_id,
            "ID заказчика": user_id,
            "Пользователь Telegram": str(data.get("username", "")),
            "Предмет": str(data.get("subject", "")),
            "Описание": str(data.get("description", "")),
            "Цена": price,
            "Дедлайн": str(data.get("deadline", "")),
            "Статус": "В обработке",   # 🔹 Меняем начальный статус
            "Подтверждение заказчика": "Нет",
            "Подтверждение исполнителя": "Нет",
            "Уведомление отправлено": "Нет"
        }

        rec = airtable_create(AIRTABLE_URL_TASKS, fields)
        record_id = rec.get("id")
        logging.info(f"Task created: {record_id}")
        return jsonify({"success": True, "record_id": record_id, "message": "Задание успешно добавлено! Мы уведомим вас, когда оно будет опубликовано."})

    except requests.exceptions.HTTPError as he:
        body = he.response.text if he.response else str(he)
        logging.error(f"Airtable error: {body}")
        return jsonify({"success": False, "error": f"Airtable error {he.response.status_code if he.response else 'N/A'}", "details": body}), 422
    except Exception as e:
        logging.exception("Error in /add-task")
        return jsonify({"success": False, "error": str(e)}), 500
        
@app.route("/take-task", methods=["POST"])
def take_task():
    try:
        data = request.get_json(force=True)
        logging.info(f"POST /take-task payload: {data}")

        record_id = data.get("record_id")
        executor_id = safe_int(data.get("executor_id"))
        executor_username = data.get("executor_username") or "без username"

        if not record_id or executor_id is None:
            return jsonify({"success": False, "error": "record_id и executor_id обязательны"}), 400

        # нормализуем username
        if executor_username != "без username" and not executor_username.startswith("@"):
            executor_username = f"@{executor_username}"

        # проверка задания
        rec = airtable_get(AIRTABLE_URL_TASKS, record_id=record_id)
        fields = rec.get("fields", {})
        status = fields.get("Статус")
        if status != "Новое":
            return jsonify({"success": False, "error": "Задание уже взято или недоступно"}), 400

        # нельзя брать своё задание
        owner_id = safe_int(fields.get("ID заказчика") or fields.get("ID пользователя"))
        if owner_id == executor_id:
            return jsonify({"success": False, "error": "Нельзя взять своё задание"}), 400

        # проверка на активное задание
        formula = f"AND({{ID исполнителя}}={executor_id}, {{Статус}}='В работе')"
        list_resp = airtable_get(AIRTABLE_URL_TASKS, filter_formula=formula)
        if list_resp.get("records"):
            return jsonify({"success": False, "error": "У вас уже есть задание в работе"}), 400

        # обновляем запись
        update_fields = {
            "ID исполнителя": executor_id,
            "Исполнитель Telegram": executor_username,   # новая колонка
            "Статус": "В работе",
            "Уведомление отправлено": "Нет"
        }
        airtable_update(AIRTABLE_URL_TASKS, record_id, update_fields)

        logging.info(f"Task {record_id} taken by {executor_id} ({executor_username})")
        return jsonify({"success": True, "record_id": record_id, "message": "Задание взято в работу"})

    except Exception as e:
        logging.exception("Error in /take-task")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/confirm-task", methods=["POST"])
def confirm_task():
    try:
        data = request.get_json(force=True)
        logging.info(f"POST /confirm-task payload: {data}")

        record_id = data.get("record_id")
        user_id = safe_int(data.get("user_id"))
        if not record_id or user_id is None:
            return jsonify({"success": False, "error": "record_id и user_id обязательны"}), 400

        rec = airtable_get(AIRTABLE_URL_TASKS, record_id=record_id)
        fields = rec.get("fields", {})
        executor_id = safe_int(fields.get("ID исполнителя"))
        customer_id = safe_int(fields.get("ID заказчика") or fields.get("ID пользователя"))

        if user_id == executor_id:
            if fields.get("Подтверждение исполнителя") == "Да":
                return jsonify({"success": False, "error": "Вы уже подтвердили выполнение"}), 400
            airtable_update(AIRTABLE_URL_TASKS, record_id, {"Подтверждение исполнителя": "Да"})
        elif user_id == customer_id:
            if fields.get("Подтверждение заказчика") == "Да":
                return jsonify({"success": False, "error": "Вы уже подтвердили выполнение"}), 400
            airtable_update(AIRTABLE_URL_TASKS, record_id, {"Подтверждение заказчика": "Да"})
        else:
            return jsonify({"success": False, "error": "Вы не участник задания"}), 403

        rec2 = airtable_get(AIRTABLE_URL_TASKS, record_id=record_id)
        f2 = rec2.get("fields", {})
        if f2.get("Подтверждение исполнителя") == "Да" and f2.get("Подтверждение заказчика") == "Да":
            airtable_update(AIRTABLE_URL_TASKS, record_id, {"Статус": "Завершено"})
            logging.info(f"Task {record_id} marked Завершено")

        return jsonify({"success": True})

    except Exception as e:
        logging.exception("Error in /confirm-task")
        return jsonify({"success": False, "error": str(e)}), 500

# --------- Projects ---------
@app.route("/add-project", methods=["POST"])
def add_project():
    try:
        data = request.get_json(force=True)
        logging.info(f"Пришли данные для Projects: {data}")

        fields = {
            "Имя": data.get("name"),
            "Тема проекта": data.get("projectTopic"),
            "Дедлайн": data.get("deadline"),
            "Пожелания": data.get("wishes"),
            "Контакты": data.get("contacts"),
            "Дата заявки": datetime.now().strftime("%Y-%m-%d"),
            "Статус": "Новая"
        }

        rec = airtable_create(AIRTABLE_URL_PROJECTS, fields)
        logging.info(f"Project created: {rec.get('id')}")
        return jsonify({"success": True, "message": "Заявка успешно добавлена"}), 200

    except requests.exceptions.HTTPError as he:
        body = he.response.text if he.response else str(he)
        logging.error(f"Airtable error Projects: {body}")
        return jsonify({"success": False, "message": "Ошибка при добавлении !", "details": body}), 422
    except Exception as e:
        logging.exception("Ошибка в /add-project")
        return jsonify({"success": False, "message": str(e)}), 500

# ---------------- Run ----------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)







