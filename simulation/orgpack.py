#!/usr/bin/env python3
"""Organization pack for the EMCOMM simulator (Python standard library only).

A pack is one JSON object with everything the simulator needs to know about the
organizations it plays: councils, stakes, wards and branches, buildings, the welfare
line and the leaders' contact details. It is built from a CDOL export folder
(``csv/*.csv`` plus ``simulator/*.geojson``) or read from a prepared ``orgpack.json``
of the same shape, so an area without a CDOL extract can write the JSON by hand.

Packs hold names, addresses and contact details. They live OUTSIDE the repository
(``secure data/`` or a folder the user picks) and are never shipped or committed.
This module contains no organization data of its own.

    python simulation/orgpack.py "<export root>"              # build and print a summary
    python simulation/orgpack.py "<export root>" --out p.json  # build and save
"""
import csv
import json
import re
import sys
from pathlib import Path

PACK_KIND = 'church_emcomm_orgpack'
UNIT_TYPES = ('Ward', 'Branch')
STAKE_ROLES = ('Stake President', 'Stake Presidency First Counselor', 'Stake Presidency Second Counselor',
               'Stake Clerk', 'Stake Executive Secretary', 'Stake Assistant Clerk')
UNIT_ROLES = ('Bishop', 'Branch President', 'Bishopric First Counselor', 'Bishopric Second Counselor',
              'Branch Presidency First Counselor', 'Branch Presidency Second Counselor',
              'Ward Clerk', 'Branch Clerk', 'Ward Executive Secretary', 'Branch Executive Secretary',
              'Ward Assistant Clerk', 'Ward Assistant Clerk--Finance', 'Ward Assistant Clerk--Membership')
WELFARE_ROLES = ('Area Welfare and Self-Reliance Manager', 'Welfare and Self-Reliance Manager',
                 'Humanitarian Specialist', 'WSRS Senior Service Missionary')
COUNCIL_ROLES = ('Area Seventy',)
STATE_ABBR = {'utah': 'UT', 'idaho': 'ID', 'wyoming': 'WY', 'nevada': 'NV', 'arizona': 'AZ', 'colorado': 'CO',
              'montana': 'MT', 'oregon': 'OR', 'washington': 'WA', 'california': 'CA', 'new mexico': 'NM'}
NAME_SUFFIXES = {'jr', 'jr.', 'sr', 'sr.', 'ii', 'iii', 'iv'}
# Unit-name keywords that mark a care-facility or retirement branch (special units
# whose members live in one facility rather than in a geographic area).
CARE_WORDS = ('care', 'center', 'centre', 'nursing', 'rehab', 'health', 'assisted', 'living', 'manor', 'home',
              'transitional', 'senior', 'villa', 'hospital', 'lodge', 'gardens', 'house', 'springs', 'terrace', 'place')
RETIRE_WORDS = ('retirement', 'retire')


