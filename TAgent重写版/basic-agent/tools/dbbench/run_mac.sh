#!/bin/bash
# macOS 一轮：每个库单独跑（其他数据库容器先停掉），基准 → 崩溃测试 → 记录内存与磁盘
B="$(cd "$(dirname "$0")" && pwd)"; cd "$B"
export DATA_DIR="$B/data-mac"; mkdir -p results "$DATA_DIR"
SERVERS="dbbench-postgres dbbench-mysql dbbench-surreal dbbench-mongo"
datapath() {  # macOS 自带 bash 3.2 没有关联数组
  case "$1" in
    dbbench-postgres) echo /var/lib/postgresql/data ;; dbbench-mysql) echo /var/lib/mysql ;;
    dbbench-surreal) echo /data ;; dbbench-mongo) echo /data/db ;;
  esac
}
run() {
  db=$1; container=$2
  case "$db" in sqlite-tuned) files="bench-tuned.sqlite" ;; *) files="bench.$db" ;; esac
  for c in $SERVERS; do [ "$c" != "$container" ] && docker stop "$c" >/dev/null 2>&1; done
  if [ -n "$container" ]; then docker start "$container" >/dev/null && venv/bin/python wait_ready.py "$db" "$(date +%s)"; fi
  echo "=== $db start $(date +%T)"
  /usr/bin/time -l venv/bin/python bench.py "$db" --out "results/mac-$db.json" --label mac > "results/mac-$db.log" 2> "results/mac-$db.time"
  tail -1 "results/mac-$db.log"
  for mode in single batch; do
    if [ -n "$container" ]; then venv/bin/python crash.py "$db" --container "$container" --mode $mode --out "results/mac-$db-crash-$mode.json" | tail -1
    else venv/bin/python crash.py "$db" --mode $mode --out "results/mac-$db-crash-$mode.json" | tail -1; fi
  done
  if [ -n "$container" ]; then
    docker stats --no-stream --format '{{.MemUsage}}' "$container" > "results/mac-$db.mem"
    docker exec "$container" du -sk "$(datapath "$container")" | cut -f1 > "results/mac-$db.du"
  else
    du -sk "$DATA_DIR"/$files* | awk '{s+=$1} END {print s}' > "results/mac-$db.du"
  fi
  echo "=== $db done $(date +%T)"
}
for spec in "$@"; do run "${spec%%:*}" "${spec#*:}"; done
