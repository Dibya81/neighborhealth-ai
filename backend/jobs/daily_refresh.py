"""
Daily Refresh Pipeline
=======================
Main cron job entry point.

Triggered two ways:
  1. GitHub Actions cron at 6:00 AM IST (00:30 UTC):
     POST /api/v1/admin/trigger-refresh → calls run_prediction_pipeline()

  2. Direct execution for local testing:
     python jobs/daily_refresh.py

Pipeline flow:
  Weather API → Feature Engineering → XGBoost Inference → DB Write → Alert Dispatch

Expected runtime: ~30 seconds for 198 wards.
"""

import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.logger import get_logger
from services.risk_service import run_prediction_pipeline

logger = get_logger("CRON")

def main():
    logger.info("Daily refresh started")
    start_time = time.time()

    try:
        # ── Phase 1: Risk prediction pipeline ─────────────────────────────────
        summary = run_prediction_pipeline()
        elapsed = round(time.time() - start_time, 1)
        
        # summary logging is already handled in risk_service.py [ML]
        
        # ── Phase 2: Alert dispatch ────────────────────────────────────────────
        try:
            from jobs.alert_dispatcher import dispatch_alerts
            dispatch_alerts()
        except Exception as alert_err:
            logger.error(f"Alert dispatch failed: {alert_err}")

        logger.info(f"Daily refresh complete ({elapsed}s)")
        return summary

    except Exception as e:
        logger.error(f"Daily refresh failed: {e}")
        raise


if __name__ == "__main__":
    result = main()
    print("\nResult:", result)
