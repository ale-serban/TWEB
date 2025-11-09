# 🏭 IoT Edge + Cloud Supply Chain Monitoring

This project simulates an IoT Supply Chain system using an Edge–Cloud architecture.  
It collects telemetry data (stock, environment, GPS), processes alerts at the Edge, and sends aggregated batches to the Cloud for storage and dashboard visualization.

---

## 📌 Components

| Component | Description |
|-----------|--------------|
| `sensor_sim.py` | Simulates IoT devices publishing MQTT telemetry |
| `edge/app.py` | Processes MQTT messages, enriches data, triggers alerts, batches & sends to Cloud |
| `cloud/app.py` | Receives and stores telemetry into DB, exposes API endpoints |
| `dashboard/app.py` | Streamlit dashboard for visualization |

---

## 🚀 How to Run (Local Setup)

### **1️ Clone the Repository**
```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>
```
### **2 Start the System (Docker)**
```bash
docker-compose up --build
```
### **3 Stop the System**
```bash
docker-compose down
```
