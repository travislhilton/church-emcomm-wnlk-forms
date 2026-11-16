#!/usr/bin/env python3
"""Simulator consistency: does every simulated report tell one story, and does every screen show the numbers
the simulator actually sent?

    python testing/test_sim_consistency.py                 # both parts; the screen part needs Playwright (Chromium)
    python testing/test_sim_consistency.py --port=8084     # the scratch EOC server's port (default 8084)
    python testing/test_sim_consistency.py --seeds=60      # seeds per scenario and pack in part 1 (default 40)
    python testing/test_sim_consistency.py --shots=<folder> # also save each role's view at the end as a screenshot

Part 1, no servers: every developed scenario is planned against the invented Juniper Plains example and the
synthetic test fixture, with many seeds, for every stake on its own and for the whole pack. Each Disaster Report
must agree with itself (a missionary answer of NO never carries an "accounted for" note, YES never a "not
accounted for" one), and each unit's reports must tell one story in time order: after a scripted NO, a report
drawn at random never says YES before the scripted YES; the unit's last answer is YES (every missing story ends).
The check is run once with the engine's settling step switched off, and must find the contradictions then.

Part 2, a scratch EOC server: one Copper Creek Dam run for one invented stake, every report delivered by phone in
time order. The EOC's records, the read-out (/api/readout), the Message Center (Overview tiles, missionary bar,
headquarters list, SITREP section A) and the wall must show exactly what the simulator sent: report counts,
injured, deaths, homes damaged and destroyed, volunteers, the wards whose LATEST answer says missionaries are not
accounted for (each once), and each ward asking for headquarters help once.

Invented data only: nothing from secure data/ is read.
"""
import copy
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

os.environ.setdefault('EMCOMM_DISCOVERY', 'test')
REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / 'simulation'))
import engine    # noqa: E402
import orgpack   # noqa: E402
import privacy   # noqa: E402

EXAMPLE = REPO / 'simulation' / 'example' / 'juniper-plains'
FIX = REPO / 'testing' / 'fixtures' / 'orgpack-synthetic.json'
arg = lambda name, default: next((a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith(f'--{name}=')), default)
PORT = int(arg('port', '8084'))
SEEDS = int(arg('seeds', '40'))
SHOTS = arg('shots', '')                      # a folder: screenshots of each role's view at the end, for a person to look at
res = []
STAGE = ['']


def check(label, ok, detail=''):
    ok = bool(ok)
    res.append(ok)
    label = (f'[{STAGE[0]}] ' if STAGE[0] else '') + label
    print(('PASS ' if ok else 'FAIL ') + label + (' -- ' + str(detail)[:300] if detail and not ok else ''))


# ── Part 1: every report tells one story ──
NEG = re.compile(r"\bnot\b[^.;]*\baccounted\b|\bunaccounted\b|\bmissing\b", re.I)


def yn(v):
    v = str(v or '').strip().upper()
    return 'YES' if v in ('YES', 'TRUE', '1') else 'NO' if v in ('NO', 'FALSE', '0') else ''


def story_problems(run: dict, scenario: dict) -> list:
    """Every missionary contradiction in one planned run (an empty list when it tells one story per unit)."""
    tpl_of = {i.get('id'): i.get('template', '') for i in scenario.get('injects', [])}
    templates = scenario.get('templates', {})
    out, by_unit = [], {}
    for it in sorted(run['items'], key=lambda i: (i['t'], i['id'])):
        pl = it.get('payload') or {}
        if it['kind'] != 'form' or it.get('form') != 'dr' or 'miss_safe' not in pl:
            continue
        a, note = yn(pl.get('miss_safe')), str(pl.get('miss_details') or '')
        if a == 'NO' and note and not NEG.search(note):
            out.append(f"{it['id']}: says NO but its note says {note[:70]!r}")
        if a == 'YES' and NEG.search(note):
            out.append(f"{it['id']}: says YES but its note says {note[:70]!r}")
        scripted = isinstance((templates.get(tpl_of.get(it['inject'], '')) or {}).get('miss_safe'), str)
        by_unit.setdefault(it['unit_id'], []).append((it, a, scripted))
    for uid, reps in by_unit.items():
        state = None
        for it, a, scripted in reps:
            if state == 'NO' and a == 'YES' and not scripted:
                out.append(f"{it['id']}: a random report says YES after a NO, before the scripted 'found' report")
            if a:
                state = a
        if state == 'NO':
            out.append(f"{uid}: the last report still says missionaries are not accounted for (the story never ends)")
    return out


