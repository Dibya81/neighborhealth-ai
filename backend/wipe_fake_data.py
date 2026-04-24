import sys
import os
sys.path.append(os.getcwd())
from db.client import get_supabase
from datetime import date
sb = get_supabase()
tod = date.today().isoformat()
res = sb.table("ward_risk_scores").delete().neq("score_date", "1970-01-01").execute()
print(f"Deleted old scores. Count: {len(res.data)}")
from services.risk_service import run_prediction_pipeline
run_prediction_pipeline()
print("Pipeline run completed with clean data.")
