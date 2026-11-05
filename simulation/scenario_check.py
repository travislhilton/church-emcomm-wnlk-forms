#!/usr/bin/env python3
"""Scenario validator for the EMCOMM simulator (Python standard library only).

    python simulation/scenario_check.py <scenario.json>
    python simulation/scenario_check.py <scenario.json> --pack "<export root>" --local <id>.local.json --catalog <catalog.json>

Exit code 1 when there is an error, 0 when there are only warnings (or nothing). Every message names where it is
(``injects[12] 'dr-initial'.where.in``). Nothing is written.

What it checks (the field lists come from what simulation/engine.py actually reads):
  * unknown keys at every level (a typo the engine would silently ignore), required keys;
  * injects: unique ids; kind; form dr|so|wcl (ics213|ics213rr for ICS); template exists and its keys are fields of
    that form's Worker; template value shapes (plain strings and numbers, {"range"}, {"pick"}, {"yes"} by severity
    band 0-3; Supply Order items, Work Crew Log crew); channel; `to`, `each`; every time within 0..duration;
    `same_as` and `after.need` (with a #suffix the EOC derives) name an inject; `after.is`; `where.in`, the
    severity rule's `from` and band / boost features exist in `geo`; categories; need blocks and needs.defaults;
    agency keys;
  * PACE: levels P/A/C/E, times ascending from 0; phases inside the run and not overlapping; done-when checks have
    exactly one known type and `need_met` names an inject; hot-wash `auto` rules; role cards have t and text;
  * {placeholders}: unknown ones, and per-unit ones (a ward, its bishop, ...) in texts that are filled once
    (role cards, an inject that is not per unit);
  * with --pack: the scenario planned once over the pack: injects that reach no unit, units per severity band,
    placeholders left after planning, local-binding unit names that are not in the pack;
  * a warning when the scenario has no catalog entry (the Setup tab would not list it).

The simulator's Setup tab runs the same check before "Plan the run" (GET /api/scenarios/<id>/check).
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402

DOC = ('note', 'notes', 'comment')        # documentation keys allowed anywhere

TOP_KEYS = {'kind', 'v', 'id', 'name', 'hazard', 'onset', 'summary', 'sources', 'applies', 'clock', 'geo', 'severity', 'pace',
            'phases', 'injects', 'templates', 'roles', 'hotwash', 'eocs', 'agencies', 'needs', 'done', 'severity_override',
            'lessons', 'status', 'duration_min'}
LOCAL_KEYS = {'kind', 'v', 'scenario', 'geo', 'templates', 'injects', 'roles', 'hotwash', 'phases', 'severity_override', 'agencies'}
CLOCK_KEYS = {'t0', 'duration_min', 'default_speed'}
SEVERITY_KEYS = {'rule', 'from', 'bands', 'default', 'default_no_location', 'level', 'boost'}
SEVERITY_RULES = ('distance_km', 'feature', 'constant')
BAND_KEYS = {'max', 'in', 'level'}
BOOST_KEYS = {'in', 'flag', 'add', 'min'}
FEATURE_KEYS = {'type', 'coords', 'center', 'radius_km', 'name', 'label', 'source'}
PACE_KEYS = {'t', 'level', 'why', 'trigger', 'manual'}
PHASE_KEYS = {'id', 'from', 'to', 'title', 'narrative', 'controller'}
INJECT_KEYS = {'id', 'kind', 'each', 'where', 'same_as', 't', 'template', 'form', 'channel', 'after', 'to', 'text', 'title', 'detail',
               'next', 'cat', 'prio', 'due', 'unit', 'from', 'decision', 'status', 'match', 'agency', 'fields', 'subject', 'need',
               'lesson', 'role'}
KINDS = ('form', 'note', 'voice', 'prompt', 'paper', 'work_item', 'reply', 'ics', 'rollup')
EACH = ('once', 'unit', 'stake')
TO = ('stake', 'satellite', 'area', 'all', 'unit', 'eoc')
FORMS = tuple(engine.FORM_FILENAMES)                 # dr, so, wcl
ICS = tuple(engine.ICS_FORMS)                        # ics213, ics213rr
FORM_CHANNELS = ('by_pace', 'phone', 'drop', 'winlink', 'paper', 'voice')
WHERE_KEYS = {'severity', 'severity_min', 'severity_max', 'flags_any', 'flags_none', 'in', 'unit', 'units', 'sample', 'tag', 'tag_not'}
FLAGS = ('care_facility', 'retirement', 'language_unit')
AFTER_KEYS = {'need', 'is', 'delay'}
AFTER_IS = ('met', 'overdue', 'missed', 'late')      # what Runner._needs_tick understands
MATCH_KEYS = {'cat', 'status', 'key_prefix', 'title_contains'}
WORK_STATES = ('open', 'progress', 'up', 'done', 'any')
REPLY_STATUS = ('done', 'progress', 'open')
CATS = tuple(k for k in engine.NEED_DEFAULTS if k != 'report')
NEED_RULE_KEYS = {'owner', 'done', 'decision', 'done_states', 'typed', 'label', 'role'}
NEED_KEYS = NEED_RULE_KEYS | {'cat', 'form', 'title_contains', 'prio'}
DONE_STATES = ('open', 'progress', 'up', 'done')
ROLE_KEYS = {'id', 'title', 'cards'}
CARD_KEYS = {'t', 'text'}
HOTWASH_KEYS = {'t', 'check', 'how', 'auto'}
AUTO_KEYS = {'items', 'expect'}
AUTO_ITEMS = {'cat', 'key_prefix', 'title_contains'}
AUTO_EXPECT = {'min_count', 'max_count', 'owner_within_min', 'done_within_min', 'status_in', 'decision', 'no_unowned_high'}
DONE_TYPES = ('sitrep', 'no_unowned_high', 'pct_min', 'cat_met', 'need_met')
DONE_CHECK_KEYS = {'id', 'label', 'by'} | set(DONE_TYPES)
EOCS_KEYS = {'satellite': {'name', 'where'}, 'area': {'name'}}
AGENCY_KEYS = {'name', 'call', 'contact', 'place', 'forms'}
APPLIES_KEYS = {'bbox'}
BANDS = ('0', '1', '2', '3')
# the values the engine fills: per unit (engine._Ctx) and once (engine.plan's once_values); agencies add {k}, {k}_call, {k}_contact, {k}_place
ONCE_VALUES = {'stake', 'eoc_call', 'eoc_winlink', 'eoc_email', 'eoc', 'today', 'erd', 'erd_phone', 'specialist', 'specialist_phone'}
UNIT_VALUES = ONCE_VALUES | {'unit', 'unit_type', 'city', 'building', 'address', 'building_name', 'state', 'zip', 'stake_president',
                             'stake_center', 'stake_center_city', 'stake_center_zip', 'stake_center_name', 'bishop', 'bishop_role',
                             'bishop_phone', 'bishop_email', 'crew_chief', 'crew_chief_phone', 'unit_call', 'tomorrow', 'severity'}
TEXT_KEYS = ('text', 'title', 'detail', 'next', 'due', 'unit', 'from', 'decision', 'subject')
DERIVED_SUFFIXES_FALLBACK = ('report', 'miss', 'life', 'hq', 'nbr', 'local', 'shelter', 'bldg', 'approve', 'safety')
PLACEHOLDER = re.compile(r'\{([a-z_]+)\}')


class Report:
    def __init__(self):
        self.errors, self.warnings, self.info = [], [], []

    def err(self, where, msg):
        self.errors.append(f'{where}: {msg}')

    def warn(self, where, msg):
        self.warnings.append(f'{where}: {msg}')

    def as_dict(self) -> dict:
        return {'ok': not self.errors, 'errors': self.errors, 'warnings': self.warnings, 'info': self.info}


def _unknown(r: Report, where: str, obj, known: set):
    if not isinstance(obj, dict):
        r.err(where, f'expected an object, found {type(obj).__name__}')
        return False
    for k in obj:
        if k in DOC or k.endswith('_note') or k.startswith('_'):
            continue
        if k not in known:
            r.err(where, f'unknown key {k!r} (known: {", ".join(sorted(known))})')
    return True


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def worker_fields() -> dict:
    """{form: set of field names} read from the Worker forms (templates/<form>/*_Worker.html), or {} when not found."""
    dirs = {'dr': 'disaster-report', 'so': 'supply-order', 'wcl': 'work-crew-log'}
    out = {}
    for root in (HERE.parent / 'templates', HERE.parent.parent / 'templates', HERE.parent / 'Templates'):
        for form, d in dirs.items():
            if form in out:
                continue
            for f in sorted((root / d).glob('*_Worker.html')) if (root / d).is_dir() else []:
                t = f.read_text(encoding='utf-8', errors='ignore')
                out[form] = set(re.findall(r'<(?:input|select|textarea)\b[^>]*?\b(?:id|name)="([^"]+)"', t))
                break
    return out


def derived_suffixes() -> tuple:
    """The #suffixes of the work items the EOC derives from a report (eoc_server._derive_actions item kinds) plus #report."""
    for p in (HERE.parent / 'eoc' / 'eoc_server.py', HERE.parent / 'eoc_server.py'):
        if p.is_file():
            src = p.read_text(encoding='utf-8', errors='ignore')
            m = re.search(r'def _derive_actions\(.*?(?=\ndef )', src, re.S)
            kinds = re.findall(r"\bitem\('(\w+)'", m.group(0)) if m else []
            if kinds:
                return tuple(['report'] + sorted(set(kinds)))
    return DERIVED_SUFFIXES_FALLBACK


def _time(r, where, t, duration):
    if _num(t):
        if not 0 <= t <= duration:
            r.err(where, f'time {t:g} is outside the run (0..{duration:g})')
    elif isinstance(t, dict):
        _unknown(r, where, t, {'from', 'to'})
        a, b = t.get('from'), t.get('to')
        if not (_num(a) and _num(b)):
            r.err(where, 'a time window needs numeric "from" and "to"')
        elif not 0 <= a <= b <= duration:
            r.err(where, f'time window {a:g}..{b:g} is outside the run (0..{duration:g}) or reversed')
    else:
        r.err(where, f'time must be a minute or {{"from", "to"}}, found {t!r}')


def _bands(r, where, spec, check):
    """A per-severity-band dict {"0".."3": value}: band keys and each value."""
    if not isinstance(spec, dict) or not spec:
        r.err(where, 'expected a {"<band 0-3>": ...} object')
        return
    for b, v in spec.items():
        if b not in BANDS:
            r.err(where, f'band {b!r} is not 0, 1, 2 or 3')
        else:
            check(f'{where}.{b}', v)


def _pair(r, where, v):
    if not (isinstance(v, list) and len(v) == 2 and all(_num(x) for x in v) and v[0] <= v[1]):
        r.err(where, f'expected [min, max] numbers, found {v!r}')


def _value(r, where, spec):
    """One template value: a string, a number, {"range"}, {"pick"} or {"yes"}."""
    if isinstance(spec, (str, int, float)) and not isinstance(spec, bool):
        return
    if isinstance(spec, dict) and len(spec) == 1 and next(iter(spec)) in ('range', 'pick', 'yes'):
        k, v = next(iter(spec.items()))
        if k == 'range':
            _bands(r, f'{where}.range', v, lambda w, x: _pair(r, w, x))
        elif k == 'pick':
            _bands(r, f'{where}.pick', v, lambda w, x: None if isinstance(x, list) and x and all(isinstance(s, (str, int, float)) for s in x)
                   else r.err(w, f'expected a non-empty list of texts, found {x!r}'))
        else:
            _bands(r, f'{where}.yes', v, lambda w, x: None if _num(x) and 0 <= x <= 1 else r.err(w, f'expected a probability 0..1, found {x!r}'))
        return
    r.err(where, f'a template value is a text, a number, {{"range"}}, {{"pick"}} or {{"yes"}}; found {json.dumps(spec)[:80]}')


def _texts_of_value(spec) -> list:
    if isinstance(spec, str):
        return [spec]
    if isinstance(spec, dict):
        out = []
        for v in spec.values():
            out += _texts_of_value(v)
        return out
    if isinstance(spec, list):
        return [x for s in spec for x in _texts_of_value(s)]
    return []


def _placeholders(r, where, texts, allowed: set, unit_only: set = frozenset()):
    for t in texts:
        for name in PLACEHOLDER.findall(t or ''):
            if name in allowed:
                continue
            if name in unit_only:
                r.err(where, f'{{{name}}} names one unit, but this text is filled once (not per unit): it would stay as written')
            else:
                r.err(where, f'unknown placeholder {{{name}}}')


def agency_placeholders(agencies: dict) -> set:
    out = {'city_eoc', 'city_eoc_call', 'city_eoc_contact', 'city_eoc_place'}
    for k in agencies or {}:
        out |= {k, f'{k}_call', f'{k}_contact', f'{k}_place'}
    return out


def check(sc: dict, local: dict = None, pack: dict = None, catalog: dict = None, catalog_label: str = '') -> dict:
    """Validate one scenario (merged with its local binding when given). Returns {ok, errors, warnings, info}."""
    r = Report()
    if not isinstance(sc, dict):
        r.err('scenario', 'not a JSON object')
        return r.as_dict()
    _unknown(r, 'scenario', sc, TOP_KEYS)
    for k in ('id', 'name', 'injects'):
        if k not in sc:
            r.err('scenario', f'missing {k!r}')
    if local is not None:
        _unknown(r, 'local binding', local, LOCAL_KEYS)
        if local.get('scenario') and local['scenario'] != sc.get('id'):
            r.err('local binding', f"is for scenario {local['scenario']!r}, not {sc.get('id')!r}")
        sc = engine.merge_local(sc, local)
    clock = sc.get('clock') or {}
    _unknown(r, 'clock', clock, CLOCK_KEYS)
    duration = clock.get('duration_min', 240)
    if not _num(duration) or duration <= 0:
        r.err('clock.duration_min', f'expected a positive number of minutes, found {duration!r}')
        duration = 240
    if 'default_speed' in clock and not (_num(clock['default_speed']) and 0.1 <= clock['default_speed'] <= 60):
        r.err('clock.default_speed', 'expected a number 0.1..60')
    if 'applies' in sc:
        _unknown(r, 'applies', sc['applies'], APPLIES_KEYS)
        bb = (sc.get('applies') or {}).get('bbox')
        if bb is not None and not (isinstance(bb, list) and len(bb) == 4 and all(_num(x) for x in bb) and bb[0] < bb[2] and bb[1] < bb[3]):
            r.err('applies.bbox', 'expected [west, south, east, north]')

    # geography
    geo = sc.get('geo') or {}
    if not isinstance(geo, dict):
        r.err('geo', 'expected an object')
        geo = {}
    feats = geo.get('features') or {}
    points = {k for k, v in geo.items() if k not in ('features',) + DOC and not k.endswith('_note')}
    for k in points:
        v = geo[k]
        if not (isinstance(v, list) and len(v) == 2 and all(_num(x) for x in v)):
            r.err(f'geo.{k}', 'a point is [latitude, longitude]')
    for name, f in feats.items():
        w = f'geo.features.{name}'
        if not _unknown(r, w, f, FEATURE_KEYS):
            continue
        if f.get('type') == 'polygon':
            c = f.get('coords')
            if not (isinstance(c, list) and len(c) >= 3 and all(isinstance(p, list) and len(p) == 2 and all(_num(x) for x in p) for p in c)):
                r.err(w, 'a polygon needs "coords": at least three [longitude, latitude] points')
        elif f.get('type') == 'circle':
            if not (isinstance(f.get('center'), list) and len(f['center']) == 2 and _num(f.get('radius_km'))):
                r.err(w, 'a circle needs "center": [latitude, longitude] and "radius_km"')
        else:
            r.err(w, f"type must be polygon or circle, found {f.get('type')!r}")

    def feature(where, name):
        if name not in feats:
            r.err(where, f'no feature {name!r} in geo.features')

    # severity
    sev = sc.get('severity') or {}
    if _unknown(r, 'severity', sev, SEVERITY_KEYS):
        rule = sev.get('rule')
        if rule not in SEVERITY_RULES:
            r.err('severity.rule', f'must be one of {", ".join(SEVERITY_RULES)}, found {rule!r}')
        if rule == 'distance_km' and sev.get('from', 'epicenter') not in points:
            r.err('severity.from', f"no point {sev.get('from', 'epicenter')!r} in geo")
        for n, b in enumerate(sev.get('bands') or []):
            w = f'severity.bands[{n}]'
            if not _unknown(r, w, b, BAND_KEYS):
                continue
            if b.get('level') not in (0, 1, 2, 3):
                r.err(w, f"level must be 0..3, found {b.get('level')!r}")
            if rule == 'feature':
                feature(w + '.in', b.get('in'))
            elif rule == 'distance_km' and 'max' in b and not _num(b['max']):
                r.err(w + '.max', 'expected kilometres')
        for n, b in enumerate(sev.get('boost') or []):
            w = f'severity.boost[{n}]'
            if not _unknown(r, w, b, BOOST_KEYS):
                continue
            if 'in' in b:
                feature(w + '.in', b['in'])
            if 'flag' in b and b['flag'] not in FLAGS:
                r.err(w + '.flag', f"unknown flag {b['flag']!r} ({', '.join(FLAGS)})")
            if 'in' not in b and 'flag' not in b:
                r.err(w, 'a boost needs "in" (a feature) or "flag"')

    # PACE and phases
    pace = sc.get('pace') or []
    last = None
    for n, p in enumerate(pace):
        w = f'pace[{n}]'
        if not _unknown(r, w, p, PACE_KEYS):
            continue
        if p.get('level') not in engine.PACE_LEVELS:
            r.err(w + '.level', f"must be P, A, C or E, found {p.get('level')!r}")
        t = p.get('t')
        if not _num(t):
            r.err(w + '.t', 'expected a minute')
            continue
        if n == 0 and t != 0:
            r.err(w + '.t', 'the PACE timeline starts at 0')
        if last is not None and t <= last:
            r.err(w + '.t', f'times must ascend ({t:g} after {last:g})')
        if not 0 <= t <= duration:
            r.err(w + '.t', f'outside the run (0..{duration:g})')
        last = t
    if not pace:
        r.warn('pace', 'no PACE timeline: the run stays at P')
    phases = sc.get('phases') or []
    spans = []
    for n, p in enumerate(phases):
        w = f'phases[{n}]'
        if not _unknown(r, w, p, PHASE_KEYS):
            continue
        a, b = p.get('from'), p.get('to')
        if not (_num(a) and _num(b) and 0 <= a < b <= duration):
            r.err(w, f'from/to must be minutes with 0 <= from < to <= {duration:g}, found {a!r}..{b!r}')
            continue
        if not p.get('title'):
            r.err(w, 'missing "title"')
        spans.append((a, b, n))
    spans.sort()
    for (a1, b1, n1), (a2, b2, n2) in zip(spans, spans[1:]):
        if a2 < b1:
            r.err(f'phases[{n2}]', f'overlaps phases[{n1}] ({a2:g} < {b1:g})')

    # agencies
    agencies = sc.get('agencies') or {}
    for k, a in agencies.items():
        _unknown(r, f'agencies.{k}', a, AGENCY_KEYS)
    agency_ph = agency_placeholders(agencies)

    # templates
    wf = worker_fields()
    if not wf:
        r.warn('templates', 'the Worker forms were not found (templates/<form>/*_Worker.html): template field names not checked')
    templates = sc.get('templates') or {}
    tpl_form = {}
    for name, tpl in templates.items():
        w = f'templates.{name}'
        if not isinstance(tpl, dict):
            r.err(w, 'expected an object of Worker fields')
            continue
        for k, spec in tpl.items():
            if k == 'items':
                if not (isinstance(spec, dict) and set(spec) == {'range'}):
                    r.err(f'{w}.items', 'Supply Order items are {"range": {"<band>": {"<item code>": [min, max]}}}')
                else:
                    def items_band(ww, codes):
                        if not isinstance(codes, dict):
                            return r.err(ww, 'expected {"<item code>": [min, max]}')
                        for code, pr in codes.items():
                            _pair(r, f'{ww}.{code}', pr)
                            if wf.get('so') and code not in wf['so']:
                                r.err(f'{ww}.{code}', f'{code!r} is not an item on the Supply Order')
                    _bands(r, f'{w}.items.range', spec['range'], items_band)
                tpl_form.setdefault(name, set()).add('so')
            elif k == 'crew':
                if _unknown(r, f'{w}.crew', spec, {'count', 'hrs', 'wo'}):
                    for ck in ('count', 'hrs'):
                        if ck in spec:
                            _bands(r, f'{w}.crew.{ck}', spec[ck], lambda ww, x: _pair(r, ww, x))
                    if 'wo' in spec:
                        if not (isinstance(spec['wo'], dict) and set(spec['wo']) == {'pick'}):
                            r.err(f'{w}.crew.wo', 'expected {"pick": {"<band>": ["work order", ...]}}')
                        else:
                            _value(r, f'{w}.crew.wo', spec['wo'])
                tpl_form.setdefault(name, set()).add('wcl')
            else:
                _value(r, f'{w}.{k}', spec)
        _placeholders(r, w, _texts_of_value(tpl), UNIT_VALUES | agency_ph)

    # injects
    injects = sc.get('injects') or []
    ids = {}
    for n, inj in enumerate(injects):
        iid = inj.get('id') if isinstance(inj, dict) else None
        if not iid:
            r.err(f'injects[{n}]', 'missing "id"')
        elif iid in ids:
            r.err(f'injects[{n}] {iid!r}', f'duplicate id (also injects[{ids[iid]}])')
        else:
            ids[iid] = n
    per_unit = {}
    for inj in injects:
        if isinstance(inj, dict) and inj.get('id'):
            per_unit[inj['id']] = inj.get('each', 'once') in ('unit', 'stake')
    for inj in injects:                       # same_as inherits the units of the inject it copies
        if isinstance(inj, dict) and inj.get('same_as') in per_unit:
            per_unit[inj['id']] = per_unit[inj['same_as']]
    suffixes = derived_suffixes()
    for n, inj in enumerate(injects):
        if not isinstance(inj, dict):
            r.err(f'injects[{n}]', 'expected an object')
            continue
        w = f"injects[{n}] {inj.get('id', '?')!r}"
        _unknown(r, w, inj, INJECT_KEYS)
        kind = inj.get('kind', 'note')
        if kind not in KINDS:
            r.err(w + '.kind', f'unknown kind {kind!r} ({", ".join(KINDS)})')
        if inj.get('each', 'once') not in EACH:
            r.err(w + '.each', f"must be once, unit or stake, found {inj.get('each')!r}")
        if 'to' in inj and inj['to'] not in TO:
            r.err(w + '.to', f"must be one of {', '.join(TO)}, found {inj['to']!r}")
        if 't' not in inj and not inj.get('after'):
            r.warn(w, 'no "t": fires at T+0')
        if 't' in inj:
            _time(r, w + '.t', inj['t'], duration)
        if inj.get('same_as') and inj['same_as'] not in ids:
            r.err(w + '.same_as', f"no inject {inj['same_as']!r}")
        elif inj.get('same_as') and ids[inj['same_as']] > n:
            r.err(w + '.same_as', f"{inj['same_as']!r} comes later in the list: the engine expands injects in order, so it has no units yet")
        where = inj.get('where') or {}
        if _unknown(r, w + '.where', where, WHERE_KEYS):
            if 'in' in where:
                feature(w + '.where.in', where['in'])
            for k in ('severity', 'severity_min', 'severity_max'):
                if k in where and where[k] not in (0, 1, 2, 3):
                    r.err(f'{w}.where.{k}', 'must be 0..3')
            for k in ('flags_any', 'flags_none'):
                for fl in where.get(k) or []:
                    if fl not in FLAGS:
                        r.err(f'{w}.where.{k}', f'unknown flag {fl!r}')
            if 'sample' in where and not (_num(where['sample']) and where['sample'] >= 0):
                r.err(w + '.where.sample', 'a fraction (<= 1) or a count')
            if where and inj.get('each', 'once') == 'once' and not inj.get('same_as'):
                r.warn(w + '.where', 'ignored: the inject is not per unit ("each": "unit" or "stake")')
        # kind-specific
        if kind == 'form':
            if inj.get('form') not in FORMS:
                r.err(w + '.form', f"must be dr, so or wcl, found {inj.get('form')!r}")
            tname = inj.get('template', '')
            if tname not in templates:
                r.err(w + '.template', f'no template {tname!r} (the engine would skip this inject)')
            elif inj.get('form') in FORMS:
                tpl = templates[tname]
                fields = wf.get(inj['form'])
                if fields:
                    bad = [k for k in tpl if k not in fields and k not in ('items', 'crew')]
                    if bad:
                        r.err(w + '.template', f"template {tname!r} has fields that are not on the {engine.FORM_TITLES[inj['form']]} Worker: {', '.join(bad[:8])}")
                if (('items' in tpl) and inj['form'] != 'so') or (('crew' in tpl) and inj['form'] != 'wcl'):
                    r.err(w + '.template', f'template {tname!r} is for another form')
            if inj.get('channel', 'by_pace') not in FORM_CHANNELS:
                r.err(w + '.channel', f"must be one of {', '.join(FORM_CHANNELS)}, found {inj.get('channel')!r}")
            if not per_unit.get(inj.get('id')):
                r.err(w, 'a report comes from a unit: "each": "unit" (or "stake", or same_as a per-unit inject)')
        elif 'channel' in inj and kind != 'form':
            r.warn(w + '.channel', f'ignored for a {kind}')
        if kind == 'ics':
            if inj.get('form', 'ics213') not in ICS:
                r.err(w + '.form', f"must be ics213 or ics213rr, found {inj.get('form')!r}")
            if not isinstance(inj.get('fields', {}), dict):
                r.err(w + '.fields', 'expected an object of ICS form fields')
        ag = inj.get('agency')
        if ag is not None and ag not in agency_ph:
            r.err(w + '.agency', f'no agency {ag!r} in "agencies" (scenario or local binding)')
        if kind in ('work_item',) and not (inj.get('title') or inj.get('text')):
            r.err(w, 'a work item needs a "title"')
        if 'cat' in inj and inj['cat'] not in CATS:
            r.err(w + '.cat', f"unknown category {inj['cat']!r} ({', '.join(CATS)})")
        if 'prio' in inj and inj['prio'] not in (1, 2, 3):
            r.err(w + '.prio', 'must be 1, 2 or 3')
        if kind == 'reply':
            m = inj.get('match') or {}
            if _unknown(r, w + '.match', m, MATCH_KEYS):
                for c in ([m['cat']] if isinstance(m.get('cat'), str) else m.get('cat') or []):
                    if c not in CATS:
                        r.err(w + '.match.cat', f'unknown category {c!r}')
                for s in ([m['status']] if isinstance(m.get('status'), str) else m.get('status') or []):
                    if s not in WORK_STATES:
                        r.err(w + '.match.status', f'unknown status {s!r}')
            if 'status' in inj and inj['status'] not in REPLY_STATUS:
                r.err(w + '.status', f"must be done, progress or open, found {inj['status']!r}")
        elif 'match' in inj:
            r.warn(w + '.match', f'ignored for a {kind}')
        a = inj.get('after')
        if a is not None:
            if _unknown(r, w + '.after', a, AFTER_KEYS):
                target, _, suf = str(a.get('need', '')).partition('#')
                if target not in ids:
                    r.err(w + '.after.need', f'no inject {target!r}')
                elif suf and not any(suf == s or s.startswith(suf) for s in suffixes):
                    r.err(w + '.after.need', f'#{suf} is not a need the EOC derives ({", ".join(suffixes)})')
                if a.get('is', 'met') not in AFTER_IS:
                    r.err(w + '.after.is', f"must be one of {', '.join(AFTER_IS)}, found {a.get('is')!r}")
                if 'delay' in a and not (_num(a['delay']) and a['delay'] >= 0):
                    r.err(w + '.after.delay', 'expected minutes >= 0')
        nd = inj.get('need')
        if nd is not None:
            if _unknown(r, w + '.need', nd, NEED_KEYS):
                if 'cat' in nd and nd['cat'] not in CATS:
                    r.err(w + '.need.cat', f"unknown category {nd['cat']!r}")
                if 'form' in nd and nd['form'] not in FORMS:
                    r.err(w + '.need.form', 'must be dr, so or wcl')
                for s in nd.get('done_states') or []:
                    if s not in DONE_STATES:
                        r.err(w + '.need.done_states', f'unknown state {s!r}')
                for k in ('owner', 'done', 'typed'):
                    if k in nd and not (_num(nd[k]) and nd[k] > 0):
                        r.err(f'{w}.need.{k}', 'expected minutes > 0')
            if kind in ('voice', 'paper', 'prompt', 'note', 'ics') and not (nd.get('cat') or nd.get('form')):
                r.warn(w + '.need', 'a card need without "cat" or "form" matches any work item of the unit (category "other")')
        # placeholders
        texts = [str(inj.get(k)) for k in TEXT_KEYS if isinstance(inj.get(k), str)] + [str(v) for v in (inj.get('fields') or {}).values()]
        if isinstance(inj.get('need'), dict) and isinstance(inj['need'].get('label'), str):
            texts.append(inj['need']['label'])         # need labels are filled like the inject's text (per unit or once)
        if per_unit.get(inj.get('id')) or kind == 'rollup':
            _placeholders(r, w, texts, UNIT_VALUES | agency_ph)
        else:
            _placeholders(r, w, texts, ONCE_VALUES | agency_ph, UNIT_VALUES)

    # needs.defaults
    nds = sc.get('needs') or {}
    if _unknown(r, 'needs', nds, {'defaults'}):
        for cat, spec in (nds.get('defaults') or {}).items():
            w = f'needs.defaults.{cat}'
            if cat not in CATS + ('report',):
                r.err(w, f'unknown category {cat!r}')
            if _unknown(r, w, spec, NEED_RULE_KEYS):
                for s in spec.get('done_states') or []:
                    if s not in DONE_STATES:
                        r.err(w + '.done_states', f'unknown state {s!r}')

    # done-when checks
    done = sc.get('done') or {}
    if _unknown(r, 'done', done, {'checks'}):
        seen = set()
        for n, ck in enumerate(done.get('checks') or []):
            w = f"done.checks[{n}] {ck.get('id', '?')!r}" if isinstance(ck, dict) else f'done.checks[{n}]'
            if not _unknown(r, w, ck, DONE_CHECK_KEYS):
                continue
            types = [k for k in DONE_TYPES if k in ck]
            if len(types) != 1:
                r.err(w, f'needs exactly one of {", ".join(DONE_TYPES)}, found {types or "none"}')
            if not ck.get('label'):
                r.err(w, 'missing "label"')
            if ck.get('id') in seen:
                r.err(w, 'duplicate id')
            seen.add(ck.get('id'))
            if 'sitrep' in ck and not (isinstance(ck['sitrep'], int) and ck['sitrep'] >= 1 and _num(ck.get('by'))):
                r.err(w, '"sitrep": <n> with "by": <minute>')
            if 'need_met' in ck and ck['need_met'] not in ids:
                r.err(w + '.need_met', f"no inject {ck['need_met']!r}")
            if 'cat_met' in ck and ck['cat_met'] not in CATS:
                r.err(w + '.cat_met', f"unknown category {ck['cat_met']!r}")
            if 'pct_min' in ck and not (_num(ck['pct_min']) and 0 <= ck['pct_min'] <= 100):
                r.err(w + '.pct_min', 'a percentage')

    # hot wash
    for n, h in enumerate(sc.get('hotwash') or []):
        w = f'hotwash[{n}]'
        if not _unknown(r, w, h, HOTWASH_KEYS):
            continue
        if not h.get('check'):
            r.err(w, 'missing "check"')
        if 't' in h:
            _time(r, w + '.t', h['t'], duration)
        au = h.get('auto')
        if au is not None and _unknown(r, w + '.auto', au, AUTO_KEYS):
            it, ex = au.get('items') or {}, au.get('expect') or {}
            if _unknown(r, w + '.auto.items', it, AUTO_ITEMS):
                for c in ([it['cat']] if isinstance(it.get('cat'), str) else it.get('cat') or []):
                    if c not in CATS:
                        r.err(w + '.auto.items.cat', f'unknown category {c!r}')
            if _unknown(r, w + '.auto.expect', ex, AUTO_EXPECT):
                for s in ([ex['status_in']] if isinstance(ex.get('status_in'), str) else ex.get('status_in') or []):
                    if s not in DONE_STATES:
                        r.err(w + '.auto.expect.status_in', f'unknown status {s!r}')

    # role cards (filled once)
    for n, role in enumerate(sc.get('roles') or []):
        w = f"roles[{n}] {role.get('id', '?')!r}" if isinstance(role, dict) else f'roles[{n}]'
        if not _unknown(r, w, role, ROLE_KEYS):
            continue
        if not role.get('id') or not role.get('title'):
            r.err(w, 'a role needs "id" and "title"')
        _placeholders(r, w + '.title', [str(role.get('title', ''))], ONCE_VALUES | agency_ph, UNIT_VALUES)
        for m, c in enumerate(role.get('cards') or []):
            cw = f'{w}.cards[{m}]'
            if not _unknown(r, cw, c, CARD_KEYS):
                continue
            if 't' not in c or not c.get('text'):
                r.err(cw, 'a card needs "t" and "text"')
            elif not _num(c['t']) or c['t'] > duration:          # before T+0 is fine: the briefing
                r.err(cw + '.t', f'a minute up to {duration:g} (negative: before the start)')
            _placeholders(r, cw, [str(c.get('text', ''))], ONCE_VALUES | agency_ph, UNIT_VALUES)

    # EOCs the scenario suggests
    eocs = sc.get('eocs') or {}
    if isinstance(eocs, dict):
        for k, v in eocs.items():
            if k not in EOCS_KEYS:
                r.err('eocs', f'unknown EOC {k!r} (satellite, area)')
            elif _unknown(r, f'eocs.{k}', v, EOCS_KEYS[k]) and k == 'satellite' and isinstance(v.get('where'), dict):
                if _unknown(r, 'eocs.satellite.where', v['where'], WHERE_KEYS) and 'in' in v['where']:
                    feature('eocs.satellite.where.in', v['where']['in'])

    # catalog
    if catalog is not None:
        if not any(isinstance(s, dict) and s.get('id') == sc.get('id') for s in catalog.get('scenarios', [])):
            r.warn('catalog', f"no entry for {sc.get('id')!r} in {catalog_label or 'the catalog'}: the simulator's Setup tab will not list it")

    # with a pack: plan once
    if pack is not None and not r.errors:
        _plan_checks(r, sc, pack, injects)
    elif pack is not None:
        r.info.append('planning over the pack skipped: fix the errors first')
    return r.as_dict()


def _plan_checks(r: Report, sc: dict, pack: dict, injects: list):
    import orgpack
    names = {u['name'] for u in pack.get('units', [])}
    for u in sc.get('severity_override') or {}:
        if u not in names:
            r.err('severity_override', f'no unit named {u!r} in the pack')
    for n, inj in enumerate(injects):
        wh = inj.get('where') or {}
        for u in ([wh['unit']] if wh.get('unit') else []) + list(wh.get('units') or []):
            if u not in names:
                r.err(f"injects[{n}] {inj.get('id', '?')!r}.where", f'no unit named {u!r} in the pack')
    try:
        run = engine.plan(pack, sc, {'seed': 1, 'today': '2027-01-01'})
    except Exception as e:
        r.err('plan', f'planning over the pack failed: {type(e).__name__}: {e}')
        return
    per = {}
    for it in run['items']:
        per[it['inject']] = per.get(it['inject'], 0) + 1
    zero = [inj['id'] for inj in injects if inj.get('each', 'once') in ('unit', 'stake') or inj.get('same_as')]
    zero = [i for i in zero if not per.get(i)]
    for i in zero:
        r.warn(f'plan {i!r}', 'reaches no unit of this pack (its "where" selects nothing)')
    left = sorted({m for it in run['items'] for m in PLACEHOLDER.findall(json.dumps([it.get('text'), it.get('work'), it.get('payload'), it.get('ics'), it.get('reply')]))})
    left += sorted({m for role in run.get('roles', []) for m in PLACEHOLDER.findall(json.dumps(role))})
    for m in sorted(set(left)):
        r.err('plan', f'{{{m}}} is left unfilled after planning over the pack')
    bands = [0, 0, 0, 0]
    for u in run['scope']['units']:
        bands[u['severity']] += 1
    r.info.append(f"planned over the pack: {len(run['scope']['units'])} units, severity 0/1/2/3 = {'/'.join(map(str, bands))}, "
                  f"{len(run['items'])} items, {len(run['needs'])} needs at planning, {len(zero)} inject(s) reach no unit")
    if not any(bands[1:]):
        r.warn('plan', 'every unit of the pack is in band 0: the scenario does not touch this pack')
    try:
        bbox = orgpack.Index(pack).bbox()
        if (sc.get('applies') or {}).get('bbox') and bbox and engine.bbox_overlaps(sc['applies']['bbox'], bbox) is False:
            r.warn('applies.bbox', 'does not overlap the pack')
    except Exception:
        pass


def check_files(scenario_path, pack_path=None, local_path=None, catalog_path=None) -> dict:
    """check() from files: the local binding and catalog default to the ones beside the scenario (a pack's
    <export>/simulation/<id>.local.json, the scenarios folder's catalog.json)."""
    sp = Path(scenario_path)
    sc = json.loads(sp.read_text(encoding='utf-8-sig'))
    local = None
    if local_path:
        local = json.loads(Path(local_path).read_text(encoding='utf-8-sig'))
    else:
        guess = sp.parent.parent / f"{sc.get('id', sp.stem)}.local.json"      # <export>/simulation/scenarios/<id>.json -> <export>/simulation/<id>.local.json
        if sp.parent.name == 'scenarios' and guess.is_file():
            local = json.loads(guess.read_text(encoding='utf-8-sig'))
    cat_p = Path(catalog_path) if catalog_path else sp.parent / 'catalog.json'
    catalog = json.loads(cat_p.read_text(encoding='utf-8-sig')) if cat_p.is_file() else {'scenarios': []}
    if not catalog_path and sp.parent.resolve() != engine.SCENARIOS_DIR.resolve():
        # a pack's own scenario may also be listed by the built-in catalog
        try:
            catalog = {'scenarios': catalog.get('scenarios', []) + engine.catalog()['scenarios']}
        except Exception:
            pass
    pack = None
    if pack_path:
        import orgpack
        pack = orgpack.load(pack_path)
    res = check(sc, local, pack, catalog, str(cat_p))
    res['scenario'] = sc.get('id', sp.stem)
    res['local_binding'] = bool(local)
    return res


def main(argv) -> int:
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 2
    opt = lambda k: argv[argv.index(k) + 1] if k in argv and argv.index(k) + 1 < len(argv) else None
    try:
        res = check_files(argv[0], opt('--pack'), opt('--local'), opt('--catalog'))
    except (OSError, ValueError) as e:
        print(f'ERROR {e}')
        return 1
    print(f"Scenario {res['scenario']}" + (' (with its local binding)' if res['local_binding'] else ''))
    for e in res['errors']:
        print(f'  ERROR    {e}')
    for w in res['warnings']:
        print(f'  WARNING  {w}')
    for i in res['info']:
        print(f'  info     {i}')
    print(f"{len(res['errors'])} error(s), {len(res['warnings'])} warning(s)")
    return 1 if res['errors'] else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