def _read_csv(root: Path, name: str, optional: bool = False) -> list:
    p = root / 'csv' / name
    if optional and not p.is_file():
        return []
    with open(p, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def _read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def split_name(full: str) -> tuple:
    """'First M. Last' -> ('First', 'Last'); suffixes (Jr., III) are dropped from the last name."""
    parts = [p for p in re.split(r'\s+', (full or '').strip()) if p]
    if not parts:
        return '', ''
    if len(parts) > 1 and parts[-1].lower() in NAME_SUFFIXES:
        parts = parts[:-1]
    if len(parts) == 1:
        return parts[0], ''
    return parts[0], parts[-1]


def parse_address(raw: str) -> dict:
    """Street / city / state / ZIP from the multi-line CDOL address text.
    Lines look like '123 N 400 E' / 'Larkspur, Westland 89701-1234' / 'United States';
    some have a facility name or room first. Returns '' for anything not found."""
    lines = [ln.strip() for ln in (raw or '').replace('\r', '').split('\n') if ln.strip()]
    out = {'street': '', 'city': '', 'state': '', 'zip': ''}
    for i, ln in enumerate(lines):
        m = re.match(r'^(.*?),?\s+([A-Za-z][A-Za-z ]*?)\s+(\d{5})(?:-\d{4})?$', ln)
        if m and m.group(1):
            st = m.group(2).strip()
            out['city'] = m.group(1).strip().title() if m.group(1).isupper() else m.group(1).strip()
            out['state'] = STATE_ABBR.get(st.lower(), st.upper() if len(st) == 2 else st)
            out['zip'] = m.group(3)
            out['street'] = ' / '.join(x for x in lines[:i] if not x.lower().startswith('united states'))
            break
    if not out['street'] and lines:
        out['street'] = lines[0]
    return out


def _flags_for(name: str, org_type: str, special: bool) -> list:
    if not special:
        return []
    low = name.lower()
    if 'spanish' in low or '(' in low and ')' in low and org_type == 'Ward':
        return ['language_unit']
    if any(w in low for w in RETIRE_WORDS):
        return ['retirement']
    if org_type == 'Branch' or any(w in low for w in CARE_WORDS):
        return ['care_facility']
    return ['language_unit']


def read_export(root) -> dict:
    """Build a pack from a CDOL export folder (docs/COMMUNITY_SETUP.md describes the layout). organizations.csv,
    buildings.csv and building_organizations.csv are required; contacts, contact methods, relationships and the
    simulator/ map folder are optional (no leaders, no participation links, no boundaries when they are absent)."""
    root = Path(root)
    orgs = _read_csv(root, 'organizations.csv')
    contacts = _read_csv(root, 'contacts.csv', optional=True)
    methods = _read_csv(root, 'contactmethods.csv', optional=True)
    rels = _read_csv(root, 'relationships.csv', optional=True)
    bo = _read_csv(root, 'building_organizations.csv')
    blds = _read_csv(root, 'buildings.csv')
    bp = root / 'simulator' / 'organization_boundaries.geojson'
    gj = _read_json(bp) if bp.is_file() else {'features': []}
    props = {f['properties']['org_id']: (f['properties'], f.get('geometry')) for f in gj.get('features', [])}

    O = {o['org_id']: o for o in orgs}
    B = {b['building_id']: b for b in blds}
    bo_by_org = {b['org_id']: b for b in bo}
    # contact methods per position (person) and per organization
    pm, om = {}, {}
    for m in methods:
        if m['owner_kind'] == 'Person':
            pm.setdefault(m['position_id'], []).append(m)
        else:
            om.setdefault(m['org_id'], []).append(m)

    def org_phone(oid, kinds=('MEETINGHOUSE_PHONE', 'OFFICE_PHONE')):
        for k in kinds:
            for m in om.get(oid, []):
                if m['contact_type'] == k and m['contact_value']:
                    return m['contact_value']
        return ''

    def org_email(oid):
        for m in om.get(oid, []):
            if m['contact_kind'] == 'Email' and m['contact_value']:
                return m['contact_value']
        return ''

    pack_contacts, leaders_of = [], {}
    for c in contacts:
        role = c['role_name']
        if role not in STAKE_ROLES + UNIT_ROLES + WELFARE_ROLES + COUNCIL_ROLES:
            continue
        ms = pm.get(c['position_id'], [])
        mobile = next((m['contact_value'] for m in ms if m['contact_type'] == 'Mobile Phone' and m['contact_value']), '')
        phone = mobile or next((m['contact_value'] for m in ms if m['contact_kind'] == 'Phone' and m['contact_value']), '') or c['primary_phone']
        email = next((m['contact_value'] for m in ms if m['contact_kind'] == 'Email' and m['contact_value']), '') or c['primary_email']
        first, last = split_name(c['person_name'])
        rec = {'id': c['position_id'], 'person': c['person_id'], 'role': role, 'org': c['org_id'],
               'name': c['person_name'], 'first': first, 'last': last,
               'mobile': mobile, 'phone': phone, 'email': email}
        pack_contacts.append(rec)
        leaders_of.setdefault(c['org_id'], []).append(rec['id'])

    def bbox_of(geom):
        if not geom:
            return None
        polys = [geom['coordinates']] if geom['type'] == 'Polygon' else geom['coordinates']
        xs = [pt[0] for poly in polys for ring in poly for pt in ring]
        ys = [pt[1] for poly in polys for ring in poly for pt in ring]
        return [min(xs), min(ys), max(xs), max(ys)] if xs else None

    def rings_of(geom):
        if not geom:
            return []
        polys = [geom['coordinates']] if geom['type'] == 'Polygon' else geom['coordinates']
        return [[[pt[0], pt[1]] for pt in poly[0]] for poly in polys]   # outer rings only

    def place(oid):
        b = B.get(bo_by_org.get(oid, {}).get('building_id', ''))
        if not b:
            return None
        a = parse_address(b['address_raw'])
        return {'building': b['building_id'], 'lat': float(b['latitude']) if b['latitude'] else None,
                'lon': float(b['longitude']) if b['longitude'] else None, 'address': b['address_raw'].replace('\n', ', '),
                'street': a['street'], 'city': a['city'], 'state': a['state'], 'zip': a['zip']}

    # participation links: a language unit draws members from several stakes
    # (CDOL records it both ways: unit --Participating Units--> stake and stake --Participating with--> unit)
    draws = {}
    for r in rels:
        if not r['relationship_type'].startswith('Participating'):
            continue
        a, b = r['from_org_id'], r['to_org_id']
        if O.get(a, {}).get('org_type') in UNIT_TYPES and O.get(b, {}).get('org_type') == 'Stake':
            draws.setdefault(a, [])
            if b not in draws[a]:
                draws[a].append(b)
        elif O.get(b, {}).get('org_type') in UNIT_TYPES and O.get(a, {}).get('org_type') == 'Stake':
            draws.setdefault(b, [])
            if a not in draws[b]:
                draws[b].append(a)

    councils, stakes, units, buildings = [], [], [], {}
    for o in orgs:
        t = o['org_type']
        if t == 'Area Coordinating Council':
            councils.append({'id': o['org_id'], 'name': o['org_name'], 'stakes': [], 'leaders': leaders_of.get(o['org_id'], [])})
    cmap = {c['id']: c for c in councils}
    for o in orgs:
        if o['org_type'] != 'Stake':
            continue
        p = place(o['org_id']) or {}
        st = {'id': o['org_id'], 'name': o['org_name'], 'council': o['council_id'], 'center_building': p.get('building', ''),
              'city': p.get('city', ''), 'state': p.get('state', ''), 'zip': p.get('zip', ''), 'address': p.get('address', ''),
              'lat': p.get('lat'), 'lon': p.get('lon'), 'units': [], 'leaders': leaders_of.get(o['org_id'], []),
              'email': org_email(o['org_id']), 'phone': org_phone(o['org_id'], ('OFFICE_PHONE', 'MEETINGHOUSE_PHONE')),
              'bbox': bbox_of(props.get(o['org_id'], (None, None))[1])}
        stakes.append(st)
        if o['council_id'] in cmap:
            cmap[o['council_id']]['stakes'].append(st['id'])
    smap = {s['id']: s for s in stakes}
    for o in orgs:
        if o['org_type'] not in UNIT_TYPES:
            continue
        pr, geom = props.get(o['org_id'], ({}, None))
        p = place(o['org_id']) or {}
        u = {'id': o['org_id'], 'name': o['org_name'], 'type': o['org_type'], 'stake': o['stake_id'],
             'stake_name': smap.get(o['stake_id'], {}).get('name', ''), 'building': p.get('building', ''),
             'lat': p.get('lat'), 'lon': p.get('lon'), 'address': p.get('address', ''), 'city': p.get('city', ''),
             'state': p.get('state', ''), 'zip': p.get('zip', ''),
             'flags': _flags_for(o['org_name'], o['org_type'], bool(pr.get('special_unit'))),
             'draws_from': draws.get(o['org_id'], []), 'bbox': bbox_of(geom), 'rings': rings_of(geom),
             'label': [pr['label_latitude'], pr['label_longitude']] if pr.get('label_latitude') is not None else None,
             'area_km2': pr.get('area_sq_km'), 'leaders': leaders_of.get(o['org_id'], []), 'phone': org_phone(o['org_id'])}
        units.append(u)
        if o['stake_id'] in smap:
            smap[o['stake_id']]['units'].append(u['id'])
    for b in blds:
        a = parse_address(b['address_raw'])
        buildings[b['building_id']] = {'id': b['building_id'], 'address': b['address_raw'].replace('\n', ', '), 'street': a['street'],
                                       'city': a['city'], 'state': a['state'], 'zip': a['zip'],
                                       'lat': float(b['latitude']) if b['latitude'] else None,
                                       'lon': float(b['longitude']) if b['longitude'] else None,
                                       'units': [], 'stake_center_for': []}
    for u in units:
        if u['building'] in buildings:
            buildings[u['building']]['units'].append(u['id'])
    for s in stakes:
        if s['center_building'] in buildings:
            buildings[s['center_building']]['stake_center_for'].append(s['id'])

    welfare = {}
    for o in orgs:
        if o['org_type'] == 'Welfare and Self-Reliance Region':
            p = place(o['org_id']) or {}
            welfare['region'] = {'id': o['org_id'], 'name': o['org_name'], 'leaders': leaders_of.get(o['org_id'], []),
                                 'city': p.get('city', ''), 'address': p.get('address', ''), 'lat': p.get('lat'), 'lon': p.get('lon')}
        elif o['org_type'] == 'Area PEF Self Reliance Office':
            welfare['area_office'] = {'id': o['org_id'], 'name': o['org_name'], 'leaders': leaders_of.get(o['org_id'], [])}
        elif o['org_type'] == 'Area':
            welfare['area'] = {'id': o['org_id'], 'name': o['org_name']}
    return {'kind': PACK_KIND, 'v': 1, 'source': root.name, 'privacy': 'real',
            'councils': councils, 'stakes': stakes, 'units': units, 'buildings': list(buildings.values()),
            'welfare': welfare, 'contacts': pack_contacts}


# ── Roles the directory export does not list ────────────────────────────────
# The Church directory (CDOL) export carries bishoprics, stake presidencies, clerks and the
# welfare line, but no emergency callings. The drill director adds those in a small file beside
# the pack (``<pack folder>/simulation/local-roles.json``, never in the repository); they become
# contacts of the organization and take the privacy mode like everyone else.
LOCAL_ROLES_KIND = 'church_emcomm_local_roles'
ERD_ROLES = ('Emergency Response Director', 'Assistant Emergency Response Director')
SPECIALIST_ROLES = ('Welfare and Self-Reliance Specialist (emergency communications)', 'Stake Welfare and Self-Reliance Specialist')
SUGGESTED_ROLES = list(ERD_ROLES) + list(SPECIALIST_ROLES) + [
    'Stake Emergency Communications Coordinator', 'Amateur Radio Operator', 'Ward Emergency Preparedness Specialist',
    'Helping Hands Coordinator', 'EOC Operator']


# Roles that must be filled before an EOC (live or drilled) can work. `where` says which level needs
# it: stake (Stake EOC), satellite, area (Council / Area EOC); `source` says where the name comes
# from: directory (the export has it), local (added above), room (a person at the EOC, no pack
# entry). The live EOC Setup tab carries the same list (eoc/EOC_Message_Center.html, MUST_ROLES).
REQUIRED_ROLES = [
    {'key': 'sp', 'title': 'Stake President', 'why': 'decides the response level and approves Supply Orders', 'where': ['stake', 'satellite'], 'source': 'directory',
     'roles': ('Stake President', 'Stake Presidency First Counselor')},
    {'key': 'specialist', 'title': 'Welfare and Self-Reliance Specialist (emergency communications)', 'why': 'recommends the level, runs the stake net plan', 'where': ['stake', 'satellite'], 'source': 'local',
     'roles': SPECIALIST_ROLES},
    {'key': 'erd', 'title': 'Emergency Response Director', 'why': 'runs the EOC, announces the level, owns the SITREP', 'where': ['stake', 'satellite'], 'source': 'local',
     'roles': ERD_ROLES},
    {'key': 'ham', 'title': 'HAM operator / Winlink station at the EOC', 'why': 'the Contingency path (VARA FM, then HF)', 'where': ['stake', 'satellite', 'area'], 'source': 'local',
     'roles': ('Amateur Radio Operator', 'Stake Emergency Communications Coordinator')},
    {'key': 'operator', 'title': 'EOC operator (this laptop)', 'why': 'runs the Message Center, files the SITREP', 'where': ['stake', 'satellite', 'area'], 'source': 'room', 'roles': ('EOC Operator',)},
    {'key': 'bishop', 'title': 'Bishop or Branch President of every ward covered', 'why': 'files the Disaster Report for the ward', 'where': ['stake', 'satellite'], 'source': 'directory',
     'roles': ('Bishop', 'Branch President', 'Bishopric First Counselor', 'Branch Presidency First Counselor'), 'per_unit': True},
    {'key': 'seventy', 'title': 'Area Seventy (coordinating council)', 'why': 'the council line: decisions', 'where': ['area'], 'source': 'directory', 'roles': ('Area Seventy',), 'org': 'council'},
    {'key': 'wsrm', 'title': 'Welfare and Self-Reliance Manager (welfare line)', 'why': 'supplies, approvals, reporting to the AWSRM', 'where': ['area'], 'source': 'directory',
     'roles': ('Welfare and Self-Reliance Manager', 'Area Welfare and Self-Reliance Manager'), 'org': 'welfare'},
]


def required_status(pack: dict, site: dict) -> list:
    """For the EOC a simulator plays (site: role, stake, units, councils, played_stakes): each required
    role with who fills it from the pack, or missing. Room roles are reported as `room` (nobody in the pack)."""
    idx = Index(pack)
    level = site.get('role') if site.get('role') in ('stake', 'satellite', 'area') else 'stake'
    stake = idx.stakes.get(site.get('stake') or '')
    if level == 'satellite' and site.get('units'):
        units = [idx.units[u] for u in site['units'] if u in idx.units]
    elif level == 'stake' and stake:
        units = [u for u in idx.units_of(stake['id']) if u['id'] not in set(site.get('satellite_units') or [])]
    else:
        units = []
    councils = [idx.councils[c] for c in (site.get('councils') or []) if c in idx.councils]
    welfare = (pack.get('welfare') or {}).get('region') or {}
    out = []
    for r in REQUIRED_ROLES:
        if level not in r['where']:
            continue
        row = {'key': r['key'], 'title': r['title'], 'why': r['why'], 'source': r['source'], 'filled': False, 'who': [], 'missing': []}
        if r['source'] == 'room':
            row['status'] = 'room'
        elif r.get('per_unit'):
            for u in units:
                c = idx.leader(u, r['roles'])
                (row['who'] if c else row['missing']).append({'org': u['id'], 'name': u['name'], 'who': c.get('name', ''), 'role': c.get('role', '')} if c else {'org': u['id'], 'name': u['name']})
            row['filled'] = bool(units) and not row['missing']
            row['status'] = 'filled' if row['filled'] else 'missing'
        else:
            orgs = councils if r.get('org') == 'council' else ([welfare] if r.get('org') == 'welfare' and welfare.get('id') else ([stake] if stake else []))
            for o in orgs:
                c = idx.leader(o, r['roles'])
                if not c and r['key'] == 'ham':                # a HAM in any ward of the stake counts
                    c = next((idx.leader(u, r['roles']) for u in idx.units_of(o['id']) if idx.leader(u, r['roles'])), {}) if o is stake else {}
                (row['who'] if c else row['missing']).append({'org': o['id'], 'name': o.get('name', ''), 'who': c.get('name', ''), 'role': c.get('role', '')} if c else {'org': o['id'], 'name': o.get('name', '')})
            row['filled'] = bool(orgs) and not row['missing']
            row['status'] = 'filled' if row['filled'] else 'missing'
            if r['source'] == 'local' and not row['filled']:
                row['add'] = {'org': (row['missing'][0]['org'] if row['missing'] else ''), 'role': r['roles'][0]}
        out.append(row)
    return out


PACKAGE_MARKER = 'pseudonymized-package.json'     # in <pack>/simulation/, written by installer/build-sim-package.py


def local_roles_path(pack_path) -> Path:
    p = Path(pack_path)
    return (p if p.is_dir() else p.parent) / 'simulation' / 'local-roles.json'


def read_local_roles(path) -> list:
    try:
        d = _read_json(Path(path))
    except Exception:
        return []
    return list(d.get('roles', [])) if isinstance(d, dict) and d.get('kind') == LOCAL_ROLES_KIND else []


def write_local_roles(path, roles: list) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'kind': LOCAL_ROLES_KIND, 'v': 1, 'roles': roles}, ensure_ascii=False, indent=1), encoding='utf-8')
    return path


