# MIT Panel - Windows installer (runs the panel inside WSL2 + Ubuntu)
#
# Double-click install-windows.bat, or in an elevated PowerShell:
#   powershell -ExecutionPolicy Bypass -File install-windows.ps1
# or straight from GitHub (PowerShell as Administrator):
#   irm https://raw.githubusercontent.com/tauviec/MIT-Panel/main/install-windows.ps1 | iex
#
# The panel is a Linux panel (systemd, PHP-FPM sockets, compiled Apache/Nginx),
# so on Windows it lives in WSL2; the Windows browser reaches it via localhost.

param(
    [string]$Distro = "Ubuntu",
    [string]$RepoRaw = "https://raw.githubusercontent.com/tauviec/MIT-Panel/main"
)

$ErrorActionPreference = "Stop"

function Info($msg) { Write-Host "[*] $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "[OK] $msg" -ForegroundColor Green }
function Fail($msg) { Write-Host "[ERROR] $msg" -ForegroundColor Red; Read-Host "Tekan Enter untuk keluar"; exit 1 }

# keep the window open on any unexpected error instead of closing silently
trap { Fail "$($_.Exception.Message)`n$($_.InvocationInfo.PositionMessage)" }

# --- elevate ---------------------------------------------------------------
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    if (-not $PSCommandPath) {
        # started with "irm ... | iex": there is no file to relaunch elevated
        Fail "Buka PowerShell dengan 'Run as Administrator', lalu jalankan perintah instalasi lagi."
    }
    Info "Meminta hak Administrator..."
    Start-Process powershell -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -File `"$PSCommandPath`" -Distro $Distro"
    exit 0
}

$build = [Environment]::OSVersion.Version.Build
if ($build -lt 19041) {
    Fail "WSL2 butuh Windows 10 versi 2004 (build 19041) atau lebih baru. Build ini: $build"
}

# --- WSL -------------------------------------------------------------------
# "wsl --status" also fails when the features are on but the WSL2 kernel is
# missing, so check the Windows features themselves instead.
function FeatureOn($name) {
    try { (Get-WindowsOptionalFeature -Online -FeatureName $name).State -eq "Enabled" } catch { $false }
}
$needRestart = $false
foreach ($f in "Microsoft-Windows-Subsystem-Linux", "VirtualMachinePlatform") {
    if (-not (FeatureOn $f)) {
        Info "Mengaktifkan fitur Windows $f..."
        dism.exe /online /enable-feature /featurename:$f /all /norestart | Out-Null
        $needRestart = $true
    }
}
if ($needRestart) {
    Write-Host ""
    Write-Host "Fitur WSL sudah diaktifkan. RESTART Windows, lalu jalankan install-windows.bat sekali lagi." -ForegroundColor Yellow
    Read-Host "Tekan Enter untuk keluar"
    exit 0
}

# features are on: make sure the WSL2 kernel / current WSL is installed
wsl.exe --status *> $null
if ($LASTEXITCODE -ne 0) {
    Info "Memasang/memperbarui kernel WSL2 (wsl --update)..."
    wsl.exe --update
    if ($LASTEXITCODE -ne 0) { wsl.exe --update --web-download }
    wsl.exe --shutdown *> $null
    wsl.exe --status *> $null
    if ($LASTEXITCODE -ne 0) {
        Fail "Kernel WSL2 belum terpasang. Unduh dan pasang manual dari https://aka.ms/wsl2kernel, lalu jalankan installer ini lagi."
    }
}
wsl.exe --set-default-version 2 *> $null

