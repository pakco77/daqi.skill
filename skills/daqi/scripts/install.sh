#!/bin/sh
# Initialize daqi's local stores without overwriting user data, then print the
# optional Claude Code SessionStart hook using this installation's real path.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ASSETS_DIR="$SCRIPT_DIR/../assets"
DAQI_DIR=${DAQI_HOME:-"$HOME/.daqi"}
LANGUAGE=""

usage() {
  echo "Usage: sh scripts/install.sh [--language zh|en]"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --language)
      [ "$#" -ge 2 ] || { usage >&2; exit 2; }
      LANGUAGE=$2
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
done

case "$LANGUAGE" in
  ""|zh|en) ;;
  *)
    echo "--language must be zh or en" >&2
    exit 2
    ;;
esac

if [ -n "$LANGUAGE" ]; then
  mkdir -p "$DAQI_DIR"
  if [ -L "$DAQI_DIR/SELF.md" ]; then
    echo "Refuse $DAQI_DIR/SELF.md (symbolic links are not safe store targets)" >&2
    exit 2
  fi
  if [ -f "$DAQI_DIR/SELF.md" ]; then
    existing_language=$(sed -n 's/^management_language:[[:space:]]*//p' "$DAQI_DIR/SELF.md" | head -n 1)
    if [ -z "$existing_language" ]; then
      echo "Existing $DAQI_DIR/SELF.md has no management_language; stop and repair it before initializing missing stores." >&2
      exit 2
    fi
    if [ "$existing_language" != "$LANGUAGE" ]; then
      echo "Existing store language is $existing_language, not $LANGUAGE; explicit language migration is required." >&2
      exit 2
    fi
  fi
  for store in SELF SHELF POOL; do
    target="$DAQI_DIR/$store.md"
    source="$ASSETS_DIR/$store.$LANGUAGE.template.md"
    if [ -L "$target" ] || { [ -e "$target" ] && [ ! -f "$target" ]; }; then
      echo "Refuse $target (existing links and non-files are not safe store targets)" >&2
      exit 2
    elif [ -f "$target" ]; then
      echo "Skip $target (already exists; never overwritten)"
    else
      cp "$source" "$target"
      echo "Created $target"
    fi
  done
else
  echo "Stores not initialized yet. Invoke /daqi; first use will ask for management language and an optional default project home."
fi

cat <<EOF

Claude Code automatic SessionStart setup is not shipped in this Codex V1.
The installer does not edit Claude settings.

Portable event hooks for every host:
  /daqi remember <idea>
  /daqi wrap up

These commands follow references/hooks.md. No native seed or end-of-session
hook is installed automatically.
EOF