def organizations(pack: dict) -> list:
    """Every organization a local role can belong to: councils, stakes, units, the welfare line."""
    out = [{'id': c['id'], 'name': c['name'], 'type': 'Coordinating council'} for c in pack.get('councils', [])]
    out += [{'id': s['id'], 'name': s['name'], 'type': 'Stake'} for s in pack['stakes']]
    out += [{'id': u['id'], 'name': u['name'], 'type': u.get('type', 'Ward'), 'stake': u.get('stake_name', '')} for u in pack['units']]
    w = pack.get('welfare') or {}
    for k, label in (('region', 'Welfare region'), ('area_office', 'Area office')):
        if w.get(k) and w[k].get('id'):
            out.append({'id': w[k]['id'], 'name': w[k]['name'], 'type': label})
    return out


def apply_local_roles(pack: dict, roles: list) -> int:
    """Add the local roles to the pack as contacts and leaders of their organization. Returns how many."""
    orgs = {}
    for c in pack.get('councils', []):
        orgs[c['id']] = c
    for s in pack['stakes']:
        orgs[s['id']] = s
    for u in pack['units']:
        orgs[u['id']] = u
    w = pack.get('welfare') or {}
    for k in ('region', 'area_office'):
        if w.get(k) and w[k].get('id'):
            orgs[w[k]['id']] = w[k]
    pack['contacts'] = [c for c in pack['contacts'] if not c.get('local')]
    for org in orgs.values():
        org['leaders'] = [cid for cid in org.get('leaders', []) if not str(cid).startswith('local-')]
    n = 0
    for i, r in enumerate(roles or []):
        org = orgs.get(str(r.get('org', '')))
        role = str(r.get('role', '')).strip()
        if not org or not role:
            continue
        n += 1
        first, last = str(r.get('first', '')).strip(), str(r.get('last', '')).strip()
        cid = f'local-{i + 1}'
        pack['contacts'].append({'id': cid, 'person': cid, 'role': role, 'org': org['id'], 'name': f'{first} {last}'.strip(),
                                 'first': first, 'last': last, 'mobile': str(r.get('mobile', '')).strip(), 'phone': str(r.get('phone') or r.get('mobile') or '').strip(),
                                 'email': str(r.get('email', '')).strip(), 'note': str(r.get('note', '')).strip(), 'local': True})
        org.setdefault('leaders', []).append(cid)
    return n


