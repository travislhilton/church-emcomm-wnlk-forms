# Full test of a live EOC laptop with the released installer: uninstall (U) with the servers running, install
# role 3 from the release, restore from the uninstall's own records copy, smoke test, restart, cleanup, resettle.
# Checklist A18 / A19. Copy it with reinstall_eoc.ps1 and smoke_eoc_install.ps1 into %USERPROFILE%\emcomm-reinstall on the
# laptop and run, in order: -Step pre, uninstall, install, verify, smoke, simulate, cleanup, resettle.
# verify: the installed EOC and simulator equal the GitHub release's ZIP. simulate: a whole scenario at 60x.
# Prints no record contents.
# -WantSha: the first characters of the release installer's SHA-256 (empty = any).
param([Parameter(Mandatory)][ValidateSet('stake','area')][string]$Role,
      [Parameter(Mandatory)][ValidateSet('pre','uninstall','install','verify','smoke','simulate','cleanup','resettle')][string]$Step, [string]$WantSha = '',
      [ValidateSet('example','own')][string]$Pack = 'example', [string]$PackPath = '', [string]$DrillConfig = '')
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
   C "new install answers, forms version $($now.forms) (was $($pre.forms))" ($now.forms -and $now.forms -ge $pre.forms)
   foreach ($k in 'event', 'level', 'wPath', 'wCalls', 'wOn', 'dPath', 'pack', 'privacy', 'scenario', 'site') {
     C "restored from the uninstall's copy: $k" ("$($pre.$k)" -eq "$($now.$k)") "was set $([bool]"$($pre.$k)"), now differs"
   }
 }
 'smoke' {
   Remove-Item -ErrorAction SilentlyContinue (Join-Path $here 'sim-before.json')
   PS1 'smoke_eoc_install.ps1' @('-Role', $Role) | Select-String 'RESULT|FAIL' | ForEach-Object { 'smoke: ' + $_.Line }
   Restart-Servers
   PS1 'smoke_eoc_install.ps1' @('-Role', $Role, '-Step', 'restart-check') | Select-String 'RESULT|FAIL' | ForEach-Object { 'restart-check: ' + $_.Line }
 }
 'cleanup' {   # removes every SMOKE TEST event (the smoke test's and the simulation's)
   PS1 'smoke_eoc_install.ps1' @('-Role', $Role, '-Step', 'cleanup') | Select-String 'RESULT|FAIL' | ForEach-Object { 'cleanup: ' + $_.Line }
 }
 'verify' {     # the installed EOC and simulator are the GitHub release's files, byte for byte (line endings aside)
   $dir = Join-Path $here 'fulltest'; New-Item -ItemType Directory -Force $dir | Out-Null
   $zip = Join-Path $dir 'ChurchEMCOMM_Forms_v1.0.zip'; $ex = Join-Path $dir 'release-zip'
   Invoke-WebRequest -UseBasicParsing 'https://github.com/travislhilton/church-emcomm-wnlk-forms/releases/download/v1.0/ChurchEMCOMM_Forms_v1.0.zip' -OutFile $zip
   if (Test-Path $ex) { Remove-Item -Recurse -Force $ex }
   Add-Type -AssemblyName System.IO.Compression.FileSystem; [IO.Compression.ZipFile]::ExtractToDirectory($zip, $ex)
   $mc = "$base\EOC Message Center"; $same = 0; $diff = @(); $missing = @()
   foreach ($pair in @(@('eoc', $mc), @('simulation', (Join-Path $mc 'simulation')))) {
     $src = Join-Path $ex $pair[0]
     foreach ($f in Get-ChildItem $src -Recurse -File) {
       $rel = $f.FullName.Substring($src.Length + 1); $inst = Join-Path $pair[1] $rel
       if (-not (Test-Path -LiteralPath $inst)) { $missing += "$($pair[0])\$rel"; continue }
       $a = [IO.File]::ReadAllBytes($f.FullName); $b = [IO.File]::ReadAllBytes($inst)
       $na = [Text.Encoding]::UTF8.GetString($a) -replace "`r`n", "`n"; $nb = [Text.Encoding]::UTF8.GetString($b) -replace "`r`n", "`n"
       if ($na -ceq $nb) { $same++ } else { $diff += "$($pair[0])\$rel" }
     }
   }
   C "installed EOC and simulator files equal the GitHub release's ($same files)" ($same -ge 40 -and -not $diff.Count) ($diff -join '; ')
   C "every EOC and simulator file of the release is installed" (-not $missing.Count) (($missing | Select-Object -First 8) -join '; ')
   $st = G "$EOC/api/status"; $si = G "$SIM/api/info"
   C "the running EOC server is the installed one, version $($st.formsVersion)" ($st.ok -and (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*$mc\eoc_server.py*" }))
   C 'the running simulator is the installed one' ($si.ok -and (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*$mc\simulation\sim_server.py*" }))
   Remove-Item -Recurse -Force $ex
 }
 'simulate' {   # a whole scenario from the installed simulator into the installed EOC, in a test event of its own
   $orig = (G "$EOC/api/status").activeEventId
   $null = Invoke-RestMethod -Method POST -Uri "$EOC/api/events" -ContentType 'application/json' -Body (@{ name = "SMOKE TEST full simulation, $Pack pack (THIS IS AN EXERCISE)"; type = 'Test' } | ConvertTo-Json)
   $ev = (G "$EOC/api/status").activeEventId
   C 'a test event of its own is active' ($ev -and $ev -ne $orig)
   if ($Pack -eq 'own') {
     # this laptop's own organization pack, scenario and site, as the reinstall restored them; contacts pseudonymized only.
     # Prints counts only: the pack, its scenario and its units are private.
     # As the drill controller does (card 5): the pack, then its own drill configuration as this laptop's level.
     # -PackPath: a copy of another laptop's pack (W9TLH-8 has none of its own); resettle puts the settings back.
     $info = G "$SIM/api/info"
     $pp = if ($PackPath) { $PackPath } else { [string]$info.packPath }
     if ($pp -and $pp -notlike '*\simulation\example\*') {
       $null = Invoke-RestMethod -Method POST -Uri "$SIM/api/pack" -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes((@{ path = $pp; privacy = 'pseudonymized' } | ConvertTo-Json)))
       # a pack with no drill configuration of its own (a full export): the drill configuration given, whose pack
       # path is empty, so the simulator keeps the pack just loaded (as on Setup step 1)
       $dcf = if ($DrillConfig) { $DrillConfig } else { Join-Path $pp 'simulation\drill-config.json' }
       if (Test-Path $dcf) {
         $raw = [IO.File]::ReadAllText($dcf, [Text.Encoding]::UTF8); $dcc = $raw | ConvertFrom-Json
         $eocId = @($dcc.eocs | Where-Object { $_.level -eq $Role })[0].id
         $dc = Invoke-RestMethod -Method POST -Uri "$SIM/api/drillconfig" -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes('{"config":' + $raw + ',"eoc":"' + $eocId + '","manned":["' + $eocId + '"]}'))
         C "set up from the pack's own drill configuration as its $Role EOC" ([bool]$eocId -and $dc.ok -ne $false)
       }
       $info = G "$SIM/api/info"
     }
     $own = $info.pack -and $info.packPath -and $info.packPath -notlike '*\simulation\example\*' -and (-not $PackPath -or $info.packPath -eq $PackPath)
     C 'the simulator holds this laptop''s own organization pack (not the invented example)' $own
     C 'its contacts are pseudonymized (invented names)' ($info.privacy -eq 'pseudonymized') "privacy $($info.privacy)"
     C 'a scenario and what this simulator plays are set' ([bool]$info.scenario -and [bool]$info.site.role)
     if (-not ($own -and $info.privacy -eq 'pseudonymized' -and $info.scenario)) { break }
     $cfg = @{ scenario = $info.scenario }; $label = 'its own scenario'
   } else {
   $ex = "$base\EOC Message Center\simulation\example\juniper-plains"
   $p = Invoke-RestMethod -Method POST -Uri "$SIM/api/pack" -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes((@{ path = $ex; privacy = 'pseudonymized' } | ConvertTo-Json)))
   C 'the installed simulator loads the invented example pack' ($p.ok -ne $false)
   $raw = [IO.File]::ReadAllText("$ex\simulation\drill-config.json", [Text.Encoding]::UTF8); $cfg = $raw | ConvertFrom-Json
   $eocId = if ($Role -eq 'area') { 'area' } else { 'larkspur' }
   $dc = Invoke-RestMethod -Method POST -Uri "$SIM/api/drillconfig" -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes('{"config":' + $raw + ',"eoc":"' + $eocId + '","manned":["' + $eocId + '"]}'))
   C "set up from the example drill configuration as '$eocId'" ($dc.ok -ne $false)
   $info = G "$SIM/api/info"; $label = "scenario $($cfg.scenario)"
   }
   $plan = Invoke-RestMethod -Method POST -Uri "$SIM/api/run/plan" -ContentType 'application/json' -Body (@{ scenario = $cfg.scenario; speed = 60; site = $info.site } | ConvertTo-Json -Depth 8)
   C "$label planned: $($plan.counts.items) items for $($plan.counts.units) units" ($plan.ok -and $plan.counts.items -gt 0 -and $plan.counts.units -gt 0)
   $null = Invoke-RestMethod -Method POST -Uri "$SIM/api/run/start" -ContentType 'application/json' -Body '{}'
   $t0 = Get-Date; $status = ''
   while (((Get-Date) - $t0).TotalMinutes -lt 12) { Start-Sleep 10; $status = (G "$SIM/api/run").clock.status; if ($status -eq 'finished') { break } }
   C "the whole scenario ran to the end at 60x ($([int]((Get-Date) - $t0).TotalSeconds) s)" ($status -eq 'finished') $status
   $rep = G "$SIM/api/run/report"
   $r = if ($rep.score) { $rep.score } else { $rep }
   # a report the scenario holds until an operator acts (status 'waiting', e.g. the voice relay that needs a logged relay plan)
   # is not sent in an unattended run: every other one must be
   $waiting = @((G "$SIM/api/run").items | Where-Object { $_.kind -eq 'form' -and $_.local -ne $false -and -not $_.rollup -and $_.status -eq 'waiting' }).Count
   if ($Role -eq 'area') {
     # a Council / Area EOC gets the simulated stakes' reports only inside their roll-ups (card 8): every roll-up goes,
     # each report rides in one, except those dated after the stake's last roll-up (skipped when the drill ends)
     $its = @((G "$SIM/api/run").items)
     $rolls = @($its | Where-Object { $_.kind -eq 'rollup' }); $bund = @($its | Where-Object { $_.rollup })
     $rf = @($rolls | Where-Object { $_.status -eq 'fired' }).Count; $bf = @($bund | Where-Object { $_.status -eq 'fired' }).Count; $bs = @($bund | Where-Object { $_.status -eq 'skipped' }).Count; $bw = @($bund | Where-Object { $_.status -eq 'waiting' }).Count
     C "every roll-up from the simulated stakes was sent ($rf of $($rolls.Count)), carrying $bf reports; $bs dated after the last roll-up not sent; $bw waiting on a need that never came" ($rolls.Count -gt 0 -and $rf -eq $rolls.Count -and $bf -gt 0 -and $bf + $bs + $bw -eq $bund.Count) (($bund | Group-Object status | ForEach-Object { $_.Name + '=' + $_.Count }) -join ', ')
   } else {
   C "every scheduled report was sent ($($r.reports.sent) of $($r.reports.expected); $waiting held for an operator action)" ($r.reports.expected -gt 0 -and $r.reports.sent + $waiting -eq $r.reports.expected) "status $($rep.run.status)"
   }
   C 'the simulator reached the EOC with no error' (-not $r.eoc_error) $r.eoc_error
   $msgs = @((Invoke-RestMethod "$EOC/api/messages" -TimeoutSec 30) | ForEach-Object { $_ })
   $ids = @($msgs | ForEach-Object { $_.id } | Select-Object -Unique)
   C "the EOC filed the simulator's reports ($($msgs.Count) in the test event, each once)" ($msgs.Count -gt 0 -and $ids.Count -eq $msgs.Count)
   $acts = @((Invoke-RestMethod "$EOC/api/actions" -TimeoutSec 30) | ForEach-Object { $_ })
   C "work items were made from them ($($acts.Count))" ($acts.Count -gt 0)
   $ro = G "$EOC/api/readout"
   C 'the incident read-out answers for the test event' ($null -ne $ro)
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
