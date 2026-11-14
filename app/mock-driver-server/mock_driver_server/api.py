import os, signal, shutil, sqlite3, subprocess, threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4
from ninja import Field, Router, Schema
from ninja.errors import HttpError

health_router = Router()
runs_router = Router(tags=["runs"])
DB = Path(__file__).resolve().parents[1] / "db.sqlite3"
_processes = {}
_lock = threading.Lock()

@contextmanager
def connect():
    db = sqlite3.connect(DB, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS runs (
        id TEXT PRIMARY KEY, created_at TEXT NOT NULL, started_at TEXT,
        ended_at TEXT, status TEXT NOT NULL, optimizer_url TEXT NOT NULL,
        num_searches INTEGER NOT NULL, concurrency INTEGER NOT NULL,
        process_id INTEGER, exit_code INTEGER)""")
    try:
        with db:
            yield db
    finally:
        db.close()

def row_out(row):
    return dict(row)

class StartRun(Schema):
    optimizer_url: str = "https://optimizer.int.exe.xyz"
    num_searches: int = Field(500, ge=1, le=1000000)
    concurrency: int = Field(8, ge=1, le=256)

@health_router.get("")
def health(request):
    return {"status": "ok"}

def monitor(run_id, process):
    code = process.wait()
    with _lock:
        _processes.pop(run_id, None)
    with connect() as db:
        db.execute("UPDATE runs SET status=?, exit_code=?, ended_at=? WHERE id=? AND status IN ('running','paused')",
                   ("completed" if code == 0 else "failed", code, datetime.now(timezone.utc).isoformat(), run_id))

@runs_router.get("")
def list_runs(request, limit: int = 50):
    with connect() as db:
        return [row_out(r) for r in db.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 200)),))]

@runs_router.get("/{run_id}")
def get_run(request, run_id: UUID):
    with connect() as db:
        row = db.execute("SELECT * FROM runs WHERE id=?", (str(run_id),)).fetchone()
    if row is None:
        raise HttpError(404, "Run not found")
    return row_out(row)

@runs_router.post("")
def start_run(request, body: StartRun):
    repo = Path(__file__).resolve().parents[3]
    driver = repo / "app" / "mock-driver"
    tsx = repo / "node_modules" / "tsx" / "dist" / "cli.mjs"
    node = shutil.which("node")
    if not node or not tsx.exists():
        raise HttpError(503, "Install Node dependencies with npm ci from the repository root")
    with connect() as db:
        if db.execute("SELECT 1 FROM runs WHERE status IN ('running','paused') LIMIT 1").fetchone():
            raise HttpError(409, "A simulation is already running")
        run_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        proc = subprocess.Popen([node, str(tsx), "src/index.ts", "--server", body.optimizer_url,
                                 "--n", str(body.num_searches), "--concurrency", str(body.concurrency)],
                                cwd=driver, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=True)
        db.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?)",
                   (run_id, now, now, None, "running", body.optimizer_url, body.num_searches,
                    body.concurrency, proc.pid, None))
    with _lock:
        _processes[run_id] = proc
    threading.Thread(target=monitor, args=(run_id, proc), daemon=True).start()
    return get_run(request, UUID(run_id))

def control(request, run_id, action):
    run_id = str(run_id)
    with connect() as db:
        row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise HttpError(404, "Run not found")
        if row["status"] not in ("running", "paused"):
            raise HttpError(409, "Run is " + row["status"])
        with _lock:
            proc = _processes.get(run_id)
        if proc is None:
            raise HttpError(409, "Run process is not attached to this server")
        if action == "pause" and row["status"] == "running":
            os.kill(proc.pid, signal.SIGSTOP)
            status = "paused"
        elif action == "resume" and row["status"] == "paused":
            os.kill(proc.pid, signal.SIGCONT)
            status = "running"
        elif action == "stop":
            os.kill(proc.pid, signal.SIGCONT)
            proc.terminate()
            status = "stopped"
        else:
            raise HttpError(409, "Cannot " + action + " a run that is " + row["status"])
        ended = datetime.now(timezone.utc).isoformat() if status == "stopped" else None
        db.execute("UPDATE runs SET status=?, ended_at=COALESCE(?, ended_at) WHERE id=?", (status, ended, run_id))
    return {"ok": True}

@runs_router.post("/{run_id}/pause")
def pause(request, run_id: UUID):
    return control(request, run_id, "pause")
@runs_router.post("/{run_id}/resume")
def resume(request, run_id: UUID):
    return control(request, run_id, "resume")
@runs_router.post("/{run_id}/stop")
def stop(request, run_id: UUID):
    return control(request, run_id, "stop")
