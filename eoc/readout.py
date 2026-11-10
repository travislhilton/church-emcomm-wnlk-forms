#!/usr/bin/env python3
"""The incident read-out for a voice net: an emcomm-readout/1 document (docs/contracts/emcomm-readout/).

Net control reads it on an open frequency, so it carries facts only: counts, unit names and times. It never carries
injuries, deaths, missionary status, people's names, phone numbers, email or street addresses, or GPS (owner decision
2026-11-10). A count nothing reported is null ("not reported"), never 0.

The totals are a port of buildSitrep() in EOC_Message_Center.html (unitOf, ni, parseFloat, isYes, soItemsOf,
soAggregate, sitrepHrs, sitrepDue): the read-out and the SITREP must agree. Keep them in step.

    build(conn, event_id) -> dict      # pure: reads the database through conn, takes no lock, writes nothing

Python standard library only; Python 3.8 and later.
"""
import datetime
import hashlib
import json
import pathlib
import re

SCHEMA = 'emcomm-readout/1'
APP = 'church-emcomm-eoc'
LEVELS = ('satellite', 'stake', 'area')
APPROVER = {'satellite': 'Stake President or his delegate', 'stake': 'Stake President or his delegate',
            'area': 'Area Authority or his delegate'}
PACE_LEVELS = ('P', 'A', 'C', 'E')
SITREP_OPTS = (2, 4, 8, 12, 24)      # SITREP_OPTS in the page: any other value is "not set"
UNNAMED_UNIT = 'unit not named'      # a report that names no unit (the SITREP prints "?")
TOP_ITEMS = 5

HERE = pathlib.Path(__file__).resolve().parent
PAGE = HERE / 'EOC_Message_Center.html'      # the Supply Order catalog lives in the page (SO_ITEMS); read it from there
_catalog = {}


# ── The page's helpers, in Python ─────────────────────────────────────────────
_INT = re.compile(r'\s*([+-]?\d+)')
_FLOAT = re.compile(r'\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)')


def parse_int(v):
    """JavaScript parseInt(v, 10): the leading integer, or None where parseInt gives NaN."""
    m = _INT.match(str(v if v is not None else ''))
    return int(m.group(1)) if m else None


def parse_float(v):
    """JavaScript parseFloat(v): the leading number, or None where parseFloat gives NaN."""
    m = _FLOAT.match(str(v if v is not None else ''))
    return float(m.group(1)) if m else None


def is_yes(v) -> bool:
    return str(v or '').strip().upper() in ('YES', 'Y')


def is_exercise(sub) -> bool:
    """isEx(m) in the page: the sender ticked THIS IS AN EXERCISE (Winlink tag exercise=YES, Worker checkbox)."""
    return isinstance(sub, dict) and str(sub.get('exercise') or '').strip().lower() in ('yes', '1', 'true', 'on')


def normalize(d: dict) -> dict:
    """_normalizeServerMsg(d): lower-case type; an old flat record gets its sub-object."""
    d['type'] = str(d.get('type') or '').lower()
    sub = d['type']
    if sub and not isinstance(d.get(sub), dict):
        meta = {'id', 'ts', 'type', 'filename', 'source', 'from', 'subject', 'dupKey', 'status', 'operator_note', 'origin', 'via', 'formKey'}
        d[sub] = {k: v for k, v in d.items() if k not in meta}
    return d


def unit_of(m: dict, level: str) -> str:
    """unitOf(m): the unit a record belongs to (a stake at an area EOC, else the ward, else the stake)."""
    t = m.get('type')
    s = m.get(t) if isinstance(m.get(t), dict) else {}
    if t == 'dr':
        u = s.get('stake') if level == 'area' else (s.get('ward') or s.get('stake'))
    elif t == 'so':
        u = s.get('stake')
    elif t == 'wcl':
        u = s.get('chief_stake') if level == 'area' else (s.get('chief_ward') or s.get('chief_stake'))
    else:
        u = ''
    return str(u or '').strip()


