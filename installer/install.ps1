#Requires -Version 5.1
<#
.SYNOPSIS
    Church of Jesus Christ EMCOMM (Emergency Communications) -- Installer
.DESCRIPTION
    Installs the correct package for each role:
      [1] Field Volunteer (non-HAM, no amateur radio license) -- browser Worker Forms + Quick Reference Cards
      [2] HAM Field Operator        -- browser Worker Forms + Winlink Templates + Quick Reference Cards
      [3] EOC Operator (Satellite, Stake or Council / Area EOC) -- EOC (Emergency Operations Center) Message Center + Winlink Templates
    Self-contained -- all files are copied from this repo.
#>

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot

# Keep the window open on any unhandled error so the user can read it
trap {
    Write-Host ""
    Write-Host "  ----------------------------------------" -ForegroundColor DarkGray
    Write-Host "  ERROR: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Installation did not complete." -ForegroundColor Yellow
    Write-Host "  Screenshot this window and contact your EMCOMM coordinator." -ForegroundColor Yellow
    Write-Host ""
    if (-not $env:CHURCH_EMCOMM_BAT) { Read-Host "  Press Enter to close" }
    exit 1
}

# -- Unblock check ------------------------------------------------------------
# If this script was downloaded from the internet and not unblocked, warn early
try {
    $null = Get-Item $PSCommandPath -Stream Zone.Identifier -ErrorAction Stop
    Write-Host ""
    Write-Host "  NOTE: This file was downloaded from the internet." -ForegroundColor Yellow
    Write-Host "  If the installer fails with a security error, close this window," -ForegroundColor Yellow
    Write-Host "  right-click the file, choose Properties, check Unblock, then run again." -ForegroundColor Yellow
} catch {}

# -- Banner -------------------------------------------------------------------
Clear-Host
Write-Host ""
Write-Host "  THE CHURCH OF JESUS CHRIST" -ForegroundColor White
Write-Host "  of Latter-day Saints" -ForegroundColor White
Write-Host ""
Write-Host "  Church of Jesus Christ EMCOMM" -ForegroundColor Cyan
Write-Host "  Installer v1.0" -ForegroundColor Gray
Write-Host ("  " + ("-" * 50)) -ForegroundColor DarkGray
Write-Host ""

# -- Helper functions ---------------------------------------------------------
function Write-Step { param([string]$msg) Write-Host "  --> $msg" -ForegroundColor Cyan }
function Write-OK   { param([string]$msg) Write-Host "  OK  $msg" -ForegroundColor Green }
function Write-Warn { param([string]$msg) Write-Host "  !!  $msg" -ForegroundColor Yellow }
function Write-Err  { param([string]$msg) Write-Host "  XX  $msg" -ForegroundColor Red }
function Write-Info { param([string]$msg) Write-Host "    $msg"   -ForegroundColor Gray }

# PRACTICE-SYNC:BEGIN
# Install the practice forms into one folder and retire the ones an earlier release left there. Only the generator's
# own numbered files go; anything else a person put here stays. A private set (its README says so) is left untouched.
function Sync-PracticeForms {
    param([string]$Source, [string]$Dest)
    New-Item -ItemType Directory -Force $Dest | Out-Null
    $readme = Join-Path $Dest 'README.txt'
    if ((Test-Path $readme) -and (Select-String -Path $readme -Pattern 'keep this folder private' -SimpleMatch -Quiet)) {
        Write-Warn "A private practice set is in $Dest : left as it is"
        return -1
    }
    $retired = 0
    foreach ($old in Get-ChildItem $Dest -File) {
        if ($old.Name -match '^Practice( \d+ - |_\d+_)' -and -not (Test-Path -LiteralPath (Join-Path $Source $old.Name))) {
            try { Remove-Item -LiteralPath $old.FullName -Force -ErrorAction Stop; $retired++ }
            catch { Write-Warn "Could not remove an old practice form (is it open?): $($old.Name)" }
        }
    }
    if ($retired) { Write-OK "Retired $retired old practice files from $Dest" }
    $n = 0
    foreach ($pf in Get-ChildItem $Source -File) { Copy-Item -LiteralPath $pf.FullName (Join-Path $Dest $pf.Name) -Force; $n++ }
    return $n
}
# PRACTICE-SYNC:END

function Create-Shortcut {
    param([string]$ShortcutPath, [string]$TargetPath, [string]$Arguments = '', [string]$Description = '',
          [string]$IconLocation = '', [int]$WindowStyle = 0, [string]$WorkingDirectory = '')
    $wsh = New-Object -ComObject WScript.Shell
    $sc  = $wsh.CreateShortcut($ShortcutPath)
    $sc.TargetPath  = $TargetPath
    if ($Arguments)  { $sc.Arguments   = $Arguments  }
    if ($Description){ $sc.Description = $Description}
    if ($IconLocation)     { $sc.IconLocation     = $IconLocation }
    if ($WindowStyle)      { $sc.WindowStyle      = $WindowStyle }        # 7 = minimized
    if ($WorkingDirectory) { $sc.WorkingDirectory = $WorkingDirectory }
    $sc.Save()
}

function Find-Chrome {
    $paths = @(
        (Join-Path $env:PROGRAMFILES       "Google\Chrome\Application\chrome.exe"),
        (Join-Path ${env:PROGRAMFILES(X86)} "Google\Chrome\Application\chrome.exe"),
        (Join-Path $env:LOCALAPPDATA        "Google\Chrome\Application\chrome.exe")
    )
    foreach ($p in $paths) { if (Test-Path $p) { return $p } }
    try {
        $reg = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe' -ErrorAction Stop
        if ($reg.'(default)' -and (Test-Path $reg.'(default)')) { return $reg.'(default)' }
    } catch {}
    return $null
}

function Find-Edge {
    $paths = @(
        (Join-Path $env:PROGRAMFILES       "Microsoft\Edge\Application\msedge.exe"),
        (Join-Path ${env:PROGRAMFILES(X86)} "Microsoft\Edge\Application\msedge.exe")
    )
    foreach ($p in $paths) { if (Test-Path $p) { return $p } }
    return $null
}

function Find-Browser {
    $c = Find-Chrome; if ($c) { return $c }
    $e = Find-Edge;   if ($e) { return $e }
    return $null
}

