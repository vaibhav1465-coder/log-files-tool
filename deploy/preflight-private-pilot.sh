#!/usr/bin/env bash
set -euo pipefail

fail() { printf 'FAILED: %s\n' "$1" >&2; exit 1; }
pass() { printf 'OK: %s\n' "$1"; }

[ "$(uname -m)" = "aarch64" ] || fail "server must be ARM64"
pass "ARM64 architecture"

command -v docker >/dev/null || fail "Docker is required"
docker compose version >/dev/null || fail "Docker Compose is required"
command -v aws >/dev/null || fail "AWS CLI is required"
pass "required tools"

private_env="${1:-deploy/private.env}"
[ -f "$private_env" ] || fail "private environment file is missing"
mode="$(stat -c '%a' "$private_env")"
[ "$mode" = "600" ] || fail "private environment file must have mode 600"
pass "private configuration permissions"

set -a
# shellcheck disable=SC1090
. "$private_env"
set +a

required=(APP_HOST EXPRESS_DATA_ROOT EXPRESS_BACKUP_ROOT POSTGRES_USER POSTGRES_PASSWORD REDIS_PASSWORD FE_CLOUDFRONT_BUCKET FE_CLOUDFRONT_PREFIX FE_AKAMAI_BUCKET FE_AKAMAI_PREFIX)
for name in "${required[@]}"; do
  [ -n "${!name:-}" ] || fail "required private setting is missing"
done
pass "required private settings"

free_bytes="$(df --output=avail -B1 "$EXPRESS_DATA_ROOT" 2>/dev/null | tail -1 | tr -d ' ')"
[ -n "$free_bytes" ] || fail "cannot read data-volume capacity"
[ "$free_bytes" -ge 20000000000 ] || fail "less than 20 GB free disk"
pass "disk reserve"

aws sts get-caller-identity --output json >/dev/null || fail "instance role is unavailable"
pass "instance role"

aws s3api list-objects-v2 --bucket "$FE_CLOUDFRONT_BUCKET" --prefix "$FE_CLOUDFRONT_PREFIX" --max-items 1 --output json >/dev/null || fail "CloudFront prefix is unreadable"
aws s3api list-objects-v2 --bucket "$FE_AKAMAI_BUCKET" --prefix "$FE_AKAMAI_PREFIX" --max-items 1 --output json >/dev/null || fail "Akamai prefix is unreadable"
pass "approved read-only prefixes"

docker compose --env-file "$private_env" -f docker-compose.production.yml config --quiet || fail "Compose configuration is invalid"
pass "Compose configuration"

printf 'PREFLIGHT PASSED: no source object was downloaded or changed.\n'
