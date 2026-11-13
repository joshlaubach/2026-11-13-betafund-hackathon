"""Reorganize the flat app/ package into subpackages and rewrite its references.

Default is a dry run: print the plan and write nothing. --apply creates the
subpackage __init__.py files, git-moves each module, and rewrites the text of
every module in place. Path-relative code (__file__) is reported, not rewritten.
"""

import ast
import re
import shutil
import subprocess
import sys
import tokenize
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = REPO_ROOT / "app"
PACKAGE = "app"
INIT_NAME = "__init__.py"
EXIT_APPLY_FAILED = 1
EXIT_BAD_TREE = 2

_GROUPS: dict[str, tuple[str, ...]] = {
    "": ("config", "safe_parse", "sandbox", "worker", "offline"),
    "shared": (
        "clean_answer", "calculus_core", "integral_core", "integral_finish", "function_pool",
        "difficulty", "figures", "figure_labels", "graph_problems", "wordproblem",
    ),
    "calc1": (
        "limits", "limits_samples", "derivatives", "derivatives_samples", "derivative_rules",
        "derivative_rules_samples", "derivative_advanced", "derivative_advanced_samples", "applications",
        "applications_samples", "applications_b", "applications_b_samples", "rates_optimization",
        "rates_optimization_samples", "integration_basics", "integration_basics_checks",
        "integration_basics_samples", "usub", "usub_samples", "integral_applications",
        "integral_applications_checks", "integral_applications_samples",
    ),
    "calc2": (
        "by_parts", "by_parts_samples", "partial_fractions", "partial_samples", "trig_substitution",
        "trig_sub_samples", "trigfam", "trig_samples", "improper", "improper_samples", "rules",
        "rules_samples", "strategy", "strategy_samples", "error_bounds", "arc_length",
        "arc_length_checks", "arc_length_samples", "parametric", "polar", "parametric_polar",
        "parametric_polar_checks", "parametric_polar_samples", "pp_core", "power_series",
        "power_series_b", "power_series_checks", "power_series_core", "power_series_samples",
        "sequences_series", "sequences_series_checks", "sequences_series_samples", "series_tests",
        "series_tests_checks", "series_tests_core", "series_tests_samples",
    ),
    "api": ("main", "pipeline", "auth", "db", "keys", "schemas"),
}

# Module stem -> subpackage (relative to app/). "" means the module stays at top level.
MAPPING: dict[str, str] = {stem: sub for sub, stems in _GROUPS.items() for stem in stems}
SUBPACKAGES: tuple[str, ...] = tuple(sub for sub in _GROUPS if sub)


@dataclass(frozen=True)
class Edit:
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class Plan:
    moves: tuple[tuple[str, str], ...]
    inits: tuple[str, ...]
    changed_stems: tuple[str, ...]
    warnings: tuple[str, ...]


# -- text helpers ----------------------------------------------------------------------------------------------------


def _line_starts(source: str) -> list[int]:
    """starts[i] is the character offset where 1-based line i+1 begins."""
    starts = [0]
    for line in source.split("\n"):
        starts.append(starts[-1] + len(line) + 1)
    return starts


def _offset(source: str, starts: list[int], lineno: int, byte_col: int) -> int:
    """Convert an ast (line, UTF-8 byte column) pair into a character offset in source."""
    line_start = starts[lineno - 1]
    line_end = source.find("\n", line_start)
    line_end = len(source) if line_end == -1 else line_end
    prefix = source[line_start:line_end].encode("utf-8")[:byte_col]
    return line_start + len(prefix.decode("utf-8"))


def _apply_edits(source: str, edits: list[Edit]) -> str:
    out = source
    limit = len(source)
    for edit in sorted(edits, key=lambda e: e.start, reverse=True):
        if edit.end > limit:
            raise ValueError("overlapping edits")
        out = out[: edit.start] + edit.text + out[edit.end :]
        limit = edit.start
    return out


def _rewrite_prose(text: str, mapping: dict[str, str]) -> str:
    """Rewrite app/STEM and app.STEM references in comment or docstring text."""
    moved = {stem: sub for stem, sub in mapping.items() if sub}
    if not moved:
        return text
    alternation = "|".join(re.escape(stem) for stem in sorted(moved, key=len, reverse=True))
    path_ref = re.compile(rf"(?<![\w.])app/({alternation})(?!\w)")
    dotted_ref = re.compile(rf"(?<![\w.])app\.({alternation})(?!\w)")
    text = path_ref.sub(lambda m: f"app/{moved[m.group(1)]}/{m.group(1)}", text)
    return dotted_ref.sub(lambda m: f"app.{moved[m.group(1)]}.{m.group(1)}", text)


