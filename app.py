# app.py — Studentus backend (Render). НЕ содержит BOT_TOKEN да
import os
import logging
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

# ---------------- CONFIG ----------------
# Лучше задавать AIRTABLE_API_KEY и AIRTABLE_BASE_ID как env vars в Render.
AIRTABLE_API_KEY = os.getenv(
    "AIRTABLE_API_KEY",
    "patZ7hX8W8F8apmJm.9adf2ed71f8925dd372af08a5b5af2af4b12ead4abc0036be4ea68c43c47a8c4"
)
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "appTpq4tdeQ27uxQ9")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME", "Tasks")
AIRTABLE_URL = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"

ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "https://grud1807.github.io")

HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type": "application/json"
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": [ALLOWED_ORIGIN]}})


# ---------------- Helpers ----------------
def safe_int(v, default=None):
    try:
        if v is None or v == "":
            return default
        return int(v)
    except Exception:
        return default


def airtable_create(fields: dict):
    payload = {"fields": fields}
    r = requests.post(AIRTABLE_URL, json=payload, headers=HEADERS)
    logging.info(f"Airtable create: status={r.status_code} body={r.text}")
    if not r.ok:
        r.raise_for_status()
    return r.json()


def airtable_get(record_id=None, filter_formula=None, max_records=100):
    if record_id:
        url = f"{AIRTABLE_URL}/{record_id}"
        r = requests.get(url, headers=HEADERS)
        logging.info(f"Airtable get {record_id}: status={r.status_code}")
        if not r.ok:
            r.raise_for_status()
        return r.json()
    else:
        params = {"maxRecords": max_records}
        if filter_formula:
            params["filterByFormula"] = filter_formula
        r = requests.get(AIRTABLE_URL, headers=HEADERS, params=params)
        logging.info(f"Airtable list: status={r.status_code}")
        if not r.ok:
            r.raise_for_status()
        return r.json()


def airtable_update(record_id: str, fields: dict):
    url = f"{AIRTABLE_URL}/{record_id}"
    payload = {"fields": fields}
    r = requests.patch(url, json=payload, headers=HEADERS)
    logging.info(f"Airtable patch {record_id}: status={r.status_code} body={r.text}")
    if not r.ok:
        r.raise_for_status()
    return r.json()


# ---------------- Routes ----------------
@app.route("/", methods=["GET"])
def home():
    return jsonify({"ok": True, "service": "Studentus API"})


@app.route("/add-task", methods=["POST"])
def add_task():
    """
    Ожидает JSON от add.html:
    { subject, description, price, deadline, user_id, username }
    """
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
            "ID заказчика": user_id,  # создатель = заказчик
            "Пользователь Telegram": str(data.get("username", "")),
            "Предмет": str(data.get("subject", "")),
            "Описание": str(data.get("description", "")),
            "Цена": price,
            "Дедлайн": str(data.get("deadline", "")),
            "Статус": "Новое",
            "Подтверждение заказчика": "Нет",
            "Подтверждение исполнителя": "Нет",
            "Уведомление отправлено": "Нет"  # поле, которое бот будет отслеживать
        }

        try:
            rec = airtable_create(fields)
        except requests.exceptions.HTTPError as he:
            # отдаём тело ошибки airtable клиенту (для отладки)
            body = he.response.text if he.response is not None else str(he)
            logging.error("Airtable create error: %s", body)
            return jsonify({"success": False, "error": f"Airtable error {he.response.status_code if he.response else 'N/A'}", "details": body}), 422

        record_id = rec.get("id")
        logging.info(f"Task created: {record_id}")
        return jsonify({"success": True, "record_id": record_id, "message": "Задание успешно добавлено"})

    except Exception as e:
        logging.exception("Error in /add-task")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/take-task", methods=["POST"])
