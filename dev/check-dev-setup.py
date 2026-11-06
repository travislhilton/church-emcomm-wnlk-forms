#!/usr/bin/env python3
"""Is this machine ready to develop on? Windows and macOS, standard library only.

    python dev/check-dev-setup.py            check; exit 1 if something must be fixed
    python dev/check-dev-setup.py --fix      also turn on the commit hook and make it executable
    python dev/check-dev-setup.py --tests    also run the test suites

FAIL means fix it before working here. NOTE is an optional piece this machine does not have. The tool changes
nothing without --fix, and never reads or prints the contents of secure data.
"""
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'training'))
fails = []


def say(level, text):
    print(f'{level:5}{text}')
    if level == 'FAIL':
        fails.append(text)


def git(*args):
    r = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return r.stdout.strip() if r.returncode == 0 else ''


def find_chrome():
    import importlib.util
    spec = importlib.util.spec_from_file_location('qrc', ROOT / 'training' / 'build-quick-ref-pdfs.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.find_chrome()


def main(argv):
    fix, tests = '--fix' in argv, '--tests' in argv
    print(f'{platform.system()} {platform.machine()}, Python {platform.python_version()}, {ROOT}\n')
    if sys.version_info < (3, 8):
        say('FAIL', 'Python 3.8 or later is needed')
    if not shutil.which('git'):
        say('FAIL', 'git is not installed')
        return finish()
    say('PASS', git('--version'))

    hook = ROOT / '.githooks' / 'pre-commit'
    if git('config', 'core.hooksPath') != '.githooks':
        if fix:
            git('config', 'core.hooksPath', '.githooks')
            say('PASS', 'commit hook turned on')
        else:
            say('FAIL', 'the commit hook is off: it keeps private data out of public files (run with --fix)')
    else:
        say('PASS', 'commit hook is on')
    if platform.system() != 'Windows' and not hook.stat().st_mode & 0o100:     # git skips a hook that is not executable
        if fix:
            hook.chmod(0o755)
            say('PASS', 'commit hook made executable')
        else:
            say('FAIL', 'the commit hook is not executable, so git skips it (run with --fix)')

    changed = [ln for ln in git('status', '--porcelain').splitlines() if not ln.startswith('??')]
    if len(changed) > 40:
        say('FAIL', f'{len(changed)} files show as changed, which usually means line endings. Do not commit this; see CONTRIBUTING.md')
    else:
        say('PASS', f'{len(changed)} changed files in this working tree')
    wrong = []
    for line in git('-c', 'core.quotepath=off', 'ls-files', '--eol').splitlines():
        meta, name = line.split('\t', 1)
        wt, attr = meta.split(None, 2)[1:]
        if ('eol=crlf' in attr and wt in ('w/lf', 'w/mixed')) or ('eol=lf' in attr and wt in ('w/crlf', 'w/mixed')):
            wrong.append(name)
    say('FAIL' if wrong else 'PASS', f'line endings: {len(wrong)} files differ from .gitattributes' + (f', first {wrong[0]}' if wrong else ''))

    chrome = find_chrome()
    say('PASS' if chrome else 'NOTE', f'Chrome: {chrome}' if chrome else 'no Chrome: card PDFs and icons cannot be built here (set CHROME to its path)')
    if platform.system() != 'Windows':
        say('NOTE', 'card PDFs and deck measurements are set up for Windows fonts: build those on Windows (CONTRIBUTING.md)')
    say('PASS' if shutil.which('gh') else 'NOTE', 'GitHub command line (gh) found' if shutil.which('gh') else 'no gh: install it to publish a release from here')
    private = (ROOT / 'secure data').is_dir()
    say('PASS' if private else 'NOTE', 'secure data is here' if private else 'no secure data here: private drills and packages cannot be built; never send it through GitHub')
    try:
        import playwright  # noqa: F401
        say('PASS', 'Playwright found (WebKit tests)')
    except ImportError:
        say('NOTE', 'no Playwright: test_offline_webkit.py and test_browsers.py will not run here')

    if platform.system() != 'Windows':
        vm = next((h for h in ('w9tlh-3',) if h in _ssh_hosts()), None)
        if not vm:
            say('NOTE', 'no w9tlh-3 entry in ~/.ssh/config: this machine cannot reach the Windows VM yet')
        else:
            r = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=6', vm, 'hostname'], capture_output=True, text=True)
            say('PASS' if r.returncode == 0 else 'NOTE', f'Windows VM over SSH: {r.stdout.strip()}' if r.returncode == 0 else 'the Windows VM did not answer over SSH')

    if tests:
        run_tests()
    return finish()


def _ssh_hosts():
    cfg = Path.home() / '.ssh' / 'config'
    return re.findall(r'(?im)^\s*Host\s+(\S+)', cfg.read_text(encoding='utf-8', errors='replace')) if cfg.is_file() else []


def run_tests():
    print()
    env = dict(__import__('os').environ, PYTHONIOENCODING='utf-8')
    suites = [['test_acronyms.py'], ['test_public_files.py'], ['test_example.py'], ['test_sim.py'], ['test_training_samples.py'],
              ['test_phone_api.py', '--ports=8180,8181'], ['test_offline_webkit.py'], ['test_browsers.py']]
    for s in suites:
        r = subprocess.run([sys.executable, str(ROOT / 'testing' / s[0]), *s[1:]], cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
        last = next((ln for ln in reversed((r.stdout + '\n' + r.stderr).splitlines()) if ln.strip()), '(no output)')
        if r.returncode:
            detail = [ln for ln in r.stdout.splitlines() if ln.startswith('FAIL')][:5] or r.stderr.splitlines()[-3:]
            say('FAIL', f'{s[0]}: {last}')
            for d in detail:
                print(f'       {d[:200]}')
        else:
            say('NOTE' if 'SKIP' in last else 'PASS', f'{s[0]}: {last}')


def finish():
    print(f'\n{"READY" if not fails else str(len(fails)) + " to fix"}')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
