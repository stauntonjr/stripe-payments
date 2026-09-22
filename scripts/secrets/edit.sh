#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "$SCRIPT_DIR/common.sh"

TARGET=${1:-}
EDITOR_CMD=${EDITOR:-vi}

[ -n "$TARGET" ] || {
  err "usage: $(basename "$0") <repo-relative-target>"
  exit 2
}

find_entry_by_target "$TARGET" >/dev/null || {
  err "target not found in manifest: $TARGET"
  exit 1
}

require_sops_setup
bash "$SCRIPT_DIR/decrypt-all.sh" "$TARGET"
"$EDITOR_CMD" "$(abs_path "$TARGET")"
bash "$SCRIPT_DIR/encrypt-all.sh" "$TARGET"
info "updated $TARGET"
