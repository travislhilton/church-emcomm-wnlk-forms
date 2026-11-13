"""Map drill with an organization pack on a SCRATCH EOC + simulator (never the live install). Checklist J15.
Run on the Windows host (needs Playwright and internet); a real export goes over with its contact columns emptied
first and is deleted afterwards (CONTINUE.md, J15).

Privacy: prints counts and fixed check labels only (no unit, person or place name, no contact).
Screenshots blank every page text and every canvas label, and block the paper-map overlay images.
The simulator runs pseudonymized, points only at the scratch EOC, and never starts a run (it sends nothing).

usage: python maps_drill.py --pack <export root> --label <name> --out <dir> [--pack-from-backup <settings json>]
"""
import json, os, pathlib, shutil, subprocess, sys, time, urllib.request, urllib.error

A = dict(zip(sys.argv[1::2], sys.argv[2::2]))
REPO = pathlib.Path(__file__).resolve().parents[1]
PY = sys.executable
OUT = pathlib.Path(A['--out']); LABEL = A['--label']
if '--pack-from-backup' in A:
    PACK = json.loads(pathlib.Path(A['--pack-from-backup']).read_text(encoding='utf-8-sig'))['packPath']
else:
    PACK = A['--pack']
EOC, SIM = 8380, 8390
U, US = f'http://127.0.0.1:{EOC}', f'http://127.0.0.1:{SIM}'
DEAD = 'http://127.0.0.1:9'
root = OUT / 'run'; shots = OUT / 'shots'
shutil.rmtree(root, ignore_errors=True); shots.mkdir(parents=True, exist_ok=True)
res = []


def check(label, ok, detail=''):
    res.append(bool(ok)); print(('PASS ' if ok else 'FAIL ') + label + ('' if ok or detail == '' else f' -- {detail}'), flush=True)


def call(port_url, method, path, body=None, timeout=60):
    data = None if body is None else json.dumps(body).encode()
    rq = urllib.request.Request(port_url + path, data=data, method=method, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(rq, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b'{}')
        except Exception:
            return e.code, {}


procs = []


def start(offline):
    env = dict(os.environ, LOCALAPPDATA=str(root / 'local'), EMCOMM_DOCUMENTS=str(root / 'docs'), EMCOMM_DISCOVERY='off',
               PYTHONIOENCODING='utf-8')
    if offline:
        env.update(EMCOMM_BASEMAP_URL=DEAD + '/{layer}/{z}/{y}/{x}', EMCOMM_STREETS_URL=DEAD + '/{z}/{x}/{y}')
    else:
        env.pop('EMCOMM_BASEMAP_URL', None); env.pop('EMCOMM_STREETS_URL', None)
    (root / 'local').mkdir(parents=True, exist_ok=True); (root / 'docs').mkdir(parents=True, exist_ok=True)
    tag = 'off' if offline else 'on'
    procs.append(subprocess.Popen([PY, str(REPO / 'eoc' / 'eoc_server.py'), f'--port={EOC}'], cwd=str(REPO / 'eoc'), env=env,
                                  stdout=open(root / f'eoc-{tag}.log', 'w'), stderr=subprocess.STDOUT))
    procs.append(subprocess.Popen([PY, str(REPO / 'simulation' / 'sim_server.py'), '--data', PACK, '--privacy', 'pseudonymized', str(SIM)],
                                  cwd=str(REPO / 'simulation'), env=env, stdout=open(root / f'sim-{tag}.log', 'w'), stderr=subprocess.STDOUT))
    for u in (U + '/api/status', US + '/api/info'):
        for _ in range(120):
            try:
                urllib.request.urlopen(u, timeout=3); break
            except urllib.error.HTTPError:
                break
            except Exception:
                time.sleep(0.5)


def stop():
    for p in procs:
        p.terminate()
    for p in procs:
        try:
            p.wait(timeout=10)
        except Exception:
            p.kill()
    procs.clear(); time.sleep(1)


BLANK = """(() => { const P = CanvasRenderingContext2D.prototype; P.fillText = function () {}; P.strokeText = function () {};
  const add = () => { const s = document.createElement('style'); s.textContent = '*{color:transparent!important;text-shadow:none!important;-webkit-text-fill-color:transparent!important} ::placeholder{color:transparent!important}'; (document.head || document.documentElement).appendChild(s); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', add); else add(); })();"""


def page(b, w=1366, h=768):
    ctx = b.new_context(viewport={'width': w, 'height': h})
    ctx.add_init_script(BLANK)
    # the paper-map overlay images never reach a screenshot (they can carry printed names)
    ctx.route('**/overlays/**', lambda r: r.abort() if r.request.resource_type == 'image' else r.continue_())
    ctx.route('**/map/maps/**', lambda r: r.abort())
    pg = ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(type(e).__name__))
    pg.on('dialog', lambda d: d.dismiss())
    return ctx, pg, errs