def building_names_path(pack_path) -> Path:
    p = Path(pack_path)
    return (p if p.is_dir() else p.parent) / 'simulation' / 'building-names.json'


def _ordinal_street(street: str) -> str:
    return re.sub(r'\s+', ' ', street or '').strip()


def derived_building_name(b: dict, stake_names: dict) -> str:
    """A name when no source gives one: the stake center convention, else '<City> Meetinghouse, <street>'."""
    sc = [stake_names.get(s, '') for s in (b.get('stake_center_for') or []) if stake_names.get(s)]
    if len(sc) == 1:
        return f'{sc[0]} Center'
    city = (b.get('city') or '').strip()
    street = _ordinal_street(b.get('street') or (b.get('address') or '').split(',')[0])
    return f'{city} Meetinghouse, {street}'.strip(', ') if city else f'Meetinghouse, {street}'


def apply_building_names(pack: dict, names) -> dict:
    """Give every building a ``name`` (and every unit and stake its ``building_name``). ``names`` is the list in
    ``simulation/building-names.json`` beside the pack: [{building_id, name, basis, source_url}]; a building with
    no name there gets the derived one (``name_basis`` says which). Returns counts by basis."""
    given = {}
    for r in names or []:
        if isinstance(r, dict) and r.get('building_id') and (r.get('name') or '').strip():
            given[str(r['building_id'])] = (r['name'].strip(), r.get('basis') or 'source', r.get('source_url') or '')
    stake_names = {s['id']: s['name'] for s in pack.get('stakes', [])}
    counts = {}
    by_id = {}
    for b in pack.get('buildings', []):
        if b['id'] in given:
            b['name'], b['name_basis'], b['name_source'] = given[b['id']]
        elif not b.get('name'):
            b['name'], b['name_basis'] = derived_building_name(b, stake_names), 'derived'
        counts[b.get('name_basis', 'pack')] = counts.get(b.get('name_basis', 'pack'), 0) + 1
        by_id[b['id']] = b
    for u in pack.get('units', []):
        if u.get('building') in by_id:
            u['building_name'] = by_id[u['building']]['name']
    for s in pack.get('stakes', []):
        if s.get('center_building') in by_id:
            s['center_name'] = by_id[s['center_building']]['name']
    return counts


