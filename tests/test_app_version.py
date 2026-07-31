from __future__ import annotations

from pathlib import Path

import sn_manager.app.version as version_mod
from sn_manager.app.version import resolve_app_version


def test_reads_app_version_file_from_cwd(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(version_mod.sys, "frozen", False, raising=False)
    if hasattr(version_mod.sys, "_MEIPASS"):
        monkeypatch.delattr(version_mod.sys, "_MEIPASS", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app_version.txt").write_text("v1.2.3-0-gabcdef0\n", encoding="utf-8")
    monkeypatch.setattr(version_mod, "_git_describe", lambda _cwd: "should-not-use")
    assert resolve_app_version() == "v1.2.3-0-gabcdef0"


def test_frozen_reads_meipass(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(version_mod.sys, "frozen", True, raising=False)
    monkeypatch.setattr(version_mod.sys, "_MEIPASS", str(tmp_path), raising=False)
    (tmp_path / "app_version.txt").write_text("packaged-ver\n", encoding="utf-8")
    monkeypatch.setattr(version_mod, "_git_describe", lambda _cwd: "should-not-use")
    assert resolve_app_version() == "packaged-ver"


def test_falls_back_to_git_describe(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(version_mod.sys, "frozen", False, raising=False)
    if hasattr(version_mod.sys, "_MEIPASS"):
        monkeypatch.delattr(version_mod.sys, "_MEIPASS", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(version_mod, "_walk_app_version_files", lambda: [])
    monkeypatch.setattr(version_mod, "_git_describe", lambda _cwd: "v0.1.0-5-gdeadbeef")
    assert resolve_app_version() == "v0.1.0-5-gdeadbeef"


def test_unknown_when_no_file_and_no_git(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(version_mod.sys, "frozen", False, raising=False)
    if hasattr(version_mod.sys, "_MEIPASS"):
        monkeypatch.delattr(version_mod.sys, "_MEIPASS", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(version_mod, "_walk_app_version_files", lambda: [])
    monkeypatch.setattr(version_mod, "_git_describe", lambda _cwd: None)
    assert resolve_app_version() == "unknown"
