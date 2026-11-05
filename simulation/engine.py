#!/usr/bin/env python3
"""Simulation engine (Python standard library only).

``plan(pack, scenario, options)`` turns a scenario (geography + timeline, no organization
names) and an organization pack (the real names, loaded at run time) into a *run*: every
simulated report, note, net card, paper card and role prompt with its minute, its unit
and the exact Worker-form field set the EOC (Emergency Operations Center) accepts.

``Runner`` plays a run against a live EOC server: it keeps the drill clock, fires items
when due over the channel the PACE level in force allows, posts scenario notes, applies
PACE changes, and records the EOC's answer per item. The run file is saved after every
change so a drill can be inspected or replayed afterwards.

Channels (docs/SIMULATOR_DESIGN.md section 2.3):
  phone    POST /api/upload                        (Primary / Alternate: the phone app)
  drop     a Worker .txt in the EOC Drop Folder    (an emailed file)
  winlink  a Winlink .mime in the watched Received folder (Contingency: radio)
  paper    a card on the simulator screen; the operator types it in (Emergency: runner)
  voice    a net card the HAM role player reads; the operator types what is said

Evaluation (docs/SIMULATOR_DESIGN.md section 2.7): every inject that asks the EOC for something
registers a **need** in the run's ledger (a report to be typed in, a work item to own and close,
a decision to record, a request to send up the line). ``Runner._needs_tick`` reads the EOC
(work items, messages, incident) every few seconds and marks each need open / met / late /
overdue / missed with the drill minutes it took. Injects with ``after`` fire when a need reaches
a state (the truck arrives when the delivery point was given; the bishop calls again when
nobody owned the item); ``reply`` injects play the line above and close UP items with a
decision. ``score()`` turns the ledger into the scoreboard the Run tab and the EOC screens show;
``report()`` is the after-action report.
"""
import copy
import datetime as _dt
import email.message
import email.utils
import json
import math
import os
import random
import re
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCENARIOS_DIR = HERE / 'scenarios'
RUN_KIND = 'church_emcomm_run'
PACE_LEVELS = ('P', 'A', 'C', 'E')
FORM_FILENAMES = {'dr': 'Church_Disaster_Report_Worker.txt', 'so': 'Church_Supply_Order_Worker.txt',
                  'wcl': 'Church_Work_Crew_Log_Worker.txt'}
FORM_TITLES = {'dr': 'Church Disaster Report', 'so': 'Church Supply Order', 'wcl': 'Church Work Crew Log'}
CHANNEL_BY_PACE = {'P': 'phone', 'A': 'phone', 'C': 'winlink', 'E': 'paper'}
SIM_MARK = 'SIMULATED (EMCOMM drill)'
NEED_STATES = ('open', 'met', 'late', 'overdue', 'missed', 'waived')
# What the EOC is expected to do with a work item of each category, in drill minutes, unless the
# scenario's `needs.defaults` or the inject's `need` block says otherwise. `owner`: minutes to an
# owner; `done`: minutes to DONE (or UP for the line above); `decision`: a decision text is required.
NEED_DEFAULTS = {
    'missionaries': {'owner': 10, 'done': 90, 'decision': False, 'done_states': ['done']},
    'life':         {'owner': 10, 'done': 120, 'decision': False, 'done_states': ['done']},
    'upward':       {'owner': 15, 'done': 60, 'decision': False, 'done_states': ['up', 'done']},
    'supply':       {'owner': 20, 'done': 150, 'decision': True, 'done_states': ['up', 'done']},
    'facilities':   {'owner': 30, 'done': 120, 'decision': False, 'done_states': ['done']},
    'assist':       {'owner': 30, 'done': 120, 'decision': False, 'done_states': ['done']},
    'roster':       {'owner': 30, 'done': 60, 'decision': False, 'done_states': ['done']},
    'other':        {'owner': 30, 'done': 120, 'decision': False, 'done_states': ['done']},
    'report':       {'typed': 25},                # a paper or voice report: minutes until it is on file
}
# Who answers for a need of each category at the hot wash (the after-action report groups by role)
NEED_ROLE = {'missionaries': 'EOC operator and Stake President', 'life': 'EOC operator', 'upward': 'EOC operator',
             'supply': 'Emergency Response Director and the welfare line', 'facilities': 'Emergency Response Director',
             'assist': 'EOC operator', 'roster': 'EOC operator', 'report': 'EOC operator and HAM operator', 'other': 'EOC operator'}
# One coaching line per category and failure, for the after-action report's "do better" list
NEED_COACH = {
    ('missionaries', 'owner'): 'A missionaries alert is owned the minute it appears: say a name out loud and write it on the item.',
    ('missionaries', 'done'): 'The item closes when the mission office has the names and the search has a lead; log each step.',
    ('life', 'owner'): 'Injuries and deaths get an owner at once; the owner confirms names and care with the bishop.',
    ('life', 'done'): 'Close the item when care is confirmed and it is reported up; do not leave it open all day.',
    ('upward', 'owner'): 'A headquarters-assistance request is a worklist item, not just a line in a report: own it.',
    ('upward', 'done'): 'Set the item UP before the SITREP goes; it travels with the roll-up and lands on the line above.',
    ('supply', 'owner'): 'Every Supply Order gets an owner who checks it with the ERD before it goes up.',
    ('supply', 'done'): 'Send the Supply Order up (UP) early; when the approval comes back, set DONE with the decision text.',
    ('supply', 'decision'): 'Write the approval, the truck ETA and the delivery point into the decision field.',
    ('facilities', 'owner'): 'A building or shelter question goes to the ERD by name.',
    ('facilities', 'done'): 'A leadership question is answered as a recorded decision, with the time and who decided.',
    ('facilities', 'decision'): 'Record the decision on the item so the SITREP carries it.',
    ('assist', 'owner'): 'Match the unit asking for help with one that has crews free; name the matcher on the item.',
    ('assist', 'done'): 'Close the item when the crew is on its way and the bishop knows.',
    ('report', 'typed'): 'A paper or voice report is typed into the Message Center within a few minutes; it counts for the roster only once it is on file.',
    ('report', 'accuracy'): 'Read numbers back over the net before typing them; one wrong digit changes the SITREP totals.',
    ('other', 'owner'): 'Every work item gets an owner.', ('other', 'done'): 'Every work item is moved or closed.',
}


# ── geography ────────────────────────────────────────────────────────────────
def haversine_km(lat1, lon1, lat2, lon2) -> float:
    p = math.pi / 180
    a = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(a))