function Find-Winlink {
    $paths = @(
        'C:\RMS Express\RMS Express.exe',
        (Join-Path $env:PROGRAMFILES        "RMS Express\RMS Express.exe"),
        (Join-Path ${env:PROGRAMFILES(X86)} "RMS Express\RMS Express.exe")
    )
    foreach ($p in $paths) { if (Test-Path $p) { return (Split-Path $p) } }
    return $null
}

function Test-PythonExe([string]$exe) {
    # "Python 3.x.y" when this program really runs Python 3.7 or newer, else $null. The Microsoft Store
    # placeholder (WindowsApps\python.exe when Python is not installed) prints "Python was not found" and does
    # not match; running it with --version does not open the Store.
    try {
        $ver = (& $exe --version 2>&1 | Select-Object -First 1 | Out-String).Trim()
        if ($ver -match '^Python (\d+)\.(\d+)') {
            if ([int]$Matches[1] -eq 3 -and [int]$Matches[2] -ge 7) { return $ver }
        }
    } catch {}
    return $null
}

function Find-Python {
    # Returns "Python 3.x.y (path)" if a working Python 3.7+ is found, else $null
    foreach ($cmd in @('py', 'python3', 'python')) {
        foreach ($app in @(Get-Command $cmd -All -CommandType Application -ErrorAction SilentlyContinue)) {
            $ver = Test-PythonExe $app.Source
            if ($ver) { return "$ver ($($app.Source))" }
        }
    }
    # Also check common install locations (Python installed without "Add python.exe to PATH")
    $pyPaths = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python'),
        'C:\Python3',
        (Join-Path $env:PROGRAMFILES 'Python3')
    )
    foreach ($base in $pyPaths) {
        if (-not $base -or -not (Test-Path $base)) { continue }
        foreach ($exe in @(Get-ChildItem $base -Filter 'python.exe' -Recurse -ErrorAction SilentlyContinue)) {
            $ver = Test-PythonExe $exe.FullName
            if ($ver) { return "$ver (found at $($exe.FullName); not on PATH: reinstall with 'Add python.exe to PATH' ticked so the EOC Server finds it)" }
        }
    }
    return $null
}

# -- Check repo files ---------------------------------------------------------
$required = @(
    "templates\disaster-report\Church_of_Jesus_Christ_Disaster_Report_Worker.html",
    "templates\supply-order\Church_of_Jesus_Christ_Supply_Order_Worker.html",
    "templates\work-crew-log\Church_of_Jesus_Christ_Work_Crew_Log_Worker.html",
    "eoc\EOC_Message_Center.html",
    "training\quick-ref-cards.html",
    "templates\disaster-report\Church_of_Jesus_Christ_Disaster_Report_Initial.html",
    "templates\supply-order\Church_of_Jesus_Christ_Supply_Order_Initial.html",
    "templates\work-crew-log\Church_of_Jesus_Christ_Work_Crew_Log.html"
)
$missingFiles = $required | Where-Object { -not (Test-Path (Join-Path $RepoRoot $_)) }
if ($missingFiles) {
    Write-Err "Missing repo files -- run this installer from the Church of Jesus Christ EMCOMM repo:"
    $missingFiles | ForEach-Object { Write-Info "  $_" }
    Write-Host ""
    Write-Host "  Expected repo root: $RepoRoot" -ForegroundColor Yellow
    exit 1
}

# -- Menu ---------------------------------------------------------------------
Write-Host "  Who are you installing for?" -ForegroundColor White
Write-Host ""
Write-Host "  [1]  Field Volunteer  (no HAM license)" -ForegroundColor Cyan
Write-Host "       Browser-based Worker Forms (3 HTML web-page files) + Quick Reference Cards"
Write-Host "       Fill forms on any phone, tablet, or laptop -- no radio needed"
Write-Host ""
Write-Host "  [2]  HAM Field Operator  (licensed Amateur Radio)" -ForegroundColor Cyan
Write-Host "       Browser-based Worker Forms + Winlink Express Templates + Quick Reference Cards"
Write-Host "       Use Winlink to transmit forms when cell and internet are down"
Write-Host ""
Write-Host "  [3]  EOC Operator  (Satellite, Stake or Council / Area EOC -- full install)" -ForegroundColor Cyan
Write-Host "       Browser Worker Forms + Winlink Templates + EOC Message Center + Quick Reference Cards"
Write-Host "       Complete package for any Emergency Operations Center (EOC): a Satellite EOC in a ward"
Write-Host "       building, the Stake Center EOC, or a Council / Area EOC -- same software, rolls up to the EOC above"
Write-Host ""
Write-Host "  [X]  Exit" -ForegroundColor DarkGray
Write-Host ""

do {
    $choice = Read-Host "  Enter choice [1/2/3/X]"
    if ($null -eq $choice) { Write-Host "  No input -- cancelled." -ForegroundColor Gray; exit 0 }
    $choice = $choice.Trim()
} while ($choice -notmatch '^[123Xx]$')

if ($choice -match '^[Xx]$') { Write-Host "  Cancelled." -ForegroundColor Gray; exit 0 }

$installWorker  = $choice -in @('1','2','3')
$installWinlink = $choice -in @('2','3')
$installEOC     = $choice -eq '3'

# -- Install destination ------------------------------------------------------
$installBase = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Church of Jesus Christ EMCOMM'
Write-Host ""
Write-Host "  Install location: $installBase" -ForegroundColor White
Write-Host ""

