#!/bin/bash
DB_DIR="$(dirname "$0")/data"
BACKUP_DIR="$DB_DIR/backups"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
for db in "$DB_DIR"/*.db; do
  [ -f "$db" ] || continue
  NAME=$(basename "$db")
  cp "$db" "$BACKUP_DIR/${NAME%.db}_${TIMESTAMP}.db"
done
ls -t "$BACKUP_DIR"/*.db 2>/dev/null | tail -n +8 | xargs rm -f 2>/dev/null
echo "[$(date)] DB备份完成"
