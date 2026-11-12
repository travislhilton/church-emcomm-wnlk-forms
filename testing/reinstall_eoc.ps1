# From-scratch reinstall of an EOC laptop, as a new computer would get it (checklist A18). Run on the laptop, in PowerShell.
# Order: -Phase backup, -Phase uninstall, -Phase install, -Phase start, then testing\smoke_eoc_install.ps1.
#   -Phase backup     copy everything the app installed or wrote to %USERPROFILE%\emcomm-backup-<stamp> (nothing removed)
#   -Phase uninstall  stop the app's servers, remove everything the installer created; Python, Chrome, Winlink Express stay
#   -Phase install    download the installer from the GitHub release (as a new computer would) and run role 3
#   -Phase start      start the EOC Server and the Simulator from their Desktop shortcuts, in the desktop session
param([Parameter(Mandatory)][ValidateSet('backup','uninstall','install','start')][string]$Phase, [string]$Stamp = (Get-Date -Format 'yyyyMMdd-HHmm'))
$ErrorActionPreference = 'Stop'
$name   = 'Church of Jesus Christ EMCOMM'
$desk   = [Environment]::GetFolderPath('Desktop'); $docs = [Environment]::GetFolderPath('MyDocuments')
$targets = @("C:\$name", (Join-Path $docs $name), (Join-Path $env:LOCALAPPDATA $name), (Join-Path $desk "$name Forms"),
             (Join-Path $desk "$name Quick Reference Cards.lnk"), "C:\RMS Express\Global Folders\Templates\$name Forms",
             "C:\Winlink Express\Global Folders\Templates\$name Forms")
# every Desktop item the installer made (the Forms folder, the EOC Server / Message Center / Drop Folder / Simulator / Cards
# shortcuts) and OneDrive's conflict copies of them (name-<COMPUTER>.lnk)
$targets += @(Get-ChildItem -LiteralPath $desk -Filter "$name*" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$targets = @($targets | Select-Object -Unique)
function Stop-App {
  Get-CimInstance Win32_Process -Filter "Name='python.exe' or Name='pythonw.exe'" | Where-Object { $_.CommandLine -match 'eoc_server\.py|sim_server\.py' -and $_.CommandLine -notmatch 'emcomm-(nosim|walk|real)|\\dev\\' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; "stopped " + ($_.CommandLine -replace '.*\\', '') }
  # the console windows that started them (start_eoc_server.bat / start_simulator.bat) keep the folders open
  Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" | Where-Object { $_.CommandLine -match 'start_eoc_server\.bat|start_simulator\.bat' -and $_.CommandLine -like "*C:\$name*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; "closed the window of " + (($_.CommandLine -replace '.*\\', '') -replace '"', '') }
  Start-Sleep 2
}
switch ($Phase) {
 'backup' {
   $bk = "$env:USERPROFILE\emcomm-backup-$Stamp"; New-Item -ItemType Directory -Force $bk | Out-Null
   Stop-App   # the database must not be written while it is copied
   $i = 0
   foreach ($t in $targets) {
     if (-not (Test-Path -LiteralPath $t)) { continue }
     $i++; $dst = Join-Path $bk ("{0:D2}" -f $i)
     if (Test-Path -LiteralPath $t -PathType Container) { robocopy $t $dst /E /COPY:DAT /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null }
     else { New-Item -ItemType Directory -Force $dst | Out-Null; Copy-Item -LiteralPath $t $dst }
     Add-Content (Join-Path $bk 'WHERE-EACH-FOLDER-CAME-FROM.txt') ("{0:D2} = {1}" -f $i, $t)
   }
   $n = (Get-ChildItem $bk -Recurse -File | Measure-Object).Count
   "backup: $bk ($n files)"
 }
 'uninstall' {
   Stop-App
   foreach ($t in $targets) { if (Test-Path -LiteralPath $t) { Remove-Item -LiteralPath $t -Recurse -Force; "removed $t" } }
   $left = @($targets | Where-Object { Test-Path -LiteralPath $_ })
   'left behind: ' + $left.Count
   'Winlink Express still here: ' + (Test-Path 'C:\RMS Express\RMS Express.exe')
 }
 'install' {
   $dir = "$env:USERPROFILE\emcomm-reinstall"; New-Item -ItemType Directory -Force $dir | Out-Null
   $bat = Join-Path $dir 'ChurchEMCOMM_Installer_v1.0.bat'
   Invoke-WebRequest -UseBasicParsing 'https://github.com/travislhilton/church-emcomm-wnlk-forms/releases/download/v1.0/ChurchEMCOMM_Installer_v1.0.bat' -OutFile $bat
   'downloaded: ' + (Get-Item $bat).Length + ' bytes, sha256 ' + (Get-FileHash $bat -Algorithm SHA256).Hash.Substring(0,16)
   $out = "3`n`n`n`n" | cmd /c "`"$bat`"" 2>&1 | Out-String
   Set-Content -Encoding utf8 (Join-Path $dir "install-$Stamp.log") $out
   'Copied lines: ' + ([regex]::Matches($out, 'Copied:')).Count
   ($out -split "`n" | Select-String 'Installation complete|ERROR|WARN|Install location' | ForEach-Object { '  ' + $_.Line.Trim() })
   foreach ($t in "C:\$name", (Join-Path $desk "$name Forms"), (Join-Path $desk "$name EOC Server.lnk"), (Join-Path $desk "$name Simulator.lnk"), (Join-Path $desk "$name EOC Message Center.lnk"), "C:\RMS Express\Global Folders\Templates\$name Forms") { "present: $(Test-Path -LiteralPath $t)  $t" }
 }
 'start' {
   $p = New-ScheduledTaskPrincipal -UserId (whoami) -LogonType Interactive
   foreach ($s in "$name EOC Server", "$name Simulator") {
     $lnk = Join-Path $desk "$s.lnk"
     if (-not (Test-Path -LiteralPath $lnk)) { continue }
     $tn = 'EMCOMM-start-' + ($s -replace '\W', '')
     Register-ScheduledTask -TaskName $tn -Action (New-ScheduledTaskAction -Execute 'cmd.exe' -Argument "/c start `"`" `"$lnk`"") -Principal $p -Force | Out-Null
     Start-ScheduledTask -TaskName $tn; Start-Sleep 6; Unregister-ScheduledTask -TaskName $tn -Confirm:$false
     "started from the Desktop shortcut: $s"
   }
   Start-Sleep 6
   foreach ($u in 'http://127.0.0.1:8080/api/status', 'http://127.0.0.1:8090/api/info') { try { $c = (Invoke-WebRequest -UseBasicParsing $u -TimeoutSec 8).Content; "$u -> " + $c.Substring(0, [Math]::Min(110, $c.Length)) } catch { "$u FAIL $($_.Exception.Message)" } }
 }
}
