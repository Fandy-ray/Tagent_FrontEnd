#!/bin/bash
# Linux 一轮：测试程序跑在同一 Docker 网络里的 Linux 容器中（4 核 / 4 GB），嵌入式库的数据放在容器卷上
B="$(cd "$(dirname "$0")" && pwd)"; cd "$B"; mkdir -p results
SERVERS="dbbench-postgres dbbench-mysql dbbench-surreal dbbench-mongo"
runner() {
  docker run --rm --network dbbench-net --cpus 4 --memory 4g --entrypoint sh \
    -v "$B:/bench" -v dbbench-linux:/work -w /bench \
    -e DATA_DIR=/work/data -e PG_DSN=postgresql://bench:bench@dbbench-postgres:5432/bench \
    -e MYSQL_HOST=dbbench-mysql -e MYSQL_PORT=3306 -e MONGO_URI=mongodb://dbbench-mongo:27017 \
    -e SURREAL_URL=ws://dbbench-surreal:8000/rpc \
    lfnovo/open_notebook:v1-latest -c "$1"
}
datapath() {
  case "$1" in
    dbbench-postgres) echo /var/lib/postgresql/data ;; dbbench-mysql) echo /var/lib/mysql ;;
    dbbench-surreal) echo /data ;; dbbench-mongo) echo /data/db ;;
  esac
}
run() {
  db=$1; container=$2
  case "$db" in sqlite-tuned) files="bench-tuned.sqlite" ;; *) files="bench.$db" ;; esac
  for c in $SERVERS; do [ "$c" != "$container" ] && docker stop "$c" >/dev/null 2>&1; done
  [ -n "$container" ] && docker start "$container" >/dev/null && sleep 2
  echo "=== linux $db start $(date +%T)"
  runner "/work/venv/bin/python bench.py $db --out results/linux-$db.json --label linux > results/linux-$db.log 2>&1; tail -1 results/linux-$db.log"
  if [ -z "$container" ]; then
    for mode in single batch; do runner "/work/venv/bin/python crash.py $db --mode $mode --out results/linux-$db-crash-$mode.json | tail -1"; done
    runner "du -sk /work/data/$files* | awk '{s+=\$1} END {print s}'" > "results/linux-$db.du"
  else
    docker stats --no-stream --format '{{.MemUsage}}' "$container" > "results/linux-$db.mem"
    docker exec "$container" du -sk "$(datapath "$container")" | cut -f1 > "results/linux-$db.du"
  fi
  echo "=== linux $db done $(date +%T)"
}
for spec in "$@"; do run "${spec%%:*}" "${spec#*:}"; done
