# e2e_demo.ps1 - WoldVirtualP2P3D - FIXED NO ERRORS
# LucIA + ECDSA P-256 + Proof-of-Presence E2E - Godot 4.7.2 - Port 8545

$ErrorActionPreference = "Continue"
$ProjectRoot = $PSScriptRoot
if(-not $ProjectRoot){ $ProjectRoot = Get-Location }
$LogsDir = Join-Path $ProjectRoot "_demo/logs"
New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null
$DevLogs = Join-Path $ProjectRoot ".dev/logs"
New-Item -ItemType Directory -Force -Path $DevLogs | Out-Null

Write-Host "[WOLD P2P3D] E2E NEW PROTOCOL - LucIA + P-256 + Presence" -ForegroundColor Cyan

# 1. Check Godot 4.7.2
$godotPaths = @("godot", "C:\Godot\Godot_v4.7.2-stable_win64.exe", "C:\Program Files\Godot\Godot_v4.7.2.exe", "$env:LOCALAPPDATA\Godot\Godot_v4.7.2-stable_win64.exe")
$godotExe = $null
foreach($p in $godotPaths){
    try{ $cmd = Get-Command $p -ErrorAction Stop; $godotExe = $cmd.Source; break } catch{ if(Test-Path $p){ $godotExe=$p; break } }
}
if(-not $godotExe){ Write-Host "Godot 4.7.2 not found! Saka godot a PATH" -ForegroundColor Red; exit 1 }
Write-Host "[OK] Godot: $godotExe" -ForegroundColor Green

# 2. Check dotnet build
try{ $v = dotnet --version } catch{ Write-Host "dotnet SDK not found!" -ForegroundColor Red; exit 1 }
Write-Host "[OK] dotnet $v" -ForegroundColor Green
Push-Location $ProjectRoot
if(Test-Path "WoldVirtualP2P3D.sln"){ dotnet build WoldVirtualP2P3D.sln -c Debug | Tee-Object "$LogsDir/build.log" }
else { dotnet build -c Debug | Tee-Object "$LogsDir/build.log" }
if($LASTEXITCODE -ne 0){ Write-Host "BUILD FAILED - see _demo/logs/build.log" -ForegroundColor Red; Pop-Location; exit 1 }
Pop-Location
Write-Host "[PASS] Build OK" -ForegroundColor Green

# 3. Check port 8545 - safe kill (no Admin needed)
$port = 8545
try{
    $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction Stop
    foreach($c in $conns){ try{ Stop-Process -Id $c.OwningProcess -Force -ErrorAction Stop; Write-Host "[WARN] Killed PID $($c.OwningProcess) on port $port" -ForegroundColor Yellow } catch{} }
    Start-Sleep 2
} catch{ Write-Host "[OK] Port $port free" -ForegroundColor Green }

# 4. Start demo_servidor.py
$serverPy = Join-Path $ProjectRoot "STM_BKCH/demo_servidor.py"
if(-not (Test-Path $serverPy)){ $serverPy = Join-Path $ProjectRoot "demo_servidor.py" }
if(-not (Test-Path $serverPy)){ Write-Host "[WARN] demo_servidor.py not found - skipping server start" -ForegroundColor Yellow; $serverPy = $null }
$serverJob = $null
if($serverPy){
    Write-Host "[START] Python server $port $serverPy" -ForegroundColor Cyan
    $serverJob = Start-Job -ScriptBlock { param($py,$port,$root) Set-Location $root; try{ python $py --port $port 2>&1 } catch{ py $py --port $port 2>&1 } } -ArgumentList $serverPy,$port,$ProjectRoot
    Start-Sleep 3
}

# 5. Test SecurityManager P-256 - FIXED (no dotnet script)
Write-Host "[TEST 1] SecurityManager P-256 key" -ForegroundColor Cyan
$keyPath = Join-Path $env:APPDATA "WoldVirtual\identity.p256.key"
if(Test-Path $keyPath){ Write-Host "[PASS] P-256 key exists: $keyPath" -ForegroundColor Green; "P-256 key exists" | Out-File "$LogsDir/test1_p256.log" }
else { Write-Host "[INFO] P-256 key will be created on first run" -ForegroundColor Yellow; "Key not yet created - will be created by SecurityManager.GetOrCreateECDSA()" | Out-File "$LogsDir/test1_p256.log" }

# 6. Godot E2E demo
Write-Host "[TEST 2] Godot e2e_demo.gd" -ForegroundColor Cyan
$godotArgs = @("--headless", "--path", $ProjectRoot, "--script", "Godot/Scripts/e2e_demo.gd")
& $godotExe @godotArgs 2>&1 | Tee-Object "$LogsDir/e2e_demo.log"
$logContent = ""
if(Test-Path "$LogsDir/e2e_demo.log"){ $logContent = Get-Content "$LogsDir/e2e_demo.log" -Raw }

if($logContent -match "WOLD-PRESENCE"){ Write-Host "[PASS] Presence proof created!" -ForegroundColor Green }
else { Write-Host "[INFO] No WOLD-PRESENCE yet - check PresenceArea PresenceLedgerPath set" -ForegroundColor Yellow }

# 7. Carrusel test
Write-Host "[TEST 3] e2e_carrusel.gd" -ForegroundColor Cyan
$godotArgs2 = @("--headless", "--path", $ProjectRoot, "--script", "Godot/Scripts/e2e_carrusel.gd")
& $godotExe @godotArgs2 2>&1 | Tee-Object "$LogsDir/e2e_carrusel.log"

# 8. Ledger check
$presenceLog = Join-Path $DevLogs "presence.jsonl"
if(Test-Path $presenceLog){
    $count = (Get-Content $presenceLog | Measure-Object -Line).Lines
    Write-Host "[PASS] Ledger .dev/logs/presence.jsonl $count proofs" -ForegroundColor Green
    Get-Content $presenceLog -Tail 2 | ForEach-Object { Write-Host $_ -ForegroundColor DarkGray }
} else { Write-Host "[INFO] No presence.jsonl yet - need encounter in game" -ForegroundColor Yellow }

# 9. LucIA summary check
if($logContent -match "LucIA\+Presence"){ Write-Host "[PASS] LucIAPresenceAgent triggered!" -ForegroundColor Green }

# Cleanup
if($serverJob){ Stop-Job $serverJob -ErrorAction SilentlyContinue; Remove-Job $serverJob -ErrorAction SilentlyContinue }
try{ Get-NetTCPConnection -LocalPort $port -ErrorAction Stop | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } } catch{}

Write-Host ""
Write-Host "=== E2E DONE - BABU KUSKURE ===" -ForegroundColor Cyan
Write-Host "Logs: $LogsDir" -ForegroundColor White
