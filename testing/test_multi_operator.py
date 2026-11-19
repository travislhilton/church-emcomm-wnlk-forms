#!/usr/bin/env python3
"""Several operators at once (audit 2026-11-18): two Message Center pages open on one scratch EOC server.

  - a PACE level set on page A (or pushed by the simulator) reaches page B, and B's next note never puts the old
    level back on the server;
  - a report filed by phone, a status change and a removal on page A reach page B; a roll-up record dated earlier
    than B's last look still shows;
  - a page whose computer clock runs 2 minutes fast still sees new reports (the server's clock is the cursor);
  - a note written while the server is stopped is kept on that screen, the bar says NOT SAVED, and it reaches the
    server once the server is back.

Needs Playwright (python -m pip install playwright; python -m playwright install chromium) or Google Chrome.

    python testing/test_multi_operator.py [--port=8089]
"""
import json, os, pathlib, shutil, subprocess, sys, tempfile, time, urllib.request
os.environ.setdefault('EMCOMM_DISCOVERY', 'test')
REPO = pathlib.Path(__file__).resolve().parent.parent
PORT = int(next((a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('--port=')), '8089'))
SP = pathlib.Path(tempfile.mkdtemp(prefix='eoc_multi_op_'))
BASE = f'http://127.0.0.1:{PORT}'
res = []


def check(label, ok, detail=''):
    ok = bool(ok); res.append(ok); print(('PASS ' if ok else 'FAIL ') + label + (' -- ' + str(detail)[:300] if detail and not ok else ''), flush=True)


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode('utf-8'))


try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print('SKIP: playwright is not installed (python -m pip install playwright)')
    sys.exit(2)

wd = SP / 'site' / 'eoc'
wd.mkdir(parents=True)
for f in ('eoc_server.py', 'EOC_Message_Center.html', 'EOC_Wall_Display.html', 'EOC_Phone.html', 'readout.py'):
    shutil.copy2(REPO / 'eoc' / f, wd / f)
shutil.copytree(REPO / 'templates', SP / 'site' / 'templates')
ENV = dict(os.environ, PYTHONIOENCODING='utf-8', LOCALAPPDATA=str(SP / 'appdata'), USERPROFILE=str(SP / 'home'),
           XDG_CONFIG_HOME=str(SP / 'cfg'), EMCOMM_DOCUMENTS=str(SP / 'documents'))
procs = []


def start():
    log = open(SP / 'eoc.log', 'a', encoding='utf-8')
    p = subprocess.Popen([sys.executable, '-u', 'eoc_server.py', str(PORT)], cwd=str(wd), stdout=log, stderr=subprocess.STDOUT, env=ENV)
    procs.append(p)
    for _ in range(80):
        try:
            call('GET', '/api/status'); return p
        except Exception:
            time.sleep(0.25)
    raise SystemExit('the scratch EOC server did not start: see ' + str(SP / 'eoc.log'))


def stop(p):
    p.terminate()
    try: p.wait(timeout=5)
    except Exception: p.kill()


def until(fn, secs=12):
    end = time.time() + secs
    while time.time() < end:
        try:
            if fn(): return True
        except Exception:
            pass
        time.sleep(0.4)
    return False


DR = {'inc_stake': 'Larkspur Stake', 'inc_ward': 'Larkspur 2nd Ward', 'inc_type': 'Flood', 'inc_date': '2026-11-18',
      'inc_location': 'Larkspur 2nd chapel', 'mem_injuries': '1', 'miss_safe': 'YES', 'sub_name': 'Test Volunteer'}
