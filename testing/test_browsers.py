#!/usr/bin/env python3
"""Anyone may bring any device for a role that does not need Winlink: the pages must work in every browser engine.

Runs a scratch EOC server and simulator (only Windows hosts in real use) and opens every page people use in Chromium
(Chrome, Edge, Android, Chromebook), Firefox and WebKit (Safari, every iPhone browser) at phone, tablet and laptop
sizes. Each page must load with no script error, and a page people use on a phone or tablet must fit the width.
Then, in each engine, a volunteer types into the real form: Send to EOC files it, and Save to Outbox survives a reload.

    python testing/test_browsers.py

Needs Playwright (python -m pip install playwright; python -m playwright install firefox webkit), with Chrome installed.
"""
import functools
import http.server
import json
import os
os.environ.setdefault('EMCOMM_DISCOVERY', 'test')   # this suite's EOC servers hear only each other; a real EOC on the LAN ignores them
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print('SKIP: playwright is not installed (python -m pip install playwright; python -m playwright install firefox webkit)')
    sys.exit(0)

REPO = pathlib.Path(__file__).resolve().parent.parent
PE, PS, PW = 8480, 8490, 8481
PE2 = 8483        # a second, fresh EOC server: another operator's computer (Load a setup...)
SIZES = {'phone': (390, 844), 'tablet': (820, 1180), 'laptop': (1366, 768)}
# page -> the sizes at which it must fit with no sideways scroll. The wall is a big screen; it must only load.
EOC = f'http://127.0.0.1:{PE}'
EOC2 = f'http://127.0.0.1:{PE2}'
SIM = f'http://127.0.0.1:{PS}'
WEB = f'http://127.0.0.1:{PW}'
PAGES = {
    'portal': (f'{WEB}/forms/index.html', ('phone', 'tablet', 'laptop')),
    'Comms Sheet page': (f'{WEB}/forms/comms.html', ('phone', 'tablet', 'laptop')),
    'phone page /m': (f'{EOC}/m', ('phone', 'tablet', 'laptop')),
    'Disaster Report form': (f'{EOC}/forms/dr', ('phone', 'tablet', 'laptop')),
    'Supply Order form': (f'{EOC}/forms/so', ('phone', 'tablet', 'laptop')),
    'Work Crew Log form': (f'{EOC}/forms/wcl', ('phone', 'tablet', 'laptop')),
    'Message Center': (f'{EOC}/', ('phone', 'tablet', 'laptop')),
    'wall display': (f'{EOC}/wall', ()),
    'simulator console': (f'{SIM}/', ('tablet', 'laptop')),
    'drill results /results': (f'{SIM}/results', ('phone', 'tablet', 'laptop')),
}
res = []


def check(label, ok, detail=''):
    ok = bool(ok)
    res.append(ok)
    print(('PASS ' if ok else 'FAIL ') + label + (' -- ' + str(detail)[:260] if detail and not ok else ''), flush=True)


def call(url):
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read().decode('utf-8'))


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


class QuietServer(http.server.ThreadingHTTPServer):
    def handle_error(self, request, client_address):      # a browser closing a page mid-request is not a failure
        pass


tmp = pathlib.Path(tempfile.mkdtemp(prefix='emcomm_browsers_'))
env = dict(os.environ, PYTHONIOENCODING='utf-8', LOCALAPPDATA=str(tmp / 'appdata'), USERPROFILE=str(tmp / 'home'), EMCOMM_DOCUMENTS=str(tmp / 'documents'),
           EMCOMM_STREETS_URL='http://127.0.0.1:9/{z}/{x}/{y}.png')   # the online street map: never the internet from a test
if os.name != 'nt':      # macOS and Linux take the home folder from HOME, not USERPROFILE: keep the servers off the real one
    (tmp / 'home').mkdir()
    env['HOME'] = str(tmp / 'home')
work = tmp / 'site'
(work / 'eoc').mkdir(parents=True)
for f in ('eoc_server.py', 'EOC_Message_Center.html', 'EOC_Wall_Display.html', 'EOC_Phone.html', 'readout.py'):
    shutil.copy2(REPO / 'eoc' / f, work / 'eoc' / f)
shutil.copytree(REPO / 'templates', work / 'templates')
shutil.copytree(REPO / 'simulation', work / 'simulation', ignore=shutil.ignore_patterns('__pycache__', 'runs'))
log1, log2 = open(tmp / 'eoc.log', 'w', encoding='utf-8'), open(tmp / 'sim.log', 'w', encoding='utf-8')
procs = [subprocess.Popen([sys.executable, '-u', 'eoc_server.py', str(PE)], cwd=str(work / 'eoc'), stdout=log1, stderr=subprocess.STDOUT, env=env),
         subprocess.Popen([sys.executable, '-u', 'sim_server.py', str(PS)], cwd=str(work / 'simulation'), stdout=log2, stderr=subprocess.STDOUT, env=env)]
