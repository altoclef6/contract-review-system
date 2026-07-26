# Windows desktop build

## Supported build host

- Windows 10/11 x64
- Python 3.11, Node.js 20+, pnpm 10+
- Rust stable with `x86_64-pc-windows-msvc`
- Visual Studio 2022 Build Tools with Desktop development with C++ and a Windows 10/11 SDK

Create `.venv`, install `requirements-dev.txt`, then run:

```powershell
pwsh -File scripts/build-windows-desktop.ps1
```

The script runs backend tests, Ruff, Mypy, the frontend production build,
PyInstaller onedir packaging, Tauri release compilation, and NSIS packaging.
It writes:

- `dist/windows/ContractReviewSetup-x64.exe`
- `dist/windows/ContractReviewPortable-x64.zip`

For a non-default Rust target or a large build drive:

```powershell
pwsh -File scripts/build-windows-desktop.ps1 `
  -RustTarget x86_64-pc-windows-gnu `
  -CargoTargetDir D:\ContractReviewCargo
```

Release binaries are not Authenticode-signed unless a signing certificate is
configured by the release operator. Unsigned builds can trigger SmartScreen.