def catalog() -> dict:
    """SO_ITEMS from the page: {'by_id': {...}, 'by_num': {...}, 'items': [info, ...]} (read once per file state)."""
    try:
        sig = PAGE.stat().st_mtime_ns
    except OSError:
        sig = None
    if _catalog.get('sig') != sig or 'items' not in _catalog:
        items = []
        if sig is not None:
            text = PAGE.read_text(encoding='utf-8')
            block = re.search(r'var SO_ITEMS = \[(.*?)\n\];', text, re.S)
            s = r"'((?:[^'\\]|\\.)*)'"      # a JavaScript string in single quotes (Tarp (20\' x 30\'))
            rows = re.findall(r'\[' + ','.join([s] * 5) + r'\]', block.group(1)) if block else []
            for i, row in enumerate(rows):
                iid, desc, num, unit, section = (re.sub(r'\\(.)', r'\1', x) for x in row)
                items.append({'id': iid, 'desc': desc, 'num': num, 'unit': unit, 'section': section, 'order': i})
        _catalog.clear()
        _catalog.update({'sig': sig, 'items': items, 'by_id': {x['id']: x for x in items}, 'by_num': {x['num']: x for x in items}})
    return _catalog


def _item_info(code: str) -> dict:
    """soItemInfo(code)."""
    code = str(code or '').strip()
    c = catalog()
    if code in c['by_id']:
        return dict(c['by_id'][code])
    if code in c['by_num']:
        return dict(c['by_num'][code])
    if code.startswith('LOCAL-'):
        return {'id': '', 'desc': code[6:] + ' (other item, local purchase)', 'num': '', 'unit': '', 'section': 'Other Items', 'order': 9000}
    return {'id': '', 'desc': 'Item ' + code, 'num': code, 'unit': '', 'section': 'Other Items', 'order': 9001}


def so_items(m: dict) -> list:
    """soItemsOf(m): every ordered item of one Supply Order, from the whole form when it arrived, else the tag."""
    out = []
    f = m.get('fields')
    if isinstance(f, dict):
        for info in catalog()['items']:
            q = parse_int(f.get(info['id']))
            if q is not None and q > 0:
                out.append(dict(info, qty=q))
        for i in range(1, 6):
            od = str(f.get(f'other_desc{i}') or '').strip()
            oq = parse_int(f.get(f'other_qty{i}'))
            if od and oq is not None and oq > 0:
                out.append({'id': '', 'desc': od + ' (other item, local purchase)', 'num': str(f.get(f'other_num{i}') or '').strip(),
                            'unit': str(f.get(f'other_unit{i}') or '').strip(), 'section': 'Other Items', 'order': 9000, 'qty': oq})
        if out:
            return out
    so = m.get('so') if isinstance(m.get('so'), dict) else {}
    for p in str(so.get('items') or '').split(';'):
        c = p.rfind(':')
        if c < 1:
            continue
        q = parse_int(p[c + 1:])
        if q is None or q <= 0:
            continue
        out.append(dict(_item_info(p[:c]), qty=q))
    return out


def so_aggregate(sos: list) -> list:
    """soAggregate(sos): items combined by Church item number (other items by text), in catalog order."""
    agg = {}
    for m in sos:
        for it in so_items(m):
            k = it.get('num') or it.get('desc')
            if k not in agg:
                agg[k] = dict(it, total=0)
            agg[k]['total'] += it['qty']
    return sorted(agg.values(), key=lambda a: (a['order'], a['desc'].casefold(), a['desc']))


# ── Times ─────────────────────────────────────────────────────────────────────
def iso_local(ms):
    """Milliseconds since 1970 -> local time with its offset (2026-11-10T18:57:00-07:00); None for none."""
    try:
        ms = float(ms)
    except (TypeError, ValueError):
        return None
    if ms <= 0:
        return None
    return datetime.datetime.fromtimestamp(ms / 1000, tz=datetime.timezone.utc).astimezone().isoformat(timespec='seconds')


