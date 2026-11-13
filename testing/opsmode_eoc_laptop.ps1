# Checklist A21. Actual operations (no drill) with an organization pack as the EOC's map data, in a test event. Puts the map setting back.
# -Step rmssnap / rmscompare: Winlink Express's folders before and after (nothing may be written to its messages or outbox).
param([string]$Pack = '', [ValidateSet('run','rmssnap','rmscompare')][string]$Step = 'run')
$ErrorActionPreference = 'Stop'; $EOC = 'http://127.0.0.1:8080'; $here = "$env:USERPROFILE\emcomm-reinstall"
$script:pass = 0; $script:fail = 0
function C($label, $ok, $detail = '') { if ($ok) { $script:pass++; "PASS $label" } else { $script:fail++; "FAIL $label -- $detail" } }
function Rms { @(Get-ChildItem 'C:\RMS Express' -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notmatch '\\Logs\\|\.log$' } | ForEach-Object { $_.FullName + '|' + $_.Length + '|' + $_.LastWriteTimeUtc.Ticks }) }
if ($Step -eq 'rmssnap') { $l = Rms; $l | Set-Content -Encoding utf8 "$here\rms-before.txt"; "Winlink Express snapshot: $($l.Count) files"; exit }
if ($Step -eq 'rmscompare') {
  $b = @(Get-Content "$here\rms-before.txt"); $a = Rms
  $d = @(Compare-Object $b $a | ForEach-Object { ($_.InputObject -split '\|')[0] } | Sort-Object -Unique)
  $msg = @($d | Where-Object { $_ -match '\\(Messages|Outbox|Mailbox)\\|\.mime$|\.b2f$' })
  C "nothing new or changed in Winlink Express's messages or outbox during the tests ($($b.Count) -> $($a.Count) files)" ($msg.Count -eq 0) "$($msg.Count) message files changed"
  "other Winlink Express files changed (not messages): $($d.Count - $msg.Count)"
  "RESULT: $script:pass passed, $script:fail failed"; exit
}
$inc0 = Invoke-RestMethod "$EOC/api/incident"; $orig = (Invoke-RestMethod "$EOC/api/status").activeEventId
$m0 = Invoke-RestMethod "$EOC/api/map/status"
$null = Invoke-RestMethod -Method POST -Uri "$EOC/api/events" -ContentType 'application/json' -Body (@{ name = 'SMOKE TEST actual operations with the organization pack (THIS IS AN EXERCISE)'; type = 'Test' } | ConvertTo-Json)
$ev = (Invoke-RestMethod "$EOC/api/status").activeEventId
C 'a test event of its own is active (not a drill)' ($ev -and $ev -ne $orig -and -not (Invoke-RestMethod "$EOC/api/drill").active)
$inc = Invoke-RestMethod "$EOC/api/incident"; $inc | Add-Member -Force NoteProperty mapPath $Pack
$null = Invoke-RestMethod -Method PUT -Uri "$EOC/api/incident" -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes(($inc | ConvertTo-Json -Depth 20)))
$m = Invoke-RestMethod "$EOC/api/map/status"
C "the pack is this EOC's map data: $($m.stakes) stakes, $($m.units) wards and branches, $($m.buildings) buildings" ($m.ok -and $m.stakes -gt 0 -and $m.units -gt 0)
$gj = Invoke-WebRequest -UseBasicParsing "$EOC/map/organization_boundaries.geojson"
$gt = if ($gj.Content -is [byte[]]) { [Text.Encoding]::UTF8.GetString($gj.Content) } else { [string]$gj.Content }
C "the Map tab and the wall get the boundaries ($([int]($gt.Length/1KB)) KB)" ($gj.StatusCode -eq 200 -and $gt -match 'FeatureCollection')
foreach ($pg in '/', '/wall', '/m') { C "page $pg answers with the map data set" ((Invoke-WebRequest -UseBasicParsing "$EOC$pg").StatusCode -eq 200) }
$r = Invoke-RestMethod -Method POST -Uri "$EOC/api/upload" -ContentType 'application/json' -Body (@{ reports = @(@{ id = 'opsmode-' + [guid]::NewGuid().ToString('N').Substring(0,8); form = 'dr'; data = @{ inc_stake = 'Test Stake'; inc_ward = 'Test Ward'; inc_type = 'Flood'; inc_date = (Get-Date -Format 'yyyy-MM-dd'); inc_location = 'SMOKE 1 Test Ln'; sub_name = 'Smoke Tester'; exercise = $true } }) } | ConvertTo-Json -Depth 6)
C 'a report sent to the EOC is filed in the test event' ($r.ok -and $r.new -ge 1)
C 'the incident read-out answers' ([bool](Invoke-RestMethod "$EOC/api/readout"))
$inc = Invoke-RestMethod "$EOC/api/incident"; $inc | Add-Member -Force NoteProperty mapPath ([string]$inc0.mapPath)
$null = Invoke-RestMethod -Method PUT -Uri "$EOC/api/incident" -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes(($inc | ConvertTo-Json -Depth 20)))
$m1 = Invoke-RestMethod "$EOC/api/map/status"
C 'the map data setting is back as before' ("$($m1.path)" -eq "$($m0.path)" -and [bool]$m1.ok -eq [bool]$m0.ok)
"RESULT: $script:pass passed, $script:fail failed"