def load(path) -> dict:
    """A pack from an export root (has csv/organizations.csv), an orgpack.json, or a folder holding one,
    plus the local roles and building names files beside it when there are some."""
    p = Path(path)
    if p.is_file():
        pack = _read_json(p)
    elif (p / 'orgpack.json').is_file():
        pack = _read_json(p / 'orgpack.json')
    elif (p / 'csv' / 'organizations.csv').is_file():
        pack = read_export(p)
    else:
        raise FileNotFoundError(f'{p}: not an export root (csv/organizations.csv) and no orgpack.json')
    if pack.get('kind') != PACK_KIND:
        raise ValueError(f'{p}: not a {PACK_KIND} file')
    # a participant package says so with a marker file: only the marker counts, never a label inside a pack file
    pack.pop('pre_pseudonymized', None)
    if local_roles_path(p).with_name(PACKAGE_MARKER).is_file():
        pack['pre_pseudonymized'] = True
        pack['privacy'] = 'pseudonymized'
    apply_local_roles(pack, read_local_roles(local_roles_path(p)))
    try:
        bn = _read_json(building_names_path(p))
    except Exception:
        bn = []
    apply_building_names(pack, bn if isinstance(bn, list) else bn.get('buildings', []) if isinstance(bn, dict) else [])
    return pack


