"""Tests for scripts/reorg_app.py.

Synthetic-snippet tests exercise rewrite_source directly. Real-tree tests read the
modules under app/ without modifying them. The dry-run test checks that main()
writes nothing. These tests never run the script with --apply.
"""

import ast
import copy
import difflib
import re
import sys
from collections import Counter
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = REPO_ROOT / "app"
# The migration has been applied to the real tree (app/ is now calc1/, calc2/, shared/, api/). The checks that read
# the old flat layout can no longer run and are skipped; the synthetic and throwaway-repo tests still run.
ALREADY_MIGRATED = not (APP_DIR / "limits.py").exists()
OLD_LAYOUT = pytest.mark.skipif(ALREADY_MIGRATED, reason="app/ was already reorganized; this checks the old flat layout")
sys.path.insert(0, str(REPO_ROOT))

from scripts.reorg_app import (  # noqa: E402
    MAPPING,
    SUBPACKAGES,
    main,
    rewrite_source,
)

SMALL = {
    "limits": "calc1",
    "derivatives": "calc1",
    "integral_core": "shared",
    "difficulty": "shared",
    "trigfam": "calc2",
    "keys": "api",
    "config": "",
    "offline": "",
}


def rewrite(source: str) -> str:
    return rewrite_source(source, SMALL)


# -- mapping ---------------------------------------------------------------------------------------------------------


@OLD_LAYOUT
def test_mapping_covers_exactly_the_modules_on_disk():
    on_disk = {p.stem for p in APP_DIR.glob("*.py") if p.name != "__init__.py"}
    assert set(MAPPING) == on_disk


def test_mapping_group_counts_are_10_22_36_6_and_5():
    counts = Counter(MAPPING.values())
    assert counts["shared"] == 10
    assert counts["calc1"] == 22
    assert counts["calc2"] == 36
    assert counts["api"] == 6
    assert counts[""] == 5
    assert set(SUBPACKAGES) == {"shared", "calc1", "calc2", "api"}


# -- rewrite_source: imports -----------------------------------------------------------------------------------------


def test_simple_from_import_changes_only_the_module_path():
    assert rewrite("from app.limits import verify\n") == "from app.calc1.limits import verify\n"


def test_multiline_parenthesized_from_import_keeps_layout_and_trailing_comment():
    src = "from app.integral_core import (  # noqa: F401\n    L, x,\n)  # noqa\n"
    expected = "from app.shared.integral_core import (  # noqa: F401\n    L, x,\n)  # noqa\n"
    assert rewrite(src) == expected


def test_from_app_import_keeps_unknown_names_and_moves_known_ones():
    src = "from app import catalog, difficulty, verify\n"
    assert rewrite(src) == "from app import catalog, verify\nfrom app.shared import difficulty\n"


def test_from_app_import_splits_into_one_statement_per_destination():
    src = "from app import limits, difficulty, derivatives\n"
    expected = "from app.calc1 import limits, derivatives\nfrom app.shared import difficulty\n"
    assert rewrite(src) == expected


def test_from_app_import_preserves_aliases():
    src = "from app import limits as lim, keys as k\n"
    assert rewrite(src) == "from app.calc1 import limits as lim\nfrom app.api import keys as k\n"


def test_from_app_import_mixed_top_level_name_stays():
    src = "from app import config, limits\n"
    assert rewrite(src) == "from app import config\nfrom app.calc1 import limits\n"


def test_indented_lazy_import_inside_function_keeps_indentation():
    src = "def f():\n    from app import limits, difficulty\n    return limits\n"
    expected = "def f():\n    from app.calc1 import limits\n    from app.shared import difficulty\n    return limits\n"
    assert rewrite(src) == expected


def test_trailing_comment_on_split_import_attaches_to_last_statement():
    src = "from app import limits, difficulty  # lazy\n"
    assert rewrite(src) == "from app.calc1 import limits\nfrom app.shared import difficulty  # lazy\n"


def test_import_module_path_is_rewritten_with_and_without_alias():
    assert rewrite("import app.limits\n") == "import app.calc1.limits\n"
    assert rewrite("import app.limits as lim\n") == "import app.calc1.limits as lim\n"


def test_import_of_top_level_module_is_unchanged():
    src = "import app.config\nfrom app.config import settings\n"
    assert rewrite(src) == src


