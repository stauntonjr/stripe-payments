#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "$SCRIPT_DIR/common.sh"

TARGET_FILTER=${1:-}

handle_manifest_entry() {
  local target=$1 encrypted=$2 mode=$3
  local input_file output_file tmp_file
  input_file="$(abs_path "$target")"
  output_file="$(abs_path "$encrypted")"

  [ -f "$input_file" ] || {
    err "plaintext file missing: $target"
    exit 1
  }

  mkdir -p "$(dirname "$output_file")"
  tmp_file="$(mktemp)"
  sops encrypt \
    --filename-override "$output_file" \
    --input-type binary \
    --output-type binary \
    "$input_file" > "$tmp_file"
  mv "$tmp_file" "$output_file"
  chmod 600 "$output_file"
  chmod "$mode" "$input_file"
  info "encrypted $target -> $encrypted"
}

require_sops_setup
run_with_manifest "$TARGET_FILTER"