# -- Rename from the short-lived name "Church EMCOMM" (installer of 2026-10-31.5) and the old EOC shortcut names --
# Moves Documents and app-data folders (EOC database, backups, Drop Folder, simulator settings and runs),
# removes the old Desktop shortcuts and the old Winlink template folders (this run installs the new ones).
function Move-OldFolder([string]$old, [string]$new) {
    if (-not (Test-Path $old)) { return }
    # a new folder with no files in it (an EOC Server started before this install makes an empty Drop Folder) does not count
    if ((Test-Path $new) -and -not (Get-ChildItem $new -Recurse -File -Force -ErrorAction SilentlyContinue | Select-Object -First 1)) {
        Remove-Item -LiteralPath $new -Recurse -Force -ErrorAction SilentlyContinue
    }
    if (-not (Test-Path $new)) {
        try { Move-Item -LiteralPath $old -Destination $new -ErrorAction Stop; Write-OK "Renamed: $old -> $new"; return }
        catch { Write-Warn "Could not rename $old (a file is open? close the EOC Server and run the installer again): $($_.Exception.Message)" }
    }
    # both exist (or the move failed): copy what the new folder lacks, keep the old folder for safety
    $null = robocopy $old $new /E /XC /XN /XO /NFL /NDL /NJH /NJS /NP
    Write-Warn "Copied missing files from $old into $new. The old folder was kept; delete it when you have checked."
}
$oldName = 'Church EMCOMM'
Move-OldFolder (Join-Path ([Environment]::GetFolderPath('MyDocuments')) $oldName) $installBase
if ($env:LOCALAPPDATA) { Move-OldFolder (Join-Path $env:LOCALAPPDATA $oldName) (Join-Path $env:LOCALAPPDATA 'Church of Jesus Christ EMCOMM') }
$oldDesk = [Environment]::GetFolderPath('Desktop')
foreach ($n in @("$oldName Forms", "$oldName Quick Reference Cards.lnk", "$oldName Simulator.lnk",
                 "$oldName EOC Message Center.lnk", "$oldName EOC Server.lnk", "$oldName EOC Drop Folder.lnk",
                 'Church of Jesus Christ EOC Message Center.lnk', 'Church of Jesus Christ EOC Server.lnk', 'Church of Jesus Christ EOC Drop Folder.lnk')) {
    $p = Join-Path $oldDesk $n
    if (Test-Path $p) { Remove-Item -LiteralPath $p -Recurse -Force -ErrorAction SilentlyContinue; Write-OK "Removed old shortcut: $n" }
}
foreach ($t in @('C:\RMS Express\Global Folders\Templates', 'C:\Winlink Express\Global Folders\Templates')) {
    foreach ($n in @("$oldName Forms", "$oldName Practice")) {
        $p = Join-Path $t $n
        if (Test-Path $p) { Remove-Item -LiteralPath $p -Recurse -Force -ErrorAction SilentlyContinue; Write-OK "Removed old Winlink template folder: $p" }
    }
}

# -- Check dependencies -------------------------------------------------------
Write-Step "Checking dependencies..."
Write-Host ""

$browser = Find-Browser
if ($browser) {
    Write-OK "Browser found: $(Split-Path $browser -Leaf) at $browser"
} else {
    Write-Warn "No modern browser found (Chrome or Edge)."
    Write-Warn "The forms and EOC require Chrome or Edge to work."
    Write-Info "  Download Chrome: https://www.google.com/chrome"
    Write-Info "  Download Edge:   https://www.microsoft.com/edge"
    Write-Host ""
    $ans = Read-Host "  Open Chrome download page now? (y/n)"
    if ($ans -match '^[Yy]') { Start-Process "https://www.google.com/chrome" }
    Write-Host ""
}

if ($installWinlink) {
    $winlinkDir = Find-Winlink
    if ($winlinkDir) {
        Write-OK "Winlink Express found at: $winlinkDir"
    } else {
        Write-Warn "Winlink Express not found."
        Write-Warn "Winlink templates will be installed to your Documents folder for now."
        Write-Warn "After installing Winlink, copy them to:"
        Write-Info "  C:\RMS Express\Global Folders\Templates\Church of Jesus Christ EMCOMM Forms\"
        Write-Info "  Download Winlink Express: https://winlink.org"
        Write-Host ""
        $ans = Read-Host "  Open Winlink download page now? (y/n)"
        if ($ans -match '^[Yy]') { Start-Process "https://winlink.org" }
        Write-Host ""
    }
}

if ($installEOC) {
    $pythonVer = Find-Python
    if ($pythonVer) {
        Write-OK "Python found: $pythonVer"
    } else {
        Write-Warn "Python 3 not found (a 'python' that only points to the Microsoft Store does not count)."
        Write-Warn "Python is required for the EOC network server (multi-operator mode) and the drill simulator."
        Write-Warn "The EOC standalone mode still works without Python."
        Write-Host ""
        Write-Host "  Install Python 3 now, before the EOC laptop is needed (free, no admin rights needed):" -ForegroundColor White
        Write-Info "  1. Download the Windows installer from https://www.python.org/downloads/"
        Write-Info "  2. Run it and tick 'Add python.exe to PATH' on the first screen"
        Write-Info "  3. Keep that Python installer on the EOC USB kit next to this installer:"
        Write-Info "     in a disaster there may be no internet to download it."
        Write-Host ""
        $ans = Read-Host "  Open Python download page now? (y/n)"
        if ($ans -match '^[Yy]') { Start-Process "https://www.python.org/downloads/" }
        Write-Host ""
    }
}

# -- Create install directories -----------------------------------------------
Write-Step "Creating directories..."

$dirsToCreate = @($installBase)
if ($installWorker) { $dirsToCreate += Join-Path $installBase 'Field Worker Forms' }
if ($installEOC)    { $dirsToCreate += Join-Path $installBase 'EOC Message Center'  }
if ($installEOC)    { $dirsToCreate += Join-Path $installBase 'EOC Drop Folder'     }

foreach ($d in $dirsToCreate) {
    if (-not (Test-Path $d)) {
        New-Item -ItemType Directory -Force $d | Out-Null
        Write-Info "Created: $d"
    } else {
        Write-Info "Exists:  $d"
    }
}

# -- Read-me and the PACE plan (every role) -------------------------------------
# README.md (what the system is) and PACE_PLAN.md (Primary, Alternate, Contingency, Emergency: which path a report
# takes when cellular or internet is down) in the top folder, readable with no internet.
foreach ($doc in @(@('README.md', 'README.md'), @('docs\PACE_PLAN.md', 'PACE_PLAN.md'), @('LICENSE', 'LICENSE'))) {
    $src = Join-Path $RepoRoot $doc[0]
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $installBase $doc[1]) -Force
        Write-OK "Copied: $($doc[1])"
    }
}

