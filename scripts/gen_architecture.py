"""Regenerate the auto-generated module reference in docs/ARCHITECTURE.md.

Parses every module under src/na_planner/ with the `ast` module (no imports, so it works
even if the code has unmet runtime deps), extracts each module's one-line docstring plus its
public classes and functions, and rewrites the block between the AUTOGEN markers.

Usage:
    py -3 scripts/gen_architecture.py            # rewrite the block in place
    py -3 scripts/gen_architecture.py --check    # exit 1 if the block is stale (for CI)
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "na_planner"
DOC = ROOT / "docs" / "ARCHITECTURE.md"
START = "<!-- AUTOGEN:START -->"
END = "<!-- AUTOGEN:END -->"


def _first_line(docstring: str | None) -> str:
    if not docstring:
        return ""
    return docstring.strip().splitlines()[0].strip()


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = ast.unparse(node.args)
    returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"{node.name}({args}){returns}"


def _public(name: str) -> bool:
    return not name.startswith("_")


def _describe_class(node: ast.ClassDef) -> list[str]:
    lines = [f"  - **class `{node.name}`**"]
    doc = _first_line(ast.get_docstring(node))
    if doc:
        lines.append(f"    - {doc}")
    fields = [
        f"`{t.target.id}`"
        for t in node.body
        if isinstance(t, ast.AnnAssign)
        and isinstance(t.target, ast.Name)
        and _public(t.target.id)
    ]
    if fields:
        lines.append(f"    - fields: {', '.join(fields)}")
    methods = [
        m.name
        for m in node.body
        if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and _public(m.name)
    ]
    if methods:
        lines.append(f"    - methods: {', '.join(methods)}")
    return lines


def _describe_module(path: Path) -> list[str]:
    rel = path.relative_to(ROOT).as_posix()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, OSError):
        return [f"### `{rel}`", "- _(could not parse)_", ""]

    lines = [f"### `{rel}`"]
    summary = _first_line(ast.get_docstring(tree))
    if summary:
        lines.append(f"_{summary}_")
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and _public(n.name)]
    funcs = [
        n
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and _public(n.name)
    ]
    for cls in classes:
        lines.extend(_describe_class(cls))
    for fn in funcs:
        lines.append(f"  - `{_signature(fn)}`")
    if not classes and not funcs:
        lines.append("  - _(no public API)_")
    lines.append("")
    return lines


def build_block() -> str:
    if not SRC.exists():
        return ("_No modules under `src/na_planner/` yet — this section populates as the "
                "code is built._")
    files = sorted(p for p in SRC.rglob("*.py") if p.name != "__init__.py")
    if not files:
        return ("_No modules under `src/na_planner/` yet — this section populates as the "
                "code is built._")
    out: list[str] = []
    for path in files:
        out.extend(_describe_module(path))
    return "\n".join(out).rstrip()


def render(text: str, block: str) -> str:
    pre, _, rest = text.partition(START)
    _, _, post = rest.partition(END)
    return f"{pre}{START}\n{block}\n{END}{post}"


def main(argv: list[str]) -> int:
    current = DOC.read_text(encoding="utf-8")
    updated = render(current, build_block())
    if "--check" in argv:
        if current != updated:
            print("ARCHITECTURE.md module reference is stale — run gen_architecture.py.")
            return 1
        return 0
    if current != updated:
        DOC.write_text(updated, encoding="utf-8")
        print("Updated docs/ARCHITECTURE.md module reference.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
