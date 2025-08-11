import logging
from flask import Flask, jsonify, request
import aiohttp
import asyncio

# Airtable настройки
AIRTABLE_URL = "https://api.airtable.com/v0/appTpq4tdeQ27uxQ9/Tasks"
AIRTABLE_API_KEY = "patZ7hX8W8F8apmJm.9adf2ed71f8925dd372af08a5b5af2af4b12ead4abc0036be4ea68c43c47a8c4"
HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type": "application/json"
}

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# ====== Взаимодействие с Airtable ======
async def airtable_get_all_tasks():
    async with aiohttp.ClientSession() as session:
        async with session.get(AIRTABLE_URL, headers=HEADERS) as resp:
            return await resp.json()

async def airtable_get_task(record_id: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{AIRTABLE_URL}/{record_id}", headers=HEADERS) as resp:
            return await resp.json()

async def airtable_update_task(record_id: str, fields: dict):
    async with aiohttp.ClientSession() as session:
        async with session.patch(f"{AIRTABLE_URL}/{record_id}", headers=HEADERS, json={"fields": fields}) as resp:
            return await resp.json()

# ====== API роуты ======
@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    """Получить список всех задач"""
    data = asyncio.run(airtable_get_all_tasks())
    tasks = []
    for rec in data.get("records", []):
        fields = rec.get("fields", {})
        tasks.append({
            "id": rec["id"],
            "title": fields.get("Название", "Без названия"),
            "status": fields.get("Статус", "Неизвестно"),
            "customer_id": fields.get("ID заказчика"),
            "executor_id": fields.get("ID исполнителя")
        })
    return jsonify(tasks)

@app.route("/api/tasks/<record_id>", methods=["GET"])
def get_task(record_id):
    """Получить одну задачу"""
    task = asyncio.run(airtable_get_task(record_id))
    return jsonify(task)

@app.route("/api/tasks/<record_id>", methods=["PATCH"])
def update_task(record_id):
    """Обновить поля задачи"""
    fields = request.json.get("fields", {})
    updated = asyncio.run(airtable_update_task(record_id, fields))
    return jsonify(updated)

if __name__ == "__main__":
    # Запуск на Render будет с host=0.0.0.0
    app.run(host="0.0.0.0", port=5000)