def in_ring(ring, x, y) -> bool:
    inside, j = False, len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def maidenhead(lat, lon) -> str:
    lon += 180
    lat += 90
    A = 'ABCDEFGHIJKLMNOPQRSTUVWX'
    return (A[int(lon // 20)] + A[int(lat // 10)] + str(int((lon % 20) // 2)) + str(int(lat % 10))
            + A[int(((lon % 2) * 60) // 5)].lower() + A[int(((lat % 1) * 60) // 2.5)].lower())


def in_feature(unit: dict, feature: dict) -> bool:
    if unit.get('lat') is None or not feature:
        return False
    if feature.get('type') == 'polygon':
        return in_ring(feature['coords'], unit['lon'], unit['lat'])
    if feature.get('type') == 'circle':
        return haversine_km(unit['lat'], unit['lon'], feature['center'][0], feature['center'][1]) <= feature['radius_km']
    return False


def bbox_overlaps(a, b) -> bool:
    return bool(a and b) and not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


# ── scenarios ────────────────────────────────────────────────────────────────
def pack_scenarios_dir(pack_dir) -> Path:
    """A community's own scenarios live beside its directory export, never in the repository:
    <export root>/simulation/scenarios/ (catalog.json + <id>.json), next to the local bindings."""
    return Path(pack_dir) / 'simulation' / 'scenarios'


def catalog(scenarios_dir=SCENARIOS_DIR, extra_dirs=()) -> dict:
    """The built-in catalog (the invented example community's scenarios), plus the catalog of every extra
    folder that has one (a pack's own scenarios). A pack scenario with the same id replaces the built-in one."""
    cat = json.loads((Path(scenarios_dir) / 'catalog.json').read_text(encoding='utf-8-sig'))
    for d in extra_dirs or ():
        p = Path(d) / 'catalog.json'
        if not p.is_file():
            continue
        extra = json.loads(p.read_text(encoding='utf-8-sig'))
        ids = {s['id'] for s in extra.get('scenarios', [])}
        cat['scenarios'] = [s for s in cat['scenarios'] if s['id'] not in ids] + [dict(s, source='pack') for s in extra.get('scenarios', [])]
        if extra.get('area'):
            cat['pack_area'] = extra['area']
    return cat


def load_scenario(sid: str, scenarios_dir=SCENARIOS_DIR, local_path=None, extra_dirs=()) -> dict:
    """The scenario JSON (a pack's own folder first, then the built-in one), with a local binding file
    (outside the repository) merged over it."""
    if not re.fullmatch(r'[A-Za-z0-9._-]+', sid or ''):
        raise FileNotFoundError(f'no scenario {sid!r}')
    p = next((Path(d) / f'{sid}.json' for d in list(extra_dirs or ()) if (Path(d) / f'{sid}.json').is_file()), Path(scenarios_dir) / f'{sid}.json')
    if not p.is_file():
        raise FileNotFoundError(f'no scenario {sid!r} in {scenarios_dir}')
    sc = json.loads(p.read_text(encoding='utf-8-sig'))
    if local_path and Path(local_path).is_file():
        sc = merge_local(sc, json.loads(Path(local_path).read_text(encoding='utf-8-sig')))
        sc['local_binding'] = str(local_path)
    return sc


def merge_local(scenario: dict, local: dict) -> dict:
    """Local binding: extra injects (may name units), severity overrides by unit name,
    replaced templates / roles / hot-wash lines, extra geo features."""
    sc = copy.deepcopy(scenario)
    sc.setdefault('geo', {}).setdefault('features', {}).update(local.get('geo', {}).get('features', {}))
    sc['templates'] = {**sc.get('templates', {}), **local.get('templates', {})}
    have = {i['id']: n for n, i in enumerate(sc.get('injects', []))}
    for inj in local.get('injects', []):
        if inj.get('id') in have:
            sc['injects'][have[inj['id']]] = inj
        else:
            sc.setdefault('injects', []).append(inj)
    for key in ('roles', 'hotwash', 'phases'):
        if local.get(key):
            sc[key] = local[key]
    sc['severity_override'] = {**sc.get('severity_override', {}), **local.get('severity_override', {})}
    sc['agencies'] = {**sc.get('agencies', {}), **local.get('agencies', {})}
    sc['local_notes'] = local.get('notes', {})
    return sc


def severity_of(unit: dict, scenario: dict) -> int:
    """Band 0 (unaffected) to 3 (worst) for one unit."""
    rule = scenario.get('severity', {})
    feats = scenario.get('geo', {}).get('features', {})
    ov = scenario.get('severity_override', {})
    if unit['name'] in ov:
        return int(ov[unit['name']])
    level = 0
    if unit.get('lat') is None:
        level = int(rule.get('default_no_location', 1))
    elif rule.get('rule') == 'distance_km':
        src = scenario['geo'][rule.get('from', 'epicenter')]
        d = haversine_km(unit['lat'], unit['lon'], src[0], src[1])
        for band in rule.get('bands', []):
            if 'max' not in band or d <= band['max']:
                level = int(band['level'])
                break
    elif rule.get('rule') == 'feature':
        level = int(rule.get('default', 0))
        for band in rule.get('bands', []):
            if in_feature(unit, feats.get(band['in'])):
                level = int(band['level'])
                break
    elif rule.get('rule') == 'constant':
        level = int(rule.get('level', 1))
    for b in rule.get('boost', []):
        if 'in' in b and in_feature(unit, feats.get(b['in'])):
            level += int(b.get('add', 1))
        if 'flag' in b and b['flag'] in unit.get('flags', []):
            level = max(level, int(b.get('min', 0))) + int(b.get('add', 0))
    return max(0, min(3, level))


def pace_at(pace: list, t: float) -> str:
    level = 'P'
    for step in sorted(pace, key=lambda s: s['t']):
        if step['t'] <= t:
            level = step['level']
    return level


# ── planning ─────────────────────────────────────────────────────────────────
class _Ctx:
    """Everything the template filler needs for one unit."""

    def __init__(self, idx, unit, run, rng, today):
        self.idx, self.unit, self.run, self.rng = idx, unit, run, rng
        stake = idx.stakes.get(unit['stake'], {})
        head = idx.head(unit)
        sp = idx.stake_president(unit['stake'])
        erd, spec = idx.erd(unit['stake'], unit), idx.specialist(unit['stake'])
        others = [c for c in idx.leaders(unit) if c is not head and not c.get('local')]
        chief = others[0] if others else head
        self.crew = [c for c in others if c is not chief]
        sc = idx.buildings.get(stake.get('center_building', ''), {})
        self.values = {
            'unit': unit['name'], 'unit_type': unit['type'], 'city': unit.get('city') or stake.get('city', ''),
            'building': (unit.get('address') or 'meetinghouse').split(',')[0], 'address': unit.get('address', ''),
            'building_name': unit.get('building_name') or (unit.get('address') or 'the meetinghouse').split(',')[0],
            'state': unit.get('state') or stake.get('state', ''), 'zip': unit.get('zip', ''),
            'stake': stake.get('name', unit.get('stake_name', '')), 'stake_president': sp.get('name', ''),
            'stake_center': (sc.get('address') or stake.get('address', '')).split(',')[0], 'stake_center_city': sc.get('city', stake.get('city', '')),
            'stake_center_zip': sc.get('zip', stake.get('zip', '')),
            'stake_center_name': sc.get('name') or stake.get('center_name') or (sc.get('address') or 'the stake center').split(',')[0],
            'bishop': head.get('name', ''), 'bishop_role': head.get('role', ''), 'bishop_phone': head.get('mobile') or head.get('phone', ''),
            'bishop_email': head.get('email', ''), 'crew_chief': chief.get('name', ''), 'crew_chief_phone': chief.get('mobile') or chief.get('phone', ''),
            'unit_call': unit_call(unit), 'today': today, 'tomorrow': (_dt.date.fromisoformat(today) + _dt.timedelta(days=1)).isoformat(),
            'eoc_call': run['eoc'].get('call') or 'the EOC station', 'eoc_winlink': run['eoc'].get('winlink') or 'the EOC Winlink address',
            'eoc_email': run['eoc'].get('email') or 'the EOC drop address', 'eoc': run['eoc'].get('name') or 'the EOC',
            'severity': str(unit['severity']),
            'erd': erd.get('name') or 'the Emergency Response Director', 'erd_phone': erd.get('mobile') or erd.get('phone', ''),
            'specialist': spec.get('name') or 'the Welfare and Self-Reliance Specialist (emergency communications)', 'specialist_phone': spec.get('mobile') or spec.get('phone', ''),
        }
        self.values.update(agency_values(run.get('agencies') or {}, self.values['city']))

    def fill(self, s: str) -> str:
        return re.sub(r'\{([a-z_]+)\}', lambda m: str(self.values.get(m.group(1), m.group(0))), s)


def agency_values(agencies: dict, city: str = '') -> dict:
    """Placeholders for partner agencies that do not run this system (a city EOC): {k}, {k}_call, {k}_contact, {k}_place.
    The scenario names them generically; the local binding gives the real agency, its contact and its Winlink call sign."""
    out = {'city_eoc': f'{city} City EOC'.strip() if city else 'the city EOC', 'city_eoc_call': 'CITYEOC',
           'city_eoc_contact': "the city's emergency manager", 'city_eoc_place': f'the {city} fire station' if city else 'the city fire station'}
    for k, a in (agencies or {}).items():
        if isinstance(a, dict):
            out[k] = a.get('name') or out.get(k, k)
            for f in ('call', 'contact', 'place'):
                if a.get(f):
                    out[f'{k}_{f}'] = a[f]
    return out


def unit_call(unit: dict) -> str:
    """A tactical Winlink address for the unit's simulated HAM station: never a real call sign."""
    slug = re.sub(r'[^A-Z0-9]', '', unit['name'].upper())[:6] or 'UNIT'
    return f'SIM-{slug}'


def _band_value(spec, band: int):
    """Per-severity dict: the entry for this band, else the nearest lower band, else the lowest given."""
    if not isinstance(spec, dict):
        return spec
    for b in range(band, -1, -1):
        if str(b) in spec:
            return spec[str(b)]
    keys = sorted(spec.keys(), key=lambda k: int(k) if k.isdigit() else 99)
    return spec[keys[0]] if keys else None


def resolve(spec, ctx: _Ctx):
    """One template value: literal, {"range": {band: [min,max]}}, {"pick": {band: [..]}}, {"yes": {band: p}}."""
    band = ctx.unit['severity']
    if isinstance(spec, str):
        return ctx.fill(spec)
    if isinstance(spec, (int, float)):
        return str(spec)
    if isinstance(spec, dict):
        if 'range' in spec:
            r = _band_value(spec['range'], band)
            return str(ctx.rng.randint(int(r[0]), int(r[1]))) if r else ''
        if 'pick' in spec:
            opts = _band_value(spec['pick'], band) or ['']
            return ctx.fill(ctx.rng.choice(opts))
        if 'yes' in spec:
            p = _band_value(spec['yes'], band)
            return 'YES' if p is not None and ctx.rng.random() < float(p) else 'NO'
    return ''


def build_form(form: str, template: dict, ctx: _Ctx) -> dict:
    """The Worker-form field set for one simulated report (the same keys the phone app sends)."""
    u, d = ctx.unit, {}
    for k, spec in template.items():
        if k in ('items', 'crew'):
            continue
        d[k] = resolve(spec, ctx)
    if form == 'dr':
        d.setdefault('inc_stake', ctx.values['stake'])
        d.setdefault('inc_ward', u['name'])
    elif form == 'so':
        d.setdefault('req_stake', ctx.values['stake'])
        items = template.get('items', {})
        if 'range' in items:
            for code, r in (_band_value(items['range'], u['severity']) or {}).items():
                n = ctx.rng.randint(int(r[0]), int(r[1]))
                if n > 0:
                    d[code] = str(n)
    elif form == 'wcl':
        d.setdefault('chief_stake', ctx.values['stake'])
        d.setdefault('chief_ward', u['name'])
        crew = template.get('crew', {})
        n = _band_value(crew.get('count', {}), u['severity'])
        n = ctx.rng.randint(int(n[0]), int(n[1])) if n else 0
        hrs = _band_value(crew.get('hrs', {}), u['severity']) or [2, 6]
        wo = _band_value(crew.get('wo', {}).get('pick', {}), u['severity']) or ['Welfare checks']
        people = list(ctx.crew)
        ctx.rng.shuffle(people)
        for i in range(1, min(n, 20) + 1):
            c = people[i - 1] if i - 1 < len(people) else {}
            d[f'crew_name{i}'] = c.get('name') or f'Crew member {i}'
            d[f'crew_stake{i}'] = ctx.values['stake']
            d[f'crew_ward{i}'] = u['name']
            d[f'crew_hrs{i}'] = str(ctx.rng.randint(int(hrs[0]), int(hrs[1])))
            d[f'crew_wo{i}'] = ctx.fill(ctx.rng.choice(wo))
            d[f'crew_addr{i}'] = ctx.values['city']
    if u.get('lat') is not None:
        d['stn_lat_d'] = f"{u['lat']:.6f}"
        d['stn_lon_d'] = f"{u['lon']:.6f}"
        d['stn_grid_d'] = maidenhead(u['lat'], u['lon'])
    d['exercise'] = 'YES'                  # THIS IS AN EXERCISE, like a person ticking the box on the form
    d['sim_run'] = ctx.run['id']           # makes every run's payload unique to the EOC's duplicate check
    d['sim_mark'] = SIM_MARK
    return d


def _select(units: list, where: dict, rng, scenario: dict, tags: dict = None) -> list:
    """The units an inject reaches: every filter first (severity, flags, feature, unit names, and `tag_not`: not
    the units an earlier inject tagged), then `sample` from what is left, so a sample never picks a unit that a
    later filter would drop."""
    feats = scenario.get('geo', {}).get('features', {})
    skip = set((tags or {}).get(where['tag_not'], [])) if where.get('tag_not') else set()
    out = []
    for u in units:
        if u['id'] in skip:
            continue
        if 'severity' in where and u['severity'] != int(where['severity']):
            continue
        if 'severity_min' in where and u['severity'] < int(where['severity_min']):
            continue
        if 'severity_max' in where and u['severity'] > int(where['severity_max']):
            continue
        if 'flags_any' in where and not set(where['flags_any']) & set(u.get('flags', [])):
            continue
        if 'flags_none' in where and set(where['flags_none']) & set(u.get('flags', [])):
            continue
        if 'in' in where and not in_feature(u, feats.get(where['in'])):
            continue
        if 'unit' in where and u['name'] != where['unit']:
            continue
        if 'units' in where and u['name'] not in where['units']:
            continue
        out.append(u)
    if 'sample' in where and out:
        s = where['sample']
        n = int(round(len(out) * s)) if isinstance(s, float) and s <= 1 else int(s)
        n = max(1 if s else 0, min(n, len(out)))
        out = rng.sample(out, n)
    return out


def _minute(t, rng) -> float:
    if isinstance(t, dict):
        return round(rng.uniform(float(t.get('from', 0)), float(t.get('to', 0))), 1)
    return float(t)


ROLES = ('stake', 'satellite', 'area')
# Where an inject goes when its scenario entry says nothing: reports follow their unit; notes and
# cards go to every EOC in the drill (each simulator posts them to its own EOC); work items land at
# the Stake EOC; roll-ups exist only at a Council / Area EOC.
DEFAULT_TO = {'form': 'unit', 'note': 'all', 'voice': 'all', 'prompt': 'all', 'paper': 'all', 'work_item': 'stake', 'rollup': 'area', 'ics': 'stake'}
ICS_FORMS = {'ics213': 'ICS 213 General Message', 'ics213rr': 'ICS 213RR Resource Request'}


def resolve_site(idx: '_Index', site: dict) -> dict:
    """What this simulator plays, with names filled in from the pack. `site` comes from the page:
    {role: stake|satellite|area, stake, units (satellite), satellite_units (stake: handed to a
    satellite), councils (area), played_stakes (area: stakes with their own EOC laptop), eoc}."""
    site = dict(site or {})
    role = site.get('role') if site.get('role') in ROLES else 'stake'
    out = {'role': role, 'eoc': dict(site.get('eoc') or {}), 'stake': '', 'stake_name': '', 'units': [], 'unit_names': [],
           'satellite_units': [], 'councils': [], 'council_names': [], 'stakes': [], 'played_stakes': [], 'label': '', 'parent': '',
           'played_parent': bool(site.get('played_parent'))}   # people play the EOC above this one (its replies are theirs to send)
    if role in ('stake', 'satellite'):
        sid = site.get('stake') or ''
        st = idx.stakes.get(sid, {})
        out['stake'], out['stake_name'] = sid, st.get('name', sid)
        out['stakes'] = [sid] if sid else []
        if role == 'stake':
            out['satellite_units'] = [u for u in (site.get('satellite_units') or []) if u in idx.units]
            out['label'] = f"{out['stake_name']} EOC" if sid else 'Stake EOC'
            out['parent'] = site.get('parent') or ''
        else:
            out['units'] = [u for u in (site.get('units') or []) if u in idx.units]
            out['unit_names'] = [idx.units[u]['name'] for u in out['units']]
            out['label'] = f"Satellite EOC of {out['stake_name']} ({len(out['units'])} units)" if sid else 'Satellite EOC'
            out['parent'] = f"{out['stake_name']} EOC" if sid else 'Stake EOC'
    else:
        cids = [c for c in (site.get('councils') or []) if c in idx.councils]
        out['councils'] = cids
        out['council_names'] = [idx.councils[c]['name'] for c in cids]
        out['stakes'] = [s for c in cids for s in idx.councils[c].get('stakes', []) if s in idx.stakes]
        out['played_stakes'] = [s for s in (site.get('played_stakes') or []) if s in out['stakes']]
        out['label'] = 'Council / Area EOC: ' + (', '.join(out['council_names']) or 'no council chosen')
    return out


def suggest_satellite_units(pack: dict, scenario: dict, stake_id: str) -> list:
    """Unit ids the scenario suggests for a Satellite EOC of this stake (its `eocs.satellite.where`)."""
    from orgpack import Index
    where = ((scenario.get('eocs') or {}).get('satellite') or {}).get('where')
    if not where:
        return []
    idx = Index(pack)
    units = [dict(u, severity=severity_of(u, scenario)) for u in idx.units.values() if u.get('stake') == stake_id]
    return [u['id'] for u in _select(units, dict(where, sample=None) if 'sample' in where else where, random.Random(1), scenario)]


def plan(pack: dict, scenario: dict, options: dict = None) -> dict:
    """Expand a scenario over the pack's units into a run (nothing is sent)."""
    from orgpack import Index
    options = options or {}
    # the mistakes that would otherwise surface only mid-drill (a KeyError when the PACE step fires) or silently
    # (a second inject with the same id overwrites the first one's units and needs): refuse the plan now.
    # simulation/scenario_check.py reports these and every other scenario mistake in one list.
    bad_pace = [p.get('level') for p in scenario.get('pace', []) if p.get('level') not in PACE_LEVELS]
    if bad_pace:
        raise ValueError(f"scenario {scenario.get('id')!r}: unknown PACE level(s) {bad_pace} (use P, A, C or E)")
    seen, dups = set(), set()
    for inj in scenario.get('injects', []):
        (dups if inj.get('id') in seen else seen).add(inj.get('id'))
    if dups:
        raise ValueError(f"scenario {scenario.get('id')!r}: duplicate inject id(s) {sorted(map(str, dups))}")
    idx = Index(pack)
    rng = random.Random(options.get('seed') or 1)
    today = options.get('today') or _dt.date.today().isoformat()
    eoc = dict(options.get('eoc') or {})
    # scope: explicit unit ids, else all units of the chosen stakes, else every unit in the pack
    unit_ids = options.get('units')
    if not unit_ids:
        stakes = options.get('stakes') or [s['id'] for s in pack['stakes']]
        unit_ids = [u for sid in stakes for u in idx.stakes.get(sid, {}).get('units', [])]
    excl = set(options.get('exclude') or [])
    units = []
    for uid in unit_ids:
        u = idx.units.get(uid)
        if not u or uid in excl:
            continue
        u = dict(u)
        u['severity'] = severity_of(u, scenario)
        units.append(u)
    site = resolve_site(idx, options.get('site') or {})
    if options.get('site'):
        # the role decides the scope: a stake's units, a satellite's units, or every unit of the councils' stakes
        if site['role'] == 'satellite':
            keep = set(site['units'])
        else:
            keep = {u['id'] for u in idx.units.values() if u.get('stake') in site['stakes']}
        units = [u for u in units if u['id'] in keep]
        if not eoc.get('url') and site['eoc'].get('url'):
            eoc = dict(site['eoc'])
    run = {'kind': RUN_KIND, 'v': 1, 'id': options.get('id') or _dt.datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:4],
           'created': _dt.datetime.now().isoformat(timespec='seconds'), 'today': today,
           'scenario': {'id': scenario['id'], 'name': scenario['name'], 'hazard': scenario.get('hazard', ''),
                        'local_binding': scenario.get('local_binding', ''), 'summary': scenario.get('summary', '')},
           'pack': {'source': pack.get('source', ''), 'privacy': pack.get('privacy', 'real'), 'consent': pack.get('consent') or None},
           'eoc': eoc, 'seed': options.get('seed') or 1, 'site': site, 'board': [],
           'scope': {'units': [{'id': u['id'], 'name': u['name'], 'type': u['type'], 'stake': u['stake'], 'stake_name': u.get('stake_name', ''),
                                'severity': u['severity'], 'lat': u.get('lat'), 'lon': u.get('lon'), 'flags': u.get('flags', [])} for u in units],
                     'stakes': sorted({u['stake'] for u in units})},
           'pace': copy.deepcopy(scenario.get('pace', [{'t': 0, 'level': 'P'}])),
           'phases': copy.deepcopy(scenario.get('phases', [])),
           'roles': copy.deepcopy(scenario.get('roles', [])), 'hotwash': [dict(h, result='', note='') for h in scenario.get('hotwash', [])],
           'clock': {'speed': float(options.get('speed') or scenario.get('clock', {}).get('default_speed', 1)),
                     'duration_min': scenario.get('clock', {}).get('duration_min', 240), 't0_label': scenario.get('clock', {}).get('t0', ''),
                     'status': 'planned', 'started_wall': None, 'elapsed_min': 0.0, 'paused_at': None, 'start_at_wall': None},
           'items': [], 'tags': {}, 'log': [], 'needs': [], 'need_defaults': _need_defaults(scenario), 'score_hist': [],
           'done': copy.deepcopy(scenario.get('done') or {}), 'agencies': copy.deepcopy(scenario.get('agencies') or {})}
    ctxs = {u['id']: _Ctx(idx, u, run, rng, today) for u in units}
    # placeholders for items that are not about one unit (net openings, prompts): the stake(s) in scope and the EOC
    s0 = next((s for s in run['scope']['stakes'] if s in idx.stakes), None)
    erd0, spec0 = (idx.erd(s0) if s0 else {}), (idx.specialist(s0) if s0 else {})
    once_values = {'stake': ' / '.join(idx.stakes[s]['name'] for s in run['scope']['stakes'] if s in idx.stakes) or 'stake',
                   'eoc_call': eoc.get('call') or 'the EOC station', 'eoc_winlink': eoc.get('winlink') or 'the EOC Winlink address',
                   'eoc_email': eoc.get('email') or 'the EOC drop address', 'eoc': eoc.get('name') or 'the EOC', 'today': today,
                   # the stake's emergency roles (local-roles.json beside the pack), so prompts, notes and role cards can name them
                   'erd': erd0.get('name') or 'the Emergency Response Director', 'erd_phone': erd0.get('mobile') or erd0.get('phone', ''),
                   'specialist': spec0.get('name') or 'the Welfare and Self-Reliance Specialist (emergency communications)',
                   'specialist_phone': spec0.get('mobile') or spec0.get('phone', '')}
    once_values.update(agency_values(run['agencies'], (idx.stakes.get(s0) or {}).get('city', '') if s0 else ''))
    once_fill = lambda s: re.sub(r'\{([a-z_]+)\}', lambda m: str(once_values.get(m.group(1), m.group(0))), s)
    for role in run['roles']:                      # role cards are hand-outs: fill them once, for the stake in scope
        role['title'] = once_fill(str(role.get('title', '')))
        for c in role.get('cards', []):
            if isinstance(c.get('text'), str):
                c['text'] = once_fill(c['text'])
    templates = scenario.get('templates', {})
    chosen = {}                                   # inject id -> units it expanded to (for same_as)
    for inj in scenario.get('injects', []):
        kind = inj.get('kind', 'note')
        each = inj.get('each', 'once')
        if inj.get('same_as'):
            targets = chosen.get(inj['same_as'], [])
        elif each == 'unit':
            # tag_not (the units an earlier inject sampled under this tag send nothing here) is applied before the sample
            targets = _select(units, inj.get('where', {}), rng, scenario, run['tags'])
        elif each == 'stake':
            seen, targets = set(), []
            for u in _select(units, inj.get('where', {}), rng, scenario, run['tags']):
                if u['stake'] not in seen:
                    seen.add(u['stake'])
                    targets.append(u)
        else:
            targets = [None]
        chosen[inj['id']] = targets
        if inj.get('where', {}).get('tag'):
            run['tags'][inj['where']['tag']] = [u['id'] for u in targets if u]
        if kind == 'rollup':
            # Only a Council / Area simulator makes roll-ups: one per stake it plays itself (no EOC
            # laptop of its own in the drill). The bundle is built when the item fires.
            if site['role'] == 'area':
                for sid in site['stakes']:
                    if sid in site['played_stakes']:
                        continue
                    sname = idx.stakes.get(sid, {}).get('name', sid)
                    run['items'].append({'id': f"{inj['id']}@{sid}", 'inject': inj['id'], 'kind': 'rollup', 't': _minute(inj.get('t', 0), rng),
                                         'status': 'pending', 'result': None, 'fired_wall': None, 'unit_id': '', 'unit': '', 'stake': sname, 'stake_id': sid,
                                         'severity': None, 'note': inj.get('note', ''), 'role': '', 'to': 'area', 'local': True,
                                         'text': once_fill((inj.get('text', '') or 'SITREP roll-up from {stake}').replace('{stake}', sname))})
            continue
        for u in targets:
            ctx = ctxs[u['id']] if u else None
            item = {'id': f"{inj['id']}" + (f"@{u['id']}" if u else ''), 'inject': inj['id'], 'kind': kind,
                    't': _minute(inj.get('t', 0), rng), 'status': 'pending', 'result': None, 'fired_wall': None,
                    'unit_id': u['id'] if u else '', 'unit': u['name'] if u else '', 'stake': ctx.values['stake'] if ctx else '',
                    'severity': u['severity'] if u else None, 'note': inj.get('note', ''), 'role': inj.get('role', '')}
            if inj.get('lesson'):
                item['lesson'] = inj['lesson']          # the real-disaster reason behind the inject (the debrief's "why it matters")
            if inj.get('after'):
                # a consequence: fires when another inject's need reaches a state (met / overdue / missed)
                a = inj['after']
                item['after'] = {'need': a.get('need', ''), 'is': a.get('is', 'met'), 'delay': float(a.get('delay', 0) or 0)}
                item['status'] = 'waiting'
            # which EOC of the drill this item is for, and whether this simulator plays that EOC
            to = inj.get('to') if inj.get('to') in ('stake', 'satellite', 'area', 'all', 'unit') else DEFAULT_TO.get(kind, 'all')   # scenarios also say to: eoc for the log
            if to == 'unit':
                if u and (u['id'] in site['satellite_units'] or (site['role'] == 'satellite' and u['id'] in site['units'])):
                    to = 'satellite'
                elif u and site['role'] == 'area' and u.get('stake') not in site['played_stakes']:
                    to = 'area'
                else:
                    to = 'stake'
            item['to'] = to
            if site['role'] == 'area' and to == 'area' and kind == 'form':
                item['rollup'] = True              # travels inside a roll-up bundle, never on its own
            item['local'] = to == 'all' or to == site['role']
            if u and site['role'] == 'area' and u.get('stake') in site['played_stakes']:
                item['local'] = False              # that stake has its own EOC laptop and simulator: it delivers the unit's traffic
            if kind == 'reply':
                # the line above answering: simulated unless people play that EOC in this drill
                item['local'] = not _parent_played(site)
            if not item['local']:
                item['status'] = 'elsewhere'       # the simulator of that EOC fires it
            if kind == 'form':
                tpl = templates.get(inj.get('template', ''))
                if not tpl or not u:
                    continue
                item['form'] = inj['form']
                item['channel'] = inj.get('channel', 'by_pace')
                item['payload'] = build_form(inj['form'], tpl, ctx)
            elif kind == 'work_item':
                # A request or decision that lands on the EOC's Work Items list (what the
                # reports cannot derive: leadership questions, the county, the line above).
                f = ctx.fill if ctx else once_fill
                item['text'] = f(inj.get('text', '') or inj.get('title', ''))
                item['work'] = {'title': f(inj.get('title', '')), 'detail': f(inj.get('detail', '')), 'next': f(inj.get('next', '')),
                                'cat': inj.get('cat', 'other'), 'prio': int(inj.get('prio', 2) or 2), 'due': f(inj.get('due', '')),
                                'unit': u['name'] if u else f(inj.get('unit', '')), 'key': 'sim:' + item['id'], 'from': f(inj.get('from', ''))}
            elif kind == 'reply':
                # The line above answers: UP work items matching `match` are closed with the decision,
                # the way a reply bundle from a real Council / Area EOC closes them.
                f = ctx.fill if ctx else once_fill
                item['text'] = f(inj.get('text', ''))
                item['reply'] = {'match': dict(inj.get('match') or {}), 'decision': f(inj.get('decision', '')),
                                 'status': inj.get('status') if inj.get('status') in ('done', 'progress', 'open') else 'done',
                                 'from': f(inj.get('from', '') or 'the line above'), 'unit': u['name'] if u else ''}
            elif kind == 'ics':
                # Partner-agency traffic (a city EOC that does not run this system) as the standard Winlink ICS forms;
                # never a Church form. The EOC files it as a note and a work item (eoc_server._ingest_ics).
                f = ctx.fill if ctx else once_fill
                form = inj.get('form') if inj.get('form') in ICS_FORMS else 'ics213'
                ag = inj.get('agency', 'city_eoc')
                vals = ctx.values if ctx else once_values
                fields = {k: f(str(v)) for k, v in (inj.get('fields') or {}).items()}
                item['ics'] = {'form': form, 'agency': vals.get(ag, ag), 'call': vals.get(ag + '_call', 'CITYEOC'),
                               'contact': vals.get(ag + '_contact', ''), 'place': vals.get(ag + '_place', ''),
                               'subject': f(inj.get('subject', '')), 'fields': fields}
                item['text'] = f(inj.get('text', '')) or f"{ICS_FORMS[form]} from {item['ics']['agency']}: {item['ics']['subject']}"
                item['channel'] = 'ics'
            elif kind in ('note', 'voice', 'prompt', 'paper'):
                item['text'] = ctx.fill(inj.get('text', '')) if ctx else once_fill(inj.get('text', ''))
                if kind == 'note':
                    item['channel'] = 'note'
                elif kind == 'voice':
                    item['channel'] = 'voice'
                elif kind == 'prompt':
                    item['channel'] = 'prompt'
            if isinstance(inj.get('need'), dict):
                item['need_spec'] = dict(inj['need'])          # the inject's own need (a card to act on) or overrides for its derived needs
            run['items'].append(item)
    run['items'].sort(key=lambda i: (i['t'], i['id']))
    for it in run['items']:
        if it.get('status') == 'elsewhere' or not it.get('local', True):
            continue
        need = None
        if it['kind'] == 'work_item':
            need = need_for_work_item(run, it)
        elif it['kind'] in ('voice', 'paper', 'prompt', 'note', 'ics') and it.get('need_spec'):
            need = need_for_card(run, it)
        if need:
            # a label from the scenario ("Shelter for {unit}") is filled with the item's own unit, like its text
            f = ctxs[it['unit_id']].fill if it.get('unit_id') in ctxs else once_fill
            need['label'] = f(str(need.get('label') or ''))
            if need.get('rule', {}).get('label'):
                need['rule']['label'] = f(str(need['rule']['label']))
            _register_need(run, it, need)
    return run


def _parent_played(site: dict) -> bool:
    """True when people play the EOC above this one in the drill, so its replies are theirs to send."""
    if site.get('role') == 'satellite':
        return True                                  # the Stake EOC always has its own laptop and simulator
    return bool(site.get('played_parent'))


def _need_defaults(scenario: dict) -> dict:
    d = copy.deepcopy(NEED_DEFAULTS)
    for cat, spec in ((scenario.get('needs') or {}).get('defaults') or {}).items():
        d.setdefault(cat, {}).update(spec)
    return d


def _need_rule(run: dict, cat: str, spec: dict = None) -> dict:
    rule = dict(run.get('need_defaults', NEED_DEFAULTS).get(cat) or NEED_DEFAULTS.get('other'))
    rule.update({k: v for k, v in (spec or {}).items() if k in ('owner', 'done', 'decision', 'done_states', 'typed', 'label', 'role')})
    return rule


def _register_need(run: dict, item: dict, need: dict):
    if not need or any(n['id'] == need['id'] for n in run['needs']):
        return
    need.setdefault('item', item['id'])
    need.setdefault('inject', item['inject'])
    need.setdefault('unit', item.get('unit', ''))
    need.setdefault('state', 'open')
    need.setdefault('arose_t', None)                  # set when the item fires
    need.setdefault('times', {})
    need.setdefault('evidence', '')
    run['needs'].append(need)


def need_for_work_item(run: dict, it: dict) -> dict:
    """The need a scripted work item registers: the item itself, owned and closed in time."""
    w = it.get('work') or {}
    cat = w.get('cat') or 'other'
    rule = _need_rule(run, cat, it.get('need_spec'))
    return {'id': 'need:' + it['id'], 'kind': 'item', 'cat': cat, 'prio': int(w.get('prio') or 2), 'label': rule.get('label') or w.get('title', ''),
            'match': {'key': w.get('key', '')}, 'rule': rule, 'role': rule.get('role') or NEED_ROLE.get(cat, NEED_ROLE['other'])}


def need_for_card(run: dict, it: dict) -> dict:
    """A card (net card, prompt, note) whose `need` block says what the EOC must do about it: a work
    item of the category for the unit (`match.cat`), or a report typed in (`match.form`)."""
    spec = it.get('need_spec') or {}
    cat = spec.get('cat') or 'other'
    rule = _need_rule(run, cat, spec)
    match = {'unit': it.get('unit', '')}
    if it.get('kind') == 'ics' and not spec.get('form'):
        # the EOC files an ICS message as a work item with no unit: "<agency> resource request (ICS 213RR): <item>" or
        # "<agency> message (ICS 213): <subject>", from "<agency> (<call>)", key ics:<Message-ID>
        ics = it.get('ics') or {}
        match = {'unit': '', 'agency': [x for x in (ics.get('agency'), ics.get('call')) if x], 'subject': ics.get('subject', '')}
        if spec.get('cat'):
            match['cat'] = spec['cat']
        if spec.get('title_contains'):
            match['title_contains'] = spec['title_contains']
        return {'id': 'need:' + it['id'], 'kind': 'item', 'cat': cat, 'prio': int(spec.get('prio') or 2),
                'label': spec.get('label') or it.get('text', '')[:80], 'match': match, 'rule': rule, 'role': rule.get('role') or NEED_ROLE.get(cat, NEED_ROLE['other'])}
    if spec.get('form'):
        match['form'] = spec['form']
        cat = 'report'
        rule = _need_rule(run, 'report', spec)
    else:
        match['cat'] = cat
        if spec.get('title_contains'):
            match['title_contains'] = spec['title_contains']
    return {'id': 'need:' + it['id'], 'kind': 'report' if spec.get('form') else 'item', 'cat': cat, 'prio': int(spec.get('prio') or 2),
            'label': spec.get('label') or it.get('text', '')[:80], 'match': match, 'rule': rule, 'role': rule.get('role') or NEED_ROLE.get(cat, NEED_ROLE['other'])}


def needs_for_form(run: dict, it: dict, delivered_via: str) -> list:
    """The needs a simulated report creates at the EOC: the work items the EOC itself will derive from
    it (the same code, so the titles match exactly), and, when a person must type it in (paper card,
    net card), the report itself."""
    eoc = _eoc_module()
    form = it['form']
    rec = {'id': it['id'], 'type': form, form: eoc._map_worker_to_eoc(form.upper(), it['payload']),
           'fields': {k: v for k, v in it['payload'].items() if isinstance(v, (str, int, float, bool))}}
    spec = it.get('need_spec') or {}
    out = []
    if delivered_via in ('paper', 'voice'):
        rule = _need_rule(run, 'report', spec)
        out.append({'id': f"need:{it['id']}#report", 'kind': 'report', 'cat': 'report', 'prio': 2,
                    'label': f"{FORM_TITLES[form]} from {it.get('unit', '')} typed in from the {'card' if delivered_via == 'paper' else 'net'}",
                    'match': {'form': form, 'unit': it.get('unit', '')}, 'rule': rule,
                    'role': rule.get('role') or NEED_ROLE['report'], 'truth': {k: str(v) for k, v in rec[form].items() if k in TRUTH_FIELDS.get(form, ())}})
    for a in eoc._derive_actions(rec):
        cat = a.get('cat') or 'other'
        rule = _need_rule(run, cat, spec)
        out.append({'id': f"need:{it['id']}#{a['key'].split(':')[1]}", 'kind': 'item', 'cat': cat, 'prio': int(a.get('prio') or 2), 'label': a['title'],
                    'match': {'cat': cat, 'unit': a.get('unit', ''), 'title': a['title']}, 'rule': rule,
                    'role': rule.get('role') or NEED_ROLE.get(cat, NEED_ROLE['other'])})
    return out


# The fields of a typed-in report the simulator compares with the card it handed out (EOC record keys)
TRUTH_FIELDS = {'dr': ('mem_inj', 'mem_dead', 'homes_dmg', 'homes_dest', 'miss_safe', 'need_local', 'need_neighbor', 'need_hq', 'vol_count', 'vol_hrs', 'inc_type'),
                'so': ('items', 'del_date', 'del_city'), 'wcl': ('crew_count', 'total_hrs', 'chief', 'safety')}
TRUTH_LABELS = {'mem_inj': 'injured', 'mem_dead': 'deaths', 'homes_dmg': 'homes damaged', 'homes_dest': 'homes destroyed', 'miss_safe': 'missionaries safe',
                'need_local': 'need local facilities', 'need_neighbor': 'need neighboring units', 'need_hq': 'need headquarters', 'vol_count': 'volunteers',
                'vol_hrs': 'volunteer hours', 'inc_type': 'incident type', 'items': 'items', 'del_date': 'needed by', 'del_city': 'deliver to city',
                'crew_count': 'crew count', 'total_hrs': 'total hours', 'chief': 'crew chief', 'safety': 'safety acknowledgment'}


def _norm_val(k: str, v) -> str:
    v = str(v if v is not None else '').strip()
    if k in ('miss_safe', 'need_local', 'need_neighbor', 'need_hq', 'safety'):
        return 'YES' if v.lower() in ('yes', 'true', '1', 'on') else ('NO' if v.lower() in ('no', 'false', '0', 'off') else v.upper())
    if k == 'items':
        return ';'.join(sorted(p.strip().lower() for p in v.split(';') if p.strip()))
    if k in ('mem_inj', 'mem_dead', 'homes_dmg', 'homes_dest', 'vol_count', 'vol_hrs', 'crew_count', 'total_hrs'):
        try:
            return str(float(v or 0)).rstrip('0').rstrip('.')
        except ValueError:
            return v
    return ' '.join(v.lower().split())


def compare_truth(truth: dict, rec: dict) -> dict:
    """How well a typed-in report matches the card: {score 0..1, matched, total, wrong: [text]}."""
    total, ok, wrong = 0, 0, []
    for k, tv in truth.items():
        if _norm_val(k, tv) == '' and k not in ('mem_inj', 'mem_dead', 'homes_dmg', 'homes_dest'):
            continue
        total += 1
        rv = rec.get(k, '')
        if _norm_val(k, tv) == _norm_val(k, rv):
            ok += 1
        else:
            wrong.append(f"{TRUTH_LABELS.get(k, k)}: typed {rv or 'nothing'}, card said {tv}")
    return {'score': round(ok / total, 2) if total else 1.0, 'matched': ok, 'total': total, 'wrong': wrong}


# ── Winlink message bodies (the same tagged text the Winlink templates produce) ──
def _fmt_date(v: str) -> str:
    return f'{v[5:7]}/{v[8:10]}/{v[0:4]}' if re.match(r'^\d{4}-\d{2}-\d{2}$', v or '') else (v or '')


def _ascii(s) -> str:
    return str(s if s is not None else '').encode('ascii', 'replace').decode('ascii').replace('|', '/').replace(']', ')').replace('\n', ' ')


def _tag(form: str, pairs: list) -> str:
    return f"[Church-{form.upper()}|" + '|'.join(f'{k}={_ascii(v)}' for k, v in pairs) + ']'


def body_text(form: str, d: dict, unit_name: str = '') -> str:
    """A readable report followed by the machine tag and CSV line, as a Winlink template sends it."""
    g = lambda k: _ascii(d.get(k, ''))
    L = ['=' * 60, f'     {FORM_TITLES[form]}', '     The Church of Jesus Christ of Latter-day Saints', '=' * 60, '',
         f'     *** {SIM_MARK} ***', '']
    if form == 'dr':
        L += ['INCIDENT', f"  Stake: {g('inc_stake')}", f"  Ward / Branch: {g('inc_ward')}", f"  Date: {_fmt_date(g('inc_date'))}",
              f"  Type: {g('inc_type')}", f"  Location: {g('inc_location')}", f"  Stake President: {g('sp_name')}",
              f"  Submitted by: {g('sub_name')}  {g('sub_phone')}  {g('sub_email')}", '',
              'MISSIONARIES', f"  All safe and accounted for: {g('miss_safe')}", f"  {g('miss_details')}", '',
              'MEMBERS', f"  Injuries: {g('mem_injuries')}   Deaths: {g('mem_deaths')}",
              f"  Homes damaged: {g('mem_damaged')}   Homes destroyed: {g('mem_destroyed')}", f"  {g('mem_details')}", '',
              'CHURCH BUILDINGS', f"  {g('bldg_damage')}", '', 'COMMUNITY', f"  {g('community')}", '',
              'NEEDS', f"  Local: {g('need_local')}   Neighboring stakes: {g('need_neighbor')}   Church headquarters: {g('need_hq')}",
              f"  {g('needs_details')}", '', 'VOLUNTEERS', f"  Count: {g('vol_count')}   Hours: {g('vol_hours')}",
              f"  Activities: {g('vol_activities')}", f"  Volunteer injuries: {g('vol_injuries')}  {g('vol_inj_details')}", '']
        csv_line = 'CSV,' + ','.join(_ascii(x).replace(',', ';') for x in [
            g('inc_stake'), _fmt_date(g('inc_date')), g('inc_location'), g('inc_type'), g('miss_safe'), g('mem_injuries') or '0',
            g('mem_deaths') or '0', g('mem_damaged') or '0', g('mem_destroyed') or '0', g('vol_count') or '0', g('vol_hours') or '0',
            g('need_local'), g('need_neighbor'), g('need_hq'), g('sub_name'), g('sub_phone')])
        pairs = [('stake', g('inc_stake'))] + ([('ward', g('inc_ward'))] if g('inc_ward') else []) + [
            ('date', _fmt_date(g('inc_date'))), ('location', g('inc_location')), ('type', g('inc_type')), ('miss_safe', g('miss_safe')),
            ('mem_inj', g('mem_injuries') or '0'), ('mem_dead', g('mem_deaths') or '0'), ('homes_dmg', g('mem_damaged') or '0'),
            ('homes_dest', g('mem_destroyed') or '0'), ('vol_count', g('vol_count') or '0'), ('vol_hrs', g('vol_hours') or '0'),
            ('vol_inj', g('vol_injuries')), ('need_local', g('need_local')), ('need_neighbor', g('need_neighbor')), ('need_hq', g('need_hq')),
            ('submitter', g('sub_name')), ('phone', g('sub_phone')), ('sp', g('sp_name'))]
    elif form == 'so':
        items = [f'{k}:{v}' for k, v in d.items() if len(k) == 4 and k[:2].isalpha() and k[2:].isdigit() and str(v).strip() not in ('', '0')]
        for i in range(1, 6):
            od, oq = str(d.get(f'other_desc{i}', '') or '').strip(), str(d.get(f'other_qty{i}', '') or '').strip()
            if od and oq:
                items.append(f'LOCAL-{_ascii(od)[:20]}:{oq}')
        L += ['ORDER', f"  Stake: {g('req_stake')}", f"  Order date: {_fmt_date(g('order_date'))}   Needed by: {_fmt_date(g('req_del_date'))}",
              f"  Deliver to: {g('del_contact')}  {g('del_phone')}", f"  {g('del_addr')}, {g('del_city')}, {g('del_state')} {g('del_zip')}", '',
              'ITEMS'] + [f'  {it}' for it in items] + ['']
        csv_line = 'CSV,' + ','.join(_ascii(x).replace(',', ';') for x in [g('req_stake'), _fmt_date(g('order_date')), g('del_contact'), g('del_phone'),
                                                                            g('del_city'), g('del_state'), _fmt_date(g('req_del_date')), ';'.join(items)])
        pairs = [('stake', g('req_stake')), ('contact', g('del_contact')), ('phone', g('del_phone')), ('city', g('del_city')), ('state', g('del_state')),
                 ('zip', g('del_zip')), ('addr', g('del_addr')), ('order_date', _fmt_date(g('order_date'))), ('del_date', _fmt_date(g('req_del_date'))),
                 ('items', ';'.join(items))]
    else:
        crew, total, count = [], 0.0, 0
        L += ['LOG', f"  Date: {_fmt_date(g('log_date'))}   Location: {g('log_location')}",
              f"  Crew chief: {g('chief_name')}  {g('chief_stake')} / {g('chief_ward')}  {g('chief_hrs')} h  {g('chief_phone')}", '', 'CREW']
        for i in range(1, 21):
            cn = g(f'crew_name{i}').strip()
            if not cn:
                continue
            count += 1
            hrs = g(f'crew_hrs{i}') or '0'
            try:
                total += float(hrs)
            except ValueError:
                pass
            row = [cn, g(f'crew_stake{i}'), g(f'crew_ward{i}'), hrs, g(f'crew_wo{i}'), g(f'crew_addr{i}')]
            L.append('  ' + '  '.join(row))
            crew.append(':'.join(x.replace(':', ';') for x in row))
        try:
            total += float(g('chief_hrs') or 0)
        except ValueError:
            pass
        L += ['', f"  Safety acknowledgment: {'YES' if str(d.get('safety_cert', '')).lower() in ('true', 'yes', 'on', '1') else 'NO'}", '']
        csv_line = 'CSV,' + ','.join(_ascii(x).replace(',', ';') for x in [_fmt_date(g('log_date')), g('log_location'), g('chief_name'), g('chief_stake'),
                                                                            g('chief_ward'), str(count), str(total)])
        pairs = [('date', _fmt_date(g('log_date'))), ('location', g('log_location')), ('chief', g('chief_name')), ('chief_stake', g('chief_stake')),
                 ('chief_ward', g('chief_ward')), ('chief_hrs', g('chief_hrs') or '0'), ('chief_phone', g('chief_phone')), ('crew_count', str(count)),
                 ('total_hrs', str(total)), ('safety', 'YES' if str(d.get('safety_cert', '')).lower() in ('true', 'yes', 'on', '1') else 'NO'),
                 ('crew', ';'.join(crew)), ('submitter', unit_call({'name': unit_name}) if unit_name else '')]
    for k in ('stn_lat_d', 'stn_lon_d', 'stn_grid_d'):
        if d.get(k):
            pairs.append(({'stn_lat_d': 'lat', 'stn_lon_d': 'lon', 'stn_grid_d': 'grid'}[k], d[k]))
    L += ['', csv_line, '', _tag(form, pairs), '']
    return '\r\n'.join(L)


def winlink_mime(item: dict, run: dict) -> tuple:
    """(filename, bytes) of a Winlink-style .mime message for the EOC's Received-folder watcher."""
    form, d, unit = item['form'], item['payload'], item.get('unit', '')
    call = unit_call({'name': unit})
    stake = d.get('inc_stake') or d.get('req_stake') or d.get('chief_stake') or ''
    subject = {'dr': f"Church Disaster Report: {stake} - {d.get('inc_type', '')} ({d.get('inc_date', '')})",
               'so': f"Church Supply Order: {stake} ({d.get('order_date', '')})",
               'wcl': f"Church Work Crew Log: {stake} / {d.get('chief_ward', '')} ({d.get('log_date', '')})"}[form]
    msg = email.message.EmailMessage()
    msg['Date'] = email.utils.format_datetime(_dt.datetime.now(_dt.timezone.utc))
    msg['From'] = f'{call}@winlink.org'
    msg['To'] = run['eoc'].get('winlink') or 'EOC@winlink.org'
    msg['Subject'] = _ascii(subject)
    mid = uuid.uuid4().hex[:12].upper()
    msg['Message-ID'] = mid
    msg['X-Source'] = call
    msg['X-Simulated'] = f"EMCOMM drill run {run['id']}"
    if d.get('stn_lat_d'):
        lat, lon = float(d['stn_lat_d']), float(d['stn_lon_d'])
        msg['X-Location'] = f"{abs(lat):.6f}{'N' if lat >= 0 else 'S'}, {abs(lon):.6f}{'W' if lon < 0 else 'E'} (GRID SQUARE)"
    msg.set_content(body_text(form, d, unit), charset='iso-8859-1', cte='quoted-printable')
    return f'{mid}.mime', msg.as_bytes()


ICS_LABELS = {'incident_name': 'Incident Name', 'to_name': 'To (Name and Position)', 'from_name': 'From (Name and Position)',
              'subject': 'Subject', 'date': 'Date', 'time': 'Time', 'message': 'Message', 'approved_by': 'Approved by',
              'request_number': 'Resource Request Number', 'priority': 'Priority', 'qty': 'Quantity', 'kind': 'Kind',
              'type': 'Type', 'item': 'Detailed Item Description', 'requested_arrival': 'Requested Arrival Date/Time',
              'deliver_to': 'Deliver to / Reporting Location', 'substitutes': 'Suitable Substitutes', 'requested_by': 'Requested by (Name/Position)',
              'contact': 'Contact at the Delivery Point'}


def ics_text(ics: dict) -> str:
    """The message body the way Winlink's ICS 213 / 213RR templates lay it out (label: value lines)."""
    title = {'ics213': 'GENERAL MESSAGE (ICS 213)', 'ics213rr': 'RESOURCE REQUEST MESSAGE (ICS 213RR)'}[ics['form']]
    lines = [title, '']
    for k, v in ics['fields'].items():
        lines.append(f"{ICS_LABELS.get(k, k.replace('_', ' ').title())}: {v}")
    lines += ['', f"Sent by {ics['agency']}" + (f" ({ics['call']})" if ics.get('call') else '') + (f", {ics['place']}" if ics.get('place') else '')]
    return '\r\n'.join(lines)


def ics_mime(item: dict, run: dict) -> tuple:
    """(filename, bytes) of a Winlink message carrying an ICS 213 or 213RR, with the RMS_Express_Form XML Winlink attaches."""
    ics = item['ics']
    viewer = {'ics213': 'ICS213_Viewer.html', 'ics213rr': 'ICS213RR_Viewer.html'}[ics['form']]
    msg = email.message.EmailMessage()
    msg['Date'] = email.utils.format_datetime(_dt.datetime.now(_dt.timezone.utc))
    msg['From'] = f"{ics['call']}@winlink.org"
    msg['To'] = run['eoc'].get('winlink') or 'EOC@winlink.org'
    msg['Subject'] = _ascii(('ICS 213RR' if ics['form'] == 'ics213rr' else 'ICS 213') + ' - ' + (ics.get('subject') or ''))
    mid = uuid.uuid4().hex[:12].upper()
    msg['Message-ID'] = mid
    msg['X-Source'] = ics['call']
    msg['X-Simulated'] = f"EMCOMM drill run {run['id']}"
    msg.set_content(_ascii(ics_text(ics)), charset='iso-8859-1', cte='quoted-printable')
    def esc(s):
        return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    xml = ('<?xml version="1.0"?>\r\n<RMS_Express_Form>\r\n  <form_parameters>\r\n'
           f"    <xml_file_version>1.0</xml_file_version>\r\n    <senders_callsign>{esc(ics['call'])}</senders_callsign>\r\n"
           f"    <display_form>{viewer}</display_form>\r\n  </form_parameters>\r\n  <variables>\r\n"
           + ''.join(f'    <{k}>{esc(v)}</{k}>\r\n' for k, v in ics['fields'].items())
           + '  </variables>\r\n</RMS_Express_Form>\r\n')
    msg.add_attachment(xml.encode('utf-8'), maintype='text', subtype='xml', filename=f"RMS_Express_Form_{viewer.replace('.html', '')}.xml")
    return f'{mid}.mime', msg.as_bytes()


# ── delivery ─────────────────────────────────────────────────────────────────
def _http(url: str, method: str = 'GET', body=None, timeout: float = 10) -> dict:
    data = json.dumps(body).encode('utf-8') if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8') or 'null')


class Runner:
    """Plays one run against an EOC server. All public methods are safe to call from any thread."""

    def __init__(self, run: dict, eoc_url: str, runs_dir, received_dir: str = '', drop_dir: str = '', controller_url: str = ''):
        self.run, self.eoc_url, self.runs_dir = run, eoc_url.rstrip('/'), Path(runs_dir)
        self.received_dir, self.drop_dir, self.controller_url = received_dir, drop_dir, controller_url
        self.lock = threading.RLock()
        self._thread = None
        self._stop = threading.Event()
        self._dead = threading.Event()
        self._tick_wall = 0.0
        self.run.setdefault('board', [])
        self.run.setdefault('needs', [])
        self.run.setdefault('score_hist', [])
        self.save()
        # coordination: push the drill state to the EOC, read who is ready, start on schedule
        self._coord = threading.Thread(target=self._coord_loop, daemon=True)
        self._coord.start()

    # ── drill coordination ──
    def drill_state(self) -> dict:
        c, site = self.run['clock'], self.run.get('site') or {}
        return {'active': True, 'run_id': self.run['id'], 'scenario': self.run['scenario']['name'], 'scenario_id': self.run['scenario']['id'],
                'controller': self.controller_url, 'role': site.get('role', 'stake'), 'site_label': site.get('label', ''), 'parent': site.get('parent', ''),
                'status': c['status'], 'elapsed_min': round(self.elapsed(), 2), 'speed': c['speed'],
                'start_at_ms': int(c['start_at_wall'] * 1000) if c.get('start_at_wall') else 0,
                'pace': pace_at(self.run['pace'], self.elapsed()), 'seed': self.run['seed'], 'privacy': self.run['pack']['privacy'],
                'units': site.get('unit_names', []), 'score': self.score_brief(),
                'session': bool((self.run.get('session') or {}).get('ready'))}

    def push_drill(self) -> dict:
        """PUT the drill state to this simulator's EOC; returns the EOC's answer (ready names)."""
        try:
            return _http(self.eoc_url + '/api/drill', 'PUT', self.drill_state(), timeout=4) or {}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def refresh_board(self) -> list:
        """Every EOC on the network and the drill state its own simulator pushed: this EOC first,
        then the peers this EOC hears (its LAN discovery). Remote sites are coordinated by voice."""
        rows = []
        mine = self.push_drill()
        try:
            st = _http(self.eoc_url + '/api/status', timeout=4)
        except Exception as e:
            st = {'error': str(e)}
        d = self.drill_state()
        rows.append({'url': self.eoc_url, 'self': True, 'ok': 'error' not in st, 'name': st.get('eocName', ''), 'level': st.get('eocLevel', ''),
                     'event': st.get('activeEventName', ''), 'role': d['role'], 'site_label': d['site_label'], 'scenario': d['scenario'], 'scenario_id': d['scenario_id'],
                     'seed': d['seed'], 'status': d['status'], 'start_at_ms': d['start_at_ms'], 'ready': mine.get('ready', []), 'error': st.get('error', '')})
        try:
            peers = _http(self.eoc_url + '/api/peers', timeout=4) or []
        except Exception:
            peers = []
        for p in peers:
            if not isinstance(p, dict) or p.get('self') or not p.get('url') or p['url'].rstrip('/') == self.eoc_url:
                continue
            row = {'url': p['url'], 'self': False, 'ok': False, 'name': p.get('name', ''), 'level': p.get('level', ''), 'event': p.get('event', ''),
                   'role': '', 'site_label': '', 'scenario': '', 'scenario_id': '', 'seed': None, 'status': 'no simulator', 'start_at_ms': 0, 'ready': []}
            try:
                pd = _http(p['url'].rstrip('/') + '/api/drill', timeout=3) or {}
                row['ok'] = True
                if pd.get('active'):
                    row.update({k: pd.get(k) for k in ('role', 'site_label', 'scenario', 'scenario_id', 'seed', 'status', 'start_at_ms')})
                    row['ready'] = pd.get('ready', [])
                    row['stale'] = pd.get('stale', False)
            except Exception as e:
                row['error'] = str(e)
            rows.append(row)
        with self.lock:
            self.run['board'] = rows
            self.run['board_ms'] = int(time.time() * 1000)
        return rows

    def schedule(self, at: str) -> dict:
        """Start the clock at a wall-clock time 'HH:MM' or 'HH:MM:SS' (today; a time already past
        starts at once). Every simulator of the drill set to the same time starts together."""
        parts = [int(x) for x in str(at).strip().split(':')]
        while len(parts) < 3:
            parts.append(0)
        now = _dt.datetime.now()
        when = now.replace(hour=parts[0], minute=parts[1], second=parts[2], microsecond=0)
        with self.lock:
            c = self.run['clock']
            if c['status'] == 'running':
                return {'ok': False, 'error': 'The run is already running.'}
            c['start_at_wall'] = when.timestamp()
            c['status'] = 'scheduled'
            self._log(f"Start scheduled for {when.strftime('%H:%M:%S')}")
        self.save()
        self.push_drill()
        return {'ok': True, 'start_at_ms': int(when.timestamp() * 1000)}

    def unschedule(self):
        with self.lock:
            c = self.run['clock']
            if c['status'] == 'scheduled':
                c['status'] = 'planned' if c['elapsed_min'] == 0 else 'paused'
                c['start_at_wall'] = None
                self._log('Scheduled start cancelled')
        self.save()
        self.push_drill()

    def shutdown(self, clear: bool = False):
        """Stop the clock and the coordination thread; `clear` takes the drill bar off the EOC."""
        self._stop.set()
        self._dead.set()
        if clear:
            try:
                _http(self.eoc_url + '/api/drill', 'DELETE', timeout=3)
            except Exception:
                pass

    def _coord_loop(self):
        n = 0
        while not self._dead.is_set():
            try:
                c = self.run['clock']
                if c['status'] == 'scheduled' and c.get('start_at_wall') and time.time() >= c['start_at_wall']:
                    self.start()
                if n % 5 == 0:
                    self.refresh_board()
            except Exception:
                pass
            n += 1
            time.sleep(1.0)

    # clock
    def elapsed(self) -> float:
        c = self.run['clock']
        if c['status'] == 'running' and c['started_wall']:
            return c['elapsed_min'] + (time.time() - c['started_wall']) / 60 * c['speed']
        return c['elapsed_min']

    def _log(self, text: str):
        self.run['log'].append({'wall': _dt.datetime.now().strftime('%H:%M:%S'), 't': round(self.elapsed(), 1), 'text': text})
        self.run['log'] = self.run['log'][-500:]

    def save(self):
        with self.lock:
            c = self.run['clock']
            c['saved_elapsed'] = round(self.elapsed(), 3)          # where the clock was: a restart resumes from here
            c['saved_wall'] = int(time.time() * 1000)
            self.runs_dir.mkdir(parents=True, exist_ok=True)
            atomic_write(self.runs_dir / f"run-{self.run['id']}.json", json.dumps(self.run, ensure_ascii=False, indent=1))

    def state(self) -> dict:
        with self.lock:
            s = dict(self.run)
            s['clock'] = dict(self.run['clock'], elapsed_min=round(self.elapsed(), 2), pace=pace_at(self.run['pace'], self.elapsed()))
            s['score'] = self.score() if any(n.get('arose_t') is not None for n in self.run.get('needs', [])) else None
            return s

    def _mark(self):
        """Record a clock segment: from this wall moment, the drill minute and the speed in force
        (0 while paused or stopped). `drill_minute()` maps any wall time back through them, so the
        hot-wash evidence measures drill minutes correctly across speed changes, pauses and jumps."""
        c = self.run['clock']
        c.setdefault('segments', []).append({'wall': int(time.time() * 1000), 't': round(self.elapsed(), 3),
                                             'speed': c['speed'] if c['status'] == 'running' else 0})

    def drill_minute(self, wall_ms) -> float:
        """The drill minute that was on the clock at a wall-clock time (ms)."""
        cur = None
        for s in self.run['clock'].get('segments') or []:
            if s['wall'] <= wall_ms:
                cur = s
            else:
                break
        if cur is None:
            return 0.0
        return cur['t'] + max(0, wall_ms - cur['wall']) / 60000 * cur['speed']

    def start(self):
        with self.lock:
            c = self.run['clock']
            if c['status'] == 'running':
                return
            c['started_wall'] = time.time()
            c['status'] = 'running'
            if c['elapsed_min'] == 0:
                c['t0_wall'] = time.time()
            first = c['elapsed_min'] == 0
            self._log('Run started' if first else 'Run resumed')
            self._mark()
            if not self._thread or not self._thread.is_alive():
                self._stop.clear()
                self._thread = threading.Thread(target=self._loop, daemon=True)
                self._thread.start()
        if first and (self.run.get('session') or {}).get('ready'):
            self._event_clock_start()
        self.save()
        self.push_drill()

    def _event_clock_start(self):
        """GO for a session: the EOC's drill event starts now, so its SITREP-due time counts from the start of the
        drill, not from when the event was opened before the meeting."""
        try:
            inc = _http(self.eoc_url + '/api/incident', timeout=4)
            inc['startTs'] = int(time.time() * 1000)
            inc.pop('lastSitrepTs', None)
            _http(self.eoc_url + '/api/incident', 'PUT', inc, timeout=4)
            self._log('Session started: the EOC drill event clock starts now (SITREP times count from here)')
        except Exception as e:
            self._log(f'Session started; the EOC event clock was not reset: {e}')

    def pause(self):
        with self.lock:
            c = self.run['clock']
            if c['status'] != 'running':
                return
            c['elapsed_min'] = self.elapsed()
            c['started_wall'] = None
            c['status'] = 'paused'
            self._log('Run paused')
            self._mark()
        self.save()
        self.push_drill()

    def stop(self):
        with self.lock:
            c = self.run['clock']
            c['elapsed_min'] = self.elapsed()
            c['started_wall'] = None
            c['status'] = 'stopped'
            self._log('Run stopped')
            self._mark()
        self._stop.set()
        try:
            if any(n.get('arose_t') is not None for n in self.run['needs']):
                self._needs_tick(final=True)
                self._log(f"Final score: {self.score_brief().get('pct')}% of needs met")
                self.write_report()
        except Exception as e:
            self._log(f'final score failed: {type(e).__name__}: {e}')
        self.save()
        self.push_drill()

    def set_speed(self, speed: float):
        with self.lock:
            c = self.run['clock']
            c['elapsed_min'] = self.elapsed()
            if c['status'] == 'running':
                c['started_wall'] = time.time()
            c['speed'] = max(0.1, min(60.0, float(speed)))
            self._mark()
        self.save()

    def jump(self, minute: float):
        """Move the clock (items before the new minute that have not fired stay pending until fired or skipped)."""
        with self.lock:
            c = self.run['clock']
            c['elapsed_min'] = max(0.0, float(minute))
            if c['status'] == 'running':
                c['started_wall'] = time.time()
            self._log(f'Clock set to T+{minute:g}')
            self._mark()
        self.save()

    def _push_pace(self, level: str, why: str) -> dict:
        """Set the EOC's PACE level (the header, the Help page and the SITREP react) and remember
        what was pushed, so the scenario timeline pushes each step once and only when it changes."""
        with self.lock:
            self.run['clock']['pace_pushed'] = level
        try:
            inc = _http(self.eoc_url + '/api/incident')
            if inc.get('pace') != level:
                inc['pace'], inc['paceTs'] = level, int(time.time() * 1000)
                _http(self.eoc_url + '/api/incident', 'PUT', inc)
            self._log(f'PACE {level} in force ({why}): EOC header set')
            return {'ok': True, 'level': level}
        except Exception as e:
            self._log(f'PACE {level} in force ({why}): EOC not reachable, {e}')
            return {'ok': False, 'level': level, 'error': str(e)}

    def set_pace(self, level: str, why: str = '', push: bool = True) -> dict:
        """A PACE change decided during the run: recorded on the run's timeline, pushed to the EOC."""
        level = level.upper()
        if level not in PACE_LEVELS:
            raise ValueError('level must be P, A, C or E')
        with self.lock:
            t = math.floor(self.elapsed() * 10) / 10          # never later than the clock, so it is in force at once
            self.run['pace'] = [s for s in self.run['pace'] if s['t'] < t] + [{'t': t, 'level': level, 'why': why or 'set by the controller', 'manual': True}]
            self._log(f'PACE {level} from T+{t:g}')
        res = {'ok': True, 'level': level}
        if push:
            res = self._push_pace(level, why or 'set by the controller')
        self.save()
        return res

    def item(self, item_id: str) -> dict:
        for it in self.run['items']:
            if it['id'] == item_id:
                return it
        raise KeyError(item_id)

    def set_status(self, item_id: str, status: str):
        with self.lock:
            it = self.item(item_id)
            if status in ('skipped', 'held', 'pending') and it['status'] in ('pending', 'held', 'skipped'):
                it['status'] = status
        self.save()

    def hotwash(self, n: int, result: str, note: str):
        with self.lock:
            self.run['hotwash'][n]['result'] = result
            self.run['hotwash'][n]['note'] = note
        self.save()

    def gather_evidence(self) -> dict:
        """Evaluate every hot-wash check that carries an `auto` rule against the EOC's work
        items now, and store the evidence text and a suggested result on the check. The
        controller still presses the button: the rule sees the data, not the room."""
        try:
            acts = _http(self.eoc_url + '/api/actions')
            if not isinstance(acts, list):
                acts = []
        except Exception as e:
            return {'ok': False, 'error': f'EOC not reachable: {e}'}
        speed = float(self.run['clock'].get('speed') or 1)
        n_auto = 0
        with self.lock:
            for h in self.run['hotwash']:
                rule = h.get('auto')
                if not isinstance(rule, dict):
                    continue
                n_auto += 1
                h['evidence'], h['suggest'] = evaluate_rule(rule, acts, speed, to_t=self.drill_minute)
            self._log(f'Evidence gathered from the EOC for {n_auto} hot-wash checks ({len(acts)} work items on file)')
        self.save()
        return {'ok': True, 'checks': n_auto, 'items': len(acts)}

    # delivery
    def channel_for(self, it: dict) -> str:
        ch = it.get('channel', 'by_pace')
        if ch == 'by_pace':
            ch = CHANNEL_BY_PACE[pace_at(self.run['pace'], self.elapsed())]     # the level in force now
        if ch == 'winlink' and not self.received_dir:
            ch = 'paper'                       # no Winlink folder to write into: the operator types it in
        if ch == 'drop' and not self.drop_dir:
            ch = 'phone'
        return ch

    def fire(self, item_id: str, force: bool = False) -> dict:
        with self.lock:
            it = self.item(item_id)
            if it['status'] not in ('pending', 'held', 'waiting') and not force:
                return it
            if not it.get('local', True) and not force:
                return it                        # another EOC's simulator plays this one
            it['status'] = 'firing'
        res = {}
        try:
            k = it['kind']
            if k == 'rollup':
                res = self._fire_rollup(it)
            elif k == 'reply':
                res = self._fire_reply(it)
            elif k == 'note':
                _http(self.eoc_url + '/api/notes', 'POST', {'id': str(uuid.uuid4()), 'ts': int(time.time() * 1000), 'text': 'SIM: ' + it['text']})
                res = {'ok': True, 'via': 'note'}
            elif k == 'work_item':
                w = dict(it['work'], who='SIM', auto=False)
                r = _http(self.eoc_url + '/api/actions', 'POST', w)
                res = {'ok': bool(r.get('ok')), 'via': 'work item', 'dup': bool(r.get('duplicate'))}
                if not r.get('ok'):
                    res['error'] = r.get('error', 'EOC refused the work item')
            elif k == 'form':
                ch = self.channel_for(it)
                it['delivered_via'] = ch
                if ch == 'phone':
                    r = _http(self.eoc_url + '/api/upload', 'POST',
                              {'reports': [{'id': it['id'], 'form': it['form'], 'filename': FORM_FILENAMES[it['form']], 'data': it['payload']}]})
                    res = {'ok': bool(r.get('ok')), 'via': 'phone', 'new': r.get('new', 0), 'dup': r.get('dup', 0), 'errors': r.get('errors', 0),
                           'eoc': (r.get('eoc') or {}).get('name', '')}
                elif ch == 'drop':
                    p = Path(self.drop_dir) / f"{it['id'].replace('@', '_')}_{FORM_FILENAMES[it['form']]}"
                    atomic_write(p, '﻿' + json.dumps(it['payload'], indent=2, ensure_ascii=False))
                    res = {'ok': True, 'via': 'drop', 'file': str(p)}
                elif ch == 'winlink':
                    name, data = winlink_mime(it, self.run)
                    p = Path(self.received_dir) / name
                    atomic_write(p, data)
                    res = {'ok': True, 'via': 'winlink', 'file': str(p)}
                else:
                    it['text'] = body_text(it['form'], it['payload'], it.get('unit', ''))
                    res = {'ok': True, 'via': 'paper'}
            elif k == 'ics':
                if self.received_dir:
                    name, data = ics_mime(it, self.run)
                    p = Path(self.received_dir) / name
                    atomic_write(p, data)
                    it['ics_key'] = 'ics:' + name[:-len('.mime')]     # the key the EOC files it under (ics:<Message-ID>)
                    res = {'ok': True, 'via': 'winlink (ICS)', 'file': str(p)}
                else:
                    it['text'] = ics_text(it['ics'])
                    res = {'ok': True, 'via': 'paper'}
            else:                               # voice, prompt, paper: shown on the Run tab, nothing sent
                res = {'ok': True, 'via': k}
        except urllib.error.URLError as e:
            res = {'ok': False, 'error': f'EOC not reachable: {e.reason}'}
        except Exception as e:
            res = {'ok': False, 'error': f'{type(e).__name__}: {e}'}
        with self.lock:
            it['result'] = res
            it['status'] = 'fired' if res.get('ok') else 'error'
            it['fired_wall'] = _dt.datetime.now().strftime('%H:%M:%S')
            it['fired_t'] = round(self.elapsed(), 1)
            self._log(f"{it['kind']} {it['inject']}{' ' + it['unit'] if it['unit'] else ''}: " + (res.get('via', '') if res.get('ok') else 'ERROR ' + res.get('error', '')))
            if res.get('ok'):
                self._needs_arise(it)
        self.save()
        return it

    # ── needs: what the EOC must do about what it was sent ──
    def _needs_arise(self, it: dict):
        """Register the needs a fired item creates and stamp when they arose (drill minute, wall ms)."""
        now_t, now_ms = round(self.elapsed(), 1), int(time.time() * 1000)
        if it['kind'] == 'form' and not it.get('rollup'):
            for n in needs_for_form(self.run, it, it.get('delivered_via', '')):
                _register_need(self.run, it, n)
        for n in self.run['needs']:
            if n['item'] == it['id'] and n.get('arose_t') is None:
                n['arose_t'], n['arose_ms'] = now_t, now_ms
                if it.get('ics_key') and isinstance(n.get('match'), dict) and n['match'].get('agency'):
                    n['match']['key_pref'] = it['ics_key']

    def set_need(self, need_id: str, action: str) -> dict:
        """The controller waives a need (not played in this drill: out of the score) or reopens it."""
        with self.lock:
            n = next((x for x in self.run['needs'] if x['id'] == need_id), None)
            if not n:
                return {'ok': False, 'error': 'no such need'}
            if action == 'waive':
                n['state'], n['evidence'] = 'waived', 'waived by the controller'
            elif action == 'reopen':
                n['state'], n['evidence'] = 'open', ''
            else:
                return {'ok': False, 'error': 'action must be waive or reopen'}
            self._log(f"need {n['state'].upper()} by the controller: {n['label'][:60]}")
        self.save()
        return {'ok': True, 'need': n}

    def _fire_reply(self, it: dict) -> dict:
        """The line above answers: close the EOC's UP work items that match with the decision, through a
        church_eoc_reply bundle (the same thing a real Council / Area EOC sends back), and log a note."""
        rp = it['reply']
        m = rp.get('match') or {}
        acts = _http(self.eoc_url + '/api/actions')
        # the unit a work item is about: its own fields, or the report it came from (a Supply Order names the stake only)
        hay = {}
        if rp.get('unit'):
            try:
                for row in _http(self.eoc_url + '/api/messages', timeout=5) or []:
                    d = json.loads(row.get('data_json') or '{}')
                    sub = d.get(d.get('type') or '') or {}
                    hay[row.get('id')] = ' '.join(str(sub.get(k, '')) for k in ('ward', 'contact', 'chief_ward', 'location', 'addr')).lower()
            except Exception:
                pass
        cats = m.get('cat')
        if isinstance(cats, str):
            cats = [cats]
        want = m.get('status', 'up')
        want = [want] if isinstance(want, str) else list(want)
        sel = []
        for a in acts if isinstance(acts, list) else []:
            if cats and a.get('cat') not in cats:
                continue
            if want and 'any' not in want and a.get('status') not in want:
                continue
            if m.get('key_prefix') and not str(a.get('key', '')).startswith(m['key_prefix']):
                continue
            if m.get('title_contains') and m['title_contains'].lower() not in str(a.get('title', '')).lower():
                continue
            if rp.get('unit') and rp['unit'].lower() not in (str(a.get('unit', '')) + ' ' + str(a.get('title', '')) + ' ' + hay.get((a.get('src') or {}).get('id'), '')).lower():
                continue
            sel.append(a)
        frm = {'name': f"{rp.get('from') or 'the line above'} (simulated)", 'level': 'area' if (self.run.get('site') or {}).get('role') != 'satellite' else 'stake', 'sim': True}
        text = it.get('text') or rp.get('decision') or 'reply'
        bundle = {'kind': 'church_eoc_reply', 'v': 1, 'sim': True, 'from': frm, 'to': self.run['eoc'].get('name') or '', 'exportedAt': int(time.time() * 1000),
                  'replies': [{'id': a['id'], 'key': a.get('key', ''), 'title': a.get('title', ''), 'status': rp.get('status', 'done'), 'decision': rp.get('decision', ''), 'text': text} for a in sel],
                  'notes': [{'id': str(uuid.uuid4()), 'ts': int(time.time() * 1000), 'text': 'SIM: ' + text}]}
        r = _http(self.eoc_url + '/api/merge', 'POST', bundle)
        return {'ok': bool(r.get('ok', True)), 'via': 'reply', 'closed': r.get('replies_applied', len(sel)), 'matched': len(sel),
                'note': '' if sel else 'nothing was waiting UP that matched; the reply went to the notes log only'}

    def _after_target(self, it: dict):
        """The need an `after` item waits for: `<inject>` or `<inject>#<suffix>`, for the item's unit when it has one."""
        a = it.get('after') or {}
        inj, _, suffix = a.get('need', '').partition('#')
        for n in self.run['needs']:
            if n['inject'] != inj:
                continue
            if it.get('unit_id') and '@' in n['item'] and f"@{it['unit_id']}" not in n['item']:
                continue                     # a per-unit consequence of a per-unit need: the same unit; a stake-wide need serves every unit
            if suffix and not n['id'].split('#')[-1].startswith(suffix):
                continue
            if not suffix and '#' in n['id'] and n['kind'] != 'item':
                continue
            return n
        return None

    def _needs_tick(self, final: bool = False):
        """Read the EOC and update every need that has arisen; trigger `after` items; keep the score history."""
        try:
            acts = _http(self.eoc_url + '/api/actions', timeout=5)
            rows = _http(self.eoc_url + '/api/messages', timeout=5)
            inc = _http(self.eoc_url + '/api/incident', timeout=5)
        except Exception as e:
            with self.lock:
                self.run['needs_error'] = f'EOC not reachable: {e}'
            return
        acts = acts if isinstance(acts, list) else []
        msgs = []
        for r in rows if isinstance(rows, list) else []:
            try:
                d = json.loads(r.get('data_json') or '{}')
            except Exception:
                continue
            d['ts'] = r.get('received_ms') or d.get('ts') or 0
            d['type'] = (d.get('type') or r.get('type') or '').lower()
            msgs.append(d)
        now = self.elapsed()
        changed = []
        with self.lock:
            self.run.pop('needs_error', None)
            # SITREPs: the EOC keeps only the last time one was generated; remember each as a drill minute
            ls = int((inc or {}).get('lastSitrepTs') or 0)
            if ls and ls not in [x['ms'] for x in self.run.setdefault('sitreps', [])]:
                self.run['sitreps'].append({'ms': ls, 't': round(self.drill_minute(ls), 1)})
                self._log(f"SITREP generated at the EOC (T+{self.drill_minute(ls):.0f})")
            lr = int((inc or {}).get('lastRollupTs') or 0)
            if lr and lr not in [x['ms'] for x in self.run.setdefault('rollups_sent', [])]:
                self.run['rollups_sent'].append({'ms': lr, 't': round(self.drill_minute(lr), 1)})
            for n in self.run['needs']:
                if n.get('arose_t') is None:
                    if final and n['state'] == 'open':
                        n['state'] = 'waived'
                        n['evidence'] = 'the item never fired'
                    continue
                if n['state'] in ('met', 'late', 'waived', 'missed'):
                    # missed is final (set when the run ended): /results and /report refresh with a regular tick and
                    # must not turn the final score back into open / overdue (2026-11-02 walk). Reopen sets open.
                    continue
                before = n['state']
                if n['kind'] == 'report':
                    self._eval_report_need(n, msgs, now)
                else:
                    self._eval_item_need(n, acts, now)
                if final and n['state'] in ('open', 'overdue'):
                    n['state'] = 'missed'
                    n['evidence'] = (n.get('evidence') or 'nothing matching on the EOC') + ' · run ended'
                if n['state'] != before:
                    changed.append(n)
            # consequences: items waiting for a need to reach a state
            for it in self.run['items']:
                if it.get('status') != 'waiting':
                    continue
                n = self._after_target(it)
                if not n:
                    continue
                want = it['after'].get('is', 'met')
                hit = (want == 'met' and n['state'] in ('met', 'late')) or (want == 'overdue' and n['state'] in ('overdue', 'missed'))                     or (want == 'missed' and n['state'] == 'missed') or (want == 'late' and n['state'] == 'late')
                if hit:
                    it['t'] = round(now + it['after'].get('delay', 0), 1)
                    it['status'] = 'pending'
                    it['triggered'] = {'need': n['id'], 'state': n['state'], 'at': round(now, 1)}
                    self._log(f"{it['kind']} {it['inject']}{' ' + it['unit'] if it.get('unit') else ''} triggered: {n['label'][:60]} is {n['state']}"
                              + (f", fires at T+{it['t']:g}" if it['t'] > now else ''))
            sc = self.score()
            hist = self.run.setdefault('score_hist', [])
            if not hist or hist[-1]['t'] < now - 2 or changed or final:
                hist.append({'t': round(now, 1), 'met': sc['met'] + sc['late'], 'overdue': sc['overdue'] + sc['missed'], 'open': sc['open'], 'pct': sc['pct']})
                del hist[:-600]
            for n in changed:
                self._log(f"need {n['state'].upper()}: {n['label'][:70]}" + (f" ({n['evidence'][:80]})" if n.get('evidence') else ''))
        if changed or final:
            self.save()

    def _match_action(self, n: dict, acts: list):
        m = n.get('match') or {}
        arose_ms = int(n.get('arose_ms') or 0)
        if m.get('key'):
            return next((a for a in acts if a.get('key') == m['key']), None)
        if m.get('key_pref'):                        # an ICS message delivered by Winlink: its own work item first
            a = next((a for a in acts if a.get('key') == m['key_pref']), None)
            if a:
                return a
        unit = (m.get('unit') or '').strip().lower()
        agencies = [str(x).lower() for x in (m.get('agency') or []) if x]
        pool = [a for a in acts if (not m.get('cat') or a.get('cat') == m['cat']) and int(a.get('ts') or 0) >= arose_ms - 90000
                and (not unit or unit in (str(a.get('unit', '')) + ' ' + str(a.get('title', ''))).lower())
                and (not agencies or any(x in (str(a.get('title', '')) + ' ' + str(a.get('from', ''))).lower() for x in agencies))]
        if m.get('subject'):
            subj = [a for a in pool if m['subject'].lower() in str(a.get('title', '')).lower()]
            if subj:
                return subj[0]
        if m.get('title'):
            exact = [a for a in pool if a.get('title') == m['title']]
            if exact:
                return exact[0]
        if m.get('title_contains'):
            pool = [a for a in pool if m['title_contains'].lower() in str(a.get('title', '')).lower()]
        return pool[0] if pool else None

    def _eval_item_need(self, n: dict, acts: list, now: float):
        rule, t0 = n['rule'], float(n['arose_t'])
        a = self._match_action(n, acts)
        age = now - t0
        if not a:
            n['state'] = 'overdue' if age > float(rule.get('owner', 30)) else 'open'
            n['evidence'] = f"no matching work item on the EOC after {age:.0f} min" if age > 2 else ''
            return
        tm = n.setdefault('times', {})
        # never before the need arose: an item the EOC already had (a duplicate from an earlier run) would otherwise read T+0
        to_t = lambda ms: max(t0, self.drill_minute(ms))
        tm['appeared'] = round(to_t(int(a.get('ts') or 0)), 1)
        own = _log_minutes_abs(a, 'Owner:', to_t)
        if own is None and (a.get('owner') or '').strip():
            own = tm['appeared']
        done_states = rule.get('done_states') or ['done']
        done = None
        for st in done_states:
            m = _log_minutes_abs(a, 'Status: ' + {'open': 'open', 'progress': 'in work', 'up': 'waiting on the line above', 'done': 'done'}[st], to_t)
            if m is not None and (done is None or m < done):
                done = m
        if done is None and a.get('status') in done_states:
            done = round(to_t(int(a.get('updatedTs') or a.get('ts') or 0)), 1)
        if own is not None:
            tm['owner'] = round(own, 1)
        if done is not None:
            tm['done'] = round(done, 1)
        has_decision = bool(str(a.get('decision') or '').strip())
        n['action_id'] = a.get('id', '')
        n['owner'] = a.get('owner', '')
        lim_o, lim_d = float(rule.get('owner', 30)), float(rule.get('done', 120))
        parts = [f"appeared T+{tm['appeared']:.0f}"]
        late = False
        if own is not None:
            parts.append(f"owner {a.get('owner') or '?'} after {max(0, own - t0):.0f} min" + ('' if own - t0 <= lim_o else f' (limit {lim_o:g})'))
            late = late or own - t0 > lim_o
        else:
            parts.append('no owner' + (f' after {age:.0f} min (limit {lim_o:g})' if age > lim_o else ''))
        # UP is the EOC's part done (the decision comes back from the line above); DONE needs the decision written in
        satisfied = done is not None and a.get('status') in done_states and (not rule.get('decision') or has_decision or a.get('status') == 'up')
        if done is not None:
            parts.append(f"{'done' if a.get('status') == 'done' else 'sent up'} after {max(0, done - t0):.0f} min" + ('' if done - t0 <= lim_d else f' (limit {lim_d:g})'))
            late = late or done - t0 > lim_d
        if rule.get('decision') and a.get('status') != 'up':
            parts.append('decision recorded' if has_decision else 'no decision recorded')
        n['evidence'] = '; '.join(parts)
        if satisfied:
            n['state'] = 'late' if late else 'met'
            n['met_t'] = round(now, 1)
        elif (own is None and age > lim_o) or age > lim_d:
            n['state'] = 'overdue'
        else:
            n['state'] = 'open'

    def _eval_report_need(self, n: dict, msgs: list, now: float):
        rule, t0 = n['rule'], float(n['arose_t'])
        form, unit = n['match'].get('form'), (n['match'].get('unit') or '').strip().lower()
        arose_ms = int(n.get('arose_ms') or 0)
        found = None
        for d in msgs:
            if d.get('type') != form or int(d.get('ts') or 0) < arose_ms - 60000:
                continue
            sub = d.get(form) or {}
            hay = ' '.join(str(sub.get(k, '')) for k in ('ward', 'stake', 'contact', 'chief_ward', 'location')).lower()
            if unit and unit not in hay:
                continue
            if (d.get('fields') or {}).get('sim_run') == self.run['id'] or str(d.get('from', '')).startswith('SIM-'):
                continue                     # delivered by the simulator itself, not typed in by a person
            found = d
            break
        age = now - t0
        lim = float(rule.get('typed', 25))
        if not found:
            n['state'] = 'overdue' if age > lim else 'open'
            n['evidence'] = f"not on the EOC after {age:.0f} min (limit {lim:g})" if age > lim else ''
            return
        typed = round(self.drill_minute(int(found.get('ts') or 0)), 1)
        n.setdefault('times', {})['typed'] = typed
        acc = compare_truth(n.get('truth') or {}, found.get(form) or {})
        n['accuracy'] = acc
        n['message_id'] = found.get('id', '')
        n['evidence'] = f"typed in after {max(0, typed - t0):.0f} min" + ('' if typed - t0 <= lim else f' (limit {lim:g})')             + f"; {acc['matched']} of {acc['total']} fields match the card" + ('' if not acc['wrong'] else ': ' + '; '.join(acc['wrong'][:4]))
        n['state'] = 'met' if typed - t0 <= lim and acc['score'] >= 0.8 else 'late'
        n['met_t'] = round(now, 1)

    def score(self) -> dict:
        """The scoreboard: needs by state and category, timings, reports, SITREPs, the done checks."""
        needs = [n for n in self.run['needs'] if n.get('arose_t') is not None and n['state'] != 'waived']
        c = {st: sum(1 for n in needs if n['state'] == st) for st in NEED_STATES}
        by_cat = {}
        for n in needs:
            d = by_cat.setdefault(n['cat'], {'total': 0, 'met': 0, 'late': 0, 'overdue': 0, 'open': 0, 'missed': 0})
            d['total'] += 1
            d[n['state']] = d.get(n['state'], 0) + 1
        # an open need still inside its time is not scored yet: right after GO the room would otherwise read
        # "0 % overwhelmed" before anyone could act (the final tick turns what is still open into missed)
        total = c['met'] + c['late'] + c['overdue'] + c['missed'] + c['open']
        scored = total - c['open']
        pct = round(100 * (c['met'] + 0.5 * c['late']) / scored) if scored else None
        own = sorted(n['times']['owner'] - n['arose_t'] for n in needs if n.get('times', {}).get('owner') is not None)
        done = sorted(n['times']['done'] - n['arose_t'] for n in needs if n.get('times', {}).get('done') is not None)
        med = lambda xs: round(xs[len(xs) // 2], 1) if xs else None
        forms = [i for i in self.run['items'] if i['kind'] == 'form' and i.get('local', True) and not i.get('rollup')]
        fired = [i for i in forms if i['status'] == 'fired']
        typed = [n for n in needs if n['kind'] == 'report']
        acc = [n['accuracy']['score'] for n in typed if n.get('accuracy')]
        # high-priority needs nobody owned: still open or overdue, or ended MISSED without an owner ever being set
        high_open = [n for n in needs if n['prio'] == 1 and not (n.get('owner') or '').strip()
                     and (n['state'] in ('open', 'overdue') or (n['state'] == 'missed' and (n.get('times') or {}).get('owner') is None))]
        hist = self.run.get('score_hist') or []
        now = self.elapsed()
        past = [h for h in hist if h['t'] <= now - 10]
        trend = ''
        if past and hist:
            dv = (c['overdue'] + c['missed']) - past[-1]['overdue']
            trend = 'worse' if dv > 0 else ('better' if dv < 0 else 'steady')
        label = '' if pct is None else ('strong' if pct >= 85 else 'steady' if pct >= 65 else 'struggling' if pct >= 40 else 'overwhelmed')
        checks = []
        for ck in (self.run.get('done') or {}).get('checks') or []:
            ok, why = self._done_check(ck, c, pct, high_open)
            checks.append({'id': ck.get('id', ''), 'label': ck.get('label', ''), 'ok': ok, 'why': why})
        return {'total': total, 'scored': scored, 'met': c['met'], 'late': c['late'], 'overdue': c['overdue'], 'open': c['open'], 'missed': c['missed'], 'pct': pct, 'label': label,
                'trend': trend, 'by_cat': by_cat, 'median_owner_min': med(own), 'median_done_min': med(done),
                'reports': {'expected': len(forms), 'sent': len(fired), 'typed': len(typed), 'typed_ok': sum(1 for n in typed if n['state'] in ('met', 'late'))},
                'accuracy': round(100 * sum(acc) / len(acc)) if acc else None, 'high_unowned': len(high_open),
                'sitreps': [x['t'] for x in self.run.get('sitreps') or []], 'checks': checks, 'eoc_error': self.run.get('needs_error', '')}

    def _done_check(self, ck: dict, c: dict, pct, high_open: list):
        if ck.get('sitrep'):
            ts = [x['t'] for x in self.run.get('sitreps') or []]
            n = int(ck['sitrep'])
            if len(ts) >= n:
                ok = ts[n - 1] <= float(ck.get('by', 1e9))
                return ok, f"SITREP #{n} at T+{ts[n - 1]:.0f}" + ('' if ok else f" (wanted by T+{ck['by']:g})")
            if self.elapsed() < float(ck.get('by', 1e9)):
                return None, f"SITREP #{n} not generated yet (due T+{ck.get('by', 0):g})"
            return False, f'SITREP #{n} not generated by T+{ck.get("by", 0):g}'
        if ck.get('no_unowned_high'):
            return not high_open, 'every high-priority need has an owner' if not high_open else f'{len(high_open)} high-priority need(s) without an owner'
        if ck.get('pct_min') is not None:
            ok = pct is not None and pct >= float(ck['pct_min'])
            return ok, f"{pct if pct is not None else '—'}% of needs met (wanted {ck['pct_min']:g}%)"
        if ck.get('cat_met'):
            d = {}
            for n in self.run['needs']:
                if n['cat'] == ck['cat_met'] and n.get('arose_t') is not None and n['state'] != 'waived':
                    d[n['state']] = d.get(n['state'], 0) + 1
            tot = sum(d.values())
            ok = tot > 0 and d.get('met', 0) + d.get('late', 0) == tot
            return ok, f"{d.get('met', 0) + d.get('late', 0)} of {tot} {ck['cat_met']} needs met"
        if ck.get('need_met'):
            # the needs of one inject (every unit it expanded to): all met or met late; pending until they arise
            ns = [n for n in self.run['needs'] if n['inject'] == ck['need_met'] and n['state'] != 'waived']
            arisen = [n for n in ns if n.get('arose_t') is not None]
            if not ns:
                return None, f"not in this run: {ck['need_met']} reaches no unit this EOC plays (not applicable)"
            if not arisen:
                return None, f"{ck['need_met']} has not fired yet"
            good = [n for n in arisen if n['state'] in ('met', 'late')]
            bad = [n for n in arisen if n['state'] in ('overdue', 'missed')]
            if bad:
                return False, f"{len(bad)} of {len(arisen)} {ck['need_met']} need(s) overdue or missed"
            if len(good) == len(arisen):
                return True, f"{len(good)} of {len(arisen)} {ck['need_met']} need(s) met" + (' (late)' if any(n['state'] == 'late' for n in good) else '')
            return None, f"{len(good)} of {len(arisen)} {ck['need_met']} need(s) met so far"
        return False, 'unknown check'

    def score_brief(self) -> dict:
        try:
            sc = self.score()
        except Exception:
            return {}
        return {k: sc[k] for k in ('total', 'met', 'late', 'overdue', 'open', 'missed', 'pct', 'label', 'trend', 'high_unowned')}

    def report(self) -> dict:
        """The after-action report as data: header, scoreboard, timeline, needs, hot wash, do-better list."""
        with self.lock:
            run = copy.deepcopy(self.run)
        sc = self.score()
        needs = [n for n in run['needs'] if n.get('arose_t') is not None and n['state'] != 'waived']
        needs.sort(key=lambda n: (n['arose_t'], n['id']))
        timeline = []
        for e in run.get('log', []):
            txt = e['text']
            if txt.startswith(('PACE ', 'Run ', 'SITREP ', 'need ', 'Clock set')) or 'triggered' in txt or txt.startswith('reply '):
                timeline.append({'t': e['t'], 'wall': e['wall'], 'text': txt})
        better, well = [], []
        for n in needs:
            role, cat = n.get('role') or NEED_ROLE.get(n['cat'], ''), n['cat']
            if n['state'] in ('met',):
                well.append({'role': role, 'text': f"{n['label'][:90]}: {n['evidence']}"})
                continue
            fails = []
            tm, rule, t0 = n.get('times', {}), n['rule'], n['arose_t']
            if n['kind'] == 'report':
                if tm.get('typed') is None or tm['typed'] - t0 > float(rule.get('typed', 25)):
                    fails.append('typed')
                if n.get('accuracy') and n['accuracy']['score'] < 1:
                    fails.append('accuracy')
            else:
                if tm.get('owner') is None or tm['owner'] - t0 > float(rule.get('owner', 30)):
                    fails.append('owner')
                if tm.get('done') is None or tm['done'] - t0 > float(rule.get('done', 120)):
                    fails.append('done')
                if rule.get('decision') and 'no decision' in (n.get('evidence') or ''):
                    fails.append('decision')
            coach = []
            for f in fails or ['done']:
                line = NEED_COACH.get((cat, f)) or NEED_COACH.get(('other', f)) or NEED_COACH[('other', 'done')]
                if line not in coach:
                    coach.append(line)
            better.append({'role': role, 'cat': cat, 'state': n['state'], 'need': n['label'][:90], 'what': n['evidence'] or 'nothing matching on the EOC',
                           'coach': ' '.join(coach), 'fails': fails})
        by_role = {}
        for b in better:
            by_role.setdefault(b['role'], []).append(b)
        # why it matters: the real-disaster lesson behind each need's inject (need id = need:<item id>[#part])
        items_by_id = {it['id']: it for it in run['items']}
        why, seen_lessons = [], set()
        for n in needs:
            it = items_by_id.get(n['id'][5:].split('#')[0])
            if it and it.get('lesson') and it['lesson'] not in seen_lessons:
                seen_lessons.add(it['lesson'])
                why.append({'state': n['state'], 'need': n['label'][:90], 'lesson': it['lesson'], 'role': n.get('role') or NEED_ROLE.get(n['cat'], '')})
        hw = [{'t': h.get('t', 0), 'check': h['check'], 'result': h.get('result', ''), 'note': h.get('note', ''), 'evidence': h.get('evidence', ''), 'suggest': h.get('suggest', '')} for h in run.get('hotwash', [])]
        segs = run['clock'].get('segments') or []
        speeds = sorted({s['speed'] for s in segs if s['speed']})
        return {'run': {'id': run['id'], 'created': run['created'], 'scenario': run['scenario'], 'eoc': run['eoc'], 'site': run.get('site', {}), 'privacy': run['pack']['privacy'],
                        'consent': run['pack'].get('consent') or None,
                        'status': run['clock']['status'], 'elapsed_min': round(self.elapsed(), 1), 'duration_min': run['clock']['duration_min'], 'speeds': speeds,
                        'units': len(run['scope']['units']), 'seed': run['seed'], 'generated': _dt.datetime.now().isoformat(timespec='seconds')},
                'score': sc, 'timeline': timeline, 'needs': needs, 'hotwash': hw, 'better': better, 'better_by_role': by_role, 'well': well,
                'why': why, 'phases': run.get('phases', []), 'pace': run['pace'], 'items': counts(run)}

    def _fire_rollup(self, it: dict) -> dict:
        """Bundle the reports of one simulated stake that are due by now into a church_eoc_rollup
        and merge it into the Council / Area EOC, the way a Stake EOC's roll-up arrives."""
        now_t = self.elapsed()
        with self.lock:
            parts = [x for x in self.run['items'] if x.get('rollup') and x.get('stake_id', '') in ('', it.get('stake_id'))
                     and x['stake'] == it['stake'] and x['status'] == 'pending' and x['t'] <= max(now_t, it['t'])]
            bundle = rollup_bundle(self.run, it, parts, now_t)
        if not parts:
            return {'ok': True, 'via': 'rollup', 'records': 0, 'note': 'nothing due from this stake yet'}
        drop = Path(self.drop_dir) if self.drop_dir else None
        if drop and drop.is_dir():
            # The real path: a file in the Area EOC's Drop Folder, ingested by its watcher within
            # ten seconds and moved to Ingested\, the way an emailed roll-up arrives.
            tag = re.sub(r'[^A-Za-z0-9]+', '_', it['stake']).strip('_')[:40]
            p = drop / f"church_eoc_rollup_{tag}_SIM_{it['inject']}_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            atomic_write(p, '\ufeff' + json.dumps(bundle, ensure_ascii=False, indent=1))
            res = {'ok': True, 'via': 'rollup drop', 'records': len(parts), 'file': str(p)}
        else:
            r = _http(self.eoc_url + '/api/merge', 'POST', bundle)
            res = {'ok': bool(r.get('ok', True)), 'via': 'rollup merge', 'records': len(parts), 'new': r.get('new'), 'dup': r.get('dup'),
                   'actions_new': r.get('actions_new'), 'note': 'Drop Folder not reachable from this laptop: merged directly'}
        with self.lock:
            for x in parts:
                x['status'] = 'fired'
                x['result'] = {'ok': True, 'via': res['via'], 'bundle': it['id']}
                x['fired_wall'] = _dt.datetime.now().strftime('%H:%M:%S')
                x['fired_t'] = round(now_t, 1)
        return res

    def _loop(self):
        while not self._stop.is_set():
            if self.run['clock']['status'] == 'running':
                now = self.elapsed()
                # the scenario's PACE timeline: push each step to the EOC the moment it comes into force
                lvl = pace_at(self.run['pace'], now)
                if lvl != self.run['clock'].get('pace_pushed'):
                    self._push_pace(lvl, 'scenario timeline' if self.run['clock'].get('pace_pushed') else 'at the start')
                    self.save()
                due =[it['id'] for it in self.run['items'] if it['status'] == 'pending' and it['t'] <= now and it.get('local', True) and not it.get('rollup')]
                for iid in due:
                    if self._stop.is_set() or self.run['clock']['status'] != 'running':
                        break
                    self.fire(iid)
                    time.sleep(0.2)              # a little spacing, as real traffic has
                    lvl = pace_at(self.run['pace'], self.elapsed())   # a long backlog (after a jump) must not hold back a PACE step
                    if lvl != self.run['clock'].get('pace_pushed'):
                        self._push_pace(lvl, 'scenario timeline')
                        self.save()
                if time.time() - getattr(self, '_saved_wall', 0) >= 30:
                    self._saved_wall = time.time()
                    self.save()
                if time.time() - self._tick_wall >= self.TICK_SEC or due:
                    self._tick_wall = time.time()
                    try:
                        self._needs_tick()
                    except Exception as e:
                        self._log(f'needs check failed: {type(e).__name__}: {e}')
                if now >= self.run['clock']['duration_min'] and not due:
                    with self.lock:
                        if all(it['status'] != 'pending' for it in self.run['items']):
                            self.run['clock']['elapsed_min'] = now
                            self.run['clock']['started_wall'] = None
                            self.run['clock']['status'] = 'finished'
                            self._log('Run finished')
                    try:
                        self._needs_tick(final=True)
                        self._log(f"Final score: {self.score_brief().get('pct')}% of needs met")
                        self.write_report()
                    except Exception as e:
                        self._log(f'final score failed: {type(e).__name__}: {e}')
                    self.save()
            time.sleep(1.0)

    TICK_SEC = 4.0

    def write_report(self):
        """Save the after-action report beside the run file (text and HTML)."""
        rep = self.report()
        base = self.runs_dir / f"run-{self.run['id']}"
        pathlib_write(base.with_name(base.name + '-report.txt'), report_text(rep))
        pathlib_write(base.with_name(base.name + '-report.html'), report_html(rep))
        return rep


_EOC_MOD = None


def _eoc_module():
    """The EOC server's own mapping code (Worker payload -> filed record, derived work items), so a
    simulated roll-up has exactly the shape a real one has."""
    global _EOC_MOD
    if _EOC_MOD is None:
        import contextlib
        import importlib.util
        import io
        here = Path(__file__).resolve().parent
        # repo: simulation/ beside eoc/; installed: EOC Message Center\simulation\ under the server
        cands = [here.parent / 'eoc' / 'eoc_server.py', here.parent / 'eoc_server.py', here / 'eoc_server.py']
        p = next((c for c in cands if c.is_file()), cands[0])
        spec = importlib.util.spec_from_file_location('eoc_server_for_sim', p)
        mod = importlib.util.module_from_spec(spec)
        with contextlib.redirect_stdout(io.StringIO()):
            spec.loader.exec_module(mod)
        _EOC_MOD = mod
    return _EOC_MOD


def rollup_bundle(run: dict, it: dict, parts: list, now_t: float) -> dict:
    """A church_eoc_rollup from one simulated Stake EOC: its due reports as filed records (summary
    fields only, like a real roll-up), its roster, a note, and the work items waiting on the line above."""
    eoc = _eoc_module()
    speed = float(run['clock'].get('speed') or 1)
    now_ms = int(time.time() * 1000)
    frm = f"{it['stake']} EOC (simulated)"
    msgs, roster, actions = [], {}, []
    for x in parts:
        ft = x['form'].upper()
        ts = int(now_ms - max(0.0, now_t - x['t']) * 60000 / speed)
        rec = {'id': str(uuid.uuid5(uuid.NAMESPACE_URL, f"sim-rollup:{run['id']}:{x['id']}")), 'type': x['form'], 'ts': ts,
               'filename': FORM_FILENAMES[x['form']], 'source': 'sim', 'dupKey': 'sim:' + x['id'], 'origin': frm, 'status': 'new',
               x['form']: eoc._map_worker_to_eoc(ft, x['payload'])}
        msgs.append(rec)
        roster.setdefault(x['unit_id'], {'id': 'sim-' + x['unit_id'], 'name': x['unit'], 'status': 'reported', 'lastTs': ts})
        for a in eoc._derive_actions(rec):
            if a.get('cat') in ('upward', 'supply'):
                actions.append(dict(a, id=str(uuid.uuid5(uuid.NAMESPACE_URL, 'sim-action:' + a['key'])), ts=ts, status='up', owner='', unit=x['unit'],
                                    decision='', due='', next=a.get('next', ''), log=[{'ts': ts, 'who': 'SIM', 'text': f'Status: up (sent with the roll-up from {frm})'}]))
    return {'kind': 'church_eoc_rollup', 'v': 1, 'sim': True,
            'from': {'name': frm, 'level': 'stake', 'op': 'SIM', 'units': ', '.join(r['name'] for r in roster.values())},
            'to': run['eoc'].get('name') or 'Council / Area EOC', 'incident': {'name': 'SIMULATED ' + run['scenario']['name'], 'type': run['scenario'].get('hazard', '')},
            'exportedAt': now_ms, 'since': 0, 'msgs': msgs, 'roster': list(roster.values()),
            'notes': [{'id': str(uuid.uuid4()), 'ts': now_ms, 'text': f"SIM: {it.get('text') or 'SITREP roll-up'} - {len(msgs)} report(s), {len(actions)} item(s) waiting on this EOC"}],
            'actions': actions}


def _log_minutes_abs(a: dict, prefix: str, to_t):
    """The drill minute of the item's first log line starting with `prefix`, or None."""
    for l in a.get('log') or []:
        if str(l.get('text', '')).startswith(prefix):
            return to_t(int(l.get('ts') or 0))
    return None


def pathlib_write(path, text: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, text)


def atomic_write(path, data):
    """Write a file so that a reader never sees it half written: into '<name>.<random>.tmp' in the same folder (the
    EOC's Winlink and Drop Folder watchers only pick up .mime, .txt and .json), then renamed over the target in one step."""
    path = Path(path)
    tmp = path.with_name(f'{path.name}.{uuid.uuid4().hex[:6]}.tmp')
    try:
        if isinstance(data, bytes):
            tmp.write_bytes(data)
        else:
            tmp.write_text(data, encoding='utf-8')
        for attempt in range(20):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                # Windows: a reader has the target open (a session listing, an antivirus scan); try again shortly
                if attempt == 19:
                    raise
                time.sleep(0.05)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def _log_minutes(a: dict, prefix: str, to_t=None):
    """Minutes from the item's creation to its first log line starting with `prefix`, or None:
    drill minutes when `to_t` (a wall-ms -> drill-minute map) is given, else wall minutes."""
    for l in a.get('log') or []:
        if str(l.get('text', '')).startswith(prefix):
            t0, t1 = int(a.get('ts') or 0), int(l.get('ts') or 0)
            return max(0.0, to_t(t1) - to_t(t0)) if to_t else max(0.0, (t1 - t0) / 60000)
    return None


def evaluate_rule(rule: dict, acts: list, speed: float = 1.0, to_t=None):
    """One hot-wash `auto` rule against the EOC's work items. Returns (evidence text, suggestion).
    rule = {"items": {"cat": "missionaries" | ["life", ...], "key_prefix": "sim:wi-x", "title_contains": "..."},
            "expect": {"min_count": 1, "max_count": 1, "owner_within_min": 10, "done_within_min": 30, "status_in": ["up", "done"],
                       "decision": true, "no_unowned_high": true}}
    `max_count` catches duplicates: the same household or shelter raised as two open items.
    Minutes come from the run's clock segments (`to_t`, exact across speed changes, pauses and
    jumps); without a map, wall-clock minutes are multiplied by `speed`."""
    flt = rule.get('items') or {}
    exp = rule.get('expect') or {}
    cats = flt.get('cat')
    if isinstance(cats, str):
        cats = [cats]
    sel = []
    for a in acts:
        if cats and a.get('cat') not in cats:
            continue
        if flt.get('key_prefix') and not str(a.get('key', '')).startswith(flt['key_prefix']):
            continue
        if flt.get('title_contains') and flt['title_contains'].lower() not in str(a.get('title', '')).lower():
            continue
        sel.append(a)
    ok = True
    lines = []
    label = lambda a: (a.get('title') or '?')[:60]
    if exp.get('min_count') and len(sel) < int(exp['min_count']):
        ok = False
        lines.append(f'only {len(sel)} matching work item(s) on file (expected at least {exp["min_count"]})')
    elif not sel and exp and not exp.get('no_unowned_high'):
        ok = False
        lines.append('no matching work item on file')
    else:
        lines.append(f'{len(sel)} matching work item(s)')
    if exp.get('max_count') is not None and len(sel) > int(exp['max_count']):
        ok = False
        lines.append(f'{len(sel)} matching work items where at most {exp["max_count"]} belong (duplicates: ' + ', '.join(label(a) for a in sel) + ')')
    if 'owner_within_min' in exp:
        lim = float(exp['owner_within_min'])
        for a in sel:
            m = _log_minutes(a, 'Owner:', to_t)
            if m is None:
                ok = False
                lines.append(f'{label(a)}: never given an owner' if not (a.get('owner') or '').strip() else f'{label(a)}: owner set (time not logged)')
            else:
                dm = m if to_t else m * speed
                good = dm <= lim
                ok = ok and good
                lines.append(f'{label(a)}: owner {a.get("owner") or "?"} after {dm:.0f} drill min' + ('' if good else f' (limit {lim:g})'))
    if 'done_within_min' in exp:
        lim = float(exp['done_within_min'])
        for a in sel:
            m = _log_minutes(a, 'Status: done', to_t)
            if m is None:
                ok = False
                lines.append(f'{label(a)}: not done')
            else:
                dm = m if to_t else m * speed
                good = dm <= lim
                ok = ok and good
                lines.append(f'{label(a)}: done after {dm:.0f} drill min' + ('' if good else f' (limit {lim:g})'))
    if exp.get('status_in'):
        allowed = exp['status_in'] if isinstance(exp['status_in'], list) else [exp['status_in']]
        bad = [a for a in sel if a.get('status') not in allowed]
        if bad:
            ok = False
            lines.append('not ' + ' / '.join(allowed) + ': ' + ', '.join(f'{label(a)} ({a.get("status")})' for a in bad))
        elif sel:
            lines.append('all ' + ' / '.join(allowed))
    if exp.get('decision'):
        bad = [a for a in sel if not str(a.get('decision') or '').strip()]
        if bad:
            ok = False
            lines.append('no decision recorded: ' + ', '.join(label(a) for a in bad))
        elif sel:
            lines.append('decision recorded on each')
    if exp.get('no_unowned_high'):
        bad = [a for a in acts if a.get('status') != 'done' and int(a.get('prio') or 2) == 1 and not str(a.get('owner') or '').strip()]
        if bad:
            ok = False
            lines.append('high-priority items open with no owner: ' + ', '.join(label(a) for a in bad))
        else:
            lines.append('every open high-priority item has an owner')
    return '; '.join(lines), ('✓' if ok else '✗')


STATE_WORD = {'open': 'open', 'met': 'met', 'late': 'met late', 'overdue': 'OVERDUE', 'missed': 'MISSED', 'waived': 'not played'}


def _fmt_t(m) -> str:
    try:
        m = float(m)
    except (TypeError, ValueError):
        return '—'
    s = max(0, int(round(m * 60)))
    return f'T+{s // 60:03d}:{s % 60:02d}'   # drill minutes:seconds, as the controller page shows them


def consent_line(c) -> str:
    """' (consent: <who>, <role>, <date>; recorded by <name>)' for a real-contact run, else ''."""
    if not c or not isinstance(c, dict):
        return ''
    return f" (consent: {c.get('by', '')}, {c.get('role', 'Stake President')}, {c.get('date', '')}; recorded by {c.get('recordedBy', '')})"


TITLES = ('Bishop', 'President', 'Brother', 'Sister', 'Elder', 'Chief', 'Director', 'Specialist')


def redact_text(text: str, packs: list) -> str:
    """A report text for a feedback issue that may be public: every unit, building, stake, council and place name of
    the pack(s) becomes "Unit 1", "Building 1", "Stake 1", "Council 1", "City 1" (the same number everywhere in the
    text); a leader's full name becomes the first name only (pseudonymized first names are invented, last names are
    real); emails, phone numbers and the units' simulated Winlink addresses are replaced. Numbers follow the first
    pack's order, so the same unit gets the same number in every redacted report of that pack."""
    names = {}

    def add(value, label):
        v = ' '.join(str(value or '').split())
        if len(v) >= 3 and v not in names:
            names[v] = label

    counters = {}

    def numbered(kind, key, value, seen):
        if not value:
            return
        k = (kind, key)
        if k not in seen:
            counters[kind] = counters.get(kind, 0) + 1
            seen[k] = f'{kind} {counters[kind]}'
        add(value, seen[k])

    seen = {}
    for pack in packs:
        for u in pack.get('units', []):
            numbered('Unit', u['id'], u.get('name'), seen)
        for s in pack.get('stakes', []):
            numbered('Stake', s['id'], s.get('name'), seen)
            numbered('Building', s.get('center_building') or ('stake:' + s['id']), s.get('center_name'), seen)
        for c in pack.get('councils', []):
            numbered('Council', c['id'], c.get('name'), seen)
        for b in pack.get('buildings', []):
            numbered('Building', b['id'], b.get('name'), seen)
            numbered('Building', b['id'], (b.get('street') or (b.get('address') or '').split(',')[0]), seen)
            numbered('Building', b['id'], b.get('address'), seen)
        for u in pack.get('units', []):
            numbered('Building', u.get('building') or ('unit:' + u['id']), u.get('building_name'), seen)
        w = pack.get('welfare') or {}
        for k in ('region', 'area_office', 'area'):
            if (w.get(k) or {}).get('name'):
                add(w[k]['name'], {'region': 'the welfare region', 'area_office': 'the area office', 'area': 'the Area'}[k])
        for x in pack.get('units', []) + pack.get('stakes', []) + pack.get('buildings', []):
            if x.get('city'):
                numbered('City', x['city'].lower(), x['city'], seen)
        for c in pack.get('contacts', []):
            first, last = (c.get('first') or '').strip(), (c.get('last') or '').strip()
            if last:
                if c.get('name'):
                    add(c['name'], first or 'a leader')
                if first:
                    add(f'{first} {last}', first)
                for title in TITLES:
                    add(f'{title} {last}', title)
    if names:
        rx = re.compile(r'(?<![\w])(' + '|'.join(re.escape(k) for k in sorted(names, key=len, reverse=True)) + r')(?![\w])')
        text = rx.sub(lambda m: names[m.group(1)], text)
    text = re.sub(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+', '[email]', text)
    text = re.sub(r'(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)', '[phone]', text)
    text = re.sub(r'\bSIM-[A-Z0-9]+\b', 'SIM-UNIT', text)
    lines = text.split('\n')
    if lines:
        lines[0] += ' (units redacted)'
    return '\n'.join(lines)


def report_text(rep: dict) -> str:
    """The after-action report as plain text (for the drill-feedback issue and the printed hot wash)."""
    r, sc = rep['run'], rep['score']
    L = [f"EMCOMM DRILL AFTER-ACTION REPORT - {r['scenario']['name']}",
         f"Run {r['id']} - planned {r['created']} - report {r['generated']} - privacy: {r['privacy']}" + consent_line(r.get('consent')),
         f"EOC: {r['eoc'].get('name', '')} ({r['eoc'].get('level', '')}) - plays {r['site'].get('label', '')} - {r['units']} units - seed {r['seed']}",
         f"Clock: {r['status']} at {_fmt_t(r['elapsed_min'])} of {r['duration_min']:g} drill minutes - speeds used: {', '.join(f'{x:g}x' for x in r['speeds']) or '-'}", '',
         'SCOREBOARD',
         f"  Needs met: {sc['met']} on time, {sc['late']} late, {sc['overdue']} overdue, {sc['missed']} missed, {sc['open']} still open  ->  {sc['pct'] if sc['pct'] is not None else '-'}% ({sc['label'] or 'no needs yet'})",
         f"  Median minutes to an owner: {sc['median_owner_min'] if sc['median_owner_min'] is not None else '-'} - to done: {sc['median_done_min'] if sc['median_done_min'] is not None else '-'}",
         f"  Reports: {sc['reports']['sent']} of {sc['reports']['expected']} sent by the simulator; {sc['reports']['typed_ok']} of {sc['reports']['typed']} hand-outs typed in"
         + (f" - accuracy {sc['accuracy']}%" if sc['accuracy'] is not None else ''),
         f"  SITREPs generated: {', '.join(_fmt_t(t) for t in sc['sitreps']) or 'none'}",
         f"  High-priority needs without an owner: {sc['high_unowned']}"]
    for cat, d in sorted(sc['by_cat'].items()):
        L.append(f"  {cat:13s} {d.get('met', 0) + d.get('late', 0)} of {d['total']} met" + (f" ({d.get('late', 0)} late)" if d.get('late') else '') + (f", {d.get('overdue', 0) + d.get('missed', 0)} overdue or missed" if d.get('overdue') or d.get('missed') else ''))
    if sc['checks']:
        L += ['', 'DONE WHEN'] + [f"  [{'x' if c['ok'] else '-' if c['ok'] is None else ' '}] {c['label']} - {c['why']}" for c in sc['checks']]
    L += ['', 'DO BETTER (by role)']
    if not rep['better']:
        L.append('  Nothing missed: every need that arose was met on time.')
    for role, items in rep['better_by_role'].items():
        L.append(f'  {role}:')
        for b in items:
            L.append(f"    - {b['need']} [{STATE_WORD.get(b['state'], b['state'])}]: {b['what']}")
            L.append(f"      => {b['coach']}")
    L += ['', 'WENT WELL'] + ([f"  - {w['text']}" for w in rep['well'][:25]] or ['  (nothing met on time yet)'])
    L += ['', 'NEEDS LEDGER']
    for n in rep['needs']:
        tm = n.get('times', {})
        L.append(f"  {_fmt_t(n['arose_t'])} [{STATE_WORD.get(n['state'], n['state'])}] {n['label'][:90]}" + (f" ({n['unit']})" if n.get('unit') and n['unit'] not in n['label'] else ''))
        if n.get('evidence'):
            L.append(f"      {n['evidence']}")
    L += ['', 'HOT WASH'] + [f"  [{h['result'] or ' '}] {_fmt_t(h['t'])} {h['check']}" + (f"  -- {h['note']}" if h['note'] else '') + (f"\n      evidence ({h['suggest']}): {h['evidence']}" if h['evidence'] else '') for h in rep['hotwash']]
    L += ['', 'TIMELINE'] + [f"  {e['wall']} {_fmt_t(e['t'])}  {e['text']}" for e in rep['timeline']]
    L += ['', 'PACE'] + [f"  {_fmt_t(s['t'])} {s['level']}  {s.get('why', '')}" for s in rep['pace']]
    return '\n'.join(L) + '\n'


def report_html(rep: dict) -> str:
    """The after-action report as a self-contained printable page (no external resources)."""
    import html as _h
    e = lambda x: _h.escape(str(x if x is not None else ''))
    r, sc = rep['run'], rep['score']
    col = {'met': '#1f8a4c', 'late': '#b7791f', 'overdue': '#b03a2e', 'missed': '#7a1f16', 'open': '#5b6b7a', 'waived': '#9aa5b1'}
    pct = sc['pct']
    tiles = [('Needs met', f"{sc['met'] + sc['late']}<small>/{sc['total']}</small>", f"{sc['met']} on time · {sc['late']} late"),
             ('Overdue or missed', str(sc['overdue'] + sc['missed']), f"{sc['open']} still open"),
             ('Score', f"{pct if pct is not None else '—'}<small>%</small>", sc['label'] or 'no needs arose'),
             ('Minutes to an owner', str(sc['median_owner_min'] if sc['median_owner_min'] is not None else '—'), 'median, drill minutes'),
             ('Reports', f"{sc['reports']['sent']}<small>/{sc['reports']['expected']}</small>", f"{sc['reports']['typed_ok']} of {sc['reports']['typed']} hand-outs typed" + (f" · {sc['accuracy']}% accurate" if sc['accuracy'] is not None else '')),
             ('SITREPs', str(len(sc['sitreps'])), ', '.join(_fmt_t(t) for t in sc['sitreps']) or 'none generated')]
    H = [f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>After-action report · {e(r['scenario']['name'])}</title><style>",
         "body{font:14px/1.45 -apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#1d2a36;margin:0;padding:24px;max-width:1000px}h1{font-size:22px;margin:0 0 4px}h2{font-size:15px;text-transform:uppercase;letter-spacing:.05em;color:#5b6b7a;margin:26px 0 8px;border-bottom:1px solid #d5dde5;padding-bottom:4px}",
         ".sub{color:#5b6b7a;font-size:13px}.tiles{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin:14px 0}.tile{border:1px solid #d5dde5;border-radius:8px;padding:10px 12px}.tile .k{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:#5b6b7a}.tile .v{font-size:30px;font-weight:700;line-height:1.1}.tile .v small{font-size:15px;color:#5b6b7a;font-weight:600}.tile .s{font-size:11px;color:#5b6b7a}",
         ".st{display:inline-block;font-size:11px;font-weight:700;color:#fff;border-radius:4px;padding:0 6px;min-width:52px;text-align:center}table{border-collapse:collapse;width:100%;font-size:13px}td,th{text-align:left;vertical-align:top;padding:4px 6px;border-top:1px solid #e3e8ee}th{color:#5b6b7a;font-size:11px;text-transform:uppercase}",
         ".coach{background:#fff8ec;border-left:3px solid #e67800;padding:6px 10px;margin:6px 0}.well{background:#e3f5ea;border-left:3px solid #1f8a4c;padding:4px 10px;margin:4px 0}.mono{font-family:ui-monospace,Consolas,monospace;font-size:12px;white-space:pre-wrap}.chk{list-style:none;padding:0}.chk li{padding:2px 0}",
         "@media print{body{padding:0}h2{break-after:avoid}}.bar{height:10px;border-radius:5px;background:#eceff2;overflow:hidden;display:flex}.bar i{display:block;height:100%}</style></head><body>",
         f"<h1>After-action report · {e(r['scenario']['name'])}</h1><div class='sub'>EMCOMM drill · {e(r['eoc'].get('name', ''))} plays <b>{e(r['site'].get('label', ''))}</b> · {r['units']} units · run {e(r['id'])} · seed {r['seed']} · privacy {e(r['privacy'])}{e(consent_line(r.get('consent')))} · clock {e(r['status'])} at {_fmt_t(r['elapsed_min'])} of {_fmt_t(r['duration_min'])} · speeds {', '.join(f'{x:g}×' for x in r['speeds']) or '—'} · report {e(r['generated'])}</div>",
         "<div class='sub'>Independent volunteer project, not an official Church product. Every simulated report said SIMULATED.</div>",
         "<div class='tiles'>" + ''.join(f"<div class='tile'><div class='k'>{e(k)}</div><div class='v'>{v}</div><div class='s'>{e(s)}</div></div>" for k, v, s in tiles) + '</div>']
    tot = max(1, sc['total'])
    H.append("<div class='bar'>" + ''.join(f"<i style='width:{100 * sc[k] / tot:.1f}%;background:{col[k]}' title='{k}: {sc[k]}'></i>" for k in ('met', 'late', 'open', 'overdue', 'missed')) + "</div><div class='sub'>"
             + ' · '.join(f"<span style='color:{col[k]}'>■</span> {STATE_WORD[k]} {sc[k]}" for k in ('met', 'late', 'open', 'overdue', 'missed')) + '</div>')
    if sc['by_cat']:
        H.append('<h2>By category</h2><table><tr><th>Category</th><th>Needs</th><th>Met</th><th>Late</th><th>Overdue / missed</th><th>Who</th></tr>'
                 + ''.join(f"<tr><td>{e(cat)}</td><td>{d['total']}</td><td>{d.get('met', 0)}</td><td>{d.get('late', 0)}</td><td>{d.get('overdue', 0) + d.get('missed', 0)}</td><td class='sub'>{e(NEED_ROLE.get(cat, ''))}</td></tr>" for cat, d in sorted(sc['by_cat'].items())) + '</table>')
    if sc['checks']:
        H.append('<h2>Done when</h2><ul class="chk">' + ''.join(f"<li><span class='st' style='background:{'#1f8a4c' if c['ok'] else '#9aa5b1' if c['ok'] is None else '#b03a2e'}'>{'met' if c['ok'] else 'not reached' if c['ok'] is None else 'not met'}</span> {e(c['label'])} <span class='sub'>· {e(c['why'])}</span></li>" for c in sc['checks']) + '</ul>')
    H.append('<h2>Do better, by role</h2>')
    if not rep['better']:
        H.append("<div class='well'>Nothing missed: every need that arose was met on time.</div>")
    for role, items in rep['better_by_role'].items():
        H.append(f"<h3 style='font-size:14px;margin:12px 0 4px'>{e(role)}</h3>")
        for b in items:
            H.append(f"<div class='coach'><span class='st' style='background:{col.get(b['state'], '#5b6b7a')}'>{e(STATE_WORD.get(b['state'], b['state']))}</span> <b>{e(b['need'])}</b><br><span class='sub'>{e(b['what'])}</span><br>→ {e(b['coach'])}</div>")
    if rep['well']:
        H.append('<h2>Went well</h2>' + ''.join(f"<div class='well'>{e(w['text'])}</div>" for w in rep['well'][:25]))
    H.append('<h2>Needs ledger</h2><table><tr><th>Arose</th><th>State</th><th>Need</th><th>Unit</th><th>Evidence</th></tr>'
             + ''.join(f"<tr><td class='mono'>{_fmt_t(n['arose_t'])}</td><td><span class='st' style='background:{col.get(n['state'], '#5b6b7a')}'>{e(STATE_WORD.get(n['state'], n['state']))}</span></td><td>{e(n['label'])}</td><td>{e(n.get('unit', ''))}</td><td class='sub'>{e(n.get('evidence', ''))}</td></tr>" for n in rep['needs']) + '</table>')
    H.append('<h2>Hot wash</h2><table><tr><th>T+</th><th>Result</th><th>Check</th><th>Evidence / note</th></tr>'
             + ''.join(f"<tr><td class='mono'>{_fmt_t(h['t'])}</td><td style='font-size:18px'>{e(h['result'] or '·')}</td><td>{e(h['check'])}</td><td class='sub'>{e(h['evidence'])}{(' · ' if h['evidence'] and h['note'] else '') + e(h['note'])}</td></tr>" for h in rep['hotwash']) + '</table>')
    H.append('<h2>Timeline</h2><div class="mono">' + '\n'.join(f"{e(x['wall'])} {_fmt_t(x['t'])}  {e(x['text'])}" for x in rep['timeline']) + '</div>')
    H.append('<h2>PACE</h2><div class="mono">' + '\n'.join(f"{_fmt_t(s['t'])} {e(s['level'])}  {e(s.get('why', ''))}" for s in rep['pace']) + '</div>')
    H.append('</body></html>')
    return '\n'.join(H)


_WELL_TAIL = re.compile(r':\s*appeared T\+\d+.*$')   # the evidence tail of a 'went well' line


def debrief_html(rep: dict, history: list = None, next_scenarios: list = None, results_url: str = '') -> str:
    """The debrief for the room: a projector page of slides built from the after-action report. Praise first, the
    honest score, why it matters (the real-disaster lessons behind what was missed), one or two things per role, the
    group's progress over its runs of this scenario, and the next drill. Self-contained (no external resources);
    arrow keys / space / click to move, F full screen, P print (one slide per page)."""
    import html as _h
    e = lambda x: _h.escape(str(x if x is not None else ''))
    history, next_scenarios = history or [], next_scenarios or []
    r, sc = rep['run'], rep['score']
    pct = sc.get('pct')
    word = {'strong': 'Strong', 'steady': 'Steady', 'struggling': 'Struggling', 'overwhelmed': 'Overwhelmed'}.get(sc.get('label') or '', 'Not scored yet')
    tone = 'good' if pct is not None and pct >= 65 else 'warn' if pct is not None and pct >= 40 else 'bad' if pct is not None else 'muted'
    site = (r.get('site') or {}).get('label', '')
    when = (r.get('created') or '')[:10]
    fmt_t = lambda t: f"T+{int(round(float(t or 0)))}"

    def trim(s, n=110):        # cut at a word, never mid-word
        s = ' '.join(str(s or '').split())
        return s if len(s) <= n else s[:n].rsplit(' ', 1)[0].rstrip(',;:(') + ' …'

    def role_name(s):          # one name per role in the room
        return re.sub(r'\bERD\b', 'Emergency Response Director', str(s or '').strip()) or 'EOC team'
    pace_word = {'P': 'Primary (cellular)', 'A': 'Alternate (any internet)', 'C': 'Contingency (radio and runners)', 'E': 'Emergency (runners with paper)'}
    slides = []
    # 1 cover
    slides.append(f"""<section class="cover"><p class="kick">Drill debrief · THIS WAS AN EXERCISE</p><h1>{e(r['scenario'].get('name', ''))}</h1>
<p class="lead">{e(site)}{' · ' + e(when) if when else ''} · {r.get('units', 0)} units · {fmt_t(r.get('elapsed_min'))} of {r.get('duration_min', 240)} drill minutes</p>
<p class="note">Every report in this drill said SIMULATED. {'Contacts are real, used with the recorded consent.' if r.get('privacy') == 'real' else "People's names and phones are invented; unit and building names are real."}</p></section>""")
    # 2 what you faced
    phases = ''.join(f"<li><b>{fmt_t(p.get('from'))}</b> {e(p.get('title', ''))}</li>" for p in rep.get('phases') or [])
    pace = ' → '.join(f"<span class='chip pace-{e(p.get('level', 'P'))}'>{e(p.get('level', 'P'))} <small>{fmt_t(p.get('t'))}</small></span>" for p in rep.get('pace') or [])
    summ = (r['scenario'].get('summary') or '').strip()
    if len(summ) > 520:
        summ = summ[:520].rsplit(' ', 1)[0] + ' …'
    slides.append(f"""<section><h2>What you faced</h2><div class="two"><div><p class="body">{e(summ) or 'The scenario as planned.'}</p>
<p class="sub">How you could talk (PACE: Primary, Alternate, Contingency, Emergency)</p><p class="chips">{pace}</p></div>
<div><p class="sub">Phases</p><ol class="phases">{phases}</ol></div></div></section>""")
    # 3 the score
    rp = sc.get('reports') or {}
    sitreps = sc.get('sitreps') or []
    tiles = [('Needs met', f"{sc.get('met', 0) + sc.get('late', 0)}<small> of {sc.get('total', 0)}</small>", f"{sc.get('met', 0)} on time · {sc.get('late', 0)} late"),
             ('SITREPs', str(len(sitreps)), f"first at {fmt_t(sitreps[0])}" if sitreps else 'none generated'),
             ('Reports', f"{rp.get('sent', 0)}<small> of {rp.get('expected', 0)}</small>", f"{rp.get('typed_ok', 0)} of {rp.get('typed', 0)} hand-carried typed in"),
             ('Minutes to an owner', e(sc.get('median_owner_min') if sc.get('median_owner_min') is not None else '—'), 'median, drill minutes')]
    cats = ''
    for cat, d in sorted((sc.get('by_cat') or {}).items()):
        tot = max(1, d.get('total', 0))
        segs = ''.join(f"<i class='s-{k}' style='width:{100 * d.get(k, 0) / tot:.1f}%'></i>" for k in ('met', 'late', 'open', 'overdue', 'missed'))
        cats += f"<div class='cat'><span>{e(cat)}</span><div class='bar'>{segs}</div><b>{d.get('met', 0) + d.get('late', 0)}/{d.get('total', 0)}</b></div>"
    slides.append(f"""<section><h2>The score</h2><div class="two"><div class="big {tone}"><span class="num">{'—' if pct is None else pct}<small>{'' if pct is None else '%'}</small></span><span class="word">{e(word)}</span>
<span class="small">needs met on time, half credit for late; open needs still inside their time are not counted</span></div>
<div><div class="tiles">{''.join(f"<div class='tile'><span class='t'>{t}</span><span class='v'>{v}</span><span class='s'>{s}</span></div>" for t, v, s in tiles)}</div>
<div class="cats">{cats}</div><p class="legend"><i class='s-met'></i>met <i class='s-late'></i>late <i class='s-open'></i>open <i class='s-overdue'></i>overdue <i class='s-missed'></i>missed</p></div></div></section>""")
    # 4 done when (the internal inject ids in the reasons mean nothing to the room)
    checks = sc.get('checks') or []
    if checks:
        clean = lambda w: re.sub(r'\s*\b[a-z]+(?:-[a-z0-9]+)+\s+(need\(s\))', r' \1', str(w or ''))
        rows = ''.join(f"<li class='{'ok' if c.get('ok') else 'no' if c.get('ok') is False else 'wait'}'><span class='mark'>{'✓' if c.get('ok') else '✗' if c.get('ok') is False else '…'}</span>"
                       f"<span><b>{e(c.get('label', ''))}</b><br><small>{e(clean(c.get('why', '')))}</small></span></li>" for c in checks)
        got = sum(1 for c in checks if c.get('ok'))
        slides.append(f"<section><h2>Done when <small>{got} of {len(checks)}</small></h2><ul class='checks'>{rows}</ul></section>")
    # 5 how it unfolded: PACE steps, SITREPs, and the high-priority needs that were missed, in plain words
    labels = {n['id']: n.get('label', '') for n in rep.get('needs') or []}
    prio = {n['label'][:60]: n.get('prio', 2) for n in rep.get('needs') or [] if n.get('label')}
    full = {n['label'][:60]: n['label'] for n in rep.get('needs') or [] if n.get('label')}
    events = []
    for t in rep.get('timeline') or []:
        x = t['text']
        m = re.match(r'PACE ([PACE]) in force', x)
        if m:
            events.append((t['t'], f"Now on {pace_word.get(m.group(1), m.group(1))}"))
        elif x.startswith('SITREP generated'):
            events.append((t['t'], f"SITREP #{sum(1 for v in events if v[1].startswith('SITREP')) + 1} sent"))
        else:
            m = re.match(r'need MISSED: (.*?) \(', x)
            if m and prio.get(m.group(1)[:60], 2) == 1:
                events.append((t['t'], 'Missed: ' + trim(full.get(m.group(1)[:60], m.group(1)), 90)))
    if events:
        rows = ''.join(f"<li><b>{fmt_t(t)}</b> {e(x)}</li>" for t, x in events[:10])
        slides.append(f"<section><h2>How it unfolded</h2><ol class='tl'>{rows}</ol></section>")
    # 6 what went well (praise before the do-better list): who did it, how many, two examples each
    well = rep.get('well') or []
    if well:
        by = {}
        for w in well:
            by.setdefault(role_name(w['role']), []).append(w)
        cards = ''
        for role, ws in sorted(by.items(), key=lambda kv: -len(kv[1]))[:4]:
            ex = ''.join(f"<li>{e(trim(_WELL_TAIL.sub('', w['text']), 90))}</li>" for w in ws[:2])
            cards += f"<div class='role'><h3>{e(role)} <small>{len(ws)} met on time</small></h3><ul>{ex}</ul></div>"
        slides.append(f"<section class='well'><h2>What went well <small>{len(well)} needs met on time</small></h2><div class='roles'>{cards}</div></section>")
    else:
        slides.append("<section class='well'><h2>What went well</h2><p class='body'>You came, you played, and the baseline is set. Every team starts here. The next run is the one that counts.</p></section>")
    # 7 why it matters
    why = sorted(rep.get('why') or [], key=lambda w: w['state'] in ('met',))
    if why:
        rows = ''.join(f"<li><p class='lesson'>{e(w['lesson'])}</p><p class='small'>In this drill: {e(trim(w['need'], 100))} · <b class='st-{e(w['state'])}'>{e(STATE_WORD.get(w['state'], w['state']))}</b></p></li>" for w in why[:4])
        slides.append(f"<section class='why'><h2>Why it matters</h2><p class='sub'>These injects come from real disasters of the last few years.</p><ul class='list'>{rows}</ul></section>")
    # 8 do better, by role (one name per role; at most two coaching lines each)
    br = {}
    for b in rep.get('better') or []:
        br.setdefault(role_name(b['role']), []).append(b)
    if br:
        cards = ''
        for role, items in sorted(br.items(), key=lambda kv: -len(kv[1]))[:4]:   # four roles fit one slide
            lines = []
            for b in items:
                if b['coach'] not in lines:
                    lines.append(b['coach'])
            cards += f"<div class='role'><h3>{e(role)} <small>{len(items)} need{'s' if len(items) != 1 else ''}</small></h3><ul>{''.join(f'<li>{e(x)}</li>' for x in lines[:2])}</ul></div>"
        slides.append(f"<section><h2>Do better next time</h2><div class='roles'>{cards}</div></section>")
    # 9 progress over this group's runs of the scenario
    pts = [h for h in history if h.get('pct') is not None]
    if pct is not None and not any(h.get('current') for h in pts):
        pts.append({'pct': pct, 'label': 'today', 'current': True})
    if pts:
        bars = ''.join(f"<div class='pb{' cur' if h.get('current') else ''}'><span class='pv'>{h['pct']}%</span><i style='height:{max(4, h['pct'])}%'></i><span class='pl'>{e(h.get('label', ''))}</span></div>" for h in pts[-8:])
        prev = [h for h in pts if not h.get('current')]
        if prev and pct is not None:
            d = pct - prev[-1]['pct']
            msg = f"Up {d} points since last time. Keep going." if d > 0 else (f"Down {-d} points since last time: pick the one thing that slipped and drill it." if d < 0 else "Level with last time: pick one thing to raise.")
        else:
            msg = 'This is your baseline. Run the same scenario again and beat it.'
        slides.append(f"<section><h2>Your progress</h2><p class='lead'>{e(msg)}</p><div class='prog'>{bars}</div></section>")
    # 10 next drill
    commits = []
    for b in rep.get('better') or []:
        if b['coach'] not in commits:
            commits.append(b['coach'])
    nxt = ''.join(f"<li>{e(n)}</li>" for n in next_scenarios[:3])
    slides.append(f"""<section class="next"><h2>The next drill</h2><div class="two"><div><p class="sub">Three things we will practise before then</p>
<ol class="commit">{''.join(f'<li>{e(c)}</li>' for c in commits[:3]) or '<li>Keep the habits that worked today.</li>'}</ol></div>
<div><p class="sub">Pick the date now</p><p class="date">Date: ________ &nbsp; Time: ______</p>
<p class="sub">Run it again, or try another scenario</p><ul class="list small">{"<li>The same scenario, to beat today's score</li>" + nxt}</ul>
{f"<p class='sub'>Results on your phone</p><p class='url'>{e(results_url)}</p>" if results_url else ''}</div></div></section>""")
    n = len(slides)
    body = ''.join(s.replace('<section', f"<section data-i='{i}'", 1) for i, s in enumerate(slides))
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Drill debrief</title><style>
:root{{--bg:#f4f6f9;--paper:#fff;--ink:#14213d;--muted:#5b6b7a;--line:#d9dee5;--navy:#1a2744;--good:#1f8a4c;--warn:#b7791f;--bad:#b03a2e;--miss:#7a1f16;--open:#8a97a6}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#0d1320;--paper:#151d2e;--ink:#e8edf5;--muted:#9aa8ba;--line:#2a3550;--navy:#9db7ff}}}}
:root[data-theme="dark"]{{--bg:#0d1320;--paper:#151d2e;--ink:#e8edf5;--muted:#9aa8ba;--line:#2a3550;--navy:#9db7ff}}
*{{box-sizing:border-box}}html,body{{margin:0;height:100%;background:var(--bg);color:var(--ink);font-family:system-ui,-apple-system,"Segoe UI",Arial,sans-serif}}
.deck{{position:fixed;inset:0;display:flex;align-items:center;justify-content:center}}
section{{display:none;width:min(100vw,177.78vh);height:min(56.25vw,100vh);background:var(--paper);padding:4.2% 5.5% 5%;position:relative;overflow:hidden;font-size:min(1.55vw,2.75vh)}}
section.on{{display:block}}
h1{{font-size:3.4em;line-height:1.08;margin:.2em 0 .35em;color:var(--navy)}}h2{{font-size:2.3em;margin:0 0 .6em;color:var(--navy)}}h2 small{{font-size:.5em;color:var(--muted);font-weight:600}}
h3{{margin:0 0 .3em;font-size:1.15em}}h3 small{{color:var(--muted);font-weight:500;font-size:.75em}}
.kick{{text-transform:uppercase;letter-spacing:.12em;font-weight:700;color:var(--bad);margin:0}}.cover{{display:none;padding-top:12%}}.cover.on{{display:block}}
.lead{{font-size:1.45em;color:var(--muted);margin:.2em 0 1em}}.note,.small{{color:var(--muted);font-size:.85em}}.sub{{text-transform:uppercase;letter-spacing:.08em;font-size:.75em;font-weight:700;color:var(--muted);margin:1em 0 .4em}}
.body{{font-size:1.15em;line-height:1.45}}.two{{display:grid;grid-template-columns:1.1fr 1fr;gap:4%}}
.chips{{display:flex;flex-wrap:wrap;gap:.4em;align-items:center}}.chip{{display:inline-block;padding:.25em .7em;border-radius:1em;font-weight:700;color:#fff;background:var(--good)}}
.pace-A{{background:#2563eb}}.pace-C{{background:var(--warn)}}.pace-E{{background:var(--bad)}}.chip small{{font-weight:500;opacity:.85}}
ol.phases,ol.tl{{margin:0;padding-left:1.2em;line-height:1.7}}ol.tl{{font-size:1.1em}}
.big{{display:flex;flex-direction:column;justify-content:center;align-items:flex-start}}.big .num{{font-size:7.5em;font-weight:800;line-height:1}}.big .num small{{font-size:.45em}}
.big .word{{font-size:2em;font-weight:700;margin:.1em 0 .3em}}.good .num,.good .word{{color:var(--good)}}.warn .num,.warn .word{{color:var(--warn)}}.bad .num,.bad .word{{color:var(--bad)}}.muted .num{{color:var(--muted)}}
.tiles{{display:grid;grid-template-columns:1fr 1fr;gap:.6em;margin-bottom:.8em}}.tile{{border:1px solid var(--line);border-radius:.5em;padding:.5em .7em;display:flex;flex-direction:column}}
.tile .t{{font-size:.75em;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}}.tile .v{{font-size:1.9em;font-weight:800}}.tile .v small{{font-size:.5em;color:var(--muted)}}.tile .s{{font-size:.75em;color:var(--muted)}}
.cat{{display:grid;grid-template-columns:7em 1fr 3em;gap:.5em;align-items:center;font-size:.85em;margin:.2em 0}}.bar{{display:flex;height:.8em;border-radius:.4em;overflow:hidden;background:var(--line)}}
.s-met{{background:var(--good)}}.s-late{{background:var(--warn)}}.s-open{{background:var(--open)}}.s-overdue{{background:var(--bad)}}.s-missed{{background:var(--miss)}}
.legend{{font-size:.7em;color:var(--muted)}}.legend i{{display:inline-block;width:.8em;height:.8em;border-radius:.2em;margin:0 .2em 0 .7em;vertical-align:middle}}
ul.checks{{list-style:none;margin:0;padding:0;columns:2;column-gap:3em}}ul.checks li{{display:flex;gap:.6em;break-inside:avoid;margin:0 0 .7em}}.mark{{font-size:1.4em;font-weight:800;width:1.2em}}
.ok .mark{{color:var(--good)}}.no .mark{{color:var(--bad)}}.wait .mark{{color:var(--muted)}}
ul.list{{list-style:none;margin:0;padding:0}}ul.list li{{padding:.45em 0;border-bottom:1px solid var(--line);font-size:1.05em}}.who{{display:inline-block;min-width:13em;font-weight:700;color:var(--good)}}
.lesson{{font-size:1.2em;font-style:italic;margin:0 0 .2em}}.st-met,.st-late{{color:var(--good)}}.st-missed,.st-overdue{{color:var(--bad)}}
.roles{{display:grid;grid-template-columns:1fr 1fr;gap:.8em 2.5em}}.role ul{{margin:0;padding-left:1.1em;line-height:1.4}}
.prog{{display:flex;align-items:flex-end;gap:2em;height:55%;padding-top:1em}}.pb{{flex:1;max-width:6em;height:100%;display:flex;flex-direction:column;justify-content:flex-end;align-items:center}}
.pb i{{display:block;width:100%;background:var(--open);border-radius:.3em .3em 0 0}}.pb.cur i{{background:var(--good)}}.pv{{font-weight:800;margin-bottom:.2em}}.pl{{font-size:.75em;color:var(--muted);margin-top:.3em;text-align:center}}
ol.commit{{font-size:1.25em;line-height:1.45;padding-left:1.2em}}.date{{font-size:1.6em;font-weight:700}}.url{{font-family:Consolas,monospace;font-size:1.2em}}
.foot{{position:absolute;left:5.5%;right:5.5%;bottom:2.2%;display:flex;justify-content:space-between;font-size:.62em;color:var(--muted)}}
.nav{{position:fixed;right:12px;top:10px;transition:opacity .6s;font:12px system-ui;color:var(--muted);background:var(--paper);border:1px solid var(--line);border-radius:6px;padding:4px 8px}}
@media print{{@page{{size:11in 6.1875in;margin:0}}html,body{{background:#fff}}.deck{{position:static;display:block}}section,section.cover{{display:block!important;width:11in;height:6.1875in;font-size:13pt;break-after:page}}.nav{{display:none}}}}
</style></head><body><div class="deck">{body}</div><div class="nav" id="nav">← → move · F full screen · P print</div>
<script>
var S=[].slice.call(document.querySelectorAll('section')),i=0;
S.forEach(function(s,k){{var f=document.createElement('div');f.className='foot';f.innerHTML='<span>Church of Jesus Christ EMCOMM drill debrief · an independent volunteer project, not an official Church product</span><span>'+(k+1)+' / {n}</span>';s.appendChild(f);}});
function show(k){{i=Math.max(0,Math.min(S.length-1,k));S.forEach(function(s,j){{s.classList.toggle('on',j===i);}});try{{history.replaceState(null,'','#'+(i+1));}}catch(e){{}}}}
document.addEventListener('keydown',function(ev){{var k=ev.key;if(k==='ArrowRight'||k===' '||k==='PageDown'){{show(i+1);ev.preventDefault();}}else if(k==='ArrowLeft'||k==='PageUp'){{show(i-1);}}else if(k==='Home'){{show(0);}}else if(k==='End'){{show(S.length-1);}}
else if(k==='f'||k==='F'){{if(document.fullscreenElement)document.exitFullscreen();else document.documentElement.requestFullscreen&&document.documentElement.requestFullscreen();}}else if(k==='p'||k==='P'){{window.print();}}}});
document.querySelector('.deck').addEventListener('click',function(ev){{show(ev.clientX>window.innerWidth/2?i+1:i-1);}});
show((parseInt((location.hash||'#1').slice(1),10)||1)-1);
setTimeout(function(){{document.getElementById('nav').style.opacity='0';}},6000);
</script></body></html>"""


def counts(run: dict) -> dict:
    c = {'items': len(run['items']), 'units': len(run['scope']['units']), 'needs': len(run.get('needs') or [])}
    for it in run['items']:
        c[it['kind']] = c.get(it['kind'], 0) + 1
        if it['kind'] == 'form':
            c[it['form']] = c.get(it['form'], 0) + 1
        c['status:' + it['status']] = c.get('status:' + it['status'], 0) + 1
    c['severity'] = {str(b): sum(1 for u in run['scope']['units'] if u['severity'] == b) for b in range(4)}
    c['local'] = sum(1 for it in run['items'] if it.get('local', True))
    c['elsewhere'] = sum(1 for it in run['items'] if not it.get('local', True))
    return c