# -- Install Field Worker package ---------------------------------------------
if ($installWorker) {
    Write-Host ""
    Write-Step "Installing Field Worker forms..."

    $workerDest = Join-Path $installBase 'Field Worker Forms'

    $workerFiles = @{
        "templates\disaster-report\Church_of_Jesus_Christ_Disaster_Report_Worker.html" = "Church_of_Jesus_Christ_Disaster_Report_Worker.html"
        "templates\supply-order\Church_of_Jesus_Christ_Supply_Order_Worker.html"        = "Church_of_Jesus_Christ_Supply_Order_Worker.html"
        "templates\work-crew-log\Church_of_Jesus_Christ_Work_Crew_Log_Worker.html"      = "Church_of_Jesus_Christ_Work_Crew_Log_Worker.html"
        "training\quick-ref-cards.html"                                                 = "Quick_Reference_Cards.html"
    }

    foreach ($entry in $workerFiles.GetEnumerator()) {
        $src  = Join-Path $RepoRoot $entry.Key
        $dest = Join-Path $workerDest $entry.Value
        Copy-Item $src $dest -Force
        Write-OK "Copied: $($entry.Value)"
    }

    # Printable Quick Reference Card PDFs (Letter, double-sided) -- optional in older packages
    $pdfSrcDir  = Join-Path $RepoRoot 'training\pdf'
    $pdfDestDir = Join-Path $workerDest 'Quick Reference Cards (PDF)'
    $pdfs = @()
    if (Test-Path $pdfSrcDir) { $pdfs = @(Get-ChildItem -Path $pdfSrcDir -Filter 'Quick_Reference_Card*.pdf' -File -ErrorAction SilentlyContinue) }
    if ($pdfs.Count -gt 0) {
        if (-not (Test-Path $pdfDestDir)) { New-Item -ItemType Directory -Force $pdfDestDir | Out-Null }
        foreach ($p in $pdfs) {
            # a card open in a PDF viewer is locked; keep that copy and go on rather than stop the install
            try {
                Copy-Item $p.FullName (Join-Path $pdfDestDir $p.Name) -Force -ErrorAction Stop
                Write-OK "Copied: Quick Reference Cards (PDF)\$($p.Name)"
            } catch {
                Write-Warn "Kept the existing $($p.Name): it is open in another program. Close it and run the installer again to update it."
            }
        }
    }

    # Desktop shortcut folder
    $desktopPath = [Environment]::GetFolderPath('Desktop')
    $shortcutDir  = Join-Path $desktopPath 'Church of Jesus Christ EMCOMM Forms'
    if (-not (Test-Path $shortcutDir)) {
        New-Item -ItemType Directory -Force $shortcutDir | Out-Null
        Write-Info "Created desktop folder: Church of Jesus Christ EMCOMM Forms"
    }

    $shortcuts = @(
        @{ Name='Disaster Report Form';  File='Church_of_Jesus_Christ_Disaster_Report_Worker.html' },
        @{ Name='Supply Order Form';     File='Church_of_Jesus_Christ_Supply_Order_Worker.html'    },
        @{ Name='Work Crew Log Form';    File='Church_of_Jesus_Christ_Work_Crew_Log_Worker.html'   },
        @{ Name='Quick Reference Cards'; File='Quick_Reference_Cards.html'                         }
    )

    foreach ($s in $shortcuts) {
        $htmlPath = Join-Path $workerDest $s.File
        $lnkPath  = Join-Path $shortcutDir ($s.Name + '.lnk')

        if ($browser) {
            Create-Shortcut -ShortcutPath $lnkPath `
                            -TargetPath   $browser `
                            -Arguments    "`"$htmlPath`"" `
                            -Description  $s.Name
        } else {
            $wsh = New-Object -ComObject WScript.Shell
            $sc  = $wsh.CreateShortcut($lnkPath)
            $sc.TargetPath  = $htmlPath
            $sc.Description = $s.Name
            $sc.Save()
        }
        Write-OK "Shortcut: $($s.Name)"
    }

    if ($pdfs.Count -gt 0) {
        Create-Shortcut -ShortcutPath (Join-Path $shortcutDir 'Quick Reference Cards (PDF).lnk') `
                        -TargetPath   $pdfDestDir `
                        -Description  'Printable Quick Reference Cards -- Letter, double-sided, one PDF per role'
        Write-OK "Shortcut: Quick Reference Cards (PDF)"
        # and one straight on the desktop: the cards are the first thing a new volunteer looks for
        Create-Shortcut -ShortcutPath (Join-Path $desktopPath 'Church of Jesus Christ EMCOMM Quick Reference Cards.lnk') `
                        -TargetPath   $pdfDestDir `
                        -Description  'Printable Quick Reference Cards -- one PDF per role, print double-sided'
        Write-OK "Shortcut: Church of Jesus Christ EMCOMM Quick Reference Cards (Desktop)"
    }
}