srv = start()
try:
    inc = call('GET', '/api/incident')
    inc.update({'eocName': 'Larkspur Stake EOC', 'eocLevel': 'stake', 'name': 'Two-operator check', 'pace': 'P'})
    call('PUT', '/api/incident', inc)
    with sync_playwright() as pw:
        try: b = pw.chromium.launch()
        except Exception: b = pw.chromium.launch(channel='chrome')
        ctxA, ctxB = b.new_context(), b.new_context()
        # page C's computer clock runs 2 minutes fast
        ctxC = b.new_context()
        ctxC.add_init_script('(function(){ var off = 120000, D = Date, N = D.now; Date.now = function(){ return N() + off; }; })();')
        A, B, C = ctxA.new_page(), ctxB.new_page(), ctxC.new_page()
        errs = []
        for pg in (A, B, C):
            pg.on('pageerror', lambda e: errs.append(str(e)))
            pg.goto(BASE + '/'); pg.wait_for_function('typeof networkMode !== "undefined" && networkMode && incident && incident.eventId', timeout=15000)
        js = lambda pg, expr: pg.evaluate(expr)

        # PACE set on A reaches B; B's note does not put the old level back
        js(A, "incident.pace='C'; incident.paceTs=Date.now(); save();")
        check('PACE C set on page A reaches the server', until(lambda: call('GET', '/api/incident').get('pace') == 'C', 5))
        check('page B adopts PACE C within seconds (no reload)', until(lambda: js(B, 'incident.pace') == 'C', 12), js(B, 'incident.pace'))
        js(B, "document.getElementById('note-input').value='Note from B after the PACE change'; addNote();")
        time.sleep(1.5)
        check('a note on page B leaves the server at PACE C (not the old P)', call('GET', '/api/incident').get('pace') == 'C', call('GET', '/api/incident').get('pace'))
        # the simulator pushes PACE the way engine._push_pace does: GET, change, PUT the whole incident
        sim = call('GET', '/api/incident'); sim['pace'], sim['paceTs'] = 'E', int(time.time() * 1000); call('PUT', '/api/incident', sim)
        check('a PACE level pushed by the simulator reaches both open pages', until(lambda: js(A, 'incident.pace') == 'E' and js(B, 'incident.pace') == 'E', 12),
              (js(A, 'incident.pace'), js(B, 'incident.pace')))
        js(A, "document.getElementById('note-input').value='Note from A after the simulator push'; addNote();")
        time.sleep(1.5)
        check('a note on page A afterwards leaves the server at E', call('GET', '/api/incident').get('pace') == 'E')

        # a report by phone reaches every page, the fast-clock page too
        up = call('POST', '/api/upload', {'reports': [{'id': 'p1', 'form': 'dr', 'data': DR}]})
        mid = next(m['id'] for m in call('GET', '/api/messages') if m['type'] == 'dr')
        seen = lambda pg: js(pg, f"msgs.some(function(m){{return m.id==={json.dumps(mid)};}})")
        check('a report filed by phone shows on pages A and B', up.get('new') == 1 and until(lambda: seen(A) and seen(B), 12))
        check('it shows on page C too, whose clock runs 2 minutes fast', until(lambda: seen(C), 12))
        # status change on A reaches B
        js(A, f"cycleStatus({json.dumps(mid)})")
        st = lambda pg: js(pg, f"(msgs.filter(function(m){{return m.id==={json.dumps(mid)};}})[0]||{{}}).status")
        check('a status change on page A reaches the server and page B', until(lambda: st(A) != 'new' and st(B) == st(A), 12), (st(A), st(B)))
        # a roll-up record dated 20 minutes ago still shows on B
        old = int(time.time() * 1000) - 20 * 60000
        roll = {'kind': 'church_rollup', 'v': 1, 'from': 'Larkspur 3rd Ward Satellite EOC', 'level': 'satellite', 'exportedAt': old, 'since': 0,
                'msgs': [{'id': 'ROLL0001', 'type': 'dr', 'ts': old, 'dr': {'stake': 'Larkspur Stake', 'ward': 'Larkspur 3rd Ward', 'location': 'Larkspur 3rd chapel',
                          'submitter': 'Satellite Operator', 'date': '11/18/2026', 'type': 'Flood', 'mem_inj': '0', 'miss_safe': 'YES'}}],
                'roster': [], 'notes': [], 'actions': []}
        mr = call('POST', '/api/merge', roll)
        check('a roll-up record dated 20 minutes earlier is merged', (mr.get('new') or 0) >= 1, mr)
        rid = next((m['id'] for m in call('GET', '/api/messages') if 'Larkspur 3rd Ward' in m['data_json']), '')
        check('and shows on page B without a reload', rid and until(lambda: js(B, f"msgs.some(function(m){{return m.id==={json.dumps(rid)};}})"), 12))
        # removal on A reaches B
        js(A, f"removeMsg({json.dumps(mid)}); if (pendingConfirm) {{ var f = pendingConfirm; pendingConfirm = null; f(); }}")
        check('a record removed on page A leaves page B', until(lambda: not seen(B), 12) and not any(m['id'] == mid for m in call('GET', '/api/messages')))

        # the server stops: a note on A is kept, the bar says so, and it reaches the server when it is back
        stop(srv)
        js(A, "document.getElementById('note-input').value='Written while the server was stopped'; addNote();")
        check('with the server stopped the note waits on page A and the bar says NOT SAVED',
              until(lambda: js(A, '_netQueue.length') >= 1 and 'NOT SAVED' in js(A, "document.getElementById('net-bar').textContent"), 10),
              (js(A, '_netQueue.length'), js(A, "document.getElementById('net-bar').textContent")))
        srv = start()
        check('the server back: the kept note reaches it and the queue empties',
              until(lambda: any('Written while the server was stopped' in (n.get('text') or '') for n in call('GET', '/api/notes')) and js(A, '_netQueue.length') == 0, 20))
        check('no script error on any page', not errs, errs)
        b.close()
finally:
    for p in procs:
        if p.poll() is None: stop(p)
    shutil.rmtree(SP, ignore_errors=True)
print('\nRESULT:', 'ALL PASS' if res and all(res) else 'FAILURES', f'({sum(res)}/{len(res)})')
sys.exit(0 if res and all(res) else 1)
