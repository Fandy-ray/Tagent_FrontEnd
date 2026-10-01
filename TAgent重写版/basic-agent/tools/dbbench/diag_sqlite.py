import random, sqlite3, sys, time
path = sys.argv[1]
def run(label, pragmas):
    con = sqlite3.connect(path, isolation_level=None)
    for p in ["PRAGMA journal_mode=WAL", "PRAGMA synchronous=NORMAL"] + pragmas:
        con.execute(p)
    rng = random.Random(1); ids = [rng.randrange(1, 1_000_000) for _ in range(20000)]
    for i in ids[:2000]:
        con.execute("SELECT * FROM messages WHERE id = ?", (i,)).fetchone()  # 预热
    t = time.perf_counter()
    for i in ids:
        con.execute("SELECT * FROM messages WHERE id = ?", (i,)).fetchone()
    el = time.perf_counter() - t
    t = time.perf_counter()
    for i in ids[:5000]:
        con.execute("SELECT id FROM messages WHERE id = ?", (i,)).fetchone()
    el2 = time.perf_counter() - t
    print(f"{label:34s} sqlite {sqlite3.sqlite_version}: SELECT * {len(ids)/el:>9,.0f}/s   SELECT id {5000/el2:>9,.0f}/s", flush=True)
    con.close()
run("default (as benchmarked)", [])
run("cache_size 256MB", ["PRAGMA cache_size=-262144"])
run("mmap 1GB", ["PRAGMA mmap_size=1073741824"])
run("mmap + cache", ["PRAGMA mmap_size=1073741824", "PRAGMA cache_size=-262144"])
