"""只跑并发混合负载（数据沿用已经灌好的库）。用法：mixed_only.py <db> <out.json> <新消息编号起点>

编号起点每次都要给一个没用过的：之前那轮并发测试写进去的编号还在库里，撞上就是主键冲突。
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench
db = bench.DBS[sys.argv[1]]()
if isinstance(db, bench.SQLiteTunedDB):
    db.path = bench.DATA_DIR / "bench-tuned.sqlite"  # 调优版的库文件
out = {"db": db.name, "phases": {}}
for t in (8, 32, 64):
    r = bench.mixed(db, t, 10, 1_000_000, 20_000, int(sys.argv[3]) + t * 1_000_000_000_000)
    out["phases"][f"mixed_{t}_threads"] = r
    print(db.name, t, json.dumps(r, ensure_ascii=False), flush=True)
Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
