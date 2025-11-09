# app.py — DEMO ONLY (no backend calls)
import math, random, time
from datetime import datetime, timedelta

import pandas as pd
import pydeck as pdk
import streamlit as st

# ---------------- UI / Page ----------------
st.set_page_config(page_title="Supply Chain Edge+Cloud — DEMO", layout="wide")
st.title("📦 IoT Edge + Cloud — Supply Chain Dashboard")

with st.sidebar:
    st.caption("Settings")
    refresh_ms = st.number_input("Refresh (ms)", 1000, 30000, 5000, 500)
    recent_sec = st.number_input("Recency sec", 30, 900, 120, 30)
    st.markdown(
        "<small>This settings can be made by the user. ",
        unsafe_allow_html=True,
    )

# ---------------- Helpers (demo generators) ----------------
def _rng_tick(refresh_ms: int) -> int:
    """Schimbă seed-ul la fiecare fereastră de refresh, pentru animație stabilă."""
    return int(time.time() * 1000) // int(refresh_ms)

def demo_metrics(tick: int) -> dict:
    rnd = random.Random(tick)
    total_rows_base = 2500 + tick % 1800             # crește „în timp”
    alerts = rnd.randint(3, 18)
    # mică oscilație sinusoidală pentru latență
    latency = 20 + 8 * math.sin(tick / 5.0) + rnd.uniform(-2.0, 2.0)
    return {
        "total_rows": int(total_rows_base + rnd.randint(-40, 40)),
        "alerts": int(alerts),
        "avg_edge_latency_ms": round(max(0.5, latency), 2),
    }

CLJ = (46.7712, 23.6236)  # Cluj-Napoca (lat, lon)

def demo_latest_gps(tick: int, n=18) -> pd.DataFrame:
    rnd = random.Random(1000 + tick)  # seed stabil per tick
    rows = []
    for i in range(n):
        # împrăștiem punctele ~15–25 km în jurul Clujului
        dlat = rnd.uniform(-0.22, 0.22)
        dlon = rnd.uniform(-0.35, 0.35)
        lat = CLJ[0] + dlat
        lon = CLJ[1] + dlon
        prod = rnd.choice(["SKU-1001", "SKU-1002", "SKU-2003", "SKU-2004"])
        loc  = rnd.choice(["WH-RO-CLUJ", "WH-RO-B", "TRUCK-42"])
        rows.append({
            "productId": prod,
            "locationId": loc,
            "lat": lat,
            "lon": lon,
            "ingest_ts": (datetime.utcnow() - timedelta(seconds=rnd.randint(0, 90))).isoformat() + "Z",
        })
    return pd.DataFrame(rows)

def demo_events(tick: int, n=20) -> pd.DataFrame:
    rnd = random.Random(2000 + tick)
    sensors = ["gps", "env", "stock"]
    products = ["SKU-1001", "SKU-1002", "SKU-2003", "SKU-2004", None]
    locs = ["WH-RO-CLUJ", "WH-RO-B", "TRUCK-42", None]
    rows = []
    now = datetime.utcnow()
    for i in range(n):
        ts = now - timedelta(seconds=i * rnd.randint(3, 7))
        rows.append({
            "when": ts.replace(microsecond=0),
            "sensor": rnd.choice(sensors),
            "productId": rnd.choice(products),
            "locationId": rnd.choice(locs),
            "edge_latency_ms": rnd.randint(2, 80),
            "edge_alert": rnd.choice([None, "", "TEMP_OVER_8.0", "STOCK_LOW", "GPS_LOST"]),
        })
    df = pd.DataFrame(rows)
    # ordonează descrescător după timp
    return df.sort_values("when", ascending=False).reset_index(drop=True)

# ---------------- KPI ----------------
tick = _rng_tick(refresh_ms)
m = demo_metrics(tick)
colA, colB, colC, colD = st.columns(4)
colA.metric("Total mesaje", m["total_rows"])
colB.metric("Alerte (edge)", m["alerts"])
colC.metric("Latență medie edge→cloud (ms)", m["avg_edge_latency_ms"])
colD.markdown("&nbsp;", unsafe_allow_html=True)

st.markdown("---")
left, right = st.columns([2, 1])

# ---------------- Harta GPS ----------------
with left:
    st.subheader("📍 Poziții curente (GPS)")
    gps_df = demo_latest_gps(tick)
    if not gps_df.empty:
        view_state = pdk.ViewState(
            latitude=float(gps_df["lat"].mean()),
            longitude=float(gps_df["lon"].mean()),
            zoom=8,
        )
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=gps_df,
            get_position='[lon, lat]',
            get_fill_color='[200, 30, 0, 180]',
            get_radius=160,
            pickable=True,
        )
        tooltip = {
            "html": "<b>Prod:</b> {productId}<br/><b>Loc:</b> {locationId}<br/><b>ts:</b> {ingest_ts}",
            "style": {"backgroundColor": "rgba(30,30,30,0.9)", "color": "white"},
        }
        st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip=tooltip))
    else:
        st.info("Nu există încă poziții GPS recente.")

# ---------------- Alerte & Evenimente ----------------
with right:
    st.subheader("🚨 Alerte și ultimele evenimente")
    df = demo_events(tick, n=28)
    show = df[["when", "sensor", "productId", "locationId"]]
    st.dataframe(show, use_container_width=True, height=520)

# ---------------- Auto-refresh ----------------
st.caption(f"Auto-refresh la fiecare {refresh_ms/1000:.1f}s • Recency: {recent_sec}s • DEMO mode")
# (Streamlit 1.39+) – reîmprospătare simplă fără APIs „experimental”
st.components.v1.html(
    f"<script>setTimeout(() => window.location.reload(), {int(refresh_ms)});</script>",
    height=0,
)
