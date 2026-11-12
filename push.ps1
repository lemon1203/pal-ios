param(
    [Parameter(Mandatory=$true)][string]$Token,
    [string]$RepoName = 'pal-ios',
    [string]$Owner = '',
    [switch]$Private
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$GitExe = 'C:\Users\Administrator\AppData\Local\GitHubDesktop\app-3.6.11\resources\app\git\cmd\git.exe'
if (-not (Test-Path $GitExe)) {
    $GitExe = (Get-ChildItem "$env:LOCALAPPDATA\GitHubDesktop" -Recurse -Filter git.exe -ErrorAction SilentlyContinue |
               Where-Object { $_.FullName -match 'cmd\\git\.exe$' } | Select-Object -First 1).FullName
}
if (-not $GitExe) { throw "找不到 git.exe" }
Write-Host "git: $GitExe"

$RepoDir = Split-Path -Parent $PSScriptRoot
Write-Host "仓库目录: $RepoDir"

$headers = @{
    Authorization = "Bearer $Token"
    Accept        = 'application/vnd.github+json'
    'User-Agent'  = 'dsh-pal-builder'
}

# 1. 取账号
$me = Invoke-RestMethod -Uri 'https://api.github.com/user' -Headers $headers
if (-not $Owner) { $Owner = $me.login }
Write-Host "账号: $($me.login)"

# 2. 建仓库（已存在则复用）
$body = @{ name = $RepoName; private = [bool]$Private; auto_init = $false } | ConvertTo-Json
try {
    $repo = Invoke-RestMethod -Uri 'https://api.github.com/user/repos' -Method Post -Headers $headers -Body $body -ContentType 'application/json'
    Write-Host "已创建仓库: $($repo.html_url)"
} catch {
    if ($_.Exception.Message -match '422|already exists') {
        Write-Host "仓库已存在，复用"
        $repo = Invoke-RestMethod -Uri "https://api.github.com/repos/$Owner/$RepoName" -Headers $headers
    } else { throw }
}

# 3. 本地 git 初始化并推送
Push-Location $RepoDir
try {
    if (-not (Test-Path '.git')) {
        & $GitExe init -q
        & $GitExe branch -M main
    }
    & $GitExe config user.name  $me.login
    & $GitExe config user.email "$($me.login)@users.noreply.github.com"
    & $GitExe add -A
    $status = & $GitExe status --porcelain
    if ($status) { & $GitExe commit -q -m "SDLPAL iOS build workflow" } else { Write-Host "无新改动需要提交" }

    $remoteUrl = "https://$Owner`:$Token@github.com/$Owner/$RepoName.git"
    $existing = & $GitExe remote 2>$null
    if ($existing -match 'origin') { & $GitExe remote set-url origin $remoteUrl }
    else { & $GitExe remote add origin $remoteUrl }

    & $GitExe push -u origin main --force
    Write-Host "已推送到 https://github.com/$Owner/$RepoName"
} finally {
    # 清掉 URL 里的 token
    & $GitExe remote set-url origin "https://github.com/$Owner/$RepoName.git" 2>$null
    Pop-Location
}

Write-Host ""
Write-Host "Actions 页面: https://github.com/$Owner/$RepoName/actions"
Write-Host "等构建完成后重新运行本脚本加 -Download 参数（见下方说明）即可自动取 ipa。"
Write-Host "仓库地址: https://github.com/$Owner/$RepoName"