def now_local() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')


def _num(x):
    """A sum as JSON shows it: 210, not 210.0; rounded to 2 decimals so float noise never changes the fingerprint."""
    x = round(float(x), 2)
    return int(x) if x == int(x) else x


# ── The document ──────────────────────────────────────────────────────────────
def fingerprint(doc: dict) -> str:
    """sha256 of the canonical JSON of the document without generated_at and fingerprint (the contract README)."""
    body = {k: v for k, v in doc.items() if k not in ('generated_at', 'fingerprint')}
    canon = json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return 'sha256:' + hashlib.sha256(canon.encode('utf-8')).hexdigest()


def _sum(values, parse):
    """Sum of the values that parse; None when not one record reported the value."""
    got = [x for x in (parse(v) for v in values) if x is not None]
    return sum(got) if got else None


def _names(units) -> list:
    """Unit names once each (first spelling, compared without case), sorted."""
    seen = {}
    for u in units:
        u = (u or '').strip() or UNNAMED_UNIT
        seen.setdefault(u.casefold(), u)
    return sorted(seen.values(), key=lambda s: (s.casefold(), s))


def _expected_units(conn, event_id: str, ident: dict):
    """The EOC's own list of units: the event's roster (Roster tab) or else 'Units covered' (Setup tab); None when
    neither lists any. Names only: a roster row's leader and phone never leave this function."""
    names = []
    for r in conn.execute('SELECT data_json FROM roster WHERE event_id=?', (event_id,)).fetchall():
        try:
            nm = str((json.loads(r['data_json'] or '{}') or {}).get('name') or '').strip()
        except (ValueError, TypeError, AttributeError):
            nm = ''
        if nm:
            names.append(nm)
    if not names:
        names = [s.strip() for s in re.split(r'[,;\n]+', str(ident.get('eocUnits') or '')) if s.strip()]
    if not names:
        return None
    seen = {}
    for n in names:
        seen.setdefault(n.casefold(), n)
    return list(seen.values())      # the EOC's own order


