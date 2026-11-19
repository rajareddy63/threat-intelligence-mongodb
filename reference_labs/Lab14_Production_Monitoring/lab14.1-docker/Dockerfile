FROM mongo:7.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY lab14.1-docker/requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/requirements.txt
COPY lab14.1-docker/app.py lab14.1-docker/test_app.py lab14.1-docker/webhook_sink.py /app/
COPY lab14.2-backup-benchmark/scripts/ /scripts/
COPY lab14.1-docker/entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh /scripts/*.sh

EXPOSE 8080
ENTRYPOINT ["/entrypoint.sh"]
CMD ["dashboard"]
