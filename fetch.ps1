param(
    [Parameter(Mandatory=$true)][string]$Token,
    [string]$RepoName = 'pal-ios',
    [string]$Owner = '',
    [int]$TimeoutMinutes = 40
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$headers = @{
    Authorization = "Bearer $Token"
    Accept        = 'application/vnd.github+json'
    'User-Agent'  = 'dsh-pal-builder'
}

if (-not $Owner) { $Owner = (Invoke-RestMethod -Uri 'https://api.github.com/user' -Headers $headers).login }

Write-Host "仓库: $Owner/$RepoName"

# 触发（如果还没跑）
try {
    Invoke-RestMethod -Uri "https://api.github.com/repos/$Owner/$RepoName/actions/workflows/build.yml/dispatches" `
        -Method Post -Headers $headers -Body '{"ref":"main"}' -ContentType 'application/json' | Out-Null
    Write-Host "已触发构建"
} catch { Write-Host "触发失败（可能已经在跑）: $($_.Exception.Message)" }

$deadline = (Get-Date).AddMinutes($TimeoutMinutes)
$run = $null
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 15
    $runs = Invoke-RestMethod -Uri "https://api.github.com/repos/$Owner/$RepoName/actions/runs?per_page=1" -Headers $headers
    if ($runs.workflow_runs.Count -eq 0) { Write-Host "等待 workflow 出现..."; continue }
    $run = $runs.workflow_runs[0]
    Write-Host ("[{0}] {1} | {2}" -f (Get-Date -Format 'HH:mm:ss'), $run.status, $run.conclusion)
    if ($run.status -eq 'completed') { break }
}

if (-not $run -or $run.status -ne 'completed') { throw "超时未完成" }

Write-Host "结果: $($run.conclusion)  $($run.html_url)"
if ($run.conclusion -ne 'success') {
    Write-Host "构建失败，去页面看日志: $($run.html_url)"
    exit 1
}

# 下载产物
$arts = Invoke-RestMethod -Uri "https://api.github.com/repos/$Owner/$RepoName/actions/runs/$($run.id)/artifacts" -Headers $headers
$art = $arts.artifacts | Where-Object { $_.name -eq 'SDLPAL-ipa' } | Select-Object -First 1
if (-not $art) { throw "没找到 SDLPAL-ipa 产物" }

$outZip = Join-Path (Split-Path -Parent $PSScriptRoot) 'SDLPAL-ipa.zip'
$dl = Invoke-WebRequest -Uri $art.archive_download_url -Headers $headers -OutFile $outZip -TimeoutSec 600
Write-Host "已下载: $outZip ({0:N1} MB)" -f ((Get-Item $outZip).Length / 1MB)

Expand-Archive $outZip -DestinationPath (Split-Path -Parent $PSScriptRoot) -Force
Get-ChildItem (Split-Path -Parent $PSScriptRoot) -Filter '*.ipa' | Select-Object Name, @{n='MB';e={[math]::Round($_.Length/1MB,1)}}