drills = tmp / 'Copied here' / 'Drills'
shutil.copytree(REPO / 'simulation' / 'example' / 'juniper-plains', drills / 'BRF-1 participant package' / '2 Organization pack', ignore=shutil.ignore_patterns('runs', 'local-roles.json'))
(drills / 'BRF-1 participant package' / '1 Reference cards').mkdir()
(drills / 'BRF-1 participant package 2026-11-04.zip').write_bytes(b'PK')
work2 = tmp / 'site2'        # the second operator's computer: its own copy, database, settings and Documents
(work2 / 'eoc').mkdir(parents=True)
for f in ('eoc_server.py', 'EOC_Message_Center.html', 'EOC_Wall_Display.html', 'EOC_Phone.html', 'readout.py'):
    shutil.copy2(REPO / 'eoc' / f, work2 / 'eoc' / f)
shutil.copytree(REPO / 'templates', work2 / 'templates')
env2 = dict(env, LOCALAPPDATA=str(tmp / 'appdata2'), EMCOMM_DOCUMENTS=str(tmp / 'documents2'))
log3 = open(tmp / 'eoc2.log', 'w', encoding='utf-8')
procs.append(subprocess.Popen([sys.executable, '-u', 'eoc_server.py', str(PE2)], cwd=str(work2 / 'eoc'), stdout=log3, stderr=subprocess.STDOUT, env=env2))
web = QuietServer(('127.0.0.1', PW), functools.partial(Quiet, directory=str(REPO)))
threading.Thread(target=web.serve_forever, daemon=True).start()


def open_page(browser, size, url):
    w, h = SIZES[size] if size in SIZES else (1920, 1080)      # 'tv': the wall's own size
    ctx = browser.new_context(viewport={'width': w, 'height': h})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('dialog', lambda d: d.dismiss())
    pg.goto(url, wait_until='load', timeout=30000)
    pg.wait_for_timeout(700)
    return ctx, pg, errs


