#!/usr/bin/env bash
set -euo pipefail

REPO_SLUG="izscc/iLongRun"
REPO_ARCHIVE_URL="https://codeload.github.com/izscc/iLongRun/tar.gz/refs/heads/main"
TMP_DIR=""
ROOT_DIR=""

cleanup() {
  if [ -n "$TMP_DIR" ]; then
    rm -rf "$TMP_DIR"
  fi
  return 0
}
trap cleanup EXIT

if [ -f "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/plugin.json" ]; then
  ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
  TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ilongrun-install.XXXXXX")"
  curl -fsSL "$REPO_ARCHIVE_URL" -o "$TMP_DIR/repo.tar.gz"
  tar -xzf "$TMP_DIR/repo.tar.gz" -C "$TMP_DIR"
  ROOT_DIR="$(find "$TMP_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
fi

ILONGRUN_PLUGIN_SOURCE="${ILONGRUN_PLUGIN_SOURCE:-$REPO_SLUG}" bash "$ROOT_DIR/scripts/install-all.sh"
