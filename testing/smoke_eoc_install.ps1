# Smoke test of a freshly installed EOC laptop (checklist A18). Run ON the laptop after testing\reinstall_eoc.ps1 -Phase start;
# then stop and start both servers and run -Step restart-check, then -Step cleanup.
# Works in a test event of its own and removes it afterwards; the event the laptop had stays active.
param([ValidateSet('stake','area')][string]$Role = 'stake', [string]$Want = '2026-11-13.3', [ValidateSet('all','restart-check','cleanup')][string]$Step = 'all')
$ErrorActionPreference = 'Stop'
$EOCURL = 'http://127.0.0.1:8080'; $SIM = 'http://127.0.0.1:8090'; $name = 'Church of Jesus Christ EMCOMM'
$base = "C:\$name"; New-Item -ItemType Directory -Force "$env:USERPROFILE\emcomm-reinstall" | Out-Null
$state = "$env:USERPROFILE\emcomm-reinstall\smoke-state.json"
$script:pass = 0; $script:fail = 0
function J($m, $p, $body = $null, $root = $EOCURL) { if ($null -ne $body) { Invoke-RestMethod -Method $m -Uri "$root$p" -ContentType 'application/json' -Body ($body | ConvertTo-Json -Depth 12 -Compress) -TimeoutSec 30 } else { Invoke-RestMethod -Method $m -Uri "$root$p" -TimeoutSec 30 } }
function C($label, $ok, $detail = '') { if ($ok) { $script:pass++; "PASS $label" } else { $script:fail++; "FAIL $label -- $detail" } }
# Windows PowerShell 5.1 hands a JSON list back as ONE object: unroll it before counting or looping
function L($p, $root = $EOCURL) { $r = J GET $p $null $root; @($r | ForEach-Object { $_ }) }
function Smoke-Msgs { @(L /api/messages | Where-Object { $_.data_json -like '*SMOKE*' }) }

