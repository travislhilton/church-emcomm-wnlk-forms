#!/usr/bin/env python3
"""EMCOMM simulator test: engine, privacy and server against a synthetic organization pack
(testing/fixtures/orgpack-synthetic.json: invented units and people, generic coordinates)
and a scratch EOC server on port 8085. Nothing from secure data/ is read.

    python testing/test_sim.py            # scratch folders in a temp dir, servers stopped at the end
    python testing/test_sim.py --keep     # leave the EOC (8085) and simulator (8095) running for browser checks

Checks: pack load and summary; pseudonymization (deterministic, unique, no leaks, last names
kept); scenario catalog and local binding merge; severity bands; run planning (every unit
reports, tags, same_as, per-severity values, Supply Order items, Work Crew rows); Winlink
message bodies parse with the EOC's own tag parser; delivery over phone, Winlink (.mime into
a watched folder) and Drop Folder channels files the reports at the EOC; PACE push; the
simulator server's API (pack, scenarios, plan, start/pause/stop, item actions, export); the evaluation
model (section 6: needs ledger, consequences, replies from the line above, waive, scoreboard, after-action report);
the stake's emergency roles as placeholders and the consent flow for real contacts (section 7).
"""
import io
import json
import re
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / 'simulation'))
import engine    # noqa: E402
import orgpack   # noqa: E402
import privacy   # noqa: E402

FIX = REPO / 'testing' / 'fixtures' / 'orgpack-synthetic.json'
keep = '--keep' in sys.argv
SP = pathlib.Path(next((a for a in sys.argv[1:] if not a.startswith('--')), '') or tempfile.mkdtemp(prefix='eoc_sim_test_'))
EOC_PORT, SIM_PORT = 8085, 8095
res = []


def check(label, ok, detail=''):
    ok = bool(ok)
    res.append(ok)
    print(('PASS ' if ok else 'FAIL ') + label + (' -- ' + str(detail)[:200] if detail else ''))


def call(port, method, path, body=None, raw=False):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=data, method=method, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=20) as r:
        b = r.read()
        return (r.status, b) if raw else json.loads(b.decode('utf-8'))


def wait_port(port):
    for _ in range(80):
        try:
            call(port, 'GET', '/api/status' if port == EOC_PORT else '/api/info')
            return True
        except Exception:
            time.sleep(0.25)
    return False


# ── 1. pack and privacy (no servers) ──
pack = orgpack.load(FIX)
s = orgpack.summary(pack)
check('fixture pack loads: 2 stakes, 6 units, 3 buildings, flags', s['stakes'] == 2 and s['units'] == 6 and s['buildings'] == 3 and s['flags'] == {'care_facility': 1, 'language_unit': 1}, s)
idx = orgpack.Index(pack)
check('Index: head of a unit and stake president resolve', idx.head(idx.units['U1'])['role'] == 'Bishop' and idx.stake_president('S1')['role'] == 'Stake President')
check('parse_address: street / city / state / zip', orgpack.parse_address('123 N 400 E\nLarkspur, Utah 89701-1234\nUnited States') == {'street': '123 N 400 E', 'city': 'Larkspur', 'state': 'UT', 'zip': '89701'})
check('split_name drops suffixes', orgpack.split_name('John Q. Public Jr.') == ('John', 'Public'))
# roles the directory does not list (ERD, specialist): a local file beside the pack
import copy as _copy, random as _random
p2 = _copy.deepcopy(pack)
lroles = [{'org': 'S1', 'role': 'Emergency Response Director', 'first': 'Pat', 'last': 'Tester', 'mobile': '000-000-0199', 'email': 'erd@example.test'},
          {'org': 'U2', 'role': 'Amateur Radio Operator', 'first': 'Lee', 'last': 'Radio', 'mobile': '000-000-0198', 'email': ''},
          {'org': 'NOPE', 'role': 'Ignored', 'first': 'x', 'last': 'y'}]
n_added = orgpack.apply_local_roles(p2, lroles)
i2 = orgpack.Index(p2)
check('local roles: two applied (unknown organization skipped), contacts + leaders of their org, ERD and HAM resolve', n_added == 2 and len(p2['contacts']) == len(pack['contacts']) + 2 and 'local-1' in i2.stakes['S1']['leaders'] and 'local-2' in i2.units['U2']['leaders']
      and i2.erd('S1')['name'] == 'Pat Tester' and i2.erd('S1', i2.units['U2'])['name'] == 'Pat Tester' and i2.leader(i2.units['U2'], ('Amateur Radio Operator',))['name'] == 'Lee Radio', (n_added, i2.erd('S1')))
check('local roles: applying again replaces (no duplicates)', orgpack.apply_local_roles(p2, lroles[:1]) == 1 and sum(1 for c in p2['contacts'] if c.get('local')) == 1 and i2.stakes['S1']['leaders'].count('local-1') == 1)
orgpack.apply_local_roles(p2, lroles)
ps2 = privacy.pseudonymize(p2, 'salt-A'); e2 = orgpack.Index(ps2).erd('S1')
check('local roles: pseudonymized like everyone else (first name invented, last kept, a 555-01xx fiction phone, sim email), no leak', e2['last'] == 'Tester' and e2['first'] != 'Pat' and re.fullmatch(r'\d{3}-555-01\d\d', e2['mobile']) and e2['email'].endswith('@churchemcomm.sim') and privacy.leaks(ps2, p2) == [], e2)
ctx2 = engine._Ctx(i2, dict(i2.units['U2'], severity=2), {'eoc': {}, 'id': 'test-run'}, _random.Random(1), '2026-10-30')   # the planner adds severity
check('engine context names the ERD (and a placeholder specialist when none was added)', ctx2.values['erd'] == 'Pat Tester' and ctx2.values['erd_phone'] == '000-000-0199' and ctx2.values['specialist'].startswith('the Welfare') and 'Lee Radio' not in [c.get('name') for c in ctx2.crew], ctx2.values['specialist'])
rq = {r['key']: r for r in orgpack.required_status(p2, {'role': 'stake', 'stake': 'S1', 'satellite_units': []})}
check('required roles (stake): SP and bishops filled from the directory, ERD filled by the local role, specialist missing with an Add hint, HAM filled by the ward operator, operator = room',
      rq['sp']['filled'] and rq['bishop']['filled'] and len(rq['bishop']['who']) == 4 and rq['erd']['filled'] and rq['erd']['who'][0]['who'] == 'Pat Tester'
      and not rq['specialist']['filled'] and rq['specialist']['add'] == {'org': 'S1', 'role': orgpack.SPECIALIST_ROLES[0]} and rq['ham']['filled'] and rq['operator']['status'] == 'room' and 'seventy' not in rq,
      {k: v['status'] for k, v in rq.items()})
rq2 = {r['key']: r for r in orgpack.required_status(pack, {'role': 'area', 'councils': ['C1'], 'played_stakes': []})}
check('required roles (area): Area Seventy from the council, WSRM from the welfare region, HAM missing, no stake rows',
      rq2['seventy']['filled'] and 'wsrm' in rq2 and not rq2['ham']['filled'] and 'sp' not in rq2 and 'bishop' not in rq2, {k: v['status'] for k, v in rq2.items()})
rq3 = {r['key']: r for r in orgpack.required_status(pack, {'role': 'satellite', 'stake': 'S1', 'units': ['U1', 'U2']})}
check('required roles (satellite): bishops of the two covered wards only', rq3['bishop']['filled'] and len(rq3['bishop']['who']) == 2 and not rq3['erd']['filled'])
check('every simulated report is marked THIS IS AN EXERCISE', engine.build_form('dr', {}, ctx2).get('exercise') == 'YES' and engine.build_form('wcl', {}, ctx2).get('exercise') == 'YES')
lrp = orgpack.local_roles_path(FIX)
check('local roles file lives under <pack folder>/simulation/ (git-ignored for the fixture)', lrp == FIX.parent / 'simulation' / 'local-roles.json')
ps = privacy.pseudonymize(pack, 'salt-A')
check('pseudonymized: deterministic for the same salt', json.dumps(ps, sort_keys=True) == json.dumps(privacy.pseudonymize(pack, 'salt-A'), sort_keys=True))
check('pseudonymized: different salt, different names', privacy.pseudonymize(pack, 'salt-B')['contacts'][1]['first'] != ps['contacts'][1]['first'] or privacy.pseudonymize(pack, 'salt-B')['contacts'][1]['phone'] != ps['contacts'][1]['phone'])
check('pseudonymized: no real phone, email or full name survives', privacy.leaks(ps, pack) == [], privacy.leaks(ps, pack))
FICTION = re.compile(r'\d{3}-555-01\d\d')          # 555-0100..0199: reserved for fiction in every area code
check('pseudonymized: last names kept, every phone NXX-555-01xx (reserved fiction range, any state), first.last@churchemcomm.sim emails', all(a['last'] == b['last'] for a, b in zip(pack['contacts'], ps['contacts']))
      and all(FICTION.fullmatch(c['phone']) for c in ps['contacts'] if c['phone'])
      and all(FICTION.fullmatch(o['phone']) for o in ps['stakes'] + ps['units'] + ps['buildings'] if o.get('phone'))
      and all(c['email'].endswith('@churchemcomm.sim') and c['email'].split('@')[0].split('.')[0] == privacy._ascii_slug(c['first'].split(' ')[0]) for c in ps['contacts'] if c['email']),
      [(c['org'], c['phone']) for c in ps['contacts'] if c['phone']][:6])
# more people than one area code's 100 fiction numbers: still one unique number each (the area code varies)
_big = {'kind': orgpack.PACK_KIND, 'stakes': [], 'units': [], 'buildings': [], 'councils': [],
        'contacts': [{'id': f'pos{i}', 'person': f'per{i}', 'role': 'Ward Clerk', 'org': 'X', 'first': 'Quorra', 'last': f'Testfam{i % 7}', 'name': f'Quorra Testfam{i % 7}', 'mobile': f'{i:010d}', 'phone': '', 'email': ''} for i in range(450)]}
_bp = privacy.pseudonymize(_big, 's')
check('pseudonymized phones stay unique past 100 people (450: area codes vary) and none equals a real number', len({c['mobile'] for c in _bp['contacts']}) == 450 and all(FICTION.fullmatch(c['mobile']) for c in _bp['contacts'])
      and len({c['mobile'][:3] for c in _bp['contacts']}) > 4 and privacy.leaks(_bp, _big) == [])
# a pseudonym is never another real person's full name: every real first name of one family but one is taken
_names = privacy.FIRST_NAMES
_fam = {'kind': orgpack.PACK_KIND, 'stakes': [], 'units': [], 'buildings': [], 'councils': [],
        'contacts': [{'id': f'f{i}', 'person': f'f{i}', 'role': 'Relief Society President', 'org': 'X', 'first': n, 'last': 'Zed', 'name': f'{n} Zed', 'mobile': '', 'phone': '', 'email': ''}
                     for i, n in enumerate(_names[:-1])]}
_fp = privacy.pseudonymize(_fam, 'salt-A')
_real_full = {c['name'].lower() for c in _fam['contacts']}
check('pseudonymized: no invented name equals a real full name in the pack (a family holding every first name but one), leaks() empty',
      not [c for c in _fp['contacts'] if c['name'].lower() in _real_full] and privacy.leaks(_fp, _fam) == [] and len({c['name'] for c in _fp['contacts']}) == len(_fam['contacts']),
      [c['name'] for c in _fp['contacts'] if c['name'].lower() in _real_full][:3])
check('leaks() compares phones by their digits: (000) 000-0105 written another way is still a leak',
      privacy.leaks({'contacts': [{'note': 'call (000) 000.0105'}]}, {'contacts': [{'mobile': '000-000-0105', 'first': '', 'name': ''}], 'stakes': [], 'units': []}) == ['000-000-0105'])
check('pseudonymized: men\'s callings get men\'s first names; every full name, phone and email unique',
      all(c['first'].split(' ')[0] in privacy.MALE_FIRST_NAMES for c in ps['contacts'] if privacy.is_male_role(c['role']))
      and len({c['name'] for c in ps['contacts']}) == len({c['person'] for c in ps['contacts']})
      and len({c['phone'] for c in ps['contacts'] if c['phone']}) == len({c['person'] for c in ps['contacts'] if c['phone']}))
same = [c for c in ps['contacts'] if c['person'] == 'per-02']
check('pseudonymized: one person in two roles gets one pseudonym', len(same) == 2 and same[0]['name'] == same[1]['name'] and same[0]['phone'] == same[1]['phone'])
check('pseudonymized: organization phone / email replaced (fiction range, sim domain)', FICTION.fullmatch(ps['stakes'][0]['phone']) and ps['stakes'][0]['email'].endswith('@churchemcomm.sim') and FICTION.fullmatch(ps['units'][2]['phone']))

# ── 1b. drill configuration (simulation/drillconfig.py) over the invented pack ──
import drillconfig, orgpack as _op
_bn = _op.apply_building_names(ps, [{'building_id': 'B1', 'name': 'Alpha Stake Center (source)', 'basis': 'source'}])
check('building names: a source name where given, the stake-center convention or "<City> Meetinghouse, <street>" otherwise; units carry building_name',
      ps['buildings'][0]['name'] == 'Alpha Stake Center (source)' and ps['buildings'][2]['name'] == 'Bravo Stake Center'
      and 'Meetinghouse' in ps['buildings'][1]['name'] and all(u.get('building_name') for u in ps['units']), [b['name'] for b in ps['buildings']])
