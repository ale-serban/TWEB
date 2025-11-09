FROM python:3.11-slim

# Evită prompt-urile interactive
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# deps de bază pentru compilare unor pachete
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# aplicația
COPY app.py .

EXPOSE 8501

# pornește Streamlit headless
CMD ["streamlit", "run", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0", "--browser.gatherUsageStats", "false"]
