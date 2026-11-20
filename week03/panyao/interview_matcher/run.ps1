# 统一入口：走 uv 生成的控制台脚本（依赖由 pyproject.toml / uv.lock 管理）
# 用法： .\run.ps1 01      /  .\run.ps1 02
param([Parameter(Mandatory = $true)][ValidateSet("01", "02", "03")][string]$Task)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$entry = @{
    "01" = "w1-hello"
    "02" = "w1-tool-call"
    "03" = "w2-real"
}[$Task]

$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [Text.Encoding]::UTF8

if (Get-Command uv -ErrorAction SilentlyContinue) {
    # uv run 会在需要时先同步环境，再执行控制台脚本
    uv run $entry $args
} else {
    $module = @{
        "01" = "interview_matcher.week1.hello"
        "02" = "interview_matcher.week1.tool_call"
        "03" = "interview_matcher.week2.real_resume_demo"
    }[$Task]
    $py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $py)) {
        Write-Host "既没有 uv，也找不到 $py"
        exit 1
    }
    & $py -m $module @args
}
