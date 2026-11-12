#!/usr/bin/env python3
"""Build the release files on any development machine (Windows or macOS): standard library only.

    python installer/build-release.py          both files below
    python installer/build-release.py --bat    only the one-file installer
    python installer/build-release.py --zip    only the ZIP

dist/ChurchEMCOMM_Installer_v1.0.bat
    One self-contained installer: every distributed file base64-encoded in 76-character chunks (a PowerShell string
    array, which stays under the ~16K tokenizer line limit) in front of install.ps1. Delivery: email, USB or a file
    server. A batch header avoids the execution-policy block that silently kills a downloaded .ps1.
dist/ChurchEMCOMM_Forms_v1.0.zip
    The same files laid out like the repository, so install.ps1 finds them with no change; recipients extract it and
    double-click installer/install.bat. Its entry names use forward slashes, which macOS and Linux unzip tools need.

The output does not depend on the machine: files come from git's list (never a folder walk, which would pick up
.DS_Store, __pycache__ or a drill's runtime files), in sorted order, and the ZIP's dates are fixed. Windows scripts
always go out with CRLF. A new file in a listed folder must be added with `git add` before a build ships it.

The generated PowerShell is parse-checked when powershell or pwsh is on this machine. Where neither is (a Mac without
pwsh), the build says so: after a change to install.ps1 run the build once on Windows before a release.
"""
import base64
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / 'dist'
VERSION = '1.0'
BAT = DIST / f'ChurchEMCOMM_Installer_v{VERSION}.bat'
ZIP = DIST / f'ChurchEMCOMM_Forms_v{VERSION}.zip'
ZIP_DATE = (2026, 1, 1, 0, 0, 0)        # fixed, so a rebuild of the same files gives the same ZIP on any machine

WINDOWS_SCRIPT = re.compile(r'\.(bat|cmd|ps1)$', re.I)

# Runs under cmd.exe; PowerShell never sees it (the file is extracted to a temporary .ps1 first).
BAT_HEADER = r'''@echo off
title Church of Jesus Christ EMCOMM -- Installer
setlocal enableextensions
set "CHURCH_SRC=%~f0"
set "CHURCH_TMPDIR=%TEMP%\ChurchEMCOMM_%RANDOM%"
md "%CHURCH_TMPDIR%" 2>nul
set "CHURCH_PS1=%CHURCH_TMPDIR%\installer.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
    "[IO.File]::WriteAllText($env:CHURCH_PS1, ([IO.File]::ReadAllText($env:CHURCH_SRC) -replace '(?s)^.*<#PS1START#>',''))"
if not exist "%CHURCH_PS1%" (
    echo.
    echo  ERROR: Could not extract installer.
    echo  Right-click this file ^> Properties ^> check Unblock ^> OK, then run again.
    echo.
    pause
    exit /b 1
)
set CHURCH_EMCOMM_BAT=1
powershell.exe -NoLogo -ExecutionPolicy Bypass -File "%CHURCH_PS1%"
set "EC=%ERRORLEVEL%"
rd /s /q "%CHURCH_TMPDIR%" 2>nul
echo.
echo  Press any key to close this window.
pause >nul
exit /b %EC%
<#PS1START#>'''

