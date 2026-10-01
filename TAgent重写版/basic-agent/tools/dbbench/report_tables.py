"""从结果文件生成报告正文里的几张核心表（避免手抄出错）。"""
import json
from pathlib import Path

R = Path(__file__).resolve().parent / "results"
DBS = [("sqlite-tuned", "SQLite（调优）"), ("duckdb", "DuckDB"), ("postgres", "PostgreSQL"), ("mysql", "MySQL"),
       ("mongo", "MongoDB"), ("surreal", "SurrealDB")]
J = lambda name: json.loads((R / name).read_text())  # noqa: E731
n0 = lambda v: f"{v:,.0f}"  # noqa: E731


def head(cols):
    return ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]


def persistence():
    out = head(["方案", "单条提交：崩溃后丢失 / 已确认", "5000 条一批：丢失 / 已确认", "半批", "恢复可用"])
    for key, name in [("sqlite", "SQLite")] + DBS:
        s, b = J(f"mac-{key}-crash-single.json"), J(f"mac-{key}-crash-batch.json")
        mark = "✅" if s["lost_acked"] == 0 and b["lost_acked"] == 0 else "❌"
        out.append(f"| {mark} {name} | {s['lost_acked']} / {n0(s['acked'])} | {b['lost_acked']} / {n0(b['acked'])} | "
                   f"{b['partial_batches']} | {max(s['recovery_s'], b['recovery_s']):.2f} 秒 |")
    for mode, label in (("default", "MongoDB 默认 `w:1`（再测 3 轮）"), ("journal", "MongoDB `journal=true`（3 轮）")):
        rounds = [J(f"mac-mongo-{mode}-crash-{i}.json") for i in (1, 2, 3)]
        lost = "、".join(str(r["lost_acked"]) for r in rounds)
        acked = "、".join(n0(r["acked"]) for r in rounds)
        out.append(f"| {'❌' if any(r['lost_acked'] for r in rounds) else '✅'} {label} | {lost} / {acked} | — | — | — |")
    return "\n".join(out)


def speed(plat):
    rows = [("批量写 100 万条（秒）", "bulk_insert_messages", "seconds", lambda v: f"{v:.1f}"),
            ("单条写（条/秒，每条一个事务）", "insert_single", "ops_per_s", n0),
            ("按主键读（次/秒）", "point_read", "ops_per_s", n0),
            ("查某学生最近 20 条（次/秒）", "recent_by_student", "ops_per_s", n0),
            ("读一篇作文并解析 JSON（次/秒）", "essay_read_json", "ops_per_s", n0),
            ("单条改（次/秒）", "update_single", "ops_per_s", n0),
            ("单条删（次/秒）", "delete_single", "ops_per_s", n0),
            ("批量改 10 万条（条/秒）", "update_bulk", "rows_per_s", n0),
            ("批量删 10 万条（条/秒）", "delete_bulk", "rows_per_s", n0),
            ("全文模糊搜索（毫秒/次）", "like_search_scan", "p50_ms", lambda v: f"{v:.1f}")]
    data = {k: J(f"{plat}-{k}.json")["phases"] for k, _ in DBS}
    out = head(["操作"] + [n for _, n in DBS])
    for label, phase, field, f in rows:
        vals = [data[k][phase][field] for k, _ in DBS]
        best = min(vals) if field in ("seconds", "p50_ms") else max(vals)
        out.append(f"| {label} | " + " | ".join(("**" + f(v) + "**") if v == best else f(v) for v in vals) + " |")
    return "\n".join(out)


def concurrency():
    out = head(["方案", "macOS 8 / 32 / 64 线程（次/秒）", "macOS p99（毫秒）", "Linux 8 / 32 / 64 线程（次/秒）", "Linux p99（毫秒）", "出错"])
    for key, name in DBS:
        cells, errors = [name], 0
        for plat in ("mac", "linux"):
            d = J(f"{plat}-{key}-mixed.json")["phases"] if key == "sqlite-tuned" else J(f"{plat}-{key}.json")["phases"]
            ts = [d[f"mixed_{t}_threads"] for t in (8, 32, 64)]
            cells.append(" / ".join(n0(t["ops_per_s"]) for t in ts))
            cells.append(" / ".join(f"{t['p99_ms']:.0f}" for t in ts))
            errors += sum(t["errors"] for t in ts)
        cells.append(str(errors))
        out.append("| " + " | ".join(cells) + " |")
    lock = [J(f"{p}-sqlite-locked-mixed.json")["phases"] for p in ("mac", "linux")]
    out.append("| SQLite（调优+写锁） | " + " / ".join(n0(lock[0][f"mixed_{t}_threads"]["ops_per_s"]) for t in (8, 32, 64)) + " | "
               + " / ".join(f"{lock[0][f'mixed_{t}_threads']['p99_ms']:.0f}" for t in (8, 32, 64)) + " | "
               + " / ".join(n0(lock[1][f"mixed_{t}_threads"]["ops_per_s"]) for t in (8, 32, 64)) + " | "
               + " / ".join(f"{lock[1][f'mixed_{t}_threads']['p99_ms']:.0f}" for t in (8, 32, 64)) + " | 0 |")
    return "\n".join(out)


def aggregate():
    out = head(["方案", "按班级算平均分：macOS", "Linux"])
    for key, name in [("sqlite", "SQLite")] + DBS:
        m, l = J(f"mac-{key}.json")["phases"], J(f"linux-{key}.json")["phases"]
        out.append(f"| {name} | {m['class_avg_aggregate']['p50_ms']:,.1f} 毫秒 | {l['class_avg_aggregate']['p50_ms']:,.1f} 毫秒 |")
    return "\n".join(out)


if __name__ == "__main__":
    for name, fn in (("persistence", persistence), ("speed-linux", lambda: speed("linux")), ("speed-mac", lambda: speed("mac")),
                     ("concurrency", concurrency), ("aggregate", aggregate)):
        (R / f"table-{name}.md").write_text(fn() + "\n", encoding="utf-8")
        print(f"== {name}\n{fn()}\n")
