#!/bin/sh
set -eu

[ "$#" -eq 2 ] && [ "$1" = "--root" ] || {
  echo "Usage: bootup-hook.sh --root <absolute-project-root>" >&2
  exit 2
}

case "$2" in
  /*) ;;
  *)
    echo "Usage: bootup-hook.sh --root <absolute-project-root>" >&2
    exit 2
    ;;
esac

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$SCRIPT_DIR/checkpoint.py" \
  read \
  --root "$2" \
  --project-root "${CLAUDE_PROJECT_DIR-}"
