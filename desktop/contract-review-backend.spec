from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

project_root = Path(SPEC).resolve().parents[1]
source_root = project_root / "src"

package_datas, package_binaries, package_hidden = collect_all("contract_review")
hiddenimports = package_hidden
for package in (
    "alembic",
    "langchain",
    "langchain_anthropic",
    "langchain_openai",
    "langgraph",
    "sqlalchemy.dialects.sqlite",
    "uvicorn",
):
    hiddenimports += collect_submodules(package)

datas = package_datas + [
    (str(source_root / "contract_review" / "web"), "contract_review/web"),
    (str(source_root / "contract_review" / "knowledge"), "contract_review/knowledge"),
    (str(project_root / "migrations"), "migrations"),
    (str(project_root / "alembic.ini"), "."),
]

a = Analysis(
    [str(project_root / "desktop" / "backend_entry.py")],
    pathex=[str(source_root)],
    binaries=package_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="contract-review-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="contract-review-backend",
)
