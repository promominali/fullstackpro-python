import base64
import json

from fastapi import FastAPI, Header, HTTPException, Request

from .db import get_db
from .models import ExampleItem


worker_app = FastAPI(title="Fullstack GCP Worker", version="0.1.0")


@worker_app.post("/pubsub/push")
async def pubsub_push(request: Request, x_cloud_tasks_taskname: str | None = Header(default=None)):
    # Pub/Sub push format: {"message": {"data": "base64"}, "subscription": "..."}
    body = await request.json()
    message = body.get("message", {})
    data_b64 = message.get("data")
    if not data_b64:
        raise HTTPException(status_code=400, detail="Missing data")

    try:
        decoded = base64.b64decode(data_b64).decode("utf-8")
        payload = json.loads(decoded)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Invalid Pub/Sub message") from exc

    job_type = payload.get("type")
    if job_type == "process_item":
        await handle_process_item(payload)

    return {"status": "ok"}


async def handle_process_item(payload: dict):
    item_id = payload.get("item_id")
    if not item_id:
        return
    # For demonstration we just load the item to prove DB access works; real logic would go here.
    db_gen = get_db()
    db = next(db_gen)
    try:
        _ = db.get(ExampleItem, item_id)
    finally:
        db_gen.close()  # type: ignore[call-arg]