try:
    for port, path in ((PE, '/api/status'), (PS, '/api/info'), (PE2, '/api/status')):
        for _ in range(60):
            try:
                call(f'http://127.0.0.1:{port}{path}')
                break
            except Exception:
                time.sleep(0.25)
    with sync_playwright() as p:
        engines = {'Chromium': lambda: p.chromium.launch(channel='chrome'), 'Firefox': lambda: p.firefox.launch(), 'WebKit': lambda: p.webkit.launch()}
        for name, launch in engines.items():
            b = launch()
            ctx, pg, _ = open_page(b, 'tablet', f'{WEB}/forms/index.html')
            print(f'{name}: a {SIZES["tablet"][0]} px tablet lays out at {pg.evaluate("window.innerWidth")} px here (a scaled Windows display narrows WebKit)', flush=True)
            ctx.close()
            for page, (url, fits) in PAGES.items():
                for size in SIZES:
                    ctx, pg, errs = open_page(b, size, url)
                    wide = pg.evaluate('document.documentElement.scrollWidth - document.documentElement.clientWidth')
                    label = f'{name} {size}: {page}'
                    check(f'{label} loads with no script error', not errs, errs[:2])
                    if size in fits:
                        check(f'{label} fits the width', wide <= 1, f'{wide} px too wide')
                    ctx.close()
            # on the EOC Wi-Fi: type into the real form, press the real Send button, and the EOC files it
            mark = f'{name} browser check'
            before = len(call(f'{EOC}/api/messages'))
            ctx, pg, errs = open_page(b, 'phone', f'{EOC}/forms/dr')
            pg.fill('#inc_stake', 'Larkspur Stake')
            pg.fill('#inc_ward', 'Larkspur 1st Ward')
            pg.fill('#inc_type', 'Flood')
            pg.fill('#inc_location', mark)
            pg.click('.emcomm-actions .ea-big.green')
            try:                                       # another EOC on this Wi-Fi: the page asks which one
                pg.click('text=(this one)', timeout=1500)
            except Exception:
                pass
            filed = False
            for _ in range(40):
                msgs = call(f'{EOC}/api/messages')
                if len(msgs) > before and mark in json.dumps(msgs):
                    filed = True
                    break
                time.sleep(0.25)
            check(f'{name}: Send to EOC on the real form files the report', filed and not errs, errs[:2])
            ctx.close()
            # no app at the EOC: the phone page offers the home-screen icon, says what it cannot do, and hides the steps once opened from it
            ctx, pg, errs = open_page(b, 'phone', f'{EOC}/m')
            txt = pg.inner_text('#install-card')
            check(f'{name}: the phone page offers the home-screen icon and says it works only on this Wi-Fi', 'Add to Home Screen' in txt and "works only on this EOC's Wi-Fi" in txt and not errs, txt[:120])
            pg.wait_for_function("!document.getElementById('full-app').textContent.includes('Checking')", timeout=8000)
            check(f'{name}: the phone page settles on the full offline app or on what to do with no internet', 'Going out with no signal' in pg.inner_text('#full-app'))
            ctx.close()
            ctx = b.new_context(viewport={'width': 390, 'height': 844})
            ctx.add_init_script("Object.defineProperty(navigator, 'standalone', {get: function () { return true; }})")
            pg = ctx.new_page()
            pg.goto(f'{EOC}/m', wait_until='load')
            pg.wait_for_timeout(500)
            txt = pg.inner_text('#install-card')
            check(f'{name}: opened from the icon, the page drops the install steps and keeps the Wi-Fi warning', 'Add to Home Screen' not in txt and 'only on this' in txt, txt[:120])
            ctx.close()
            # setting up the simulator as a person does: a participant package copied a few folders deep beside its zip,
            # Browse, real double-clicks (two clicks 150 ms apart at the same spot), the package offers its pack, the
            # drill's settings are offered once the pack loads
            def human_dblclick(page, selector):
                bb = page.locator(selector).first.bounding_box()
                x, y = bb['x'] + 40, bb['y'] + bb['height'] / 2
                page.mouse.click(x, y)
                page.wait_for_timeout(150)
                page.mouse.click(x, y)
                page.wait_for_timeout(700)
            ctx, pg, errs = open_page(b, 'laptop', f'{SIM}/')
            pg.click('button:has-text("Setup")')
            fresh = pg.inner_text('#packinfo')
            check(f'{name}: a new simulator shows no error before a pack is chosen', 'Error' not in fresh and 'not an export' not in fresh, fresh)
            # the first folder listing arrives late (a slow disk): a path typed meanwhile must stay in the box
            pg.evaluate("() => { const f = window.fetch; let n = 0; window.fetch = (u, o) => (String(u).includes('/api/browse') && n++ === 0) ? new Promise(r => setTimeout(r, 800)).then(() => f(u, o)) : f(u, o); }")
            pg.click('#b-browse')
            pg.wait_for_selector('#bx-bg', state='visible', timeout=5000)
            pg.fill('#bx-path', str(drills.parent))
            pg.wait_for_timeout(1200)
            check(f'{name}: a path typed while the first listing loads stays in the box', pg.input_value('#bx-path') == str(drills.parent), pg.input_value('#bx-path'))
            pg.click('#bx-go')
            pg.wait_for_selector('#bx-list button:has-text("Drills")', timeout=6000)
            human_dblclick(pg, '#bx-list button:has-text("Drills")')
            at = pg.input_value('#bx-path')
            check(f'{name}: a double-click opens exactly one folder and the Browse window stays open', pg.is_visible('#bx-bg') and at.endswith('Drills'), at)
            zip_note = pg.inner_text('#bx-list')
            check(f'{name}: a zip file is shown with how to unzip it', 'participant package 2026-11-04.zip' in zip_note and 'unzip it first' in zip_note, zip_note[-200:])
            holds = 'holds a pack' in zip_note
            human_dblclick(pg, '#bx-list button:has-text("BRF-1 participant package")')
            offer = pg.locator('#bx-status [data-use]')
            check(f'{name}: the participant package is marked and offers its 2 Organization pack', holds and offer.count() == 1 and '2 Organization pack' in offer.first.inner_text(), (holds, pg.inner_text('#bx-status')))
            offer.first.click()
            pg.wait_for_function("document.getElementById('packinfo').textContent.includes('stakes')", timeout=15000)
            check(f'{name}: choosing it closes Browse and loads the pack', not pg.is_visible('#bx-bg') and pg.input_value('#packpath').endswith('2 Organization pack'), pg.inner_text('#packinfo')[:120])
            pg.wait_for_selector('#dc-from-pack', timeout=8000)
            pg.click('#dc-from-pack')
            pg.wait_for_function("document.getElementById('dc-eoc').options.length > 0", timeout=8000)
            check(f'{name}: the drill settings in the pack are offered and open with the EOC choices', pg.evaluate("document.getElementById('dc-box').open") and pg.locator('#dc-eoc option').count() > 1 and not errs, (pg.inner_text('#dc-msg')[:120], errs[:2]))
            # Save simulator setup, then Load simulator setup... with that file (N42): the buttons, the preview, Apply
            pg.select_option('#speed', '10')
            with pg.expect_download(timeout=10000) as sdl:
                pg.click('#su-save')
            sim_file = tmp / f'sim-setup-{name}.json'
            sdl.value.save_as(str(sim_file))
            simset = json.loads(sim_file.read_text(encoding='utf-8'))
            pg.select_option('#speed', '1')
            pg.set_input_files('#su-file', str(sim_file))
            pg.wait_for_selector('#su-apply', timeout=8000)
            prev = pg.inner_text('#su-preview')
            pg.click('#su-apply')
            pg.wait_for_function("document.getElementById('su-msg').textContent.includes('Setup loaded')", timeout=8000)
            check(f'{name}: Save simulator setup downloads the file (no contacts), Load simulator setup... previews it and Apply this setup puts the speed back',
                  simset.get('kind') == 'church_emcomm_sim_setup' and simset.get('speed') == 10 and 'contacts' not in simset and 'what will change' in prev
                  and pg.input_value('#speed') == '10' and not errs, (simset.get('speed'), prev[:120], pg.input_value('#speed'), errs[:2]))
            ctx.close()
            # the Message Center: every folder it asks for opens the folder browser, never a typed-path prompt
            ctx = b.new_context(viewport={'width': SIZES['laptop'][0], 'height': SIZES['laptop'][1]})
            pg = ctx.new_page()
            errs = []
            pg.on('pageerror', lambda e: errs.append(str(e)))
            pg.on('dialog', lambda d: d.accept('') if d.type == 'prompt' else d.dismiss())   # the call-sign question: answered blank, as a person may
            pg.goto(f'{EOC}/', wait_until='load')
            pg.wait_for_timeout(700)
            # the first folder listing arrives late (a slow disk): a path typed meanwhile must stay in the box
            pg.evaluate("() => { const f = window.fetch; let n = 0; window.fetch = (u, o) => (String(u).includes('/api/browse') && n++ === 0) ? new Promise(r => setTimeout(r, 800)).then(() => f(u, o)) : f(u, o); }")
            pg.evaluate("browseMapFolder()")
            pg.wait_for_selector('#fb-bg', state='visible', timeout=5000)
            pg.fill('#fb-path', str(work / 'simulation' / 'example'))
            pg.wait_for_timeout(1200)
            check(f'{name}: in the Message Center a path typed while the first listing loads stays in the box', pg.input_value('#fb-path') == str(work / 'simulation' / 'example'), pg.input_value('#fb-path'))
            pg.click('#fb-box button:has-text("Go")')
            pg.wait_for_selector('#fb-list button:has-text("juniper-plains")', timeout=6000)
            marked = 'map data' in pg.inner_text('#fb-list')
            pg.click('#fb-list button:has-text("juniper-plains")')
            pg.wait_for_function("document.getElementById('fb-note').textContent.includes('looks right')", timeout=6000)
            pg.click('#fb-use')
            chosen = pg.input_value('#eoc-map-path')
            pg.evaluate("browseMapFolder()")
            pg.wait_for_selector('#fb-bg', state='visible', timeout=5000)
            pg.fill('#fb-path', str(drills.parent))
            pg.click('#fb-box button:has-text("Go")')
            pg.wait_for_selector('#fb-list button:has-text("Drills")', timeout=6000)
            human_dblclick(pg, '#fb-list button:has-text("Drills")')
            fb_at = pg.input_value('#fb-path')
            check(f'{name}: in the Message Center a double-click opens exactly one folder and the window stays open', pg.is_visible('#fb-bg') and fb_at.endswith('Drills'), fb_at)
            pg.evaluate("fbClose()")
            check(f'{name}: the Map data folder Browse finds the export and fills the box', marked and chosen.endswith('juniper-plains') and not errs, (marked, chosen, errs[:2]))
            drop = tmp / f'drop-{name}'
            drop.mkdir()
            pg.evaluate("configureDrop()")
            pg.wait_for_selector('#fb-bg', state='visible', timeout=5000)
            # let the first listing land: a reply arriving inside fill() (faster than any typing) runs the two paths together
            pg.wait_for_selector('#fb-list:not(.busy)', timeout=6000)
            pg.fill('#fb-path', str(drop))
            pg.click('#fb-box button:has-text("Go")')
            pg.wait_for_function(f"document.getElementById('fb-path').value.endsWith('drop-{name}')", timeout=6000)
            pg.click('#fb-use')
            ok = False
            for _ in range(20):
                if pathlib.Path(call(f'{EOC}/api/drop/status').get('watch_path', '')) == drop:
                    ok = True
                    break
                time.sleep(0.25)
            check(f'{name}: the Drop Folder is chosen with the folder browser and saved', ok and not errs, (call(f'{EOC}/api/drop/status').get('watch_path'), errs[:2]))
            wl = tmp / f'winlink-{name}'
            for d in ('Messages', 'Data'):   # Winlink Express keeps <folder>\\<CALLSIGN>\\Messages and Data
                (wl / 'W7TST' / d).mkdir(parents=True)
            pg.evaluate("configureWatcher()")
            pg.wait_for_selector('#fb-bg', state='visible', timeout=5000)
            # let the first listing land: a reply arriving inside fill() (faster than any typing) runs the two paths together
            pg.wait_for_selector('#fb-list:not(.busy)', timeout=6000)
            pg.fill('#fb-path', str(wl))
            pg.click('#fb-box button:has-text("Go")')
            pg.wait_for_function(f"document.getElementById('fb-path').value.endsWith('winlink-{name}')", timeout=6000)
            pg.click('#fb-use')
            # step 2 of 2 (2026-11-12.4): tick the callsign found in that folder; the only one is ticked already
            pg.wait_for_selector('.wl-call', timeout=6000)
            found = pg.eval_on_selector_all('.wl-call', 'xs => xs.map(x => [x.value, x.checked])')
            pg.click('#modal-confirm-btn')
            ok = False
            for _ in range(20):
                ws = call(f'{EOC}/api/watcher/status')
                if pathlib.Path(ws.get('watch_path', '')) == wl and ws.get('callsigns') == ['W7TST']:
                    ok = True
                    break
                time.sleep(0.25)
            check(f'{name}: the Winlink Express folder is chosen with the folder browser, then its callsign is ticked (no typed prompt), and both are saved',
                  ok and found == [['W7TST', True]] and not errs, (found, ws.get('watch_path'), ws.get('callsigns'), errs[:2]))
            # first run (2026-11-12.4): the Overview's "Set up this EOC" list, the Setup tab's Jump to bar, and Save EOC
            # Identity putting the units covered on the roster (each unit once, however often it is saved)
            pg.evaluate("switchTab('overview')")
            start = pg.inner_text('#ov-start')
            pg.evaluate("switchTab('setup')")
            pg.click('.setup-nav a[href="#comms-card"]')
            pg.wait_for_timeout(400)
            nav_top = pg.evaluate("Math.round(document.getElementById('comms-card').getBoundingClientRect().top)")
            units = [f'Larkspur {name} A Ward', f'Larkspur {name} B Ward']
            pg.fill('#eoc-units', ', '.join(units))
            pg.evaluate('saveEocIdentity()')
            pg.wait_for_timeout(600)
            pg.evaluate('saveEocIdentity()')
            pg.wait_for_timeout(900)
            got = [r['name'] for r in call(f'{EOC}/api/roster') if r.get('name') in units]
            check(f'{name}: first run: the setup list renders, Jump to scrolls its card into view, Save EOC Identity puts each unit covered on the roster once',
                  ('steps left' in start.lower() or start.strip() == '') and nav_top < 140 and sorted(got) == sorted(units) and not errs,
                  (start[:80], nav_top, got, errs[:2]))
            # Comms Sheet gateways (K8): a sheet from before 2026-11-12.2 (free-text mode, out of order) opens with each row's
            # Contingency step chosen and sorted; Holds mail saves; fields this page does not know ride along
            stamp = int(time.time() * 1000) + len(name)
            old = {'org': 'Juniper Plains Stake', 'gateways': [
                {'call': 'W7HFX', 'freq': '7.102', 'mode': 'VARA HF', 'loc': 'Regional'},
                {'call': 'K7EOC-3', 'freq': '145.050', 'mode': 'VARA FM P2P', 'loc': 'Stake EOC', 'future': 'kept'},
                {'call': 'W7PO-10', 'freq': '145.070', 'mode': 'VARA FM RMS Post Office'},
                {'call': 'W7GW-10', 'freq': '145.030', 'mode': 'VARA FM', 'notes': 'wide'}]}
            pg.evaluate("([s, t]) => fetch('/api/comms', {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({sheet: s, updatedMs: t})})", [old, stamp])
            pg.evaluate("loadCommsFromServer()")
            pg.wait_for_function(f"comms.updatedMs === {stamp}", timeout=8000)
            pg.evaluate("_commsEditorStamp = -1; renderCommsEditor()")
            uses = pg.evaluate("[...document.querySelectorAll('table.comms-edit[data-t=gateways] select[data-k=use]')].map(x => x.value)")
            check(f'{name}: an older Comms Sheet opens with each gateway\'s Contingency step chosen, in the order to try them', uses == ['RMS Gateway', 'VARA FM RMS Post Office', 'VARA FM P2P', 'VARA HF'], uses)
            pg.evaluate("document.querySelector('table.comms-edit[data-t=gateways] tbody tr select[data-k=holds]').value = 'Yes'")   # Setup tab, not open
            pg.evaluate("saveComms()")
            gw = []
            for _ in range(20):
                gw = call(f'{EOC}/api/comms').get('sheet', {}).get('gateways') or []
                if gw and gw[0].get('holds') == 'Yes':
                    break
                time.sleep(0.25)
            first, p2p = (gw + [{}, {}])[0], ([g for g in gw if g.get('use') == 'VARA FM P2P'] + [{}])[0]
            check(f'{name}: the Comms Sheet saves Use and Holds mail, a mode older pages read, and a field it does not show',
                  first.get('use') == 'RMS Gateway' and first.get('holds') == 'Yes' and first.get('mode') == 'VARA FM' and first.get('notes') == 'wide'
                  and p2p.get('future') == 'kept' and p2p.get('freq') == '145.050' and not errs, (gw, errs[:2]))
            view = pg.inner_text('#comms-view')
            check(f'{name}: the Comms tab lists the gateways in the order to try them', 0 <= view.find('W7GW-10') < view.find('W7PO-10') < view.find('K7EOC-3') < view.find('W7HFX'), view[:300])
            # the roster changed elsewhere (another operator, the simulator, a roll-up): this screen adopts it on its
            # poll, and its next save (any click) does not put back the roster it had loaded
            unit = f'Roster Test Ward {name}'
            before = call(f'{EOC}/api/roster')
            pg.evaluate("r => fetch('/api/roster', {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(r)})", before + [{'id': 'rt-' + name, 'name': unit}])
            try:
                pg.wait_for_function(f"roster.some(r => r.name === {unit!r})", timeout=12000)
                adopted = True
            except Exception:
                adopted = False
            pg.evaluate("save()"); time.sleep(1)
            kept = any(r.get('name') == unit for r in call(f'{EOC}/api/roster'))
            check(f'{name}: an open Message Center adopts a roster changed elsewhere and its next save keeps it', adopted and kept and not errs, (adopted, kept, errs[:2]))
            pg.evaluate("r => fetch('/api/roster', {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(r)})", before)
            # Share this EOC's setup (F41): Save this EOC's setup here, Load a setup... on a second, fresh EOC server; the same
            # setup afterwards. A file of another kind is refused with where it loads; a folder not on that computer is kept
            pg.evaluate("switchTab('setup')")
            pg.fill('#eoc-name', f'Larkspur Stake EOC {name}')
            pg.fill('#eoc-parent-email', 'parent@example.org')
            pg.fill('#eoc-welfare-winlink', 'W7WSR')
            pg.evaluate('saveEocIdentity()')
            pg.fill('#inc-name', f'{name} share test event')
            pg.select_option('#inc-pace', 'C')
            pg.select_option('#inc-sitrep-hrs', '4')
            pg.evaluate('saveIncident()')
            pg.wait_for_timeout(1200)
            pg.click('#setup-save-btn')
            pg.wait_for_selector('#modal-bg.open', timeout=5000)
            dialog_txt = pg.inner_text('#modal-body')
            pg.check('#setup-with-event')
            with pg.expect_download(timeout=10000) as dl:
                pg.click('#modal-confirm-btn')
            setup_file = tmp / f'setup-{name}.json'
            dl.value.save_as(str(setup_file))
            sdata = json.loads(setup_file.read_text(encoding='utf-8'))
            check(f'{name}: Save this EOC\'s setup writes a church_eoc_setup file (identity, roster names, Comms Sheet, Winlink call sign, folders as hints, the event when ticked; no messages or notes) and says it can hold real contacts',
                  sdata.get('kind') == 'church_eoc_setup' and sdata['identity'].get('eocName') == f'Larkspur Stake EOC {name}' and sdata['winlink']['callsigns'] == ['W7TST']
                  and pathlib.Path(sdata['folders']['winlink']) == wl and sdata['event'].get('pace') == 'C' and sdata.get('comms') and 'msgs' not in sdata and 'notes' not in sdata
                  and 'real contacts' in dialog_txt and dl.value.suggested_filename.startswith('church_eoc_setup_') and not errs, (list(sdata), dialog_txt[-120:], errs[:2]))
            inc1, comms1, roster1 = call(f'{EOC}/api/incident'), call(f'{EOC}/api/comms'), call(f'{EOC}/api/roster')
            ctx2 = b.new_context(viewport={'width': SIZES['laptop'][0], 'height': SIZES['laptop'][1]})
            pg2 = ctx2.new_page()
            errs2 = []
            pg2.on('pageerror', lambda e: errs2.append(str(e)))
            pg2.goto(f'{EOC2}/', wait_until='load')
            pg2.wait_for_function('networkMode === true', timeout=10000)
            pg2.wait_for_timeout(700)
            pg2.evaluate("switchTab('setup')")
            wrong = tmp / f'wrong-{name}.json'
            wrong.write_text(json.dumps({'kind': 'church_emcomm_drill_config', 'eocs': []}), encoding='utf-8')
            pg2.set_input_files('#setup-file', str(wrong))
            pg2.wait_for_function("document.getElementById('setup-msg').textContent.length > 0", timeout=5000)
            refused = pg2.inner_text('#setup-msg')
            check(f'{name}: Load a setup... refuses a drill configuration and points to Load a drill configuration', 'drill configuration' in refused and 'Load a drill configuration' in refused
                  and not pg2.evaluate("document.getElementById('modal-bg').classList.contains('open')"), refused)
            sdata['folders']['map'] = str(tmp / 'not on this computer' / 'map data')
            moved = tmp / f'setup-{name}-moved.json'
            moved.write_text(json.dumps(sdata), encoding='utf-8')
            pg2.set_input_files('#setup-file', str(moved))
            pg2.wait_for_selector('#modal-bg.open', timeout=8000)
            preview = pg2.inner_text('#modal-body')
            pg2.click('#modal-confirm-btn')
            same, inc2 = {}, {}
            for _ in range(40):
                inc2, comms2, roster2, ws2 = call(f'{EOC2}/api/incident'), call(f'{EOC2}/api/comms'), call(f'{EOC2}/api/roster'), call(f'{EOC2}/api/watcher/status')
                same = {k: (v, inc2.get(k)) for k, v in sdata['identity'].items() if inc2.get(k) != v}
                same.update({k: (inc1.get(k), inc2.get(k)) for k in ('name', 'pace', 'sitrepHrs') if inc1.get(k) != inc2.get(k)})
                if comms2.get('sheet') != comms1.get('sheet'):
                    same['comms'] = 'differs'
                if not {r['name'] for r in roster1} <= {r['name'] for r in roster2}:
                    same['roster'] = 'missing units'
                if pathlib.Path(ws2.get('watch_path') or '.') != wl or ws2.get('callsigns') != ['W7TST']:
                    same['winlink'] = (ws2.get('watch_path'), ws2.get('callsigns'))
                if pathlib.Path(call(f'{EOC2}/api/drop/status').get('watch_path') or '.') != drop:
                    same['drop'] = 'not set'
                if not same:
                    break
                time.sleep(0.25)
            check(f'{name}: Load a setup... on a second, fresh EOC server gives the same setup: identity, must-have roles, event PACE and SITREP interval, Comms Sheet, roster units, Winlink folder and call sign, Drop Folder',
                  not same and not errs2, (same, errs2[:2]))
            check(f'{name}: Load a setup... says what will change, and a folder not on this computer is kept as it was',
                  'not on this computer' in preview and 'Comms Sheet' in preview and (inc2.get('mapPath') or '') == '' and 'EOC setup loaded from' in json.dumps(call(f'{EOC2}/api/notes')), (preview[:300], inc2.get('mapPath')))
            ctx2.close()
            ctx.close()
            ctx, pg, errs = open_page(b, 'tv', f'{EOC}/wall')      # the wall is laid out for a TV
            try:
                pg.wait_for_function("document.getElementById('nets').textContent.includes('P2P')", timeout=10000)
            except Exception:
                pass
            nets = pg.inner_text('#nets')
            check(f'{name}: the wall shows the first gateway (holds mail) and the stake P2P frequency', 'RMS W7GW-10' in nets and 'holds mail' in nets and 'P2P K7EOC-3' in nets and '145.050' in nets and not errs, (nets[:300], errs[:2]))
            ctx.close()
            ctx, pg, errs = open_page(b, 'phone', f'{WEB}/forms/comms.html')
            bundle = {'kind': 'church_comms_sheet', 'v': 1, 'updatedMs': stamp, 'sheet': call(f'{EOC}/api/comms')['sheet']}
            pg.evaluate("d => { localStorage.setItem('church_comms_sheet', JSON.stringify(d)); location.reload(); }", bundle)
            pg.wait_for_selector('#view .card', timeout=8000)
            pv = pg.inner_text('#view')
            check(f'{name}: the portal Comms Sheet shows each gateway\'s step, in order, and whether it holds mail',
                  0 <= pv.find('RMS Gateway W7GW-10') < pv.find('VARA FM P2P K7EOC-3') < pv.find('VARA HF W7HFX') and 'Holds mail: Yes' in pv and not errs, (pv[:300], errs[:2]))
            ctx.close()
            # no signal: the report saved from the portal's form is still in the Outbox after the portal reloads
            ctx, pg, errs = open_page(b, 'phone', f'{WEB}/templates/disaster-report/Church_of_Jesus_Christ_Disaster_Report_Worker.html')
            pg.fill('#inc_stake', 'Larkspur Stake')
            pg.fill('#inc_location', mark + ' outbox')
            pg.click('.emcomm-actions .ea-big.green')
            saved = False
            try:
                pg.wait_for_selector('text=Saved to the Outbox', timeout=8000)
                saved = True
            except Exception:
                pass
            pg.goto(f'{WEB}/forms/index.html', wait_until='load')
            pg.wait_for_timeout(900)
            kept = '1 report saved on this phone' in pg.inner_text('body')
            check(f'{name}: Save to Outbox keeps the report after the portal reloads', saved and kept and not errs, (saved, kept, errs[:2]))
            ctx.close()
            # Contingency (card 1 C, card 2 B): the file a volunteer saves on the phone, loaded into the Winlink template
            # with Load Data, keeps THIS IS AN EXERCISE and every box (the phone writes true / false, Winlink's Save Data 1 / 0)
            for d, worker, initial, fill, boxes, tag in (
                    ('disaster-report', 'Church_of_Jesus_Christ_Disaster_Report_Worker.html', 'Church_of_Jesus_Christ_Disaster_Report_Initial.html', {'inc_stake': 'Larkspur Stake', 'inc_location': mark + ' radio'}, [], 'DR'),
                    ('supply-order', 'Church_of_Jesus_Christ_Supply_Order_Worker.html', 'Church_of_Jesus_Christ_Supply_Order_Initial.html', {'req_stake': 'Larkspur Stake', 'del_addr': mark + ' radio'}, [], 'SO'),
                    ('work-crew-log', 'Church_of_Jesus_Christ_Work_Crew_Log_Worker.html', 'Church_of_Jesus_Christ_Work_Crew_Log.html', {'chief_stake': 'Larkspur Stake', 'log_location': mark + ' radio'}, ['safety_cert'], 'WCL')):
                ctx, pg, errs = open_page(b, 'phone', f'{WEB}/templates/{d}/{worker}')
                pg.check('#exercise')
                for k, v in fill.items():
                    pg.fill('#' + k, v)
                for k in boxes:
                    pg.check('#' + k)
                saved_file = pathlib.Path(tmp) / f'{name}-{tag}.txt'
                saved_file.write_text(pg.evaluate('getFileContent()'), encoding='utf-8')
                ctx.close()
                ctx, pg, errs = open_page(b, 'laptop', f'{WEB}/templates/{d}/{initial}')
                pg.set_input_files('#fileToLoad', str(saved_file)); pg.wait_for_timeout(500)
                filled = all(pg.input_value('#' + k) == v for k, v in fill.items())
                ticked = pg.is_checked('#exercise') and all(pg.is_checked('#' + k) for k in boxes)
                body = pg.evaluate('buildMsg()')
                check(f'{name}: {tag} file from the phone, loaded into the Winlink template, keeps THIS IS AN EXERCISE and its boxes',
                      filled and ticked and f'[Church-{tag}|exercise=YES|' in body and 'THIS IS AN EXERCISE' in body and not errs, (filled, ticked, body[-160:], errs[:2]))
                ctx.close()
            if name == 'Chromium':
                # Work items: a poll that overlaps this page's own change must not put the older list back (card walk
                # 2026-11-13: an item set Up showed OPEN again for up to 5 s, and a roll-up exported then left it out)
                ctx, pg, errs = open_page(b, 'laptop', f'{EOC}/')
                pg.evaluate("switchTab('actions')"); pg.fill('#act-new-title', f'{name} race item'); pg.click('button:has-text("+ Add")')
                pg.wait_for_timeout(1500)
                aid = next(a['id'] for a in call(f'{EOC}/api/actions') if a['title'] == f'{name} race item')
                held = []
                def hold(route):                                 # the change stays on its way while a poll runs
                    if route.request.method == 'PATCH': held.append(route)
                    else: route.continue_()
                pg.route('**/api/actions/**', hold)
                pg.evaluate(f"patchAction({json.dumps(aid)}, {{status: 'up'}})")
                pg.wait_for_timeout(7000)                        # more than one 5 s poll
                st = pg.evaluate(f"actions.filter(function(a){{return a.id==={json.dumps(aid)};}})[0].status")
                for r in held: r.continue_()
                pg.wait_for_timeout(1500)
                pg.unroute('**/api/actions/**')
                server = next(a['status'] for a in call(f'{EOC}/api/actions') if a['id'] == aid)
                check(f'{name}: a work item set Up stays Up on the page while the change is on its way (a poll in between does not undo it)', held and st == 'up' and server == 'up', (held, st, server))
                # Reports already on file: dragged onto the page again after a reload, they are not shown twice
                mime = tmp / 'dup-check.mime'
                mime.write_bytes(('Date: Fri, 13 Nov 2026 18:00:00 +0000\r\nFrom: W9ZZZ@winlink.org\r\nTo: EOC@winlink.org\r\nSubject: dup\r\nMessage-ID: DUPCHECK01\r\n'
                                  'MIME-Version: 1.0\r\nContent-Type: text/plain; charset="iso-8859-1"\r\n\r\nDisaster report\r\n'
                                  '[Church-DR|stake=Larkspur Stake|ward=Larkspur 2nd Ward|type=Flood|location=dup check 1 Elm|date=2026-11-13]\r\nCSV,DR\r\n').encode('latin-1'))
                pg.set_input_files('#file-input', str(mime)); pg.wait_for_timeout(2500)
                n1 = len(call(f'{EOC}/api/messages'))
                pg.reload(); pg.wait_for_timeout(2500)
                # as if the first copy came by phone, Drop Folder or Winlink: those carry no key this page can match
                pg.evaluate("msgs.forEach(function(m){ delete m.dupKey; })")
                pg.set_input_files('#file-input', str(mime)); pg.wait_for_timeout(2500)
                shown = pg.evaluate("msgs.filter(function(m){ return m.dr && m.dr.location === 'dup check 1 Elm'; }).length")
                t = pg.inner_text('#toast')
                check(f'{name}: a report already on file, dragged on again after a reload, is shown once and the page says so', shown == 1 and len(call(f'{EOC}/api/messages')) == n1 and 'Already on file' in t, (shown, t))
                # Drop Folder: a file holding only reports already on file is read, and the page says so
                dropdir = tmp / 'dup-drop'; dropdir.mkdir(exist_ok=True)
                call_json = lambda path, body: urllib.request.urlopen(urllib.request.Request(EOC + path, data=json.dumps(body).encode(), method='PUT', headers={'Content-Type': 'application/json'}), timeout=10).read()
                call_json('/api/drop/config', {'watch_path': str(dropdir), 'enabled': True})
                pg.reload(); pg.wait_for_timeout(2500)
                c2, w2, _ = open_page(b, 'phone', f'{WEB}/templates/disaster-report/Church_of_Jesus_Christ_Disaster_Report_Worker.html')
                w2.fill('#inc_stake', 'Larkspur Stake'); w2.fill('#inc_location', 'dup check 2 Oak')
                txt = w2.evaluate('getFileContent()'); c2.close()
                (dropdir / 'first.txt').write_text(txt, encoding='utf-8')
                for _ in range(30):
                    if not (dropdir / 'first.txt').exists(): break
                    time.sleep(1)
                (dropdir / 'again.txt').write_text(txt, encoding='utf-8')
                t = ''
                for _ in range(40):
                    t = pg.inner_text('#toast') + ' ' + pg.inner_text('#drop-bar')
                    if 'already on file' in t: break
                    time.sleep(0.5)
                ds = call(f'{EOC}/api/drop/status')
                check(f'{name}: a Drop Folder file whose report is already on file is counted and the page says so', ds.get('dup', 0) >= 1 and ds.get('last_dup') == 'again.txt' and 'already on file' in t, (ds.get('dup'), ds.get('last_dup'), t[:200]))
                call_json('/api/drop/config', {'enabled': False})
                ctx.close()
            b.close()
finally:
    web.shutdown()
    for pr in procs:
        pr.terminate()
    for pr in procs:
        try:
            pr.wait(10)
        except subprocess.TimeoutExpired:
            pr.kill()
    log1.close()
    log2.close()
    log3.close()
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\nRESULT: {'ALL PASS' if all(res) else 'FAILURES'} ({sum(res)}/{len(res)})")
sys.exit(0 if all(res) else 1)
