#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-${1:-}}"
if [[ -z "${SERVICE_NAME}" ]]; then
  echo "SERVICE_NAME must be set (metastore|hiveserver2)" >&2
  exit 2
fi
if [[ "${SERVICE_NAME}" != "metastore" && "${SERVICE_NAME}" != "hiveserver2" ]]; then
  echo "Unsupported SERVICE_NAME: ${SERVICE_NAME} (expected metastore|hiveserver2)" >&2
  exit 2
fi

HIVE_HOME="${HIVE_HOME:-/opt/hive}"
HIVE_CONF_DIR="${HIVE_CONF_DIR:-${HIVE_HOME}/conf}"

export PATH="${HIVE_HOME}/bin:/opt/hadoop/bin:${PATH}"

DB_DRIVER="${DB_DRIVER:-postgres}"

HIVE_METASTORE_DB_HOST="${HIVE_METASTORE_DB_HOST:-hive-metastore-db}"
HIVE_METASTORE_DB_PORT="${HIVE_METASTORE_DB_PORT:-5432}"
HIVE_METASTORE_DB_NAME="${HIVE_METASTORE_DB_NAME:-hive_metastore}"
HIVE_METASTORE_DB_USER="${HIVE_METASTORE_DB_USER:-hive}"
HIVE_METASTORE_PASSWORD="${HIVE_METASTORE_PASSWORD:-}"

HDFS_NAMENODE_URI="${HDFS_NAMENODE_URI:-hdfs://hdfs-namenode:8020}"
HIVE_WAREHOUSE_DIR="${HIVE_WAREHOUSE_DIR:-/user/hive/warehouse}"

METASTORE_PORT="${METASTORE_PORT:-9083}"
HIVE_METASTORE_URI="${HIVE_METASTORE_URI:-thrift://hive-metastore:${METASTORE_PORT}}"

HIVE_SERVER2_THRIFT_PORT="${HIVE_SERVER2_THRIFT_PORT:-10000}"
HIVE_SERVER2_WEBUI_PORT="${HIVE_SERVER2_WEBUI_PORT:-10002}"

HDFS_BIN="${HDFS_BIN:-/opt/hadoop/bin/hdfs}"

wait_for_port() {
  local host="$1"
  local port="$2"
  local timeout_seconds="${3:-60}"
  local label="${4:-$host:$port}"
  local start
  start="$(date +%s)"
  while true; do
    if (echo >"/dev/tcp/${host}/${port}") >/dev/null 2>&1; then
      return 0
    fi
    if (( "$(date +%s)" - start >= timeout_seconds )); then
      echo "Timed out waiting for ${label} at ${host}:${port}" >&2
      return 1
    fi
    sleep 1
  done
}

parse_thrift_host_port() {
  local uri="${1-}"
  local rest="${uri#*://}"
  rest="${rest%%/*}"
  local host="${rest%:*}"
  local port="${rest##*:}"
  if [[ -z "${host}" || "${host}" == "${port}" ]]; then
    host="${rest}"
    port=""
  fi
  printf '%s %s\n' "${host}" "${port}"
}

xml_escape() {
  local s="${1-}"
  s="${s//&/&amp;}"
  s="${s//</&lt;}"
  s="${s//>/&gt;}"
  s="${s//\"/&quot;}"
  s="${s//\'/&apos;}"
  printf '%s' "${s}"
}

ensure_writable_home() {
  local current="${HOME:-}"
  if [[ -z "${current}" || ! -d "${current}" || ! -w "${current}" ]]; then
    export HOME="/tmp/hive"
  fi
  mkdir -p "${HOME}"
}

write_hadoop_conf() {
  mkdir -p "${HIVE_CONF_DIR}"
  rm -f "${HIVE_CONF_DIR}/core-site.xml"

  cat >"${HIVE_CONF_DIR}/core-site.xml" <<EOF
<?xml version="1.0"?>
<configuration>
  <property>
    <name>fs.defaultFS</name>
    <value>$(xml_escape "${HDFS_NAMENODE_URI}")</value>
  </property>
</configuration>
EOF
}