_spec = {'kind': 'church_emcomm_drill_spec', 'v': 1, 'name': 'Test drill', 'scenario': 'copper-creek-dam',
         'event': {'name': 'DRILL test', 'type': 'Earthquake', 'sitrepHrs': '4'},
         'eocs': [{'id': 'alpha', 'level': 'stake', 'stake': 'Alpha Stake', 'manned': 'always', 'winlink': ['n0call-3']},
                  {'id': 'bravo', 'level': 'stake', 'stake': 'Bravo Stake', 'manned': 'optional'},
                  {'id': 'area', 'level': 'area', 'councils': ['Alpha Coordinating Council'], 'building': 'B2', 'manned': 'optional', 'name': 'Area EOC at B2'}]}
_cfg = drillconfig.build(ps, _spec, str(FIX))
_a = next(e for e in _cfg['eocs'] if e['id'] == 'alpha'); _ar = next(e for e in _cfg['eocs'] if e['id'] == 'area')
check('drill config: stake EOC identity from the pack (name, units, location, council line with the Area Seventy, welfare line with the WSRM, Stake President, Winlink station)',
      _a['identity']['eocName'] == 'Alpha Stake EOC' and len(_a['identity']['eocUnits'].split(', ')) == 4 and _a['identity']['eocLat']
      and 'Area Seventy' in _a['identity']['councilName'] and _a['identity']['councilEmail'].endswith('@churchemcomm.sim')
      and 'WSRM' in _a['identity']['welfareName'] and _a['identity']['roles']['sp']['name'] and _a['winlink'] == ['N0CALL-3']
      and _a['identity']['roles']['ham']['phone'] == 'N0CALL-3' and _a['identity']['mapPath'], _a['identity'])
check('drill config: Area EOC covers the council\'s stakes, at its building, with the AWSRM on the welfare line', _ar['identity']['eocLevel'] == 'area'
      and _ar['stakes'] == ['S1', 'S2'] and _ar['building']['id'] == 'B2' and 'AWSRM' in _ar['identity']['welfareName'] and _ar['identity']['roles']['seventy']['name'])
check('drill config: always-staffed EOCs are always on; optional ones only when named', drillconfig.manned_set(_cfg) == {'alpha'} and drillconfig.manned_set(_cfg, ['area']) == {'alpha', 'area'})
check('drill config: with the Area EOC staffed the stake reports to it (parent fields, simulator does not play the line above); without it, no parent and the simulator plays the replies',
      drillconfig.identity_for(_cfg, 'alpha', ['area'])['parentName'] == 'Area EOC at B2' and drillconfig.identity_for(_cfg, 'alpha')['parentName'] == ''
      and drillconfig.site_for(_cfg, 'alpha', ['area']) == {'role': 'stake', 'stake': 'S1', 'parent': 'Area EOC at B2', 'played_parent': True}
      and drillconfig.site_for(_cfg, 'alpha')['played_parent'] is False)
check('drill config: the Area simulator plays every stake without people (Bravo unless Bravo is staffed)',
      drillconfig.site_for(_cfg, 'area', ['area'])['played_stakes'] == ['S1'] and drillconfig.site_for(_cfg, 'area', ['area', 'bravo'])['played_stakes'] == ['S1', 'S2'])
try:
    drillconfig.build(ps, dict(_spec, eocs=[{'id': 'x', 'level': 'stake', 'stake': 'No Such Stake'}]), ''); _err = ''
except ValueError as _e:
    _err = str(_e)
check('drill config: a stake that is not in the pack is an error, named', 'No Such Stake' in _err, _err)

# ── 1c. partner agency (a city EOC that does not run this system): ICS 213RR / 213 by Winlink ──
import tempfile as _tf, re
from pathlib import Path
_sc = engine.load_scenario('copper-creek-dam')
_run = engine.plan(ps, _sc, {'seed': 3, 'today': '2027-01-13', 'eoc': {'name': 'Alpha Stake EOC', 'winlink': 'N0EOC@winlink.org'}})
_ics = [i for i in _run['items'] if i['kind'] == 'ics' and i['status'] == 'pending']
check('ICS: the city EOC\'s resource requests are planned with the scenario\'s own (invented) agency and call sign, no placeholder left',
      _ics and any(i['ics']['agency'] == 'Larkspur City EOC' and i['ics']['call'] == 'SIM-LKCITY' for i in _ics) and all(i['ics']['agency'].endswith('City EOC') for i in _ics)
      and not any(re.search(r'\{[a-z_]+\}', json.dumps(i['ics'])) for i in _ics), [(i['inject'], i['ics']['agency']) for i in _ics][:3])
_gen = engine.plan(ps, dict(_sc, agencies={}), {'seed': 3, 'today': '2027-01-13', 'eoc': {'name': 'Alpha Stake EOC', 'winlink': 'N0EOC@winlink.org'}})
_gi = [i for i in _gen['items'] if i['kind'] == 'ics' and i['status'] == 'pending']
check('ICS: with no agency in the scenario or a binding, generic names (CITYEOC, "<city> City EOC")',
      _gi and all(i['ics']['call'] == 'CITYEOC' and i['ics']['agency'].endswith('City EOC') for i in _gi), [(i['inject'], i['ics']['agency'], i['ics']['call']) for i in _gi][:3])
_rr = next(i for i in _ics if i['ics']['form'] == 'ics213rr')
_name, _data = engine.ics_mime(_rr, _run)
_tmp = Path(_tf.mkdtemp()) / _name; _tmp.write_bytes(_data)
_eocm = engine._eoc_module()
_m = _eocm._parse_mime_file(_tmp); _p = _eocm._parse_ics(_m)
check('ICS: the simulator\'s Winlink ICS 213RR (body + RMS_Express_Form XML) is read by the EOC server as a resource request with its fields',
      _p and _p['form'] == 'ics213rr' and _p['fields'].get('qty') == _rr['ics']['fields']['qty'] and _p['fields'].get('item') and _p['fields'].get('item') in _rr['ics']['fields']['item'] and _m['subject'].startswith('ICS 213RR'), _p)
_plain = dict(_m, xml=[], subject='ICS 213 - Road report', body='GENERAL MESSAGE (ICS 213)\r\nSubject: Road report\r\nMessage: 100 East open again\r\n')
_pp = _eocm._parse_ics(_plain)
check('ICS: a plain-text ICS 213 with no XML is still recognized, its fields read from the text', _pp and _pp['form'] == 'ics213' and _pp['fields'].get('message') == '100 East open again', _pp)
check('ICS: an ordinary message is not taken for an ICS form', _eocm._parse_ics(dict(_m, xml=[], subject='Hello', body='Lunch at noon?')) is None)

# ── 1d. audit fixes 2026-11-02: scenario validator, drill-spec check, LAN privacy views, engine gaps ──
import scenario_check, subprocess as _sp
_r = _sp.run([sys.executable, str(REPO / 'simulation' / 'scenario_check.py'), str(REPO / 'simulation' / 'scenarios' / 'copper-creek-dam.json'), '--pack', str(FIX)],
             capture_output=True, text=True, encoding='utf-8', errors='replace', env=dict(os.environ, PYTHONIOENCODING='utf-8'))
check('scenario_check: copper-creek-dam passes (exit 0, no error) and plans over the fixture', _r.returncode == 0 and '0 error(s)' in _r.stdout and 'planned over the pack' in _r.stdout, _r.stdout[-300:] + _r.stderr[-300:])
_bad = json.loads((REPO / 'simulation' / 'scenarios' / 'copper-creek-dam.json').read_text(encoding='utf-8'))
_bad['id'] = 'zz-broken'                                                 # no catalog entry
_bad['injects'][1]['id'] = _bad['injects'][0]['id']                       # duplicate id
_bad['pace'][1]['level'] = 'X'                                            # unknown PACE level
_bad['injects'].append({'id': 'zz-typo', 'kind': 'note', 't': 999, 'txet': 'oops', 'text': 'Call {bishop} now'})   # unknown key, time, per-unit placeholder
_bad['injects'].append({'id': 'zz-after', 'kind': 'note', 'text': 'x', 'after': {'need': 'nope#zzz', 'is': 'later'}})
_bad['injects'].append({'id': 'zz-form', 'kind': 'form', 'form': 'dr', 'each': 'unit', 'template': 'no-such', 'where': {'in': 'no_such_feature'}})
_bad['phases'][1]['from'] = _bad['phases'][0]['from']                     # overlapping phases
_bad['done']['checks'].append({'id': 'zz', 'label': 'two types', 'pct_min': 50, 'cat_met': 'life'})
_bf = SP / 'broken-scenario.json'; _bf.parent.mkdir(parents=True, exist_ok=True); _bf.write_text(json.dumps(_bad), encoding='utf-8')
_r = _sp.run([sys.executable, str(REPO / 'simulation' / 'scenario_check.py'), str(_bf)], capture_output=True, text=True, encoding='utf-8', errors='replace', env=dict(os.environ, PYTHONIOENCODING='utf-8'))
_want = ('duplicate id', 'must be P, A, C or E', "unknown key 'txet'", 'outside the run', '{bishop} names one unit', "no inject 'nope'", 'after.is', "no template 'no-such'",
         "no feature 'no_such_feature'", 'overlaps', 'exactly one of', 'no entry for')
check('scenario_check: a broken scratch scenario fails (exit 1) listing every planted error, no traceback', _r.returncode == 1 and all(w in _r.stdout for w in _want) and 'Traceback' not in _r.stdout + _r.stderr,
      [w for w in _want if w not in _r.stdout] or _r.stderr[-200:])
_res = scenario_check.check(dict(_bad, injects=[dict(i, need=dict(i.get('need') or {}, label='Shelter for {unit}')) if i['id'] == 'wi-sp-shelter' else i for i in _bad['injects']]))
check('scenario_check: a per-unit placeholder ({unit}) in the need label of a once-filled inject is flagged', any("wi-sp-shelter" in e and '{unit} names one unit' in e for e in _res['errors']))
for _label, _sc_bad, _frag in (('an unknown PACE level', dict(_sc0 := engine.load_scenario('copper-creek-dam'), pace=[{'t': 0, 'level': 'P'}, {'t': 10, 'level': 'Q'}]), 'unknown PACE level'),
                               ('duplicate inject ids', dict(_sc0, injects=_sc0['injects'] + [_sc0['injects'][0]]), 'duplicate inject id')):
    try:
        engine.plan(pack, _sc_bad, {'seed': 1}); _msg = ''
    except ValueError as _e:
        _msg = str(_e)
    check(f'engine.plan refuses {_label} at plan time (not a KeyError mid-drill)', _frag in _msg, _msg)
# drill spec validation
_spec_ok = {'kind': 'church_emcomm_drill_spec', 'v': 1, 'name': 'Drill', 'scenario': 'copper-creek-dam', 'eocs': [{'id': 'alpha', 'level': 'stake', 'stake': 'Alpha Stake', 'manned': 'always', 'winlink': ['N0CALL-3', 'SIM-ALPHA']}],
            'agencies': [{'id': 'city', 'name': 'Alpha City EOC', 'call': 'SIM-CITY', 'serves': ['Alpha Stake']}]}
_spec_bad = {'kind': 'church_emcomm_drill_spec', 'v': 1, 'name': 'Drill: <your scenario> (edit)', 'scenario': 'copper-creek-dam', 'extra': 1,
             'eocs': [{'id': 'alpha', 'level': 'ward', 'stake': 'Alpha Stake', 'manned': 'sometimes', 'winlink': ['N0CALL@winlink.org']},
                      {'id': 'alpha', 'level': 'stake', 'stake': 'Zulu Stake'}],
             'agencies': [{'id': 'city', 'name': 'City EOC', 'serves': ['No Such Stake']}]}
_ve = drillconfig.validate_spec(_spec_bad, ps)
check('drillconfig.validate_spec: a good spec has no problem; a bad one lists unknown keys, level, manned, call sign, starter text, duplicate id, unknown stake and serves',
      drillconfig.validate_spec(_spec_ok, ps) == [] and all(any(f in e for e in _ve) for f in ("unknown key 'extra'", 'level must be', 'manned must be', 'not a call sign', 'starter text left in', 'duplicate id', "'Zulu Stake' is not in the pack", "serves 'No Such Stake'")), _ve)
_sd = SP / 'specdir'; _sd.mkdir(parents=True, exist_ok=True); shutil.copy2(FIX, _sd / 'orgpack.json')
(_sd / 'bad-spec.json').write_text(json.dumps(dict(_spec_bad, export='.')), encoding='utf-8')
_r = _sp.run([sys.executable, str(REPO / 'simulation' / 'drillconfig.py'), str(_sd / 'bad-spec.json')], capture_output=True, text=True, encoding='utf-8', errors='replace')
check('drillconfig.py on a bad spec: exit 1, the problems listed, no traceback, nothing written', _r.returncode == 1 and 'problem(s) in the drill spec' in _r.stdout and 'Traceback' not in _r.stdout + _r.stderr
      and not (_sd / 'drill-config.json').exists(), _r.stdout[-300:] + _r.stderr[-300:])
# community.py init: the example's scenario only where it applies, otherwise a neutral placeholder
import community
_far = json.loads(FIX.read_text(encoding='utf-8'))
for _o in _far['units'] + _far['stakes'] + _far['buildings']:
    if _o.get('lon') is not None:
        _o['lon'] += 60
(_sd / 'far').mkdir(exist_ok=True); (_sd / 'far' / 'orgpack.json').write_text(json.dumps(_far), encoding='utf-8')
(_sd / 'near').mkdir(exist_ok=True); shutil.copy2(FIX, _sd / 'near' / 'orgpack.json')
with __import__('contextlib').redirect_stdout(io.StringIO()):
    community.init(_sd / 'far'); community.init(_sd / 'near')
