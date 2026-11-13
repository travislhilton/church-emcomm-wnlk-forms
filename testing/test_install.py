#!/usr/bin/env python3
"""Install test: the release files are current, and the installer leaves exactly the right files for every role.

    python testing/test_install.py                 every check (the install runs need Windows)
    python testing/test_install.py --keep          leave the scratch folder for a look afterwards
    python testing/test_install.py --ports=A,B     ports for the installed EOC server and simulator (8187, 8188)

On any machine: dist/ holds what a fresh build of this working tree gives (the one-file installer byte for byte,
the ZIP file by file).

On Windows it then runs the installer itself, from a fresh build, into a scratch folder. EMCOMM_TEST_ROOT makes
install.ps1 treat folders inside that scratch folder as Documents, the Desktop, the system drive and Winlink
Express, so this computer's own install, Desktop and Winlink are never touched. The runs:

    role 3 (EOC Operator) from the one-file installer; the installed EOC server and simulator are started from
        the installed layout, serve every page, file an uploaded report and a Drop Folder file, load the example
    role 3 again over that install: stale files of an earlier release go, the EOC's records stay
    role 2 (HAM Field Operator) from the one-file installer
    role 1 (Field Volunteer) from the ZIP, by installer\\install.bat
    role 1 where Documents syncs to the cloud: the earlier install moves to the system drive
    no answer at the menu: nothing installed, no error

Each run must print no error and only the warnings it should, and the installed files must be exactly the
package's files (none missing, none extra, every byte equal to the repository).

The last line says how many checks ran. A run that stops early, or skips a stage, fails.
"""
import importlib.util
import json
import os
os.environ.setdefault('EMCOMM_DISCOVERY', 'test')   # this suite's EOC servers hear only each other; a real EOC on the LAN ignores them
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WINDOWS = sys.platform == 'win32'
KEEP = '--keep' in sys.argv
PE, PS = (int(x) for x in next((a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('--ports=')), '8187,8188').split(','))
NAME = 'Church of Jesus Christ EMCOMM'

res, stages = [], []


def check(label, ok, detail=''):
    ok = bool(ok)
    res.append(ok)
    print(('PASS ' if ok else 'FAIL ') + label + (' -- ' + str(detail)[:400] if detail and not ok else ''))
    return ok


