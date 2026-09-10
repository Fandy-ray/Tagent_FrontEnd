"""分层架构守卫。纯标准库，无需额外依赖。

用法（工作目录 basic-agent/）：

    python -m tools.check_architecture

检查项：
  1. 未定义的名字——引用了但既没定义、没 import、也不是内置
     （抽取式重构最容易漏的就是"函数搬走了、它依赖的 import 没跟着搬"，
       这种问题只在跑到那一行时才炸，测试未必覆盖得到）
  2. 未使用的 import
  3. 分层依赖方向（见 docs/basic-agent-layering-plan.md §9）
  4. 配置收口：os.getenv 只允许出现在 app/config.py
  5. Flask 只允许出现在 app/api/ 与 app/factory.py
  6. controller 之间不得互相 import
"""

from __future__ import annotations

import ast
import builtins
import pathlib
import sys


APP = pathlib.Path("app")

# 层 -> 禁止 import 的层
FORBIDDEN = {
    "app.repository": ("app.service", "app.api", "app.infra"),
    "app.schema": ("app.service", "app.api", "app.repository", "app.infra"),
    "app.util": ("app.service", "app.api", "app.repository", "app.infra", "app.schema"),
    "app.errors": ("app.service", "app.api", "app.repository", "app.infra", "app.schema"),
    "app.infra": ("app.service", "app.api", "app.repository"),
    "app.prompts": ("app.service", "app.api", "app.repository", "app.infra"),
    "app.service": ("app.api",),
    "app.rag": ("app.service", "app.api", "app.repository"),
    "app.api": ("app.repository",),
}

CONTROLLERS = {"health", "openai_compat", "agent", "exam", "admin", "internal"}


def module_name(path: pathlib.Path) -> str:
    parts = list(path.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def layer_of(mod: str) -> str | None:
    parts = mod.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else None


def imported_modules(tree: ast.AST) -> list[tuple[str, int]]:
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            out.append((n.module, n.lineno))
        elif isinstance(n, ast.Import):
            for a in n.names:
                out.append((a.name, n.lineno))
    return out


def bound_names(tree: ast.AST) -> set[str]:
    bound = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                bound.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                bound.add(a.asname or a.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            bound.add(node.id)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, ast.Global):
            bound.update(node.names)
    return bound


def used_names(tree: ast.AST) -> set[str]:
    used = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            used.add(n.id)
        elif isinstance(n, ast.Attribute):
            root = n
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name):
                used.add(root.id)
    return used


def import_bindings(tree: ast.AST) -> list[tuple[str, int]]:
    """(本模块可见的名字, 行号)，用于未使用检测。"""
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                out.append(((a.asname or a.name).split(".")[0], n.lineno))
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                if a.name == "*":
                    continue
                out.append((a.asname or a.name, n.lineno))
    return out


def main() -> int:
    problems: list[str] = []
    files = sorted(p for p in APP.rglob("*.py") if "__pycache__" not in p.parts)

    for path in files:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        mod = module_name(path)
        layer = layer_of(mod)
        rel = path.as_posix()

        # 1. 未定义的名字
        missing = used_names(tree) - bound_names(tree) - set(dir(builtins)) - {
            "__name__", "__file__", "__doc__",
        }
        for name in sorted(missing):
            problems.append(f"{rel}: 未定义的名字 `{name}`")

        # 2. 未使用的 import（__init__.py 的重导出除外）
        if path.name != "__init__.py":
            # 字符串形式的类型注解也算使用（如 dataclass 里的 "ExamCache"）
            annotated = {
                n.value for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
            }
            text_names = used_names(tree) | annotated
            for name, lineno in import_bindings(tree):
                if name == "annotations":
                    continue
                if name not in text_names:
                    problems.append(f"{rel}:{lineno}: 未使用的 import `{name}`")

        # 3. 分层方向
        for imported, lineno in imported_modules(tree):
            for bad in FORBIDDEN.get(layer, ()):
                if imported == bad or imported.startswith(bad + "."):
                    problems.append(
                        f"{rel}:{lineno}: {layer} 不得依赖 {bad}（import {imported}）"
                    )

        # 4. 配置收口
        if rel != "app/config.py" and ("os.getenv" in text or "os.environ" in text):
            problems.append(f"{rel}: os.getenv/os.environ 只允许出现在 app/config.py")

        # 5. Flask 边界
        if not (rel.startswith("app/api/") or rel == "app/factory.py"):
            for imported, lineno in imported_modules(tree):
                if imported == "flask" or imported.startswith("flask."):
                    problems.append(f"{rel}:{lineno}: 只有 api 层与启动类可以 import flask")

        # 6. controller 互调
        if rel.startswith("app/api/") and path.stem in CONTROLLERS:
            for imported, lineno in imported_modules(tree):
                if imported.startswith("app.api."):
                    target = imported.rsplit(".", 1)[-1]
                    if target in CONTROLLERS:
                        problems.append(
                            f"{rel}:{lineno}: controller 不得 import 兄弟 controller（{imported}）"
                        )

    if problems:
        print(f"架构检查未通过，共 {len(problems)} 项：\n")
        for p in problems:
            print("  " + p)
        return 1

    print(f"架构检查通过：{len(files)} 个模块，6 项规则全部满足。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