_s_far = json.loads((_sd / 'far' / 'simulation' / 'drill-spec.json').read_text(encoding='utf-8'))['scenario']
_s_near = json.loads((_sd / 'near' / 'simulation' / 'drill-spec.json').read_text(encoding='utf-8'))['scenario']
check('community.py init: "<scenario id>" for a pack no scenario covers, the covering developed scenario otherwise (never another community\'s id)', _s_far == '<scenario id>' and _s_near == 'copper-creek-dam', (_s_far, _s_near))
# the simulator server's LAN view: only the controller laptop gets real local roles and agency contact names
import sim_server
check('sim_server.is_controller: loopback and this computer are the controller; another LAN address is not', sim_server.is_controller('127.0.0.1') and sim_server.is_controller('::1')
      and sim_server.is_controller('::ffff:127.0.0.1') and not sim_server.is_controller('192.0.2.77'))
_lan = SP / 'lanpack'; (_lan / 'simulation').mkdir(parents=True, exist_ok=True); shutil.copy2(FIX, _lan / 'orgpack.json')
orgpack.write_local_roles(orgpack.local_roles_path(_lan), lroles[:2])
(_lan / 'simulation' / 'copper-creek-dam.local.json').write_text(json.dumps({'agencies': {'city_eoc': {'name': 'Alpha City EOC', 'contact': 'Jordan Example, Fire Chief'}},
                                                                             'injects': [{'id': 'zz-local', 'kind': 'note', 't': 5, 'text': 'Jordan Example asks for sandbags'}]}), encoding='utf-8')
_saved = (sim_server.STATE.export, sim_server.STATE.pack, sim_server.STATE.pack_real, sim_server.STATE.privacy, dict(sim_server.STATE.settings))
_real_pack = orgpack.load(_lan)
sim_server.STATE.export, sim_server.STATE.pack_real, sim_server.STATE.pack, sim_server.STATE.privacy = _lan, _real_pack, privacy.pseudonymize(_real_pack, 'salt-A'), 'pseudonymized'
sim_server.STATE.settings = {'packPath': str(_lan)}
_phone = sim_server.local_roles_view(False); _ctl = sim_server.local_roles_view(True)
check('LAN view of the local roles: pseudonymized names and phones, no path, read only; the controller sees what was typed',
      _phone['readonly'] and not _phone['path'] and '000-000-0199' not in json.dumps(_phone) and 'Pat' not in [r['first'] for r in _phone['roles']] and _phone['roles'][0]['last'] == 'Tester'
      and _ctl['roles'][0]['first'] == 'Pat' and _ctl['roles'][0]['mobile'] == '000-000-0199' and not _ctl['readonly'], _phone['roles'][:1])
_sv = sim_server.scenario_view('copper-creek-dam', False)
check('LAN view of a scenario: agency contact names reduced to the title and removed from texts, no binding path; the controller sees them',
      'Jordan Example' not in json.dumps(_sv) and _sv['agencies']['city_eoc']['contact'] == 'Fire Chief' and _sv.get('local_binding') == 'yes'
      and 'Jordan Example' in json.dumps(sim_server.scenario_view('copper-creek-dam', True)))
_rp = engine.plan(sim_server.STATE.pack, sim_server.scenario_for_run('copper-creek-dam'), {'seed': 2, 'stakes': ['S1']})
check('a pseudonymized run is planned without the agency contact name (what /api/run, /report, /results and /debrief serve)', 'Jordan Example' not in json.dumps(_rp))
_chk = sim_server.check_scenario('copper-creek-dam')
check('the Setup tab\'s scenario check (GET /api/scenarios/<id>/check): copper-creek-dam with its binding passes over the loaded pack', _chk['ok'] and not _chk['errors'], _chk['errors'][:3])
sim_server.STATE.export, sim_server.STATE.pack, sim_server.STATE.pack_real, sim_server.STATE.privacy, sim_server.STATE.settings = _saved
_red = engine.redact_text('Alpha 1st Ward at the stake center: ' + ps['contacts'][0]['name'] + ' (' + ps['contacts'][0]['phone'] + ', ' + ps['contacts'][0]['email'] + ') via SIM-ALPHA1', [ps, pack])
check('redacted report text: unit names numbered, the leader keeps only the first name, phone, email and simulated call replaced',
      'Alpha 1st Ward' not in _red and 'Unit ' in _red and ps['contacts'][0]['last'] not in _red and ps['contacts'][0]['first'] in _red and '[phone]' in _red and '[email]' in _red and 'SIM-UNIT' in _red, _red)
# engine gaps found while writing a scenario
_units = [dict(u, severity=2) for u in pack['units']]
_sel = engine._select(_units, {'tag_not': 'cut', 'sample': 1}, _random.Random(1), {}, {'cut': [u['id'] for u in _units[:-1]]})
check('_select: tag_not is applied before sample (a sample of 1 never lands on an excluded unit and comes back empty)', [u['id'] for u in _sel] == [_units[-1]['id']], [u['id'] for u in _sel])
_scl = engine.load_scenario('copper-creek-dam')
_scl = dict(_scl, injects=[dict(i, need=dict(i.get('need') or {'cat': 'assist'}, label='Answer {unit} by noon')) if i.get('kind') == 'voice' and i.get('each') == 'unit' else i for i in _scl['injects']])
_rl = engine.plan(pack, _scl, {'seed': 5, 'stakes': ['S1']})
_lab = [n for n in _rl['needs'] if n['label'].startswith('Answer ')]
check('need labels are filled per unit when the need is registered ({unit} becomes the ward)', _lab and all('{' not in n['label'] and n['unit'] in n['label'] for n in _lab), [n['label'] for n in _lab][:2])
_ics_it = dict(_rr, need_spec={'cat': 'assist'}, unit='', unit_id='')
_ni = engine.need_for_card(_run, _ics_it); _ni['arose_ms'] = 0
_ag = _rr['ics']['agency']
_acts = [{'id': 'a1', 'cat': 'assist', 'ts': 1, 'title': 'Alpha 1st Ward: crews', 'from': 'EOC'},
         {'id': 'a2', 'cat': 'assist', 'ts': 2, 'title': f'{_ag} resource request (ICS 213RR): sandbags', 'from': f"{_ag} ({_rr['ics']['call']})", 'unit': ''}]
check('ICS needs match the EOC work item by the agency (no unit on it), and by its Winlink key once delivered',
      engine.Runner._match_action(None, _ni, _acts)['id'] == 'a2' and engine.Runner._match_action(None, dict(_ni, match=dict(_ni['match'], key_pref='ics:X')), _acts + [{'id': 'a3', 'key': 'ics:X', 'cat': 'other', 'ts': 3, 'title': 'other'}])['id'] == 'a3', _ni['match'])
_rd = SP / 'gap-runs'
_g = engine.Runner(engine.plan(pack, engine.load_scenario('copper-creek-dam'), {'seed': 5, 'stakes': ['S1']}), 'http://127.0.0.1:9', _rd)
try:
    _ok, _why = _g._done_check({'need_met': 'no-such-inject'}, {}, None, [])
    _g.run['needs'] = [{'id': 'n1', 'item': 'x', 'inject': 'x', 'kind': 'item', 'cat': 'life', 'prio': 1, 'label': 'x', 'state': 'missed', 'arose_t': 1.0, 'times': {}, 'owner': '', 'rule': {}, 'role': ''}]
    _sc_m = _g.score()
    check('done checks: need_met for an inject not in this run is not applicable (None, "not in this run"); no_unowned_high fails on a high need that ended MISSED with no owner',
          _ok is None and 'not in this run' in _why and _sc_m['high_unowned'] == 1 and {c['id']: c['ok'] for c in _sc_m['checks']}['high'] is False, (_ok, _why, _sc_m['high_unowned']))
    _g.save()
    check('the run file is written atomically: no .tmp file left beside it', (_rd / f"run-{_g.run['id']}.json").is_file() and not list(_rd.glob('*.tmp')))
finally:
    _g.shutdown()

# ── 2. scenarios and planning ──
cat = engine.catalog()
check('catalog: the invented example community\'s 9 scenarios, one developed', len(cat['scenarios']) == 9 and sum(1 for x in cat['scenarios'] if x['status'] == 'developed') == 1)
sc = engine.load_scenario('copper-creek-dam')
check('scenario applies to the fixture bbox', engine.bbox_overlaps(sc['applies']['bbox'], idx.bbox()))
sev = {u['id']: engine.severity_of(u, sc) for u in pack['units']}
check('severity: flood path band 3, river flood plain 2, care facility >= 2, far unit lower', sev['U1'] == 3 and sev['U3'] >= 2 and sev['U4'] >= 2 and sev['U5'] < 3, sev)
local = {'severity_override': {'Bravo 1st Ward': 3}, 'injects': [{'id': 'dr-missing', 'kind': 'form', 'form': 'dr', 'each': 'unit', 'where': {'unit': 'Alpha 2nd Ward', 'tag': 'missing'}, 't': 40, 'template': 'dr_missing', 'channel': 'by_pace'},
                                                             {'id': 'n-local', 'kind': 'note', 't': 5, 'text': 'local note'}]}
scl = engine.merge_local(sc, local)
check('local binding: override + replaced inject + added inject', engine.severity_of(idx.units['U5'], scl) == 3 and any(i['id'] == 'n-local' for i in scl['injects'])
      and next(i for i in scl['injects'] if i['id'] == 'dr-missing')['where'].get('unit') == 'Alpha 2nd Ward')
run = engine.plan(ps, scl, {'seed': 3, 'today': '2026-10-30', 'eoc': {'name': 'Alpha Stake EOC', 'winlink': 'EOC-A@winlink.org', 'email': 'eoc@example.test', 'call': 'EOC-A'}})
c = engine.counts(run)
check('plan: every unit has an initial DR; notes, prompts, voice cards present', c['units'] == 6 and sum(1 for i in run['items'] if i['inject'] == 'dr-initial') == 6 and c['note'] >= 16 and c['prompt'] >= 10 and c['voice'] >= 5, c)
check('plan: tags and same_as follow the local binding', run['tags'].get('missing') == ['U2'] and all(i['unit_id'] == 'U2' for i in run['items'] if i['inject'] in ('dr-found', 'v-found', 'v-missing')), run['tags'])
miss = next(i for i in run['items'] if i['inject'] == 'dr-missing')
check('plan: missing-missionaries report says NO with details', miss['payload']['miss_safe'] == 'NO' and 'NOT accounted' in miss['payload']['miss_details'] and miss['payload']['inc_ward'] == 'Alpha 2nd Ward')
dr1 = next(i for i in run['items'] if i['inject'] == 'dr-initial' and i['unit_id'] == 'U1')
p = dr1['payload']
check('plan: DR payload carries stake, ward, pseudonymized bishop, GPS, grid, sim marks', p['inc_stake'] == 'Alpha Stake' and p['inc_ward'] == 'Alpha 1st Ward' and FICTION.fullmatch(p['sub_phone']) and p['stn_grid_d'] and p['sim_run'] == run['id'] and 1 <= int(p['mem_injuries']) <= 15, p)
check('plan: placeholders filled (no braces left)', not any('{' in str(v) for i in run['items'] for v in (i.get('payload') or {}).values()) and not any('{' in i.get('text', '') for i in run['items']))
so = next(i for i in run['items'] if i['kind'] == 'form' and i['form'] == 'so' and i['inject'] == 'so-care')
check('plan: care-facility Supply Order ships to the stake center with catalog items and cots', so['unit_id'] == 'U4' and so['payload']['del_addr'] == pack['stakes'][0]['address'].split(',')[0] and so['payload']['del_city'] == 'Alphaville' and int(so['payload']['wa01']) > 0 and 'Cots' in so['payload']['other_desc1'])
wcl = [i for i in run['items'] if i['kind'] == 'form' and i['form'] == 'wcl' and i['inject'] == 'wcl-crews']
check('plan: Work Crew Logs have crew rows with hours and the safety flag', wcl and all(i['payload'].get('crew_name1') and i['payload'].get('crew_hrs1') and i['payload']['safety_cert'] == 'true' for i in wcl), len(wcl))
# research enrichment (2026-10-31): the walk-up crew's log has no safety acknowledgment and waits on the volunteers need;
# the cut-off canyon unit sends no follow-up report or crew log (tag_not) but its relayed report arrives by voice at T+130;
# per-unit consequences of a stake-wide need (the chest-pain ambulance note) wait for their own unit's need
wu = [i for i in run['items'] if i['inject'] == 'wcl-unsupervised']
cut = run['tags'].get('cutoff', [])
late = [i for i in run['items'] if i['inject'] in ('dr-followup', 'wcl-crews') and i['unit_id'] in cut]
relay = [i for i in run['items'] if i['inject'] == 'dr-relay']
check('lessons: the walk-up crew log (safety NO) waits on the volunteers need; the cut-off unit sends no follow-up or crew log but is relayed by voice',
      len(wu) == 1 and wu[0]['payload']['safety_cert'] == 'false' and wu[0]['status'] == 'waiting' and wu[0]['after']['need'] == 'v-walkups'
      and len(cut) == 1 and not late and len(relay) == 1 and relay[0]['unit_id'] == cut[0] and relay[0]['channel'] == 'voice' and 'RELAYED BY VOICE' in relay[0]['payload']['mem_details'],
      (len(wu), cut, len(late), len(relay)))
amb = [i for i in run['items'] if i['inject'] == 'n-ambulance']
sl = [i for i in run['items'] if i['inject'] in ('n-starlink', 'p-starlink')]
check('lessons: Starlink comes up only after the set-up need is met; 14 roles with the county liaison and the receiving stake',
      len(sl) == 2 and all(i['status'] == 'waiting' and i['after']['need'] == 'p-starlink-setup' for i in sl)
      and any(r['id'] == 'county_liaison' for r in run['roles']) and any(r['id'] == 'receiving_stake' for r in run['roles']) and len(run['roles']) == 14, (len(sl), len(run['roles'])))
