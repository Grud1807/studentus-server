import logging
from flask import Flask, request, jsonify
import requests
import os
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=["https://grud1807.github.io"])  # Разрешаем запросы с фронта

# Настройки Airtable
AIRTABLE_API_KEY = os.getenv(
    "AIRTABLE_API_KEY",
    "patZ7hX8W8F8apmJm.9adf2ed71f8925dd372af08a5b5af2af4b12ead4abc0036be4ea68c43c47a8c4"
)
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
    r.raise_for_status()
    return r.json()


def airtable_update_record(record_id, fields):
    url = f"{AIRTABLE_URL}/{record_id}"
    r = requests.patch(url, json={"fields": fields}, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def airtable_get_task_by_unique_id(unique_id):
    params = {"filterByFormula": f"{{Уникальный ID}}={unique_id}"}
    r = requests.get(AIRTABLE_URL, headers=HEADERS, params=params)
    r.raise_for_status()
    records = r.json().get("records", [])
    return records[0] if records else None


@app.route("/add-task", methods=["POST"])
def add_task():
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
        "Цена": int(data["price"]),          # обязательно int
        "Дедлайн": data["deadline"],         # должен быть строкой, лучше формат ISO: YYYY-MM-DD
        "ID пользователя": int(data["user_id"]),
        "Пользователь Telegram": data["username"],
        "Статус": "Новое",
        "Подтверждение заказчика": "Нет",
        "Подтверждение исполнителя": "Нет",
        "ID исполнителя": None,
        "Исполнитель Telegram": "",
    }
    logging.info(f"Отправляем в Airtable поля: {fields}")
    record = airtable_create_record(fields)
    logging.info(f"Задание добавлено в Airtable, ID записи: {record.get('id')}")
    return jsonify({"success": True, "id": record.get("id")})
except requests.exceptions.HTTPError as http_err:
    logging.error(f"Ошибка Airtable HTTP: {http_err.response.text}")
    return jsonify({"success": False, "error": f"Airtable error: {http_err.response.text}"}), 500
except Exception as e:
    logging.error(f"Ошибка добавления задания: {e}")
    return jsonify({"success": False, "error": str(e)}), 500

@app.route("/take-task", methods=["POST"])
def take_task():
    data = request.get_json()
    logging.info(f"Получены данные для взятия задания: {data}")

    required_fields = ["unique_id", "executor_id", "executor_tg"]
    missing = [f for f in required_fields if f not in data or data[f] in [None, ""]]
    if missing:
        error_msg = f"Отсутствуют обязательные поля: {', '.join(missing)}"
        logging.error(error_msg)
        return jsonify({"success": False, "error": error_msg}), 400

    unique_id = data["unique_id"]
    executor_id = int(data["executor_id"])
    executor_tg = data["executor_tg"]

    try:
        task = airtable_get_task_by_unique_id(unique_id)
        if not task:
            error_msg = f"Задание с Уникальный ID={unique_id} не найдено."
            logging.error(error_msg)
            return jsonify({"success": False, "error": error_msg}), 404

        record_id = task["id"]
        fields = task["fields"]

        if fields.get("Статус") != "Новое":
            error_msg = "Задание уже взято или недоступно."
            logging.error(error_msg)
            return jsonify({"success": False, "error": error_msg}), 400

        if fields.get("ID пользователя") == executor_id:
            error_msg = "Нельзя взять в работу своё задание."
            logging.error(error_msg)
            return jsonify({"success": False, "error": error_msg}), 400

        # Проверяем, не взял ли исполнитель уже другое задание в работе
        filter_executor = f'AND({{ID исполнителя}}={executor_id}, {{Статус}}="В работе")'
        r = requests.get(AIRTABLE_URL, headers=HEADERS, params={"filterByFormula": filter_executor})
        r.raise_for_status()
        records = r.json().get("records", [])
        if records:
            error_msg = "Вы уже взяли другое задание в работу. Завершите его перед взятием нового."
            logging.error(error_msg)
            return jsonify({"success": False, "error": error_msg}), 400

        # Обновляем задание: ставим исполнителя, меняем статус на "В работе"
        update_fields = {
            "Статус": "В работе",
            "ID исполнителя": executor_id,
            "Исполнитель Telegram": executor_tg,
            "Подтверждение заказчика": "Нет",
            "Подтверждение исполнителя": "Нет",
        }
        airtable_update_record(record_id, update_fields)
        logging.info(f"Задание {unique_id} взято в работу исполнителем {executor_id}")

        return jsonify({"success": True})
    except Exception as e:
        logging.error(f"Ошибка при взятии задания: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/confirm-task", methods=["POST"])
def confirm_task():
    """
    Ожидается JSON:
    {
        "unique_id": int,
        "user_id": int
    }
    Пользователь (исполнитель или заказчик) подтверждает выполнение задания.
    Если обе стороны подтвердили — статус меняется на "Завершена".
    """
    data = request.get_json()
    logging.info(f"Получены данные для подтверждения задания: {data}")

    required_fields = ["unique_id", "user_id"]
    missing = [f for f in required_fields if f not in data or data[f] in [None, ""]]
    if missing:
        error_msg = f"Отсутствуют обязательные поля: {', '.join(missing)}"
        logging.error(error_msg)
        return jsonify({"success": False, "error": error_msg}), 400

    unique_id = data["unique_id"]
    user_id = int(data["user_id"])

    try:
        task = airtable_get_task_by_unique_id(unique_id)
        if not task:
            error_msg = f"Задание с Уникальный ID={unique_id} не найдено."
            logging.error(error_msg)
            return jsonify({"success": False, "error": error_msg}), 404

        record_id = task["id"]
        fields = task["fields"]

        executor_id = fields.get("ID исполнителя")
        customer_id = fields.get("ID пользователя")

        if user_id != executor_id and user_id != customer_id:
            error_msg = "Пользователь не участвует в этом задании."
            logging.error(error_msg)
            return jsonify({"success": False, "error": error_msg}), 403

        # Определяем роль пользователя и обновляем подтверждение
        if user_id == executor_id:
            if fields.get("Подтверждение исполнителя") == "Да":
                return jsonify({"success": False, "error": "Вы уже подтвердили выполнение."}), 400
            airtable_update_record(record_id, {"Подтверждение исполнителя": "Да"})
            logging.info(f"Исполнитель {user_id} подтвердил выполнение задания {unique_id}")
        else:
            if fields.get("Подтверждение заказчика") == "Да":
                return jsonify({"success": False, "error": "Вы уже подтвердили выполнение."}), 400
            airtable_update_record(record_id, {"Подтверждение заказчика": "Да"})
            logging.info(f"Заказчик {user_id} подтвердил выполнение задания {unique_id}")

        # Проверяем, подтвердили ли обе стороны
        updated_task = airtable_get_task_by_unique_id(unique_id)
        updated_fields = updated_task["fields"]
        if (updated_fields.get("Подтверждение исполнителя") == "Да" and
                updated_fields.get("Подтверждение заказчика") == "Да"):
            airtable_update_record(record_id, {"Статус": "Завершена"})
            logging.info(f"Задание {unique_id} завершено.")

        return jsonify({"success": True})

    except Exception as e:
        logging.error(f"Ошибка подтверждения задания: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