FOCUS = """async (half) => { const g = await (await fetch('/map/buildings.geojson')).json();
  const pts = g.features.map(f => f.geometry && f.geometry.coordinates).filter(c => c && typeof c[0] === 'number');
  const xs = pts.map(c => c[0]).sort((a, b) => a - b), ys = pts.map(c => c[1]).sort((a, b) => a - b);
  const m = EMCOMM_MAP.merc(xs[xs.length >> 1], ys[ys.length >> 1]);
  MAP.focusOn([m[0] - half, m[1] - half, m[0] + half, m[1] + half]); MAP.draw(); return pts.length; }"""

try:
    start(False)
    # ── the EOC: map data from the pack, the basemap downloaded for its area ──
    code, _ = call(U, 'PUT', '/api/incident', {'mapPath': PACK, 'level': 'area'})
    check('scratch EOC takes the pack as its map data folder', code == 200, code)
    st = call(U, 'GET', '/api/map/status')[1]
    check('EOC map status: map data found', bool(st) and st.get('ok', True) is not False, list(st)[:6])
    bs = call(U, 'GET', '/api/basemap/status')[1]; area = bs.get('area') or {}
    b = area.get('bounds') or []
    print(f"  basemap area from: {area.get('source')}; size about {round((b[2]-b[0])*85, 1) if b else '?'} x {round((b[3]-b[1])*111, 1) if b else '?'} km; "
          f"estimate {area.get('tiles')} tiles, {round((area.get('bytes') or 0) / 1048576)} MB (zoom {area.get('zmin')}-{area.get('zmax')})", flush=True)
    check('the basemap area comes from the pack\'s map data', area.get('source') == 'map data', area.get('source'))
    t0 = time.time()
    code, f = call(U, 'POST', '/api/basemap/fetch', {})
    zmax = 15
    while code == 400 and 'too big' in str(f.get('error', '')) and zmax > 10:
        print(f"  default download refused as too big ({f.get('tiles')} tiles); trying zoom 8-{zmax - 1}", flush=True)
        zmax -= 1; code, f = call(U, 'POST', '/api/basemap/fetch', {'zmin': 8, 'zmax': zmax})
    check(f'the basemap download starts (zoom 8-{zmax}, {f.get("tiles")} tiles)', code == 200 and f.get('ok'), (code, f.get('error')))
    job = {}
    while True:
        time.sleep(10); job = call(U, 'GET', '/api/basemap/status')[1].get('job') or {}
        if not job.get('running') or time.time() - t0 > 3600:
            break
    mins = round((time.time() - t0) / 60, 1)
    print(f"  download: {job.get('saved')} saved, {job.get('skipped')} skipped, {job.get('failed')} failed of {job.get('total')} in {mins} min, "
          f"{round((job.get('bytes') or 0) / 1048576)} MB", flush=True)
    check('the basemap download finishes with few or no failed tiles', job.get('total') and not job.get('running') and (job.get('failed') or 0) <= max(5, job['total'] // 200), job.get('message'))

    # ── the simulator: pack loaded pseudonymized, pointed only at the scratch EOC, no run ──
    code, _ = call(US, 'POST', '/api/settings', {'eocUrl': U})
    info = call(US, 'GET', '/api/info')[1]
    check('simulator: pack loaded, pseudonymized, pointed at the scratch EOC only', info.get('ok') and info.get('privacy') == 'pseudonymized' and info.get('eocUrl') == U,
          (info.get('ok'), info.get('privacy'), info.get('eocUrl') == U))
    c = info.get('counts') or {}
    print(f"  simulator pack counts: boundaries {c.get('organization_boundaries')}, locations {c.get('organization_locations')}, buildings {c.get('buildings')}, overlays {c.get('overlays')}, missing images {c.get('missingImages')}", flush=True)
    sbs = call(US, 'GET', '/api/basemap/status')[1]
    check('simulator sees the saved Topo and Imagery', all(((sbs.get('layers') or {}).get(k) or {}).get('zooms') for k in ('topo', 'imagery')))

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        try:
            br = p.chromium.launch(channel='chrome')
        except Exception:
            br = p.chromium.launch()

        def mc_pass(tag, offline):
            ctx, pg, errs = page(br)
            pg.goto(U + '/', wait_until='load'); pg.evaluate("switchTab('map')")
            pg.wait_for_function('MAP && MAP.loaded()', timeout=30000)
            for lvl in ('area', 'stake'):
                pg.evaluate(f"MAP.setLevel('{lvl}'); MAP.fit()")
                n = pg.evaluate('MAP.units().length')
                check(f'[{tag}] Message Center map: {lvl} level draws its units ({n})', n > 0)
            pg.evaluate("MAP.setLevel('area'); MAP.fit()")
            for layer in ('streets', 'topo', 'imagery', 'none'):
                pg.select_option('#map-basemap', layer)
                want = layer if not (offline and layer == 'streets') else 'topo'
                if layer == 'none':
                    pg.wait_for_timeout(800); ok = not pg.evaluate('MAP.basemap().shown')
                else:
                    try:
                        pg.wait_for_function(f"MAP.basemap().shown === '{want}' && MAP.basemap().drawn > 0", timeout=20000); ok = True
                    except Exception:
                        ok = False
                pg.wait_for_timeout(2500)
                st = pg.evaluate('MAP.basemap()')
                lab = f'[{tag}] Map tab, {layer}' + (' -> falls back to the saved Topo, says "Street map needs internet"' if want != layer else '')
                if want != layer:
                    ok = ok and 'Street map needs internet' in (st.get('note') or '')
                check(lab, ok, {k: st.get(k) for k in ('choice', 'shown', 'drawn')})
                pg.screenshot(path=str(shots / f'{tag}-mc-{layer}-fit.png'))
                if layer in ('streets', 'topo', 'imagery') and not (offline and layer == 'streets'):
                    for half in (6000, 1500):
                        pg.evaluate(FOCUS, half); pg.wait_for_timeout(3500)
                        pg.screenshot(path=str(shots / f'{tag}-mc-{layer}-{half}m.png'))
                    pg.evaluate('MAP.fit()')
            check(f'[{tag}] no page error on the Map tab', not errs, errs[:3])
            ctx.close()
            ctx, pg, errs = page(br, 1920, 1080)
            pg.goto(U + '/wall', wait_until='load'); pg.wait_for_timeout(6000)
            pg.screenshot(path=str(shots / f'{tag}-wall.png'))
            check(f'[{tag}] the wall display loads with its map and no page error', not errs, errs[:3])
            ctx.close()

        def sim_pass(tag):
            ctx, pg, errs = page(br)
            pg.goto(US + '/', wait_until='load'); pg.wait_for_function('SIM.BM.status', timeout=20000)
            for layer in ('topo', 'imagery'):
                pg.evaluate("(l) => { const s = document.getElementById('l-basemap'); s.value = l; s.dispatchEvent(new Event('change')); }", layer)
                pg.evaluate("() => { const W = 2 * Math.PI * 6378137, t = W / 1024, r = SIM.BM.status.layers.topo.ranges['10'];"
                            " SIM.fitBox([-W / 2 + r[0] * t, W / 2 - (r[3] + 1) * t, -W / 2 + (r[2] + 1) * t, W / 2 - r[1] * t], 0.95); SIM.draw(); }")
                try:
                    pg.wait_for_function('SIM.BM.drawn > 0', timeout=15000); ok = True
                except Exception:
                    ok = False
                pg.wait_for_timeout(3000)
                check(f'[{tag}] simulator map draws the saved {layer} under the units', ok)
                pg.screenshot(path=str(shots / f'{tag}-sim-{layer}.png'))
            check(f'[{tag}] no page error on the simulator console', not errs, errs[:3])
            ctx.close()

        mc_pass('online', False); sim_pass('online')
        stop(); start(True)
        mc_pass('offline', True); sim_pass('offline')
        br.close()
    # the overlay images themselves (served, counted, never shown here)
    man = call(US, 'GET', '/data/simulator/overlays/manifest.json')[1]
    items = man if isinstance(man, list) else (man.get('overlays') or man.get('items') or [])
    print(f'  overlay manifest entries: {len(items)}', flush=True)
finally:
    stop()
    shutil.rmtree(root, ignore_errors=True)
print(f'RESULT {LABEL}: {sum(res)}/{len(res)} passed', flush=True)