check('plan: items sorted by minute, within the scenario duration', all(run['items'][k]['t'] <= run['items'][k + 1]['t'] for k in range(len(run['items']) - 1)) and run['items'][-1]['t'] <= 240)
check('pace_at follows the scripted timeline', [engine.pace_at(run['pace'], t) for t in (0, 79, 80, 174, 175, 225)] == ['P', 'P', 'C', 'C', 'A', 'P'])
check('plan: no unit outside the scope', engine.counts(engine.plan(ps, sc, {'units': ['U1', 'U2']}))['units'] == 2 and engine.counts(engine.plan(ps, sc, {'stakes': ['S2']}))['units'] == 2)
# the run clock's segments map a wall-clock time to the drill minute across speed changes, pauses and jumps
_rr = engine.Runner.__new__(engine.Runner)
_rr.run = {'clock': {'segments': [{'wall': 0, 't': 0, 'speed': 4}, {'wall': 60000, 't': 4, 'speed': 0}, {'wall': 120000, 't': 4, 'speed': 10}, {'wall': 150000, 't': 50, 'speed': 10}]}}
check('drill_minute: 4x for a minute, paused a minute, 10x, a jump to T+50', _rr.drill_minute(30000) == 2 and _rr.drill_minute(90000) == 4 and _rr.drill_minute(126000) == 5 and _rr.drill_minute(156000) == 51 and _rr.drill_minute(-5) == 0,
      [_rr.drill_minute(x) for x in (30000, 90000, 126000, 156000)])
_a = {'ts': 30000, 'log': [{'ts': 126000, 'text': 'Owner: Pat'}]}
check('evidence minutes come from the clock map, not the current speed (owner 3 drill min after creation)', engine.evaluate_rule({'expect': {'owner_within_min': 10}}, [_a], 60, to_t=_rr.drill_minute)[0].endswith('after 3 drill min')
      and engine.evaluate_rule({'expect': {'owner_within_min': 1}}, [_a], 1, to_t=_rr.drill_minute)[1] == '✗', engine.evaluate_rule({'expect': {'owner_within_min': 10}}, [_a], 60, to_t=_rr.drill_minute))

# ── 3. Winlink bodies against the EOC's own parser ──
spec = __import__('importlib.util').util.spec_from_file_location('eoc_server', REPO / 'eoc' / 'eoc_server.py')
eoc = __import__('importlib.util').util.module_from_spec(spec)
with __import__('contextlib').redirect_stdout(io.StringIO()):
    spec.loader.exec_module(eoc)
for form in ('dr', 'so', 'wcl'):
    it = next(i for i in run['items'] if i['kind'] == 'form' and i['form'] == form and not i.get('after'))
    name, data = engine.winlink_mime(it, run)
    tmp = SP / name
    SP.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(data)
    mime = eoc._parse_mime_file(tmp)
    tag = eoc._parse_church_tag(mime['body'])
    want = {'dr': {'stake', 'ward', 'miss_safe', 'mem_inj', 'need_hq', 'lat', 'grid'}, 'so': {'stake', 'items', 'contact', 'zip'}, 'wcl': {'chief', 'chief_ward', 'crew', 'total_hrs', 'safety'}}[form]
    check(f'{form.upper()} .mime: ASCII, parsed by the EOC, tag has the expected keys', all(b < 128 for b in data) and tag and tag[0] == form.upper() and want <= set(tag[1]) and 'SIMULATED' in mime['body'] and mime['from_'].startswith('SIM-'),
          sorted(tag[1]) if tag else mime['body'][:200])
    mapped = eoc._map_worker_to_eoc(form.upper(), it['payload'])
    check(f'{form.upper()} Worker payload: detected and mapped by the EOC', eoc._detect_form_type(engine.FORM_FILENAMES[form], it['payload']) == form.upper() and (mapped.get('stake') or mapped.get('chief_stake')) == it['stake'], mapped)

