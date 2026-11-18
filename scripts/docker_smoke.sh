#!/usr/bin/env bash
# Smoke test for the container image (L4): build, CLI help, CLI on a golden
# fixture, demo health. Usage: scripts/docker_smoke.sh [image-tag]
set -euo pipefail
IMAGE="${1:-bylaw-rule-verification:smoke}"
NAME="bylaw-smoke-$$"
cd "$(dirname "$0")/.."

# EXTRA_CA_BUNDLE: optional CA file for a TLS-intercepting proxy (build secret only).
secret=()
if [ -n "${EXTRA_CA_BUNDLE:-}" ]; then secret=(--secret "id=ca,src=$EXTRA_CA_BUNDLE"); fi
docker build --quiet "${secret[@]}" -t "$IMAGE" . >/dev/null
echo "PASS image built: $IMAGE"

docker run --rm "$IMAGE" bylaw-verify --help | grep -q "contract 1.0"
echo "PASS bylaw-verify --help (contract 1.0)"

decision=$(docker run --rm "$IMAGE" sh -c '
  mkdir -p /tmp/c/configs && cp configs/calgary_rcg.json /tmp/c/configs/ &&
  bylaw-verify --candidates tests/fixtures/cli_contract/verified/candidates.json \
    --evidence tests/fixtures/cli_contract/verified/evidence.json \
    --config /tmp/c/configs/calgary_rcg.json --out-dir /tmp/c/out' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['decisions'][0]['decision'])")
test "$decision" = verified
echo "PASS bylaw-verify golden fixture -> $decision"

docker run -d --rm --name "$NAME" -p 127.0.0.1:18631:8631 "$IMAGE" >/dev/null
trap 'docker stop "$NAME" >/dev/null 2>&1 || true' EXIT
for _ in $(seq 1 60); do
  body=$(curl -fsS http://127.0.0.1:18631/_stcore/health 2>/dev/null || true)
  [ "$body" = ok ] && break
  sleep 1
done
test "$body" = ok
echo "PASS demo container /_stcore/health -> ok"
echo "docker smoke PASS"
