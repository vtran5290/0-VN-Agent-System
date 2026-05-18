# Build third-AI feedback package for ChatGPT final review.
# Usage: .\scripts\trading\build_third_ai_review_return_package.ps1
param([string]$Tag = "")
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $RepoRoot
$py = Join-Path $RepoRoot ".venv\Scripts\python.exe"
& $py (Join-Path $RepoRoot "scripts\trading\build_third_ai_feedback_for_chatgpt_package.py")
