"""Evidence-first static inspection of Python source trees.

This is a small, dependency-free REA-inspired capability for understanding code
before proposing changes. It parses source with ast; it never imports, executes,
or modifies inspected files. Static findings are clues, not proof of runtime
behavior.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path


@dataclass(frozen=True)
class SourceFile:
    path: str
    sha256: str
    size_bytes: int
    parsed: bool


@dataclass(frozen=True)
class SourceSymbol:
    kind: str
    name: str
    qualified_name: str
    path: str
    line: int
    end_line: int | None


@dataclass(frozen=True)
class ImportReference:
    module: str
    names: tuple[str, ...]
    path: str
    line: int
    relative_level: int = 0


@dataclass(frozen=True)
class CallReference:
    caller: str
    callee: str
    path: str
    line: int


@dataclass(frozen=True)
class InspectionReport:
    root: str
    files: tuple[SourceFile, ...]
    symbols: tuple[SourceSymbol, ...]
    imports: tuple[ImportReference, ...]
    calls: tuple[CallReference, ...]
    warnings: tuple[str, ...]


class _SourceVisitor(ast.NodeVisitor):
    def __init__(self, relative_path: str) -> None:
        self.relative_path = relative_path
        self.symbols: list[SourceSymbol] = []
        self.imports: list[ImportReference] = []
        self.calls: list[CallReference] = []
        self._scope: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        qualified = ".".join((*self._scope, node.name))
        self.symbols.append(SourceSymbol("class", node.name, qualified, self.relative_path,
                                         node.lineno, getattr(node, "end_lineno", None)))
        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        qualified = ".".join((*self._scope, node.name))
        self.symbols.append(SourceSymbol("function", node.name, qualified, self.relative_path,
                                         node.lineno, getattr(node, "end_lineno", None)))
        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Import(self, node: ast.Import) -> None:
        self.imports.append(ImportReference(
            module="", names=tuple(alias.name for alias in node.names),
            path=self.relative_path, line=node.lineno,
        ))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.imports.append(ImportReference(
            module=node.module or "", names=tuple(alias.name for alias in node.names),
            path=self.relative_path, line=node.lineno, relative_level=node.level,
        ))

    def visit_Call(self, node: ast.Call) -> None:
        caller = ".".join(self._scope) if self._scope else "<module>"
        self.calls.append(CallReference(caller, _call_name(node.func), self.relative_path, node.lineno))
        self.generic_visit(node)


def _call_name(node: ast.expr) -> str:
    """Return a static dotted name; dynamic expressions remain explicitly unknown."""
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return ".".join(reversed(parts))
    if isinstance(current, ast.Call):
        return "<dynamic-call-result>"
    return "<dynamic-call>"


def inspect_source_tree(
    root: str | Path,
    *,
    max_files: int = 500,
    max_file_bytes: int = 1_000_000,
) -> InspectionReport:
    """Inventory and parse Python files beneath root without executing them.

    Symlinks are excluded. The limits are hard bounds, and parse/read failures
    are returned as warnings rather than being silently treated as valid code.
    """
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise ValueError("Inspection root must be an existing directory.")
    if not 1 <= max_files <= 5000:
        raise ValueError("max_files must be between 1 and 5000.")
    if not 1 <= max_file_bytes <= 10_000_000:
        raise ValueError("max_file_bytes must be between 1 and 10000000.")

    file_records: list[SourceFile] = []
    symbols: list[SourceSymbol] = []
    imports: list[ImportReference] = []
    calls: list[CallReference] = []
    warnings: list[str] = []

    candidates: list[Path] = []
    for current, directories, filenames in os.walk(root_path, followlinks=False):
        current_path = Path(current)
        directories[:] = sorted(
            name for name in directories
            if not (current_path / name).is_symlink() and name not in {".git", "__pycache__", ".venv", "venv"}
        )
        for filename in sorted(filenames):
            path = current_path / filename
            if filename.endswith(".py") and not path.is_symlink():
                candidates.append(path)
    candidates.sort(key=lambda item: item.relative_to(root_path).as_posix())

    if len(candidates) > max_files:
        warnings.append(f"File limit reached: inspected first {max_files} of {len(candidates)} Python files.")
        candidates = candidates[:max_files]

    for path in candidates:
        relative = path.relative_to(root_path).as_posix()
        try:
            size = path.stat().st_size
            if size > max_file_bytes:
                file_records.append(SourceFile(relative, "", size, False))
                warnings.append(f"Skipped oversized file: {relative} ({size} bytes).")
                continue
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            try:
                source = raw.decode("utf-8")
                tree = ast.parse(source, filename=relative)
            except (UnicodeDecodeError, SyntaxError) as exc:
                file_records.append(SourceFile(relative, digest, len(raw), False))
                warnings.append(f"Could not parse {relative}: {type(exc).__name__}.")
                continue
            file_records.append(SourceFile(relative, digest, len(raw), True))
            visitor = _SourceVisitor(relative)
            visitor.visit(tree)
            symbols.extend(visitor.symbols)
            imports.extend(visitor.imports)
            calls.extend(visitor.calls)
        except OSError as exc:
            file_records.append(SourceFile(relative, "", 0, False))
            warnings.append(f"Could not read {relative}: {type(exc).__name__}.")

    return InspectionReport(
        root=str(root_path),
        files=tuple(file_records),
        symbols=tuple(symbols),
        imports=tuple(imports),
        calls=tuple(calls),
        warnings=tuple(warnings),
    )


def trace_symbol(report: InspectionReport, symbol: str) -> dict[str, tuple[object, ...]]:
    """Find exact symbol definitions and static call-name matches.

    This is a navigation aid, not a complete call graph: aliases, reflection,
    dynamic dispatch, decorators, and runtime-generated calls may be unresolved.
    """
    query = symbol.strip()
    if not query or len(query) > 200:
        raise ValueError("symbol must contain 1–200 characters.")
    normalized = query.casefold()
    definitions = tuple(
        item for item in report.symbols
        if item.name.casefold() == normalized or item.qualified_name.casefold() == normalized
    )
    callers = tuple(
        item for item in report.calls
        if item.callee.casefold() == normalized
        or item.callee.casefold().endswith("." + normalized)
    )
    return {"definitions": definitions, "callers": callers}
