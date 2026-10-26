"""Alert delivery worker.

    python -m app.services.alerts.worker            # run forever (docker-compose service "worker")

Loop: every minute push due alerts (quiet hours over) onto the queue; consume the queue, render the
message in the subscriber's language, send it, record the result. Failed sends are retried 3 times.
"""
from __future__ import annotations

import logging
import os
import socket
import time

from app import db
from app.geo import ward_name
from app.forecast_store import get_bundle
from app.services.alerts.channels import DeliveryError, send
from app.services.alerts.engine import dispatch_due
from app.services.alerts.queue import get_queue
from app.services.alerts.unsubscribe import unsubscribe_link
from app.services.alerts.templates import render
from app.settings import get_settings

log = logging.getLogger("alerts.worker")


def deliver(alert_id: str) -> str:
    a = db.fetchone("SELECT * FROM alerts WHERE id = ?", (alert_id,))
    if not a or a["status"] not in ("dispatched", "queued"):
        return "skipped"
    sub = db.fetchone("SELECT * FROM subscriptions WHERE id = ?", (a["subscription_id"],))
    if not sub or not sub["active"]:
        db.update("alerts", alert_id, {"status": "suppressed", "reason": "unsubscribed"})
        return "suppressed"
    bundle = get_bundle() or {}
    week = next((f["week_end"] for f in bundle.get("forecast", []) if f["horizon"] == a["horizon"]), "")
    link = f"{get_settings().public_web_url}/map?ward={a['ward_id']}&ref=alert&a={alert_id}"
    subject, body = render(sub["language"], a["band"], sub["label"], ward_name(a["ward_id"]), week, link,
                           channel=a["channel"], unsubscribe_link=unsubscribe_link(sub["id"]))
    to = sub["destination_email"] if a["channel"] == "email" else sub["destination_phone"]
    attempts = 0
    while True:
        try:
            send(a["channel"], to, subject, body)
            db.update("alerts", alert_id, {"status": "sent", "sent_at": db.now()})
            return "sent"
        except DeliveryError as e:
            attempts += 1
            if attempts >= 3:
                db.update("alerts", alert_id, {"status": "failed", "reason": str(e)[:200]})
                return "failed"
            time.sleep(2 ** attempts)


def run_forever() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    q = get_queue()
    consumer = f"{socket.gethostname()}-{os.getpid()}"
    last_dispatch = 0.0
    log.info("alerts worker started as %s (dry_run=%s)", consumer, get_settings().alerts_dry_run)
    while True:
        if time.time() - last_dispatch > 60:
            n = dispatch_due()
            if n:
                log.info("dispatched %d due alerts", n)
            last_dispatch = time.time()
        for msg_id, alert_id in q.get(consumer, block_ms=5000):
            result = deliver(alert_id)
            q.ack(msg_id)
            log.info("alert %s -> %s", alert_id, result)


if __name__ == "__main__":
    db.migrate()
    run_forever()
