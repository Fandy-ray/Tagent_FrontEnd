"""整卷路径对照：三段并发出卷 + 本地/LLM 分批判卷。"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

OLD = "http://127.0.0.1:5098"
NEW = "http://127.0.0.1:5099"


def call(base, path, body, timeout=600):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode()), (time.perf_counter() - t0)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}"), (time.perf_counter() - t0)


def exam_shape(d):
    """试卷的结构不变量：题型区块、题量范围、公开投影不得泄漏答案。"""
    data = d.get("data", {})
    cloze, choice, essay = data.get("cloze", []), data.get("choice", []), data.get("essay", [])
    leaked = set()
    for q in cloze:
        leaked |= {k for k in q if k in {"accept", "match_mode", "explanation"}}
    for q in choice:
        leaked |= {k for k in q if k in {"correct_index", "explanation"}}
    for q in essay:
        leaked |= {k for k in q if k in {"reference_answer", "rubric"}}
    return {
        "code": d.get("code"),
        "keys": sorted(data),
        "cloze_keys": sorted(cloze[0]) if cloze else [],
        "choice_keys": sorted(choice[0]) if choice else [],
        "essay_keys": sorted(essay[0]) if essay else [],
        "total_points": data.get("total_points"),
        "leaked_answer_fields": sorted(leaked),
    }


def review_shape(d):
    data = d.get("data", {})
    results = data.get("results", [])
    return {
        "code": d.get("code"),
        "keys": sorted(data),
        "section_keys": sorted(data.get("sections", {})),
        "result_keys": sorted(results[0]) if results else [],
        "verdicts": sorted({r.get("verdict") for r in results}),
        "n_results": len(results),
    }


def main():
    print("=" * 92)
    out = {}
    for label, base in (("旧", OLD), ("新", NEW)):
        st, body, secs = call(base, "/quiz/exam/generate",
                              {"model": "deepseek-chat", "topic": "排队论"})
        print(f"[{label}] POST /quiz/exam/generate  HTTP {st}  {secs:.1f}s")
        if st != 200:
            print("    ", json.dumps(body, ensure_ascii=False)[:300])
            return 1
        d = body["data"]
        print(f"     题量 填空={len(d['cloze'])} 选择={len(d['choice'])} 解答={len(d['essay'])}"
              f"  总分={d['total_points']}  标题={d['title'][:24]}")
        out[label] = (body, secs)

    so, sn = exam_shape(out["旧"][0]), exam_shape(out["新"][0])
    print("\n出卷结构比对:", "一致" if so == sn else "不一致")
    if so != sn:
        print("  旧:", so)
        print("  新:", sn)
        return 1
    if so["leaked_answer_fields"]:
        print("  !! 公开投影泄漏答案字段:", so["leaked_answer_fields"])
        return 1
    print("  公开投影未泄漏任何答案字段（accept/correct_index/reference_answer/rubric）")

    # 判卷：全部留空 + 一个选择题乱填，走本地判分 + LLM 分批
    print()
    rv = {}
    for label, base in (("旧", OLD), ("新", NEW)):
        body = out[label][0]["data"]
        answers = {}
        for q in body["cloze"][:2]:
            answers[q["id"]] = "排队论"
        for q in body["choice"][:2]:
            answers[q["id"]] = 0
        for q in body["essay"][:1]:
            answers[q["id"]] = "排队论研究顾客到达与服务的随机过程。"
        st, resp, secs = call(base, "/quiz/exam/review",
                              {"model": "deepseek-chat", "exam_id": body["exam_id"], "answers": answers})
        print(f"[{label}] POST /quiz/exam/review    HTTP {st}  {secs:.1f}s")
        if st != 200:
            print("    ", json.dumps(resp, ensure_ascii=False)[:300])
            return 1
        print(f"     总分={resp['data']['total_score']}  判定分布={review_shape(resp)['verdicts']}")
        rv[label] = resp

    ro, rn = review_shape(rv["旧"]), review_shape(rv["新"])
    same = {k: (ro[k], rn[k]) for k in ro if ro[k] != rn[k] and k != "verdicts"}
    print("\n判卷结构比对:", "一致" if not same else f"不一致 {same}")
    return 0 if not same else 1


if __name__ == "__main__":
    sys.exit(main())
