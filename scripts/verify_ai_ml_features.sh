#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
JUPYTER_CONTAINER="${JUPYTER_CONTAINER:-caduceus-jupyterlab}"

require() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require curl
require jq
require sha256sum
require docker
require timeout
require python3

echo "== Compose health =="
docker compose ps >/dev/null
docker compose ps | awk 'NR==1 || /caduceus-(nginx|ai-gateway-service|jupyterlab)/'
echo

echo "== ML registry: list + assignments =="
curl -fsS "${BASE_URL}/api/ai/ml/models" | jq '.models | length as $n | {count:$n, first: (.[0] // null)}'
curl -fsS "${BASE_URL}/api/ai/ml/assignments" | jq '.tasks as $t | .assignments as $a | {tasks:$t, assignments:$a}'
echo

MODEL_ID=""
PROJECT_ID=""
TOPOLOGY_ID=""
TMP_DIR="$(mktemp -d)"
cleanup() {
  set +e
  if [ -n "${MODEL_ID}" ]; then
    curl -sS -X PUT -H 'Content-Type: application/json' \
      -d '{"task":"anomaly_detection","model_id":"ml_builtin_anomaly_robust_zscore"}' \
      "${BASE_URL}/api/ai/ml/assignments" >/dev/null 2>&1 || true
    curl -sS -X DELETE "${BASE_URL}/api/ai/ml/models/${MODEL_ID}" >/dev/null 2>&1 || true
  fi
  if [ -n "${PROJECT_ID}" ]; then
    curl -sS -X DELETE "${BASE_URL}/api/projects/${PROJECT_ID}" >/dev/null 2>&1 || true
  fi
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

echo "== ML registry: upload + download + assign + delete =="
MODEL_FILE="${TMP_DIR}/test-model.onnx"
head -c 2048 /dev/urandom > "${MODEL_FILE}"

UPLOAD_JSON="${TMP_DIR}/upload.json"
curl -fsS -X POST \
  -F "file=@${MODEL_FILE}" \
  -F "task=anomaly_detection" \
  -F "name=Test ONNX Model" \
  -F "framework=onnx" \
  -F "algorithm=test" \
  -F "version=0.0.1" \
  -F "description=verify_ai_ml_features.sh" \
  "${BASE_URL}/api/ai/ml/models/upload" > "${UPLOAD_JSON}"

MODEL_ID="$(jq -r '.id' < "${UPLOAD_JSON}")"
if [ -z "${MODEL_ID}" ] || [ "${MODEL_ID}" = "null" ]; then
  echo "Upload did not return a model id" >&2
  exit 1
fi

jq '{id, task, name, framework, artifact_filename, artifact_sha256, artifact_size_bytes}' < "${UPLOAD_JSON}"

DOWNLOADED="${TMP_DIR}/download.bin"
curl -fsS -o "${DOWNLOADED}" "${BASE_URL}/api/ai/ml/models/${MODEL_ID}/download"

ORIG_SHA="$(sha256sum "${MODEL_FILE}" | awk '{print $1}')"
DL_SHA="$(sha256sum "${DOWNLOADED}" | awk '{print $1}')"
if [ "${ORIG_SHA}" != "${DL_SHA}" ]; then
  echo "SHA mismatch: orig=${ORIG_SHA} downloaded=${DL_SHA}" >&2
  exit 1
fi

curl -fsS -X PUT -H 'Content-Type: application/json' \
  -d "{\"task\":\"anomaly_detection\",\"model_id\":\"${MODEL_ID}\"}" \
  "${BASE_URL}/api/ai/ml/assignments" | jq .

ACTIVE="$(curl -fsS "${BASE_URL}/api/ai/ml/assignments" | jq -r '.assignments[] | select(.task=="anomaly_detection") | .model_id')"
if [ "${ACTIVE}" != "${MODEL_ID}" ]; then
  echo "Assignment did not update: got ${ACTIVE} expected ${MODEL_ID}" >&2
  exit 1
fi

curl -fsS -X PUT -H 'Content-Type: application/json' \
  -d '{"task":"anomaly_detection","model_id":"ml_builtin_anomaly_robust_zscore"}' \
  "${BASE_URL}/api/ai/ml/assignments" >/dev/null

curl -fsS -X DELETE "${BASE_URL}/api/ai/ml/models/${MODEL_ID}" | jq .
MODEL_ID=""
echo

echo "== PCAP API smoke check =="
for _ in $(seq 1 20); do
  if curl -fsS "${BASE_URL}/api/pcap/captures" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
curl -fsS "${BASE_URL}/api/pcap/captures" | jq .
echo

echo "== Shared mode + Flink + Decision Engine (streaming) =="

PROJECT_JSON="${TMP_DIR}/project.json"
PROJECT_NAME="verify-stream-$(date +%s)"
curl -fsS -X POST -H 'Content-Type: application/json' \
  -d "{\"name\":\"${PROJECT_NAME}\",\"description\":\"verify streaming control plane\"}" \
  "${BASE_URL}/api/projects" > "${PROJECT_JSON}"
PROJECT_ID="$(jq -r '.id' < "${PROJECT_JSON}")"
if [ -z "${PROJECT_ID}" ] || [ "${PROJECT_ID}" = "null" ]; then
  echo "Project create did not return id" >&2
  exit 1
fi

TOPOLOGY_ID="$(curl -fsS "${BASE_URL}/api/topologies?project_id=${PROJECT_ID}&limit=5" | jq -r '.[0].id')"
if [ -z "${TOPOLOGY_ID}" ] || [ "${TOPOLOGY_ID}" = "null" ]; then
  echo "Failed to resolve topology id for project ${PROJECT_ID}" >&2
  exit 1
fi

INFRA_JSON="${TMP_DIR}/infra.json"
curl -fsS -X POST "${BASE_URL}/api/topologies/${TOPOLOGY_ID}/infra/ensure" > "${INFRA_JSON}"
MODE="$(jq -r '.mode // ""' < "${INFRA_JSON}")"
echo "infra mode: ${MODE}"
if [ "${MODE}" = "isolated" ]; then
  echo "Expected shared infra mode, got isolated" >&2
  exit 1
fi

FLINK_UI_PORT="${FLINK_UI_PORT:-8088}"
curl -fsS "http://localhost:${FLINK_UI_PORT}/overview" | jq '{flink_version: .["flink-version"], taskmanagers: .taskmanagers}'
if ! curl -fsS "http://localhost:${FLINK_UI_PORT}/jobs/overview" | grep -q 'metrics-feature-job'; then
  echo "Flink metrics-feature-job not running" >&2
  exit 1
fi
echo

echo "== Spark + HDFS UI (shared) =="
SPARK_UI_PORT="${SPARK_UI_PORT:-8094}"
HDFS_UI_PORT="${HDFS_UI_PORT:-9870}"

curl -fsS "http://localhost:${SPARK_UI_PORT}/" | grep -qi 'Spark Master' || {
  echo "Spark UI not reachable on :${SPARK_UI_PORT}" >&2
  exit 1
}
curl -fsS "${BASE_URL}/infra-proxy/spark-shared/" | grep -qi 'Spark Master' || {
  echo "Spark UI proxy not reachable at /infra-proxy/spark-shared/" >&2
  exit 1
}
if curl -fsS -I "${BASE_URL}/infra-proxy/spark-shared/" | grep -qi '^x-frame-options:'; then
  echo "Expected Spark UI proxy to strip X-Frame-Options" >&2
  exit 1
fi

curl -fsS "http://localhost:${HDFS_UI_PORT}/dfshealth.html" | grep -qi 'Namenode information' || {
  echo "HDFS NameNode UI not reachable on :${HDFS_UI_PORT}" >&2
  exit 1
}
curl -fsS "${BASE_URL}/infra-proxy/hdfs-shared/dfshealth.html" | grep -qi 'Namenode information' || {
  echo "HDFS UI proxy not reachable at /infra-proxy/hdfs-shared/" >&2
  exit 1
}
if curl -fsS -I "${BASE_URL}/infra-proxy/hdfs-shared/" | grep -qi '^x-frame-options:'; then
  echo "Expected HDFS UI proxy to strip X-Frame-Options" >&2
  exit 1
fi

curl -fsS "http://localhost:8017/health" | jq .
curl -fsS "http://localhost:8017/api/stats" | jq '{running, received, emitted, errors}'

echo
echo "== Hive (shared) =="
HIVE_WEBUI_PORT="${HIVE_SERVER2_WEBUI_PORT:-10002}"

for _ in $(seq 1 30); do
  if curl -fsS "http://localhost:${HIVE_WEBUI_PORT}/" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

curl -fsS "http://localhost:${HIVE_WEBUI_PORT}/" >/dev/null || {
  echo "HiveServer2 Web UI not reachable on :${HIVE_WEBUI_PORT}" >&2
  exit 1
}
curl -fsS "${BASE_URL}/infra-proxy/hive-shared/" >/dev/null || {
  echo "HiveServer2 Web UI proxy not reachable at /infra-proxy/hive-shared/" >&2
  exit 1
}

echo
echo "== DB viewer UIs (shared) =="

for _ in $(seq 1 30); do
  if curl -fsS "${BASE_URL}/infra-proxy/pgadmin-shared/" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

PGADMIN_HTML="${TMP_DIR}/pgadmin.html"
curl -fsS -L -o "${PGADMIN_HTML}" "${BASE_URL}/infra-proxy/pgadmin-shared/" || {
  echo "pgAdmin UI proxy not reachable at /infra-proxy/pgadmin-shared/" >&2
  exit 1
}
grep -qi 'pgadmin' "${PGADMIN_HTML}" || {
  echo "pgAdmin UI did not return expected content" >&2
  exit 1
}
if curl -fsS -I "${BASE_URL}/infra-proxy/pgadmin-shared/" | grep -qi '^x-frame-options:'; then
  echo "Expected pgAdmin UI proxy to strip X-Frame-Options" >&2
  exit 1
fi

CRED_JSON="${TMP_DIR}/infra_creds.json"
curl -fsS "${BASE_URL}/api/infrastructure/topologies/${TOPOLOGY_ID}/infra/credentials" > "${CRED_JSON}"

MONGO_EXPRESS_USER="$(jq -r '.credentials.mongo_express.user // ""' < "${CRED_JSON}")"
MONGO_EXPRESS_PASSWORD="$(jq -r '.credentials.mongo_express.password // ""' < "${CRED_JSON}")"
if [ -z "${MONGO_EXPRESS_USER}" ] || [ -z "${MONGO_EXPRESS_PASSWORD}" ]; then
  echo "Mongo Express credentials missing from credentials API" >&2
  exit 1
fi
MONGO_EXPRESS_HTML="${TMP_DIR}/mongo_express.html"
curl -fsS -L -u "${MONGO_EXPRESS_USER}:${MONGO_EXPRESS_PASSWORD}" -o "${MONGO_EXPRESS_HTML}" "${BASE_URL}/infra-proxy/mongo-express-shared/" || {
  echo "Mongo Express UI proxy not reachable at /infra-proxy/mongo-express-shared/" >&2
  exit 1
}
grep -qi 'mongo' "${MONGO_EXPRESS_HTML}" || {
  echo "Mongo Express UI did not return expected content" >&2
  exit 1
}
if curl -fsS -I -u "${MONGO_EXPRESS_USER}:${MONGO_EXPRESS_PASSWORD}" "${BASE_URL}/infra-proxy/mongo-express-shared/" | grep -qi '^x-frame-options:'; then
  echo "Expected Mongo Express UI proxy to strip X-Frame-Options" >&2
  exit 1
fi

for _ in $(seq 1 30); do
  if curl -fsS "${BASE_URL}/infra-proxy/hue-shared/" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

HUE_HTML="${TMP_DIR}/hue.html"
curl -fsS -L -o "${HUE_HTML}" "${BASE_URL}/infra-proxy/hue-shared/" || {
  echo "Hue UI proxy not reachable at /infra-proxy/hue-shared/" >&2
  exit 1
}
grep -qi 'hue' "${HUE_HTML}" || {
  echo "Hue UI did not return expected content" >&2
  exit 1
}
if curl -fsS -I "${BASE_URL}/infra-proxy/hue-shared/" | grep -qi '^x-frame-options:'; then
  echo "Expected Hue UI proxy to strip X-Frame-Options" >&2
  exit 1
fi

docker exec -e HOME=/tmp/hive caduceus-hive-server2 bash -lc '
  mkdir -p "$HOME"
  /opt/hive/bin/beeline -u "jdbc:hive2://localhost:10000/default;auth=noSasl" -n hive -e "
    CREATE DATABASE IF NOT EXISTS caduceus_verify;
    SHOW DATABASES LIKE '\''caduceus_verify'\'';
    SELECT 1;
  "
' || {
  echo "Hive beeline query failed" >&2
  exit 1
}