def plans(pack: dict, sid: str):
    """(label, run, scenario) for each seed, each stake alone and the whole pack."""
    scenario = engine.load_scenario(sid)
    scopes = [('every stake', {})] + [(f"stake {s['id']}", {'stakes': [s['id']]}) for s in pack['stakes']]
    for seed in range(1, SEEDS + 1):
        for label, opt in scopes:
            yield f'seed {seed}, {label}', engine.plan(pack, scenario, dict(opt, seed=seed, today='2026-11-14')), scenario


cat = engine.catalog()
sids = [s['id'] for s in cat['scenarios'] if s.get('status') == 'developed']
check('the catalog has developed scenarios to check', sids, cat.get('scenarios'))
packs = {'invented example': privacy.pseudonymize(orgpack.load(EXAMPLE), 'consistency'),
         'synthetic fixture': privacy.pseudonymize(orgpack.load(FIX), 'consistency')}
for sid in sids:
    for pname, pack in packs.items():
        n, bad, found = 0, [], 0
        for label, run, sc in plans(pack, sid):
            n += 1
            p = story_problems(run, sc)
            bad += [f'{label}: {x}' for x in p[:2]]
            found += sum(1 for it in run['items'] if (it.get('payload') or {}).get('miss_safe') == 'NO')
        check(f'{sid}, {pname}: every Disaster Report agrees with itself and each unit tells one missionary story '
              f'({n} plans, {found} NO answers)', not bad, bad[:4])

# the check itself must catch the old behaviour: the engine without its settling step
_settle = engine._settle_missionaries
engine._settle_missionaries = lambda *a, **k: None
try:
    caught = sum(len(story_problems(run, sc)) for _, run, sc in plans(packs['invented example'], 'copper-creek-dam'))
finally:
    engine._settle_missionaries = _settle
check(f'the story check finds the contradictions when the engine does not settle them ({caught} found)', caught > 0)

# the debrief's cover line: an invented community is called invented, and a run never shows past its end
_p = orgpack.load(EXAMPLE)
check('the invented example pack says it is invented; the synthetic fixture does not', _p.get('invented') and not orgpack.load(FIX).get('invented'))


# ── Part 2: the screens show what the simulator sent ──
def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}{path}', data=data, method=method, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode('utf-8'))


def ni(v):
    m = re.match(r'\s*(\d+)', str(v or ''))
    return int(m.group(1)) if m else 0


DECIDE = re.compile(r'\b(decide[sd]?|decision|approve[sd]?|approval|recommend(s|ed|ation)?)\b', re.I)


def is_decision(a):
    """The leaders' list, written here on its own: open, not waiting above, no decision written, asks for one."""
    return a.get('status') not in ('done', 'up') and not str(a.get('decision') or '').strip() \
        and bool(DECIDE.search(str(a.get('title') or '') + ' ' + str(a.get('next') or '')))


