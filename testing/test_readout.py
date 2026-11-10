#!/usr/bin/env python3
"""Incident read-out test (GET /api/readout, emcomm-readout/1; contract in docs/contracts/emcomm-readout/).

A scratch EOC server (port 8086) is seeded with invented Juniper Plains reports, roster and event; then:
  - the document passes the contract's schema (a small validator here: no new dependencies) and so do the fixtures;
  - its fingerprint is the contract's (and the fixtures' fingerprints check out);
  - it carries no injuries, deaths, missionary status, names, phones, emails, addresses or GPS;
  - its totals equal hand-computed ones for the seeded data;
  - readout-latest.json is written beside the server on the call and again when a SITREP is saved;
  - readout.build() gives null (never 0) where nothing was reported, reads old flat records, flags exercises;
  - with Playwright installed: the Message Center's own buildSitrep() in Chromium gives the same totals (parity).

    python testing/test_readout.py
"""
import json, os, pathlib, re, shutil, sqlite3, subprocess, sys, tempfile, time, urllib.error, urllib.request
REPO = pathlib.Path(__file__).resolve().parent.parent
CONTRACT = REPO / 'docs' / 'contracts' / 'emcomm-readout'
PORT = int(next((a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('--port=')), '8086'))
SP = pathlib.Path(tempfile.mkdtemp(prefix='eoc_readout_test_'))
sys.path.insert(0, str(REPO / 'eoc'))
import readout   # noqa: E402  (the module under test, from the repository)

res = []


def check(label, ok, detail=''):
    ok = bool(ok); res.append(ok); print(('PASS ' if ok else 'FAIL ') + label + (' -- ' + str(detail)[:300] if detail and not ok else ''), flush=True)


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}{path}', data=data, method=method, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode('utf-8'))


# ── A small JSON Schema check: the keywords the contract uses ────────────────
_TYPES = {'object': dict, 'array': list, 'string': str, 'boolean': bool, 'null': type(None)}


def _is(v, t):
    if t == 'integer':
        return isinstance(v, int) and not isinstance(v, bool)
    if t == 'number':
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    return isinstance(v, _TYPES[t])


def validate(v, s, at='$'):
    """Errors of v against schema s (type, const, enum, required, properties, items, maxItems, pattern, maxLength)."""
    errs = []
    if 'const' in s and v != s['const']:
        errs.append(f'{at}: {v!r} is not {s["const"]!r}')
    if 'enum' in s and v not in s['enum']:
        errs.append(f'{at}: {v!r} not one of {s["enum"]}')
    if 'type' in s:
        ts = s['type'] if isinstance(s['type'], list) else [s['type']]
        if not any(_is(v, t) for t in ts):
            return errs + [f'{at}: {type(v).__name__} is not {ts}']
    if isinstance(v, dict):
        errs += [f'{at}: missing {k}' for k in s.get('required', []) if k not in v]
        for k, sub in s.get('properties', {}).items():
            if k in v:
                errs += validate(v[k], sub, f'{at}.{k}')
    if isinstance(v, list):
        if 'maxItems' in s and len(v) > s['maxItems']:
            errs.append(f'{at}: {len(v)} items > {s["maxItems"]}')
        for i, x in enumerate(v):
            errs += validate(x, s.get('items', {}), f'{at}[{i}]')
    if isinstance(v, str):
        if 'pattern' in s and not re.search(s['pattern'], v):
            errs.append(f'{at}: {v!r} does not match {s["pattern"]}')
        if 'maxLength' in s and len(v) > s['maxLength']:
            errs.append(f'{at}: longer than {s["maxLength"]}')
    return errs


SCHEMA = json.loads((CONTRACT / 'emcomm-readout-1.schema.json').read_text(encoding='utf-8'))
DATE_TIME = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}([+-]\d{2}:\d{2}|Z)$')
# keys a read-out must never have, anywhere (owner decision 2026-11-10: not read on an open frequency)
FORBIDDEN = re.compile(r'inj|dead|death|miss|submit|phone|email|addr|lat$|lon$|gps|grid|contact|chief$|sp_?name', re.I)