echo "Producing synthetic metrics.raw and expecting metrics.processed + anomaly alert..."
python3 - <<PY | docker exec -i caduceus-kafka kafka-console-producer --bootstrap-server localhost:9092 --topic metrics.raw >/dev/null
import json, time

topology_id = "${TOPOLOGY_ID}"
device = "h1"
emu = "verify"
start_ms = int(time.time() * 1000)

rows = []
bytes_sent = 0
for i in range(12):
    ts = start_ms + i * 1000
    if i == 11:
        bytes_sent = 20000
    else:
        bytes_sent = i * 100
    metrics = {
        "topology_id": topology_id,
        "emulation_id": emu,
        "device": device,
        "source": "grpc",
        "timestamp": ts,
        "bytes_sent": bytes_sent,
        "bytes_received": bytes_sent,
        "packets_sent": bytes_sent // 10,
        "packets_received": bytes_sent // 10,
        "errors_in": 0,
        "errors_out": 0,
        "drops_in": 0,
        "drops_out": 0,
        "cpu_percent": 10.0,
        "memory_percent": 10.0,
    }
    env = {
        "topology_id": topology_id,
        "emulation_id": emu,
        "device": device,
        "source": "grpc",
        "timestamp": ts,
        "metrics": metrics,
    }
    rows.append(json.dumps(env))

