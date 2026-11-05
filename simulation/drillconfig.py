#!/usr/bin/env python3
"""Drill configuration: one file that sets up every EOC of a drill (Python standard library only).

A drill SPEC (written by the drill director, kept beside the pack in ``secure data/``) names the EOCs of a drill:
which stake or councils each one serves, the building it sits in, whether people always staff it or only
optionally, and its Winlink call sign. This module turns the spec plus the organization pack into a drill
CONFIGURATION (``church_emcomm_drill_config``) that

  * the EOC server loads (Message Center → Setup → Load drill configuration, or
    ``eoc_server.py --config=<file> --eoc=<id> [--manned=<id,id>]``): EOC identity (level, name, units, location,
    the EOC above, the council line and the welfare line, must-have roles), the map data folder, the Winlink
    call sign that feeds it, and a drill event;
  * the simulator loads (Setup → Load drill configuration): the pack, the privacy mode, the scenario and what this
    simulator plays, given which optional EOCs have people this time.

Names, phones and emails come from the pack in the spec's privacy mode (pseudonymized by default: invented first
names, ...-555-01xx phones, @churchemcomm.sim emails). The configuration holds organization names and pseudonyms, so
it lives in ``secure data/`` with the pack and is never committed. This module holds no organization data.

    python simulation/drillconfig.py "<spec.json>"                 # checks the spec, writes drill-config.json beside it
    python simulation/drillconfig.py "<spec.json>" --out <file>
    python simulation/drillconfig.py "<spec.json>" --check         # only check the spec against the pack

validate_spec(spec, pack) lists the spec's mistakes (unknown keys, manned and level values, call-sign shapes, a
starter's "(edit ...)" or "<...>" text left in, stakes, councils, buildings and agencies' `serves` that are not in
the pack); the command prints them and stops without writing anything.
"""
import json
import os
import re
import sys
from pathlib import Path

CONFIG_KIND = 'church_emcomm_drill_config'
SPEC_KIND = 'church_emcomm_drill_spec'
SIM_DOMAIN = 'churchemcomm.sim'
LEVEL_LABEL = {'stake': 'Stake EOC', 'satellite': 'Satellite EOC', 'area': 'Council / Area EOC'}