def keys_of(v, out=None):
    out = set() if out is None else out
    if isinstance(v, dict):
        for k, x in v.items():
            out.add(k); keys_of(x, out)
    elif isinstance(v, list):
        for x in v:
            keys_of(x, out)
    return out


def contract_checks(doc, label):
    errs = validate(doc, SCHEMA)
    check(f'{label}: valid emcomm-readout/1 (schema)', not errs, errs)
    times = [doc['generated_at'], doc['as_of'], doc['pace'].get('since'), doc['incident'].get('next_sitrep_at')]
    check(f'{label}: times are local with an offset', all(t is None or DATE_TIME.match(t) for t in times), times)
    check(f'{label}: fingerprint is sha256 of the canonical JSON without generated_at and fingerprint', doc['fingerprint'] == readout.fingerprint(doc), doc['fingerprint'])
    bad = sorted(k for k in keys_of(doc) if FORBIDDEN.search(k))
    check(f'{label}: no injuries, deaths, missionary status, names, phones, emails, addresses or GPS among the keys', not bad, bad)


for fx in sorted((CONTRACT / 'fixtures').glob('*.json')):
    contract_checks(json.loads(fx.read_text(encoding='utf-8')), f'fixture {fx.name}')

# ── The seeded EOC (invented: Juniper Plains Area, Larkspur Stake) ───────────
PRIVATE = ('Field Worker One', 'Field Worker Two', '555-0101', '555-0102', 'one@example.org', '40.41', '-117.52',
           'Sisters not reached', '12 Aspen Lane', 'Crew Chief Three', 'Bishop Example', '555-0199', 'Deliver Contact')
DRS = [
    {'inc_stake': 'Larkspur Stake', 'inc_ward': 'Larkspur 1st Ward', 'inc_type': 'Earthquake', 'inc_date': '2026-11-10',
     'mem_injuries': '2', 'mem_deaths': '1', 'mem_damaged': '3', 'mem_destroyed': '1', 'vol_count': '10', 'vol_hours': '20',
     'miss_safe': 'NO', 'miss_details': 'Sisters not reached', 'need_local': 'YES', 'sub_name': 'Field Worker One',
     'sub_phone': '555-0101', 'sub_email': 'one@example.org', 'stn_lat_d': '40.41', 'stn_lon_d': '-117.52'},
    {'inc_stake': 'Larkspur Stake', 'inc_ward': 'Larkspur 2nd Ward', 'inc_type': 'Earthquake', 'inc_date': '2026-11-10',
     'mem_damaged': '5', 'mem_destroyed': '0', 'vol_count': '6', 'vol_hours': '7.5', 'miss_safe': 'YES',
     'need_hq': 'YES', 'need_neighbor': 'YES', 'sub_name': 'Field Worker Two', 'sub_phone': '555-0102'},
    {'inc_stake': 'Larkspur Stake', 'inc_ward': 'Larkspur 2nd Ward', 'inc_type': 'Earthquake', 'inc_date': '2026-11-10',
     'mem_damaged': '1', 'need_hq': 'YES', 'sub_name': 'Field Worker Two', 'bldg_damage': 'second report'},
]
SOS = [
    {'req_stake': 'Larkspur Stake', 'order_date': '2026-11-10', 'del_contact': 'Deliver Contact', 'del_addr': '12 Aspen Lane',
     'del_phone': '555-0199', 'gs01': '3', 'wa01': '10', 'other_desc1': 'Generator fuel', 'other_qty1': '4'},
    {'req_stake': 'Larkspur Stake', 'order_date': '2026-11-10', 'wa01': '5', 'tl10': '2'},
]
WCLS = [
    {'log_date': '2026-11-10', 'chief_name': 'Crew Chief Three', 'chief_stake': 'Larkspur Stake', 'chief_ward': 'Larkspur 3rd Ward',
     'chief_hrs': '5', 'crew_name1': 'Crew A', 'crew_hrs1': '4', 'crew_name2': 'Crew B', 'crew_hrs2': '3.5', 'safety_cert': True},
    {'log_date': '2026-11-10', 'chief_name': 'Crew Chief Three', 'chief_stake': 'Larkspur Stake', 'chief_ward': 'Larkspur 1st Ward',
     'crew_name1': 'Crew C', 'crew_hrs1': '2'},
]
UNITS = [f'Larkspur {n} Ward' for n in ('1st', '2nd', '3rd', '4th', '5th', '6th')]
EXPECTED = {   # by hand from the seeded reports, the way buildSitrep() adds them up
    'reports': {'dr': 3, 'so': 2, 'wcl': 2},
    'property': {'homes_damaged': 9, 'homes_destroyed': 1},
    'volunteers': {'count': 16, 'hours': 27},                     # ni('7.5') = 7; the third report's blanks count 0
    'needs': {'local': ['Larkspur 1st Ward'], 'neighbor': ['Larkspur 2nd Ward'], 'hq': ['Larkspur 2nd Ward']},
    'crews': {'logs': 2, 'members': 3, 'hours': 14.5},             # 5 + 4 + 3.5, then 2
    'supplies': {'orders': 2, 'top_items': [{'desc': 'Bottled water (24 bottles per case)', 'qty': 15},
                                            {'desc': 'Generator fuel (other item, local purchase)', 'qty': 4},
                                            {'desc': 'Blanket—3-lb. poly fleece (10 per case)', 'qty': 3},
                                            {'desc': "Extension cord, 100'", 'qty': 2}]},
}

