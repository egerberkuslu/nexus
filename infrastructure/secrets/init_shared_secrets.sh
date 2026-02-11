#!/bin/sh
set -eu

mkdir -p /run/secrets/caduceus

gen() {
  tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32
}

write_if_missing() {
  path="$1"
  value="$2"
  if [ ! -s "$path" ]; then
    printf '%s\n' "$value" > "$path"
  fi
}

write_if_missing /run/secrets/caduceus/pgadmin_email "admin@example.com"
write_if_missing /run/secrets/caduceus/pgadmin_password "$(gen)"

write_if_missing /run/secrets/caduceus/mongo_express_user "caduceus"
write_if_missing /run/secrets/caduceus/mongo_express_password "$(gen)"

write_if_missing /run/secrets/caduceus/hue_user "hue"
write_if_missing /run/secrets/caduceus/hue_password "$(gen)"

chmod 644 /run/secrets/caduceus/*