print("\n".join(rows))
PY

MATCHED_PROCESSED=""
for _ in $(seq 1 8); do
  MATCHED_PROCESSED="$(
    docker exec caduceus-kafka kafka-console-consumer \
      --bootstrap-server localhost:9092 \
      --topic metrics.processed \
      --from-beginning \
      --timeout-ms 5000 2>/dev/null \
      | grep -E '^{' \
      | jq -c --arg tid "${TOPOLOGY_ID}" 'select(.topology_id==$tid and .source=="flink.features")' \
      | tail -n 1 || true
  )"
  if [ -n "${MATCHED_PROCESSED}" ]; then
    break
  fi
  sleep 1
done
if [ -z "${MATCHED_PROCESSED}" ]; then
  echo "Did not observe metrics.processed output for topology ${TOPOLOGY_ID}" >&2
  exit 1
fi

MATCHED_ALERT=""
for _ in $(seq 1 8); do
  MATCHED_ALERT="$(
    docker exec caduceus-kafka kafka-console-consumer \
      --bootstrap-server localhost:9092 \
      --topic alerts.anomaly \
      --from-beginning \
      --timeout-ms 5000 2>/dev/null \
      | grep -E '^{' \
      | jq -c --arg tid "${TOPOLOGY_ID}" 'select(.topology_id==$tid and .kind=="anomaly")' \
      | tail -n 1 || true
  )"
  if [ -n "${MATCHED_ALERT}" ]; then
    break
  fi
  sleep 1
