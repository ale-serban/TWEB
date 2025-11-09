# cloud-api/app.py
import os, json, sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Body, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

DB_PATH = os.environ.get("DB_PATH", "/data/cloud.db")
DEFAULT_RECENT_SEC = int(os.environ.get("RECENT_SEC", "300"))

app = FastAPI(title="Cloud API - SupplyChain")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# --- ADAUGĂ în cloud-api/app.py ---
from fastapi.responses import HTMLResponse

@app.get("/live/metrics", response_class=HTMLResponse)
def live_metrics(interval: int = 2000) -> str:
    return f"""<!doctype html>
<html><head><meta charset="utf-8" />
<title>cloud-api /metrics (live)</title>
<style>
  html,body {{ background:#0f1115; color:#e8e6e3; font:14px ui-monospace; margin:0; }}
  header {{ padding:10px 14px; border-bottom:1px solid #24262c; }}
  pre {{ margin:0; padding:14px; white-space:pre-wrap; }}
  .ok {{ color:#6ee7a2; }} .err {{ color:#f87171; }}
</style></head>
<body>
  <header>Polling: <b id="iv">{interval}</b> ms • Last: <b id="lu">-</b> • Status: <b id="st">-</b></header>
  <pre id="out">loading…</pre>
<script>
const out=document.getElementById('out'), lu=document.getElementById('lu'), st=document.getElementById('st');
const iv=parseInt(new URLSearchParams(location.search).get('interval')||'{interval}',10);
async function tick(){{
  try {{
    const r=await fetch('/metrics',{cache:'no-store'});
    st.textContent=r.status+' '+r.statusText; st.className=r.ok?'ok':'err';
    out.textContent=JSON.stringify(await r.json(),null,2);
    lu.textContent=new Date().toLocaleTimeString();
  }} catch(e){{ st.textContent='error'; st.className='err'; out.textContent=String(e); }}
}}
tick(); setInterval(tick,iv);
</script></body></html>"""

@app.get("/live/last", response_class=HTMLResponse)
def live_last(n: int = 10, interval: int = 2000) -> str:
    return f"""<!doctype html>
<html><head><meta charset="utf-8" />
<title>cloud-api /last?n={n} (live)</title>
<style>
  html,body {{ background:#0f1115; color:#e8e6e3; font:14px ui-monospace; margin:0; }}
  header {{ padding:10px 14px; border-bottom:1px solid #24262c; }}
  pre {{ margin:0; padding:14px; white-space:pre-wrap; }}
  .ok {{ color:#6ee7a2; }} .err {{ color:#f87171; }}
</style></head>
<body>
  <header>n=<b id="nn">{n}</b> • Polling: <b id="iv">{interval}</b> ms • Last: <b id="lu">-</b> • Status: <b id="st">-</b></header>
  <pre id="out">loading…</pre>
<script>
const out=document.getElementById('out'), lu=document.getElementById('lu'), st=document.getElementById('st');
const q=new URLSearchParams(location.search);
const iv=parseInt(q.get('interval')||'{interval}',10);
const n =parseInt(q.get('n')||'{n}',10);
async function tick(){{
  try {{
    const r=await fetch('/last?n='+encodeURIComponent(n),{{cache:'no-store'}});
    st.textContent=r.status+' '+r.statusText; st.className=r.ok?'ok':'err';
    out.textContent=JSON.stringify(await r.json(),null,2);
    lu.textContent=new Date().toLocaleTimeString();
  }} catch(e){{ st.textContent='error'; st.className='err'; out.textContent=String(e); }}
}}
tick(); setInterval(tick,iv);
</script></body></html>"""


# -------------------------- DB helpers --------------------------
def get_db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con

db = get_db()

def init_schema() -> None:
    cur = db.cursor()
    cur.executescript(
        """
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS telemetry (
          id              TEXT PRIMARY KEY,
          ts              TEXT NOT NULL,
          ingest_ts       TEXT NOT NULL DEFAULT (datetime('now')),
          topic           TEXT,
          sensor          TEXT,
          productId       TEXT,
          locationId      TEXT,
          edge_alert      TEXT,
          edge_latency_ms INTEGER,
          data_json       TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_tel_ingest_ts  ON telemetry(ingest_ts);
        CREATE INDEX IF NOT EXISTS idx_tel_sensor     ON telemetry(sensor);
        CREATE INDEX IF NOT EXISTS idx_tel_prod_loc   ON telemetry(productId, locationId);
        """
    )
    db.commit()

