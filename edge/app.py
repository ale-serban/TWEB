# edge-node/app.py
import json, os, threading, time
from datetime import datetime, timezone
from typing import List, Dict, Any

import requests
import paho.mqtt.client as mqtt
from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
CLOUD_INGEST_URL = os.getenv("CLOUD_INGEST_URL", "http://cloud-api:8000/ingest")

AGG_WINDOW_SEC = int(os.getenv("AGG_WINDOW_SEC", "5"))
ALERT_TEMP_MAX = float(os.getenv("ALERT_TEMP_MAX", "8.0"))

app = FastAPI(title="Edge Node")

buffer_lock = threading.Lock()
buffer: List[Dict[str, Any]] = []
metrics = {
    "batches_sent": 0,
    "messages_in": 0,
    "alerts": 0,
    "last_post_status": None
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def on_connect(client, userdata, flags, rc):
    print(f"[EDGE] MQTT connected rc={rc}")
    client.subscribe("sc/telemetry/#")

def on_message(client, userdata, msg):
    global buffer
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        metrics["messages_in"] += 1
        # îmbogățire metadate edge
        payload["_edge"] = {
            "topic": msg.topic,
            "received_ts": now_iso()
        }
        # alertă simplă: temperatură > prag
        if payload.get("sensor") == "env":
            temp = (payload.get("data") or {}).get("temp_c", 0)
            if isinstance(temp, (int, float)) and temp > ALERT_TEMP_MAX:
                payload["_edge"]["alert"] = f"TEMP_OVER_{ALERT_TEMP_MAX}"
                metrics["alerts"] += 1
        with buffer_lock:
            buffer.append(payload)
    except Exception as e:
        print("[EDGE] parse error:", e)

def poster_loop():
    global buffer
    session = requests.Session()
    while True:
        time.sleep(AGG_WINDOW_SEC)
        with buffer_lock:
            batch = buffer
            buffer = []
        if not batch:
            continue

        # calculează latența senzor->edge (ms)
        for item in batch:
            try:
                ts_src  = datetime.fromisoformat(str(item["ts"]).replace("Z", "+00:00"))
                ts_edge = datetime.fromisoformat(str(item["_edge"]["received_ts"]).replace("Z", "+00:00"))
                item["_edge"]["latency_ms_sensor_to_edge"] = int((ts_edge - ts_src).total_seconds() * 1000)
            except Exception:
                pass

        try:
            resp = session.post(CLOUD_INGEST_URL, json={"batch_ts": now_iso(), "items": batch}, timeout=10)
            metrics["batches_sent"] += 1
            metrics["last_post_status"] = f"{resp.status_code}"
            print(f"[EDGE] POST {CLOUD_INGEST_URL} size={len(batch)} status={resp.status_code}")
        except Exception as e:
            metrics["last_post_status"] = f"error:{e}"
            print("[EDGE] POST error:", e)

def run_mqtt():
    client = mqtt.Client(client_id="edge-node")
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    client.loop_forever()

@app.get("/health")
def health():
    return {"status": "ok", "metrics": metrics}

# ---------- Pagina LIVE pentru /health (auto-refresh în browser) ----------
@app.get("/live/health", response_class=HTMLResponse)
def live_health(interval: int = 2000) -> str:
    """
    Vizualizare live pentru /health.
    Exemplu: http://localhost:8081/live/health?interval=1500
    """
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>edge-node /health (live)</title>
<style>
  html,body {{ background:#0f1115; color:#e8e6e3; font:14px/1.4 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; margin:0; }}
  header {{ padding:10px 14px; border-bottom:1px solid #24262c; }}
  #info span {{ opacity:.8; margin-right:12px; }}
  pre {{ margin:0; padding:14px; white-space:pre-wrap; word-break:break-word; }}
  .ok {{ color:#6ee7a2; }} .err {{ color:#f87171; }}
</style>
</head>
<body>
  <header>
    <div id="info">
      <span>Polling: <b id="iv">{interval}</b> ms</span>
      <span>Last update: <b id="lu">-</b></span>
      <span>Status: <b id="st">-</b></span>
    </div>
  </header>
  <pre id="out">loading…</pre>
<script>
const out = document.getElementById('out');
const lu  = document.getElementById('lu');
const st  = document.getElementById('st');
const iv  = parseInt(new URLSearchParams(location.search).get('interval') || '{interval}', 10);

async function tick() {{
  try {{
    const r = await fetch('/health', {{ cache:'no-store' }});
    st.textContent = r.status + ' ' + r.statusText;
    st.className = (r.ok ? 'ok':'err');
    const j = await r.json();
    out.textContent = JSON.stringify(j, null, 2);
    lu.textContent = new Date().toLocaleTimeString();
  }} catch (e) {{
    st.textContent = 'error';
    st.className = 'err';
    out.textContent = String(e);
  }}
}}
tick();
setInterval(tick, iv);
</script>
</body>
</html>"""

def start_background():
    threading.Thread(target=run_mqtt,   daemon=True).start()
    threading.Thread(target=poster_loop, daemon=True).start()

start_background()