def take_task():
    """
    Ожидает JSON:
    { record_id, executor_id, executor_username (опционально) }
    Обновляет запись: ID исполнителя, Статус -> "В работе", Уведомление отправлено = "Нет"
    """
    try:
        data = request.get_json(force=True)
        logging.info(f"POST /take-task payload: {data}")

        record_id = data.get("record_id")
        executor_id = safe_int(data.get("executor_id"))
        # executor_username не сохраняем (в таблице колонка для этого отсутствует)

        if not record_id:
            return jsonify({"success": False, "error": "Нужен record_id задания"}), 400
        if executor_id is None:
            return jsonify({"success": False, "error": "executor_id должен быть числом"}), 400

        # получаем запись
        rec = airtable_get(record_id=record_id)
        fields = rec.get("fields", {})
        status = fields.get("Статус")
        if status != "Новое":
            return jsonify({"success": False, "error": "Задание уже взято или недоступно"}), 400

        # нельзя взять своё задание
        owner_id = safe_int(fields.get("ID заказчика") or fields.get("ID пользователя"))
        if owner_id == executor_id:
            return jsonify({"success": False, "error": "Нельзя взять своё задание"}), 400

        # проверить, не взял ли исполнитель другое в работе
        formula = f"AND({{ID исполнителя}}={executor_id}, {{Статус}}='В работе')"
        list_resp = airtable_get(filter_formula=formula)
        if list_resp.get("records"):
            return jsonify({"success": False, "error": "У вас уже есть задание в работе"}), 400

        update_fields = {
            "ID исполнителя": executor_id,
            "Статус": "В работе",
            "Уведомление отправлено": "Нет"  # бот увидит и отправит уведомления
        }

        try:
            airtable_update(record_id, update_fields)
        except requests.exceptions.HTTPError as he:
            body = he.response.text if he.response is not None else str(he)
            logging.error("Airtable patch error: %s", body)
            return jsonify({"success": False, "error": f"Airtable error {he.response.status_code if he.response else 'N/A'}", "details": body}), 422

        logging.info(f"Task {record_id} taken by {executor_id}")
        return jsonify({"success": True, "record_id": record_id, "message": "Задание взято в работу"})

    except Exception as e:
        logging.exception("Error in /take-task")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/confirm-task", methods=["POST"])
def confirm_task():
    """
    Ожидает JSON:
    { record_id, user_id }
    Обновляет поле подтверждения; если обе стороны подтвердили — ставит 'Завершено'.
    """
    try:
        data = request.get_json(force=True)
        logging.info(f"POST /confirm-task payload: {data}")

        record_id = data.get("record_id")
        user_id = safe_int(data.get("user_id"))

        if not record_id:
            return jsonify({"success": False, "error": "Нужен record_id"}), 400
        if user_id is None:
            return jsonify({"success": False, "error": "user_id должен быть числом"}), 400

        rec = airtable_get(record_id=record_id)
        fields = rec.get("fields", {})
        executor_id = safe_int(fields.get("ID исполнителя"))
        customer_id = safe_int(fields.get("ID заказчика") or fields.get("ID пользователя"))

        if user_id == executor_id:
            if fields.get("Подтверждение исполнителя") == "Да":
                return jsonify({"success": False, "error": "Вы уже подтвердили выполнение"}), 400
            airtable_update(record_id, {"Подтверждение исполнителя": "Да"})
        elif user_id == customer_id:
            if fields.get("Подтверждение заказчика") == "Да":
                return jsonify({"success": False, "error": "Вы уже подтвердили выполнение"}), 400
            airtable_update(record_id, {"Подтверждение заказчика": "Да"})
        else:
            return jsonify({"success": False, "error": "Вы не участник задания"}), 403

        # проверка завершения
        rec2 = airtable_get(record_id=record_id)
        f2 = rec2.get("fields", {})
        if f2.get("Подтверждение исполнителя") == "Да" and f2.get("Подтверждение заказчика") == "Да":
            airtable_update(record_id, {"Статус": "Завершено"})
            logging.info(f"Task {record_id} marked Завершено")

        return jsonify({"success": True})

    except Exception as e:
        logging.exception("Error in /confirm-task")
        return jsonify({"success": False, "error": str(e)}), 500


# ---------- Run ----------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