init_schema()

def row_to_dict(r: sqlite3.Row) -> Dict[str, Any]:
    d = dict(r)
    return d

# -------------------------- Endpoints --------------------------
@app.get("/health")
def health():
    return {"status": "ok", "db": DB_PATH}
def _norm_id(item: dict, k1: str, k2: str) -> str | None:
    v = item.get(k1)
    if v is None:
        v = item.get(k2)
    return str(v) if v is not None else None

# ... în interiorul handler-ului /ingest, pentru fiecare `it` din items:
product_id = _norm_id(it, "productId", "product_id")
location_id = _norm_id(it, "locationId", "location_id")

sensor = it.get("sensor")
data_json = it.get("data") if isinstance(it.get("data"), dict) else it.get("data_json")
if isinstance(data_json, dict):
    data_json = json.dumps(data_json)

# edge meta
edge_alert = (it.get("_edge") or {}).get("alert")
edge_latency_ms = (it.get("_edge") or {}).get("latency_ms_sensor_to_edge")
topic = (it.get("_edge") or {}).get("topic")

# timpi
src_ts = it.get("ts")              # când a fost generat de „senzor”
ingest_ts = datetime.utcnow().isoformat() + "Z"  # când ajunge în cloud

# construiește row/insert exact ca în codul tău, dar folosind variabilele de mai sus:
# productId=product_id, locationId=location_id, sensor=sensor, data_json=data_json,
# ts=src_ts, ingest_ts=ingest_ts, edge_alert=edge_alert, edge_latency_ms=edge_latency_ms, topic=topic

@app.get("/metrics")
def metrics():
    cur = db.cursor()
    total = cur.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0]
    alerts = cur.execute("SELECT COUNT(*) FROM telemetry WHERE edge_alert IS NOT NULL").fetchone()[0]
    avg_lat = cur.execute(
        "SELECT AVG(edge_latency_ms) FROM telemetry WHERE edge_latency_ms IS NOT NULL"
    ).fetchone()[0]
    return {
        "total_rows": int(total),
        "alerts": int(alerts),
        "avg_edge_latency_ms": None if avg_lat is None else float(avg_lat),
    }

@app.get("/last")
def last(n: int = Query(200, ge=1, le=2000)):
    rows = db.execute(
        """
        SELECT id, ts, ingest_ts, topic, sensor,
               productId, locationId, edge_alert, edge_latency_ms, data_json
        FROM telemetry
        ORDER BY ingest_ts DESC
        LIMIT ?
        """,
        (n,),
    ).fetchall()
    return {"items": [row_to_dict(r) for r in rows]}

@app.get("/recent")
def recent(
    n: int = Query(200, ge=1, le=2000),
    seconds: int = Query(DEFAULT_RECENT_SEC, ge=1, le=86400),
):
    rows = db.execute(
        """
        SELECT id, ts, ingest_ts, topic, sensor,
               productId, locationId, edge_alert, edge_latency_ms, data_json
        FROM telemetry
        WHERE julianday('now') - julianday(ingest_ts) <= (? / 86400.0)
        ORDER BY ingest_ts DESC
        LIMIT ?
        """,
        (seconds, n),
    ).fetchall()
    return {"items": [row_to_dict(r) for r in rows]}

@app.get("/latest_gps")
def latest_gps():
    """
    Ultimul punct GPS pentru fiecare (productId, locationId).
    Compatibil cu SQLite.
    """
    rows = db.execute(
        """
        SELECT t1.*
        FROM telemetry t1
        JOIN (
          SELECT productId, locationId, MAX(ingest_ts) AS max_ts
          FROM telemetry
          WHERE sensor='gps'
          GROUP BY productId, locationId
        ) t2
        ON t1.productId=t2.productId
       AND t1.locationId=t2.locationId
       AND t1.ingest_ts=t2.max_ts
        WHERE t1.sensor='gps'
        ORDER BY t1.ingest_ts DESC
        """
    ).fetchall()
    return {"items": [row_to_dict(r) for r in rows]}

# -------------- Local dev (optional) --------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
