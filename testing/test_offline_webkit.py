"""Offline app test in WebKit (the iPhone's browser engine), from the field test of 2026-10-31: an iPhone in
airplane mode showed a black screen at launch, form buttons that did nothing, an Outbox whose Open / Close /
Send did nothing, and a saved report that was gone after the app was closed.

What it checks, with the repo served on localhost (a secure context, so the service worker runs as on GitHub Pages):
  * hanging network (server accepts, never answers: what the iPhone did): the portal starts in seconds, the
    Outbox card is drawn, a form opens from the portal, Save to Outbox confirms, the Outbox Open loads the
    report in place, Close closes;
  * clean offline network: the same launch and form open;
  * durability: a report whose localStorage copy is lost comes back from the IndexedDB copy on the next start;
  * offline fallbacks: the card PDF and every manifest icon load as themselves (not the portal); an address the
    phone never saved gets the short offline answer with an error status;
  * update safety: an update during which one file fails to download keeps every form available offline.

Needs:  python -m pip install playwright  &&  python -m playwright install webkit
Port 8099 must be free.   python testing/test_offline_webkit.py
"""
import functools, http.server, json, pathlib, re, socket, sys, threading, time

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print('SKIP: playwright is not installed (python -m pip install playwright; python -m playwright install webkit)')
    sys.exit(0)

REPO = pathlib.Path(__file__).resolve().parent.parent
PORT = 8099
BASE = f'http://localhost:{PORT}/'
DR = 'templates/disaster-report/Church_of_Jesus_Christ_Disaster_Report_Worker.html'
results = []


def check(name, ok, detail=''):
    results.append(bool(ok))
    print(('PASS ' if ok else 'FAIL ') + name + (f' -- {detail}' if detail and not ok else ''))


class Quiet(http.server.SimpleHTTPRequestHandler):
    """The repo as GitHub Pages serves it; for the update test it hands out a changed sw.js and fails one file."""
    sw_suffix = ''          # appended to the CACHE name in sw.js: a new version of the app
    fail = set()            # paths (no leading /) that answer 500
    def log_message(self, *a): pass
    def do_GET(self):
        path = self.path.split('?')[0].lstrip('/')
        if path in self.fail:
            self.send_error(500); return
        if path == 'sw.js' and self.sw_suffix:
            body = (REPO / 'sw.js').read_text(encoding='utf-8')
            body = re.sub(r"(var CACHE = 'emcomm-app-[^']*)'", lambda m: m.group(1) + self.sw_suffix + "'", body, count=1).encode('utf-8')
            self.send_response(200); self.send_header('Content-Type', 'text/javascript'); self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(body); return
        return super().do_GET()


class Server:
    """Static server for the repo, switchable to a server that accepts connections and never answers."""
    def __init__(self):
        self.httpd = None; self.stop = None; self.thread = None

    def serve(self, sw_suffix='', fail=()):
        self.halt()
        Quiet.sw_suffix = sw_suffix; Quiet.fail = set(fail)
        self.httpd = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), functools.partial(Quiet, directory=str(REPO)))
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True); self.thread.start()
        for _ in range(50):
            try: socket.create_connection(('127.0.0.1', PORT), 0.2).close(); return
            except OSError: time.sleep(0.1)

    def hang(self):
        self.halt()
        self.stop = threading.Event()
        def run(stop):
            s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(('127.0.0.1', PORT)); s.listen(64); s.settimeout(0.3)
            held = []
            while not stop.is_set():
                try: c, _ = s.accept(); held.append(c)
                except socket.timeout: pass
            for c in held: c.close()
            s.close()
        self.thread = threading.Thread(target=run, args=(self.stop,), daemon=True); self.thread.start(); time.sleep(0.3)

    def halt(self):
        if self.httpd: self.httpd.shutdown(); self.httpd.server_close(); self.httpd = None; self.thread.join(3)
        if self.stop: self.stop.set(); self.thread.join(3); self.stop = None
        time.sleep(0.3)


def install(ctx):
    """First visit with internet: the service worker installs and caches the app."""
    pg = ctx.new_page(); pg.on('dialog', lambda d: d.accept())
    pg.goto(BASE + 'forms/index.html')
    pg.wait_for_function('navigator.serviceWorker && navigator.serviceWorker.controller', timeout=15000)
    pg.wait_for_timeout(1500)   # let install finish caching
    return pg