def save(pack: dict, path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pack, ensure_ascii=False, indent=1), encoding='utf-8')
    return path


class Index:
    """Lookups over a pack (built once per run)."""

    def __init__(self, pack: dict):
        self.pack = pack
        self.units = {u['id']: u for u in pack['units']}
        self.stakes = {s['id']: s for s in pack['stakes']}
        self.councils = {c['id']: c for c in pack.get('councils', [])}
        self.buildings = {b['id']: b for b in pack['buildings']}
        self.contacts = {c['id']: c for c in pack['contacts']}

    def leader(self, org: dict, roles) -> dict:
        """First contact of the organization whose role is in `roles` (ordered by preference)."""
        for role in roles:
            for cid in org.get('leaders', []):
                c = self.contacts.get(cid)
                if c and c['role'] == role:
                    return c
        return {}

    def leaders(self, org: dict, exclude_roles=()) -> list:
        return [self.contacts[cid] for cid in org.get('leaders', []) if cid in self.contacts and self.contacts[cid]['role'] not in exclude_roles]

    def head(self, unit: dict) -> dict:
        return self.leader(unit, ('Bishop', 'Branch President', 'Bishopric First Counselor', 'Branch Presidency First Counselor'))

    def stake_president(self, stake_id: str) -> dict:
        s = self.stakes.get(stake_id)
        return self.leader(s, ('Stake President', 'Stake Presidency First Counselor')) if s else {}

    def erd(self, stake_id: str, unit: dict = None) -> dict:
        """The Emergency Response Director: the unit's own if one was added, else the stake's."""
        s = self.stakes.get(stake_id)
        return (self.leader(unit, ERD_ROLES) if unit else {}) or (self.leader(s, ERD_ROLES) if s else {})

    def specialist(self, stake_id: str) -> dict:
        s = self.stakes.get(stake_id)
        return self.leader(s, SPECIALIST_ROLES) if s else {}

    def units_of(self, stake_id: str) -> list:
        return [self.units[u] for u in self.stakes.get(stake_id, {}).get('units', []) if u in self.units]

    def bbox(self) -> list:
        """[west, south, east, north] of every unit building in the pack."""
        xs = [u['lon'] for u in self.pack['units'] if u.get('lon') is not None]
        ys = [u['lat'] for u in self.pack['units'] if u.get('lat') is not None]
        return [min(xs), min(ys), max(xs), max(ys)] if xs else None


def summary(pack: dict) -> dict:
    """Counts only (safe to print or log): no names, no contact values."""
    units = pack['units']
    flags = {}
    for u in units:
        for f in u.get('flags', []):
            flags[f] = flags.get(f, 0) + 1
    with_contact = sum(1 for c in pack['contacts'] if c.get('mobile') or c.get('phone'))
    return {'source': pack.get('source', ''), 'privacy': pack.get('privacy', 'real'),
            'councils': len(pack.get('councils', [])), 'stakes': len(pack['stakes']), 'units': len(units),
            'wards': sum(1 for u in units if u['type'] == 'Ward'), 'branches': sum(1 for u in units if u['type'] == 'Branch'),
            'buildings': len(pack['buildings']), 'contacts': len(pack['contacts']), 'contactsWithPhone': with_contact,
            'flags': flags, 'unitsWithoutLocation': sum(1 for u in units if u.get('lat') is None),
            'states': sorted({u['state'] for u in units if u.get('state')}), 'bbox': Index(pack).bbox()}


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        sys.exit(0)
    out = args[args.index('--out') + 1] if '--out' in args else ''
    pk = load(args[0])
    print(json.dumps(summary(pk), indent=1))
    if out:
        print('saved', save(pk, out))
