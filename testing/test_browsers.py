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
SIZES = {'phone': (390, 844), 'tablet': (820, 1180), 'laptop': (1366, 768)}
# page -> the sizes at which it must fit with no sideways scroll. The wall is a big screen; it must only load.
EOC = f'http://127.0.0.1:{PE}'
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
env = dict(os.environ, PYTHONIOENCODING='utf-8', LOCALAPPDATA=str(tmp / 'appdata'), USERPROFILE=str(tmp / 'home'), EMCOMM_DOCUMENTS=str(tmp / 'documents'))
work = tmp / 'site'
(work / 'eoc').mkdir(parents=True)
for f in ('eoc_server.py', 'EOC_Message_Center.html', 'EOC_Wall_Display.html', 'EOC_Phone.html'):
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
web = QuietServer(('127.0.0.1', PW), functools.partial(Quiet, directory=str(REPO)))
threading.Thread(target=web.serve_forever, daemon=True).start()


def open_page(browser, size, url):
    w, h = SIZES[size]
    ctx = browser.new_context(viewport={'width': w, 'height': h})
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('dialog', lambda d: d.dismiss())
    pg.goto(url, wait_until='load', timeout=30000)
    pg.wait_for_timeout(700)
    return ctx, pg, errs


try:
    for port, path in ((PE, '/api/status'), (PS, '/api/info')):
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
            pg.click('#b-browse')
            pg.wait_for_selector('#bx-bg', state='visible', timeout=5000)
            pg.fill('#bx-path', str(drills.parent))
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
            ctx.close()
            # the Message Center: every folder it asks for opens the folder browser, never a typed-path prompt
            ctx = b.new_context(viewport={'width': SIZES['laptop'][0], 'height': SIZES['laptop'][1]})
            pg = ctx.new_page()
            errs = []
            pg.on('pageerror', lambda e: errs.append(str(e)))
            pg.on('dialog', lambda d: d.accept('') if d.type == 'prompt' else d.dismiss())   # the call-sign question: answered blank, as a person may
            pg.goto(f'{EOC}/', wait_until='load')
            pg.wait_for_timeout(700)
            pg.evaluate("browseMapFolder()")
            pg.wait_for_selector('#fb-bg', state='visible', timeout=5000)
            pg.fill('#fb-path', str(work / 'simulation' / 'example'))
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
            wl.mkdir()
            pg.evaluate("configureWatcher()")
            pg.wait_for_selector('#fb-bg', state='visible', timeout=5000)
            pg.fill('#fb-path', str(wl))
            pg.click('#fb-box button:has-text("Go")')
            pg.wait_for_function(f"document.getElementById('fb-path').value.endsWith('winlink-{name}')", timeout=6000)
            pg.click('#fb-use')
            ok = False
            for _ in range(20):
                if pathlib.Path(call(f'{EOC}/api/watcher/status').get('watch_path', '')) == wl:
                    ok = True
                    break
                time.sleep(0.25)
            check(f'{name}: the Winlink Express folder is chosen with the folder browser and saved', ok and not errs, (call(f'{EOC}/api/watcher/status').get('watch_path'), errs[:2]))
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
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\nRESULT: {'ALL PASS' if all(res) else 'FAILURES'} ({sum(res)}/{len(res)})")
sys.exit(0 if all(res) else 1)