def timed_goto(pg, url, ready_js, limit_s):
    t0 = time.time()
    try: pg.goto(url, wait_until='commit', timeout=limit_s * 1000)
    except Exception: pass
    try:
        pg.wait_for_function(ready_js, timeout=max(500, int((limit_s - (time.time() - t0)) * 1000)))
        return time.time() - t0
    except Exception:
        return None


# The precache list in sw.js: every entry exists (one missing file would stop every update from installing),
# and every icon the manifest names is in it.
_sw = (REPO / 'sw.js').read_text(encoding='utf-8')
_list = _sw[_sw.index('var FILES'):]
_files = re.findall(r"'([^']+)'", _list[:_list.index('];')])
check(f'sw.js: every precache file exists in the repo ({len(_files)})', all((REPO / f).is_file() for f in _files), [f for f in _files if not (REPO / f).is_file()])
_man = json.loads((REPO / 'forms/manifest.webmanifest').read_text(encoding='utf-8'))
check('sw.js: every manifest icon and the volunteer card PDF are precached',
      all('forms/' + i['src'] in _files for i in _man['icons']) and 'training/pdf/Quick_Reference_Card_1_Helping_Hands_Volunteer.pdf' in _files)

srv = Server()
try:
    with sync_playwright() as p:
        b = p.webkit.launch()
        dev = dict(p.devices['iPhone 13'])

        # ── hanging network ──────────────────────────────────────────────────
        srv.serve()
        ctx = b.new_context(**dev, service_workers='allow')
        pg = install(ctx)
        srv.hang()
        took = timed_goto(pg, BASE + 'forms/index.html', "window.EMCOMM && EMCOMM.ctx === 'portal' && document.getElementById('emcomm-outbox').textContent.indexOf('Outbox') >= 0", 8)
        check('hanging network: the portal starts and draws the Outbox card within 8 s', took is not None, f'took {took}')
        t0 = time.time()
        try:
            pg.locator('a.form-card').first.click(no_wait_after=True)
            pg.wait_for_function("location.pathname.indexOf('Disaster_Report_Worker') >= 0 && window.EMCOMM && EMCOMM.ctx === 'portal'", timeout=8000)
            ok = True
        except Exception as e:
            ok = False
        check('hanging network: tapping Disaster Report opens the form within 8 s', ok, f'{time.time() - t0:.1f}s')
        pg.fill('#inc_location', '123 Hang St')
        pg.get_by_role('button', name='Save to Outbox').first.click()
        try: pg.wait_for_selector('#ea-ov h3:has-text("Saved to the Outbox")', timeout=5000); ok = True
        except Exception: ok = False
        check('hanging network: Save to Outbox confirms', ok)
        saved = pg.evaluate("EMCOMM.outbox.flush().then(() => new Promise(r => { var q = indexedDB.open('emcomm'); q.onsuccess = () => { var g = q.result.transaction('kv').objectStore('kv').get('church_outbox_v1'); g.onsuccess = () => r((g.result || []).length); }; }))")
        check('the saved report is in the durable copy (IndexedDB)', saved == 1, saved)
        pg.locator('#ea-ov button', has_text='Keep editing').click()
        pg.fill('#inc_location', '')   # an empty form: Open must bring the saved values back
        pg.locator('.emcomm-actions .ea-link', has_text='Outbox').first.click()
        url_before = pg.url
        pg.locator('#ea-ov button', has_text='Open').first.click(no_wait_after=True)
        pg.wait_for_timeout(600)
        check('Outbox Open loads the report in place (no page load), at once', pg.locator('#ea-ov').count() == 0 and pg.input_value('#inc_location') == '123 Hang St'
              and '?outbox=' in pg.url and pg.url.split('?')[0] == url_before.split('?')[0], pg.url)
        pg.locator('.emcomm-actions .ea-link', has_text='Outbox').first.click(); pg.wait_for_timeout(200)
        pg.locator('#ea-ov button', has_text='Close').click(); pg.wait_for_timeout(200)
        check('Outbox Close closes', pg.locator('#ea-ov').count() == 0)
        took = timed_goto(pg, BASE + DR, "window.EMCOMM && EMCOMM.ctx === 'portal'", 8)
        check('hanging network: a form opened by address starts within 8 s', took is not None, f'took {took}')

        # ── durability: the localStorage copy is lost, the IndexedDB copy brings it back ──
        pg.evaluate("localStorage.setItem('church_outbox_v1', '[]')")
        took = timed_goto(pg, BASE + 'forms/index.html', "window.EMCOMM && EMCOMM.ctx === 'portal'", 8)
        pg.wait_for_timeout(300)
        n = pg.evaluate('EMCOMM.outbox.waiting().length')
        check('a report lost from localStorage comes back from IndexedDB on the next start', n == 1, n)
        check('the Outbox card counts it', '1 report' in pg.inner_text('#emcomm-outbox'), pg.inner_text('#emcomm-outbox')[:80])
        ctx.close()

        # ── clean offline network ────────────────────────────────────────────
        srv.serve()
        ctx = b.new_context(**dev, service_workers='allow')
        pg = install(ctx)
        ctx.set_offline(True)
        took = timed_goto(pg, BASE + 'forms/index.html', "window.EMCOMM && EMCOMM.ctx === 'portal'", 6)
        check('offline: the portal starts within 6 s', took is not None, f'took {took}')
        took = timed_goto(pg, BASE + DR + '?outbox=none', "window.EMCOMM && EMCOMM.ctx === 'portal' && !!document.getElementById('inc_location')", 6)
        check('offline: a form with ?outbox= on the address opens from the cache', took is not None, f'took {took}')

        # ── offline fallbacks (PACE audit G2): saved files come back as themselves, never as the portal ──
        def offline_get(path):
            return pg.evaluate('''(u) => fetch(u).then(r => r.arrayBuffer().then(b => {
                var a = new Uint8Array(b), ct = r.headers.get('content-type') || '';
                return {status: r.status, type: ct, head: String.fromCharCode.apply(null, a.slice(0, 8)), size: a.length,
                        text: ct.indexOf('text') >= 0 ? new TextDecoder().decode(a) : ''};
            }), e => ({status: -1, type: String(e), head: '', size: 0, text: ''}))''', BASE + path)
        card = offline_get('training/pdf/Quick_Reference_Card_1_Helping_Hands_Volunteer.pdf')
        check('offline: the volunteer card PDF loads as the PDF', card['status'] == 200 and card['head'].startswith('%PDF'), str(card)[:120])
        man = json.loads((REPO / 'forms/manifest.webmanifest').read_text(encoding='utf-8'))
        bad = []
        for ic in man['icons']:
            r = offline_get('forms/' + ic['src'])
            if not (r['status'] == 200 and r['head'][1:4] == 'PNG'): bad.append(ic['src'] + ' ' + str(r)[:80])
        check(f"offline: every manifest icon ({len(man['icons'])}, maskable too) loads as the image", not bad, '; '.join(bad))
        r = offline_get('training/quick-ref-cards.html')
        check('offline: the Quick Reference Cards page loads as itself', r['status'] == 200 and 'Quick Reference' in r['text'] and 'emcomm-outbox' not in r['text'], str(r)[:120])
        r = offline_get('forms/icons/not-saved.png')
        check('offline: an address the phone never saved gets the offline answer with an error status (not the portal)',
              r['status'] >= 400 and 'Not saved on this phone' in r['text'], str(r)[:160])
        took = timed_goto(pg, BASE + 'training/pdf/not-saved.pdf', "document.body && document.body.innerText.indexOf('Not saved on this phone') >= 0", 6)
        check('offline: opening a document the phone never saved says so (not the portal)', took is not None, f'took {took}')
        took = timed_goto(pg, BASE + 'forms/never-saved.html', "window.EMCOMM && EMCOMM.ctx === 'portal' && !!document.getElementById('emcomm-outbox')", 6)
        check('offline: a page the phone never saved still opens the portal', took is not None, f'took {took}')

        # ── paper forms (Emergency path): blank form offline, Print, printed header ──
        took = timed_goto(pg, BASE + DR + '?blank=1', "window.EMCOMM && EMCOMM.ctx === 'portal' && !!document.getElementById('ea-blank-bar')", 6)
        check('offline: a blank form (?blank=1) opens from the cache with the print bar', took is not None, f'took {took}')
        check('blank form: no date and no GPS filled in', pg.input_value('#inc_date') == '' and pg.input_value('#stn_lat_d') == '')
        check('Print is offered under the form', pg.locator('.emcomm-actions .ea-link', has_text='Print').count() == 2)
        pg.evaluate("window.dispatchEvent(new Event('beforeprint'))")
        paper = pg.evaluate("(document.getElementById('ea-paper') || {}).textContent || ''")
        check('the printed page says where the paper goes', 'Fill in by hand' in paper and 'Crew Chief or a runner' in paper, paper[-200:])
        check('the paper copy is laid out like the Church form and says it is based on it, not official',
              'Reporting Period' in paper and 'Anticipated Needs' in paper and 'Based on Church form PD60000184' in paper and 'Not an official Church form' in paper)
        pg.fill('#inc_location', 'Larkspur, WL')
        pg.evaluate("window.dispatchEvent(new Event('beforeprint'))")
        check('a filled form prints its answers on the paper copy', 'Larkspur, WL' in pg.evaluate("document.getElementById('ea-paper').textContent"))

        # ── Home: the app on a home screen has no Back button (Travis, 2026-10-31) ──
        hp = ctx.new_page(); asked = []
        hp.on('dialog', lambda d: (asked.append(d.message), d.dismiss()))
        took = timed_goto(hp, BASE + DR, "window.EMCOMM && EMCOMM.ctx === 'portal' && !!document.getElementById('ea-home')", 6)
        check('offline: the form shows a Home link at the top', took is not None and hp.inner_text('#ea-home').strip().endswith('Home'), f'took {took}')
        hp.fill('#inc_location', 'Larkspur, WL')
        hp.click('#ea-home'); hp.wait_for_timeout(800)
        check('Home asks first when what was typed is not in the Outbox, and Cancel stays on the form',
              asked and 'not in the Outbox' in asked[0] and DR in hp.url and hp.input_value('#inc_location') == 'Larkspur, WL', str(asked)[:80])
        hp.evaluate("EMCOMM.saveToOutbox(true)"); asked.clear()
        hp.click('#ea-home')
        try: hp.wait_for_url('**/forms/index.html', timeout=6000); home_ok = True
        except Exception: home_ok = False
        check('after Save to Outbox, Home goes straight to the portal (offline, from the cache)', home_ok and not asked, hp.url)
        try: hp.wait_for_function("window.EMCOMM && EMCOMM.ctx === 'portal' && !!document.getElementById('emcomm-outbox')", timeout=6000); started = True
        except Exception: started = False
        check('the portal starts and its Outbox card shows the saved report', started and '1 report' in hp.inner_text('#emcomm-outbox'), hp.inner_text('body')[:80] if started else '')
        ctx.close()

        # ── update safety (PACE audit G3): a new version comes out while one Worker form fails to download.
        #    The forms must stay on the phone: either the update does not install (the old version keeps
        #    working) or it installs with the phone's older copy of the missing file. ──
        SO = 'templates/supply-order/Church_of_Jesus_Christ_Supply_Order_Worker.html'
        srv.serve()
        ctx = b.new_context(**dev, service_workers='allow')
        pg = install(ctx)
        srv.serve(sw_suffix='-update-test', fail={SO})
        state = pg.evaluate('''() => navigator.serviceWorker.getRegistration().then(reg => reg.update().then(() => new Promise(done => {
            var w = reg.installing || reg.waiting;
            if (!w) return done('no new worker');
            var t = setTimeout(() => done('timeout ' + w.state), 20000);
            w.addEventListener('statechange', () => { if (w.state === 'activated' || w.state === 'redundant') { clearTimeout(t); done(w.state); } });
        }), e => 'update rejected: ' + e))''')
        pg.wait_for_timeout(500)
        keys = pg.evaluate('caches.keys()')
        has_so = pg.evaluate('(u) => caches.match(u, {ignoreSearch: true}).then(r => !!r)', BASE + SO)
        check('update with one failed download: the Supply Order form is still saved on the phone',
              has_so and (state in ('activated', 'redundant') or state.startswith('update rejected')), f'{state}, {keys}')
        ctx.set_offline(True)
        took = timed_goto(pg, BASE + SO, "document.title.indexOf('Supply Order') >= 0 && window.EMCOMM && EMCOMM.ctx === 'portal'", 6)
        check('after that update, offline: the Supply Order form opens (not the portal)', took is not None, f'{state} took {took}')
        took = timed_goto(pg, BASE + DR, "document.title.indexOf('Disaster Report') >= 0 && window.EMCOMM && EMCOMM.ctx === 'portal'", 6)
        check('after that update, offline: the Disaster Report form opens', took is not None, f'took {took}')
        print(f'      (update outcome: {state}; caches {keys})')
        ctx.close()

        # ── No dead ends: every link on the portal either opens outside the app (a new browser view with its own
        #    Done / back) or lands on a page with a way back (Travis, 2026-10-31: the card PDF trapped him) ──
        srv.serve()
        ctx = b.new_context(**dev); pg = ctx.new_page(); pg.on('dialog', lambda d: d.accept())
        pg.goto(BASE + 'forms/index.html'); pg.wait_for_function("window.EMCOMM && EMCOMM.ctx === 'portal'", timeout=8000)
        links = pg.evaluate("""() => [...document.querySelectorAll('a[href]')].map(a => ({href: a.href, raw: a.getAttribute('href'), blank: a.target === '_blank', text: a.textContent.trim().slice(0, 40)}))
                                 .filter(l => !/^(tel|mailto|javascript):/.test(l.raw) && !l.raw.startsWith('#'))""")
        dead = []
        for l in links:
            if l['blank'] or not l['href'].startswith(BASE): continue
            if l['href'].split('#')[0].split('?')[0] == BASE + 'forms/index.html': continue
            q = ctx.new_page(); q.on('dialog', lambda d: d.accept())
            q.goto(l['href'], wait_until='load'); q.wait_for_timeout(1500)
            back = q.evaluate("() => [...document.querySelectorAll('#ea-home, a.home, a.home-link')].map(a => a.getAttribute('href'))")
            if not back: dead.append(l['text'] + ' -> ' + l['raw'])
            q.close()
        pdfs = [l for l in links if l['raw'].lower().endswith('.pdf')]
        check(f'no dead ends: every in-app page linked from the portal has a way back ({len(links)} links)', not dead, '; '.join(dead))
        check('documents (PDF, the card page) open outside the app', pdfs and all(l['blank'] for l in pdfs)
              and all(l['blank'] for l in links if 'quick-ref-cards' in l['raw']), str([l['raw'] for l in pdfs if not l['blank']]))
        ctx.close()

        # ── Print from the iPhone home-screen app (Travis, 2026-10-31: "Print this blank form" did nothing: an app
        #    started from the home screen ignores window.print()). Emulated: navigator.standalone is true in the
        #    app, false in the browser view the print page opens in; window.print is recorded. ──
        ctx = b.new_context(**dev)
        ctx.add_init_script("""Object.defineProperty(Navigator.prototype, 'standalone', {get: () => !/[?&]print=1/.test(location.search)});
            window.__printed = 0; window.print = function () { window.__printed++; };""")
        pg = ctx.new_page(); pg.on('dialog', lambda d: d.accept())
        pg.goto(BASE + DR + '?blank=1'); pg.wait_for_function("window.EMCOMM && EMCOMM.ctx === 'portal' && !!document.getElementById('ea-blank-bar')", timeout=8000)
        with ctx.expect_page(timeout=6000) as pop:
            pg.click('#ea-blank-bar .ea-big')
        q = pop.value; q.wait_for_function("window.EMCOMM && EMCOMM.ctx && !!document.getElementById('ea-print-bar')", timeout=8000); q.wait_for_timeout(1000)
        check('app: Print this blank form opens the browser view with the blank form, and it prints there',
              'blank=1' in q.url and 'print=1' in q.url and q.evaluate('window.__printed') >= 1 and 'Fill in by hand' in q.evaluate("document.getElementById('ea-paper').textContent")
              and pg.evaluate('window.__printed') == 0, q.url)
        q.close()
        pg.goto(BASE + DR); pg.wait_for_function("window.EMCOMM && EMCOMM.ctx === 'portal' && !!document.getElementById('inc_location')", timeout=8000)
        pg.fill('#inc_location', 'Larkspur, WL'); pg.check('input[name=miss_safe][value=NO]'); pg.fill('#miss_details', 'Elders in the Larkspur 4th Ward area not reached')
        with ctx.expect_page(timeout=6000) as pop:
            pg.locator('.emcomm-actions .ea-link', has_text='Print').first.click()
        q = pop.value; q.wait_for_function("window.EMCOMM && EMCOMM.ctx && !!document.getElementById('ea-print-bar')", timeout=8000); q.wait_for_timeout(1000)
        paper = q.evaluate("document.getElementById('ea-paper').textContent")
        check('app: Print on a filled form carries its answers to the browser view and prints them',
              '#p=j' in q.url and 'Larkspur, WL' in paper and 'Elders in the Larkspur 4th Ward area' in paper and q.evaluate('window.__printed') >= 1
              and q.input_value('#inc_location') == 'Larkspur, WL', q.url[:120])
        q.click('#ea-print-bar .ea-big'); q.wait_for_timeout(300)
        check('the Print button in the browser view prints there (it does not hand off again)', len(ctx.pages) == 2 and q.evaluate('window.__printed') >= 2, f'{len(ctx.pages)} pages, printed {q.evaluate("window.__printed")}')
        ctx.close()
        b.close()
finally:
    srv.halt()

print(f"\nRESULT: {'ALL PASS' if all(results) else 'FAILURES'} ({sum(results)}/{len(results)})")
sys.exit(0 if all(results) else 1)
