#!/usr/bin/env python3
"""The map background (basemap), with no internet: a local fake tile server stands in for USGS (United States
Geological Survey) The National Map and for OpenStreetMap.

Server: POST /api/basemap/fetch downloads a small area in the background into the scratch settings folder, a second
run skips what is saved, a failing tile does not stop the job, a too-big area is refused before anything is fetched,
only the person at the EOC laptop may start it, /basemap/<layer>/<z>/<y>/<x> serves a saved tile with the right type
and refuses every other path.
Browsers (Chromium, Firefox, WebKit, when Playwright is installed): the Map tab draws the online street map under the
overlays, the saved Topo map when chosen (remembered after a reload), and with the street map unreachable it falls
back to the saved Topo map with the note "Street map needs internet", no page error and no retry storm.

    python testing/test_basemap.py [--ports=8190,8191]
"""
import functools
import http.server
import json
import os
os.environ.setdefault('EMCOMM_DISCOVERY', 'off')
import pathlib
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zlib

REPO = pathlib.Path(__file__).resolve().parent.parent
PA, PB = (int(x) for x in next((a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('--ports=')), '8190,8191').split(','))
EXAMPLE = REPO / 'simulation' / 'example' / 'juniper-plains'
res = []


def check(label, ok, detail=''):
    ok = bool(ok)
    res.append(ok)
    print(('PASS ' if ok else 'FAIL ') + label + (' -- ' + str(detail)[:260] if detail and not ok else ''), flush=True)


def png(rgb):
    """A 256 x 256 one-colour PNG, built with the standard library."""
    raw = b''.join(b'\x00' + bytes(rgb) * 256 for _ in range(256))
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 256, 256, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


COLOURS = {'topo': (30, 140, 60), 'imagery': (120, 70, 20), 'streets': (200, 40, 160)}
TILES = {k: png(v) for k, v in COLOURS.items()}
hits = {'topo': 0, 'imagery': 0, 'streets': 0, 'failed': 0}
agents = set()


