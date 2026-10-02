"""启动 / 停止脚本的写法检查。

macOS 自带的 bash 3.2 在 UTF-8 环境（终端默认就是）下，会把紧跟在变量名后面的中文字符的首字节
吞进变量名：`"$FRONTEND_PORT，$FRONT_MODE"` 变成去找一个叫 `FRONTEND_PORT\\xef` 的变量，
`set -u` 下直接报 unbound variable 退出（2026-10-03，双击 start.command 时出现，basic-agent 已经起来、前端没起）。
在没设语言的环境里跑不会出错，所以手动测试很容易漏。这里把所有 .sh 扫一遍：变量后面直接跟非 ASCII 字符的，一律要写成 ${VAR}。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]  # TAgent重写版/
SCRIPTS = sorted(
    {*ROOT.glob("scripts/*.sh"), *ROOT.glob("deploy/**/*.sh"), *ROOT.parent.glob("*.command")}
)
BARE_VAR_BEFORE_NON_ASCII = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*(?=[^\x00-\x7f])")


def test_there_are_scripts_to_check():
    assert any(p.name == "start.sh" for p in SCRIPTS)


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_no_bare_variable_followed_by_chinese(script):
    offenders = []
    for number, line in enumerate(script.read_text(encoding="utf-8").splitlines(), start=1):
        if line.lstrip().startswith("#"):
            continue  # 注释里专门举了反例
        if BARE_VAR_BEFORE_NON_ASCII.search(line):
            offenders.append(f"{script.name}:{number}: {line.strip()}")
    assert not offenders, "变量后面直接跟中文，要写成 ${VAR}：\n" + "\n".join(offenders)
