from __future__ import annotations

from pathlib import Path

import scripts.build_windows as build_windows


def test_release_archive_name_uses_v1_version():
    assert build_windows.VERSION == "1.0.0"
    assert build_windows.APP_NAME == "PDF-Chapter-Splitter"
    assert build_windows.RELEASE_ARCHIVE_NAME == "PDF-Chapter-Splitter-v1.0.0-windows-x64.zip"


def test_pyinstaller_command_uses_project_spec_file(tmp_path: Path):
    command = build_windows.build_pyinstaller_command(tmp_path)

    assert command == [
        str(tmp_path / ".venv" / "Scripts" / "python.exe"),
        "-m",
        "PyInstaller",
        "--noconfirm",
        str(tmp_path / "PDF-Chapter-Splitter.spec"),
    ]


def test_clean_build_directories_only_removes_project_build_outputs(tmp_path: Path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    build_dir = project_root / "build"
    dist_dir = project_root / "dist"
    source_dir = project_root / "src"
    for path in (build_dir, dist_dir, source_dir):
        path.mkdir()
        (path / "marker.txt").write_text("keep or remove", encoding="utf-8")

    build_windows.clean_build_directories(project_root)

    assert not build_dir.exists()
    assert not dist_dir.exists()
    assert source_dir.exists()
    assert (source_dir / "marker.txt").exists()