class FakeTiles(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        m = re.match(r'^/usgs/(topo|imagery)/(\d+)/(\d+)/(\d+)$', self.path) or re.match(r'^/(streets)/(\d+)/(\d+)/(\d+)\.png$', self.path)
        if not m:
            self.send_response(404); self.end_headers(); return
        layer, z, a, b = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
        agents.add(self.headers.get('User-Agent', ''))
        if layer == 'imagery' and z == 11 and (a + b) % 5 == 0:     # a tile the source cannot give: the job carries on
            hits['failed'] += 1
            self.send_response(503); self.end_headers(); return
        hits[layer] += 1
        self.send_response(200)
        self.send_header('Content-Type', 'image/png')
        self.send_header('Content-Length', str(len(TILES[layer])))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(TILES[layer])


class Quiet(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


def call(port, method, path, body=None, raw=False, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=data, method=method, headers=dict({'Content-Type': 'application/json'}, **(headers or {})))
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            b = r.read()
            return (r.status, b, r.headers) if raw else (r.status, json.loads(b.decode('utf-8')))
    except urllib.error.HTTPError as e:
        b = e.read()
        if raw:
            return e.code, b, e.headers
        try:
            return e.code, json.loads(b.decode('utf-8'))
        except Exception:
            return e.code, {}


def wait_job(port, secs=90):
    for _ in range(secs * 4):
        st = call(port, 'GET', '/api/basemap/status')[1]
        if not st['job'].get('running'):
            return st
        time.sleep(0.25)
    return st


tmp = pathlib.Path(tempfile.mkdtemp(prefix='emcomm_basemap_'))
fake = Quiet(('127.0.0.1', 0), FakeTiles)
FP = fake.server_address[1]
threading.Thread(target=fake.serve_forever, daemon=True).start()
DEAD = free_port()          # nothing listens here: the street map as a browser with no internet sees it
(tmp / 'home').mkdir()
base_env = dict(os.environ, PYTHONIOENCODING='utf-8', LOCALAPPDATA=str(tmp / 'appdata'), HOME=str(tmp / 'home'), USERPROFILE=str(tmp / 'home'),
                EMCOMM_DOCUMENTS=str(tmp / 'documents'), EMCOMM_BASEMAP_URL=f'http://127.0.0.1:{FP}/usgs/{{layer}}/{{z}}/{{y}}/{{x}}')
procs = []
for name, port, streets in (('srvA', PA, f'http://127.0.0.1:{FP}/streets/{{z}}/{{x}}/{{y}}.png'), ('srvB', PB, f'http://127.0.0.1:{DEAD}/streets/{{z}}/{{x}}/{{y}}.png')):
    wd = tmp / name / 'eoc'
    wd.mkdir(parents=True)
    for f in ('eoc_server.py', 'EOC_Message_Center.html', 'EOC_Wall_Display.html', 'EOC_Phone.html', 'readout.py'):
        shutil.copy2(REPO / 'eoc' / f, wd / f)
    shutil.copytree(REPO / 'templates', tmp / name / 'templates')
    log = open(tmp / f'{name}.log', 'w', encoding='utf-8')
    procs.append(subprocess.Popen([sys.executable, '-u', 'eoc_server.py', str(port)], cwd=str(wd), stdout=log, stderr=subprocess.STDOUT,
                                  env=dict(base_env, EMCOMM_STREETS_URL=streets)))
PS = PB + 1                 # the simulator: reads the same saved tiles from the same settings folder
shutil.copytree(REPO / 'simulation', tmp / 'simulation', ignore=shutil.ignore_patterns('__pycache__', 'runs'))
procs.append(subprocess.Popen([sys.executable, '-u', 'sim_server.py', str(PS)], cwd=str(tmp / 'simulation'), stdout=open(tmp / 'sim.log', 'w', encoding='utf-8'),
                              stderr=subprocess.STDOUT, env=base_env))
CACHE = tmp / 'appdata' / 'Church of Jesus Christ EMCOMM' / 'basemap'
try:
    for port in (PA, PB):
        for _ in range(80):
            try:
                call(port, 'GET', '/api/status')
                break
            except Exception:
                time.sleep(0.25)
    # ── server ──
    st = call(PA, 'GET', '/api/basemap/status')[1]
    check('status: nothing saved, no area before the EOC has a map or a location', st['layers']['topo']['tiles'] == 0 and not st['area']['bounds'], st)
    code, ans = call(PA, 'POST', '/api/basemap/fetch', {})
    check('download with no area says what to set first', code == 400 and 'EOC latitude' in ans.get('error', ''), ans)
    for port in (PA, PB):
        inc = call(port, 'GET', '/api/incident')[1]
        inc.update({'eocName': 'Juniper Plains Stake EOC', 'eocLevel': 'stake', 'eocLat': '40.33', 'eocLon': '-117.53', 'mapPath': str(EXAMPLE), 'name': 'Basemap check'})
        call(port, 'PUT', '/api/incident', inc)
    st = call(PA, 'GET', '/api/basemap/status')[1]
    a = st['area']
    check('status: the default area is the map data, with an estimate of tiles and size', a['source'] == 'map data' and a['bounds'] and a['tiles'] > 0 and a['bytes'] > 0 and a['zmin'] == 8 and a['zmax'] == 15, a)
    check('status: hands the page the street map address from EMCOMM_STREETS_URL', st['streetsUrl'].startswith(f'http://127.0.0.1:{FP}/streets/'), st['streetsUrl'])
    code, ans = call(PA, 'POST', '/api/basemap/fetch', {'zmin': 0, 'zmax': 18, 'bounds': [-125, 30, -100, 45]})
    check('a too-big area is refused with the count, before anything is fetched', code == 400 and 'too big' in ans.get('error', '') and ans.get('tiles', 0) > 25000 and sum(hits.values()) == 0, ans)
    for bad in ({'layers': ['roads']}, {'bounds': [10, 10, 5, 5]}, {'bounds': 'all'}, {'zmin': 'x'}, {'zmin': 9, 'zmax': 3}):
        code, ans = call(PA, 'POST', '/api/basemap/fetch', bad)
        check(f'a bad request is refused: {json.dumps(bad)}', code == 400 and not ans.get('ok'), ans)
    code, ans = call(PA, 'POST', '/api/basemap/fetch', {}, headers={'Origin': 'http://example.invalid'})
    check('another site\'s page cannot start a download', code == 403, ans)
    own = subprocess.run([sys.executable, '-c', "import eoc_server as e; print(e._basemap_fetch_request({}, False)[0])"], cwd=str(tmp / 'srvA' / 'eoc'),
                         capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60, env=base_env)
    check('a phone or another laptop on the Wi-Fi cannot start a download (only the person at the EOC laptop)', own.stdout.strip().endswith('403'), own.stdout[-200:] + own.stderr[-300:])
    # the map views' area, saved at zoom 8 to 11 (small and quick against the fake server)
    code, ans = call(PA, 'POST', '/api/basemap/fetch', {'layers': ['topo', 'imagery'], 'zmin': 8, 'zmax': 11})
    check('download starts in the background and answers at once', code == 200 and ans.get('ok') and ans['job']['running'], ans)
    code2, ans2 = call(PA, 'POST', '/api/basemap/fetch', {'zmin': 8, 'zmax': 11})
    check('a second download while one runs is refused', code2 == 409, ans2)
    st = wait_job(PA)
    j = st['job']
    files = sorted(CACHE.rglob('*.png'))
    check('download finishes: every tile saved or counted as failed', not j['running'] and j['saved'] + j['failed'] == j['total'] == ans['tiles'] and j['saved'] > 0, j)
    check('a tile the source cannot give is counted, retried a little, and the job carries on', j['failed'] > 0 and hits['failed'] >= j['failed'] * 2 and j['errors'], (j['failed'], hits['failed']))
    check('tiles land in the scratch settings folder as basemap/<layer>/<z>/<y>/<x>.png', len(files) == j['saved'] and all(re.search(r'basemap[\\/](topo|imagery)[\\/]\d+[\\/]\d+[\\/]\d+\.png$', str(f)) for f in files), len(files))
    check('status: per layer saved tiles, size, zooms and area', st['layers']['topo']['tiles'] > 0 and st['layers']['topo']['zooms'] == [8, 11] and st['layers']['topo']['bytes'] > 0 and st['layers']['topo']['bounds'], st['layers']['topo'])
    check('the request names a generic program, nothing personal', agents == {'EMCOMM-EOC-offline-basemap/1.0'}, agents)
    before = hits['topo'] + hits['imagery']
    code, ans = call(PA, 'POST', '/api/basemap/fetch', {'layers': ['topo'], 'zmin': 8, 'zmax': 11})
    j = wait_job(PA)['job']
    check('a second download skips every tile already saved', j['skipped'] == j['total'] and j['saved'] == 0 and hits['topo'] + hits['imagery'] == before, j)
    f = files[0]
    rel = f.relative_to(CACHE).parts       # layer, z, y, x.png
    code, body, hd = call(PA, 'GET', f'/basemap/{rel[0]}/{rel[1]}/{rel[2]}/{rel[3][:-4]}', raw=True)
    check('/basemap/<layer>/<z>/<y>/<x> serves a saved tile as image/png with a long cache time', code == 200 and body[:4] == b'\x89PNG' and hd.get('Content-Type') == 'image/png' and 'max-age' in (hd.get('Cache-Control') or ''), (code, hd.get('Content-Type')))
    for bad in ('/basemap/topo/1/0/99', '/basemap/roads/8/1/1', '/basemap/topo/x/1/1', '/basemap/topo/8/../../eoc-settings', '/basemap/topo/8/1/1/2',
                '/basemap/..%2F..%2Feoc-settings.json', '/basemap/topo/8/1/-1'):
        code, body, hd = call(PA, 'GET', bad, raw=True)
        check(f'{bad} is refused (404)', code == 404, code)

    for _ in range(80):
        try:
            call(PS, 'GET', '/api/info')
            break
        except Exception:
            time.sleep(0.25)
    sst = call(PS, 'GET', '/api/basemap/status')[1]
    check('simulator: sees the tiles the EOC server saved on this laptop', (sst.get('layers') or {}).get('topo', {}).get('zooms') == [8, 11], sst)
    code, body, hd = call(PS, 'GET', f'/basemap/{rel[0]}/{rel[1]}/{rel[2]}/{rel[3][:-4]}', raw=True)
    check('simulator: serves a saved tile as image/png', code == 200 and body[:4] == b'\x89PNG' and hd.get('Content-Type') == 'image/png', code)
    code, body, hd = call(PS, 'GET', '/basemap/topo/8/../../simulator-settings', raw=True)
    check('simulator: any other /basemap/ path is refused (404)', code == 404, code)

    # ── browsers ──
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sync_playwright = None
        print('SKIP browsers: playwright is not installed')
    if sync_playwright:
        with sync_playwright() as p:
            engines = {'Chromium': lambda: p.chromium.launch(channel='chrome'), 'Firefox': p.firefox.launch, 'WebKit': p.webkit.launch}
            for name, launch in engines.items():
                try:
                    b = launch()
                except Exception:
                    if name != 'Chromium':
                        raise
                    b = p.chromium.launch()
                ctx = b.new_context(viewport={'width': 1366, 'height': 768})
                pg = ctx.new_page()
                errs = []
                pg.on('pageerror', lambda e: errs.append(str(e)))
                pg.on('dialog', lambda d: d.dismiss())
                s0 = hits['streets']
                pg.goto(f'http://127.0.0.1:{PA}/', wait_until='load')
                pg.evaluate("switchTab('map')")
                pg.wait_for_function("MAP && MAP.loaded() && MAP.basemap().drawn > 0", timeout=15000)
                stt = pg.evaluate('MAP.basemap()')
                note = pg.inner_text('#map-basemap-note')
                check(f'{name}: the Map tab draws the online street map by default, with its attribution', stt['shown'] == 'streets' and hits['streets'] > s0 and 'OpenStreetMap contributors' in note, (stt, note))
                pg.select_option('#map-basemap', 'topo')
                pg.wait_for_function("MAP.basemap().shown === 'topo' && MAP.basemap().drawn > 0", timeout=10000)
                note = pg.inner_text('#map-basemap-note')
                # canvas pixels: the saved area outside the units shows the topo tile (washed), the middle of the units shows the overlays on top
                px = pg.evaluate("""() => { const c = document.getElementById('map-canvas'), x = c.getContext('2d'), d = window.devicePixelRatio || 1;
                    const g = (sx, sy) => Array.from(x.getImageData(Math.round(sx * d), Math.round(sy * d), 1, 1).data).slice(0, 3);
                    const grid = []; for (let i = 1; i < 40; i++) for (let k = 1; k < 20; k++) grid.push(g(c.clientWidth * i / 40, c.clientHeight * k / 20));
                    return {grid: grid, mid: g(c.clientWidth / 2, c.clientHeight / 2)}; }""")
                t = COLOURS['topo']
                washed = [round(v * 0.88 + 255 * 0.12) for v in t]
                near = lambda q, r, tol: all(abs(q[i] - r[i]) <= tol for i in range(3))
                check(f'{name}: Topo (offline) draws the saved tiles from this EOC server, with the USGS attribution', 'USGS The National Map' in note and any(near(q, washed, 6) for q in px['grid']), (px['mid'], washed, note))
                check(f'{name}: the units and markers are drawn on top of the basemap', not near(px['mid'], washed, 12), px)
                pg.reload(wait_until='load')
                pg.evaluate("switchTab('map')")
                pg.wait_for_function("MAP && MAP.loaded() && MAP.basemap().drawn > 0", timeout=15000)
                check(f'{name}: the choice is remembered by this browser', pg.input_value('#map-basemap') == 'topo' and pg.evaluate('MAP.basemap().shown') == 'topo')
                pg.evaluate("switchTab('setup')")
                pg.wait_for_function("document.getElementById('basemap-saved').textContent.indexOf('Topo') >= 0", timeout=8000)
                setup = pg.inner_text('#basemap-box')
                check(f'{name}: Setup shows the basemap block: area, estimate, the button, what is saved', 'Download basemap now (needs internet)' in setup and 'About' in setup and 'Saved on this laptop: Topo' in setup, setup[:300])
                check(f'{name}: no page error on the Map tab or Setup', not errs, errs[:2])
                ctx.close()
                # no internet for the street map: falls back to the saved Topo map, says so, and does not keep asking
                ctx = b.new_context(viewport={'width': 1366, 'height': 768})
                pg = ctx.new_page()
                errs = []
                failed = []
                pg.on('pageerror', lambda e: errs.append(str(e)))
                pg.on('requestfailed', lambda r: failed.append(r.url) if str(DEAD) in r.url else None)
                pg.goto(f'http://127.0.0.1:{PB}/', wait_until='load')
                pg.evaluate("switchTab('map')")
                pg.wait_for_function("MAP && MAP.loaded() && MAP.basemap().shown === 'topo' && MAP.basemap().drawn > 0", timeout=15000)
                note = pg.inner_text('#map-basemap-note')
                vis = pg.is_visible('#map-basemap-note')
                n1 = len(failed)
                pg.evaluate("for (var i = 0; i < 30; i++) MAP.draw()")
                pg.wait_for_timeout(1500)
                check(f'{name}: street map unreachable -> the saved Topo map, with the note "Street map needs internet"', vis and 'Street map needs internet' in note and pg.evaluate('MAP.basemap().choice') == 'streets', note)
                check(f'{name}: no retry storm: redraws ask the street map nothing more while it is down', len(failed) == n1 and n1 <= 40, (n1, len(failed)))
                check(f'{name}: no page error with no street map', not errs, errs[:2])
                ctx.close()
                ctx = b.new_context(viewport={'width': 1920, 'height': 1080})
                pg = ctx.new_page()
                errs = []
                pg.on('pageerror', lambda e: errs.append(str(e)))
                pg.goto(f'http://127.0.0.1:{PB}/wall', wait_until='load')
                pg.wait_for_timeout(2500)
                check(f'{name}: the wall loads with the basemap module and no page error', not errs, errs[:2])
                ctx.close()
                if name == 'Chromium':      # the simulator console: Topo under its own map
                    ctx = b.new_context(viewport={'width': 1366, 'height': 768})
                    pg = ctx.new_page()
                    errs = []
                    pg.on('pageerror', lambda e: errs.append(str(e)))
                    pg.on('dialog', lambda d: d.dismiss())
                    pg.goto(f'http://127.0.0.1:{PS}/', wait_until='load')
                    pg.wait_for_function('SIM.BM.status', timeout=10000)
                    pg.evaluate("() => { const s = document.getElementById('l-basemap'); s.value = 'topo'; s.dispatchEvent(new Event('change')); }")
                    pg.evaluate("() => { const W = 2 * Math.PI * 6378137, t = W / 1024, r = SIM.BM.status.layers.topo.ranges['10'];"
                                " SIM.fitBox([-W / 2 + r[0] * t, W / 2 - (r[3] + 1) * t, -W / 2 + (r[2] + 1) * t, W / 2 - r[1] * t], 0.9); SIM.draw(); }")
                    pg.wait_for_function('SIM.BM.drawn > 0', timeout=10000)
                    note = pg.inner_text('#l-basemap-note')
                    check(f'{name}: the simulator console draws the saved Topo map under its map, with the USGS attribution', 'USGS The National Map' in note and not errs, (note, errs[:2]))
                    ctx.close()
                b.close()
finally:
    for pr in procs:
        pr.terminate()
    for pr in procs:
        try:
            pr.wait(timeout=10)
        except Exception:
            pr.kill()
    fake.shutdown()
    if '--keep' not in sys.argv:
        shutil.rmtree(tmp, ignore_errors=True)
print(f'\n{sum(res)}/{len(res)} basemap checks passed')
sys.exit(0 if all(res) else 1)
