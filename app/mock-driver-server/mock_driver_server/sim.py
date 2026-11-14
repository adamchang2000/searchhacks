import json
import random
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

from ninja import Router
from ninja.errors import HttpError

FIELDS = ("purchase_conversion", "user_confirmed_outcome", "user_stopped_following_up")
router = Router(tags=["simulation"])
DB = Path(__file__).resolve().parents[1] / "db.sqlite3"
OPTIMIZER = "https://optimizer.int.exe.xyz"
_lock = threading.Lock()
_active = {}

DEFAULT = {
    "total_queries": 500,
    "rate_per_second": 2,
    "providers": ["exa", "parallel", "brave"],
    "categories": [
        {"id": 18, "label": "Shopping", "weight": 5, "queries": [
            {"text": "best running shoes for flat feet", "weight": 3},
            {"text": "buy a waterproof ski jacket today", "weight": 2},
            {"text": "durable 8x10 rug for a home with a dog", "weight": 2}]},
        {"id": 67, "label": "Travel", "weight": 3, "queries": [
            {"text": "weekend flights from SFO to New York", "weight": 2},
            {"text": "hotels near Yosemite with EV charging", "weight": 1}]},
        {"id": 1227, "label": "Computer Science", "weight": 2, "queries": [
            {"text": "how does BM25 ranking work", "weight": 2},
            {"text": "Django Ninja OpenAPI schema export", "weight": 1}]}
    ],
    "success_rates": {
        "18": {"exa": 0.7, "parallel": 0.5, "brave": 0.35},
        "67": {"exa": 0.4, "parallel": 0.75, "brave": 0.45},
        "1227": {"exa": 0.5, "parallel": 0.45, "brave": 0.8}
    }
}

def now():
    return datetime.now(timezone.utc).isoformat()

