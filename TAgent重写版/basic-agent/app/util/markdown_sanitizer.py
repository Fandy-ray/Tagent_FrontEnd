"""LLM 输出的 Markdown 清洗。

模型经常吐出半截的表格、没配对的 $$ 或 \begin{...}，直接渲染会把前端顶坏。
这里做的全是纯文本修补：截断补齐、配对检查、字段表识别。

放在 util/ 而不是 service/：跟 RAG、出题、判卷都没关系，任何层都可以用，
本模块不 import 任何业务模块。
"""

from __future__ import annotations

import re


_FIELD_TYPE_NAMES = {
    "bool",
    "boolean",
    "double",
    "enumerated",
    "float",
    "handle",
    "int",
    "integer",
    "long",
    "short",
    "string",
    "time",
    "unsigned int",
    "unsigned long",
}

_GREEK_LATEX_COMMAND = re.compile(
    r"\\(?:alpha|beta|gamma|delta|epsilon|varepsilon|zeta|eta|theta|vartheta|iota|kappa|lambda|mu|nu|xi|pi|varpi|rho|varrho|sigma|varsigma|tau|upsilon|phi|varphi|chi|psi|omega|Gamma|Delta|Theta|Lambda|Xi|Pi|Sigma|Upsilon|Phi|Psi|Omega)(?:_\{[^{}\n]+\}|_[A-Za-z0-9]+)?"
)

def clean_reference_for_display(context: str) -> str:
    sections = []
    for section in context.split("\n\n---\n\n"):
        lines = section.splitlines()
        while lines and _is_orphan_table_row(lines[0]):
            lines.pop(0)
        cleaned = _sanitize_markdown_fragment("\n".join(lines))
        if cleaned:
            sections.append(cleaned)
    return "\n\n---\n\n".join(sections)

def _sanitize_markdown_fragment(value: str) -> str:
    cleaned = value.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"(?m)^\s*--- Page \d+ ---\s*$", "", cleaned)
    cleaned = _repair_partial_markdown_tables(cleaned)
    cleaned = _drop_unclosed_display_math(cleaned)
    cleaned = _drop_unclosed_latex_environment(cleaned)
    cleaned = re.sub(
        r"(?<!\\)(?<!\$)\$([^$\n]+)\$(?!\$)",
        lambda match: f"${match.group(1).strip()}$",
        cleaned,
    )
    cleaned = _drop_unmatched_inline_math(cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()

def _repair_partial_markdown_tables(value: str) -> str:
    lines = value.splitlines()
    output: list[str] = []
    index = 0
    while index < len(lines):
        if not _is_markdown_table_row(lines[index]):
            output.append(lines[index])
            index += 1
            continue

        table_rows: list[str] = []
        while index < len(lines) and _is_markdown_table_row(lines[index]):
            table_rows.append(lines[index].strip())
            index += 1

        cells = [_markdown_table_cells(row) for row in table_rows]
        column_count = len(cells[0]) if cells else 0
        is_rectangular = column_count >= 2 and all(len(row) == column_count for row in cells)
        has_separator = any(_is_markdown_separator_row(row) for row in cells)
        if len(table_rows) >= 2 and is_rectangular and not has_separator:
            separator = "| " + " | ".join("---" for _ in range(column_count)) + " |"
            if _looks_like_field_table(cells):
                table_rows = ["| 属性名 | 类型 | 描述 |", separator, *table_rows]
        output.extend(table_rows)

    return "\n".join(output)

def _is_markdown_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 3

def _markdown_table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]

def _is_markdown_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)

def _looks_like_field_table(rows: list[list[str]]) -> bool:
    if not rows or len(rows[0]) != 3:
        return False
    type_cells = [re.sub(r"\s+", " ", row[1].strip(" `*").lower()) for row in rows]
    recognized = sum(cell in _FIELD_TYPE_NAMES for cell in type_cells)
    return recognized >= max(2, (len(rows) + 1) // 2)

def clean_generated_markdown(value: str) -> str:
    cleaned = _sanitize_markdown_fragment(value)
    parts = re.split(r"(\$\$[\s\S]*?\$\$|\$[^$\n]*\$)", cleaned)
    for index in range(0, len(parts), 2):
        parts[index] = _GREEK_LATEX_COMMAND.sub(lambda match: f"${match.group(0)}$", parts[index])
    return "".join(parts)

def _drop_unclosed_display_math(value: str) -> str:
    lines = value.splitlines()
    output: list[str] = []
    opening_index: int | None = None
    for line in lines:
        output.append(line)
        if line.strip() != "$$":
            continue
        if opening_index is None:
            opening_index = len(output) - 1
        else:
            opening_index = None
    if opening_index is not None:
        del output[opening_index:]
    return "\n".join(output)

def _drop_unclosed_latex_environment(value: str) -> str:
    for match in re.finditer(r"\\begin\{([^}]+)\}", value):
        closing = rf"\end{{{match.group(1)}}}"
        if value.find(closing, match.end()) == -1:
            return value[: match.start()].rstrip()
    return value

def _drop_unmatched_inline_math(value: str) -> str:
    positions: list[int] = []
    index = 0
    while index < len(value):
        if value[index] == "\\":
            index += 2
            continue
        if value.startswith("$$", index):
            index += 2
            continue
        if value[index] == "$":
            positions.append(index)
        index += 1
    if len(positions) % 2:
        return value[: positions[-1]].rstrip()
    return value

def truncate_markdown_fragment(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return _sanitize_markdown_fragment(value)
    prefix = value[:max_chars]
    candidates = [
        prefix.rfind("\n\n"),
        prefix.rfind("\n"),
        prefix.rfind("。"),
        prefix.rfind("；"),
        prefix.rfind(". "),
        prefix.rfind("; "),
    ]
    boundary = max(candidates)
    if boundary >= max_chars // 2:
        prefix = prefix[:boundary]
    return _sanitize_markdown_fragment(prefix)

def _is_orphan_table_row(line: str) -> bool:
    stripped = line.strip()
    if not (stripped.startswith("|") and stripped.endswith("|")):
        return False
    if re.search(r"[\u4e00-\u9fffA-Za-z]", stripped):
        return False
    numeric_cells = re.findall(r"-?\d+(?:\.\d+)?", stripped)
    return len(numeric_cells) >= 3
