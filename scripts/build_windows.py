"""Build the Windows release package for PDF Chapter Splitter."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


APP_NAME = "PDF-Chapter-Splitter"
VERSION = "1.0.0"
RELEASE_ARCHIVE_NAME = f"{APP_NAME}-v{VERSION}-windows-x64.zip"


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def python_executable(root: Path) -> Path:
    venv_python = root / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return venv_python
    return Path(sys.executable)


def build_pyinstaller_command(root: Path) -> list[str]:
    return [
        str(root / ".venv" / "Scripts" / "python.exe"),
        "-m",
        "PyInstaller",
        "--noconfirm",
        str(root / f"{APP_NAME}.spec"),
    ]


def clean_build_directories(root: Path) -> None:
    resolved_root = root.resolve()
    for name in ("build", "dist"):
        target = (resolved_root / name).resolve()
        if target.parent != resolved_root:
            raise RuntimeError(f"Refusing to remove path outside project root: {target}")
        if target.exists():
            shutil.rmtree(target)


def run_command(command: list[str], *, root: Path) -> None:
    print(f"> {' '.join(command)}")
    subprocess.run(command, cwd=root, check=True)


def write_release_readme(app_dir: Path) -> None:
    (app_dir / "README.txt").write_text(
        "\n".join(
            [
                "PDF Chapter Splitter v1.0.0",
                "",
                "双击 PDF-Chapter-Splitter.exe 启动程序。",
                "",
                "使用步骤：",
                "1. 选择 PDF。",
                "2. 检查并确认程序发现的章节。",
                "3. 选择输出目录并开始拆分。",
                "",
                "限制：当前不支持 OCR、AI 识别或 PDF 页面预览；扫描版 PDF 可能需要手动添加章节。",
                "",
            ]
        ),
        encoding="utf-8",
    )


def create_release_archive(root: Path) -> Path:
    app_dir = root / "dist" / APP_NAME
    exe_path = app_dir / f"{APP_NAME}.exe"
    if not exe_path.exists():
        raise FileNotFoundError(f"Expected EXE was not generated: {exe_path}")

    write_release_readme(app_dir)
    release_dir = root / "release"
    release_dir.mkdir(exist_ok=True)
    archive_path = release_dir / RELEASE_ARCHIVE_NAME
    if archive_path.exists():
        archive_path.unlink()

    archive_base = archive_path.with_suffix("")
    shutil.make_archive(str(archive_base), "zip", root / "dist", APP_NAME)
    return archive_path


def main() -> int:
    root = project_root()
    python = python_executable(root)

    clean_build_directories(root)
    run_command([str(python), "-m", "pytest", "-q"], root=root)
    run_command([str(python), "-m", "compileall", "-q", "src", "tests"], root=root)
    run_command(build_pyinstaller_command(root), root=root)
    archive_path = create_release_archive(root)

    print(f"Release package: {archive_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
