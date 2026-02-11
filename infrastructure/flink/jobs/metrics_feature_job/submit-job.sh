#!/usr/bin/env bash
set -euo pipefail

JOBMANAGER_HOST="${FLINK_JOBMANAGER_HOST:-flink-jobmanager}"
JOBMANAGER_PORT="${FLINK_JOBMANAGER_PORT:-8081}"
REST="http://${JOBMANAGER_HOST}:${JOBMANAGER_PORT}"

BOOTSTRAP="${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}"
RAW_TOPIC="${KAFKA_RAW_TOPIC:-metrics.raw}"
PROCESSED_TOPIC="${KAFKA_PROCESSED_TOPIC:-metrics.processed}"

JOB_NAME="metrics-feature-job"

echo "[flink] Waiting for JobManager at ${REST} ..."
for i in $(seq 1 120); do
  if curl -fsS "${REST}/overview" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! curl -fsS "${REST}/overview" >/dev/null 2>&1; then
  echo "[flink] JobManager not reachable after timeout" >&2
  exit 1
fi

if curl -fsS "${REST}/jobs/overview" | grep -q "\"name\":\"${JOB_NAME}\""; then
  echo "[flink] ${JOB_NAME} already running"
else
  echo "[flink] Submitting ${JOB_NAME} (bootstrap=${BOOTSTRAP}, raw=${RAW_TOPIC}, processed=${PROCESSED_TOPIC})"
  flink run -d -m "${JOBMANAGER_HOST}:${JOBMANAGER_PORT}" \
    /opt/flink/jobs/metrics-feature-job.jar \
    --bootstrap.servers="${BOOTSTRAP}" \
    --topic.raw="${RAW_TOPIC}" \
    --topic.processed="${PROCESSED_TOPIC}"
fi

echo "[flink] Job submitter is idling"
tail -f /dev/null