# -- Install EOC package ------------------------------------------------------
if ($installEOC) {
    Write-Host ""
    Write-Step "Installing EOC Message Center..."

    $eocDest = Join-Path $installBase 'EOC Message Center'
    $eocSrc  = Join-Path $RepoRoot 'eoc\EOC_Message_Center.html'
    $eocFile = Join-Path $eocDest 'EOC_Message_Center.html'

    Copy-Item $eocSrc $eocFile -Force
    Write-OK "Copied: EOC_Message_Center.html"

    # Wall display (served by the server at /wall) -- optional in older packages
    $wallSrc = Join-Path $RepoRoot 'eoc\EOC_Wall_Display.html'
    if (Test-Path $wallSrc) {
        Copy-Item $wallSrc (Join-Path $eocDest 'EOC_Wall_Display.html') -Force
        Write-OK "Copied: EOC_Wall_Display.html  (open http://<server-ip>:8080/wall on the TV)"
    }
    # Phone page (served at /m and /receive): new reports and Send to EOC for phones on the EOC Wi-Fi
    $phoneSrc = Join-Path $RepoRoot 'eoc\EOC_Phone.html'
    if (Test-Path $phoneSrc) {
        Copy-Item $phoneSrc (Join-Path $eocDest 'EOC_Phone.html') -Force
        Write-OK "Copied: EOC_Phone.html  (phones open http://<server-ip>:8080/m)"
    }

    # Copy EOC server files if present
    $serverPy  = Join-Path $RepoRoot 'eoc\eoc_server.py'
    $serverBat = Join-Path $RepoRoot 'eoc\start_eoc_server.bat'
    if (Test-Path $serverPy) {
        Copy-Item $serverPy  (Join-Path $eocDest 'eoc_server.py')         -Force
        Write-OK "Copied: eoc_server.py"
    }
    if (Test-Path $serverBat) {
        Copy-Item $serverBat (Join-Path $eocDest 'start_eoc_server.bat')  -Force
        Write-OK "Copied: start_eoc_server.bat"
    }
    $serverCmd = Join-Path $RepoRoot 'eoc\start_eoc_server.command'   # macOS launcher, carried along for a Mac EOC laptop
    if (Test-Path $serverCmd) { Copy-Item $serverCmd (Join-Path $eocDest 'start_eoc_server.command') -Force }

    # EMCOMM simulator (drills): installed beside the server so it can read eoc_server.py
    $simSrc = Join-Path $RepoRoot 'simulation'
    if (Test-Path (Join-Path $simSrc 'sim_server.py')) {
        $simDest = Join-Path $eocDest 'simulation'
        if (-not (Test-Path (Join-Path $simDest 'scenarios'))) { New-Item -ItemType Directory -Force (Join-Path $simDest 'scenarios') | Out-Null }
        foreach ($n in @('sim_server.py', 'engine.py', 'orgpack.py', 'privacy.py', 'drillconfig.py', 'community.py', 'scenario_check.py', 'index.html', 'README.md', 'start_simulator.bat', 'start_simulator.command')) {
            $p = Join-Path $simSrc $n
            if (Test-Path $p) { Copy-Item $p (Join-Path $simDest $n) -Force }
        }
        # built-in scenarios: replace the folder's contents, so a scenario removed from the release does not linger
        Get-ChildItem (Join-Path $simDest 'scenarios') -Filter '*.json' -File | Remove-Item -Force
        Get-ChildItem (Join-Path $simSrc 'scenarios') -Filter '*.json' | ForEach-Object { Copy-Item $_.FullName (Join-Path $simDest ('scenarios\' + $_.Name)) -Force }
        # the invented example community (Juniper Plains Area): an export folder every part of the system can load
        $exSrc = Join-Path $simSrc 'example'
        if (Test-Path $exSrc) {
            $exBase = (Get-Item $exSrc).FullName      # the long form: a short TEMP path (TRAVIS~1) would cut the names wrong
            foreach ($ef in Get-ChildItem $exSrc -Recurse -File) {
                $rel = $ef.FullName.Substring($exBase.Length).TrimStart('\')
                # same filter as the build scripts: no Python cache, no drill runs or local role choices (git-ignored)
                if ($rel -like '*__pycache__*' -or ('\' + $rel) -match '\\simulation\\(runs|local-roles\.json)') { continue }
                $t = Join-Path (Join-Path $simDest 'example') $rel
                $td = Split-Path $t -Parent
                if (-not (Test-Path $td)) { New-Item -ItemType Directory -Force $td | Out-Null }
                Copy-Item $ef.FullName $t -Force
            }
        }
        Write-OK "Copied: simulation\ (drill simulator: sim_server.py, scenarios, example community)"
    }

    # A copy of the volunteer web app (the GitHub Pages portal: forms\, sw.js, the three Worker forms, the volunteer
    # card), laid out as the site is, so it can be put on another https web host if GitHub Pages cannot be reached.
    # The EOC Server does not serve it: phones on the EOC Wi-Fi use http://<server-ip>:8080/m and /forms/dr, /so, /wcl.
    $portalSrc = Join-Path $RepoRoot 'forms'
    if (Test-Path (Join-Path $portalSrc 'index.html')) {
        $portalDest = Join-Path $installBase 'Web App (portal copy)'
        if (Test-Path $portalDest) { Remove-Item -LiteralPath $portalDest -Recurse -Force }   # ours: replaced whole, nothing stale
        $pBase = (Get-Item $portalSrc).FullName.TrimEnd('\')      # the long form, as for the example community above
        $portalFiles = @(Get-ChildItem $portalSrc -Recurse -File | ForEach-Object { 'forms\' + $_.FullName.Substring($pBase.Length).TrimStart('\') })
        $portalFiles += @('sw.js', 'training\quick-ref-cards.html', 'training\pdf\Quick_Reference_Card_1_Helping_Hands_Volunteer.pdf',
                          'templates\disaster-report\Church_of_Jesus_Christ_Disaster_Report_Worker.html',
                          'templates\supply-order\Church_of_Jesus_Christ_Supply_Order_Worker.html',
                          'templates\work-crew-log\Church_of_Jesus_Christ_Work_Crew_Log_Worker.html')
        $np = 0
        foreach ($rel in $portalFiles) {
            $src = Join-Path $RepoRoot $rel
            if (-not (Test-Path $src)) { continue }
            $t = Join-Path $portalDest $rel
            $td = Split-Path $t -Parent
            if (-not (Test-Path $td)) { New-Item -ItemType Directory -Force $td | Out-Null }
            Copy-Item $src $t -Force; $np++
        }
        Write-OK "Copied: Web App (portal copy)\ ($np files: the volunteer web app as GitHub Pages serves it)"
    }

    # Desktop shortcut for the EOC Message Center: a small launcher that opens the EOC Server's page when the
    # server runs on this laptop (records shared with every operator), and the standalone file only when it does not
    # (records kept in this browser alone). Opening the file while the server runs would split the records.
    $desktopPath = [Environment]::GetFolderPath('Desktop')
    $lnkPath = Join-Path $desktopPath 'Church of Jesus Christ EMCOMM EOC Message Center.lnk'
    $launcher = Join-Path $eocDest 'Open EOC Message Center.cmd'
    $launcherText = @(
        '@echo off',
        'rem Church of Jesus Christ EMCOMM -- opens the EOC (Emergency Operations Center) Message Center.',
        'rem EOC Server running on this laptop: its page, http://localhost:8080 (records shared with every operator).',
        'rem Not running: the standalone file next to this launcher (records kept in this browser only).',
        'set "EOC_HTML=%~dp0EOC_Message_Center.html"',
        ('set "EOC_BROWSER=' + $(if ($browser) { $browser } else { '' }) + '"'),
        'powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "$p = if ($env:EOC_PORT) { $env:EOC_PORT } else { ''8080'' }; $t = $env:EOC_HTML; try { $r = [Net.WebRequest]::Create(''http://127.0.0.1:'' + $p + ''/api/status''); $r.Timeout = 2000; $r.Proxy = $null; $r.GetResponse().Close(); $t = ''http://localhost:'' + $p + ''/'' } catch {}; if ($env:EOC_BROWSER -and (Test-Path -LiteralPath $env:EOC_BROWSER)) { Start-Process -FilePath $env:EOC_BROWSER -ArgumentList ([char]34 + $t + [char]34) } else { Start-Process $t }"'
    ) -join "`r`n"
    [System.IO.File]::WriteAllText($launcher, $launcherText + "`r`n", (New-Object System.Text.UTF8Encoding($false)))
    Create-Shortcut -ShortcutPath     $lnkPath `
                    -TargetPath       $launcher `
                    -WorkingDirectory $eocDest `
                    -WindowStyle      7 `
                    -IconLocation     $(if ($browser) { "$browser,0" } else { '' }) `
                    -Description      'Church of Jesus Christ EMCOMM EOC Message Center (the EOC Server page when the server runs here, else standalone)'
    Write-OK "Shortcut: Church of Jesus Christ EMCOMM EOC Message Center (Desktop; opens the EOC Server page when the server runs)"

    # Desktop shortcut for EOC network server
    if (Test-Path (Join-Path $eocDest 'start_eoc_server.bat')) {
        $serverLnk = Join-Path $desktopPath 'Church of Jesus Christ EMCOMM EOC Server.lnk'
        Create-Shortcut -ShortcutPath $serverLnk `
                        -TargetPath   (Join-Path $eocDest 'start_eoc_server.bat') `
                        -Description  "Church of Jesus Christ EMCOMM EOC Network Server"
        Write-OK "Shortcut: Church of Jesus Christ EMCOMM EOC Server (Desktop)"
    }

    # Desktop shortcut for the drill simulator
    if (Test-Path (Join-Path $eocDest 'simulation\start_simulator.bat')) {
        $simLnk = Join-Path $desktopPath 'Church of Jesus Christ EMCOMM Simulator.lnk'
        Create-Shortcut -ShortcutPath $simLnk `
                        -TargetPath   (Join-Path $eocDest 'simulation\start_simulator.bat') `
                        -Description  "Church of Jesus Christ EMCOMM drill simulator (port 8090)"
        Write-OK "Shortcut: Church of Jesus Christ EMCOMM Simulator (Desktop)"
    }

    # Desktop shortcut to the EOC Drop Folder
    $dropFolderPath = Join-Path $installBase 'EOC Drop Folder'
    $dropLnk = Join-Path $desktopPath 'Church of Jesus Christ EMCOMM EOC Drop Folder.lnk'
    $wshDrop = New-Object -ComObject WScript.Shell
    $scDrop = $wshDrop.CreateShortcut($dropLnk)
    $scDrop.TargetPath = $dropFolderPath
    $scDrop.Description = 'Church of Jesus Christ EMCOMM EOC -- Drop internet-submitted form files here to auto-ingest'
    $scDrop.Save()
    Write-OK "Shortcut: Church of Jesus Christ EMCOMM EOC Drop Folder (Desktop)"
}

# -- Install Winlink templates (HAM Field Operator and EOC) -------------------
if ($installWinlink) {
    Write-Host ""
    Write-Step "Installing Winlink templates..."

    $winlinkTemplatePaths = @('C:\RMS Express\Global Folders\Templates')
    if ($winlinkDir) {
        $winlinkTemplatePaths = @((Join-Path $winlinkDir 'Global Folders\Templates')) + $winlinkTemplatePaths
    }

    $templateDest = $null
    foreach ($tp in $winlinkTemplatePaths) {
        $parent = Split-Path $tp -Parent
        if (Test-Path $parent) { $templateDest = $tp; break }
    }

    if (-not $templateDest) {
        $fallbackBase = if ($installEOC) { Join-Path $installBase 'EOC Message Center' } else { $installBase }
        $templateDest = Join-Path $fallbackBase 'Winlink Templates'
        Write-Warn "Winlink path not found -- templates saved to:"
        Write-Info "  $templateDest"
        Write-Warn "After installing Winlink, copy that folder to:"
        Write-Info "  C:\RMS Express\Global Folders\Templates\"
    }

    $churchTemplateDest = Join-Path $templateDest 'Church of Jesus Christ EMCOMM Forms'
    New-Item -ItemType Directory -Force $churchTemplateDest | Out-Null

    # Winlink's Select Template dialog lists only the .txt definitions; each one names its
    # entry form and its viewer (the viewer is what Winlink opens for a RECEIVED message)
    $templateFiles = @{
        "templates\disaster-report\Church_of_Jesus_Christ_Disaster_Report_Initial.html" = "Church_of_Jesus_Christ_Disaster_Report_Initial.html"
        "templates\disaster-report\Church_of_Jesus_Christ_Disaster_Report_Viewer.html"  = "Church_of_Jesus_Christ_Disaster_Report_Viewer.html"
        "templates\disaster-report\Church of Jesus Christ Disaster Report.txt"           = "Church of Jesus Christ Disaster Report.txt"
        "templates\supply-order\Church_of_Jesus_Christ_Supply_Order_Initial.html"        = "Church_of_Jesus_Christ_Supply_Order_Initial.html"
        "templates\supply-order\Church_of_Jesus_Christ_Supply_Order_Viewer.html"         = "Church_of_Jesus_Christ_Supply_Order_Viewer.html"
        "templates\supply-order\Church of Jesus Christ Supply Order.txt"                 = "Church of Jesus Christ Supply Order.txt"
        "templates\work-crew-log\Church_of_Jesus_Christ_Work_Crew_Log.html"              = "Church_of_Jesus_Christ_Work_Crew_Log.html"
        "templates\work-crew-log\Church_of_Jesus_Christ_Work_Crew_Log_Viewer.html"       = "Church_of_Jesus_Christ_Work_Crew_Log_Viewer.html"
        "templates\work-crew-log\Church of Jesus Christ Work Crew Log.txt"               = "Church of Jesus Christ Work Crew Log.txt"
    }

    foreach ($entry in $templateFiles.GetEnumerator()) {
        $src  = Join-Path $RepoRoot $entry.Key
        $dest = Join-Path $churchTemplateDest $entry.Value
        Copy-Item $src $dest -Force
        Write-OK "Template: $($entry.Value)"
    }

    # Practice forms: pre-filled copies of the entry forms (THIS IS AN EXERCISE ticked) from the
    # simulator scenario, each with its own .txt definition, so a HAM can send a realistic
    # exercise message in a minute. Their viewers are copied beside them.
    $practiceSrc = Join-Path $RepoRoot 'training\practice-forms'
    if (Test-Path $practiceSrc) {
        $practiceDest = Join-Path $templateDest 'Church of Jesus Christ EMCOMM Practice'
        $n = Sync-PracticeForms $practiceSrc $practiceDest
        if ($n -ge 0) { Write-OK "Practice forms: $n files (pre-filled, THIS IS AN EXERCISE) -> Church of Jesus Christ EMCOMM Practice\" }

        # A training copy in the EMCOMM folder, so trainers find the practice forms (and their
        # README) without digging into Winlink's folders, and can copy them to another station.
        $trainingDest = Join-Path $installBase 'Training\Winlink Practice Forms'
        $n = Sync-PracticeForms $practiceSrc $trainingDest
        if ($n -ge 0) { Write-OK "Practice forms: training copy -> $trainingDest" }
        $trainingLnkDir = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Church of Jesus Christ EMCOMM Forms'
        if (Test-Path $trainingLnkDir) {
            Create-Shortcut -ShortcutPath (Join-Path $trainingLnkDir 'Training - Winlink Practice Forms.lnk') `
                            -TargetPath   $trainingDest `
                            -Description  'Pre-filled Winlink practice forms (THIS IS AN EXERCISE) and how to use them'
            Write-OK "Shortcut: Training - Winlink Practice Forms"
        }
    }

    # Scenario training sets (training\scenario-samples\<code>\, for example CCD-1 = Copper Creek Dam):
    # filled Church forms from one stake's wards, plus ICS 213RR resource requests between the stake EOC and a
    # city EOC. The ICS forms are built here from this station's own standard Winlink ICS213RR form (the
    # Winlink form is never copied into the repository): the pre-filled values are added as a script.
    $sampleRoot = Join-Path $RepoRoot 'training\scenario-samples'
    if (Test-Path $sampleRoot) {
        $stdIcs = $null
        foreach ($cand in @($winlinkDir, 'C:\RMS Express')) {
            if (-not $cand) { continue }
            $p = Join-Path $cand 'Standard Templates\ICS USA Forms'
            if (Test-Path (Join-Path $p 'ICS213RR_Initial.html')) { $stdIcs = $p; break }
        }
        $utf8 = New-Object System.Text.UTF8Encoding($false)
        # retire the public sets an earlier release installed and this one no longer ships; a private build that
        # someone copied in from a participant package says PRIVATE BUILD in its README and is never touched
        $shipped = @(Get-ChildItem $sampleRoot -Directory | ForEach-Object { $_.Name })
        foreach ($pair in @(@($templateDest, 'Church of Jesus Christ EMCOMM Training '), @((Join-Path $installBase 'Training'), 'Winlink Training '))) {
            if (-not (Test-Path $pair[0])) { continue }
            foreach ($old in Get-ChildItem $pair[0] -Directory -Filter ($pair[1] + '*')) {
                $code = $old.Name.Substring($pair[1].Length)
                if ($shipped -contains $code) { continue }
                $rd = Join-Path $old.FullName 'README.txt'
                $ours = (Test-Path $rd) -and ((Get-Content $rd -TotalCount 1) -like 'Church of Jesus Christ EMCOMM Winlink training set*')
                $private = (Test-Path $rd) -and (Select-String -Path $rd -Pattern 'PRIVATE BUILD' -SimpleMatch -Quiet)
                if ($ours -and -not $private) {
                    Remove-Item -Recurse -Force $old.FullName
                    Write-OK "Retired training set $code (no longer in this release): $($old.FullName)"
                }
            }
        }
        foreach ($set in Get-ChildItem $sampleRoot -Directory) {
            $code = $set.Name
            $dests = @((Join-Path $templateDest "Church of Jesus Christ EMCOMM Training $code"),
                       (Join-Path $installBase "Training\Winlink Training $code"))
            foreach ($d in $dests) {
                # our own folder: empty it first, so a renumbered set leaves no stale message behind
                if (Test-Path $d) { Get-ChildItem $d -File | Remove-Item -Force }
                New-Item -ItemType Directory -Force $d | Out-Null
                $nc = 0
                foreach ($sf in Get-ChildItem $set.FullName -File) {
                    if ($sf.Extension -eq '.json' -and $d -eq $dests[0]) { continue }   # data for this step, not a template
                    Copy-Item $sf.FullName (Join-Path $d $sf.Name) -Force; $nc++
                }
                $ni = 0
                $jf = Join-Path $set.FullName 'ICS213RR samples.json'
                if ($stdIcs -and (Test-Path $jf)) {
                    $init = [System.IO.File]::ReadAllText((Join-Path $stdIcs 'ICS213RR_Initial.html'))
                    $tdef = [System.IO.File]::ReadAllText((Join-Path $stdIcs 'ICS213RR Resource Request Message.txt'))
                    Copy-Item (Join-Path $stdIcs 'ICS213RR_Viewer.html') (Join-Path $d 'ICS213RR_Viewer.html') -Force
                    $data = [System.IO.File]::ReadAllText($jf, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
                    foreach ($s in $data.samples) {
                        $i = $init.LastIndexOf('</body>')
                        if ($i -lt 0) { continue }
                        [System.IO.File]::WriteAllText((Join-Path $d $s.html), $init.Substring(0, $i) + $s.script + $init.Substring($i), $utf8)
                        $t = ([regex]'^\s*Form:\s*[^,\r\n]+,').Replace($tdef, ('Form: ' + $s.html + ','), 1)
                        [System.IO.File]::WriteAllText((Join-Path $d ($s.name + '.txt')), $t, $utf8)
                        $ni++
                    }
                }
                Write-OK "Training set ${code}: $nc files + $ni ICS 213RR forms -> $d"
            }
            if (-not $stdIcs) { Write-Warn "Training set ${code}: Winlink's standard ICS213RR form not found; the ICS 213RR requests are in the README to send by hand." }
        }
    }

    Write-Host ""
    Write-Info "Template path: $churchTemplateDest"
}

# -- Summary ------------------------------------------------------------------
Write-Host ""
Write-Host ("  " + ("-" * 50)) -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Info "  Read first: $(Join-Path $installBase 'README.md') and PACE_PLAN.md (which path a report takes when the network is down)"
Write-Host ""

if ($installWorker) {
    Write-Host "  Forms installed:" -ForegroundColor Cyan
    Write-Info "  Files:     $(Join-Path $installBase 'Field Worker Forms')"
    Write-Info "  Shortcuts: Desktop\Church of Jesus Christ EMCOMM Forms\"
    Write-Info "  Cards:     Desktop\Church of Jesus Christ EMCOMM Quick Reference Cards  (one PDF per role)"
    Write-Host ""
}

if ($installWinlink) {
    Write-Host "  Winlink templates:" -ForegroundColor Cyan
    if ($winlinkDir) {
        Write-Info "  Templates: $winlinkDir\Global Folders\Templates\Church of Jesus Christ EMCOMM Forms\"
        Write-Info "  Practice:  $winlinkDir\Global Folders\Templates\Church of Jesus Christ EMCOMM Practice\  (pre-filled exercise forms)"
        Write-Info "  Training:  $(Join-Path $installBase 'Training\Winlink Practice Forms')  (same practice forms + README)"
    } else {
        Write-Info "  Templates: $(Join-Path $installBase 'Winlink Templates\Church of Jesus Christ EMCOMM Forms')"
        Write-Info "  (Move to C:\RMS Express\Global Folders\Templates\ after installing Winlink)"
        Write-Info "  Training:  $(Join-Path $installBase 'Training\Winlink Practice Forms')  (practice forms + README)"
    }
    Write-Host ""
}

if ($installEOC) {
    Write-Host "  EOC Message Center:" -ForegroundColor Cyan
    Write-Info "  EOC file:  $(Join-Path $installBase 'EOC Message Center\EOC_Message_Center.html')"
    Write-Info "  Shortcut:  Desktop\Church of Jesus Christ EMCOMM EOC Message Center.lnk"
    Write-Info "             (opens the EOC Server page when the server runs on this laptop, else the standalone file)"
    Write-Host ""
    Write-Info "  Web app:   $(Join-Path $installBase 'Web App (portal copy)')  (the GitHub Pages portal, to host on another https site if needed)"
    Write-Host ""
    Write-Host "  EOC Network Server (multi-operator WiFi):" -ForegroundColor Cyan
    Write-Info "  Server:    $(Join-Path $installBase 'EOC Message Center\start_eoc_server.bat')"
    Write-Info "  Shortcut:  Desktop\Church of Jesus Christ EMCOMM EOC Server.lnk"
    Write-Host ""
    Write-Host "  Church of Jesus Christ EMCOMM Simulator (drills; one per EOC laptop, needs the EOC Server running with a DRILL event):" -ForegroundColor Cyan
    Write-Info "  Start:     $(Join-Path $installBase 'EOC Message Center\simulation\start_simulator.bat')  ->  http://<this-laptop>:8090"
    Write-Info "  Shortcut:  Desktop\Church of Jesus Christ EMCOMM Simulator.lnk"
    Write-Info "  Load the organization pack (Church directory export) on its Setup tab; it stays on this laptop."
    Write-Host ""
    Write-Host "  Internet Drop Folder (reports by email, text, AirDrop, USB; roll-up .json files from a lower EOC):" -ForegroundColor Cyan
    Write-Info "  Folder:    $(Join-Path $installBase 'EOC Drop Folder')"
    Write-Info "  Shortcut:  Desktop\Church of Jesus Christ EMCOMM EOC Drop Folder.lnk"
    Write-Info "  Drop any Worker Form .txt file, or a Roll-up .json from a Satellite/Stake EOC, here -- ingested within 10 seconds."
    Write-Info "  Processed files move to: EOC Drop Folder\Ingested\"
    if ($pythonVer) {
        Write-OK "Python ready: $pythonVer"
    } else {
        Write-Warn "Python 3 not installed -- networked mode will not work until Python is installed."
        Write-Info "  Install it from https://www.python.org/downloads/ now and keep the Python installer on the USB kit"
    }
    Write-Host ""
    Write-Host "  Quick start for EOC operators:" -ForegroundColor White
    Write-Info "  Single operator (standalone, no EOC Server running):"
    Write-Info "    Double-click the EOC Message Center shortcut, drag .mime files in"
    Write-Info "  Multiple operators on same WiFi (networked mode, recommended):"
    Write-Info "    1. One laptop runs the EOC Server shortcut"
    Write-Info "    2. All operators open http://<server-ip>:8080 in any browser"
    Write-Info "    3. Church form messages from Winlink auto-ingest within 10 seconds"
    Write-Info "    4. Everyone sees new messages in real time"
    Write-Host ""
    Write-Host "  Receiving internet-submitted reports (email, text, AirDrop, USB):" -ForegroundColor White
    Write-Info "    Volunteer fills form -> saves .txt file -> texts/emails/AirDrops it to you"
    Write-Info "    You save the .txt file to the EOC Drop Folder shortcut on your Desktop"
    Write-Info "    EOC server picks it up automatically within 10 seconds"
    Write-Host ""
}

if ($installWorker -and $installWinlink) {
    Write-Host "  Quick start for HAM field operators:" -ForegroundColor White
    Write-Info "  Option A -- Winlink Express on a laptop:"
    Write-Info "    Open Winlink, select a Church template, fill and transmit"
    Write-Info "  Option B -- phone or tablet in the field:"
    Write-Info "    Fill a Worker Form in the browser, save the .txt file"
    Write-Info "    Load it into a Winlink template on your laptop and transmit"
    Write-Host ""
} elseif ($installWorker) {
    Write-Host "  Quick start for field volunteers:" -ForegroundColor White
    Write-Info "  1. Double-click a form shortcut on your Desktop"
    Write-Info "  2. Fill out the form and tap Save to My Phone"
    Write-Info "  3. Have internet? Email the saved .txt file to your leader or the Stake EOC"
    Write-Info "     No service? Get it to a HAM operator (USB drive, AirDrop, Nearby Share)"
    Write-Host ""
}

if ($browser) {
    Write-Host "  Browser: $(Split-Path $browser -Leaf)" -ForegroundColor Gray
} else {
    Write-Warn "No browser detected. Install Chrome or Edge before using the forms."
}
Write-Host ""

# Keep window open when run directly (not from install.bat which has its own pause)
if (-not $env:CHURCH_EMCOMM_BAT) {
    Read-Host "  Press Enter to close"
}