@contextmanager
def db():
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS sim_config (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS sim_runs (
        id TEXT PRIMARY KEY, created_at TEXT NOT NULL, ended_at TEXT,
        status TEXT NOT NULL, config TEXT NOT NULL, issued INTEGER NOT NULL DEFAULT 0,
        completed INTEGER NOT NULL DEFAULT 0, errors INTEGER NOT NULL DEFAULT 0)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS sim_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, created_at TEXT NOT NULL,
        category_id INTEGER NOT NULL, query TEXT NOT NULL, provider TEXT,
        is_good INTEGER, error TEXT)""")
    if "feedback" not in {row["name"] for row in conn.execute("PRAGMA table_info(sim_events)")}:
        conn.execute("ALTER TABLE sim_events ADD COLUMN feedback TEXT")
    for column, kind in (("goodness", "REAL"), ("feedback_submitted_at", "TEXT")):
        if column not in {row["name"] for row in conn.execute("PRAGMA table_info(sim_events)")}:
            conn.execute("ALTER TABLE sim_events ADD COLUMN " + column + " " + kind)
    conn.execute("INSERT OR IGNORE INTO sim_config VALUES (1, ?)", (json.dumps(DEFAULT),))
    try:
        with conn:
            yield conn
    finally:
        conn.close()

def normalize(config):
    for rates in config["success_rates"].values():
        for provider, value in rates.items():
            if isinstance(value, (int, float)):
                rates[provider] = {"user_confirmed_outcome": value}
    return config

def validate(config):
    if not isinstance(config, dict):
        raise HttpError(400, "Scenario must be an object")
    try:
        total = config["total_queries"]
        rate = config["rate_per_second"]
        providers = config["providers"]
        cats = config["categories"]
        rates = config["success_rates"]
        if type(total) is not int or not 1 <= total <= 1000000:
            raise ValueError("total_queries must be 1 to 1000000")
        if type(rate) not in (int, float) or not 0.1 <= rate <= 100:
            raise ValueError("rate_per_second must be 0.1 to 100")
        if not isinstance(providers, list) or not providers or len(set(providers)) != len(providers) or not all(isinstance(p, str) and p for p in providers):
            raise ValueError("providers must be a nonempty list of unique names")
        if not isinstance(cats, list) or not cats or len({c["id"] for c in cats}) != len(cats):
            raise ValueError("categories must have unique IDs")
        for cat in cats:
            if type(cat["id"]) is not int or type(cat["weight"]) not in (int, float) or cat["weight"] <= 0:
                raise ValueError("category IDs and weights are invalid")
            if not isinstance(cat["label"], str) or not cat["label"].strip():
                raise ValueError("category label is required")
            if not cat["queries"]:
                raise ValueError("each category needs queries")
            for query in cat["queries"]:
                if not isinstance(query["text"], str) or not query["text"].strip() or type(query["weight"]) not in (int, float) or query["weight"] <= 0:
                    raise ValueError("query text and positive weight are required")
            for provider in providers:
                record = rates[str(cat["id"])][provider]
                if not isinstance(record, dict) or not record or any(k not in FIELDS for k in record):
                    raise ValueError("Configure at least one outcome probability per provider")
                for probability in record.values():
                    if type(probability) not in (int, float) or not 0 <= probability <= 1:
                        raise ValueError("Outcome probabilities must be between 0 and 1")
    except (KeyError, TypeError, ValueError) as exc:
        raise HttpError(400, str(exc))
    return config

def call(path, payload):
    request = Request(OPTIMIZER + path, data=json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=15) as response:
        return json.load(response)

def work(run_id, control):
    with db() as conn:
        config = normalize(json.loads(conn.execute("SELECT config FROM sim_runs WHERE id=?", (run_id,)).fetchone()["config"]))
    categories = config["categories"]
    try:
        for query_index in range(config["total_queries"]):
            while not control["resume"].wait(timeout=0.2):
                if control["stop"].is_set():
                    break
            if control["stop"].is_set():
                break
            category = random.choices(categories, weights=[c["weight"] for c in categories])[0]
            query = random.choices(category["queries"], weights=[q["weight"] for q in category["queries"]])[0]["text"]
            with db() as conn:
                conn.execute("UPDATE sim_runs SET issued=issued+1 WHERE id=?", (run_id,))
            provider, feedback, error = None, {}, None
            goodness, submitted_at = random.random(), None
            try:
                # The category is known, so skip the optimizer's (paid) jev classification and make
                # it route on the same category that success_rates are keyed by.
                route = call("/api/which_search", {"query": query, "available_providers": config["providers"],
                                                   "override_query_category": category["id"]})
                provider = route["provider"]
                probabilities = config["success_rates"][str(category["id"])][provider]
                # Synthetic sessions contain three queries. Cessation is observed only at
                # the end of a multi-query session; earlier searches leave it unknown.
                feedback = {key: goodness >= 1 - probability for key, probability in probabilities.items()
                            if key != "user_stopped_following_up" or query_index % 3 == 2}
                if feedback:
                    call("/api/submit_feedback", {"feedback_token": route["feedback_token"], "feedback": feedback})
                    submitted_at = now()
            except Exception as exc:
                error = str(exc)[:500]
            with db() as conn:
                conn.execute("INSERT INTO sim_events (run_id,created_at,category_id,query,provider,feedback,error,goodness,feedback_submitted_at) VALUES (?,?,?,?,?,?,?,?,?)",
                             (run_id, now(), category["id"], query, provider, json.dumps(feedback), error, goodness, submitted_at))
                conn.execute("UPDATE sim_runs SET completed=completed+1, errors=errors+? WHERE id=?",
                             (int(error is not None), run_id))
            if control["stop"].wait(1 / config["rate_per_second"]):
                break
        status = "stopped" if control["stop"].is_set() else "completed"
    except Exception:
        status = "failed"
    with db() as conn:
        conn.execute("UPDATE sim_runs SET status=?, ended_at=? WHERE id=?", (status, now(), run_id))
    with _lock:
        _active.pop(run_id, None)

@router.get("/scenario")
def scenario(request):
    with db() as conn:
        return normalize(json.loads(conn.execute("SELECT body FROM sim_config WHERE id=1").fetchone()["body"]))

@router.put("/scenario")
def save_scenario(request):
    body = json.loads(request.body)
    validate(body)
    with db() as conn:
        conn.execute("UPDATE sim_config SET body=? WHERE id=1", (json.dumps(body),))
    return {"ok": True}

@router.get("/runs")
def runs(request):
    with db() as conn:
        return [dict(row) for row in conn.execute("SELECT id,created_at,ended_at,status,issued,completed,errors FROM sim_runs ORDER BY created_at DESC LIMIT 20")]

@router.post("/runs")
def start(request):
    with db() as conn:
        if conn.execute("SELECT 1 FROM sim_runs WHERE status IN ('running','paused','stopping') LIMIT 1").fetchone():
            raise HttpError(409, "A run is already active")
        config = validate(normalize(json.loads(conn.execute("SELECT body FROM sim_config WHERE id=1").fetchone()["body"])))
        run_id = str(uuid4())
        conn.execute("INSERT INTO sim_runs (id,created_at,status,config) VALUES (?,?,?,?)",
                     (run_id, now(), "running", json.dumps(config)))
    control = {"resume": threading.Event(), "stop": threading.Event()}
    control["resume"].set()
    with _lock:
        _active[run_id] = control
    threading.Thread(target=work, args=(run_id, control), daemon=True).start()
    return {"id": run_id}

@router.post("/runs/{run_id}/{action}")
def change_run(request, run_id: UUID, action: str):
    if action not in ("pause", "resume", "stop"):
        raise HttpError(404, "Unknown action")
    key = str(run_id)
    with _lock:
        control = _active.get(key)
    if control is None:
        raise HttpError(409, "Run is not active")
    with db() as conn:
        row = conn.execute("SELECT status FROM sim_runs WHERE id=?", (key,)).fetchone()
        if not row or row["status"] not in ("running", "paused"):
            raise HttpError(409, "Run is finished")
        if action == "pause" and row["status"] != "running" or action == "resume" and row["status"] != "paused":
            raise HttpError(409, "Invalid state transition")
        if action == "pause":
            control["resume"].clear()
            status = "paused"
        elif action == "resume":
            control["resume"].set()
            status = "running"
        else:
            control["stop"].set()
            control["resume"].set()
            status = "stopping"
        conn.execute("UPDATE sim_runs SET status=? WHERE id=?", (status, key))
    return {"ok": True}

@router.get("/events")
def events(request, run_id: UUID, limit: int = 100):
    with db() as conn:
        rows = conn.execute("SELECT * FROM sim_events WHERE run_id=? ORDER BY id DESC LIMIT ?",
                            (str(run_id), max(1, min(limit, 500)))).fetchall()
        return [{**dict(row), "feedback": json.loads(row["feedback"]) if row["feedback"] else None} for row in rows]

@router.get("/timeseries")
def timeseries(request, run_id: UUID):
    end = time.time()
    start = end - 60
    with db() as conn:
        rows = conn.execute(
            """SELECT provider, query, goodness, feedback, feedback_submitted_at
               FROM sim_events WHERE run_id=? AND feedback_submitted_at >= ?
               AND goodness IS NOT NULL ORDER BY id""",
            (str(run_id), datetime.fromtimestamp(start, timezone.utc).isoformat()),
        ).fetchall()
    points = [{"provider": row["provider"], "query": row["query"], "goodness": row["goodness"],
               "feedback": json.loads(row["feedback"]),
               "timestamp": datetime.fromisoformat(row["feedback_submitted_at"]).timestamp()} for row in rows]
    return {"providers": sorted({p["provider"] for p in points}), "points": points, "start": start, "end": end}
