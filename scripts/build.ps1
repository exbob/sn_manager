#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

uv run pyinstaller `
  --noconfirm `
  --windowed `
  --name sn-manager `
  --paths src `
  --collect-submodules PySide6 `
  src/sn_manager/__main__.py

Write-Host "Built: dist\sn-manager\sn-manager.exe"