def test_unknown_module_and_names_are_untouched():
    src = (
        "from app import catalog, verify\n"
        "from app.llm.client import Usage\n"
        "from app.strategies import REGISTRY\n"
    )
    assert rewrite(src) == src


def test_from_app_import_config_alone_is_unchanged():
    src = "from app import config\n"
    assert rewrite(src) == src


# -- rewrite_source: strings -----------------------------------------------------------------------------------------


def test_exact_module_string_constants_are_rewritten_and_other_strings_are_not():
    src = 'MODULE = "app.limits"\nTOP = "app.config"\nNOTE = "see app.limits here"\nT = _topic_task("app.trigfam")\n'
    expected = 'MODULE = "app.calc1.limits"\nTOP = "app.config"\nNOTE = "see app.limits here"\nT = _topic_task("app.calc2.trigfam")\n'
    assert rewrite(src) == expected


# -- rewrite_source: comments and docstrings -------------------------------------------------------------------------


def test_docstring_path_and_dotted_references_are_rewritten():
    src = '"""Reference app/limits.py and app/derivatives.verify.\n\nRun python -m app.keys to start.\n"""\n'
    expected = (
        '"""Reference app/calc1/limits.py and app/calc1/derivatives.verify.\n\n'
        'Run python -m app.api.keys to start.\n"""\n'
    )
    assert rewrite(src) == expected


def test_comment_path_reference_is_rewritten():
    src = "# see app/difficulty.py for the grader\nX = 1\n"
    assert rewrite(src) == "# see app/shared/difficulty.py for the grader\nX = 1\n"


# -- rewrite_source: idempotence, determinism, parseability ----------------------------------------------------------

SAMPLE = (
    '"""Module doc: app/limits.py, app/derivatives.verify, python -m app.keys."""\n'
    "# comment about app/difficulty.py\n"
    "from app import catalog, difficulty, limits as lim, config\n"
    "from app.integral_core import (  # noqa\n"
    "    L,\n"
    ")  # noqa\n"
    "import app.trigfam as tf\n"
    'MODULE = "app.limits"\n'
    "def f():\n"
    "    from app import offline, keys\n"
    "    return lim\n"
)


def test_rewrite_is_idempotent():
    once = rewrite(SAMPLE)
    assert rewrite(once) == once


def test_rewrite_is_deterministic_and_does_not_mutate_mapping():
    mapping = copy.deepcopy(SMALL)
    assert rewrite_source(SAMPLE, mapping) == rewrite_source(SAMPLE, mapping)
    assert mapping == SMALL


def test_rewritten_snippets_parse():
    ast.parse(rewrite(SAMPLE))


# -- rewrite_source: CRLF line endings -------------------------------------------------------------------------------

CRLF_SAMPLE = (
    '"""Docstring app/limits.py,\r\n'
    "python -m app.keys.\r\n"
    '"""\r\n'
    "# comment about app/difficulty.py\r\n"
    "from app import catalog, difficulty, limits as lim, config  # lazy\r\n"
    "from app.integral_core import (  # noqa\r\n"
    "    L,\r\n"
    ")  # noqa\r\n"
    "import app.trigfam as tf\r\n"
    'MODULE = "app.limits"\r\n'
    "def f():\r\n"
    "    from app import offline, keys\r\n"
    "    return lim\r\n"
)


def test_crlf_source_rewrites_to_the_lf_result_with_crlf_endings():
    lf_source = CRLF_SAMPLE.replace("\r\n", "\n")
    assert rewrite(CRLF_SAMPLE) == rewrite(lf_source).replace("\n", "\r\n")


def test_crlf_rewrite_has_no_bare_lf_and_changes_text():
    out = rewrite(CRLF_SAMPLE)
    assert out.count("\n") == out.count("\r\n")
    assert out != CRLF_SAMPLE


def test_crlf_source_without_moved_references_is_unchanged():
    src = "from app import config\r\nX = 1\r\n"
    assert rewrite(src) == src


# -- real tree (read only) -------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_pairs() -> dict[str, tuple[str, str]]:
    if ALREADY_MIGRATED:
        pytest.skip("app/ was already reorganized; the real-tree rewrite checks describe the old flat layout")
    pairs = {}
    for stem in MAPPING:
        old = (APP_DIR / f"{stem}.py").read_text(encoding="utf-8")
        pairs[stem] = (old, rewrite_source(old, MAPPING))
    return pairs


