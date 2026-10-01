"""把 results/<平台>-<库>*.json 汇总成 Markdown 对比表。用法：python summarize.py mac"""
import json, re, sys
from pathlib import Path

R = Path(__file__).resolve().parent / "results"
ORDER = ["sqlite", "sqlite-tuned", "duckdb", "postgres", "mysql", "mongo", "surreal"]


def load(plat):
    rows = {}
    for db in ORDER:
        f = R / f"{plat}-{db}.json"
        if not f.exists():
            continue
        data = json.loads(f.read_text())
        extra = {}
        for mode in ("single", "batch"):
            c = R / f"{plat}-{db}-crash-{mode}.json"
            if c.exists():
                extra[f"crash_{mode}"] = json.loads(c.read_text())
        for suffix in ("du", "mem"):
            p = R / f"{plat}-{db}.{suffix}"
            if p.exists():
                extra[suffix] = p.read_text().strip()
        t = R / f"{plat}-{db}.time"
        if t.exists():
            m = re.search(r"(\d+)\s+maximum resident set size", t.read_text())
            if m:
                extra["client_rss_mb"] = round(int(m.group(1)) / 1e6)
        rows[db] = (data, extra)
    return rows


def fmt(v, digits=0):
    if v is None:
        return "—"
    if isinstance(v, float) and digits:
        return f"{v:,.{digits}f}"
    return f"{v:,.0f}" if isinstance(v, (int, float)) else str(v)


def table(rows, title, cols):
    names = [rows[db][0]["db"] for db in rows]
    out = [f"| {title} | " + " | ".join(names) + " |", "| --- |" + " --- |" * len(names)]
    for label, getter in cols:
        cells = []
        for db in rows:
            try:
                cells.append(getter(*rows[db]))
            except Exception:  # noqa: BLE001
                cells.append("—")
        out.append(f"| {label} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def main(plat):
    rows = load(plat)
    P = lambda d, k: d["phases"][k]  # noqa: E731
    print(table(rows, "写入", [
        ("批量写 100 万条（条/秒）", lambda d, e: fmt(P(d, "bulk_insert_messages")["rows_per_s"])),
        ("批量写 100 万条（秒）", lambda d, e: fmt(P(d, "bulk_insert_messages")["seconds"], 1)),
        ("批量写 2 万篇作文（篇/秒）", lambda d, e: fmt(P(d, "bulk_insert_essays")["rows_per_s"])),
        ("单条写、每条一个事务（条/秒）", lambda d, e: fmt(P(d, "insert_single")["ops_per_s"])),
        ("单条写 p99（毫秒）", lambda d, e: fmt(P(d, "insert_single")["p99_ms"], 2)),
    ]))
    print()
    print(table(rows, "读", [
        ("按主键读（次/秒）", lambda d, e: fmt(P(d, "point_read")["ops_per_s"])),
        ("按主键读 p99（毫秒）", lambda d, e: fmt(P(d, "point_read")["p99_ms"], 3)),
        ("查某学生最近 20 条（次/秒）", lambda d, e: fmt(P(d, "recent_by_student")["ops_per_s"])),
        ("查某学生最近 20 条 p99（毫秒）", lambda d, e: fmt(P(d, "recent_by_student")["p99_ms"], 3)),
        ("按班级算平均分（毫秒/次）", lambda d, e: fmt(P(d, "class_avg_aggregate")["p50_ms"], 1)),
        ("全文模糊搜索（毫秒/次）", lambda d, e: fmt(P(d, "like_search_scan")["p50_ms"], 1)),
        ("读一篇作文 + 解析批改 JSON（次/秒）", lambda d, e: fmt(P(d, "essay_read_json")["ops_per_s"])),
    ]))
    print()
    print(table(rows, "改与删", [
        ("单条改（次/秒）", lambda d, e: fmt(P(d, "update_single")["ops_per_s"])),
        ("批量改 10 万条（条/秒）", lambda d, e: fmt(P(d, "update_bulk")["rows_per_s"])),
        ("单条删（次/秒）", lambda d, e: fmt(P(d, "delete_single")["ops_per_s"])),
        ("批量删 10 万条（条/秒）", lambda d, e: fmt(P(d, "delete_bulk")["rows_per_s"])),
        ("删改后总数核对", lambda d, e: "✅" if P(d, "count_check")["ok"] else "❌"),
    ]))
    print()
    conc = []
    for t in (8, 32, 64):
        conc.append((f"{t} 线程：吞吐（次/秒）", lambda d, e, t=t: fmt(P(d, f"mixed_{t}_threads")["ops_per_s"])))
        conc.append((f"{t} 线程：p99（毫秒）", lambda d, e, t=t: fmt(P(d, f"mixed_{t}_threads")["p99_ms"], 1)))
        conc.append((f"{t} 线程：出错", lambda d, e, t=t: fmt(P(d, f"mixed_{t}_threads")["errors"])))
    print(table(rows, "并发混合负载", conc))
    print()
    print(table(rows, "持久化与资源", [
        ("崩溃：单条提交，确认后丢失", lambda d, e: f"{e['crash_single']['lost_acked']} / {e['crash_single']['acked']:,}"),
        ("崩溃：5000 条一批，确认后丢失", lambda d, e: f"{e['crash_batch']['lost_acked']} / {e['crash_batch']['acked']:,}"),
        ("崩溃：出现半批", lambda d, e: fmt(e["crash_batch"]["partial_batches"])),
        ("崩溃后恢复可用（秒）", lambda d, e: fmt(max(e["crash_single"]["recovery_s"], e["crash_batch"]["recovery_s"]), 2)),
        ("磁盘占用（MB，du）", lambda d, e: fmt(int(e["du"]) / 1024, 0)),
        ("数据库内存（服务端，测完）", lambda d, e: e.get("mem", "（在应用进程内）").split(" / ")[0]),
        ("测试进程峰值内存（MB）", lambda d, e: fmt(e.get("client_rss_mb"))),
    ]))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "mac")
