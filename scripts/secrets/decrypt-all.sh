#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "$SCRIPT_DIR/common.sh"

TARGET_FILTER=${1:-}

handle_manifest_entry() {
  local target=$1 encrypted=$2 mode=$3
  local source_file output_file tmp_file
  source_file="$(abs_path "$encrypted")"
  output_file="$(abs_path "$target")"

  [ -f "$source_file" ] || {
    err "encrypted file missing: $encrypted"
    exit 1
  }

  mkdir -p "$(dirname "$output_file")"
  tmp_file="$(mktemp)"
  sops decrypt --input-type binary --output-type binary "$source_file" > "$tmp_file"
  chmod "$mode" "$tmp_file"
  mv "$tmp_file" "$output_file"
  info "decrypted $target"
}

require_sops_setup
run_with_manifest "$TARGET_FILTER"