# -- structural rewrite (imports and exact module-name strings) ------------------------------------------------------


def _fmt_alias(alias: ast.alias) -> str:
    return f"{alias.name} as {alias.asname}" if alias.asname else alias.name


def _split_statements(node: ast.ImportFrom, mapping: dict[str, str]) -> list[str]:
    """Regenerate `from app import ...` as one statement per destination, unknown names first."""
    remaining = [_fmt_alias(a) for a in node.names if not mapping.get(a.name)]
    groups: dict[str, list[str]] = {}
    for alias in node.names:
        sub = mapping.get(alias.name)
        if sub:
            groups.setdefault(sub, []).append(_fmt_alias(alias))
    statements = [f"from {PACKAGE} import {', '.join(remaining)}"] if remaining else []
    for sub, names in groups.items():
        statements.append(f"from {PACKAGE}.{sub} import {', '.join(names)}")
    return statements


def _trailing_comment_end(source: str, end: int) -> int | None:
    """End offset of a comment that follows the statement on its last line, or None."""
    eol = source.find("\n", end)
    eol = len(source) if eol == -1 else eol
    content_end = eol - 1 if eol - 1 >= end and source[eol - 1] == "\r" else eol
    return content_end if source[end:content_end].lstrip().startswith("#") else None


def _newline_at(source: str, offset: int) -> str:
    """The line ending of the line containing offset: "\\r\\n" or "\\n"."""
    eol = source.find("\n", offset)
    return "\r\n" if eol > 0 and source[eol - 1] == "\r" else "\n"


def _split_edit(source: str, starts: list[int], node: ast.ImportFrom, mapping: dict[str, str]) -> Edit:
    start = _offset(source, starts, node.lineno, node.col_offset)
    end = _offset(source, starts, node.end_lineno, node.end_col_offset)
    line_start = starts[node.lineno - 1]
    if source[line_start:start].strip():
        raise ValueError(f"from-import at line {node.lineno} does not start its line")
    if "#" in source[start:end]:
        raise ValueError(f"comment inside split from-import at line {node.lineno}")
    indent = source[line_start:start]
    newline = _newline_at(source, start)
    comment_end = _trailing_comment_end(source, end)
    tail_end = end if comment_end is None else comment_end
    tail = "" if comment_end is None else source[end:comment_end]
    text = (newline + indent).join(_split_statements(node, mapping))
    return Edit(start, tail_end, text + tail)


def _module_edit(source: str, starts: list[int], node: ast.ImportFrom, mapping: dict[str, str]) -> Edit | None:
    stem = node.module[len(PACKAGE) + 1 :]
    sub = mapping.get(stem)
    if not sub:
        return None
    start = _offset(source, starts, node.lineno, node.col_offset)
    pattern = re.compile(rf"from\s+({re.escape(PACKAGE + '.' + stem)})(?!\w)")
    match = pattern.match(source, start)
    if match is None:
        raise ValueError(f"module path of from-import at line {node.lineno} not found")
    return Edit(match.start(1), match.end(1), f"{PACKAGE}.{sub}.{stem}")


def _from_edits(source: str, starts: list[int], node: ast.ImportFrom, mapping: dict[str, str]) -> list[Edit]:
    if node.module == PACKAGE:
        if any(mapping.get(alias.name) for alias in node.names):
            return [_split_edit(source, starts, node, mapping)]
        return []
    edit = _module_edit(source, starts, node, mapping)
    return [edit] if edit else []


def _import_edits(source: str, starts: list[int], node: ast.Import, mapping: dict[str, str]) -> list[Edit]:
    edits = []
    for alias in node.names:
        if not alias.name.startswith(PACKAGE + "."):
            continue
        stem = alias.name[len(PACKAGE) + 1 :]
        sub = mapping.get(stem)
        if not sub:
            continue
        start = _offset(source, starts, alias.lineno, alias.col_offset)
        if not source.startswith(alias.name, start):
            raise ValueError(f"import name at line {alias.lineno} not found")
        edits.append(Edit(start, start + len(alias.name), f"{PACKAGE}.{sub}.{stem}"))
    return edits


