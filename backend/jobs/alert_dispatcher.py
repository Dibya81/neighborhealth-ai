import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.logger import get_logger
from db.diseases import get_all_diseases
from db.risk_scores import get_latest_scores_all_wards
from db.wards import get_all_wards
from db.subscriptions import (
    get_active_subscriptions_for_wards,
    log_alert_sent,
    already_alerted_today,
)
from services.alert_service import get_elevated_wards, is_ward_above_threshold, dispatch_to_subscriber

logger = get_logger("CRON")


def dispatch_alerts() -> dict:
    logger.info("Starting multi-disease alert dispatch...")

    all_diseases = get_all_diseases()
    if not all_diseases:
        logger.warning("No diseases found in registry — skipping.")
        return {"alerts_sent": 0, "reason": "no_diseases"}

    stats = {"sent": 0, "skipped_dedup": 0, "failed": 0, "disease_counts": {}}
    ward_names = {w["id"]: w["name"] for w in get_all_wards()}

    for disease in all_diseases:
        disease_id   = disease["id"]
        disease_name = disease["name"]

        all_scores = get_latest_scores_all_wards(disease=disease_id)
        if not all_scores:
            continue

        elevated_wards = get_elevated_wards(all_scores)
        if not elevated_wards:
            continue

        elevated_ward_ids = [s["ward_id"] for s in elevated_wards]
        score_by_ward     = {s["ward_id"]: s for s in elevated_wards}
        subscriptions     = get_active_subscriptions_for_wards(elevated_ward_ids)
        disease_sent      = 0

        for sub in subscriptions:
            ward_id    = sub["ward_id"]
            score_row  = score_by_ward.get(ward_id, {})
            risk_score = float(score_row.get("risk_score", 0))
            risk_level = score_row.get("risk_level", "high")

            if not sub.get("notify_diseases") or disease_id not in sub["notify_diseases"]:
                continue

            if not is_ward_above_threshold(risk_score, sub.get("threshold")):
                continue

            if already_alerted_today(sub["id"], disease_id=disease_id):
                stats["skipped_dedup"] += 1
                continue

            ward_name = ward_names.get(ward_id, f"Ward {ward_id}")

            try:
                result = dispatch_to_subscriber(sub, ward_name, disease_name, risk_score, risk_level)
                log_alert_sent(sub["id"], ward_id, risk_score, sub["contact_type"], disease_id=disease_id)
                stats["sent"] += 1
                disease_sent  += 1
                logger.info(
                    "Alert dispatched to ...%s | ward=%s | disease=%s | score=%.1f | status=%s",
                    sub["contact"][-4:], ward_id, disease_id, risk_score, result.get("status"),
                )
            except Exception as e:
                stats["failed"] += 1
                logger.error("Failed to dispatch %s alert for sub %s: %s", disease_id, sub["id"], e)

        stats["disease_counts"][disease_id] = disease_sent

    logger.info("Multi-disease dispatch complete: %s", stats)
    return stats


if __name__ == "__main__":
    result = dispatch_alerts()
    print("Dispatch result:", result)