wd = SP / 'site' / 'eoc'
wd.mkdir(parents=True)
for f in ('eoc_server.py', 'EOC_Message_Center.html', 'EOC_Wall_Display.html', 'EOC_Phone.html', 'readout.py'):
    shutil.copy2(REPO / 'eoc' / f, wd / f)
shutil.copytree(REPO / 'templates', SP / 'site' / 'templates')
log = open(SP / 'eoc.log', 'w', encoding='utf-8')   # a file, not a pipe: a full pipe would freeze the server
proc = subprocess.Popen([sys.executable, '-u', 'eoc_server.py', str(PORT)], cwd=str(wd), stdout=log, stderr=subprocess.STDOUT,
                        env=dict(os.environ, PYTHONIOENCODING='utf-8', LOCALAPPDATA=str(SP / 'appdata'), USERPROFILE=str(SP / 'home'),
                                 EMCOMM_DOCUMENTS=str(SP / 'documents')))
try:
    for _ in range(80):
        try: call('GET', '/api/status'); break
        except Exception: time.sleep(0.25)
    # an empty event first: nothing reported is null, never 0
    empty = call('GET', '/api/readout')
    contract_checks(empty, 'empty event')
    check('empty event: counts nobody reported are null, report counts 0, units unknown',
          empty['property'] == {'homes_damaged': None, 'homes_destroyed': None} and empty['volunteers'] == {'count': None, 'hours': None}
          and empty['crews'] == {'logs': 0, 'members': None, 'hours': None} and empty['reporting']['units_expected'] is None
          and empty['reporting']['not_reported'] is None and empty['as_of'] is None and empty['incident']['interval_hours'] is None
          and empty['pace'] == {'level': None, 'since': None}, empty)

    pace_ts = int(time.time() * 1000) - 3600000
    inc = call('GET', '/api/incident')
    inc.update({'eocName': 'Larkspur Stake EOC', 'eocLevel': 'stake', 'name': 'Larkspur earthquake', 'type': 'Earthquake', 'area': 'Larkspur',
                'sitrepHrs': '4', 'sitrepBy': 'Stake President', 'pace': 'C', 'paceTs': pace_ts, 'startTs': pace_ts,
                'rollups': [{'from': 'Larkspur 2nd Ward Satellite EOC', 'level': 'satellite', 'at': pace_ts, 'new': 1}]})
    call('PUT', '/api/incident', inc)
    call('PUT', '/api/roster', [{'id': f'u{i}', 'name': n, 'spName': 'Bishop Example', 'spPhone': '555-0199'} for i, n in enumerate(UNITS)])
    up = call('POST', '/api/upload', {'reports': [{'id': f'r{i}', 'form': f, 'data': d} for i, (f, d) in enumerate(
        [('dr', d) for d in DRS] + [('so', d) for d in SOS] + [('wcl', d) for d in WCLS])]})
    check('seeded 3 Disaster Reports, 2 Supply Orders, 2 Work Crew Logs', up.get('new') == 7, up)

    doc = call('GET', '/api/readout')
    print('\n/api/readout for the seeded data:\n' + json.dumps(doc, indent=1, ensure_ascii=False) + '\n')
    contract_checks(doc, 'seeded event')
    text = json.dumps(doc, ensure_ascii=False)
    leaked = [p for p in PRIVATE if p in text]
    check('seeded event: no submitter, crew chief, leader, phone, email, address, GPS or missionary detail in the document', not leaked, leaked)
    for k, v in EXPECTED.items():
        got = doc['reporting']['reports'] if k == 'reports' else doc[k]
        check(f'seeded event: {k} = hand-computed totals', got == v, (got, v))
    rp = doc['reporting']
    check('seeded event: reported = units with a Disaster Report; expected and not reported from the roster',
          rp['reported'] == ['Larkspur 1st Ward', 'Larkspur 2nd Ward'] and rp['units_reported'] == 2 and rp['units_expected'] == 6
          and rp['not_reported'] == UNITS[2:] and rp['unit_word'] == 'ward' and rp['via_rollup'] == ['Larkspur 2nd Ward Satellite EOC'], rp)
    check('seeded event: source, approver, pace, incident from the EOC and its event',
          doc['source']['eoc'] == {'name': 'Larkspur Stake EOC', 'level': 'stake'} and doc['source']['event']['name'] == 'Larkspur earthquake'
          and doc['source']['event']['exercise'] is False and doc['source']['forms_version'] == call('GET', '/api/status')['formsVersion']
          and doc['approver'] == {'role': 'Stake President or his delegate'} and doc['pace'] == {'level': 'C', 'since': readout.iso_local(pace_ts)}
          and doc['incident']['interval_hours'] == 4 and doc['incident']['next_sitrep_at'] == readout.iso_local(pace_ts + 4 * 3600000)
          and doc['notes'] == [], (doc['source'], doc['pace'], doc['incident']))
    again = call('GET', '/api/readout')
    check('same data, same fingerprint (generated_at does not count)', again['fingerprint'] == doc['fingerprint'])
    rl = wd / 'readout-latest.json'
    fdoc = json.loads(rl.read_text(encoding='utf-8')) if rl.is_file() else {}
    check('readout-latest.json written beside the server on the call (no temp file left)', fdoc.get('fingerprint') == doc['fingerprint']
          and not (wd / 'readout-latest.json.tmp').exists(), rl)

    # a SITREP saved (the page PUTs a new lastSitrepTs) rewrites the file; other saves do not
    rl.unlink()
    inc = call('GET', '/api/incident'); inc['ic'] = 'Incident Commander'; call('PUT', '/api/incident', inc)
    check('an incident save without a new SITREP does not write the file', not rl.exists())
    st = int(time.time() * 1000) - 600000   # ten minutes ago: the page's own SITREP below is later
    inc['lastSitrepTs'] = st; call('PUT', '/api/incident', inc)
    fdoc = json.loads(rl.read_text(encoding='utf-8')) if rl.is_file() else {}
    check('a new SITREP (lastSitrepTs) writes readout-latest.json, next SITREP 4 hours on', fdoc.get('incident', {}).get('next_sitrep_at') == readout.iso_local(st + 4 * 3600000), fdoc.get('incident'))

    # ── Parity with the page's own buildSitrep() (Chromium) ──────────────────
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sync_playwright = None
        print('SKIP JavaScript parity: playwright is not installed (python -m pip install playwright; python -m playwright install chromium)')
    if sync_playwright:
        with sync_playwright() as p:
            try:
                b = p.chromium.launch()
            except Exception:   # no Playwright Chromium downloaded (the Windows VM): the installed Chrome
                b = p.chromium.launch(channel='chrome')
            pg = b.new_page(viewport={'width': 1366, 'height': 900})
            errs = []
            pg.on('pageerror', lambda e: errs.append(str(e)))
            pg.on('dialog', lambda d: d.dismiss())
            pg.goto(f'http://127.0.0.1:{PORT}/')
            pg.wait_for_function('typeof msgs !== "undefined" && msgs.length === 7 && typeof incident === "object" && incident.eocName', timeout=20000)
            pg.evaluate('buildSitrep()')
            txt = pg.inner_text('#sitrep-pre')
            tiles = pg.evaluate('''() => { var o = {}; renderDRAgg(msgs.filter(function(m){return m.type==="dr";}));
                document.querySelectorAll("#dr-agg-stats .stat").forEach(function(s){ o[s.querySelector(".l").textContent] = s.querySelector(".n").textContent; }); return o; }''')
            agg = pg.evaluate('soAggregate(msgs.filter(function(m){return m.type==="so";})).map(function(a){return {desc:a.desc, qty:a.total};})')
            b.close()

        def grab(rx, cast=float):
            m = re.search(rx, txt)
            return cast(m.group(1)) if m else None

        def unit_list(label):
            m = re.search(r'needing ' + label + r'[^\n]*\n\s+([^\n]*)', txt) if label != 'hq' else re.search(r'requesting Church HQ support[^\n]*\n\s+([^\n]*)', txt)
            names = [] if not m or m.group(1).strip() == 'None' else [s.strip() for s in m.group(1).split(',')]
            return sorted(set(names))
        js = {'homes_damaged': int(tiles.get('Homes Damaged', -1)), 'homes_destroyed': int(tiles.get('Homes Destroyed', -1)),
              'vol_count': grab(r'Total volunteers:\s+([\d.]+)'), 'vol_hours': grab(r'Total volunteer hours:\s+([\d.]+)'),
              'logs': grab(r'Work crew logs received:\s+(\d+)'), 'members': grab(r'Total crew members:\s+(\d+)'),
              'crew_hours': grab(r'SECTION G[\s\S]*Total volunteer hours:\s+([\d.]+)'), 'orders': grab(r'(\d+) supply order\(s\) received'),
              'local': unit_list('local Church facilities'), 'neighbor': unit_list('neighboring unit assist'), 'hq': unit_list('hq')}
        py = {'homes_damaged': doc['property']['homes_damaged'], 'homes_destroyed': doc['property']['homes_destroyed'],
              'vol_count': doc['volunteers']['count'], 'vol_hours': doc['volunteers']['hours'], 'logs': doc['crews']['logs'],
              'members': doc['crews']['members'], 'crew_hours': doc['crews']['hours'], 'orders': doc['supplies']['orders'],
              'local': doc['needs']['local'], 'neighbor': doc['needs']['neighbor'], 'hq': doc['needs']['hq']}
        check('page loaded with no script error', not errs, errs)
        check('parity: the page\'s buildSitrep() totals equal the read-out\'s (homes, volunteers, crews, orders, needs)', js == py, {k: (js[k], py[k]) for k in js if js[k] != py[k]})
        top_js = sorted(agg, key=lambda a: -a['qty'])[:5]
        check('parity: the page\'s soAggregate() largest five equal the read-out\'s top items', top_js == doc['supplies']['top_items'], (top_js, doc['supplies']['top_items']))
        time.sleep(1.0)   # the page saves the SITREP time a moment after generating it
        fdoc = json.loads(rl.read_text(encoding='utf-8')) if rl.is_file() else {}
        page_st = call('GET', '/api/incident').get('lastSitrepTs') or 0
        check('Generate SITREP in the page rewrote readout-latest.json with the same facts and the next SITREP from it', fdoc.get('reporting') == doc['reporting']
              and fdoc.get('property') == doc['property'] and page_st > st and fdoc.get('incident', {}).get('next_sitrep_at') == readout.iso_local(page_st + 4 * 3600000), (page_st, fdoc.get('incident')))