def _slug(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', (s or '').lower()).strip('-') or 'eoc'


def _by_name(items, name):
    n = (name or '').strip().lower()
    return next((x for x in items if (x.get('name') or '').strip().lower() == n or x.get('id') == name), None)


def _contact(pack, org_id, *roles):
    ids = {c['id']: c for c in pack['contacts']}
    for role in roles:
        for c in pack['contacts']:
            if c.get('org') == org_id and c.get('role') == role:
                return c
    return None


def _who(c, title=''):
    if not c:
        return {}
    return {'name': c.get('name', ''), 'phone': c.get('mobile') or c.get('phone') or '', 'email': c.get('email', ''),
            'title': title or c.get('role', '')}


SPEC_KEYS = {'kind', 'v', 'name', 'scenario', 'export', 'privacy', 'event', 'eocs', 'agencies', 'note'}
EVENT_KEYS = {'name', 'type', 'sitrepHrs', 'sitrepBy', 'area', 'note'}
EOC_KEYS = {'id', 'level', 'stake', 'councils', 'manned', 'winlink', 'building', 'name', 'note'}
AGENCY_KEYS = {'id', 'name', 'call', 'contact', 'place', 'forms', 'serves', 'note'}
# an amateur call sign (W9TLH, KB7FUB-10) or a Winlink tactical address (SIM-LKS, CITYEOC): letters, digits, one hyphen
CALL_RE = re.compile(r'^(?=.*[A-Z])[A-Z0-9]{2,10}(?:-[A-Z0-9]{1,10})?$')
LEFTOVER_RE = re.compile(r'\(edit\b|<[^<>]{1,60}>', re.I)


def validate_spec(spec: dict, pack: dict = None) -> list:
    """The mistakes in a drill spec, as plain sentences (empty when it is fine). With the pack, the stakes, councils,
    buildings and the agencies' `serves` are looked up in it."""
    errs = []
    if not isinstance(spec, dict):
        return ['the spec is not a JSON object']

    def unknown(where, obj, known):
        if not isinstance(obj, dict):
            errs.append(f'{where}: expected an object')
            return False
        for k in obj:
            if k not in known and not k.endswith('_note'):
                errs.append(f'{where}: unknown key {k!r} (known: {", ".join(sorted(known))})')
        return True

    if spec.get('kind') != SPEC_KIND:
        errs.append(f'"kind" must be {SPEC_KIND!r}')
    unknown('spec', spec, SPEC_KEYS)
    if spec.get('privacy', 'pseudonymized') not in ('pseudonymized', 'real'):
        errs.append(f"privacy: must be pseudonymized or real, found {spec.get('privacy')!r}")
    if not str(spec.get('scenario') or '').strip():
        errs.append('scenario: missing (the id of the scenario this drill plays)')
    if 'event' in spec:
        unknown('event', spec['event'], EVENT_KEYS)

    def leftovers(where, obj):
        if isinstance(obj, str):
            m = LEFTOVER_RE.search(obj)
            if m:
                errs.append(f'{where}: starter text left in ({m.group(0)!r}): replace it')
        elif isinstance(obj, dict):
            for k, v in obj.items():
                if k != 'note' and not k.endswith('_note'):
                    leftovers(f'{where}.{k}', v)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                leftovers(f'{where}[{i}]', v)

    for k, v in spec.items():
        if k != 'note':
            leftovers(k, v)
    stakes = {s['name'].strip().lower() for s in (pack or {}).get('stakes', [])} | {s['id'] for s in (pack or {}).get('stakes', [])}
    councils = {c['name'].strip().lower() for c in (pack or {}).get('councils', [])} | {c['id'] for c in (pack or {}).get('councils', [])}
    blds = {b['id'] for b in (pack or {}).get('buildings', [])}
    ids = set()
    eocs = spec.get('eocs')
    if not isinstance(eocs, list) or not eocs:
        errs.append('eocs: expected a list of at least one EOC')
        eocs = []
    for n, e in enumerate(eocs):
        w = f"eocs[{n}] {e.get('id', '?')!r}" if isinstance(e, dict) else f'eocs[{n}]'
        if not unknown(w, e, EOC_KEYS):
            continue
        eid = e.get('id') or _slug(e.get('name', ''))
        if eid in ids:
            errs.append(f'{w}: duplicate id')
        ids.add(eid)
        level = e.get('level', 'stake')
        if level not in LEVEL_LABEL:
            errs.append(f'{w}: level must be stake, satellite or area, found {level!r}')
        if e.get('manned', 'always') not in ('always', 'optional'):
            errs.append(f"{w}: manned must be always or optional, found {e.get('manned')!r}")
        calls = e.get('winlink') or []
        if not isinstance(calls, list):
            errs.append(f'{w}: winlink must be a list of call signs')
            calls = []
        for c in calls:
            if not CALL_RE.match(str(c).strip().upper()):
                errs.append(f'{w}: {c!r} is not a call sign or Winlink tactical address (letters, digits, one hyphen; no @winlink.org)')
        if pack is not None:
            if level in ('stake', 'satellite') and str(e.get('stake') or '').strip().lower() not in stakes and e.get('stake') not in stakes:
                errs.append(f"{w}: stake {e.get('stake')!r} is not in the pack")
            if level == 'area':
                for c in e.get('councils') or []:
                    if str(c).strip().lower() not in councils and c not in councils:
                        errs.append(f'{w}: council {c!r} is not in the pack')
            if e.get('building') and e['building'] not in blds:
                errs.append(f"{w}: building {e['building']!r} is not in the pack")
        elif level in ('stake', 'satellite') and not e.get('stake'):
            errs.append(f'{w}: a {level} EOC names its stake')
    if sum(1 for e in eocs if isinstance(e, dict) and e.get('level') == 'area') > 1:
        errs.append('eocs: at most one Council / Area EOC')
    agencies = spec.get('agencies') or []
    if not isinstance(agencies, list):
        errs.append('agencies: expected a list')
        agencies = []
    for n, a in enumerate(agencies):
        w = f"agencies[{n}] {a.get('id', '?')!r}" if isinstance(a, dict) else f'agencies[{n}]'
        if not unknown(w, a, AGENCY_KEYS):
            continue
        if not a.get('id') or not a.get('name'):
            errs.append(f'{w}: an agency needs "id" and "name"')
        if a.get('call') and not CALL_RE.match(str(a['call']).strip().upper()):
            errs.append(f"{w}: call {a['call']!r} is not a call sign or Winlink tactical address")
        serves = a.get('serves') or []
        if not isinstance(serves, list):
            errs.append(f'{w}: serves must be a list of stake names')
        elif pack is not None:
            for s in serves:
                if str(s).strip().lower() not in stakes and s not in stakes:
                    errs.append(f'{w}: serves {s!r}, which is not a stake in the pack')
    return errs


def build(pack: dict, spec: dict, export_path: str = '') -> dict:
    """The drill configuration for a spec over a (pseudonymized or real) pack."""
    if spec.get('kind') != SPEC_KIND:
        raise ValueError(f'not a {SPEC_KIND}')
    blds = {b['id']: b for b in pack['buildings']}
    councils = {c['id']: c for c in pack.get('councils', [])}
    welfare = pack.get('welfare') or {}
    region = welfare.get('region') or {}
    office = welfare.get('area_office') or {}
    wsrm = _contact(pack, region.get('id'), 'Welfare and Self-Reliance Manager')
    awsrm = _contact(pack, office.get('id'), 'Area Welfare and Self-Reliance Manager') or _contact(pack, region.get('id'), 'Area Welfare and Self-Reliance Manager')
    map_path = os.path.abspath(export_path) if export_path else ''   # keeps the drive letter (resolve() turns a mapped drive into \server\share)
    out_eocs, errors = [], []
    area_spec = next((e for e in spec.get('eocs', []) if e.get('level') == 'area'), None)

    for e in spec.get('eocs', []):
        eid, level = e.get('id') or _slug(e.get('name', '')), e.get('level', 'stake')
        rec = {'id': eid, 'level': level, 'manned': e.get('manned', 'always'), 'winlink': [c.upper() for c in (e.get('winlink') or [])]}
        if level in ('stake', 'satellite'):
            st = _by_name(pack['stakes'], e.get('stake'))
            if not st:
                errors.append(f"{eid}: stake {e.get('stake')!r} is not in the pack"); continue
            b = blds.get(e.get('building') or st.get('center_building')) or {}
            units = [u for u in pack['units'] if u.get('stake') == st['id']]
            council = councils.get(st.get('council')) or {}
            seventy = _contact(pack, council.get('id'), 'Area Seventy')
            sp = _contact(pack, st['id'], 'Stake President')
            erd = _contact(pack, st['id'], 'Emergency Response Director')
            spec_c = _contact(pack, st['id'], 'Welfare and Self-Reliance Specialist', 'Stake Welfare and Self-Reliance Specialist')
            name = e.get('name') or f"{st['name']} EOC"
            rec.update({'name': name, 'stake': st['id'], 'stake_name': st['name'], 'council': council.get('id', ''), 'council_name': council.get('name', ''),
                        'units': [u['id'] for u in units], 'unit_names': [u['name'] for u in units]})
            ident = {'eocLevel': level, 'eocName': name, 'eocUnits': ', '.join(u['name'] for u in units),
                     'eocLat': str(b.get('lat', '')), 'eocLon': str(b.get('lon', '')), 'mapPath': map_path,
                     'councilName': f"{council.get('name', '')}" + (f" — {seventy['name']}, Area Seventy" if seventy else ''),
                     'councilEmail': (seventy or {}).get('email', ''), 'councilWinlink': '',
                     'welfareName': f"{region.get('name', 'Welfare region')}" + (f" — {wsrm['name']}, WSRM" if wsrm else ''),
                     'welfareEmail': (wsrm or {}).get('email', ''), 'welfareWinlink': '',
                     'parentName': '', 'parentEmail': '', 'parentWinlink': '',
                     'roles': {k: {'name': v.get('name', ''), 'phone': v.get('phone', '')} for k, v in
                               (('sp', _who(sp)), ('erd', _who(erd)), ('specialist', _who(spec_c))) if v}}
            if rec['winlink']:
                ident['roles']['ham'] = {'name': f"{name} Winlink station", 'phone': ', '.join(rec['winlink'])}
            rec['sim'] = {'role': level, 'stake': st['id']}
        else:
            cids = []
            for cn in e.get('councils') or []:
                c = _by_name(list(councils.values()), cn)
                if c: cids.append(c['id'])
                else: errors.append(f"{eid}: council {cn!r} is not in the pack")
            b = blds.get(e.get('building')) or {}
            if e.get('building') and not b:
                errors.append(f"{eid}: building {e.get('building')!r} is not in the pack")
            stakes = [s for s in pack['stakes'] if s.get('council') in cids]
            seventies = [x for x in (_contact(pack, c, 'Area Seventy') for c in cids) if x]
            name = e.get('name') or ('Council / Area EOC — ' + ', '.join(councils[c]['name'] for c in cids))
            rec.update({'name': name, 'councils': cids, 'council_names': [councils[c]['name'] for c in cids],
                        'stakes': [s['id'] for s in stakes], 'stake_names': [s['name'] for s in stakes]})
            ident = {'eocLevel': 'area', 'eocName': name, 'eocUnits': ', '.join(s['name'] for s in stakes),
                     'eocLat': str(b.get('lat', '')), 'eocLon': str(b.get('lon', '')), 'mapPath': map_path,
                     'councilName': ' · '.join(f"{councils[c]['name']}" + (f" — {s7['name']}, Area Seventy" if s7 else '')
                                               for c, s7 in zip(cids, [_contact(pack, c, 'Area Seventy') for c in cids])),
                     'councilEmail': ', '.join(x['email'] for x in seventies if x.get('email')), 'councilWinlink': '',
                     'welfareName': f"{office.get('name', 'Area welfare office')}" + (f" — {awsrm['name']}, AWSRM" if awsrm else ''),
                     'welfareEmail': (awsrm or {}).get('email', ''), 'welfareWinlink': '',
                     'parentName': '', 'parentEmail': '', 'parentWinlink': '',
                     'roles': {'seventy': {'name': ', '.join(x['name'] for x in seventies), 'phone': ', '.join(x.get('mobile') or x.get('phone') or '' for x in seventies)}}}
            if wsrm:
                ident['roles']['wsrm'] = {'name': wsrm['name'], 'phone': wsrm.get('mobile') or wsrm.get('phone') or ''}
            if rec['winlink']:
                ident['roles']['ham'] = {'name': f"{name} Winlink station", 'phone': ', '.join(rec['winlink'])}
            rec['sim'] = {'role': 'area', 'councils': cids}
        rec['email'] = f"{_slug(rec['name'])}@{SIM_DOMAIN}"
        # partner agencies that do not run this system (a city EOC): who they are and their Winlink call sign, for the EOCs
        # they work with (`serves`: stake names; empty = every EOC). Their traffic is ICS 213 / 213RR, never Church forms.
        serve_names = {rec.get('stake_name', '')} | set(rec.get('stake_names') or [])
        ident['agencies'] = [{k: a.get(k, '') for k in ('id', 'name', 'call', 'contact', 'place', 'forms')}
                             for a in spec.get('agencies', []) if not a.get('serves') or serve_names & set(a['serves'])]
        rec['building'] = {k: b.get(k, '') for k in ('id', 'name', 'address', 'lat', 'lon')} if b else {}
        rec['identity'] = ident
        out_eocs.append(rec)

    # When the Area EOC has people, the stake EOCs report to it: their "EOC above" fields
    area = next((r for r in out_eocs if r['level'] == 'area'), None)
    for r in out_eocs:
        if area and r is not area:
            r['ifAreaManned'] = {'parentName': area['name'], 'parentEmail': area['email'], 'parentWinlink': ', '.join(area['winlink'])}
    if errors:
        raise ValueError('; '.join(errors))
    return {'kind': CONFIG_KIND, 'v': 1, 'name': spec.get('name', 'Drill'), 'scenario': spec.get('scenario', ''),
            'privacy': pack.get('privacy', 'pseudonymized'), 'pack': map_path, 'event': dict(spec.get('event') or {}),
            'eocs': out_eocs, 'area': area['id'] if area else '',
            'note': 'Built by simulation/drillconfig.py from the drill spec and the organization pack. Holds organization names and '
                    'pseudonymized contacts: keep it in secure data/, never commit it.'}


# ── used by the EOC server and the simulator (copies of these two small rules live in eoc_server.py) ──
def manned_set(config: dict, manned=None) -> set:
    """The EOCs with people this time: every 'always' EOC plus the optional ones named in ``manned``."""
    want = {m.strip() for m in (manned or []) if m and m.strip()}
    return {e['id'] for e in config.get('eocs', []) if e.get('manned', 'always') == 'always' or e['id'] in want}


def identity_for(config: dict, eoc_id: str, manned=None) -> dict:
    e = next((x for x in config.get('eocs', []) if x['id'] == eoc_id), None)
    if not e:
        raise KeyError(f'{eoc_id}: not an EOC of this drill configuration')
    ident = json.loads(json.dumps(e['identity']))
    on = manned_set(config, manned)
    if config.get('area') in on and e['level'] != 'area':
        ident.update(e.get('ifAreaManned') or {})
    return ident


def site_for(config: dict, eoc_id: str, manned=None) -> dict:
    """What the simulator at this EOC plays (engine.resolve_site input)."""
    e = next((x for x in config.get('eocs', []) if x['id'] == eoc_id), None)
    if not e:
        raise KeyError(f'{eoc_id}: not an EOC of this drill configuration')
    on = manned_set(config, manned)
    area = next((x for x in config['eocs'] if x['id'] == config.get('area')), None)
    if e['level'] == 'area':
        played = [x['sim']['stake'] for x in config['eocs'] if x['level'] in ('stake', 'satellite') and x['id'] in on]
        return {'role': 'area', 'councils': e['sim']['councils'], 'played_stakes': played}
    area_on = bool(area) and area['id'] in on
    return {'role': e['level'], 'stake': e['sim']['stake'], 'parent': area['name'] if area_on else '', 'played_parent': area_on}


def main(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__); return 2
    spec_path = Path(argv[0])
    try:
        spec = json.loads(spec_path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as e:
        print(f'{spec_path}: cannot read the drill spec: {e}')
        return 1
    out = Path(argv[argv.index('--out') + 1]) if '--out' in argv else spec_path.with_name('drill-config.json')
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import orgpack, privacy
    export = Path((spec.get('export') if isinstance(spec, dict) else '') or '.')
    if not export.is_absolute():
        export = Path(os.path.abspath(spec_path.parent / export))
    try:
        pack = orgpack.load(export)
    except Exception as e:
        print(f'{spec_path}: the organization pack at {export} does not load ("export" in the spec): {type(e).__name__}: {e}')
        return 1
    errs = validate_spec(spec, pack)
    if errs:
        print(f'{spec_path}: {len(errs)} problem(s) in the drill spec, nothing written:')
        for e in errs:
            print(f'  - {e}')
        return 1
    if '--check' in argv:
        print(f'{spec_path}: the drill spec is fine ({len(spec["eocs"])} EOCs)')
        return 0
    mode = spec.get('privacy', 'pseudonymized')
    pack = privacy.apply(pack, mode, privacy.salt_for(export) if mode == 'pseudonymized' else '')
    try:
        cfg = build(pack, spec, str(export))
    except ValueError as e:
        print(f'{spec_path}: {e}')
        return 1
    out.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{out}: {len(cfg["eocs"])} EOCs ({", ".join(e["id"] + ":" + e["manned"] for e in cfg["eocs"])}), privacy {cfg["privacy"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