def load_builder():
    spec = importlib.util.spec_from_file_location('build_release', str(REPO / 'installer' / 'build-release.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── What each role must leave behind, written out here and not read from install.ps1 ─────────────────────────────
WORKERS = {'disaster-report': 'Church_of_Jesus_Christ_Disaster_Report_Worker.html',
           'supply-order': 'Church_of_Jesus_Christ_Supply_Order_Worker.html',
           'work-crew-log': 'Church_of_Jesus_Christ_Work_Crew_Log_Worker.html'}
TEMPLATES = ['templates/disaster-report/Church_of_Jesus_Christ_Disaster_Report_Initial.html',
             'templates/disaster-report/Church_of_Jesus_Christ_Disaster_Report_Viewer.html',
             'templates/disaster-report/Church of Jesus Christ Disaster Report.txt',
             'templates/supply-order/Church_of_Jesus_Christ_Supply_Order_Initial.html',
             'templates/supply-order/Church_of_Jesus_Christ_Supply_Order_Viewer.html',
             'templates/supply-order/Church of Jesus Christ Supply Order.txt',
             'templates/work-crew-log/Church_of_Jesus_Christ_Work_Crew_Log.html',
             'templates/work-crew-log/Church_of_Jesus_Christ_Work_Crew_Log_Viewer.html',
             'templates/work-crew-log/Church of Jesus Christ Work Crew Log.txt']
EOC_FILES = ['EOC_Message_Center.html', 'EOC_Wall_Display.html', 'EOC_Phone.html', 'eoc_server.py', 'readout.py', 'start_eoc_server.bat']
SIM_FILES = ['sim_server.py', 'engine.py', 'orgpack.py', 'privacy.py', 'drillconfig.py', 'community.py', 'scenario_check.py',
             'index.html', 'README.md', 'start_simulator.bat']
PORTAL_EXTRA = ['sw.js', 'training/quick-ref-cards.html', 'training/pdf/Quick_Reference_Card_1_Helping_Hands_Volunteer.pdf'] + \
               ['templates/%s/%s' % (d, n) for d, n in WORKERS.items()]
LAUNCHER = 'Open EOC Message Center.cmd'          # written by the installer, not copied
SHORTCUTS = {
    1: ['%s Forms/Disaster Report Form.lnk', '%s Forms/Supply Order Form.lnk', '%s Forms/Work Crew Log Form.lnk',
        '%s Forms/Quick Reference Cards.lnk', '%s Forms/Quick Reference Cards (PDF).lnk', '%s Quick Reference Cards.lnk'],
    2: ['%s Forms/Training - Winlink Practice Forms.lnk'],
    3: ['%s EOC Message Center.lnk', '%s EOC Server.lnk', '%s Simulator.lnk', '%s EOC Drop Folder.lnk'],
}
# what the EOC writes while it runs: an upgrade must leave these alone, and they are not part of the package
DATA = re.compile(r'^(EOC Message Center/(eoc_data\.db.*|backups/.*|readout-latest\.json|(simulation/)?__pycache__/.*)|EOC Drop Folder/.*)$')


def expected(pkg, role, base, wl_templates):
    """{installed path: repository-relative source} for one role, given the package's file list."""
    e = {}

    def put(dest, rel):
        if rel in pkg:
            e[dest] = rel
    put(base / 'README.md', 'README.md')
    put(base / 'PACE_PLAN.md', 'docs/PACE_PLAN.md')
    put(base / 'LICENSE', 'LICENSE')
    fw = base / 'Field Worker Forms'
    for d, n in WORKERS.items():
        put(fw / n, 'templates/%s/%s' % (d, n))
    put(fw / 'Quick_Reference_Cards.html', 'training/quick-ref-cards.html')
    for rel in pkg:
        if re.match(r'training/pdf/Quick_Reference_Card[^/]*\.pdf$', rel):
            put(fw / 'Quick Reference Cards (PDF)' / rel.rsplit('/', 1)[1], rel)
    if role >= 2:
        for rel in TEMPLATES:
            put(wl_templates / (NAME + ' Forms') / rel.rsplit('/', 1)[1], rel)
        for rel in pkg:
            parts = rel.split('/')
            if rel.startswith('training/practice-forms/') and len(parts) == 3:
                put(wl_templates / (NAME + ' Practice') / parts[2], rel)
                put(base / 'Training' / 'Winlink Practice Forms' / parts[2], rel)
            if rel.startswith('training/scenario-samples/') and len(parts) == 4:
                put(base / 'Training' / ('Winlink Training ' + parts[2]) / parts[3], rel)
                if not parts[3].endswith('.json'):           # the ICS 213RR data file is for the installer, not a template
                    put(wl_templates / (NAME + ' Training ' + parts[2]) / parts[3], rel)
    if role == 3:
        eoc = base / 'EOC Message Center'
        for n in EOC_FILES:
            put(eoc / n, 'eoc/' + n)
        for n in SIM_FILES:
            put(eoc / 'simulation' / n, 'simulation/' + n)
        for rel in pkg:
            parts = rel.split('/')
            if rel.startswith('simulation/scenarios/') and rel.endswith('.json') and len(parts) == 3:
                put(eoc / 'simulation' / 'scenarios' / parts[2], rel)
            if rel.startswith('simulation/example/'):
                put(eoc.joinpath('simulation', 'example', *parts[2:]), rel)
            if rel.startswith('forms/') or rel in PORTAL_EXTRA:
                put((base / 'Web App (portal copy)').joinpath(*parts), rel)
    return e


def files_under(folder):
    return {p for p in folder.rglob('*') if p.is_file()} if folder.is_dir() else set()


def compare(label, builder, pkg, role, root, base=None, also_ok=()):
    """Installed files against the package: none missing, none extra, every byte equal. Shortcuts too."""
    base = base or (root / 'Documents' / NAME)
    wl = root / 'RMS Express' / 'Global Folders' / 'Templates'
    exp = expected(pkg, role, base, wl)
    got = files_under(base) | files_under(wl)
    got = {p for p in got if not (base in p.parents and DATA.match(p.relative_to(base).as_posix()))}
    allowed = {base / 'EOC Message Center' / LAUNCHER} if role == 3 else set()
    missing = sorted(str(p) for p in set(exp) - got)
    extra = sorted(str(p) for p in got - set(exp) - allowed - set(also_ok))
    check('%s: every file of the package is installed (%d files)' % (label, len(exp)), exp and not missing, missing[:4])
    check('%s: nothing else is in the install or the Winlink template folders' % label, not extra, extra[:4])
    differ = [str(p) for p, rel in exp.items() if p.is_file() and p.read_bytes() != builder.read_for_release(rel)]
    check('%s: every installed file equals the repository, byte for byte' % label, not differ, differ[:4])
    want = sorted(s % NAME for r in range(1, role + 1) for s in SHORTCUTS[r])
    have = sorted(p.relative_to(root / 'Desktop').as_posix() for p in files_under(root / 'Desktop'))
    check('%s: the Desktop has this role\'s shortcuts and no others (%d)' % (label, len(want)), have == want,
          {'missing': sorted(set(want) - set(have)), 'extra': sorted(set(have) - set(want))})
    if role >= 2:
        defs = [p for p in exp if p.suffix == '.txt' and (NAME + ' Forms') in p.parts]
        crlf = [p.name for p in defs if p.is_file() and b'\r\n' in p.read_bytes() and b'\n' not in p.read_bytes().replace(b'\r\n', b'')]
        check('%s: the three Winlink template definitions have CRLF line endings' % label, len(defs) == 3 and len(crlf) == 3, crlf)
    if role == 3:
        launcher = base / 'EOC Message Center' / LAUNCHER
        text = launcher.read_bytes() if launcher.is_file() else b''
        check('%s: the Message Center launcher is written (CRLF, opens the server page or the file)' % label,
              b'EOC_HTML' in text and b'/api/status' in text and b'\n' not in text.replace(b'\r\n', b''))
        check('%s: the EOC Drop Folder is there' % label, (base / 'EOC Drop Folder').is_dir())
    return exp


def make_root(root, winlink=True):
    """An empty stand-in for a Windows computer: its own app data, and Winlink Express when asked."""
    (root / 'AppData').mkdir(parents=True)
    if winlink:
        (root / 'RMS Express' / 'Global Folders' / 'Templates').mkdir(parents=True)
        (root / 'RMS Express' / 'RMS Express.exe').write_bytes(b'')      # the installer looks for the program file


def run_installer(cmd, root, answers, cwd=None):
    env = dict(os.environ, EMCOMM_TEST_ROOT=str(root), LOCALAPPDATA=str(root / 'AppData'))
    env.pop('CHURCH_EMCOMM_BAT', None)
    t0 = time.time()
    r = subprocess.run(cmd, input=answers.encode('ascii'), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
                       cwd=str(cwd) if cwd else None, timeout=900)
    return r.returncode, r.stdout.decode('utf-8', 'replace'), time.time() - t0


def clean_output(label, rc, out, warnings=()):
    """The run finished, said so, and printed no error and no warning but the ones named."""
    lines = [ln.strip() for ln in out.splitlines()]
    errors = [ln for ln in lines if ln.startswith('XX ') or 'ERROR' in ln or 'Exception' in ln or 'did not complete' in ln]
    warns = [ln for ln in lines if ln.startswith('!! ') and not any(w in ln for w in warnings)]
    check('%s: the installer finishes (exit 0, "Installation complete!")' % label, rc == 0 and 'Installation complete!' in out, (rc, lines[-6:]))
    check('%s: no error and no unexpected warning on the screen' % label, not errors and not warns, (errors + warns)[:4])
    asked = [ln for ln in lines if '(y/n)' in ln]
    check('%s: one question only (the role), nothing else is asked' % label, not asked, asked)


def call(port, method, path, body=None, raw=False):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request('http://127.0.0.1:%d%s' % (port, path), data=data, method=method, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=20) as r:
        b = r.read()
        return (r.status, b) if raw else json.loads(b.decode('utf-8'))


def port_free(port):
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(('127.0.0.1', port)) != 0


def servers(root, base):
    """Start the installed EOC server and simulator where the installer put them, and use them."""
    eoc = base / 'EOC Message Center'
    if not check('the test ports %d and %d are free (a stale server would answer in place of the installed one)' % (PE, PS), port_free(PE) and port_free(PS)):
        return
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1', LOCALAPPDATA=str(root / 'AppData'), USERPROFILE=str(root / 'home'))
    env.pop('EMCOMM_DOCUMENTS', None)       # as installed: the Drop Folder is the one beside the server
    (root / 'winlink-empty').mkdir()
    procs, logs = [], []
    try:
        # Through the start scripts the Desktop shortcuts run (they find Python themselves), from another folder
        for name, bat, args in (('eoc', eoc / 'start_eoc_server.bat', '%d "--winlink-folder=%s"' % (PE, root / 'winlink-empty')),
                                ('sim', eoc / 'simulation' / 'start_simulator.bat', str(PS))):
            log = open(str(root / (name + '.log')), 'w', encoding='utf-8')      # a file: a full pipe would freeze the server
            logs.append(log)
            # cmd /c ""script" args": the outer quotes are the ones cmd removes
            procs.append(subprocess.Popen('cmd /c ""%s" %s"' % (bat, args), cwd=str(root), stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, env=env))
        up = {}
        for port, path in ((PE, '/api/status'), (PS, '/api/info')):
            for _ in range(80):
                try:
                    up[port] = call(port, 'GET', path)
                    break
                except Exception:
                    time.sleep(0.25)
        want = re.search(r"^FORMS_VERSION = '([^']+)'", (REPO / 'eoc' / 'eoc_server.py').read_text(encoding='utf-8'), re.M).group(1)
        if not check('installed EOC server: its Desktop start script finds Python and starts it; it reports this release (%s)' % want, up.get(PE, {}).get('formsVersion') == want,
                     up.get(PE) or (root / 'eoc.log').read_text(encoding='utf-8', errors='replace')[-400:]):
            return
        pages = {'/': b'EOC', '/wall': b'wallmap', '/m': b'EOC on this Wi-Fi', '/receive': b'decodePayload', '/forms/dr': b'Disaster Report',
                 '/forms/so': b'Supply Order', '/forms/wcl': b'Work Crew Log', '/icons/icon-180.png': b'\x89PNG', '/app.webmanifest': b'EMCOMM EOC',
                 '/api/readout': b'emcomm-readout/1'}
        bad = []
        for path, marker in pages.items():
            try:
                s, b = call(PE, 'GET', path, raw=True)
                if s != 200 or marker not in b:
                    bad.append(path)
            except Exception as e:
                bad.append('%s (%s)' % (path, e))
        check('installed EOC server: serves every page (Message Center, wall, phone page, the three forms, icon, manifest, read-out)', not bad, bad)
        s, b = call(PE, 'GET', '/', raw=True)
        check('installed EOC server: the Message Center it serves is the installed file', b == (eoc / 'EOC_Message_Center.html').read_bytes())
        dq = call(PE, 'GET', '/api/drop/status')
        drop = base / 'EOC Drop Folder'
        check('installed EOC server: watches the Drop Folder of its own install', dq.get('enabled') and Path(dq.get('watch_path', '')) == drop, dq)
        dr = {'inc_stake': 'Juniper Plains Stake', 'inc_ward': 'Larkspur 1st Ward', 'inc_type': 'Flood', 'inc_date': '2026-11-11',
              'inc_location': 'Install test', 'sub_name': 'Install Test', 'exercise': True}
        r1 = call(PE, 'POST', '/api/upload', {'reports': [{'id': 'install-1', 'form': 'dr', 'data': dr}]})
        check('installed EOC server: files a report a phone uploads', r1.get('ok') and r1.get('new') == 1, r1)
        (drop / 'Church_of_Jesus_Christ_Supply_Order_Worker.txt').write_text(
            json.dumps({'req_stake': 'Juniper Plains Stake', 'order_date': '2026-11-11', 'del_city': 'Larkspur', 'gs01': '2'}), encoding='utf-8')
        n = 0
        for _ in range(40):
            n = len(call(PE, 'GET', '/api/messages'))
            if n >= 2:
                break
            time.sleep(0.5)
        check('installed EOC server: files a form saved into the Drop Folder and moves it to Ingested', n == 2 and files_under(drop / 'Ingested')
              and not list(drop.glob('*.txt')), (n, [p.name for p in files_under(drop)]))
        check('installed EOC server: its database is beside it, in the install', (eoc / 'eoc_data.db').is_file())
        check('installed EOC server: says whether Windows Firewall blocks other devices (not blocked here)', call(PE, 'GET', '/api/status').get('firewallBlocked') is False
              and '[FIREWALL] not checked' not in (root / 'eoc.log').read_text(encoding='utf-8', errors='replace'))

        check('installed simulator: its Desktop start script finds Python and starts it; it serves its page', up.get(PS) is not None and call(PS, 'GET', '/', raw=True)[0] == 200,
              (root / 'sim.log').read_text(encoding='utf-8', errors='replace')[-400:] if up.get(PS) is None else '')
        if up.get(PS) is not None:
            cat = call(PS, 'GET', '/api/scenarios')
            ids = [s.get('id') for s in cat.get('scenarios', [])]
            listed = [s['id'] for s in json.loads((REPO / 'simulation' / 'scenarios' / 'catalog.json').read_text(encoding='utf-8'))['scenarios']]
            check('installed simulator: lists the release\'s scenarios (%d)' % len(listed), sorted(ids) == sorted(listed), ids)
            ex = eoc / 'simulation' / 'example' / 'juniper-plains'
            r2 = call(PS, 'POST', '/api/pack', {'path': str(ex), 'privacy': 'pseudonymized'})
            info = r2.get('info') or {}
            check('installed simulator: loads the installed example community (Juniper Plains) with its map data', r2.get('ok') and info.get('pack')
                  and info.get('ok') and not info.get('packError'), {k: info.get(k) for k in ('ok', 'error', 'packError', 'pack')})
            r3 = subprocess.run([sys.executable, '-c', 'import engine; print(engine._eoc_module().FORMS_VERSION)'], cwd=str(eoc / 'simulation'),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, timeout=120)
            check('installed simulator: finds the EOC server\'s code in the installed layout', r3.stdout.decode('utf-8', 'replace').strip().endswith(want), r3.stdout[-300:])
        private = [str(p) for p in root.rglob('secure data')]
        check('nothing named "secure data" anywhere in the install', not private, private)
        (root / 'ran-servers').write_text('', encoding='utf-8')
    finally:
        for p in procs:      # the script's window and the Python it started
            subprocess.run(['taskkill', '/PID', str(p.pid), '/T', '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for p in procs:
            try:
                p.wait(timeout=8)
            except Exception:
                p.kill()
        for _ in range(40):      # Windows frees the database file a moment after the process ends
            if port_free(PE) and port_free(PS):
                break
            time.sleep(0.25)
        for log in logs:
            log.close()


def main():
    builder = load_builder()
    scratch = Path(tempfile.mkdtemp(prefix='emcomm_install_test_')).resolve()     # resolve: a short TEMP name (NAME~1) would not compare
    try:
        # ── The release files in dist/ are what this working tree builds ──
        bat, zf = scratch / builder.BAT.name, scratch / builder.ZIP.name
        bat_pkg = set(builder.build_bat(bat, quiet=True))
        zip_pkg = set(builder.build_zip(zf, quiet=True)) - {'README.txt'}
        check('dist: the one-file installer is the one this working tree builds (run installer/build-release.py)',
              builder.BAT.is_file() and builder.BAT.read_bytes() == bat.read_bytes())
        with zipfile.ZipFile(str(zf)) as a, zipfile.ZipFile(str(builder.ZIP)) as b:
            same = a.namelist() == b.namelist() and all(a.read(n) == b.read(n) for n in a.namelist())
        check('dist: the ZIP holds the files this working tree builds, each one equal', same)
        check('the ZIP holds everything the one-file installer holds, plus its own installer', bat_pkg <= zip_pkg
              and {'installer/install.bat', 'installer/install.ps1'} <= zip_pkg, sorted(bat_pkg - zip_pkg)[:4])
        check('the package holds every file the roles need', all(rel in bat_pkg for rel in TEMPLATES + PORTAL_EXTRA + ['eoc/' + n for n in EOC_FILES]
              + ['simulation/' + n for n in SIM_FILES] + ['README.md', 'docs/PACE_PLAN.md', 'LICENSE']))
        stages.append('release files')
        if not WINDOWS:
            return
        ics_warning = ('ICS213RR form not found',)       # the stand-in Winlink has no standard forms; the message tells the operator what to do

        # ── Role 3 from the one-file installer, then the installed servers ──
        r3 = scratch / 'role3'
        make_root(r3)
        rc, out, secs = run_installer(['cmd', '/c', str(bat)], r3, '3\n')
        (scratch / 'role3.out.txt').write_text(out, encoding='utf-8')
        clean_output('role 3 (one-file installer, %.0f s)' % secs, rc, out, ics_warning)
        base3 = r3 / 'Documents' / NAME
        compare('role 3', builder, bat_pkg, 3, r3)
        check('role 3: the installer found Python for the EOC server', 'Python ready:' in out)
        stages.append('role 3')
        servers(r3, base3)
        if (r3 / 'ran-servers').is_file():
            stages.append('servers')
        check('the servers stopped and left nothing listening on the test ports', port_free(PE) and port_free(PS))

        # ── Role 3 again, over an install an earlier release left: stale files go, the EOC's records stay ──
        wl = r3 / 'RMS Express' / 'Global Folders' / 'Templates'
        stale = [base3 / 'EOC Message Center' / 'simulation' / 'scenarios' / 'retired-scenario.json',
                 base3 / 'Web App (portal copy)' / 'forms' / 'retired-page.html',
                 base3 / 'Training' / 'Winlink Practice Forms' / 'Practice 99 - Retired Form.txt',
                 wl / (NAME + ' Practice') / 'Practice 99 - Retired Form.txt',
                 base3 / 'EOC Message Center' / 'start_eoc_server.command']
        for p in stale:
            p.write_text('left by an earlier release', encoding='utf-8')
        own = wl / (NAME + ' Practice') / 'My own note.txt'          # a person's own file in a folder the installer manages
        own.write_text('mine', encoding='utf-8')
        db = base3 / 'EOC Message Center' / 'eoc_data.db'
        before = db.read_bytes() if db.is_file() else None
        kept_before = sorted(p.name for p in files_under(base3 / 'EOC Drop Folder'))
        rc, out, secs = run_installer(['cmd', '/c', str(bat)], r3, '3\n')
        (scratch / 'role3-again.out.txt').write_text(out, encoding='utf-8')
        clean_output('role 3 again (%.0f s)' % secs, rc, out, ics_warning)
        compare('role 3 again', builder, bat_pkg, 3, r3, also_ok=[own])
        check('role 3 again: files of an earlier release are gone', not [p for p in stale if p.exists()], [str(p) for p in stale if p.exists()])
        check('role 3 again: a person\'s own file in the practice folder stays', own.is_file())
        check('role 3 again: the EOC database and the Drop Folder are untouched', before is not None and db.read_bytes() == before
              and sorted(p.name for p in files_under(base3 / 'EOC Drop Folder')) == kept_before and kept_before)
        stages.append('role 3 again')

        # ── Role 2 from the one-file installer ──
        r2 = scratch / 'role2'
        make_root(r2)
        rc, out, secs = run_installer(['cmd', '/c', str(bat)], r2, '2\n')
        (scratch / 'role2.out.txt').write_text(out, encoding='utf-8')
        clean_output('role 2 (one-file installer, %.0f s)' % secs, rc, out, ics_warning)
        compare('role 2', builder, bat_pkg, 2, r2)
        check('role 2: no EOC parts', not (r2 / 'Documents' / NAME / 'EOC Message Center').exists() and not (r2 / 'Documents' / NAME / 'EOC Drop Folder').exists())
        stages.append('role 2')

        # ── Role 1 from the ZIP, by installer\install.bat, on a computer with no Winlink ──
        r1 = scratch / 'role1'
        make_root(r1, winlink=False)
        with zipfile.ZipFile(str(zf)) as z:
            z.extractall(str(scratch / 'unzipped'))
        rc, out, secs = run_installer(['cmd', '/c', str(scratch / 'unzipped' / 'installer' / 'install.bat')], r1, '1\n\n')   # the last Enter answers its "Press any key"
        (scratch / 'role1.out.txt').write_text(out, encoding='utf-8')
        clean_output('role 1 (ZIP, %.0f s)' % secs, rc, out)
        compare('role 1', builder, zip_pkg, 1, r1)
        check('role 1: forms and cards only (no Winlink, EOC or Training folders)', sorted(p.name for p in (r1 / 'Documents' / NAME).iterdir())
              == ['Field Worker Forms', 'LICENSE', 'PACE_PLAN.md', 'README.md'] and not (r1 / 'RMS Express').exists(),
              sorted(p.name for p in (r1 / 'Documents' / NAME).iterdir()))
        stages.append('role 1')

        # ── Documents syncs to the cloud: the install, and an earlier one, go to the system drive ──
        rs = scratch / 'synced' / 'OneDrive'
        make_root(rs, winlink=False)
        old = rs / 'Documents' / NAME
        (old / 'EOC Message Center').mkdir(parents=True)
        (old / 'EOC Drop Folder' / 'Ingested').mkdir(parents=True)
        (old / 'EOC Message Center' / 'eoc_data.db').write_bytes(b'the EOC records')
        (old / 'EOC Message Center' / 'eoc_data.db-shm').write_bytes(b'stale index')
        (old / 'EOC Drop Folder' / 'Ingested' / 'report.txt').write_text('{}', encoding='utf-8')
        rc, out, secs = run_installer(['cmd', '/c', str(bat)], rs, '1\n')
        (scratch / 'synced.out.txt').write_text(out, encoding='utf-8')
        clean_output('synced Documents (%.0f s)' % secs, rc, out)
        new = rs / 'SystemDrive' / NAME
        check('synced Documents: the install goes to the system drive, and says why', (new / 'Field Worker Forms').is_dir()
              and 'syncs to the cloud' in out and 'Install location: ' + str(new) in out)
        check('synced Documents: the earlier install moved with its records; the stale SQLite index did not; the old folder is gone',
              (new / 'EOC Message Center' / 'eoc_data.db').read_bytes() == b'the EOC records' if (new / 'EOC Message Center' / 'eoc_data.db').is_file() else False)
        check('synced Documents: nothing is left in the synced folder', not old.exists() and (new / 'EOC Drop Folder' / 'Ingested' / 'report.txt').is_file()
              and not (new / 'EOC Message Center' / 'eoc_data.db-shm').exists(), [str(p) for p in files_under(old)][:4])
        stages.append('synced Documents')

        # ── No answer at the menu ──
        rn = scratch / 'none'
        make_root(rn)
        rc, out, secs = run_installer(['cmd', '/c', str(bat)], rn, '')
        check('no answer at the menu: nothing is installed and nothing fails', rc == 0 and 'cancelled' in out and not (rn / 'Documents' / NAME).exists()
              and not files_under(rn / 'RMS Express' / 'Global Folders'), (rc, out[-300:]))
        rc, out, secs = run_installer(['cmd', '/c', str(bat)], rn, 'x\n')
        check('X at the menu: cancelled, nothing installed', rc == 0 and 'Cancelled' in out and not (rn / 'Documents' / NAME).exists(), (rc, out[-300:]))
        left = [p.name for p in Path(os.environ.get('TEMP', str(scratch))).glob('ChurchEMCOMM_*') if p.stat().st_mtime > START]
        check('the installer leaves no working files in TEMP', not left, left)
        stages.append('cancelled')

        # ── Uninstall (U) on the role 3 install: a no keeps everything; a yes copies the records, then removes it all ──
        tpl3 = r3 / 'RMS Express' / 'Global Folders' / 'Templates'
        private = tpl3 / (NAME + ' Training PRIV-1')
        private.mkdir(parents=True, exist_ok=True)
        (private / 'README.txt').write_text('Church of Jesus Christ EMCOMM Winlink training set PRIV-1\nPRIVATE BUILD\n', encoding='utf-8')
        mine = [base3, r3 / 'AppData' / NAME, r3 / 'Desktop' / (NAME + ' Forms'), r3 / 'Desktop' / (NAME + ' EOC Server.lnk'),
                tpl3 / (NAME + ' Forms'), tpl3 / (NAME + ' Practice')]
        check('uninstall: the role 3 install is there to remove', all(p.exists() for p in mine), [str(p) for p in mine if not p.exists()])
        db_before = db.read_bytes() if db.is_file() else None
        drop_before = sorted(p.name for p in files_under(base3 / 'EOC Drop Folder'))
        rc, out, secs = run_installer(['cmd', '/c', str(bat)], r3, 'u\nn\n')
        check('uninstall, then no at the prompt: nothing is removed', rc == 0 and 'Nothing was removed' in out and all(p.exists() for p in mine), (rc, out[-300:]))
        rc, out, secs = run_installer(['cmd', '/c', str(bat)], r3, 'u\ny\n\n')     # Y, then Enter = keep a copy of the records
        (scratch / 'uninstall.out.txt').write_text(out, encoding='utf-8')
        check('uninstall: it says what it removes and that Python, the browser and Winlink Express stay',
              rc == 0 and 'This removes:' in out and 'not touched' in out and 'is uninstalled' in out, (rc, out[-400:]))
        left = [str(p) for p in mine if p.exists()] + [p.name for p in (r3 / 'Desktop').glob(NAME + '*')] \
            + [p.name for p in tpl3.glob(NAME + '*') if p != private]
        check('uninstall: the install folder, settings, Desktop items and Winlink template folders are gone', not left, left)
        check('uninstall: a private training set in Winlink stays, and the output says so', (private / 'README.txt').is_file() and 'private training set' in out)
        check('uninstall: Winlink Express itself stays', (r3 / 'RMS Express' / 'RMS Express.exe').is_file())
        copies = sorted((r3 / 'home').glob(NAME + ' records *'))
        cdb = copies[0] / 'install folder (Documents)' / 'EOC Message Center' / 'eoc_data.db' if copies else None
        check('uninstall: the EOC records were copied first (database byte for byte, Drop Folder, settings)',
              len(copies) == 1 and db_before is not None and cdb.is_file() and cdb.read_bytes() == db_before
              and sorted(p.name for p in files_under(copies[0] / 'install folder (Documents)' / 'EOC Drop Folder')) == drop_before
              and (copies[0] / 'settings (AppData)').is_dir() and 'Your EOC records are in:' in out,
              [str(p) for p in files_under(copies[0])][:6] if copies else 'no copy')
        rc, out, secs = run_installer(['cmd', '/c', str(bat)], r3, 'u\n')
        check('uninstall again: nothing to remove, nothing fails', rc == 0 and 'Nothing to remove' in out, (rc, out[-300:]))
        stages.append('uninstall')
    finally:
        if KEEP:
            print('scratch folder kept:', scratch)
        else:
            shutil.rmtree(str(scratch), ignore_errors=True)


START = time.time()
try:
    main()
except Exception as e:      # a stage that stops is a failure with a name, not a silent short run
    import traceback
    traceback.print_exc()
    check('the test ran to the end', False, '%s: %s' % (type(e).__name__, e))
need = ['release files'] + (['role 3', 'servers', 'role 3 again', 'role 2', 'role 1', 'synced Documents', 'cancelled', 'uninstall'] if WINDOWS else [])
check('every stage ran: ' + ', '.join(need), stages == need, stages)
print('\nRESULT:', 'ALL PASS' if all(res) else 'FAILURES', '(%d/%d)' % (sum(res), len(res)),
      '' if WINDOWS else '· SKIP the install runs: the installer runs on Windows only')
sys.exit(0 if res and all(res) else 1)