def _string_edit(source: str, starts: list[int], node: ast.Constant, mapping: dict[str, str]) -> Edit | None:
    if not (isinstance(node.value, str) and node.value.startswith(PACKAGE + ".")):
        return None
    stem = node.value[len(PACKAGE) + 1 :]
    sub = mapping.get(stem)
    if not sub:
        return None
    start = _offset(source, starts, node.lineno, node.col_offset)
    end = _offset(source, starts, node.end_lineno, node.end_col_offset)
    segment = source[start:end].replace(f"{PACKAGE}.{stem}", f"{PACKAGE}.{sub}.{stem}", 1)
    return Edit(start, end, segment)


def _structural_edits(source: str, tree: ast.AST, mapping: dict[str, str]) -> list[Edit]:
    starts = _line_starts(source)
    edits: list[Edit] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            edits.extend(_from_edits(source, starts, node, mapping))
        elif isinstance(node, ast.Import):
            edits.extend(_import_edits(source, starts, node, mapping))
        elif isinstance(node, ast.Constant):
            edit = _string_edit(source, starts, node, mapping)
            if edit is not None:
                edits.append(edit)
    return edits


# -- prose rewrite (comments and docstrings) -------------------------------------------------------------------------


def _docstring_nodes(tree: ast.AST) -> list[ast.Constant]:
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                found.append(first.value)
    return found


