"""等数据库能真正执行查询为止，输出从给定时刻起花了多少秒。用法：wait_ready.py <db> <起始时间戳>"""
import sys, time
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import bench
db, since = bench.DBS[sys.argv[1]](), float(sys.argv[2])
deadline = time.time() + 180
while time.time() < deadline:
    try:
        con = db.connect()
        if sys.argv[1] == "surreal":
            con.query("RETURN 1")
        elif sys.argv[1] == "mongo":
            con.command("ping")
        else:
            db.run(con, "SELECT 1").fetchone()
        print(f"{db.name} ready after {time.time() - since:.1f}s")
        break
    except Exception as exc:  # noqa: BLE001
        last = exc
        time.sleep(0.3)
else:
    print(f"{db.name} NOT ready: {last}")
