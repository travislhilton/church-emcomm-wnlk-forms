# Before and after a walk through the quick-reference cards on a live EOC laptop: -Step snap stops the servers,
# copies the EOC database, the AppData settings (not the basemap) and the Drop Folder's file list, and starts them
# again; -Step restore puts all of it back byte for byte (the incident, comms sheet and roster are laptop-wide, not
# per event, so a test event's cleanup alone cannot undo a walk) and removes files the walk added to the Drop Folder.
# Run in %USERPROFILE%\emcomm-reinstall next to reinstall_eoc.ps1. Prints no record contents.
param([Parameter(Mandatory)][ValidateSet('snap','restore')][string]$Step)
$ErrorActionPreference = 'Stop'
$name = 'Church of Jesus Christ EMCOMM'; $base = "C:\$name"; $app = Join-Path $env:LOCALAPPDATA $name
$mc = Join-Path $base 'EOC Message Center'
$here = "$env:USERPROFILE\emcomm-reinstall"; Set-Location $here
$snap = Join-Path $here 'cardwalk-snap'
function Stop-Servers {
  Get-CimInstance Win32_Process -Filter "Name='python.exe' or Name='pythonw.exe'" | Where-Object { $_.CommandLine -match 'eoc_server\.py|sim_server\.py' -and $_.CommandLine -notmatch '\\dev\\' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
  Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" | Where-Object { $_.CommandLine -match 'start_eoc_server\.bat|start_simulator\.bat' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
  Start-Sleep 3
}
function Start-Servers { $null = powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'reinstall_eoc.ps1') -Phase start 2>&1 }
function DbHash { (Get-FileHash (Join-Path $mc 'eoc_data.db') -Algorithm SHA256).Hash.Substring(0, 16) }
function DropPath { try { (Invoke-RestMethod http://127.0.0.1:8080/api/drop/status -TimeoutSec 10).watch_path } catch { '' } }
switch ($Step) {
 'snap' {
   $drop = DropPath
   Stop-Servers
   if (Test-Path $snap) { Remove-Item -Recurse -Force $snap }
   New-Item -ItemType Directory -Force "$snap\db", "$snap\app" | Out-Null
   Get-ChildItem $mc -Filter 'eoc_data.db*' -File | Copy-Item -Destination "$snap\db"
   $null = robocopy $app "$snap\app" /E /XD basemap /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
   $files = @(); if ($drop -and (Test-Path $drop)) { $files = @(Get-ChildItem $drop -Recurse -File | ForEach-Object { $_.FullName }) }
   [ordered]@{ drop = $drop; files = $files; db = (DbHash) } | ConvertTo-Json | Set-Content -Encoding utf8 "$snap\state.json"
   Start-Servers
   "snapshot taken: database $(DbHash), $(@(Get-ChildItem "$snap\app" -Recurse -File).Count) settings files, Drop Folder $($files.Count) files"
 }
 'restore' {
   $st = Get-Content -Raw "$snap\state.json" | ConvertFrom-Json
   Stop-Servers
   Get-ChildItem $mc -Filter 'eoc_data.db*' -File | Remove-Item -Force
   Copy-Item "$snap\db\*" $mc
   $null = robocopy "$snap\app" $app /MIR /XD basemap /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
   $added = 0
   if ($st.drop -and (Test-Path $st.drop)) {
     $keep = @{}; foreach ($f in @($st.files)) { $keep[$f] = 1 }
     Get-ChildItem $st.drop -Recurse -File | Where-Object { -not $keep.ContainsKey($_.FullName) } | ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force; $added++ }
   }
   $h = DbHash
   Start-Servers
   "restored: database $h (snapshot $($st.db), equal $($h -eq $st.db)), settings mirrored, $added files the walk added to the Drop Folder removed"
 }
}