if ($Step -eq 'all') {
  # 1. what the installer put on the laptop
  $desk = [Environment]::GetFolderPath('Desktop')
  foreach ($t in "$base\EOC Message Center\eoc_server.py", "$base\EOC Message Center\simulation\sim_server.py", "$base\EOC Message Center\simulation\example\juniper-plains\csv\organizations.csv",
                 (Join-Path $desk "$name EOC Server.lnk"), (Join-Path $desk "$name Simulator.lnk"), (Join-Path $desk "$name EOC Message Center.lnk"), (Join-Path $desk "$name Forms"),
                 "C:\RMS Express\Global Folders\Templates\$name Forms") { C "installed: $(Split-Path $t -Leaf)" (Test-Path -LiteralPath $t) $t }
  # 2. the EOC server and its pages
  $st = J GET /api/status
  C "EOC server answers, forms version $($st.formsVersion)" ($st.ok -and $st.formsVersion -eq $Want) $st.formsVersion
  foreach ($pg in '/', '/wall', '/m', '/forms/dr', '/forms/so', '/forms/wcl') {
    try { $r = Invoke-WebRequest -UseBasicParsing "$EOCURL$pg" -TimeoutSec 15; C "page $pg" ($r.StatusCode -eq 200 -and $r.Content.Length -gt 1500) $r.StatusCode } catch { C "page $pg" $false $_.Exception.Message }
  }
  # 3. a test event of its own
  $orig = $st.activeEventId
  $null = J POST /api/events @{ name = 'SMOKE TEST after reinstall (THIS IS AN EXERCISE)'; type = 'Test' }
  $smoke = (J GET /api/status).activeEventId
  C 'a test event opened and made active' ($smoke -and $smoke -ne $orig)
  @{ orig = $orig; smoke = $smoke } | ConvertTo-Json | Set-Content -Encoding utf8 $state
  # 4. reports in: Send to EOC (phone), the Drop Folder, a duplicate
  $today = Get-Date -Format 'yyyy-MM-dd'
  $dr = @{ inc_stake = 'Larkspur Stake'; inc_ward = 'Larkspur 1st Ward'; inc_type = 'Flood'; inc_date = $today; inc_location = 'SMOKE 1 Test Ln'; sub_name = 'Smoke Tester'; mem_injuries = '1'; exercise = $true }
  $u = J POST /api/upload @{ reports = @(@{ id = 'smoke1'; form = 'dr'; data = $dr }) }
  C 'Send to EOC files a report (phone path)' ($u.ok -and $u.new -eq 1) ($u | ConvertTo-Json -Compress)
  $u2 = J POST /api/upload @{ reports = @(@{ id = 'smoke1-again'; form = 'dr'; data = $dr }) }
  C 'the same report again is a duplicate' ($u2.dup -eq 1) ($u2 | ConvertTo-Json -Compress)
  $drop = (J GET /api/drop/status).watch_path
  $dr2 = $dr.Clone(); $dr2.inc_location = 'SMOKE 2 Drop Ln'
  ($dr2 | ConvertTo-Json) | Set-Content -Encoding utf8 (Join-Path $drop 'Church_Disaster_Report_Worker.txt')
  $ok = $false; for ($i = 0; $i -lt 30; $i++) { Start-Sleep 1; if (Smoke-Msgs | Where-Object { $_.data_json -like '*SMOKE 2 Drop Ln*' }) { $ok = $true; break } }
  C 'a report saved into the Drop Folder is filed within 30 s' $ok $drop
  C 'work item made from the injury report' ((L /api/actions).Count -ge 1)
  try { $ro = J GET /api/readout; C 'incident read-out (/api/readout) answers' ($null -ne $ro) } catch { C 'incident read-out' $false $_.Exception.Message }
  $bs = J GET /api/basemap/status; C 'basemap status answers (nothing downloaded yet)' ($null -ne $bs)
  # 5. the simulator: the invented example pack, its drill configuration, a short run delivering to this EOC
  $si = J GET /api/info $null $SIM
  C 'simulator answers' ($null -ne $si)
  @{ packPath = $si.packPath; privacy = $si.privacy; scenario = $si.scenario } | ConvertTo-Json | Add-Content -Encoding utf8 "$env:USERPROFILE\emcomm-reinstall\sim-before.json"
  $ex = "$base\EOC Message Center\simulation\example\juniper-plains"
  $p = J POST /api/pack @{ path = $ex; privacy = 'pseudonymized' } $SIM
  C 'simulator loads the example organization pack' ($p.ok -ne $false -and $p.info.pack) ($p | ConvertTo-Json -Compress -Depth 3).Substring(0, 160)
  $raw = [IO.File]::ReadAllText("$ex\simulation\drill-config.json", [Text.Encoding]::UTF8)
  $cfg = $raw | ConvertFrom-Json
  $eocId = if ($Role -eq 'area') { 'area' } else { 'larkspur' }
  # the file's own text, as the page sends it (Windows PowerShell 5.1 would reshape it on the way back to JSON)
  $dc = Invoke-RestMethod -Method POST -Uri "$SIM/api/drillconfig" -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes('{"config":' + $raw + ',"eoc":"' + $eocId + '","manned":["' + $eocId + '"]}'))
  C "simulator set up from the example drill configuration as '$eocId'" ($dc.ok -ne $false) (($dc | ConvertTo-Json -Compress -Depth 3) -replace '^(.{160}).*', '$1')
  $info = J GET /api/info $null $SIM
  $plan = J POST /api/run/plan @{ scenario = $cfg.scenario; speed = 60; site = $info.site } $SIM
  C 'simulator plans the scenario against this EOC' ($plan.ok -and $plan.counts) (($plan | ConvertTo-Json -Compress -Depth 3) -replace '^(.{160}).*', '$1')
  $n0 = (L /api/messages).Count
  $null = J POST /api/run/start @{} $SIM
  $ok = $false; for ($i = 0; $i -lt 120; $i++) { Start-Sleep 2; if ((L /api/messages).Count -gt $n0) { $ok = $true; break } }
  $null = J POST /api/run/stop @{} $SIM
  C 'a simulator run delivers reports to the EOC (60x, within 4 min)' $ok "messages before $n0, after $((L /api/messages).Count)"
}
if ($Step -eq 'restart-check') {
  $s = Get-Content -Raw $state | ConvertFrom-Json
  $st = J GET /api/status
  C 'after a restart the EOC server answers and the test event is still active' ($st.ok -and $st.activeEventId -eq $s.smoke)
  C 'after a restart the test reports are still on file' (@(Smoke-Msgs).Count -ge 2)
  C 'after a restart the simulator answers' ($null -ne (J GET /api/info $null $SIM))
}
if ($Step -eq 'cleanup') {
  try { $null = J POST /api/run/stop @{} $SIM } catch {}
  $evs = (L /api/events)
  $smokes = @($evs | Where-Object { $_.name -like 'SMOKE TEST*' })
  $keep = $evs | Where-Object { $_.name -notlike 'SMOKE TEST*' } | Select-Object -First 1
  foreach ($e in $smokes) {
    $null = J PUT "/api/events/$($e.id)" @{ activate = $true }
    foreach ($m in (L /api/messages)) { $null = Invoke-RestMethod -Method DELETE -Uri "$EOCURL/api/messages/$($m.id)" }
    foreach ($a in (L /api/actions)) { $null = Invoke-RestMethod -Method DELETE -Uri "$EOCURL/api/actions/$($a.id)" }
  }
  $null = J PUT "/api/events/$($keep.id)" @{ activate = $true }
  foreach ($e in $smokes) { $null = Invoke-RestMethod -Method DELETE -Uri "$EOCURL/api/events/$($e.id)" }
  $st = J GET /api/status; $left = @((L /api/events) | Where-Object { $_.name -like 'SMOKE TEST*' }).Count
  C "test events removed ($($smokes.Count)); the original event active again with nothing in it" ($left -eq 0 -and $st.activeEventId -eq $keep.id -and $st.msgCount -eq 0) "left $left, msgs $($st.msgCount)"
  $drop = (J GET /api/drop/status).watch_path
  Get-ChildItem -LiteralPath (Join-Path (Split-Path $drop) 'EOC Ingested'), (Join-Path $drop 'Ingested') -Filter 'Church_Disaster_Report_Worker*' -ErrorAction SilentlyContinue | Remove-Item -Force
}
"RESULT: $script:pass passed, $script:fail failed"