done
if [ -z "${MATCHED_ALERT}" ]; then
  echo "Did not observe alerts.anomaly output for topology ${TOPOLOGY_ID}" >&2
  exit 1
fi

echo "processed sample: ${MATCHED_PROCESSED}" | head -c 220 && echo
echo "alert sample:     ${MATCHED_ALERT}" | head -c 220 && echo

echo "== Influx verification (raw + processed streams) =="
INFLUX_URL="${INFLUX_URL:-http://localhost:8086}"
INFLUX_TOKEN="${INFLUX_TOKEN:-changeme_influxdb_token}"
INFLUX_ORG="${INFLUX_ORG:-caduceus-flux}"
INFLUX_BUCKET="${INFLUX_BUCKET:-metrics}"

wait_influx() {
  local flux="$1"
  for _ in $(seq 1 20); do
    if curl -fsS \
      -H "Authorization: Token ${INFLUX_TOKEN}" \
      -H "Content-Type: application/vnd.flux" \
      -H "Accept: application/csv" \
      --data-binary "${flux}" \
      "${INFLUX_URL}/api/v2/query?org=${INFLUX_ORG}" | grep -q "${TOPOLOGY_ID}"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

FLUX_RAW="from(bucket: \"${INFLUX_BUCKET}\") |> range(start: -10m) |> filter(fn: (r) => r._measurement == \"network_metrics\" and r.topology_id == \"${TOPOLOGY_ID}\" and r.source == \"grpc\" and r._field == \"bytes_sent\") |> limit(n: 1)"
FLUX_PROCESSED="from(bucket: \"${INFLUX_BUCKET}\") |> range(start: -10m) |> filter(fn: (r) => r._measurement == \"network_metrics\" and r.topology_id == \"${TOPOLOGY_ID}\" and r.source == \"flink.features\" and r._field == \"tx_bps\") |> limit(n: 1)"

wait_influx "${FLUX_RAW}"
wait_influx "${FLUX_PROCESSED}"
echo "Influx OK (raw+processed)"
echo

echo "== Jupyter proxy headers (iframe) =="
JUPYTER_HEADERS="${TMP_DIR}/jupyter_headers.txt"
curl -sS -D "${JUPYTER_HEADERS}" -o /dev/null "${BASE_URL}/jupyter/lab" || true
grep -i '^x-frame-options:' "${JUPYTER_HEADERS}" || true
grep -i '^content-security-policy:' "${JUPYTER_HEADERS}" || true

if ! grep -qi '^x-frame-options: *SAMEORIGIN' "${JUPYTER_HEADERS}"; then
  echo "Expected X-Frame-Options: SAMEORIGIN on /jupyter/lab" >&2
  exit 1
fi
if ! grep -qi "frame-ancestors 'self'" "${JUPYTER_HEADERS}"; then
  echo "Expected CSP frame-ancestors 'self' on /jupyter/lab" >&2
  exit 1
fi
echo

echo "== Jupyter container notebook execution =="
docker exec "${JUPYTER_CONTAINER}" python - <<'PY'
import os
from pathlib import Path

import nbformat
from nbclient import NotebookClient

work = Path("/home/jovyan/work")
work.mkdir(parents=True, exist_ok=True)

print("python:", __import__("sys").version)

# Smoke-check client libs used by notebooks.
import influxdb_client  # noqa: F401
import kafka  # noqa: F401
import pyspark  # noqa: F401
import pyflink  # noqa: F401

# Validate Spark connectivity (shared Spark master).
try:
    from pyspark.sql import SparkSession

    master = os.environ.get("SPARK_MASTER_URL") or "spark://spark-master:7077"
    spark = SparkSession.builder.master(master).appName("caduceus-verify").getOrCreate()
    print("spark_version:", spark.version)
    print("spark_count:", spark.range(10).count())
    spark.stop()
except Exception as exc:
    raise SystemExit(f"spark test failed: {exc}")

nb = nbformat.v4.new_notebook()
nb.cells.append(nbformat.v4.new_code_cell("print('notebook_ok')\n"))
path = work / "_verify_notebook.ipynb"
path.write_text(nbformat.writes(nb), encoding="utf-8")

client = NotebookClient(nb, timeout=120, kernel_name="python3")
client.execute()

out_path = work / "_verify_notebook.executed.ipynb"
out_path.write_text(nbformat.writes(nb), encoding="utf-8")

print("executed:", out_path)
print("ml_models_dir:", (work / "ml_models").exists())
print("pcaps_dir:", (work / "pcaps").exists())
PY

echo
echo "OK"