FORMS = {
    'disaster-report': ['Church_of_Jesus_Christ_Disaster_Report_Initial.html', 'Church_of_Jesus_Christ_Disaster_Report_Viewer.html',
                        'Church_of_Jesus_Christ_Disaster_Report_Worker.html', 'Church of Jesus Christ Disaster Report.txt'],
    'supply-order': ['Church_of_Jesus_Christ_Supply_Order_Initial.html', 'Church_of_Jesus_Christ_Supply_Order_Viewer.html',
                     'Church_of_Jesus_Christ_Supply_Order_Worker.html', 'Church of Jesus Christ Supply Order.txt'],
    'work-crew-log': ['Church_of_Jesus_Christ_Work_Crew_Log.html', 'Church_of_Jesus_Christ_Work_Crew_Log_Viewer.html',
                      'Church_of_Jesus_Christ_Work_Crew_Log_Worker.html', 'Church of Jesus Christ Work Crew Log.txt'],
}
CORE = [f'templates/{d}/{n}' for d, names in FORMS.items() for n in names] + [
    'eoc/EOC_Message_Center.html', 'eoc/EOC_Wall_Display.html', 'eoc/EOC_Phone.html', 'eoc/eoc_server.py', 'eoc/readout.py',
    'eoc/start_eoc_server.bat',
    'simulation/sim_server.py', 'simulation/engine.py', 'simulation/orgpack.py', 'simulation/privacy.py',
    'simulation/drillconfig.py', 'simulation/community.py', 'simulation/scenario_check.py', 'simulation/index.html',
    'simulation/README.md', 'simulation/start_simulator.bat',
    'simulation/scenarios/catalog.json', 'training/quick-ref-cards.html',
] + [f'training/pdf/Quick_Reference_Card_{n}.pdf' for n in (
    '1_Helping_Hands_Volunteer', '2_EMCOMM_HAM_Operator', '3_EOC_Operator', '4_Leaders_Overview', '5_Drill_Controller',
    '6_Satellite_EOC', '7_Stake_Center_EOC', '8_Council_Area_EOC', '9_Your_First_Drill', '10_Team_Leader_Crew_Chief')] + [
    'sw.js', 'README.md', 'docs/PACE_PLAN.md', 'LICENSE']
ZIP_ONLY = ['installer/install.bat', 'installer/install.ps1', 'training/pdf/Quick_Reference_Cards_All.pdf']


def tracked(prefix: str) -> list:
    """Files under a folder that git knows of or would add (new files too, ignored ones never), that exist now."""
    out = subprocess.run(['git', '-c', 'core.quotepath=off', 'ls-files', '--cached', '--others', '--exclude-standard', '-z', '--', prefix],
                         cwd=ROOT, capture_output=True, check=True).stdout.decode('utf-8')
    return sorted(n for n in out.split('\0') if n and (ROOT / n).is_file())


def shared_files() -> list:
    """Repository-relative paths in both the installer and the ZIP."""
    files = list(CORE)
    files += [n for n in tracked('training/practice-forms') if n.count('/') == 2]       # that folder only, as install.ps1 expects
    files += [n for n in tracked('simulation/scenarios') if n.endswith('.json') and n != 'simulation/scenarios/catalog.json' and n.count('/') == 2]
    files += [n for n in tracked('simulation/example') if not re.search(r'/simulation/(runs|local-roles\.json)', n)]
    files += tracked('forms') + tracked('training/scenario-samples')
    return sorted(set(files))


def read_for_release(rel: str) -> bytes:
    """The file's bytes; Windows scripts go out with CRLF whatever the checkout (cmd.exe can mis-read LF labels)."""
    data = (ROOT / rel).read_bytes()
    if WINDOWS_SCRIPT.search(rel):
        return re.sub(r'\r?\n', '\r\n', data.decode('utf-8')).encode('utf-8')
    return data


def installer_body() -> str:
    """install.ps1 pointed at the extraction folder, with its repository check removed."""
    text = (ROOT / 'installer' / 'install.ps1').read_text(encoding='utf-8-sig')
    text = re.sub(r'(?s)^#Requires.*?#>\s*', '', text, count=1)
    old = '$RepoRoot = Split-Path -Parent $PSScriptRoot'
    if old not in text:
        sys.exit(f'install.ps1 no longer has the line: {old}')
    text = text.replace(old, '$RepoRoot = $ExtractRoot')
    return re.sub(r'(?s)# -- Check repo files.*?exit 1\r?\n\}', '', text, count=1)