def _prose_edits(source: str, tree: ast.AST, mapping: dict[str, str]) -> list[Edit]:
    starts = _line_starts(source)
    edits = []
    for node in _docstring_nodes(tree):
        start = _offset(source, starts, node.lineno, node.col_offset)
        end = _offset(source, starts, node.end_lineno, node.end_col_offset)
        new = _rewrite_prose(source[start:end], mapping)
        if new != source[start:end]:
            edits.append(Edit(start, end, new))
    for token in tokenize.generate_tokens(StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            start = starts[token.start[0] - 1] + token.start[1]
            end = start + len(token.string)
            new = _rewrite_prose(token.string, mapping)
            if new != token.string:
                edits.append(Edit(start, end, new))
    return edits


def rewrite_source(source: str, mapping: dict[str, str]) -> str:
    """Return source with every reference to a moved module rewritten. Pure and idempotent."""
    structured = _apply_edits(source, _structural_edits(source, ast.parse(source), mapping))
    return _apply_edits(structured, _prose_edits(structured, ast.parse(structured), mapping))


# -- tree checks, plan, apply ----------------------------------------------------------------------------------------


class ApplyError(RuntimeError):
    """A failed apply step; the message names the step and the file it was working on."""


def new_relpath(stem: str, mapping: dict[str, str] = MAPPING) -> str:
    sub = mapping[stem]
    return f"{sub}/{stem}.py" if sub else f"{stem}.py"


def subpackages_of(mapping: dict[str, str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(sub for sub in mapping.values() if sub))


def _module_stems(app_dir: Path) -> set[str]:
    return {p.stem for p in app_dir.glob("*.py") if p.name != INIT_NAME}


def tree_problems(app_dir: Path, mapping: dict[str, str] = MAPPING) -> list[str]:
    if not app_dir.is_dir():
        return [f"{app_dir} not found"]
    on_disk = _module_stems(app_dir)
    problems = [f"mapped module has no file: {stem}.py" for stem in sorted(set(mapping) - on_disk)]
    problems += [f"unmapped module in app/: {stem}.py" for stem in sorted(on_disk - set(mapping))]
    for stem, sub in mapping.items():
        if sub and (app_dir / new_relpath(stem, mapping)).exists():
            problems.append(f"destination already exists: app/{new_relpath(stem, mapping)}")
    return problems


def preflight(app_dir: Path) -> list[str]:
    """Reasons --apply must refuse before touching anything. Empty means it may proceed."""
    if shutil.which("git") is None:
        return ["git is not available on PATH; --apply needs git to move files"]
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--", app_dir.name],
            cwd=app_dir.parent,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        return [f"could not run git: {exc}"]
    if result.returncode != 0:
        return [f"git status failed: {result.stderr.strip()}"]
    dirty = [line for line in result.stdout.splitlines() if line.strip()]
    if not dirty:
        return []
    return [f"{app_dir.name}/ has uncommitted changes; commit or stash them before --apply:", *dirty]


def _read(path: Path) -> str:
    with path.open(encoding="utf-8", newline="") as handle:
        return handle.read()


def _write(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def _path_warnings(app_dir: Path, mapping: dict[str, str] = MAPPING) -> tuple[str, ...]:
    warnings = []
    for stem, sub in mapping.items():
        if sub and "__file__" in _read(app_dir / f"{stem}.py"):
            warnings.append(
                f"app/{stem}.py uses __file__ and moves to app/{new_relpath(stem, mapping)}; "
                "its path-relative code is not rewritten"
            )
    return tuple(warnings)


def _changed_stems(app_dir: Path, mapping: dict[str, str]) -> tuple[str, ...]:
    changed = []
    for stem in mapping:
        old_text = _read(app_dir / f"{stem}.py")
        if rewrite_source(old_text, mapping) != old_text:
            changed.append(stem)
    return tuple(changed)


def build_plan(app_dir: Path, mapping: dict[str, str] = MAPPING) -> Plan:
    moves = tuple((f"app/{stem}.py", f"app/{new_relpath(stem, mapping)}") for stem, sub in mapping.items() if sub)
    inits = tuple(f"app/{sub}/{INIT_NAME}" for sub in subpackages_of(mapping))
    return Plan(
        moves=moves,
        inits=inits,
        changed_stems=_changed_stems(app_dir, mapping),
        warnings=_path_warnings(app_dir, mapping),
    )


def format_plan(plan: Plan, mapping: dict[str, str] = MAPPING) -> list[str]:
    lines = [f"move {old} -> {new}" for old, new in plan.moves]
    lines += [f"create {init}" for init in plan.inits]
    lines.append(f"files whose text would change: {len(plan.changed_stems)} of {len(mapping)}")
    lines += [f"warning: {message}" for message in plan.warnings]
    return lines


@contextmanager
def _step(name: str, path: str) -> Iterator[None]:
    try:
        yield
    except Exception as exc:
        raise ApplyError(f"{name} failed for {path}: {exc}") from exc


def _create_init(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _write(path, "")


def _git_mv(repo_root: Path, old: str, new: str) -> None:
    result = subprocess.run(
        ["git", "mv", old, new],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git mv exited {result.returncode}")


def _rewrite_file(path: Path, mapping: dict[str, str]) -> None:
    old_text = _read(path)
    new_text = rewrite_source(old_text, mapping)
    if new_text != old_text:
        _write(path, new_text)


def apply_plan(app_dir: Path, plan: Plan, mapping: dict[str, str] = MAPPING) -> None:
    """Create subpackages, git-mv every module, then rewrite text. Stops at the first failing step."""
    repo_root = app_dir.parent
    for init in plan.inits:
        with _step("create folder and __init__.py", init):
            _create_init(repo_root / init)
    for old, new in plan.moves:
        with _step("git mv", f"{old} -> {new}"):
            _git_mv(repo_root, old, new)
    for stem in mapping:
        path = app_dir / new_relpath(stem, mapping)
        with _step("rewrite text", f"app/{path.relative_to(app_dir).as_posix()}"):
            _rewrite_file(path, mapping)


def _restore_hint(plan: Plan) -> list[str]:
    folders = sorted({str(Path(init).parent.as_posix()) for init in plan.inits})
    return [
        "the tree may be partly changed. To restore it, run from the repo root:",
        "  git restore --staged --worktree app",
        "  then delete the new folders created by this run: " + ", ".join(folders),
    ]


def main(
    argv: list[str] | None = None,
    app_dir: Path = APP_DIR,
    mapping: dict[str, str] = MAPPING,
) -> int:
    args = sys.argv[1:] if argv is None else argv
    apply = "--apply" in args
    problems = tree_problems(app_dir, mapping)
    if not problems and apply:
        problems = preflight(app_dir)
    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        return EXIT_BAD_TREE
    plan = build_plan(app_dir, mapping)
    for line in format_plan(plan, mapping):
        print(line)
    if not apply:
        print("dry run: nothing written (pass --apply to apply)")
        return 0
    try:
        apply_plan(app_dir, plan, mapping)
    except ApplyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        for line in _restore_hint(plan):
            print(line, file=sys.stderr)
        return EXIT_APPLY_FAILED
    print("applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
