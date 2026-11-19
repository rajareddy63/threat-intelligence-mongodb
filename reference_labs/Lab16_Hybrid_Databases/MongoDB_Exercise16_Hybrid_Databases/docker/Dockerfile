FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y gcc curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
CMD ["python", "/app/lab16.2-hybrid-service/demo_runner.py"]
