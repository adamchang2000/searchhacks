import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
import uvicorn

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/dev.json")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    cfg = Path(args.config).resolve()
    envfile = json.loads(cfg.read_text()).get("env_file")
    if envfile:
        envfile = Path(envfile)
        load_dotenv(envfile if envfile.is_absolute() else cfg.parent / envfile)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mock_driver_server.settings")
    db_path = Path(__file__).resolve().parents[1] / "db.sqlite3"
    with sqlite3.connect(db_path) as db:
        try:
            db.execute("UPDATE sim_runs SET status=?, ended_at=? WHERE status IN (?, ?, ?)",
                       ("failed", datetime.now(timezone.utc).isoformat(), "running", "paused", "stopping"))
        except sqlite3.OperationalError as exc:
            if "no such table" not in str(exc):
                raise
    uvicorn.run("mock_driver_server.asgi:application", host=args.host, port=args.port)
