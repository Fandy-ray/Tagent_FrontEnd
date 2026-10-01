#!/bin/bash
# MongoDB 两种写入确认对比：默认 {w:1}（不等日志落盘） vs journal=true（等日志落盘再确认）
B="$(cd "$(dirname "$0")" && pwd)"; cd "$B"; export DATA_DIR="$B/data-mac"
for c in dbbench-postgres dbbench-mysql dbbench-surreal; do docker stop $c >/dev/null 2>&1; done
docker start dbbench-mongo >/dev/null; venv/bin/python wait_ready.py mongo "$(date +%s)"
for round in 1 2 3; do
  MONGO_URI="mongodb://127.0.0.1:57017/?journal=true" venv/bin/python crash.py mongo --container dbbench-mongo --mode single --out "results/mac-mongo-journal-crash-$round.json" | tail -1
  venv/bin/python crash.py mongo --container dbbench-mongo --mode single --out "results/mac-mongo-default-crash-$round.json" | tail -1
done
# 单条写吞吐（每条一次往返）：默认 vs journal=true
for uri in "mongodb://127.0.0.1:57017" "mongodb://127.0.0.1:57017/?journal=true"; do
  MONGO_URI="$uri" venv/bin/python - <<'PYEOF'
import os, random, sys, time
sys.path.insert(0, ".")
import bench
db = bench.MongoDB(); con = db.connect(); rng = random.Random(5)
rows = [bench.message_row(rng, 800_000_000 + i) for i in range(5000)]
t = time.perf_counter()
for r in rows:
    db.insert_one(con, r)
el = time.perf_counter() - t
con.messages.delete_many({"_id": {"$gte": 800_000_000, "$lt": 800_010_000}})
print(f"{os.environ['MONGO_URI']}: 单条写 {5000 / el:,.0f} 条/秒")
PYEOF
done
docker stop dbbench-mongo >/dev/null