def powershell_script(files: list) -> str:
    L = ['#Requires -Version 5.1', '<#', '.SYNOPSIS', f'    Church of Jesus Christ EMCOMM -- Single-File Installer v{VERSION}', '.DESCRIPTION',
         '    All form files are embedded. No ZIP to extract.', f'    Double-click ChurchEMCOMM_Installer_v{VERSION}.bat to run.', '',
         '    No internet required. No admin rights required.', '#>', '', "$ErrorActionPreference = 'Stop'", '',
         '# ---- Embedded files (base64, 76-char chunks) ---------------------------', '$EmbeddedFiles = @(']
    for rel in files:
        folder, _, name = rel.rpartition('/')
        b64 = base64.b64encode(read_for_release(rel)).decode('ascii')
        L += ['    @{', f"        Name = '{name}'", f"        Dir  = '{(folder or '.').replace('/', chr(92))}'", '        Chunks = @(']
        L += [f"            '{b64[i:i + 76]}'" for i in range(0, len(b64), 76)]
        L += ['        )', '    }']
    L += [')', '', '# ---- Extract to temp ---------------------------------------------------',
          '# inside the folder the batch header made and removes when this script ends, however it ends (cancelled, error)',
          '$ExtractRoot = if ($env:CHURCH_TMPDIR) { Join-Path $env:CHURCH_TMPDIR "files" } else { Join-Path $env:TEMP "ChurchEMCOMM_Install_$(Get-Random)" }',
          'New-Item -ItemType Directory -Force $ExtractRoot | Out-Null',
          'foreach ($f in $EmbeddedFiles) {',
          '    $dir  = Join-Path $ExtractRoot $f.Dir',
          '    $dest = Join-Path $dir $f.Name',
          '    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }',
          '    [System.IO.File]::WriteAllBytes($dest, [Convert]::FromBase64String([string]::Concat($f.Chunks)))',
          '}', '', '# ---- Installer logic (install.ps1 with patched RepoRoot) ---------------', installer_body(),
          '', '# ---- Cleanup -----------------------------------------------------------',
          'Remove-Item $ExtractRoot -Recurse -Force -ErrorAction SilentlyContinue']
    return '\r\n'.join(L)


def check_powershell_syntax(script: str):
    shell = shutil.which('powershell') or shutil.which('pwsh')
    if not shell:
        print('  SKIPPED the PowerShell syntax check: no powershell or pwsh here. After a change to install.ps1, build once on Windows.')
        return
    with tempfile.TemporaryDirectory(prefix='emcomm-build-') as td:
        p = Path(td) / 'check.ps1'
        p.write_bytes(script.encode('utf-8'))
        code = ('$e = $null; $null = [System.Management.Automation.Language.Parser]::ParseFile($args[0], [ref]$null, [ref]$e); '
                '$e | ForEach-Object { Write-Output ("Line " + $_.Extent.StartLineNumber + ": " + $_) }; exit $e.Count')
        r = subprocess.run([shell, '-NoProfile', '-Command', f'& {{ {code} }} "{p}"'], capture_output=True, text=True)
    if r.returncode:
        sys.exit('FAIL: syntax errors in the generated PowerShell:\n' + r.stdout[-2000:] + r.stderr[-1000:])
    print('  PowerShell syntax check passed')


def build_bat(out: Path = None, quiet: bool = False):
    """Write the one-file installer (to dist/, or to `out`: testing/test_install.py builds a scratch copy)."""
    out = out or BAT
    files = shared_files()
    script = powershell_script(files)
    output = re.sub(r'\r?\n', '\r\n', BAT_HEADER + script)
    out.write_bytes(output.encode('utf-8'))
    if not quiet:
        print(f'  {out.name}: {len(files)} files, {out.stat().st_size // 1024} KB')
        check_powershell_syntax(script)
    return files


def build_zip(out: Path = None, quiet: bool = False):
    """Write the ZIP (to dist/, or to `out`)."""
    out = out or ZIP
    readme = (ROOT / 'installer' / 'dist-readme.txt').read_text(encoding='utf-8').replace('{VERSION}', VERSION)
    entries = {n: read_for_release(n) for n in shared_files() + ZIP_ONLY}
    entries['README.txt'] = re.sub(r'\r?\n', '\r\n', readme).encode('utf-8')
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, entries[name])
    if not quiet:
        print(f'  {out.name}: {len(entries)} files, {out.stat().st_size // 1024} KB')
    return sorted(entries)


def main(argv):
    unknown = set(argv) - {'--bat', '--zip'}
    if unknown:
        sys.exit(__doc__)
    DIST.mkdir(exist_ok=True)
    if '--zip' not in argv or '--bat' in argv:
        build_bat()
    if '--bat' not in argv or '--zip' in argv:
        build_zip()


if __name__ == '__main__':
    main(sys.argv[1:])
