"""Admin commands.

    python -m app.cli migrate
    python -m app.cli create-user --email a@b.c --password ... --role official
    python -m app.cli run-alerts                 # evaluate subscriptions after a new forecast
    python -m app.cli export-reports             # verified reports per ward -> used by ml.publish
    python -m app.cli load-wards                 # ward polygons -> PostGIS (Postgres only)
"""
from __future__ import annotations

import argparse
import json

import pandas as pd

from app import db
from app.security import ROLES, hash_password


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="app.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate")
    p = sub.add_parser("create-user")
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--name")
    p.add_argument("--role", choices=ROLES, default="official")
    sub.add_parser("run-alerts")
    sub.add_parser("export-reports")
    sub.add_parser("load-wards")
    args = ap.parse_args(argv)

    db.migrate()
    if args.cmd == "migrate":
        print("migrations applied")
    elif args.cmd == "create-user":
        if db.fetchone("SELECT id FROM users WHERE email = ?", (args.email.lower(),)):
            db.execute("UPDATE users SET role = ?, password_hash = ? WHERE email = ?",
                       (args.role, hash_password(args.password), args.email.lower()))
            print("updated existing user")
        else:
            db.insert("users", {"id": db.new_id(), "email": args.email.lower(), "name": args.name,
                                "password_hash": hash_password(args.password), "role": args.role, "language": "en",
                                "created_at": db.now()})
            print(f"created {args.role} {args.email}")
    elif args.cmd == "run-alerts":
        from app.services.alerts.engine import evaluate_subscriptions
        print(json.dumps(evaluate_subscriptions(), indent=2))
    elif args.cmd == "export-reports":
        from app.services.reports import verified_reports_by_ward
        from pipeline.config import get_paths
        counts = verified_reports_by_ward()
        out = get_paths().processed / "verified_reports_by_ward.csv"
        pd.DataFrame([{"ward_id": k, "reports_4w": v} for k, v in counts.items()],
                     columns=["ward_id", "reports_4w"]).to_csv(out, index=False)
        print(f"{len(counts)} wards -> {out}")
    elif args.cmd == "load-wards":
        from app.settings import get_settings
        if not get_settings().is_postgres:
            raise SystemExit("load-wards needs Postgres + PostGIS (DATABASE_URL=postgresql://...)")
        from pipeline.config import REPO_ROOT, load_city
        cfg = load_city()["geography"]
        gj = json.loads((REPO_ROOT / cfg["wards_geojson"]).read_text())
        for f in gj["features"]:
            db.execute("INSERT INTO wards (ward_id, ward_name, geom) VALUES (?, ?, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(?), 4326))) "
                       "ON CONFLICT (ward_id) DO UPDATE SET ward_name = EXCLUDED.ward_name, geom = EXCLUDED.geom",
                       (str(f["properties"][cfg["ward_id_key"]]), f["properties"][cfg["ward_name_key"]], json.dumps(f["geometry"])))
        print(f"loaded {len(gj['features'])} wards into PostGIS")


if __name__ == "__main__":
    main()