write_hive_conf() {
  mkdir -p "${HIVE_CONF_DIR}"
  rm -f "${HIVE_CONF_DIR}/hive-site.xml"

  local jdbc_url="jdbc:postgresql://${HIVE_METASTORE_DB_HOST}:${HIVE_METASTORE_DB_PORT}/${HIVE_METASTORE_DB_NAME}"

  cat >"${HIVE_CONF_DIR}/hive-site.xml" <<EOF
<?xml version="1.0"?>
<configuration>
  <property>
    <name>javax.jdo.option.ConnectionURL</name>
    <value>$(xml_escape "${jdbc_url}")</value>
  </property>
  <property>
    <name>javax.jdo.option.ConnectionDriverName</name>
    <value>org.postgresql.Driver</value>
  </property>
  <property>
    <name>javax.jdo.option.ConnectionUserName</name>
    <value>$(xml_escape "${HIVE_METASTORE_DB_USER}")</value>
  </property>
  <property>
    <name>javax.jdo.option.ConnectionPassword</name>
    <value>$(xml_escape "${HIVE_METASTORE_PASSWORD}")</value>
  </property>

  <property>
    <name>hive.metastore.uris</name>
    <value>$(xml_escape "${HIVE_METASTORE_URI}")</value>
  </property>
  <property>
    <name>hive.metastore.thrift.bind.host</name>
    <value>0.0.0.0</value>
  </property>
  <property>
    <name>hive.metastore.port</name>
    <value>$(xml_escape "${METASTORE_PORT}")</value>
  </property>
  <property>
    <name>hive.metastore.warehouse.dir</name>
    <value>$(xml_escape "${HIVE_WAREHOUSE_DIR}")</value>
  </property>
  <property>
    <name>hive.metastore.schema.verification</name>
    <value>false</value>
  </property>

  <property>
    <name>hive.server2.thrift.bind.host</name>
    <value>0.0.0.0</value>
  </property>
  <property>
    <name>hive.server2.thrift.port</name>
    <value>$(xml_escape "${HIVE_SERVER2_THRIFT_PORT}")</value>
  </property>
  <property>
    <name>hive.server2.webui.host</name>
    <value>0.0.0.0</value>
  </property>
  <property>
    <name>hive.server2.webui.port</name>
    <value>$(xml_escape "${HIVE_SERVER2_WEBUI_PORT}")</value>
  </property>

  <property>
    <name>hive.server2.authentication</name>
    <value>NOSASL</value>
  </property>
  <property>
    <name>hive.server2.enable.doAs</name>
    <value>false</value>
  </property>

  <property>
    <name>hive.notification.event.poll.interval</name>
    <value>0</value>
  </property>
</configuration>
EOF
}

bootstrap_hdfs_dirs() {
  local superuser="${HDFS_SUPERUSER_NAME:-root}"

  export HADOOP_USER_NAME="${superuser}"

  # Wait until safemode is OFF (best-effort).
  for _ in $(seq 1 60); do
    if "${HDFS_BIN}" dfsadmin -safemode get 2>/dev/null | grep -qi 'OFF'; then
      break
    fi
    sleep 2
  done

  "${HDFS_BIN}" dfs -test -d /tmp || "${HDFS_BIN}" dfs -mkdir -p /tmp
  "${HDFS_BIN}" dfs -chmod 1777 /tmp || true

  "${HDFS_BIN}" dfs -test -d "${HIVE_WAREHOUSE_DIR}" || "${HDFS_BIN}" dfs -mkdir -p "${HIVE_WAREHOUSE_DIR}"
  "${HDFS_BIN}" dfs -chmod -R 777 "${HIVE_WAREHOUSE_DIR}" || true

  export HADOOP_USER_NAME="${HIVE_USER_NAME:-hive}"
}

initialize_schema_if_needed() {
  if "${HIVE_HOME}/bin/schematool" -dbType "${DB_DRIVER}" -info >/dev/null 2>&1; then
    echo "Hive schema already initialized (${DB_DRIVER})"
    return 0
  fi

  echo "Initializing Hive schema (${DB_DRIVER})…"
  "${HIVE_HOME}/bin/schematool" -dbType "${DB_DRIVER}" -initSchema
  echo "Hive schema initialized"
}

ensure_writable_home

write_hadoop_conf
write_hive_conf

export HIVE_CONF_DIR="${HIVE_CONF_DIR}"
export HADOOP_CONF_DIR="${HIVE_CONF_DIR}"
export TEZ_CONF_DIR="${HIVE_CONF_DIR}"

export HADOOP_CLIENT_OPTS="${HADOOP_CLIENT_OPTS:-} -Xmx1G -Dhive.root.logger=console -Dhive.log.level=INFO ${SERVICE_OPTS:-}"

wait_for_port "${HIVE_METASTORE_DB_HOST}" "${HIVE_METASTORE_DB_PORT}" 120 "Hive metastore Postgres"
wait_for_port "hdfs-namenode" "8020" 180 "HDFS NameNode RPC"

bootstrap_hdfs_dirs

if [[ "${SERVICE_NAME}" == "metastore" ]]; then
  export METASTORE_PORT="${METASTORE_PORT}"
  initialize_schema_if_needed
fi

if [[ "${SERVICE_NAME}" == "hiveserver2" ]]; then
  read -r meta_host meta_port < <(parse_thrift_host_port "${HIVE_METASTORE_URI}")
  if [[ -z "${meta_host}" ]]; then
    echo "Failed to parse HIVE_METASTORE_URI: ${HIVE_METASTORE_URI}" >&2
    exit 2
  fi
  meta_port="${meta_port:-${METASTORE_PORT}}"
  wait_for_port "${meta_host}" "${meta_port}" 120 "Hive metastore service"
  export HADOOP_CLASSPATH="${TEZ_HOME:-/opt/tez}/*:${TEZ_HOME:-/opt/tez}/lib/*:${HADOOP_CLASSPATH:-}"
fi

exec "${HIVE_HOME}/bin/hive" --skiphadoopversion --skiphbasecp --service "${SERVICE_NAME}"