# ── 4. servers: scratch EOC (8085) + simulator (8095) ──
procs = []
try:
    d = SP / 'eocA'
    if d.exists():
        shutil.rmtree(d)
    (d / 'eoc').mkdir(parents=True)
    for f in ('eoc_server.py', 'EOC_Message_Center.html', 'EOC_Wall_Display.html', 'EOC_Phone.html'):
        shutil.copy2(REPO / 'eoc' / f, d / 'eoc' / f)
    shutil.copytree(REPO / 'templates', d / 'templates')
    received = SP / 'winlink' / 'Received'
    received.mkdir(parents=True, exist_ok=True)
    log = open(SP / 'eocA.log', 'w', encoding='utf-8')          # a file, not a pipe
    env = dict(os.environ, PYTHONIOENCODING='utf-8', LOCALAPPDATA=str(SP / 'appdata'), EMCOMM_DOCUMENTS=str(SP / 'documents'))   # never the real Drop Folder
    procs.append(subprocess.Popen([sys.executable, '-u', 'eoc_server.py', str(EOC_PORT)], cwd=str(d / 'eoc'), stdout=log, stderr=subprocess.STDOUT, env=env))
    check('EOC server up on 8085', wait_port(EOC_PORT))
    inc = call(EOC_PORT, 'GET', '/api/incident')
    inc.update({'eocName': 'Alpha Stake EOC', 'eocLevel': 'stake', 'eocLat': '40.33', 'eocLon': '-117.55', 'name': 'DRILL copper-creek test', 'sitrepHrs': '4', 'sitrepBy': 'Stake President', 'pace': 'P'})
    call(EOC_PORT, 'PUT', '/api/incident', inc)
    # the EOC's Winlink watcher: point it at the scratch Received folder
    wst = call(EOC_PORT, 'PUT', '/api/watcher/config', {'watch_path': str(received), 'enabled': True})
    watcher_ok = wst.get('enabled') and wst.get('watch_path') == str(received)
    print('      (watcher', 'enabled at the scratch folder)' if watcher_ok else 'not enabled: Winlink channel will fall back to paper)')

    slog = open(SP / 'sim.log', 'w', encoding='utf-8')
    procs.append(subprocess.Popen([sys.executable, '-u', str(REPO / 'simulation' / 'sim_server.py'), str(SIM_PORT), '--data', str(FIX)], stdout=slog, stderr=subprocess.STDOUT, env=env))
    check('simulator server up on 8095', wait_port(SIM_PORT))
    info = call(SIM_PORT, 'GET', '/api/info')
    check('simulator: fixture pack loaded, pseudonymized by default, dataset absent but harmless', info['pack'] and info['pack']['units'] == 6 and info['privacy'] == 'pseudonymized' and not info['ok'], {k: info.get(k) for k in ('privacy', 'packError', 'error')})
    check('simulator: /api/pack serves the pseudonymized pack (no fixture phone)', '000-000-0105' not in json.dumps(call(SIM_PORT, 'GET', '/api/pack')))
    r = call(SIM_PORT, 'POST', '/api/pack', {'path': str(FIX), 'privacy': 'real'}) if False else None
    try:
        call(SIM_PORT, 'POST', '/api/pack', {'path': str(FIX), 'privacy': 'real'})
        check('simulator: real mode without confirm is refused', False)
    except urllib.error.HTTPError as e:
        check('simulator: real mode without confirm is refused', e.code == 400)
    call(SIM_PORT, 'POST', '/api/pack', {'path': str(FIX), 'privacy': 'real', 'confirm': True, 'consent': {'by': 'President Tester', 'date': '2026-10-31', 'recordedBy': 'Pat', 'inRoom': True}})
    check('simulator: real mode with confirm and the recorded consent serves real values', '000-000-0105' in json.dumps(call(SIM_PORT, 'GET', '/api/pack')))
    call(SIM_PORT, 'POST', '/api/pack', {'path': str(FIX), 'privacy': 'pseudonymized'})
    # local roles through the server: saved beside the pack, pack reloaded, pseudonymized
    r = call(SIM_PORT, 'POST', '/api/local-roles', {'roles': lroles[:2]})
    lr = call(SIM_PORT, 'GET', '/api/local-roles')
    pk = call(SIM_PORT, 'GET', '/api/pack')
    erds = [c for c in pk['contacts'] if c['role'] == 'Emergency Response Director']
    check('server: PUT /api/local-roles writes the file beside the pack and reloads (2 roles, pseudonymized, info counts them)', r['ok'] and r['count'] == 2 and pathlib.Path(r['path']) == lrp and lrp.is_file() and lr['ok'] and len(lr['roles']) == 2
          and any(o['id'] == 'U2' for o in lr['orgs']) and 'Emergency Response Director' in lr['suggested'] and len(erds) == 1 and erds[0]['last'] == 'Tester' and erds[0]['first'] != 'Pat' and '000-000-0199' not in json.dumps(pk)
          and call(SIM_PORT, 'GET', '/api/info')['localRoles'] == 2, (r.get('path'), len(erds)))
    call(SIM_PORT, 'POST', '/api/settings', {'site': {'role': 'stake', 'stake': 'S1', 'satellite_units': []}})
    rqs = {r['key']: r for r in call(SIM_PORT, 'GET', '/api/local-roles')['required']}
    check('server: /api/local-roles reports the required roles for the saved site (ERD filled by the local role, pseudonymized name)', rqs['erd']['filled'] and rqs['erd']['who'][0]['who'] != 'Pat Tester' and rqs['erd']['who'][0]['who'].endswith('Tester') and not rqs['specialist']['filled'], rqs['erd']['who'])
    try:
        call(SIM_PORT, 'POST', '/api/local-roles', {'roles': [{'org': 'NOPE', 'role': 'X'}]})
        check('server: an unknown organization id is refused', False)
    except urllib.error.HTTPError as e:
        check('server: an unknown organization id is refused', e.code == 400)
    call(SIM_PORT, 'POST', '/api/local-roles', {'roles': []})
    check('server: clearing the roles removes them from the pack', call(SIM_PORT, 'GET', '/api/info')['localRoles'] == 0 and not [c for c in call(SIM_PORT, 'GET', '/api/pack')['contacts'] if c.get('local')])
    cats = call(SIM_PORT, 'GET', '/api/scenarios')
    check('simulator: catalog marks scenarios that apply here', all(x.get('applies_here') for x in cats['scenarios']))
    probe = call(SIM_PORT, 'GET', f'/api/eoc?url=http://127.0.0.1:{EOC_PORT}')
    check('simulator: EOC probe sees the scratch EOC and its folders', probe['ok'] and probe['status']['eocName'] == 'Alpha Stake EOC' and probe.get('dropDir'), {k: probe.get(k) for k in ('ok', 'receivedDir', 'dropDir')})
    plan = call(SIM_PORT, 'POST', '/api/run/plan', {'scenario': 'copper-creek-dam', 'stakes': ['S1'], 'eoc': {'url': f'http://127.0.0.1:{EOC_PORT}', 'winlink': 'EOC-A@winlink.org'}, 'seed': 5, 'speed': 60})
    check('simulator: run planned for one stake (4 units)', plan['ok'] and plan['counts']['units'] == 4 and plan['run']['clock']['status'] == 'planned', plan.get('counts'))
    # fire one item of each channel by hand
    st = call(SIM_PORT, 'GET', '/api/run')
    note = next(i for i in st['items'] if i['kind'] == 'note')
    r = call(SIM_PORT, 'POST', '/api/run/item', {'id': note['id'], 'action': 'fire'})
    check('fire a note: posted to the EOC notes log', r['item']['status'] == 'fired' and any(n['text'].startswith('SIM: ') for n in call(EOC_PORT, 'GET', '/api/notes')))
    dr = next(i for i in st['items'] if i['inject'] == 'dr-initial')
    r = call(SIM_PORT, 'POST', '/api/run/item', {'id': dr['id'], 'action': 'fire'})     # PACE P at planning time -> phone
    check('fire a DR at P: delivered by phone upload, filed as new', r['item']['result'].get('via') == 'phone' and r['item']['result'].get('new') == 1, r['item']['result'])
    msgs = call(EOC_PORT, 'GET', '/api/messages')
    m = next((json.loads(x['data_json']) for x in msgs if x['type'] == 'dr'), {})
    check('EOC filed the simulated DR with the unit name for the roster', m.get('dr', {}).get('ward') == dr['unit'] and m.get('fields', {}).get('sim_mark', '').startswith('SIMULATED'))
    r = call(SIM_PORT, 'POST', '/api/run/pace', {'level': 'C', 'why': 'test'})
    check('PACE C pushed to the EOC', r['ok'] and call(EOC_PORT, 'GET', '/api/status')['pace'] == 'C')
    call(SIM_PORT, 'POST', '/api/run/eoc')
    dr2 = next(i for i in st['items'] if i['inject'] == 'dr-initial' and i['id'] != dr['id'])
    call(SIM_PORT, 'POST', '/api/run/start')
    r = call(SIM_PORT, 'POST', '/api/run/item', {'id': dr2['id'], 'action': 'fire'})
    via = r['item']['result'].get('via')
    if watcher_ok:
        check('fire a DR at C: written as a Winlink .mime into the watched folder', via == 'winlink' and pathlib.Path(r['item']['result']['file']).is_file(), r['item']['result'])
        check('the .mime is written atomically: no .tmp file left in the Winlink folder', not list(pathlib.Path(r['item']['result']['file']).parent.glob('*.tmp')))
        for _ in range(40):
            if len(call(EOC_PORT, 'GET', '/api/messages')) >= 2:
                break
            time.sleep(0.5)
        msgs = call(EOC_PORT, 'GET', '/api/messages')
        wl = [json.loads(x['data_json']) for x in msgs if json.loads(x['data_json']).get('source') == 'auto']
        check('EOC watcher ingested the simulated Winlink message (source auto, from SIM-)', wl and all(w['from'].startswith('SIM-') for w in wl) and any(w['dr']['ward'] == dr2['unit'] for w in wl), [w.get('from') for w in wl])
    else:
        check('fire a DR at C without a Winlink folder: falls back to a paper card with the body text', via == 'paper' and '[Church-DR|' in r['item'].get('text', ''))
    call(SIM_PORT, 'POST', '/api/run/pause')
    so = next(i for i in st['items'] if i['kind'] == 'form' and i['form'] == 'so')
    r = call(SIM_PORT, 'POST', '/api/run/item', {'id': so['id'], 'action': 'skip'})
    check('skip an item', r['ok'] and next(i for i in call(SIM_PORT, 'GET', '/api/run')['items'] if i['id'] == so['id'])['status'] == 'skipped')
    # drop channel: force one item through the Drop Folder
    import engine as _e
    wcl = next(i for i in st['items'] if i['kind'] == 'form' and i['form'] == 'wcl' and not i.get('after'))
    call(SIM_PORT, 'POST', '/api/run/pace', {'level': 'P', 'why': 'test back to P', 'push': False})
    before = len(call(EOC_PORT, 'GET', '/api/messages'))
    r = call(SIM_PORT, 'POST', '/api/run/item', {'id': wcl['id'], 'action': 'fire'})
    check('fire a WCL at P: phone upload filed', r['item']['result'].get('new') == 1 and len(call(EOC_PORT, 'GET', '/api/messages')) == before + 1, r['item']['result'])
    # the clock: at 60x, 2 wall seconds = 2 drill minutes
    call(SIM_PORT, 'POST', '/api/run/jump', {'minute': 1.5})
    call(SIM_PORT, 'POST', '/api/run/start')
    time.sleep(3)
    s2 = call(SIM_PORT, 'GET', '/api/run')
    fired_auto = [i for i in s2['items'] if i['status'] == 'fired' and i['t'] <= s2['clock']['elapsed_min'] and i['inject'] == 'n-nws']
    check('clock runs at the speed set and fires due items on its own', s2['clock']['status'] == 'running' and s2['clock']['elapsed_min'] >= 3 and fired_auto, s2['clock'])
    call(SIM_PORT, 'POST', '/api/run/stop')
    check('stop: status stopped', call(SIM_PORT, 'GET', '/api/run')['clock']['status'] == 'stopped')
    # work-item injects: a request lands on the EOC's Work Items list, with the unit's names filled in
    st = call(SIM_PORT, 'GET', '/api/run')
    wis = [i for i in st['items'] if i['kind'] == 'work_item' and not i.get('after')]   # the scripted ones; consequence items wait on a need
    wm = next((i for i in wis if i['inject'] == 'wi-mission-office'), None)
    check('plan: the scripted work-item injects (all for this Stake EOC except the area one), the mission-office one bound to the missing-missionaries unit', len(wis) >= 9 and all(i['local'] for i in wis if i['inject'] != 'wi-area-totals') and not next(i for i in wis if i['inject'] == 'wi-area-totals')['local'] and wm and wm['unit'] and wm['unit'] in wm['work']['title'] and '{' not in wm['work']['next'], [(i['inject'], i['unit']) for i in wis])
    before = len(call(EOC_PORT, 'GET', '/api/actions'))
    r = call(SIM_PORT, 'POST', '/api/run/item', {'id': wm['id'], 'action': 'fire'})
    acts = call(EOC_PORT, 'GET', '/api/actions')
    got = next((a for a in acts if a.get('key') == 'sim:' + wm['id']), {})
    check('fire a work item: on the EOC list as HIGH, due 08:50, from the mission office, not auto', r['item']['result'].get('via') == 'work item' and len(acts) == before + 1 and got.get('prio') == 1 and got.get('due') == '08:50' and got.get('from') == 'Mission office' and got.get('auto') is False and got['log'][0]['who'] == 'SIM', got)
    r = call(SIM_PORT, 'POST', '/api/run/item', {'id': wm['id'], 'action': 'fire', 'force': True})
    check('firing it again is a duplicate on the EOC (same key), not a second item', r['item']['result'].get('dup') and len(call(EOC_PORT, 'GET', '/api/actions')) == before + 1)
    # the EOC's own derived items are there too (the fired DRs had injuries / needs per the scenario templates, or not: count only)
    # evidence: no owner yet -> the first auto check suggests x; give the item an owner -> suggests ok
    ev = call(SIM_PORT, 'POST', '/api/run/evidence')
    hw = call(SIM_PORT, 'GET', '/api/run')['hotwash']
    auto = [h for h in hw if h.get('auto')]
    check('evidence gathered for the 15 auto checks', ev.get('ok') and ev.get('checks') == 15 and len(auto) == 15 and all(h.get('evidence') for h in auto), ev)
    h125 = next(h for h in auto if h['t'] == 140)
    check('T+140 (one item per household): no "Alder Street" item on file yet -> suggests x and says so', h125['suggest'] == '✗' and 'only 0 matching' in h125['evidence'], h125['evidence'])
    for k in range(2):
        call(EOC_PORT, 'POST', '/api/actions', {'title': f'Welfare check 415 Alder Street (copy {k})', 'cat': 'other', 'prio': 2, 'who': 'Pat', 'status': 'done', 'decision': 'found', 'key': f'test:dup:{k}'})
    ev = call(SIM_PORT, 'POST', '/api/run/evidence')
    h125 = next(h for h in call(SIM_PORT, 'GET', '/api/run')['hotwash'] if h.get('auto') and h['t'] == 140)
    check('T+140: two items for the same household -> max_count 1 names the duplicates', h125['suggest'] == '✗' and 'duplicates' in h125['evidence'] and '2 matching' in h125['evidence'], h125['evidence'])
    h50 = next(h for h in auto if h['t'] == 50)
    check('T+50 (owner within 10 min): the mission-office item has no owner -> suggests x', h50['suggest'] == '✗' and 'never given an owner' in h50['evidence'], h50['evidence'])
    call(SIM_PORT, 'POST', '/api/run/speed', {'speed': 1})      # evidence minutes = wall minutes x speed: read them at 1x here
    call(EOC_PORT, 'PATCH', f"/api/actions/{got['id']}", {'owner': 'Specialist', 'who': 'Op'})
    call(SIM_PORT, 'POST', '/api/run/evidence')
    h50 = next(h for h in call(SIM_PORT, 'GET', '/api/run')['hotwash'] if h.get('auto') and h['t'] == 50)
    check('after one owner is set: its Owner: log line is read; the DR-derived items are still unowned -> x', h50['suggest'] == '✗' and 'owner Specialist after' in h50['evidence'] and 'never given an owner' in h50['evidence'], h50['evidence'])
    for a in call(EOC_PORT, 'GET', '/api/actions'):
        if a.get('status') != 'done' and not a.get('owner'):
            call(EOC_PORT, 'PATCH', f"/api/actions/{a['id']}", {'owner': 'ERD', 'who': 'Op'})
    call(SIM_PORT, 'POST', '/api/run/evidence')
    hw = call(SIM_PORT, 'GET', '/api/run')['hotwash']
    h50 = next(h for h in hw if h.get('auto') and h['t'] == 50)
    check('every item owned: T+50 suggests ok with each owner and its minutes', h50['suggest'] == '✓' and 'owner ERD after' in h50['evidence'] and 'never' not in h50['evidence'], h50['evidence'])
    h236 = next(h for h in hw if h.get('auto') and h['t'] == 236)
    check('T+236 (no unowned high items): every open high item has an owner now', h236['suggest'] == '✓', h236['evidence'])
    h110 = next(h for h in call(SIM_PORT, 'GET', '/api/run')['hotwash'] if h.get('auto') and h['t'] == 52)
    check('T+52 (warming-centre decision): item not fired yet -> no matching item, suggests x', h110['suggest'] == '✗' and 'only 0' in h110['evidence'], h110['evidence'])
    call(SIM_PORT, 'POST', '/api/run/hotwash', {'n': 0, 'result': 'x', 'note': 'did it'})
    status, txt = call(SIM_PORT, 'GET', '/api/run/export', raw=True)
    check('hot wash export is plain text with the result, the evidence and the log', status == 200 and f'[x] T+{hw[0]["t"]}'.encode() in txt and b'PACE C from' in txt and 'evidence (✓)'.encode('utf-8') in txt)
    runs = list(pathlib.Path(plan['run']['id'] and (FIX.parent / 'simulation' / 'runs')).glob('run-*.json'))
    check('run file saved beside the pack', any(p.name.endswith(plan['run']['id'] + '.json') for p in runs), [p.name for p in runs][-3:])
    # the scenario's PACE timeline drives the EOC header: a fresh plan (timeline intact: P, C at T+80), jump to T+79, run at 60x past T+80
    call(EOC_PORT, 'PUT', '/api/incident', dict(call(EOC_PORT, 'GET', '/api/incident'), pace='E'))
    plan = call(SIM_PORT, 'POST', '/api/run/plan', {'scenario': 'copper-creek-dam', 'stakes': ['S1'], 'eoc': {'url': f'http://127.0.0.1:{EOC_PORT}', 'winlink': 'EOC-A@winlink.org'}, 'seed': 5, 'speed': 60})
    call(SIM_PORT, 'POST', '/api/run/jump', {'minute': 79})
    call(SIM_PORT, 'POST', '/api/run/start')
    time.sleep(0.6)
    p_start = call(EOC_PORT, 'GET', '/api/status')['pace']
    time.sleep(2.5)
    s3 = call(SIM_PORT, 'GET', '/api/run')
    p_c = call(EOC_PORT, 'GET', '/api/status')['pace']
    lg = [l['text'] for l in s3['log'] if l['text'].startswith('PACE ')]
    check('timeline: P pushed to the EOC at the start, C pushed when T+80 comes (EOC header follows the scenario)', p_start == 'P' and p_c == 'C' and s3['clock']['pace'] == 'C' and s3['clock'].get('pace_pushed') == 'C'
          and any('PACE P in force (at the start)' in x for x in lg) and any('PACE C in force (scenario timeline)' in x for x in lg) and sum('PACE C in force' in x for x in lg) == 1, (p_start, p_c, lg))
    call(SIM_PORT, 'POST', '/api/run/stop')
    check('clock segments recorded (start, jump, stop)', len(call(SIM_PORT, 'GET', '/api/run')['clock'].get('segments') or []) >= 3)
    for _ in range(40):                                   # let the watcher file the reports that run fired, so the counts below are stable
        if not any(received.glob('*.mime')):
            break
        time.sleep(0.5)

    # ── 5. several EOCs: what each simulator plays, routing, drill bar, Ready, scheduled start, roll-ups ──
    def start_eoc(tag, port, level, name):
        dd = SP / ('eoc_' + tag)
        if dd.exists():
            shutil.rmtree(dd)
        (dd / 'eoc').mkdir(parents=True)
        for f in ('eoc_server.py', 'EOC_Message_Center.html', 'EOC_Wall_Display.html', 'EOC_Phone.html'):
            shutil.copy2(REPO / 'eoc' / f, dd / 'eoc' / f)
        shutil.copytree(REPO / 'templates', dd / 'templates')
        lg = open(SP / f'eoc_{tag}.log', 'w', encoding='utf-8')
        procs.append(subprocess.Popen([sys.executable, '-u', 'eoc_server.py', str(port)], cwd=str(dd / 'eoc'), stdout=lg, stderr=subprocess.STDOUT,
                                      env=dict(os.environ, PYTHONIOENCODING='utf-8', LOCALAPPDATA=str(SP / ('appdata_' + tag)), EMCOMM_DOCUMENTS=str(SP / ('documents_' + tag)))))
        for _ in range(80):
            try:
                call(port, 'GET', '/api/status'); break
            except Exception:
                time.sleep(0.25)
        i2 = call(port, 'GET', '/api/incident')
        i2.update({'eocName': name, 'eocLevel': level, 'name': 'DRILL copper-creek test ' + tag, 'pace': 'P'})
        call(port, 'PUT', '/api/incident', i2)
    SAT, AREA = 8086, 8087
    start_eoc('sat', SAT, 'satellite', 'Alpha West Satellite EOC')
    start_eoc('area', AREA, 'area', 'Alpha Council EOC')
    check('satellite (8086) and area (8087) EOCs up with their levels', call(SAT, 'GET', '/api/status')['eocLevel'] == 'satellite' and call(AREA, 'GET', '/api/status')['eocLevel'] == 'area')
    st0 = call(EOC_PORT, 'GET', '/api/status')
    check('EOC status carries the drill state (none pushed yet, or the earlier run)', 'drill' in st0)
    # 5a. this simulator plays the Stake EOC; Riverbottom Ward (U3) is covered by a Satellite EOC
    plan = call(SIM_PORT, 'POST', '/api/run/plan', {'scenario': 'copper-creek-dam', 'seed': 5, 'speed': 60, 'eoc': {'url': f'http://127.0.0.1:{EOC_PORT}'},
                                                     'site': {'role': 'stake', 'stake': 'S1', 'satellite_units': ['U3']}})
    run = plan['run']; its = run['items']
    u3 = [i for i in its if i['kind'] == 'form' and i['unit_id'] == 'U3']; u1 = [i for i in its if i['kind'] == 'form' and i['unit_id'] == 'U1']
    check('stake role: scope = the stake, the satellite\'s ward\'s reports are elsewhere, the others local', plan['counts']['units'] == 4 and u3 and all(i['to'] == 'satellite' and i['status'] == 'elsewhere' for i in u3) and all(i['to'] == 'stake' and i['local'] for i in u1), plan['counts'])
    check('stake role: notes and cards everywhere (local), work items here, no roll-ups', all(i['local'] for i in its if i['kind'] in ('note', 'voice', 'prompt')) and all(i['to'] == 'stake' and i['local'] for i in its if i['kind'] == 'work_item' and i['inject'] != 'wi-area-totals') and not any(i['kind'] == 'rollup' for i in its) and run['site']['label'] == 'Alpha Stake EOC', run['site'])
    wa = next(i for i in its if i['inject'] == 'wi-area-totals')
    check('stake role: the area-only work item is elsewhere', wa['to'] == 'area' and wa['status'] == 'elsewhere')
    r = call(SIM_PORT, 'POST', '/api/run/item', {'id': u3[0]['id'], 'action': 'fire'})
    check('firing an elsewhere item does nothing', r['item']['status'] == 'elsewhere' and not r['item']['result'])
    d = call(EOC_PORT, 'GET', '/api/drill')
    check('the Stake EOC shows the drill the simulator pushed: role, label, scenario, planned, seed, controller', d.get('active') and d['role'] == 'stake' and d['site_label'] == 'Alpha Stake EOC' and d['scenario'] == run['scenario']['name'] and d['status'] == 'planned' and d['seed'] == 5 and d['controller'].endswith(':8095') and d['ready'] == [], d)
    call(EOC_PORT, 'POST', '/api/drill/ready', {'who': 'Travis'})
    call(EOC_PORT, 'POST', '/api/drill/ready', {'who': 'Op Two'})
    call(EOC_PORT, 'POST', '/api/drill/ready', {'who': 'Op Two', 'ready': False})
    b = call(SIM_PORT, 'POST', '/api/run/board')['board']
    check('Ready check-ins reach the simulator\'s board (this EOC first, marked self)', b and b[0]['self'] and b[0]['ready'] == ['Travis'] and b[0]['name'] == 'Alpha Stake EOC' and b[0]['role'] == 'stake', b[0])
    check('the Stake EOC\'s /api/status carries ready names and the drill label', call(EOC_PORT, 'GET', '/api/status')['drill']['ready'] == ['Travis'])
    at = (time.localtime(time.time() + 3)); hhmmss = f'{at.tm_hour:02d}:{at.tm_min:02d}:{at.tm_sec:02d}'
    r = call(SIM_PORT, 'POST', '/api/run/schedule', {'at': hhmmss})
    s1 = call(SIM_PORT, 'GET', '/api/run')
    check('scheduled start: clock scheduled with the wall time, pushed to the EOC', r['ok'] and s1['clock']['status'] == 'scheduled' and s1['clock']['start_at_wall'] and call(EOC_PORT, 'GET', '/api/drill')['status'] == 'scheduled', s1['clock'])
    for _ in range(30):                                  # the coordination loop checks every second; give a busy laptop time
        time.sleep(0.5)
        s2 = call(SIM_PORT, 'GET', '/api/run'); d2 = call(EOC_PORT, 'GET', '/api/drill')
        if s2['clock']['status'] == 'running' and d2['status'] == 'running':
            break
    check('the clock started by itself at the scheduled time; the EOC drill bar says running', s2['clock']['status'] == 'running' and d2['status'] == 'running' and d2['elapsed_min'] >= 0, (s2['clock']['status'], d2['status']))
    check('Ready names survive re-pushes of the same run', d2['ready'] == ['Travis'])
    call(SIM_PORT, 'POST', '/api/run/stop')
    check('Message Center and wall carry a drill bar element', b'id="drill-bar"' in call(EOC_PORT, 'GET', '/', raw=True)[1] and b'id="drillbar"' in call(EOC_PORT, 'GET', '/wall', raw=True)[1])
    status, m = call(EOC_PORT, 'GET', '/m', raw=True)
    check('phone page lists work items and the drill card', status == 200 and b'id="work-card"' in m and b'drill-card' in m and b'/api/actions' in m)
    # 5b. this simulator plays the Satellite EOC covering U3
    plan = call(SIM_PORT, 'POST', '/api/run/plan', {'scenario': 'copper-creek-dam', 'seed': 5, 'speed': 60, 'eoc': {'url': f'http://127.0.0.1:{SAT}'},
                                                     'site': {'role': 'satellite', 'stake': 'S1', 'units': ['U3']}})
    run = plan['run']; its = run['items']
    forms = [i for i in its if i['kind'] == 'form']
    check('satellite role: scope = its ward only, its reports local, work items elsewhere (the Stake EOC\'s), parent named', plan['counts']['units'] == 1 and forms and all(i['unit_id'] == 'U3' and i['to'] == 'satellite' and i['local'] for i in forms)
          and all(i['status'] == 'elsewhere' for i in its if i['kind'] == 'work_item') and run['site']['parent'] == 'Alpha Stake EOC' and 'Satellite EOC of Alpha Stake' in run['site']['label'], run['site'])
    dr3 = next(i for i in forms if i['inject'] == 'dr-initial')
    before = len(call(SAT, 'GET', '/api/messages'))
    r = call(SIM_PORT, 'POST', '/api/run/item', {'id': dr3['id'], 'action': 'fire'})
    check('satellite role: the report is filed at the Satellite EOC, not the Stake EOC', r['item']['result'].get('new') == 1 and len(call(SAT, 'GET', '/api/messages')) == before + 1)
    d3 = call(SAT, 'GET', '/api/drill')
    check('the Satellite EOC\'s drill bar: role satellite, reports to the Stake EOC, the ward named', d3['role'] == 'satellite' and d3['parent'] == 'Alpha Stake EOC' and d3['units'] == ['Riverbottom Ward'], d3)
    check('the Stake EOC still shows the earlier (stopped) run of its own simulator', call(EOC_PORT, 'GET', '/api/drill')['role'] == 'stake')
    # 5c. this simulator plays the Council / Area EOC over council C1 (stakes S1, S2); S1 has its own laptop, S2 is simulated here
    drop_area = SP / 'drop_area'
    drop_area.mkdir(parents=True, exist_ok=True)
    call(AREA, 'PUT', '/api/drop/config', {'watch_path': str(drop_area), 'enabled': True})   # never the real Documents folder
    plan = call(SIM_PORT, 'POST', '/api/run/plan', {'scenario': 'copper-creek-dam', 'seed': 5, 'speed': 60, 'eoc': {'url': f'http://127.0.0.1:{AREA}'},
                                                     'site': {'role': 'area', 'councils': ['C1'], 'played_stakes': ['S1']}})
    run = plan['run']; its = run['items']
    s1f = [i for i in its if i['kind'] == 'form' and i['stake'] == 'Alpha Stake']; s2f = [i for i in its if i['kind'] == 'form' and i['stake'] == 'Bravo Stake']
    rolls = [i for i in its if i['kind'] == 'rollup']
    check('area role: all 6 units in scope; the played stake\'s reports are elsewhere; the simulated stake\'s travel in roll-ups', plan['counts']['units'] == 6 and s1f and all(i['status'] == 'elsewhere' for i in s1f) and s2f and all(i['to'] == 'area' and i.get('rollup') and i['status'] == 'pending' for i in s2f), plan['counts'])
    check('area role: two roll-up items for the simulated stake, the area work item local, stake work items elsewhere', [i['stake'] for i in rolls] == ['Bravo Stake', 'Bravo Stake'] and [i['t'] for i in rolls] == [62, 188]
          and next(i for i in its if i['inject'] == 'wi-area-totals')['local'] and all(i['status'] == 'elsewhere' for i in its if i['kind'] == 'work_item' and i['inject'] != 'wi-area-totals'), [(i['inject'], i['t']) for i in rolls])
    check('area role: label names the council', run['site']['label'] == 'Council / Area EOC: Alpha Coordinating Council' and call(AREA, 'GET', '/api/drill')['site_label'] == run['site']['label'])
    call(SIM_PORT, 'POST', '/api/run/jump', {'minute': 70})
    due_parts = [i for i in s2f if i['t'] <= 70]
    before = len(call(AREA, 'GET', '/api/messages'))
    r = call(SIM_PORT, 'POST', '/api/run/item', {'id': rolls[0]['id'], 'action': 'fire'})
    rr = r['item']['result']
    check('roll-up #1 fired: one church_eoc_rollup file written into the Area EOC\'s Drop Folder', rr.get('ok') and rr.get('via') == 'rollup drop' and rr.get('records') == len(due_parts) and rr.get('file', '').startswith(str(drop_area)) and pathlib.Path(rr['file']).name.startswith('church_eoc_rollup_Bravo_Stake_SIM_rollup-1_'), rr)
    for _ in range(60):
        if len(call(AREA, 'GET', '/api/messages')) >= before + len(due_parts):
            break
        time.sleep(0.5)
    msgs_a = call(AREA, 'GET', '/api/messages')
    recs = [json.loads(x['data_json']) for x in msgs_a]
    check('the Area EOC\'s Drop Folder watcher ingested it: the due reports are on file, the file moved to Ingested', len(msgs_a) == before + len(due_parts) and not pathlib.Path(rr['file']).exists() and (drop_area / 'Ingested' / pathlib.Path(rr['file']).name).exists(), (len(msgs_a), before, len(due_parts)))
    check('merged records carry origin and via = the simulated Stake EOC, summary fields only', recs and all(x.get('via') == 'Bravo Stake EOC (simulated)' and x.get('origin') == 'Bravo Stake EOC (simulated)' and 'fields' not in x for x in recs), recs[0] if recs else None)
    s3 = call(SIM_PORT, 'GET', '/api/run')
    check('the bundled reports are marked fired via rollup drop; any later ones stay pending for roll-up #2', due_parts and all(i['status'] == 'fired' and i['result']['via'] == 'rollup drop' for i in s3['items'] if i.get('rollup') and i['t'] <= 70) and all(i['status'] == 'pending' for i in s3['items'] if i.get('rollup') and i['t'] > 70), [(i['t'], i['status']) for i in s3['items'] if i.get('rollup')])
    ro = call(AREA, 'GET', '/api/roster')
    check('the Area roster gained the simulated stake\'s units', {x['name'] for x in ro} >= {i['unit'] for i in due_parts}, [x['name'] for x in ro])
    notes_a = call(AREA, 'GET', '/api/notes')
    check('the roll-up logged a SIM note at the Area EOC, prefixed with the sending EOC', any('SIM: SITREP #1 roll-up from Bravo Stake' in n['text'] and n['text'].startswith('[Bravo Stake EOC (simulated)]') for n in notes_a), [n['text'][:80] for n in notes_a][:3])
    acts_a = call(AREA, 'GET', '/api/actions')
    ups = [a for a in acts_a if a.get('from') == 'Bravo Stake EOC (simulated)']
    check('work items waiting on the line above arrived open at the Area EOC naming the simulated stake (if any report asked)', all(a['status'] == 'open' for a in ups), len(ups))
    call(SIM_PORT, 'POST', '/api/run/start'); time.sleep(2.5); call(SIM_PORT, 'POST', '/api/run/pause')
    s4 = call(SIM_PORT, 'GET', '/api/run')
    check('the running clock never fires elsewhere items or bundled reports on their own', all(i['status'] == 'elsewhere' for i in s4['items'] if i['local'] is False) and not any(i['status'] == 'fired' and i['result'] and not str(i['result'].get('via', '')).startswith('rollup') for i in s4['items'] if i.get('rollup')))
    call(SIM_PORT, 'POST', '/api/run/stop')
    # fallback: Drop Folder off at the Area -> a fresh area plan's roll-up merges directly and says so
    call(AREA, 'PUT', '/api/drop/config', {'enabled': False})
    plan = call(SIM_PORT, 'POST', '/api/run/plan', {'scenario': 'copper-creek-dam', 'seed': 5, 'speed': 60, 'eoc': {'url': f'http://127.0.0.1:{AREA}'},
                                                     'site': {'role': 'area', 'councils': ['C1'], 'played_stakes': ['S1']}})
    roll1 = next(i for i in plan['run']['items'] if i['kind'] == 'rollup')
    call(SIM_PORT, 'POST', '/api/run/jump', {'minute': 70})
    r = call(SIM_PORT, 'POST', '/api/run/item', {'id': roll1['id'], 'action': 'fire'})
    rr2 = r['item']['result']
    check('roll-up without a reachable Drop Folder: merged directly (all duplicates of the first run), the Run tab says so', rr2.get('via') == 'rollup merge' and 'not reachable' in rr2.get('note', '') and rr2.get('records') == len(due_parts) and rr2.get('dup') == len(due_parts) and not list(drop_area.glob('*.json')), rr2)
    call(AREA, 'PUT', '/api/drop/config', {'enabled': True})
    call(SIM_PORT, 'POST', '/api/run/stop')

    # ── 6. evaluation: the needs ledger, consequences, replies from the line above, scoreboard, after-action report ──
    NEED = 8088
    start_eoc('needs', NEED, 'stake', 'Alpha Stake EOC')
    call(NEED, 'PUT', '/api/drop/config', {'watch_path': str(SP / 'drop_needs'), 'enabled': False})
    plan = call(SIM_PORT, 'POST', '/api/run/plan', {'scenario': 'copper-creek-dam', 'seed': 5, 'speed': 60, 'eoc': {'url': f'http://127.0.0.1:{NEED}'}, 'site': {'role': 'stake', 'stake': 'S1'}})
    run = plan['run']; its = run['items']
    waiting = [i for i in its if i['status'] == 'waiting']
    replies = [i for i in its if i['kind'] == 'reply']
    check('plan: needs registered for the scripted work items and the cards with a need block; consequence items wait; reply items are local', plan['counts'].get('needs', 0) >= 8 and len(waiting) >= 20 and all(i.get('after') for i in waiting)
          and replies and all(i['local'] for i in replies) and any(i['inject'] == 'n-approvals' and i['status'] == 'pending' for i in replies), (plan['counts'].get('needs'), len(waiting), len(replies)))
    nd = {n['id']: n for n in run['needs']}
    check('need rules: scenario defaults per category, decision on the shelter question, the member-notification card matched by title', nd['need:wi-sp-shelter']['rule']['decision'] is True and nd['need:wi-sp-shelter']['rule']['done'] == 30 and nd['need:wi-county-headcount']['rule']['owner'] == 15
          and any(n['match'].get('title_contains') == 'notify' and n['cat'] == 'life' for n in run['needs']), nd['need:wi-sp-shelter']['rule'])
    plan2 = call(SIM_PORT, 'POST', '/api/run/plan', {'scenario': 'copper-creek-dam', 'seed': 5, 'speed': 60, 'eoc': {'url': f'http://127.0.0.1:{NEED}'}, 'site': {'role': 'stake', 'stake': 'S1', 'played_parent': True}})
    check('people play the line above: the simulated replies are elsewhere', all(i['local'] is False and i['status'] == 'elsewhere' for i in plan2['run']['items'] if i['kind'] == 'reply'))
    plan = call(SIM_PORT, 'POST', '/api/run/plan', {'scenario': 'copper-creek-dam', 'seed': 5, 'speed': 60, 'eoc': {'url': f'http://127.0.0.1:{NEED}'}, 'site': {'role': 'stake', 'stake': 'S1'}})
    its = plan['run']['items']
    dr = next(i for i in its if i['inject'] == 'dr-initial' and i['severity'] == 3)
    call(SIM_PORT, 'POST', '/api/run/jump', {'minute': 5}); call(SIM_PORT, 'POST', '/api/run/pace', {'level': 'P', 'why': 'test'})
    r = call(SIM_PORT, 'POST', '/api/run/item', {'id': dr['id'], 'action': 'fire'})
    st = call(SIM_PORT, 'POST', '/api/run/needs')
    arisen = [n for n in st['needs'] if n.get('arose_t') is not None]
    check('a band-3 Disaster Report at P makes the EOC derive work items and the ledger register a need per item (injuries, help, building, …) at T+5', r['item']['result'].get('via') == 'phone' and len(arisen) >= 4
          and all(n['arose_t'] == 5 for n in arisen) and any(n['id'].endswith('#life') for n in arisen) and any(n['id'].endswith('#nbr') for n in arisen) and not any(n['kind'] == 'report' for n in arisen), [n['id'] for n in arisen])
    call(SIM_PORT, 'POST', '/api/run/jump', {'minute': 20})
    wi = next(i for i in its if i['inject'] == 'wi-sp-shelter'); call(SIM_PORT, 'POST', '/api/run/item', {'id': wi['id'], 'action': 'fire'})
    paper = next(i for i in its if i['inject'] == 'dr-paper'); rp = call(SIM_PORT, 'POST', '/api/run/item', {'id': paper['id'], 'action': 'fire'})
    st = call(SIM_PORT, 'POST', '/api/run/needs')
    nd = {n['id']: n for n in st['needs']}
    life = next(n for n in st['needs'] if n['id'].endswith('#life') and n['arose_t'] == 5)
    rep_need = next((n for n in st['needs'] if n['kind'] == 'report'), None)
    check('T+20: the injuries need is OVERDUE (no owner after 15 min, limit 10); the shelter question is open; the paper report registered a typed-in need', life['state'] == 'overdue' and 'no owner' in life['evidence']
          and nd['need:wi-sp-shelter']['state'] == 'open' and rep_need and rep_need['state'] == 'open' and rp['item']['result'].get('via') == 'paper', (life['evidence'], rep_need and rep_need['state']))
    s = call(SIM_PORT, 'GET', '/api/run')
    trig = [i for i in s['items'] if i.get('triggered')]
    check('consequence: the overdue injuries need triggered the bishop\'s repeat call for that ward, due now', any(i['inject'] == 'v-bishop-injured' and i['unit_id'] == dr['unit_id'] and i['status'] == 'pending' and i['t'] == 20 for i in trig), [(i['id'], i['status'], i['t']) for i in trig])
    acts = call(NEED, 'GET', '/api/actions')
    la = next(a for a in acts if a['id'] == life['action_id']); sh = next(a for a in acts if a['key'] == 'sim:' + wi['id'])
    call(NEED, 'PATCH', f"/api/actions/{la['id']}", {'owner': 'Pat', 'who': 'Pat', 'status': 'progress'})
    call(NEED, 'PATCH', f"/api/actions/{sh['id']}", {'owner': 'ERD', 'who': 'Pat', 'status': 'done', 'decision': 'North building opens; the ERD runs it'})
    call(SIM_PORT, 'POST', '/api/run/jump', {'minute': 26})
    st = call(SIM_PORT, 'POST', '/api/run/needs'); nd = {n['id']: n for n in st['needs']}
    check('the shelter question answered with a recorded decision is MET; the injuries item owned late stays open until done (owner Pat after 15 min)', nd['need:wi-sp-shelter']['state'] == 'met' and 'decision recorded' in nd['need:wi-sp-shelter']['evidence']
          and nd[life['id']]['state'] == 'open' and 'owner Pat after 15 min' in nd[life['id']]['evidence'], (nd['need:wi-sp-shelter']['evidence'], nd[life['id']]['evidence']))
    s = call(SIM_PORT, 'GET', '/api/run')
    check('resolution: the shelter decision triggered the ERD\'s note 8 drill minutes later', any(i['inject'] == 'n-shelter-decided' and i['status'] == 'pending' and i['t'] == 34 for i in s['items']), [(i['id'], i['status'], i['t']) for i in s['items'] if i.get('triggered')])
    # the operator types in the paper report with one wrong number
    pay = paper['payload']
    rec = {'id': 'typed-needs-1', 'type': 'dr', 'ts': int(time.time() * 1000), 'source': 'manual', 'dupKey': 'manual:needs-1',
           'dr': {'stake': pay['inc_stake'], 'ward': pay['inc_ward'], 'mem_inj': str(int(pay['mem_injuries']) + 1), 'mem_dead': pay['mem_deaths'], 'homes_dmg': pay['mem_damaged'],
                  'homes_dest': pay['mem_destroyed'], 'miss_safe': pay['miss_safe'], 'need_local': pay['need_local'], 'need_neighbor': pay['need_neighbor'], 'need_hq': pay['need_hq'],
                  'vol_count': pay.get('vol_count', '0'), 'vol_hrs': pay.get('vol_hours', '0'), 'inc_type': pay['inc_type'], 'exercise': 'YES'}}
    call(NEED, 'POST', '/api/messages', rec)
    st = call(SIM_PORT, 'POST', '/api/run/needs'); rn = next(n for n in st['needs'] if n['kind'] == 'report')
    check('typed-in report: the need is MET within 25 min and the accuracy check names the wrong field (injured typed +1)', rn['state'] == 'met' and rn.get('accuracy') and rn['accuracy']['matched'] == rn['accuracy']['total'] - 1 and 'injured' in rn['evidence'], rn['evidence'])
    ct = engine.compare_truth({'mem_inj': '12', 'miss_safe': 'NO', 'need_hq': 'YES'}, {'mem_inj': '12', 'miss_safe': 'No', 'need_hq': 'no'})
    check('compare_truth: numbers and yes/no compared case-blind, one mismatch named', ct['matched'] == 2 and ct['total'] == 3 and len(ct['wrong']) == 1 and 'headquarters' in ct['wrong'][0].lower(), ct)
    # supply: UP is the EOC's part; the welfare line answers 25-30 drill minutes later and closes it DONE with the decision
    so = next((i for i in its if i['inject'] == 'so-care'), None) or next(i for i in its if i['inject'] == 'so-water')
    call(SIM_PORT, 'POST', '/api/run/item', {'id': so['id'], 'action': 'fire'})
    sup = next(a for a in call(NEED, 'GET', '/api/actions') if a['cat'] == 'supply' and a['status'] == 'open')
    call(NEED, 'PATCH', f"/api/actions/{sup['id']}", {'owner': 'ERD', 'who': 'Pat', 'status': 'up'})
    st = call(SIM_PORT, 'POST', '/api/run/needs'); sn = next(n for n in st['needs'] if n['cat'] == 'supply' and n.get('arose_t') is not None)
    rep_items = [i for i in call(SIM_PORT, 'GET', '/api/run')['items'] if i['kind'] == 'reply' and i['inject'] == 'r-' + so['inject'] and i['unit_id'] == so['unit_id']]
    check('Supply Order set UP: the approval need is MET and the welfare line\'s reply is scheduled 25-30 drill minutes later', sn['state'] == 'met' and rep_items and rep_items[0]['status'] == 'pending' and 51 <= rep_items[0]['t'] <= 56, (sn['evidence'], [(i['status'], i['t']) for i in rep_items]))
    rr = call(SIM_PORT, 'POST', '/api/run/item', {'id': rep_items[0]['id'], 'action': 'fire', 'force': True})['item']['result']
    sup2 = next(a for a in call(NEED, 'GET', '/api/actions') if a['id'] == sup['id'])
    check('the reply closes the UP item DONE with the decision written in and a log line from the welfare line', rr.get('via') == 'reply' and rr.get('closed') == 1 and sup2['status'] == 'done' and 'Approved by the WSRM' in sup2.get('decision', '')
          and any(l['text'].startswith('Reply from Welfare line') for l in sup2['log']) and isinstance(sup2.get('replied'), dict), (rr, sup2['status'], sup2.get('decision', '')[:40]))
    # waive / reopen; the scoreboard; the report
    nbr = next(n for n in st['needs'] if n['id'].endswith('#nbr'))
    w = call(SIM_PORT, 'POST', '/api/run/need', {'id': nbr['id'], 'action': 'waive'})
    sc1 = call(SIM_PORT, 'POST', '/api/run/needs')['score']
    call(SIM_PORT, 'POST', '/api/run/need', {'id': nbr['id'], 'action': 'reopen'})
    sc2 = call(SIM_PORT, 'POST', '/api/run/needs')['score']
    check('waive drops a need from the score; reopen puts it back', w['need']['state'] == 'waived' and sc1['total'] == sc2['total'] - 1 and sc2['open'] + sc2['overdue'] == sc1['open'] + sc1['overdue'] + 1, (sc1['total'], sc2['total']))
    s = call(SIM_PORT, 'GET', '/api/run'); sc = s['score']
    cks = {c['id']: c for c in sc['checks']}
    check('done checks need_met: the meetings, member-notification and rumour checks are pending (None) until their cards fire, with the reason',
          all(k in cks and cks[k].get('ok') is None and 'not fired yet' in cks[k]['why'] for k in ('meetings', 'notify', 'rumour')), {k: cks.get(k) for k in ('meetings', 'notify', 'rumour')})
    _scored = sc['met'] + sc['late'] + sc['overdue'] + sc['missed']
    check('scoreboard: counts by state, pct = (met + half late) / scored (an open need inside its time is not scored yet), label, median minutes to an owner, high needs without an owner, done checks (SITREPs pending before their deadline)',
          sc['total'] == sc['met'] + sc['late'] + sc['open'] + sc['overdue'] + sc['missed'] and sc['met'] >= 3 and sc['scored'] == _scored and sc['pct'] == round(100 * (sc['met'] + 0.5 * sc['late']) / _scored) and sc['label'] in ('strong', 'steady', 'struggling', 'overwhelmed')
          and sc['median_owner_min'] is not None and sc['high_unowned'] >= 1 and {c['id']: c['ok'] for c in sc['checks']}['sitrep1'] is None and {c['id']: c['ok'] for c in sc['checks']}['high'] is False, {k: sc[k] for k in ('total', 'met', 'late', 'open', 'overdue', 'pct', 'label', 'high_unowned')})
    rep = call(SIM_PORT, 'GET', '/api/run/report')
    txt = call(SIM_PORT, 'GET', '/api/run/report.txt', raw=True)[1].decode('utf-8')
    html = call(SIM_PORT, 'GET', '/report', raw=True)[1].decode('utf-8')
    red = call(SIM_PORT, 'GET', '/api/run/report.txt?redact=units', raw=True)[1].decode('utf-8')
    _unames = [u['name'] for u in pack['units']]
    check('report as text, units redacted: no unit name of the pack, numbered units instead, marked redacted', not any(n in red for n in _unames) and 'Unit ' in red and '(units redacted)' in red.splitlines()[0],
          [n for n in _unames if n in red][:3])
    check('after-action report: JSON with the do-better list by role and what went well; text with DONE WHEN and the needs; printable HTML', rep['better'] and rep['better_by_role'] and rep['well'] and all(b['role'] and b['coach'] for b in rep['better'])
          and 'DONE WHEN' in txt and 'NEEDS LEDGER' in txt.upper() and html.startswith('<!DOCTYPE html>') and '<h1>After-action report' in html and 'Do better' in html, (len(rep['better']), len(rep['well']), len(txt), len(html)))
    call(SIM_PORT, 'POST', '/api/run/stop')
    s = call(SIM_PORT, 'GET', '/api/run')
    rd = pathlib.Path(call(SIM_PORT, 'GET', '/api/info')['runsDir'])
    check('stop finalizes: open needs are MISSED, the log carries the final score, the report files sit beside the run file', any('Final score' in e['text'] for e in s['log']) and all(n['state'] != 'open' for n in s['needs'] if n.get('arose_t') is not None)
          and (rd / f"run-{s['id']}-report.html").exists() and (rd / f"run-{s['id']}-report.txt").exists(), (str(rd), [e['text'][:40] for e in s['log'][-3:]]))
    fin = s['score']
    call(SIM_PORT, 'GET', '/results', raw=True); call(SIM_PORT, 'GET', '/api/run/report')      # the room's phones and the hot wash refresh
    aft = call(SIM_PORT, 'GET', '/api/run')['score']
    check('the final score stays final: /results and the report after the stop leave MISSED needs missed (nothing back to open or overdue)',
          fin['missed'] > 0 and all(aft[k] == fin[k] for k in ('met', 'late', 'open', 'overdue', 'missed', 'pct')), ({k: fin[k] for k in ('open', 'overdue', 'missed')}, {k: aft[k] for k in ('open', 'overdue', 'missed')}))
    # ── 7. open items closed 2026-10-31: the stake's emergency roles in texts and role cards; consent for real contacts ──
    scl7 = engine.load_scenario('copper-creek-dam')
    run7 = engine.plan(p2, scl7, {'seed': 5, 'today': '2026-10-31', 'eoc': {'name': 'Alpha Stake EOC'}, 'stakes': ['S1']})
    pr = next(i for i in run7['items'] if i['inject'] == 'p-decide-c')
    sh = next(i for i in run7['items'] if i['inject'] == 'n-shelter-decided')
    sp_card = next(r for r in run7['roles'] if r['id'] == 'stake_president')['cards'][0]['text']
    check('placeholders: {erd} names the local-roles ERD in a prompt, a consequence note and a role card; {specialist} falls back to the role name when nobody holds it',
          'Pat Tester' in sh['text'] and sh['text'].startswith('Pat Tester (Emergency Response Director)') and 'Pat Tester' in pr['text'] and 'Welfare and Self-Reliance Specialist' in pr['text']
          and '{' not in sp_card and '{erd}' not in json.dumps(run7['roles']), (pr['text'][:90], sp_card[:90]))
    # consent: real contacts need who / date / recorded by / in-the-room; it is stamped in the pack, the run and the report; pseudonymized drops it
    try:
        call(SIM_PORT, 'POST', '/api/pack', {'path': str(FIX), 'privacy': 'real', 'confirm': True}); bad = None
    except urllib.error.HTTPError as e:
        bad = e.code
    try:
        call(SIM_PORT, 'POST', '/api/pack', {'path': str(FIX), 'privacy': 'real', 'confirm': True, 'consent': {'by': 'President Tester', 'date': '2026-10-31', 'recordedBy': 'Pat', 'inRoom': False}}); bad2 = None
    except urllib.error.HTTPError as e:
        bad2 = e.code
    check('real contacts refused without the recorded consent (400), and without the in-the-room promise', bad == 400 and bad2 == 400, (bad, bad2))
    r7 = call(SIM_PORT, 'POST', '/api/pack', {'path': str(FIX), 'privacy': 'real', 'confirm': True, 'consent': {'by': 'President Tester', 'role': 'Stake President', 'date': '2026-10-31', 'recordedBy': 'Pat', 'inRoom': True}})
    inf7 = call(SIM_PORT, 'GET', '/api/info')
    cs = inf7.get('consent') or {}
    check('real contacts loaded with the consent: info carries who, role, date, recorded by and when; the served pack is real', r7['ok'] and inf7['privacy'] == 'real' and cs.get('by') == 'President Tester' and cs.get('role') == 'Stake President'
          and cs.get('date') == '2026-10-31' and cs.get('recordedBy') == 'Pat' and cs.get('recordedAt') and cs.get('packPath'), cs)
    plan7 = call(SIM_PORT, 'POST', '/api/run/plan', {'scenario': 'copper-creek-dam', 'seed': 5, 'speed': 60, 'eoc': {'url': f'http://127.0.0.1:{NEED}'}, 'site': {'role': 'stake', 'stake': 'S1'}})
    rep7 = call(SIM_PORT, 'GET', '/api/run/report.txt', raw=True)[1].decode('utf-8')
    hw7 = call(SIM_PORT, 'GET', '/api/run/export.txt', raw=True)[1].decode('utf-8') if False else ''
    check('the run and the after-action report are stamped with the consent', plan7['run']['pack']['privacy'] == 'real' and (plan7['run']['pack'].get('consent') or {}).get('by') == 'President Tester'
          and 'privacy: real (consent: President Tester, Stake President, 2026-10-31; recorded by Pat)' in rep7, rep7.splitlines()[1] if rep7 else '')
    sf = pathlib.Path(inf7['settingsFile'])
    st7 = json.loads(sf.read_text(encoding='utf-8')) if sf.is_file() else {}
    call(SIM_PORT, 'POST', '/api/pack', {'path': str(FIX), 'privacy': 'pseudonymized'})
    inf8 = call(SIM_PORT, 'GET', '/api/info')
    st8 = json.loads(sf.read_text(encoding='utf-8')) if sf.is_file() else {}
    check('the consent is remembered in the settings while real contacts are loaded and dropped when the pack is loaded pseudonymized again',
          (st7.get('consent') or {}).get('by') == 'President Tester' and inf8['privacy'] == 'pseudonymized' and inf8.get('consent') is None and 'consent' not in st8, (sorted(st7), sorted(st8)))
    # a participant package holds no real contacts: asking for real mode with consent still gives pseudonymized
    _pk = pathlib.Path(tempfile.mkdtemp(prefix='emcomm-marked-pack-'))
    (_pk / 'simulation').mkdir()
    (_pk / 'orgpack.json').write_text(pathlib.Path(FIX).read_text(encoding='utf-8'), encoding='utf-8')
    (_pk / 'simulation' / orgpack.PACKAGE_MARKER).write_text('{}', encoding='utf-8')
    r9 = call(SIM_PORT, 'POST', '/api/pack', {'path': str(_pk), 'privacy': 'real', 'confirm': True, 'consent': {'by': 'President Tester', 'date': '2026-10-31', 'recordedBy': 'Pat', 'inRoom': True}})
    check('a participant package stays pseudonymized when real mode is asked: no real label, no consent stamped',
          r9['ok'] and r9['info']['privacy'] == 'pseudonymized' and r9['info'].get('consent') is None and r9['info']['pack']['privacy'] == 'pseudonymized', r9.get('info', {}).get('privacy'))
    call(SIM_PORT, 'POST', '/api/pack', {'path': str(FIX), 'privacy': 'pseudonymized'})
    shutil.rmtree(_pk, ignore_errors=True)
    # ── 8. the trainer's session: rehearse, reset, GO, live, results; saved every 30 s and resumable ──
    plan = call(SIM_PORT, 'POST', '/api/run/plan', {'scenario': 'copper-creek-dam', 'seed': 5, 'speed': 60, 'eoc': {'url': f'http://127.0.0.1:{NEED}'}, 'site': {'role': 'stake', 'stake': 'S1'}})
    ss = call(SIM_PORT, 'GET', '/api/session')
    check('session: status lists the pack, the EOC, the planned run and the results address', ss['ok'] and ss['pack'] and ss['eoc']['ok'] and ss['run'] and ss['run']['status'] == 'planned'
          and ss['results_url'].endswith(':8095/results') and not ss['run']['session'], {k: ss.get(k) for k in ('pack', 'eoc')})
    reh = plan['run']['id']
    call(SIM_PORT, 'POST', '/api/run/start'); time.sleep(1.5)                         # a rehearsal: a few drill minutes of traffic
    r = call(SIM_PORT, 'POST', '/api/session/reset', {'event': 'DRILL: session test (THIS IS AN EXERCISE)'})
    st = call(NEED, 'GET', '/api/status'); d = call(NEED, 'GET', '/api/drill')
    old = json.loads((pathlib.Path(call(SIM_PORT, 'GET', '/api/info')['runsDir']) / f'run-{reh}.json').read_text(encoding='utf-8'))
    check('reset: the rehearsal is stopped and kept as a rehearsal; a fresh drill event on the EOC; the same run planned again at T+0, marked a session',
          r['ok'] and r['run'] != reh and r['event'] and st['activeEventName'] == 'DRILL: session test (THIS IS AN EXERCISE)' and old.get('rehearsal') and old['clock']['status'] == 'stopped'
          and call(SIM_PORT, 'GET', '/api/run')['clock']['status'] == 'planned', (r, st.get('activeEventName')))
    check('reset: every EOC screen is told the drill is ready (planned, session) and PACE is the scenario\'s first level',
          d.get('status') == 'planned' and d.get('session') is True and st.get('pace') == 'P', {k: d.get(k) for k in ('status', 'session')})
    status_mc = call(NEED, 'GET', '/', raw=True)[1]; status_wall = call(NEED, 'GET', '/wall', raw=True)[1]; status_m = call(NEED, 'GET', '/m', raw=True)[1]
    check('the Message Center, wall and phone page say "ready: waiting for the trainer\'s GO"; the wall explains a DRILL event with no run',
          b"waiting for the trainer" in status_mc and b"waiting for the trainer" in status_wall and b"waiting for the trainer" in status_m and b'No simulator run has started' in status_wall)
    sim_page = call(SIM_PORT, 'GET', '/', raw=True)[1]
    check('the simulator page opens on the Session tab with the five steps and GO', b'id="pane-session"' in sim_page and b'id="ss-go"' in sim_page and b'data-pane="session">Session' in sim_page)
    g0 = int(time.time() * 1000)
    g = call(SIM_PORT, 'POST', '/api/session/go', {})
    inc = call(NEED, 'GET', '/api/incident')
    check('GO: the run starts and the EOC drill event clock starts now (SITREP times count from GO)', g['ok'] and g['status'] == 'running' and int(inc.get('startTs') or 0) >= g0 - 2000, (g, inc.get('startTs'), g0))
    time.sleep(2)
    ss = call(SIM_PORT, 'GET', '/api/session')
    check('live: the Session tab sees the clock, the phase, PACE and what comes next', ss['run']['status'] == 'running' and ss['run']['minute'] > 0 and ss['run']['phase'] and ss['run']['next'], ss['run'] and {k: ss['run'].get(k) for k in ('minute', 'phase', 'pace')})
    sb = ss['run']['score']
    check('live: right after GO, needs still inside their time give no percentage and no label (no "0 % overwhelmed" before anyone could act)',
          sb['met'] + sb['late'] + sb['overdue'] + sb['missed'] > 0 or (sb['pct'] is None and sb['label'] == ''), sb)
    status, page = call(SIM_PORT, 'GET', '/results', raw=True)
    check('results for the room: a read-only report page that refreshes while the drill runs', status == 200 and b'After-action report' in page and b'http-equiv="refresh"' in page)
    status, deb = call(SIM_PORT, 'GET', '/debrief', raw=True)
    dt = deb.decode('utf-8')
    check('debrief for the room: slides (cover, what you faced, the score, what went well, the next drill), the disclaimer, no external resources',
          status == 200 and all(s in dt for s in ('Drill debrief', 'What you faced', 'The score', 'What went well', 'The next drill', 'not an official Church product'))
          and dt.count('<section') >= 5 and not re.search(r'(src|href)=["\']https?://', dt), (status, dt.count('<section')))
    rep_why = call(SIM_PORT, 'GET', '/api/run/report')
    check('the report carries why it matters (the inject lessons), the phases and the scenario summary', isinstance(rep_why.get('why'), list) and rep_why.get('phases') and rep_why['run']['scenario'].get('summary'),
          (len(rep_why.get('why') or []), len(rep_why.get('phases') or [])))
    # a closed window or a restart: the run file says running; another plan replaces the runner without stopping it
    cur = call(SIM_PORT, 'GET', '/api/run')['id']
    time.sleep(1)
    call(SIM_PORT, 'POST', '/api/run/pause')
    rf = pathlib.Path(call(SIM_PORT, 'GET', '/api/info')['runsDir']) / f'run-{cur}.json'
    call(SIM_PORT, 'POST', '/api/run/plan', {'scenario': 'copper-creek-dam', 'seed': 5, 'speed': 60, 'eoc': {'url': f'http://127.0.0.1:{NEED}'}, 'site': {'role': 'stake', 'stake': 'S1'}})
    crash = json.loads(rf.read_text(encoding='utf-8')); crash['clock'].update(status='running', started_wall=time.time() - 3600)   # as a crash leaves it
    rf.write_text(json.dumps(crash), encoding='utf-8')
    lst = call(SIM_PORT, 'GET', '/api/sessions')['sessions']
    mine = next((x for x in lst if x['id'] == cur), {})
    check('saved sessions: the interrupted session is listed as resumable, the rehearsal as a rehearsal', mine.get('resumable') and mine.get('session') and any(x['id'] == reh and x['rehearsal'] for x in lst), mine)
    rs = call(SIM_PORT, 'POST', '/api/session/resume', {'id': cur})
    run_now = call(SIM_PORT, 'GET', '/api/run')
    check('resume: the run comes back paused at the minute it was saved; GO continues it from there', rs['ok'] and rs['status'] == 'paused' and rs['minute'] > 0 and run_now['id'] == cur
          and abs(run_now['clock']['elapsed_min'] - rs['minute']) < 0.2, rs)
    call(SIM_PORT, 'POST', '/api/session/go', {}); time.sleep(1)
    check('GO after resume continues the clock (no restart at T+0)', call(SIM_PORT, 'GET', '/api/run')['clock']['elapsed_min'] > rs['minute'])
    call(SIM_PORT, 'POST', '/api/run/stop')
    bad = call(SIM_PORT, 'POST', '/api/session/resume', {'id': '../../etc'})
    check('resume refuses a run id that is not a saved run', bad.get('ok') is False)
    print('\nRESULT:', 'ALL PASS' if all(res) else 'FAILURES', f'({sum(res)}/{len(res)})')
finally:
    if keep:
        print('servers left running (stop them yourself):', [p.pid for p in procs], '· scratch in', SP)
    else:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()
        shutil.rmtree(FIX.parent / 'simulation', ignore_errors=True)   # runs + salt written beside the fixture
sys.exit(0 if res and all(res) else 1)
