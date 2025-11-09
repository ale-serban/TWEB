import json, random, time, uuid, os
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
CLIENT_ID = f"sim-{uuid.uuid4().hex[:8]}"

PRODUCT_IDS  = ["SKU-1001","SKU-1002","SKU-2003"]
LOCATION_IDS = ["WH-RO-CLUJ","WH-RO-B","TRUCK-42"]

def now_iso(): return datetime.now(timezone.utc).isoformat()

def gen_gps():
    base_lat, base_lon = 46.77, 23.59
    return {
        "lat": round(base_lat + random.uniform(-0.01, 0.01), 6),
        "lon": round(base_lon + random.uniform(-0.01, 0.01), 6),
        "speed_kmh": round(random.uniform(0, 70), 1)
    }

def gen_stock():
    level = max(0, int(random.gauss(120, 20)))
    return {"level": level, "reorder_point": 80, "safety_stock": 40}

def gen_env():
    temp = round(random.uniform(2, 12), 1)  # >8°C = alertă lanț rece
    hum  = round(random.uniform(30, 80), 1)
    return {"temp_c": temp, "humidity_pct": hum}

def make_payload(sensor_type):
    return {
        "id": str(uuid.uuid4()),
        "ts": now_iso(),               # moment generare la sursă
        "productId": random.choice(PRODUCT_IDS),
        "locationId": random.choice(LOCATION_IDS),
        "sensor": sensor_type,
        "data": (
            gen_gps()   if sensor_type=="gps"   else
            gen_stock() if sensor_type=="stock" else
            gen_env()
        )
    }

def main():
    client = mqtt.Client(client_id=CLIENT_ID, clean_session=True)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    client.loop_start()
    topics = {"gps":"sc/telemetry/gps","stock":"sc/telemetry/stock","env":"sc/telemetry/env"}
    print(f"[SIM] Connected to MQTT {MQTT_HOST}:{MQTT_PORT} as {CLIENT_ID}")

    try:
        while True:
            sensor = random.choice(list(topics.keys()))
            payload = make_payload(sensor)
            client.publish(topics[sensor], json.dumps(payload), qos=0, retain=False)
            print(f"[PUB] {topics[sensor]} {payload}")
            time.sleep(random.uniform(1.0, 2.0))
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop(); client.disconnect()

if __name__ == "__main__":
    main()
