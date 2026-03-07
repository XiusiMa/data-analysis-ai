#!/bin/zsh
set -euo pipefail

BASE_DIR="/Users/sophia/dev/data-analysis-ai/xiaoyuzhou-export"
PYTHON_BIN="$BASE_DIR/.venv/bin/python"
LOG_DIR="$BASE_DIR/logs"
mkdir -p "$LOG_DIR"

RUN_LOG="$LOG_DIR/cron_$(date +%Y%m%d_%H%M%S).log"
ALERT_FILE="$LOG_DIR/last_failure.txt"
SUCCESS_FILE="$LOG_DIR/last_success.txt"
ALERT_EMAIL="${ALERT_EMAIL:-sophiama021@gmail.com}"

notify_macos() {
  local title="$1"
  local message="$2"
  if command -v osascript >/dev/null 2>&1; then
    osascript -e "display notification \"$message\" with title \"$title\"" >/dev/null 2>&1 || true
  fi
}

notify_email() {
  local subject="$1"
  local body="$2"
  if [[ -n "$ALERT_EMAIL" ]] && command -v mail >/dev/null 2>&1; then
    echo "$body" | mail -s "$subject" "$ALERT_EMAIL" || true
  fi
}

exec >> "$RUN_LOG" 2>&1

echo "==== xiaoyuzhou pipeline start: $(date '+%Y-%m-%d %H:%M:%S') ===="
cd "$BASE_DIR"

if [[ ! -x "$PYTHON_BIN" ]]; then
  msg="FAILED: python not found at $PYTHON_BIN"
  echo "$msg"
  printf "%s\n%s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$msg" > "$ALERT_FILE"
  notify_macos "Xiaoyuzhou Cron Failed" "$msg"
  notify_email "Xiaoyuzhou Cron Failed" "$msg"
  exit 1
fi

if HEADLESS=1 "$PYTHON_BIN" "$BASE_DIR/export.py" && "$PYTHON_BIN" "$BASE_DIR/import_to_sqlite.py"; then
  msg="SUCCESS: download + import completed"
  echo "$msg"
  printf "%s\n%s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$msg" > "$SUCCESS_FILE"
  rm -f "$ALERT_FILE"
  notify_macos "Xiaoyuzhou Cron Success" "download + import completed"
else
  msg="FAILED: check log $RUN_LOG"
  echo "$msg"
  printf "%s\n%s\n%s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$msg" "$RUN_LOG" > "$ALERT_FILE"
  notify_macos "Xiaoyuzhou Cron Failed" "See log: $RUN_LOG"
  notify_email "Xiaoyuzhou Cron Failed" "See log: $RUN_LOG"
  exit 1
fi

echo "==== xiaoyuzhou pipeline done: $(date '+%Y-%m-%d %H:%M:%S') ===="
