# Full test of a live EOC laptop with the released installer: uninstall (U) with the servers running, install
# role 3 from the release, restore from the uninstall's own records copy, smoke test, restart, cleanup, resettle.
# Checklist A18 / A19. Copy it with reinstall_eoc.ps1 and smoke_eoc_install.ps1 into %USERPROFILE%\emcomm-reinstall on the
# laptop and run, in order: -Step pre, uninstall, install, smoke, resettle. Prints no record contents.
# -WantSha: the first characters of the release installer's SHA-256 (empty = any).
param([Parameter(Mandatory)][ValidateSet('stake','area')][string]$Role,
      [Parameter(Mandatory)][ValidateSet('pre','uninstall','install','smoke','resettle')][string]$Step, [string]$WantSha = '')
$ErrorActionPreference = 'Stop'
$name = 'Church of Jesus Christ EMCOMM'; $base = "C:\$name"; $app = Join-Path $env:LOCALAPPDATA $name
$here = "$env:USERPROFILE\emcomm-reinstall"; Set-Location $here
$preFile = Join-Path $here 'pre-full.json'
$EOC = 'http://127.0.0.1:8080'; $SIM = 'http://127.0.0.1:8090'
$script:pass = 0; $script:fail = 0
function C($label, $ok, $detail = '') { if ($ok) { $script:pass++; "PASS $label" } else { $script:fail++; "FAIL $label -- $detail" } }
function G($u) { Invoke-RestMethod $u -TimeoutSec 20 }
function PS1($file, [string[]]$a) { powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here $file) @a 2>&1 | Out-String }
function Listening($port) { @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue).Count -gt 0 }
function State {
  $st = G "$EOC/api/status"; $inc = G "$EOC/api/incident"; $w = G "$EOC/api/watcher/status"; $d = G "$EOC/api/drop/status"; $si = G "$SIM/api/info"
  [ordered]@{ forms = $st.formsVersion; event = $st.activeEventId; level = $inc.eocLevel; wPath = $w.watch_path; wCalls = (@($w.callsigns) -join ','); wOn = [bool]$w.enabled
              dPath = $d.watch_path; pack = $si.packPath; privacy = $si.privacy; scenario = $si.scenario; site = $si.site.role }
}
function Restart-Servers {
  Get-CimInstance Win32_Process -Filter "Name='python.exe' or Name='pythonw.exe'" | Where-Object { $_.CommandLine -match 'eoc_server\.py|sim_server\.py' -and $_.CommandLine -notmatch '\\dev\\' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
  Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" | Where-Object { $_.CommandLine -match 'start_eoc_server\.bat|start_simulator\.bat' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
  Start-Sleep 3; $null = PS1 'reinstall_eoc.ps1' @('-Phase', 'start')
}
function Copy-Back {   # the uninstall's records copy -> the new install: database and settings
  $rec = Get-ChildItem $env:USERPROFILE -Directory -Filter "$name records *" | Sort-Object LastWriteTime | Select-Object -Last 1
  $mc = Join-Path $rec.FullName 'install folder (system drive)\EOC Message Center'
  if (-not (Test-Path $mc)) { $mc = Join-Path $rec.FullName 'install folder (Documents)\EOC Message Center' }
  Get-ChildItem $mc -Filter 'eoc_data.db*' -File | Copy-Item -Destination "$base\EOC Message Center" -Force
  $null = robocopy (Join-Path $rec.FullName 'settings (AppData)') $app /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
  $rec.FullName
}

switch ($Step) {
 'pre' {
   $s = State; $s | ConvertTo-Json | Set-Content -Encoding utf8 $preFile
   "before: forms $($s.forms), level $($s.level), Winlink folder set $([bool]$s.wPath) ($($s.wCalls)), Drop Folder set $([bool]$s.dPath), simulator privacy $($s.privacy), scenario $($s.scenario), site $($s.site)"
   PS1 'reinstall_eoc.ps1' @('-Phase', 'backup')
   PS1 'reinstall_eoc.ps1' @('-Phase', 'start')
 }
 'uninstall' {
   C 'before: the EOC Server and Simulator are running (8080, 8090 listening)' ((Listening 8080) -and (Listening 8090))
   $wins = @(Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" | Where-Object { $_.CommandLine -match 'start_eoc_server\.bat|start_simulator\.bat' }).Count
   C "before: their two console windows are open ($wins)" ($wins -ge 2)
   $dir = Join-Path $here 'fulltest'; New-Item -ItemType Directory -Force $dir | Out-Null
   $bat = Join-Path $dir 'ChurchEMCOMM_Installer_v1.0.bat'
   Invoke-WebRequest -UseBasicParsing 'https://github.com/travislhilton/church-emcomm-wnlk-forms/releases/download/v1.0/ChurchEMCOMM_Installer_v1.0.bat' -OutFile $bat
   $h = (Get-FileHash $bat -Algorithm SHA256).Hash
   C "the release's installer downloaded (sha256 $($h.Substring(0,16)))" (-not $WantSha -or $h.StartsWith($WantSha.ToUpper()))
   $out = "u`ny`n`n`n" | cmd /c "`"$bat`"" 2>&1 | Out-String
   Set-Content -Encoding utf8 (Join-Path $dir 'uninstall.log') $out
   C 'uninstall: lists what it removes' ($out -match 'This removes:')
   C 'uninstall: stopped the running EOC Server and Simulator' ($out -match 'Stopped the EOC Server')
   C 'uninstall: copied the records' ($out -match 'Records copied:')
   C 'uninstall: says it is uninstalled' ($out -match 'is uninstalled') (($out -split "`n" | Select-String 'still there|XX|!!' | ForEach-Object { $_.Line.Trim() }) -join ' | ')
   Start-Sleep 2
   C 'after: nothing listens on 8080 or 8090' (-not (Listening 8080) -and -not (Listening 8090))
   $desk = [Environment]::GetFolderPath('Desktop')
   $left = @(@($base, $app) | Where-Object { Test-Path -LiteralPath $_ }) + @(Get-ChildItem -LiteralPath $desk -Filter "$name*" -ErrorAction SilentlyContinue | ForEach-Object { $_.Name }) +
           @(Get-ChildItem 'C:\RMS Express\Global Folders\Templates' -Directory -Filter "$name*" -ErrorAction SilentlyContinue | ForEach-Object { $_.Name })
   C 'after: install folder, AppData folder, Desktop items and Winlink template folders are gone' (-not $left.Count) ($left -join '; ')
   C 'after: Winlink Express and Python are still installed' ((Test-Path 'C:\RMS Express\RMS Express.exe') -and (Test-Path 'C:\Program Files\Python312\python.exe'))
   $rec = Get-ChildItem $env:USERPROFILE -Directory -Filter "$name records *" | Sort-Object LastWriteTime | Select-Object -Last 1
   $db = @(Get-ChildItem $rec.FullName -Recurse -File -Filter 'eoc_data.db')
   C "the records copy holds the database and the settings ($(@(Get-ChildItem $rec.FullName -Recurse -File).Count) files)" ($db.Count -eq 1 -and $db[0].Length -gt 0 -and (Test-Path (Join-Path $rec.FullName 'settings (AppData)\simulator-settings.json')))
 }
 'install' {
   PS1 'reinstall_eoc.ps1' @('-Phase', 'install')
   "restored from the records copy: " + (Copy-Back)
   PS1 'reinstall_eoc.ps1' @('-Phase', 'start')
   $pre = Get-Content -Raw $preFile | ConvertFrom-Json; $now = State
   C "new install answers, forms version $($now.forms) (as before)" ($now.forms -eq $pre.forms)
   foreach ($k in 'event', 'level', 'wPath', 'wCalls', 'wOn', 'dPath', 'pack', 'privacy', 'scenario', 'site') {
     C "restored from the uninstall's copy: $k" ("$($pre.$k)" -eq "$($now.$k)") "was set $([bool]"$($pre.$k)"), now differs"
   }
 }
 'smoke' {
   Remove-Item -ErrorAction SilentlyContinue (Join-Path $here 'sim-before.json')
   PS1 'smoke_eoc_install.ps1' @('-Role', $Role) | Select-String 'RESULT|FAIL' | ForEach-Object { 'smoke: ' + $_.Line }
   Restart-Servers
   PS1 'smoke_eoc_install.ps1' @('-Role', $Role, '-Step', 'restart-check') | Select-String 'RESULT|FAIL' | ForEach-Object { 'restart-check: ' + $_.Line }
   PS1 'smoke_eoc_install.ps1' @('-Role', $Role, '-Step', 'cleanup') | Select-String 'RESULT|FAIL' | ForEach-Object { 'cleanup: ' + $_.Line }
 }
 'resettle' {   # the smoke test leaves the invented example in the simulator: put this laptop's own simulator settings back
   $rec = Get-ChildItem $env:USERPROFILE -Directory -Filter "$name records *" | Sort-Object LastWriteTime | Select-Object -Last 1
   Get-CimInstance Win32_Process -Filter "Name='python.exe' or Name='pythonw.exe'" | Where-Object { $_.CommandLine -match 'sim_server\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
   Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" | Where-Object { $_.CommandLine -match 'start_simulator\.bat' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
   Start-Sleep 2
   Copy-Item (Join-Path $rec.FullName 'settings (AppData)\simulator-settings.json') $app -Force
   Restart-Servers
   $pre = Get-Content -Raw $preFile | ConvertFrom-Json; $now = State
   foreach ($k in 'event', 'level', 'wPath', 'wCalls', 'dPath', 'pack', 'privacy', 'scenario', 'site') {
     C "as before the test: $k" ("$($pre.$k)" -eq "$($now.$k)") "was set $([bool]"$($pre.$k)")"
   }
   C 'as before the test: the active event is empty' ((G "$EOC/api/status").msgCount -eq 0)
 }
}
if ($script:pass + $script:fail) { "RESULT: $script:pass passed, $script:fail failed" }
