from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..cache import cached
from ..db import get_db
from ..deps import authenticated_user_dep
from ..models import ExampleItem
from ..queues import publish_event


router = APIRouter()


@router.get("/items")
@cached(ttl=30)
async def list_items(db: Session = Depends(get_db)):
    items = db.query(ExampleItem).order_by(ExampleItem.created_at.desc()).limit(100).all()
    return [
        {"id": i.id, "slug": i.slug, "name": i.name, "description": i.description}
        for i in items
    ]


@router.post("/items/{item_id}/process")
async def process_item(item_id: int, user=Depends(authenticated_user_dep)):
    # Publish a background job to Pub/Sub to process this item
    publish_event({"type": "process_item", "item_id": item_id, "requested_by": user.id})
    return {"status": "queued"}
