#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MANIFEST="${MANIFEST:-$REPO_ROOT/secrets/manifest.tsv}"
DEFAULT_AGE_KEY_FILE="${SOPS_AGE_KEY_FILE:-$HOME/.config/sops/age/keys.txt}"

err() { printf '[secrets] %s\n' "$*" >&2; }
info() { printf '[secrets] %s\n' "$*"; }

require_tool() {
  command -v "$1" >/dev/null 2>&1 || {
    err "required tool not found: $1"
    exit 1
  }
}

require_sops_setup() {
  require_tool sops
  if [ -n "${SOPS_AGE_KEY:-}" ]; then
    return 0
  fi
  if [ -f "$DEFAULT_AGE_KEY_FILE" ]; then
    export SOPS_AGE_KEY_FILE="$DEFAULT_AGE_KEY_FILE"
    return 0
  fi
  err "missing age key; set SOPS_AGE_KEY or create $DEFAULT_AGE_KEY_FILE"
  exit 1
}

abs_path() {
  printf '%s/%s\n' "$REPO_ROOT" "$1"
}

manifest_entries() {
  grep -v '^[[:space:]]*#' "$MANIFEST" | sed '/^[[:space:]]*$/d'
}

find_entry_by_target() {
  local target=$1
  manifest_entries | awk -F '\t' -v target="$target" '$1 == target { print $0; found=1 } END { if (!found) exit 1 }'
}

run_with_manifest() {
  local only_target=${1:-}
  local entry target encrypted mode
  while IFS=$'\t' read -r target encrypted mode; do
    [ -n "$target" ] || continue
    if [ -n "$only_target" ] && [ "$target" != "$only_target" ]; then
      continue
    fi
    handle_manifest_entry "$target" "$encrypted" "$mode"
  done < <(manifest_entries)
  if [ -n "$only_target" ] && ! find_entry_by_target "$only_target" >/dev/null; then
    err "target not found in manifest: $only_target"
    exit 1
  fi
}
