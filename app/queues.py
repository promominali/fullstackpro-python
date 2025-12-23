from __future__ import annotations

import json
from typing import Any

from google.cloud import pubsub_v1

from .config import settings


_publisher: pubsub_v1.PublisherClient | None = None


def get_publisher() -> pubsub_v1.PublisherClient | None:
    global _publisher
    if not settings.gcp_project_id or not settings.pubsub_topic:
        return None
    if _publisher is None:
        _publisher = pubsub_v1.PublisherClient()
    return _publisher


def publish_event(data: dict[str, Any]) -> None:
    """Publish a small JSON payload to the configured Pub/Sub topic.

    In production, ensure the service account for this service has the
    pubsub.publisher role on the topic.
    """

    publisher = get_publisher()
    if publisher is None:
        # In dev/local, we simply no-op.
        return

    topic_path = publisher.topic_path(settings.gcp_project_id, settings.pubsub_topic)
    payload = json.dumps(data).encode("utf-8")
    future = publisher.publish(topic_path, payload)
    future.add_done_callback(lambda f: f.exception() if f.exception() else None)