def build(conn, event_id: str, forms_version=None, drill_active: bool = False, generated_at=None) -> dict:
    """The emcomm-readout/1 document for one Emergency Event. conn: an open sqlite3 connection (row_factory Row)."""
    ev_row = conn.execute('SELECT * FROM events WHERE id=?', (event_id,)).fetchone()
    ev = json.loads(ev_row['data_json'] or '{}') if ev_row else {}
    r = conn.execute('SELECT data_json FROM incident WHERE singleton=1').fetchone()
    ident = json.loads(r['data_json'] or '{}') if r else {}
    level = ident.get('eocLevel') if ident.get('eocLevel') in LEVELS else 'stake'      # eocLevel() in the page

    msgs = []
    for row in conn.execute('SELECT * FROM messages WHERE event_id=? ORDER BY received_ms ASC', (event_id,)).fetchall():
        try:
            d = json.loads(row['data_json'] or '{}')
        except ValueError:
            continue
        if not isinstance(d, dict):
            continue
        d['id'], d['ts'] = row['id'], row['received_ms']
        normalize(d)
        if d['type'] in ('dr', 'so', 'wcl'):
            msgs.append(d)
    drs = [m for m in msgs if m['type'] == 'dr']
    sos = [m for m in msgs if m['type'] == 'so']
    wcls = [m for m in msgs if m['type'] == 'wcl']

    # Disaster Reports: property and volunteers (ni() in the page: the leading integer)
    dr_sub = [m['dr'] for m in drs]
    reported = _names(unit_of(m, level) for m in drs if unit_of(m, level))
    expected = _expected_units(conn, event_id, ident)
    got = {u.casefold() for u in reported}
    needs = {k: _names(unit_of(m, level) for m in drs if is_yes(m['dr'].get('need_' + k))) for k in ('local', 'neighbor', 'hq')}

    # Work Crew Logs (parseFloat for hours, ni for members, as the SITREP's section G)
    crew_members = _sum((m['wcl'].get('crew_count') for m in wcls), parse_int)
    crew_hours = _sum((m['wcl'].get('total_hrs') for m in wcls), parse_float)

    # Supply Orders: the largest totals first (ties stay in catalog order)
    agg = so_aggregate(sos)
    top = sorted(agg, key=lambda a: -a['total'])[:TOP_ITEMS]

    # Roll-ups merged from lower EOCs (Section H of the SITREP)
    via = sorted({str(x.get('from') or '').strip() for x in (ev.get('rollups') or []) if isinstance(x, dict)} - {''},
                 key=lambda s: (s.casefold(), s))

    # SITREP interval and the next one due (sitrepHrs(), sitrepDue() in the page)
    hrs = parse_int(ev.get('sitrepHrs'))
    hrs = hrs if hrs in SITREP_OPTS else None
    base = max(_ms(ev.get('lastSitrepTs')), _ms(ev.get('lastRollupTs'))) or _ms(ev.get('startTs'))
    pace = ev.get('pace') if ev.get('pace') in PACE_LEVELS else None

    homes_dmg = _sum((s.get('homes_dmg') for s in dr_sub), parse_int)
    homes_dest = _sum((s.get('homes_dest') for s in dr_sub), parse_int)
    vol_count = _sum((s.get('vol_count') for s in dr_sub), parse_int)
    vol_hrs = _sum((s.get('vol_hrs') for s in dr_sub), parse_int)

    doc = {
        'schema': SCHEMA,
        'generated_at': generated_at or now_local(),
        'as_of': iso_local(max((m['ts'] or 0) for m in msgs)) if msgs else None,
        'source': {
            'app': APP,
            'forms_version': forms_version,
            'eoc': {'name': str(ident.get('eocName') or '').strip() or None, 'level': level},
            'event': {'id': event_id or None, 'name': str(ev.get('name') or '').strip() or None,
                      # an exercise when any report counted here is marked THIS IS AN EXERCISE, or a drill simulator
                      # is feeding this EOC: exercise traffic must never be read on the air as real
                      'exercise': bool(drill_active) or any(is_exercise(m.get(m['type'])) for m in msgs)},
        },
        'approver': {'role': APPROVER[level]},
        'pace': {'level': pace, 'since': iso_local(ev.get('paceTs')) if pace else None},
        'incident': {
            'name': str(ev.get('name') or '').strip() or None,
            'type': str(ev.get('type') or '').strip() or None,
            'area': str(ev.get('area') or '').strip() or None,
            'interval_hours': hrs,
            'next_sitrep_at': iso_local(base + hrs * 3600000) if base and hrs else None,
        },
        'reporting': {
            'unit_word': 'stake' if level == 'area' else 'ward',
            'units_expected': len(expected) if expected is not None else None,
            'units_reported': len(reported),
            'reported': reported,
            'not_reported': [u for u in expected if u.casefold() not in got] if expected is not None else None,
            'reports': {'dr': len(drs), 'so': len(sos), 'wcl': len(wcls)},
            'via_rollup': via,
        },
        'property': {'homes_damaged': homes_dmg, 'homes_destroyed': homes_dest},
        'needs': needs,
        'supplies': {'orders': len(sos), 'top_items': [{'desc': a['desc'], 'qty': a['total']} for a in top]},
        'crews': {'logs': len(wcls), 'members': crew_members, 'hours': _num(crew_hours) if crew_hours is not None else None},
        'volunteers': {'count': vol_count, 'hours': vol_hrs},
        'notes': [],
    }
    doc['fingerprint'] = fingerprint(doc)
    return doc


def _ms(v) -> int:
    try:
        return int(float(v or 0))
    except (TypeError, ValueError):
        return 0