finally:
    proc.terminate()
    try: proc.wait(timeout=5)
    except Exception: proc.kill()

# ── readout.build() on its own: nulls, old flat records, exercise, area level ─
conn = sqlite3.connect(':memory:'); conn.row_factory = sqlite3.Row
conn.executescript('''CREATE TABLE messages (id TEXT, received_ms INTEGER, type TEXT, data_json TEXT, event_id TEXT);
    CREATE TABLE roster (id TEXT, data_json TEXT, event_id TEXT); CREATE TABLE incident (singleton INTEGER, data_json TEXT);
    CREATE TABLE events (id TEXT, created_ms INTEGER, status TEXT, active INTEGER, data_json TEXT);''')
conn.execute("INSERT INTO incident VALUES (1, ?)", (json.dumps({'eocName': 'Juniper Plains Area EOC', 'eocLevel': 'area', 'eocUnits': 'Larkspur Stake; Kestrel Stake, Saddleback Stake'}),))
conn.execute("INSERT INTO events VALUES ('e1', 0, 'open', 1, ?)", (json.dumps({'name': 'Larkspur earthquake drill', 'sitrepHrs': '3', 'pace': 'X'}),))
rows = [('m1', 1762822620000, 'dr', {'type': 'dr', 'dr': {'stake': 'Larkspur Stake', 'ward': 'Larkspur 2nd Ward', 'homes_dmg': '4', 'need_hq': 'Y', 'exercise': 'YES', 'mem_inj': '3'}}),
        ('m2', 1762822680000, 'DR', {'type': 'DR', 'stake': 'Kestrel Stake', 'need_local': 'yes', 'submitter': 'Someone'}),   # old flat format
        ('m3', 1762822740000, 'wcl', {'type': 'wcl', 'wcl': {'chief_stake': 'Kestrel Stake'}}),
        ('m4', 1762822800000, 'ics', {'type': 'ics', 'ics': {'subject': 'not counted'}})]
