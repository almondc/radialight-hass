#!/usr/bin/env bash
set -euo pipefail

# Safe sync script: copies a local integration into ha-dev/config/custom_components/radialight_cloud
# Usage: ./sync_integration.sh /absolute/path/to/source/radialight_cloud

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /absolute/path/to/source/radialight_cloud" >&2
  exit 1
fi

SRC="$1"

if [[ -z "$SRC" ]]; then
  echo "Source path is empty. Refusing to run." >&2
  exit 1
fi

if [[ ! -d "$SRC" ]]; then
  echo "Source path does not exist or is not a directory: $SRC" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEST_BASE="$ROOT_DIR/config/custom_components"
DEST="$DEST_BASE/radialight_cloud"

# Safety checks
case "$DEST" in
  "$DEST_BASE"/*) ;;
  *)
    echo "Destination is outside allowed directory: $DEST" >&2
    exit 1
    ;;
esac

# Only delete/overwrite the destination integration folder
if [[ -d "$DEST" ]]; then
  rm -rf "$DEST"
fi

mkdir -p "$DEST_BASE"
cp -R "$SRC" "$DEST"

echo "Synced integration to $DEST"
