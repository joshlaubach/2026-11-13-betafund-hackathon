"""End-to-end tests for the --apply path of scripts/reorg_app.py.

Every apply test runs against a throwaway git repository under tmp_path with a tiny
mapping. The real app/ tree is only read: a module-scoped fixture compares its file
paths and sizes before and after this module runs.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = REPO_ROOT / "app"
sys.path.insert(0, str(REPO_ROOT))

from scripts import reorg_app  # noqa: E402
from scripts.reorg_app import main  # noqa: E402

TINY = {
    "config": "",
    "worker": "",
    "clean_answer": "shared",
    "limits": "calc1",
    "limits_samples": "calc1",
    "main": "api",
}

PACKAGE_FILES: dict[str, bytes] = {
    "app/__init__.py": b"",
    "app/config.py": b"SETTING = 1\n",
    "app/worker.py": (
        b"import importlib\n\n\n"
        b'def load_limits():\n    return importlib.import_module("app.limits")\n\n\n'
        b"def load_clean():\n    from app import clean_answer\n    return clean_answer\n"
    ),
    "app/clean_answer.py": (
        b'"""Normalize app/clean_answer text."""\n'
        b"def canon(text):\n    return text.strip()\n"
    ),
    "app/limits.py": (
        b'"""Limits module; see app/limits_samples.py."""\n'
        b"from app.clean_answer import canon\n"
        b"from app import config, limits_samples\n\n\n"
        b"def run(text):\n    return canon(text) + str(config.SETTING) + str(limits_samples.N)\n"
    ),
    "app/limits_samples.py": b"N = 3\n",
    "app/main.py": (
        b"from app import config, clean_answer\r\n\r\n\r\n"
        b"def main():\r\n    return config.SETTING, clean_answer.canon(' x ')\r\n"
    ),
}


def _tree_snapshot(root: Path) -> list[tuple[str, int]]:
    return sorted((str(p.relative_to(root)), p.stat().st_size) for p in root.rglob("*") if p.is_file())


@pytest.fixture(scope="module", autouse=True)
def real_app_untouched():
    before = _tree_snapshot(APP_DIR)
    yield
    assert _tree_snapshot(APP_DIR) == before


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout


def _make_repo(root: Path, files: dict[str, bytes]) -> Path:
    """Create a git repo at root holding files (paths relative to root), commit them, return root/app."""
    root.mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "Test User")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "core.autocrlf", "false")
    _git(root, "config", "commit.gpgsign", "false")
    for rel, data in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "fixture")
    return root / "app"


def _status(repo: Path) -> str:
    return _git(repo, "status", "--porcelain")


def _app_state(app: Path) -> tuple[list[tuple[str, int]], list[str]]:
    """Files under app/ (paths and sizes) plus the directories that exist under it."""
    dirs = sorted(str(p.relative_to(app)) for p in app.rglob("*") if p.is_dir() and p.name != "__pycache__")
    return _tree_snapshot(app), dirs


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _make_repo(tmp_path / "repo", PACKAGE_FILES)
    return tmp_path / "repo"


def test_apply_migrates_a_tiny_package_end_to_end(repo, capsys):
    app = repo / "app"
    code = main(["--apply"], app_dir=app, mapping=TINY)
    assert code == 0, capsys.readouterr().err

    for new in ("shared/clean_answer.py", "calc1/limits.py", "calc1/limits_samples.py", "api/main.py"):
        assert (app / new).is_file(), new
    for old in ("clean_answer.py", "limits.py", "limits_samples.py", "main.py"):
        assert not (app / old).exists(), old
    assert (app / "config.py").is_file() and (app / "worker.py").is_file()

    for sub in ("shared", "calc1", "api"):
        assert (app / sub / "__init__.py").read_bytes() == b""
    assert len(list(app.glob("*/__init__.py"))) == 3


def test_apply_records_moves_as_renames(repo):
    main(["--apply"], app_dir=repo / "app", mapping=TINY)
    renames = [line for line in _status(repo).splitlines() if line.startswith("R")]
    assert len(renames) == 4, renames


def test_every_migrated_module_compiles(repo):
    main(["--apply"], app_dir=repo / "app", mapping=TINY)
    for path in (repo / "app").rglob("*.py"):
        compile(path.read_bytes(), str(path), "exec")


def test_migrated_package_imports_in_a_clean_interpreter(repo):
    main(["--apply"], app_dir=repo / "app", mapping=TINY)
    code = (
        "import sys; sys.path.insert(0, " + repr(str(repo)) + "); "
        "import app.worker, app.calc1.limits, app.api.main"
    )
    result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_crlf_file_keeps_crlf_endings_and_splits_its_grouped_import(repo):
    main(["--apply"], app_dir=repo / "app", mapping=TINY)
    data = (repo / "app" / "api" / "main.py").read_bytes()
    assert data.count(b"\n") == data.count(b"\r\n")
    assert b"from app import config\r\nfrom app.shared import clean_answer\r\n" in data


def test_string_module_path_is_rewritten(repo):
    main(["--apply"], app_dir=repo / "app", mapping=TINY)
    text = (repo / "app" / "worker.py").read_text(encoding="utf-8")
    assert '"app.calc1.limits"' in text
    assert '"app.limits"' not in text
    assert "from app.shared import clean_answer" in text


def test_grouped_import_is_split_and_module_path_rewritten(repo):
    main(["--apply"], app_dir=repo / "app", mapping=TINY)
    text = (repo / "app" / "calc1" / "limits.py").read_text(encoding="utf-8")
    assert "from app import config\nfrom app.calc1 import limits_samples\n" in text
    assert "from app.shared.clean_answer import canon\n" in text
    assert "see app/calc1/limits_samples.py" in text


def test_unchanged_module_is_byte_identical_after_apply(repo):
    main(["--apply"], app_dir=repo / "app", mapping=TINY)
    assert (repo / "app" / "calc1" / "limits_samples.py").read_bytes() == PACKAGE_FILES["app/limits_samples.py"]
    assert (repo / "app" / "config.py").read_bytes() == PACKAGE_FILES["app/config.py"]


def test_rerunning_apply_on_migrated_tree_exits_nonzero_and_changes_nothing(repo, capsys):
    app = repo / "app"
    assert main(["--apply"], app_dir=app, mapping=TINY) == 0
    before_state = _app_state(app)
    before_status = _status(repo)
    capsys.readouterr()

    code = main(["--apply"], app_dir=app, mapping=TINY)

    assert code != 0
    assert capsys.readouterr().err
    assert _app_state(app) == before_state
    assert _status(repo) == before_status


def test_dirty_app_folder_makes_apply_exit_2_and_change_nothing(tmp_path, capsys):
    app = _make_repo(tmp_path / "dirty", PACKAGE_FILES)
    with (app / "limits.py").open("ab") as handle:
        handle.write(b"# local edit\n")
    before_state = _app_state(app)
    before_status = _status(tmp_path / "dirty")

    code = main(["--apply"], app_dir=app, mapping=TINY)

    assert code == 2
    err = capsys.readouterr().err
    assert "uncommitted changes" in err
    assert "limits.py" in err
    assert _app_state(app) == before_state
    assert _status(tmp_path / "dirty") == before_status
    assert not (app / "shared").exists()


def test_apply_refuses_with_exit_2_when_git_is_missing(repo, capsys, monkeypatch):
    monkeypatch.setattr(reorg_app.shutil, "which", lambda name: None)
    before_state = _app_state(repo / "app")

    code = main(["--apply"], app_dir=repo / "app", mapping=TINY)

    assert code == 2
    assert "git is not available" in capsys.readouterr().err
    assert _app_state(repo / "app") == before_state


def test_failing_step_exits_1_names_the_file_and_gives_restore_hint(repo, capsys, monkeypatch):
    def failing_git_mv(repo_root, old, new):
        if old == "app/limits.py":
            raise RuntimeError("boom")

    monkeypatch.setattr(reorg_app, "_git_mv", failing_git_mv)

    code = main(["--apply"], app_dir=repo / "app", mapping=TINY)

    err = capsys.readouterr().err
    assert code == 1
    assert "git mv failed for app/limits.py -> app/calc1/limits.py: boom" in err
    assert "git restore --staged --worktree app" in err
    assert "app/calc1" in err
    assert (repo / "app" / "shared" / "__init__.py").is_file()
