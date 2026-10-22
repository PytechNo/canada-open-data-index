# The nightly updater: the repo's scripts, plus the committed snapshot (raw/, docs/) that seeds an empty volume.
FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY . .
CMD ["bash", "deploy/updater.sh"]