def test_every_real_module_rewrites_to_parseable_source(real_pairs):
    for stem, (_, new) in real_pairs.items():
        ast.parse(new)


def test_real_rewrite_is_idempotent(real_pairs):
    for stem, (_, new) in real_pairs.items():
        assert rewrite_source(new, MAPPING) == new, stem


def _from_app_import_lines(source: str) -> set[int]:
    """1-based line numbers covered by `from app import ...` statements (these are regenerated)."""
    covered: set[int] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module == "app":
            covered.update(range(node.lineno, node.end_lineno + 1))
    return covered


def test_only_lines_that_reference_app_change(real_pairs):
    for stem, (old, new) in real_pairs.items():
        old_lines, new_lines = old.splitlines(), new.splitlines()
        regenerated = _from_app_import_lines(old)
        matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            for number in range(i1 + 1, i2 + 1):
                assert number in regenerated or "app" in old_lines[number - 1], (stem, old_lines[number - 1])
            for line in new_lines[j1:j2]:
                assert "app" in line, (stem, line)


def test_no_moved_name_remains_in_a_from_app_import(real_pairs):
    moved = {stem for stem, sub in MAPPING.items() if sub}
    for stem, (_, new) in real_pairs.items():
        for node in ast.walk(ast.parse(new)):
            if isinstance(node, ast.ImportFrom) and node.module == "app":
                leftover = {alias.name for alias in node.names} & moved
                assert not leftover, (stem, leftover)


def test_no_old_module_path_remains(real_pairs):
    for stem, (_, new) in real_pairs.items():
        for moved_stem, sub in MAPPING.items():
            if not sub:
                continue
            name = re.escape(moved_stem)
            patterns = (
                rf"from app\.{name}\s+import",
                rf"\bimport app\.{name}(?!\w)",
                rf"[\"']app\.{name}[\"']",
            )
            for pattern in patterns:
                assert not re.search(pattern, new), (stem, pattern)


def test_offline_gets_calc1_and_calc2_import_lines(real_pairs):
    _, new = real_pairs["offline"]
    assert "from app.calc1 import" in new
    assert "from app.calc2 import" in new


def test_pipeline_keeps_nonexistent_catalog_import(real_pairs):
    old, new = real_pairs["pipeline"]
    assert "from app import catalog" in old
    assert "from app import catalog" in new


# -- dry run and tree checks -----------------------------------------------------------------------------------------


def _tree_snapshot(root: Path) -> list[tuple[str, int]]:
    return sorted((str(p.relative_to(root)), p.stat().st_size) for p in root.rglob("*") if p.is_file())


@OLD_LAYOUT
def test_dry_run_prints_plan_and_writes_nothing(capsys):
    before = _tree_snapshot(APP_DIR)
    code = main([], app_dir=APP_DIR)
    out = capsys.readouterr().out
    after = _tree_snapshot(APP_DIR)
    assert code == 0
    assert before == after
    lines = out.splitlines()
    assert sum(1 for line in lines if line.startswith("move ")) == 74
    assert sum(1 for line in lines if line.startswith("create ")) == 4
    assert "warning: app/main.py" in out
    assert "warning: app/wordproblem.py" in out


def _fake_app(tmp_path: Path, extra: tuple[str, ...] = ()) -> Path:
    app = tmp_path / "app"
    app.mkdir()
    (app / "__init__.py").write_text("", encoding="utf-8")
    for stem in MAPPING:
        (app / f"{stem}.py").write_text("", encoding="utf-8")
    for name in extra:
        (app / name).write_text("", encoding="utf-8")
    return app


def test_missing_app_dir_exits_2(tmp_path, capsys):
    assert main([], app_dir=tmp_path / "nope") == 2
    assert "not found" in capsys.readouterr().err


def test_unmapped_module_exits_2(tmp_path, capsys):
    app = _fake_app(tmp_path, extra=("stray.py",))
    assert main([], app_dir=app) == 2
    assert "stray.py" in capsys.readouterr().err


def test_mapped_module_without_file_exits_2(tmp_path, capsys):
    app = _fake_app(tmp_path)
    (app / "limits.py").unlink()
    assert main([], app_dir=app) == 2
    assert "limits.py" in capsys.readouterr().err
