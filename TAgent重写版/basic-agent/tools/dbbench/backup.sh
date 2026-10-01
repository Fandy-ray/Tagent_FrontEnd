#!/bin/bash
# 备份：在 100 万条数据量上，用每个库官方的备份方式做一次完整备份，记耗时与备份文件大小
B="$(cd "$(dirname "$0")" && pwd)"; cd "$B"; OUT=results/backup.txt; : > "$OUT"
now() { python3 -c "import time; print(time.time())"; }
report() { python3 -c "print(f'$1\t{$3 - $2:.1f}s\t{$4 / 1e6:.0f} MB')" >> "$OUT"; tail -1 "$OUT"; }
t0=$(now); venv/bin/python -c "
import sqlite3; src = sqlite3.connect('data-mac/bench.sqlite'); dst = sqlite3.connect('data-mac/backup.sqlite'); src.backup(dst); dst.close()"
report "SQLite（在线备份 API）" "$t0" "$(now)" "$(stat -f %z data-mac/backup.sqlite)"; rm -f data-mac/backup.sqlite
rm -rf data-mac/duck-export; t0=$(now); venv/bin/python -c "
import duckdb; duckdb.connect('data-mac/bench.duckdb').execute(\"EXPORT DATABASE 'data-mac/duck-export' (FORMAT PARQUET)\")"
report "DuckDB（EXPORT DATABASE，Parquet）" "$t0" "$(now)" "$(du -sk data-mac/duck-export | awk '{print $1 * 1024}')"; rm -rf data-mac/duck-export
for c in dbbench-postgres dbbench-mysql dbbench-mongo dbbench-surreal; do docker stop $c >/dev/null 2>&1; done
docker start dbbench-postgres >/dev/null; sleep 3; t0=$(now)
docker exec dbbench-postgres pg_dump -U bench -Fc -f /tmp/bench.dump bench
report "PostgreSQL（pg_dump -Fc）" "$t0" "$(now)" "$(docker exec dbbench-postgres stat -c %s /tmp/bench.dump)"; docker exec dbbench-postgres rm /tmp/bench.dump; docker stop dbbench-postgres >/dev/null
docker start dbbench-mysql >/dev/null; sleep 6; t0=$(now)
docker exec dbbench-mysql sh -c 'mysqldump -uroot -pbench --single-transaction bench > /tmp/bench.sql 2>/dev/null'
report "MySQL（mysqldump）" "$t0" "$(now)" "$(docker exec dbbench-mysql stat -c %s /tmp/bench.sql)"; docker exec dbbench-mysql rm /tmp/bench.sql; docker stop dbbench-mysql >/dev/null
docker start dbbench-mongo >/dev/null; sleep 3; t0=$(now)
docker exec dbbench-mongo mongodump --quiet --db bench --gzip --archive=/tmp/bench.archive
report "MongoDB（mongodump --gzip）" "$t0" "$(now)" "$(docker exec dbbench-mongo stat -c %s /tmp/bench.archive)"; docker exec dbbench-mongo rm /tmp/bench.archive; docker stop dbbench-mongo >/dev/null
docker start dbbench-surreal >/dev/null; sleep 3; t0=$(now)
docker exec dbbench-surreal /surreal export -e http://localhost:8000 -u root -p root --namespace bench --database bench /data/bench.surql
report "SurrealDB（surreal export）" "$t0" "$(now)" "$(docker cp dbbench-surreal:/data/bench.surql - | wc -c)"; docker stop dbbench-surreal >/dev/null