def role_checks(pg, msgs, recs, want_miss, last_stage):
    """Each role's view on the Message Center against the EOC's own records."""
    def shot(name, sel=None):
        if SHOTS and last_stage:
            pathlib.Path(SHOTS).mkdir(parents=True, exist_ok=True)
            (pg.query_selector(sel) if sel else pg).screenshot(path=str(pathlib.Path(SHOTS) / f'{name}.png'))
    # the operator: the drop box folds to one line once reports are on file
    check('operator: the big drop box folds to one line once reports are on file',
          not pg.is_visible('#drop-zone') and pg.is_visible('#drop-mini'))
    # the leaders: Decisions to make
    acts = call('GET', '/api/actions')
    want_dec = sorted(a['id'] for a in acts if is_decision(a))
    pg.evaluate("switchTab('actions'); showDecisions()"); pg.wait_for_timeout(300)
    rows = pg.query_selector_all('#act-tbody tr')
    chips = pg.query_selector_all('#act-tbody .act-decide')
    cnt = pg.inner_text('#cnt-decide').strip()
    check(f'leaders: Decisions to make lists every open item asking for a decision, each marked DECIDE ({len(want_dec)})',
          want_dec and len(rows) == len(want_dec) == len(chips) and cnt == str(len(want_dec)), (len(rows), len(chips), cnt, len(want_dec)))
    ov = pg.evaluate("switchTab('overview'), document.getElementById('ov-alerts').innerText")
    check('leaders: the Overview says how many decisions wait for the Stake President', f'{len(want_dec)} decision' in ov, ov[:300])
    shot('1-overview')
    pg.evaluate("switchTab('actions'); showDecisions()"); pg.wait_for_timeout(200); shot('2-decisions')
    if last_stage:
        first = want_dec[0]
        pg.evaluate(f"patchAction({json.dumps(first)}, {{decision: 'Approved by the Stake President (test)', log: 'decided'}})")
        pg.wait_for_timeout(800)
        after = call('GET', '/api/actions')
        check('leaders: a decision written on an item takes it off the list, here and on the server',
              pg.inner_text('#cnt-decide').strip() == str(len(want_dec) - 1) and sum(1 for a in after if is_decision(a)) == len(want_dec) - 1)
    # the operator: Group by ward, and NEW since the tab was last opened
    pg.evaluate("switchTab('actions'); setActFilter('open', document.querySelector('#act-filters .filter-btn')); "
                "document.getElementById('act-group').checked = true; actGroupChanged()")
    open_items = [a for a in call('GET', '/api/actions') if a.get('status') != 'done']
    units = {(a.get('unit') or '').strip() for a in open_items}
    groups = pg.query_selector_all('#act-tbody tr.act-group')
    total = sum(int(re.search(r'(\d+) item', g.inner_text()).group(1)) for g in groups)
    check(f'operator: Group by ward gives one block per ward, every open item in one ({len(units)} blocks, {len(open_items)} items)',
          len(groups) == len(units) and total == len(open_items), (len(groups), len(units), total))
    shot('3-work-items-by-ward')
    pg.evaluate("document.getElementById('act-group').checked = false; actGroupChanged()")
    cut = sorted(a.get('ts') or 0 for a in open_items)[len(open_items) // 2]
    pg.evaluate(f"localStorage.setItem('emcomm_act_seen', '{cut}'); switchTab('overview'); switchTab('actions')")
    new = len(pg.query_selector_all('#act-tbody .act-new'))
    check('operator: NEW marks exactly the open items added since the tab was last opened', new == sum(1 for a in open_items if (a.get('ts') or 0) > cut), new)
    # the mission office: one line per ward, its latest answer
    drs = [r['dr'] for r in recs if r['type'] == 'dr']
    wards = {((d.get('stake') or '') + '|' + (d.get('ward') or '')).lower() for d in drs}
    pg.evaluate("switchTab('overview'); document.querySelector('#ov-miss details').open = true")
    mrows = pg.query_selector_all('#ov-miss tbody tr')
    no_rows = sorted(r.query_selector('td').inner_text().strip() for r in mrows if 'NOT ACCOUNTED' in r.inner_text())
    txt = pg.evaluate('missText()')
    shot('4-missionaries', '#ov-miss')
    check(f'mission office: one line per ward that reported ({len(wards)}), NOT ACCOUNTED FOR on the wards whose latest answer is NO',
          len(mrows) == len(wards) and no_rows == want_miss and all(w in txt for w in want_miss), (len(mrows), no_rows, want_miss))
    # the welfare line: one line per Supply Order, the ones to approve counted
    sos = [m for m in msgs if m['type'] == 'so']
    pg.evaluate("switchTab('so')")
    srows = pg.query_selector_all('#so-board tbody tr')
    acts = call('GET', '/api/actions')
    appr = {a.get('key'): a for a in acts}
    to_approve = sum(1 for m in sos if m.get('status') != 'complete' and (appr.get('so:approve:' + m['id']) or {}).get('status') not in ('done', 'up'))
    head = pg.inner_text('#so-board p')
    check(f'welfare line: one line per Supply Order ({len(sos)}), {to_approve} to approve',
          len(srows) == len(sos) and f'{to_approve} to approve' in head, (len(srows), head[:160]))
    if last_stage and sos:
        a = appr.get('so:approve:' + sos[0]['id'])
        pg.evaluate(f"patchAction({json.dumps(a['id'])}, {{status: 'done', decision: 'Stake President 14:05 (test)'}})"); pg.wait_for_timeout(600)
        check('welfare line: approving an order\'s work item shows it Approved and counts one fewer to approve',
              f'{to_approve - 1} to approve' in pg.inner_text('#so-board p') and 'Approved: Stake President 14:05 (test)' in pg.inner_text('#so-board'))
    shot('5-supply-orders', '#so-board')
    # net control: the wards to call
    pg.evaluate("switchTab('comms')"); pg.wait_for_timeout(200); shot('6-net-control', '#comms-net')
    net = pg.evaluate('netCallText()')
    callpart = net.split('CALL ON THE NET NOW:', 1)[-1].split('GOES UP', 1)[0]
    check('net control: the call list names every ward whose missionaries are not accounted for',
          all(w in callpart for w in want_miss) and ('missionaries not accounted for' in callpart) == bool(want_miss), callpart[:300])
    named_units = [ln.strip().split(':', 1)[0] for ln in callpart.strip().splitlines() if ln.startswith('  ') and ':' in ln]
    check('net control: each ward is named once on the call list, its reasons together', len(named_units) == len(set(named_units)), named_units)


try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

SP = pathlib.Path(tempfile.mkdtemp(prefix='eoc_sim_consistency_'))
proc = None
try:
    d = SP / 'eoc'
    shutil.copytree(REPO / 'eoc', d, ignore=shutil.ignore_patterns('eoc_data.db*', 'backups', '__pycache__', 'readout-latest.json*'))
    shutil.copytree(REPO / 'templates', SP / 'templates')
    env = dict(os.environ, PYTHONIOENCODING='utf-8', LOCALAPPDATA=str(SP / 'appdata'), EMCOMM_DOCUMENTS=str(SP / 'documents'),
               USERPROFILE=str(SP / 'home'), EMCOMM_BASEMAP_URL='off', EMCOMM_STREETS_URL='off')
    log = open(SP / 'eoc.log', 'w', encoding='utf-8')
    proc = subprocess.Popen([sys.executable, '-u', 'eoc_server.py', f'--port={PORT}'], cwd=str(d), stdout=log, stderr=subprocess.STDOUT, env=env)
    for _ in range(80):
        try:
            call('GET', '/api/status'); break
        except Exception:
            time.sleep(0.25)
    pack = packs['invented example']
    stake = pack['stakes'][0]
    inc = call('GET', '/api/incident')
    inc.update({'eocName': stake['name'], 'eocLevel': 'stake', 'name': 'DRILL consistency (THIS IS AN EXERCISE)', 'pace': 'P', 'sitrepHrs': '4'})
    call('PUT', '/api/incident', inc)
    scenario = engine.load_scenario('copper-creek-dam')
    run = engine.plan(pack, scenario, {'seed': 5, 'stakes': [stake['id']], 'today': '2026-11-14',
                                       'eoc': {'name': stake['name'], 'url': f'http://127.0.0.1:{PORT}'}})
    run['pace'] = [{'t': 0, 'level': 'P'}]           # every report by phone, so the EOC files them in the order they were sent
    runner = engine.Runner(run, f'http://127.0.0.1:{PORT}', SP / 'runs')
    found_t = min(i['t'] for i in run['items'] if i.get('inject') == 'dr-found')
    sent = []

    def deliver(until):
        for it in [i for i in run['items'] if i['kind'] == 'form' and i['status'] == 'pending' and i.get('local', True) and i['t'] < until]:
            runner.jump(it['t'])
            r = runner.fire(it['id'])
            r = r.get('result') if isinstance(r, dict) and 'result' in r else r
            if (r or {}).get('via') == 'phone':
                sent.append((it, r))

    def totals_checks(pg, wl, drs):
        """Totals two ways (Travis, 2026-11-16): every report added, or each ward's latest report only. The event's
        choice leads on the Overview, the Disaster Reports tab, the SITREP and the wall; the other is shown beside it."""
        keys = ('inj', 'dead', 'dmg', 'dest', 'vol')
        def shot(name, sel=None, page=pg):
            if SHOTS:
                pathlib.Path(SHOTS).mkdir(parents=True, exist_ok=True)
                (page.query_selector(sel) if sel else page).screenshot(path=str(pathlib.Path(SHOTS) / f'{name}.png'))
        def tot(ps):
            return {'inj': sum(ni(p.get('mem_injuries')) for p in ps), 'dead': sum(ni(p.get('mem_deaths')) for p in ps),
                    'dmg': sum(ni(p.get('mem_damaged')) for p in ps), 'dest': sum(ni(p.get('mem_destroyed')) for p in ps),
                    'vol': sum(ni(p.get('vol_count')) for p in ps)}
        latest = {}
        for p in drs:                                     # delivered in time order: the last one per ward is its latest
            latest[(str(p.get('inc_stake') or '') + '|' + str(p.get('inc_ward') or '')).lower()] = p
        A, L = tot(drs), tot(list(latest.values()))
        differ = [k for k in keys if A[k] != L[k]]
        check(f'totals: the run has wards whose follow-up reports repeat numbers, so the two counts differ (every report {A}, each ward\'s latest {L})', differ, (A, L))
        LABEL = {'inj': 'Injuries', 'dead': 'Deaths', 'dmg': 'Homes Damaged', 'dest': 'Homes Destroyed', 'vol': r'Volunteers \(Disaster Reports\)'}
        def tiles():
            t = pg.inner_text('#ov-stats'); out = {}
            for k, lab in LABEL.items():
                m = re.search(r'(\d+)\s*\n\s*' + lab + r'(?:\s*\n\s*([^\n]*?): (\d+))?', t)
                out[k] = (int(m.group(1)), int(m.group(3)) if m and m.group(3) else None) if m else None
            return out
        def want_tiles(main, other):
            return {k: (main[k], other[k] if other[k] != main[k] else None) for k in keys}
        pg.evaluate("switchTab('overview')"); pg.wait_for_timeout(400)
        got = tiles()
        check('totals: by default the Overview adds every report and shows each ward\'s latest under the numbers that differ', got == want_tiles(A, L), got)
        bar = pg.inner_text('#ov-totals-by')
        check('totals: the Overview offers both counts, "Add every report" chosen', 'Add every report' in bar and 'latest report' in bar
              and pg.evaluate("document.querySelector('#ov-totals-by .filter-btn.active').textContent") == 'Add every report', bar)
        shot('totals-all', '#tab-overview')
        pg.click('#ov-totals-by >> text=Each ward\u2019s latest report'); pg.wait_for_timeout(800)
        got = tiles()
        check('totals: chosen "Each ward\'s latest report", the Overview leads with it and shows every report added under the numbers that differ',
              got == want_tiles(L, A), got)
        shot('totals-latest', '#tab-overview')
        ev = call('GET', '/api/incident')
        check('totals: the choice is kept with the event on the server', ev.get('totalsBy') == 'latest', ev.get('totalsBy'))
        check('totals: the choice is written in the EOC log', any('Totals now lead with' in (n.get('text') or '') for n in call('GET', '/api/notes')))
        pg.evaluate("switchTab('dr')"); pg.wait_for_timeout(300)
        drt = pg.inner_text('#dr-agg-stats')
        m = re.search(r'(\d+)\s*\n\s*Homes Damaged', drt)
        check('totals: the Disaster Reports tab follows the same choice', m and int(m.group(1)) == L['dmg'], drt[:200])
        pg.evaluate("switchTab('overview')")
        pg.evaluate('buildSitrep()'); pg.wait_for_timeout(500)
        b = pg.inner_text('#sitrep-pre').split('SECTION B', 1)[-1].split('SECTION D', 1)[0]
        line = lambda lab, k: re.search(lab + r':\s+' + str(L[k]) + (r'\s+\(every report added: ' + str(A[k]) + r'\)' if A[k] != L[k] else r'\s*\n'), b)
        ok = all(line(lab, k) for lab, k in (('Members injured', 'inj'), ('Member deaths', 'dead'), ('Member homes damaged', 'dmg'),
                                             ('Member homes destroyed', 'dest'), ('Total volunteers', 'vol')))
        check('totals: the SITREP gives the chosen count, the other in brackets where it differs, and now the homes too',
              ok and "each ward\u2019s latest Disaster Report" in b, b[:600])
        wl.reload(wait_until='load'); wl.wait_for_timeout(2500)
        nums = lambda sel: [int(x) for x in re.findall(r'\d+', wl.inner_text(sel))]
        w = {'life': nums('#life-v'), 'homes': nums('#homes-v'), 'homes_sub': wl.inner_text('#homes-sub'), 'life_sub': wl.inner_text('#life-sub'),
             'alerts': wl.inner_text('#alerts')}
        okw = ((f"{L['inj']} member" in w['alerts'] if L['inj'] else True) and
               (w['life'] == [L['inj'], L['dead']] and w['homes'] == [L['dmg'], L['dest']]
               and ((f"every report added: {A['dmg']} / {A['dest']}" in w['homes_sub']) if (A['dmg'], A['dest']) != (L['dmg'], L['dest']) else True)
               and ((f"every report added: {A['inj']} / {A['dead']}" in w['life_sub']) if (A['inj'], A['dead']) != (L['inj'], L['dead']) else True)))
        check('totals: the wall (tiles and its alert strip) follows the event\'s choice and shows the other count under the numbers', okw, w)
        shot('totals-wall', page=wl)
        pg.click('#ov-totals-by >> text=Add every report'); pg.wait_for_timeout(800)
        check('totals: back to "Add every report" on the page and the server', tiles() == want_tiles(A, L) and call('GET', '/api/incident').get('totalsBy') == 'all',
              call('GET', '/api/incident').get('totalsBy'))

    def verify(expect_missing):
        drs = [it['payload'] for it, _ in sent if it['form'] == 'dr']
        want = {'dr': len(drs), 'so': sum(1 for it, _ in sent if it['form'] == 'so'), 'wcl': sum(1 for it, _ in sent if it['form'] == 'wcl'),
                'inj': sum(ni(p.get('mem_injuries')) for p in drs), 'dead': sum(ni(p.get('mem_deaths')) for p in drs),
                'dmg': sum(ni(p.get('mem_damaged')) for p in drs), 'dest': sum(ni(p.get('mem_destroyed')) for p in drs),
                'vol': sum(ni(p.get('vol_count')) for p in drs)}
        last = {}
        for p in drs:                                     # the latest answer from each ward decides
            if yn(p.get('miss_safe')):
                last[p.get('inc_ward')] = yn(p.get('miss_safe'))
        want_miss = sorted(u for u, a in last.items() if a == 'NO')
        want_hq = sorted({p.get('inc_ward') for p in drs if yn(p.get('need_hq')) == 'YES'})
        if expect_missing is not None:
            check('the run has a ward whose missionaries are not accounted for' if expect_missing else 'every ward\'s latest report has its missionaries accounted for',
                  bool(want_miss) == expect_missing, want_miss)

        msgs = call('GET', '/api/messages')
        recs = [json.loads(m['data_json']) for m in msgs]
        got_dr = [r['dr'] for r in recs if r['type'] == 'dr']
        got = {'dr': len(got_dr), 'so': sum(1 for r in recs if r['type'] == 'so'), 'wcl': sum(1 for r in recs if r['type'] == 'wcl'),
               'inj': sum(ni(x.get('mem_inj')) for x in got_dr), 'dead': sum(ni(x.get('mem_dead')) for x in got_dr),
               'dmg': sum(ni(x.get('homes_dmg')) for x in got_dr), 'dest': sum(ni(x.get('homes_dest')) for x in got_dr),
               'vol': sum(ni(x.get('vol_count')) for x in got_dr)}
        check(f'the EOC\'s records hold what was sent: {want}', got == want, {'EOC': got})

        ro = call('GET', '/api/readout')
        rgot = {'dr': ro['reporting']['reports']['dr'], 'so': ro['reporting']['reports']['so'], 'wcl': ro['reporting']['reports']['wcl'],
                'dmg': ro['property']['homes_damaged'], 'dest': ro['property']['homes_destroyed'], 'vol': ro['volunteers']['count']}
        check('the read-out for a voice net gives the same counts and totals', all(rgot[k] == want[k] for k in rgot), rgot)
        check('the read-out names each ward asking for headquarters help once', sorted(ro['needs']['hq']) == want_hq, (ro['needs']['hq'], want_hq))

        if not sync_playwright:
            print('SKIP the Message Center and wall checks: no Playwright here')
        else:
            with sync_playwright() as pw:
                try:
                    br = pw.chromium.launch()
                except Exception:
                    br = pw.chromium.launch(channel='chrome')
                pg = br.new_page(viewport={'width': 1440, 'height': 900}); errs = []
                pg.on('pageerror', lambda e: errs.append(str(e)[:150])); pg.on('dialog', lambda dl: dl.dismiss())
                pg.goto(f'http://127.0.0.1:{PORT}/', wait_until='load')
                pg.wait_for_function(f'typeof msgs !== "undefined" && msgs.length === {len(msgs)}', timeout=30000)
                pg.wait_for_timeout(800)
                stats = pg.inner_text('#ov-stats')
                n = lambda label: int(re.search(r'(\d+)\s*\n\s*' + label, stats).group(1)) if re.search(r'(\d+)\s*\n\s*' + label, stats) else None
                mc = {'dr': n('Disaster Reports'), 'inj': n('Injuries'), 'dead': n('Deaths'), 'dmg': n('Homes Damaged'), 'dest': n('Homes Destroyed'),
                      'vol': n('Volunteers \\(Disaster Reports\\)')}
                check('Message Center Overview tiles show the same counts and totals', all(mc[k] == want[k] for k in mc), mc)
                bar = pg.inner_text('#miss-bar')
                named = sorted(x.strip() for x in bar.split(':', 1)[-1].split(',')) if 'NOT ACCOUNTED' in bar else []
                check(f'Message Center missionary bar names each ward whose latest report says NO, once ({want_miss or "none"})',
                      named == want_miss and ('NOT ACCOUNTED' in bar) == bool(want_miss), bar[:200])
                alerts = pg.inner_text('#ov-alerts')
                m = re.search(r'help from Church headquarters\s*\n([^\n]*)', alerts)
                hq = sorted(x.strip() for x in m.group(1).split(',')) if m else []
                check('Message Center headquarters list names each ward once', hq == want_hq, (hq, want_hq))
                pg.evaluate('buildSitrep()'); pg.wait_for_timeout(500)
                sit = pg.inner_text('#sitrep-pre')
                a = sit.split('SECTION A', 1)[-1].split('SECTION B', 1)[0]
                check('SITREP section A agrees with the missionary bar',
                      (('NOT ACCOUNTED FOR' in a) == bool(want_miss)) and all(w in a for w in want_miss) and all(a.count(w) == 1 for w in want_miss), a[:300])
                role_checks(pg, msgs, recs, want_miss, not expect_missing)
                check('the Message Center raised no page error', not errs, errs)

                wl = br.new_page(viewport={'width': 1920, 'height': 1080}); werrs = []
                wl.on('pageerror', lambda e: werrs.append(str(e)[:150]))
                wl.goto(f'http://127.0.0.1:{PORT}/wall', wait_until='load')
                wl.wait_for_function('document.getElementById("rep-v") && document.getElementById("rep-v").textContent.trim() !== ""', timeout=30000)
                wl.wait_for_timeout(1500)
                nums = lambda sel: [int(x) for x in re.findall(r'\d+', wl.inner_text(sel))]
                wall = {'reports': nums('#rep-v'), 'life': nums('#life-v'), 'homes': nums('#homes-v')}
                check('the wall shows the same reports, injured / deaths and homes damaged / destroyed',
                      wall == {'reports': [want['dr'] + want['so'] + want['wcl']], 'life': [want['inj'], want['dead']], 'homes': [want['dmg'], want['dest']]}, wall)
                body = wl.inner_text('body')
                mline = re.search(r'Missionaries not accounted for\s*\n?\s*([^\n]*)', body)
                wnamed = sorted(x.strip() for x in mline.group(1).split(',')) if mline and want_miss else []
                check('the wall\'s Needs panel names each ward whose latest report says NO, once', wnamed == want_miss if want_miss else
                      (mline and 'none' in mline.group(1).lower()), mline.group(1) if mline else body[:200])
                acts = [a for a in call('GET', '/api/actions') if a.get('status') != 'done']
                n_dec = sum(1 for a in acts if is_decision(a))
                m = re.search(r'(\d+) to decide', wl.inner_text('#act-sum'))
                check(f'the wall\'s work items count the decisions to make ({n_dec})', (int(m.group(1)) if m else 0) == n_dec, wl.inner_text('#act-sum'))
                check('the wall raised no page error', not werrs, werrs)
                if expect_missing is False:
                    totals_checks(pg, wl, drs)
                br.close()

    STAGE[0] = 'just before the found report'
    deliver(found_t)
    verify(True)
    STAGE[0] = 'at the end'
    deliver(1e9)
    runner.stop()
    dup = [it['id'] for it, r in sent if r.get('new') != 1]
    check(f'the EOC files every report the simulator sent by phone, none refused as a duplicate ({len(sent)} sent)', sent and not dup, dup[:5])
    verify(False)

    # the trainer: every role's own score, and a cover that tells the truth about the run and the community
    STAGE[0] = 'debrief'
    runner.run['clock']['elapsed_min'] = run['clock']['duration_min'] + 0.6       # a finished run stops a little past its end
    try:
        runner._needs_tick(final=True)
    except Exception as e:
        print('      (needs check:', type(e).__name__, e, ')')
    rep = runner.report()
    rs, needs = rep.get('roles_score') or {}, rep.get('needs') or []
    check(f'trainer: each person\'s score counts every need they share, one name per line ({len(needs)} needs, {len(rs)} roles)',
          needs and sum(d['total'] for d in rs.values()) == sum(len(engine.role_people(n.get('role') or engine.NEED_ROLE.get(n['cat'], ''))) for n in needs)
          and all(d['met'] + d['late'] + d['open'] + d['overdue'] + d['missed'] == d['total'] for d in rs.values())
          and not any(' and ' in r or ',' in r for r in rs), rs)
    deb = engine.debrief_html(rep)
    check('trainer: the debrief has a slide with each role\'s score, one line per role', "Each role's score" in deb and deb.count("<div class='cat'>") >= len(rs))
    check('trainer: the debrief cover never shows past the end ("T+240 of 240") and calls the invented community invented',
          'T+240 of 240 drill minutes' in deb and 'all invented' in deb and 'names are real' not in deb, re.findall(r'T\+\d+ of \d+', deb)[:2])
    check('trainer: the after-action report (text and page) lists each role\'s score',
          "EACH ROLE'S SCORE" in engine.report_text(rep) and "Each role's score" in engine.report_html(rep))
finally:
    if proc:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
    shutil.rmtree(SP, ignore_errors=True)

print(f'\n{sum(res)}/{len(res)} passed')
sys.exit(0 if all(res) else 1)
