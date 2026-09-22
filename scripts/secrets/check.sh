#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "$SCRIPT_DIR/common.sh"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

handle_manifest_entry() {
  local target=$1 encrypted=$2 mode=$3
  local source_file output_file
  source_file="$(abs_path "$encrypted")"
  output_file="$tmp_dir/$target"
  mkdir -p "$(dirname "$output_file")"
  sops decrypt --input-type binary --output-type binary "$source_file" > "$output_file"
  chmod "$mode" "$output_file"
  [ -s "$output_file" ] || {
    err "decrypted file is empty: $target"
    exit 1
  }
  info "verified $target"
}

require_sops_setup
run_with_manifest
info "all manifest entries decrypted successfully"