for i, ms, t, d in rows:
    conn.execute('INSERT INTO messages VALUES (?,?,?,?,?)', (i, ms, t, json.dumps(d), 'e1'))
b = readout.build(conn, 'e1', generated_at='2026-11-10T19:02:11-07:00')
contract_checks(b, 'build() at an area EOC')
check('build(): a value no report carried is null (homes destroyed, volunteers, crew members and hours), a reported one is summed',
      b['property'] == {'homes_damaged': 4, 'homes_destroyed': None} and b['volunteers'] == {'count': None, 'hours': None}
      and b['crews'] == {'logs': 1, 'members': None, 'hours': None}, (b['property'], b['volunteers'], b['crews']))
check('build(): area level counts stakes, the Area Authority approves, units from "Units covered" in its order',
      b['reporting']['unit_word'] == 'stake' and b['approver']['role'] == 'Area Authority or his delegate' and b['reporting']['reported'] == ['Kestrel Stake', 'Larkspur Stake']
      and b['reporting']['units_expected'] == 3 and b['reporting']['not_reported'] == ['Saddleback Stake'], b['reporting'])
check('build(): old flat record read, Y and yes count as yes, an ICS (Incident Command System) message not counted',
      b['needs'] == {'local': ['Kestrel Stake'], 'neighbor': [], 'hq': ['Larkspur Stake']} and b['reporting']['reports'] == {'dr': 2, 'so': 0, 'wcl': 1}, b['needs'])
check('build(): one report marked THIS IS AN EXERCISE makes the read-out an exercise', b['source']['event']['exercise'] is True)
check('build(): an interval leadership never set (3 h) and an unknown PACE level are null', b['incident']['interval_hours'] is None and b['incident']['next_sitrep_at'] is None and b['pace'] == {'level': None, 'since': None})
check('build(): as_of is the newest counted record', b['as_of'] == readout.iso_local(1762822740000), b['as_of'])
check('build(): a drill simulator feeding the EOC also makes it an exercise', readout.build(conn, 'e1', drill_active=True)['source']['event']['exercise'] is True)
check('build(): the Supply Order catalog is read from the page (65 items)', len(readout.catalog()['items']) == 65, len(readout.catalog()['items']))

shutil.rmtree(SP, ignore_errors=True)
print('\nRESULT:', 'ALL PASS' if all(res) else 'FAILURES', f'({sum(res)}/{len(res)})')
sys.exit(0 if res and all(res) else 1)
