from pathlib import Path

import sn_manager.app.paths as paths_mod
from sn_manager.app.paths import (
    app_dir,
    default_db_path,
    resolve_app_icon_path,
    resolve_user_manual_path,
)


def test_app_dir_cwd_when_not_frozen(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(paths_mod.sys, "frozen", False, raising=False)
    monkeypatch.chdir(tmp_path)
    assert app_dir() == tmp_path.resolve()
    assert default_db_path() == tmp_path.resolve() / "sn_manager.db"


def test_app_dir_executable_parent_when_frozen(tmp_path: Path, monkeypatch) -> None:
    exe = tmp_path / "dist" / "sn-manager"
    exe.parent.mkdir(parents=True)
    exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(paths_mod.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths_mod.sys, "executable", str(exe))
    assert app_dir() == exe.resolve().parent
    assert default_db_path() == exe.resolve().parent / "sn_manager.db"


def test_resolve_user_manual_frozen_beside_exe(tmp_path: Path, monkeypatch) -> None:
    exe = tmp_path / "dist" / "sn-manager.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("", encoding="utf-8")
    manual = exe.parent / "user-manual.md"
    manual.write_text("# help\n", encoding="utf-8")
    monkeypatch.setattr(paths_mod.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths_mod.sys, "executable", str(exe))
    assert resolve_user_manual_path() == manual.resolve()


def test_resolve_user_manual_frozen_missing(tmp_path: Path, monkeypatch) -> None:
    exe = tmp_path / "dist" / "sn-manager.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(paths_mod.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths_mod.sys, "executable", str(exe))
    assert resolve_user_manual_path() is None


def test_resolve_user_manual_dev_docs(tmp_path: Path, monkeypatch) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    manual = docs / "user-manual.md"
    manual.write_text("# help\n", encoding="utf-8")
    pkg = tmp_path / "src" / "sn_manager" / "app"
    pkg.mkdir(parents=True)
    monkeypatch.setattr(paths_mod.sys, "frozen", False, raising=False)
    monkeypatch.setattr(paths_mod, "__file__", str(pkg / "paths.py"))
    monkeypatch.chdir(tmp_path)
    assert resolve_user_manual_path() == manual.resolve()


def test_resolve_app_icon_frozen_meipass(tmp_path: Path, monkeypatch) -> None:
    icon_dir = tmp_path / "assets" / "icons"
    icon_dir.mkdir(parents=True)
    icon = icon_dir / "sn-manager.png"
    icon.write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr(paths_mod.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths_mod.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert resolve_app_icon_path() == icon.resolve()


def test_resolve_app_icon_frozen_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(paths_mod.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths_mod.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert resolve_app_icon_path() is None


def test_resolve_app_icon_dev_from_cwd(tmp_path: Path, monkeypatch) -> None:
    icon_dir = tmp_path / "assets" / "icons"
    icon_dir.mkdir(parents=True)
    icon = icon_dir / "sn-manager.png"
    icon.write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr(paths_mod.sys, "frozen", False, raising=False)
    if hasattr(paths_mod.sys, "_MEIPASS"):
        monkeypatch.delattr(paths_mod.sys, "_MEIPASS", raising=False)
    monkeypatch.chdir(tmp_path)
    assert resolve_app_icon_path() == icon.resolve()


def test_resolve_app_icon_dev_walk_from_module(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "repo"
    icon_dir = root / "assets" / "icons"
    icon_dir.mkdir(parents=True)
    icon = icon_dir / "sn-manager.png"
    icon.write_bytes(b"\x89PNG\r\n\x1a\n")
    pkg = root / "src" / "sn_manager" / "app"
    pkg.mkdir(parents=True)
    monkeypatch.setattr(paths_mod.sys, "frozen", False, raising=False)
    if hasattr(paths_mod.sys, "_MEIPASS"):
        monkeypatch.delattr(paths_mod.sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(paths_mod, "__file__", str(pkg / "paths.py"))
    monkeypatch.chdir(tmp_path)  # cwd 无图标，须向上找到 repo
    assert resolve_app_icon_path() == icon.resolve()


def test_resolve_app_icon_dev_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(paths_mod.sys, "frozen", False, raising=False)
    if hasattr(paths_mod.sys, "_MEIPASS"):
        monkeypatch.delattr(paths_mod.sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(paths_mod, "__file__", str(tmp_path / "paths.py"))
    monkeypatch.chdir(tmp_path)
    assert resolve_app_icon_path() is None