# wsl -l -q prints UTF-16 with NULs; strip them before comparing
$distros = (wsl.exe -l -q) -replace "`0", "" | Where-Object { $_.Trim() -ne "" } | ForEach-Object { $_.Trim() }
if ($distros -notcontains $Distro) {
    Info "Memasang distro $Distro..."
    wsl.exe --install -d $Distro --no-launch
    # register the distro with root as default user, no interactive prompt
    $launcher = ($Distro.ToLower() -replace "[^a-z0-9]", "") + ".exe"
    if (Get-Command $launcher -ErrorAction SilentlyContinue) {
        & $launcher install --root
    } else {
        wsl.exe -d $Distro -u root -- true
    }
    $distros = (wsl.exe -l -q) -replace "`0", "" | ForEach-Object { $_.Trim() }
    if ($distros -notcontains $Distro) {
        Fail "Distro $Distro belum terpasang. Buka Microsoft Store, pasang '$Distro', jalankan sekali, lalu ulangi installer ini."
    }
}
Ok "WSL2 + $Distro siap"

# --- systemd inside WSL (the panel and its services use systemctl) ---------
Info "Mengaktifkan systemd di $Distro..."
wsl.exe -d $Distro -u root -- bash -c "grep -q '^systemd=true' /etc/wsl.conf 2>/dev/null || printf '[boot]\nsystemd=true\n' >> /etc/wsl.conf"
wsl.exe --terminate $Distro | Out-Null
Start-Sleep -Seconds 3

# --- install the panel: from this folder, or straight from GitHub -----------
$here = if ($PSCommandPath) { Split-Path -Parent $PSCommandPath } else { "" }
if ($here -and (Test-Path (Join-Path $here "scripts\install.sh"))) {
    # newer WSL drops backslashes from the arguments, so pass C:/... instead
    $wslPath = "$(wsl.exe -d $Distro -u root -- wslpath -a ($here -replace '\\', '/'))".Trim()
    if (-not $wslPath) { Fail "Tidak bisa menerjemahkan path $here ke path WSL." }
    Info "Memasang MIT Panel dari $here (di WSL: $wslPath). Ini bisa 10-30 menit..."
    wsl.exe -d $Distro -u root -- bash -c "sed -i 's/\r$//' '$wslPath/install.sh' '$wslPath/scripts/install.sh' && bash '$wslPath/install.sh'"
} else {
    Info "Mengunduh dan memasang MIT Panel dari $RepoRaw. Ini bisa 10-30 menit..."
    wsl.exe -d $Distro -u root -- bash -c "apt-get update -y >/dev/null; apt-get install -y curl >/dev/null; curl -fsSL $RepoRaw/install.sh | bash"
}
if ($LASTEXITCODE -ne 0) {
    Fail "Instalasi di WSL gagal. Lihat log: wsl -d $Distro -u root -- cat /opt/mit/server/panel/mit-install.log"
}
Ok "MIT Panel terpasang"

# --- keep WSL (and the panel) running after login ---------------------------
# WSL stops the VM when no wsl.exe process is left, so a hidden task holds it open.
Info "Membuat autostart saat login Windows..."
$taskName = "MIT Panel (WSL)"
$action = New-ScheduledTaskAction -Execute "wsl.exe" -Argument "-d $Distro -u root -- bash -c `"/etc/init.d/mit start >/dev/null 2>&1; exec sleep infinity`""
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -Hidden -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Ok "Autostart dibuat (Task Scheduler: $taskName)"

# --- login info + desktop shortcut ------------------------------------------
Start-Sleep -Seconds 5
$info = wsl.exe -d $Distro -u root -- bash -c "mit default 2>/dev/null || /etc/init.d/mit default"
$info = $info -replace "\x1b\[[0-9;]*m", ""
Write-Host ""
$info | ForEach-Object { Write-Host $_ }

$url = ($info | Select-String "Url-Localhost:\s*(\S+)").Matches | Select-Object -First 1 | ForEach-Object { $_.Groups[1].Value }
if ($url) {
    $shortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "MIT Panel.url"
    "[InternetShortcut]`r`nURL=$url`r`n" | Set-Content -Path $shortcut -Encoding ASCII
    Ok "Shortcut desktop dibuat: MIT Panel"
    Start-Process $url
}

Write-Host ""
Write-Host "Perintah panel dari Windows:  wsl -d $Distro -u root -- mit start|stop|restart|default" -ForegroundColor Yellow
Read-Host "Selesai. Tekan Enter untuk keluar"
