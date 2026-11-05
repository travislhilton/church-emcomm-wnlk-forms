#!/usr/bin/env python3
"""Build the invented example community (the Juniper Plains Area) from world.json.

Writes a complete Church-directory-style export folder, entirely made up, that every part of the system loads
the way it loads a real export: the simulator (Setup -> Organization pack), the EOC Message Center (Map data folder,
drill configuration), simulation/community.py, the tests. Nothing in it describes a real organization, person or place.

    python simulation/example/build_example.py            # writes simulation/example/juniper-plains/
    python simulation/example/build_example.py --check    # rebuild in memory and compare (no maps redrawn)

Output (the export root):
    csv/            organizations, contacts, contactmethods, addresses, buildings, building_organizations, relationships
    simulator/      organization_boundaries, buildings, organization_locations (GeoJSON),
                    overlays/manifest.json + overlays/maps/*.png (drawn street maps: one per stake and one of the Area)
    simulation/     drill-spec.json, building-names.json (starter files, as community.py init would write them)
    README.txt

Maps need Pillow (pip install pillow); everything else is the Python standard library. Deterministic: the same
world.json gives the same files.
"""
import csv
import hashlib
import io
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORLD = json.loads((HERE / 'world.json').read_text(encoding='utf-8'))
OUT = HERE / 'juniper-plains'
SRC_TAG = 'invented-example'

LAT0, LON0 = WORLD['frame']['origin_lat'], WORLD['frame']['origin_lon']
KM_LAT = 110.95
KM_LON = 111.32 * math.cos(math.radians(LAT0))


def ll(x, y):
    """km east / north of the frame origin -> (lon, lat), rounded."""
    return round(LON0 + x / KM_LON, 6), round(LAT0 + y / KM_LAT, 6)


def merc(lon, lat):
    r = 6378137.0
    return r * math.radians(lon), r * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


# ── invented people ─────────────────────────────────────────────────────────
MEN = ('Aaron Adam Alan Andrew Arthur Austin Ben Blake Brady Brent Bryce Caleb Calvin Carl Carson Chad Clark Clayton Cody Cole '
       'Craig Dale Dallin Dean Derek Devin Doug Drew Dustin Dwight Eli Eric Ethan Evan Garrett Gavin Glen Gordon Grant Hal Hayden '
       'Heber Henry Isaac Jared Jay Jeff Joel Jonah Jordan Joseph Kade Keith Kent Kirk Kyle Lance Lane Lee Levi Lyle Marcus Mark '
       'Martin Max Miles Morgan Nathan Neil Noel Owen Parker Paul Quinn Ray Reed Rex Rhett Roland Ross Russ Ryan Sam Scott Seth '
       'Shane Spencer Stuart Ted Trent Troy Tyler Vance Wade Walter Warren Wes Wyatt').split()
WOMEN = ('Abigail Alice Amy Anna Becca Beth Brooke Camille Carla Claire Dana Eliza Emma Erin Faith Grace Hannah Holly Ivy Jane '
         'Jenna Julia Kara Kate Laura Leah Lydia Mara Megan Mia Nora Paige Rachel Rose Ruth Sadie Sara Tess Vera Wren').split()
LAST = ('Abbott Alder Ashby Bair Barlow Beckstead Bingham Bowcutt Brimhall Burnside Callister Carver Chadwick Colby Cottam Crandall '
        'Dalby Delong Driggs Dunford Eldredge Ellsworth Farnes Felt Fenn Garff Gledhill Goodsell Hadfield Halverson Harker Hatfield '
        'Hendry Hollis Huish Isom Jeppson Kartchner Keddington Kimber Lambson Larsen Leavitt Lindquist Lofgreen Lundell Madsen Marchant '
        'Merrill Moffat Mortensen Nebeker Nyman Oakes Orton Ostler Packard Pehrson Peery Pickett Poulter Quist Rasband Redd Renshaw '
        'Rigby Rowberry Sagers Sanderson Schow Selin Shurtz Skousen Spendlove Staheli Stucki Sumsion Tanner Thalman Tingey Trane '
        'Udall Updike Vance Varley Wadley Walkenhorst Warby Welling Whitlock Wiscombe Woolsey Yardley Yorgason Zundel').split()

STAKE_ROLES = ['Stake President', 'Stake Presidency First Counselor', 'Stake Presidency Second Counselor', 'Stake Clerk',
               'Stake Executive Secretary']
WARD_ROLES = ['Bishop', 'Bishopric First Counselor', 'Bishopric Second Counselor', 'Ward Clerk', 'Ward Executive Secretary']
BRANCH_ROLES = ['Branch President', 'Branch Presidency First Counselor', 'Branch Presidency Second Counselor', 'Branch Clerk']


class People:
    def __init__(self):
        self.rng = random.Random(20261101)
        self.used = set()
        self.n = 0

    def person(self, woman=False):
        while True:
            name = f"{self.rng.choice(WOMEN if woman else MEN)} {self.rng.choice(LAST)}"
            if name not in self.used:
                self.used.add(name)
                self.n += 1
                return name, f'P{self.n:04d}'

    def phone(self):
        # 555-0100 to 555-0199 is the range set aside for fiction; the area code is fictional too
        return f'555-555-01{self.rng.randrange(100):02d}'


# ── geometry helpers ────────────────────────────────────────────────────────
def rect_ring(x0, y0, x1, y1):
    return [list(ll(x0, y0)), list(ll(x1, y0)), list(ll(x1, y1)), list(ll(x0, y1)), list(ll(x0, y0))]


def grid_cells(rect, cols, rows):
    x0, y0, x1, y1 = rect
    w, h = (x1 - x0) / cols, (y1 - y0) / rows
    cells = []
    for r in range(rows - 1, -1, -1):           # north row first, west to east: ward numbers read like a page
        for c in range(cols):
            cells.append((x0 + c * w, y0 + r * h, x0 + (c + 1) * w, y0 + (r + 1) * h))
    return cells


def town_of(name):
    return next(t for t in WORLD['towns'] if t['name'] == name)


def nearest_town(x, y):
    return min(WORLD['towns'], key=lambda t: (t['center'][0] - x) ** 2 + (t['center'][1] - y) ** 2)


def grid_address(x, y, town):
    """A street address on the town's grid: 1 km = 500 address units, numbers rounded to 5."""
    cx, cy = town['center']
    ns, ew = round((y - cy) * 500 / 5) * 5, round((x - cx) * 500 / 5) * 5
    a = f"{abs(ns)} {'N' if ns >= 0 else 'S'} {abs(ew)} {'E' if ew >= 0 else 'W'}"
    return a


def zip_of(town):
    return str(WORLD['zip_base'] + [t['name'] for t in WORLD['towns']].index(town['name']) + 1)


def address_raw(x, y, town, facility=''):
    lines = ([facility] if facility else []) + [grid_address(x, y, town), f"{town['name']}, {WORLD['state_abbr']} {zip_of(town)}", 'United States']
    return '\n'.join(lines)


# ── build ────────────────────────────────────────────────────────────────────
def build():
    P = People()
    orgs, contacts, methods, addresses, buildings, bo, rels, feats, bfeats, locs, names = [], [], [], [], [], [], [], [], [], [], []
    mid = 0

    def org(oid, name, typ, council='', stake='', parent='', building=''):
        orgs.append({'org_id': oid, 'org_uuid': hashlib.md5(oid.encode()).hexdigest(), 'org_name': name, 'org_type': typ, 'status': 'Active',
                     'active_date': '2019-01-01', 'area_id': WORLD['area']['id'], 'council_id': council, 'stake_id': stake,
                     'parent_org_id': parent, 'property_number': building.replace('B-', 'PROP-') if building else '', 'building_id': building,
                     'map_count': '1', 'map_status': 'invented', 'source_url': '', 'extracted_on': '2026-11-01'})

    def staff(oid, oname, otype, roles, council='', stake='', women=()):
        nonlocal mid
        for role in roles:
            name, pid = P.person(woman=role in women)
            pos = f'POS-{oid}-{roles.index(role) + 1}'
            phone = P.phone()
            first, last = name.split(' ', 1)
            email = f'{first.lower()}.{last.lower()}@churchemcomm.sim'
            contacts.append({'position_id': pos, 'person_id': pid, 'person_name': name, 'org_id': oid, 'org_name': oname, 'org_type': otype,
                             'role_name': role, 'requested_role': role, 'primary_contact': 'true' if roles.index(role) == 0 else 'false',
                             'active_date': '2024-06-01', 'primary_phone': phone, 'primary_email': email, 'council_id': council,
                             'stake_id': stake, 'profile_checked': 'invented', 'source_url': ''})
            for kind, typ, val in (('Phone', 'Mobile Phone', phone), ('Email', 'Personal Email', email)):
                mid += 1
                methods.append({'contact_method_id': f'CM{mid:05d}', 'owner_kind': 'Person', 'owner_id': pid, 'org_id': oid, 'position_id': pos,
                                'contact_kind': kind, 'contact_type': typ, 'contact_value': val, 'contact_uri': '', 'source_url': ''})

    def building(bid, x, y, town, orgs_here, facility=''):
        raw = address_raw(x, y, town, facility)
        lon, lat = ll(x, y)
        buildings.append({'building_id': bid, 'property_number': bid.replace('B-', 'PROP-'), 'address_raw': raw, 'latitude': lat,
                          'longitude': lon, 'source_org_id': orgs_here[0][0] if orgs_here else '', 'source_url': ''})
        for oid, oname, otype, council, stake in orgs_here:
            bo.append({'building_id': bid, 'org_id': oid, 'org_name': oname, 'org_type': otype, 'relationship_type': 'Meets In',
                       'mapping_status': 'invented', 'block_start_time': '9:00 AM', 'sacrament_start_time': '9:00 AM', 'meeting_room': '',
                       'property_number': bid.replace('B-', 'PROP-'), 'address_raw': raw, 'council_id': council, 'stake_id': stake,
                       'mapping_basis': 'invented', 'building_org_id': f'{bid}:{oid}', 'source_url': ''})
            addresses.append({'address_id': f'A-{oid}', 'org_id': oid, 'building_id': bid, 'address_type': 'Physical',
                              'address_line_1': raw.split('\n')[0], 'address_line_2': raw.split('\n')[1], 'address_line_3': '',
                              'address_raw': raw, 'latitude': lat, 'longitude': lon, 'source_url': ''})
        bfeats.append({'type': 'Feature', 'properties': {'building_id': bid, 'property_number': bid.replace('B-', 'PROP-'), 'address_raw': raw,
                                                         'latitude': lat, 'longitude': lon, 'organization_ids': [o[0] for o in orgs_here],
                                                         'organization_names': [o[1] for o in orgs_here], 'coordinate_method': 'invented'},
                       'geometry': {'type': 'Point', 'coordinates': [lon, lat]}})

    def feature(oid, name, typ, stake, rings, label, special=False, council=''):
        geom = {'type': 'Polygon', 'coordinates': [rings[0]]} if len(rings) == 1 else {'type': 'MultiPolygon', 'coordinates': [[r] for r in rings]}
        xs = [p[0] for r in rings for p in r]
        ys = [p[1] for r in rings for p in r]
        lon, lat = ll(*label)
        props = {'org_id': oid, 'org_name': name, 'org_type': typ, 'stake_id': stake, 'council_id': council, 'label_longitude': lon,
                 'label_latitude': lat, 'special_unit': special, 'bounds': [min(xs), min(ys), max(xs), max(ys)], 'quality': 'invented',
                 'area_sq_km': None}
        feats.append({'type': 'Feature', 'properties': props, 'geometry': geom})

    def loc(oid, name, typ, x, y, bid='', kind='building'):
        lon, lat = ll(x, y)
        locs.append({'type': 'Feature', 'properties': {'org_id': oid, 'org_name': name, 'org_type': typ, 'building_id': bid,
                                                       'location_kind': kind, 'physical_location_known': kind == 'building'},
                     'geometry': {'type': 'Point', 'coordinates': [lon, lat]}})

    area = WORLD['area']
    org(area['id'], area['name'], 'Area')
    allrect = [s['rect'] for s in WORLD['stakes']]
    feature(area['id'], area['name'], 'Area', '', [rect_ring(*r) for r in allrect], (0.0, 4.0))
    loc(area['id'], area['name'], 'Area', 0.0, 4.0, kind='label')
    wf = WORLD['welfare']
    org(wf['region']['id'], wf['region']['name'], 'Welfare and Self-Reliance Region', parent=area['id'], building='B-WSR')
    org(wf['area_office']['id'], wf['area_office']['name'], 'Area PEF Self Reliance Office', parent=area['id'])
    staff(wf['region']['id'], wf['region']['name'], 'Welfare and Self-Reliance Region',
          ['Welfare and Self-Reliance Manager', 'Humanitarian Specialist'], women=('Humanitarian Specialist',))
    staff(wf['area_office']['id'], wf['area_office']['name'], 'Area PEF Self Reliance Office', ['Area Welfare and Self-Reliance Manager'])
    wx, wy = wf['region']['at']
    building('B-WSR', wx, wy, town_of('Larkspur'), [(wf['region']['id'], wf['region']['name'], 'Welfare and Self-Reliance Region', '', '')],
             facility=wf['region']['office'])
    loc(wf['region']['id'], wf['region']['name'], 'Welfare and Self-Reliance Region', wx, wy, 'B-WSR')
    loc(wf['area_office']['id'], wf['area_office']['name'], 'Area PEF Self Reliance Office', wx, wy, kind='unavailable')
    rels.append({'from_org_id': wf['region']['id'], 'relationship_type': 'Parent', 'to_org_id': area['id'], 'to_org_name': area['name'],
                 'association_date': '2019-01-01', 'association_status': 'Active', 'source_url': ''})

    stakes = {s['id']: s for s in WORLD['stakes']}
    for c in WORLD['councils']:
        org(c['id'], c['name'], 'Area Coordinating Council', council=c['id'], parent=area['id'])
        staff(c['id'], c['name'], 'Area Coordinating Council', ['Area Seventy'], council=c['id'])
        rings = [rect_ring(*stakes[s]['rect']) for s in c['stakes']]
        cx = sum((stakes[s]['rect'][0] + stakes[s]['rect'][2]) / 2 for s in c['stakes']) / len(c['stakes'])
        cy = sum((stakes[s]['rect'][1] + stakes[s]['rect'][3]) / 2 for s in c['stakes']) / len(c['stakes'])
        feature(c['id'], c['name'], 'Area Coordinating Council', '', rings, (cx, cy), council=c['id'])
        loc(c['id'], c['name'], 'Area Coordinating Council', cx, cy, kind='label')
        rels.append({'from_org_id': c['id'], 'relationship_type': 'Parent', 'to_org_id': area['id'], 'to_org_name': area['name'],
                     'association_date': '2019-01-01', 'association_status': 'Active', 'source_url': ''})

    council_of = {s: c['id'] for c in WORLD['councils'] for s in c['stakes']}
    units_meta = []
    for s in WORLD['stakes']:
        sid, cid, town = s['id'], council_of[s['id']], town_of(s['town'])
        bl = [(f'B-{sid}-{i + 1}', x, y) for i, (x, y) in enumerate(s['buildings'])]
        org(sid, s['name'], 'Stake', council=cid, stake=sid, parent=cid, building=bl[0][0])
        staff(sid, s['name'], 'Stake', STAKE_ROLES, council=cid, stake=sid)
        x0, y0, x1, y1 = s['rect']
        feature(sid, s['name'], 'Stake', sid, [rect_ring(*s['rect'])], ((x0 + x1) / 2, (y0 + y1) / 2), council=cid)
        rels.append({'from_org_id': sid, 'relationship_type': 'Parent', 'to_org_id': cid, 'to_org_name': next(c['name'] for c in WORLD['councils'] if c['id'] == cid),
                     'association_date': '2019-01-01', 'association_status': 'Active', 'source_url': ''})
        here = {b[0]: [] for b in bl}
        here[bl[0][0]].append((sid, s['name'], 'Stake', cid, sid))
        cells = grid_cells(s['rect'], *s['grid'])
        for i, (name, cell) in enumerate(zip(s['wards'], cells)):
            uid = f'U-{sid}-{i + 1}'
            cxm, cym = (cell[0] + cell[2]) / 2, (cell[1] + cell[3]) / 2
            bid = min(bl, key=lambda b: (b[1] - cxm) ** 2 + (b[2] - cym) ** 2)[0]
            org(uid, name, 'Ward', council=cid, stake=sid, parent=sid, building=bid)
            staff(uid, name, 'Ward', WARD_ROLES, council=cid, stake=sid)
            feature(uid, name, 'Ward', sid, [rect_ring(*cell)], (cxm, cym), council=cid)
            here[bid].append((uid, name, 'Ward', cid, sid))
            units_meta.append((uid, name, sid, cell))
            rels.append({'from_org_id': uid, 'relationship_type': 'Parent', 'to_org_id': sid, 'to_org_name': s['name'],
                         'association_date': '2019-01-01', 'association_status': 'Active', 'source_url': ''})
        for j, sp in enumerate(s.get('special', [])):
            uid = f'U-{sid}-B{j + 1}'
            fx, fy = sp['at']
            if sp.get('facility'):
                bid = f'B-{sid}-F{j + 1}'
                building(bid, fx, fy, nearest_town(fx, fy), [(uid, sp['name'], sp['type'], cid, sid)], facility=sp['facility'])
                ring = [rect_ring(fx - 0.18, fy - 0.14, fx + 0.18, fy + 0.14)]
            else:
                bid = min(bl, key=lambda b: (b[1] - fx) ** 2 + (b[2] - fy) ** 2)[0]
                here[bid].append((uid, sp['name'], sp['type'], cid, sid))
                ring = [rect_ring(*stakes[d]['rect']) for d in sp.get('draws_from', [sid])]
            org(uid, sp['name'], sp['type'], council=cid, stake=sid, parent=sid, building=bid)
            staff(uid, sp['name'], sp['type'], BRANCH_ROLES, council=cid, stake=sid)
            feature(uid, sp['name'], sp['type'], sid, ring, (fx, fy), special=True, council=cid)
            loc(uid, sp['name'], sp['type'], fx, fy, bid)
            for d in sp.get('draws_from', []):
                rels.append({'from_org_id': uid, 'relationship_type': 'Participating Units', 'to_org_id': d, 'to_org_name': stakes[d]['name'],
                             'association_date': '2019-01-01', 'association_status': 'Active', 'source_url': ''})
            rels.append({'from_org_id': uid, 'relationship_type': 'Parent', 'to_org_id': sid, 'to_org_name': s['name'],
                         'association_date': '2019-01-01', 'association_status': 'Active', 'source_url': ''})
        for bid, x, y in bl:
            building(bid, x, y, nearest_town(x, y), here[bid])
            for oid, oname, otype, _, _ in here[bid]:
                if otype != 'Branch':
                    loc(oid, oname, otype, x, y, bid)
            first = here[bid][0][1] if here[bid] else ''
            names.append({'building_id': bid, 'address': address_raw(x, y, nearest_town(x, y)).replace('\n', ', '),
                          'name': f"{s['name']} Center" if bid == bl[0][0] else f"{nearest_town(x, y)['name']} Meetinghouse, {grid_address(x, y, nearest_town(x, y))}",
                          'basis': 'invented', 'source_url': None, 'note': 'Invented example building.'})
    for b in buildings:
        if b['building_id'].startswith('B-WSR') or '-F' in b['building_id']:
            names.append({'building_id': b['building_id'], 'address': b['address_raw'].replace('\n', ', '), 'name': b['address_raw'].split('\n')[0],
                          'basis': 'invented', 'source_url': None, 'note': 'Invented example facility.'})

    files = {
        'csv/organizations.csv': orgs, 'csv/contacts.csv': contacts, 'csv/contactmethods.csv': methods, 'csv/addresses.csv': addresses,
        'csv/buildings.csv': buildings, 'csv/building_organizations.csv': bo, 'csv/relationships.csv': rels,
    }
    out = {}
    for path, rows in files.items():
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), lineterminator='\n')
        w.writeheader()
        w.writerows(rows)
        out[path] = buf.getvalue()
    note = 'Invented example (Juniper Plains Area): no real organization, person or place.'
    out['simulator/organization_boundaries.geojson'] = json.dumps({'type': 'FeatureCollection', 'note': note, 'features': feats}, indent=1)
    out['simulator/buildings.geojson'] = json.dumps({'type': 'FeatureCollection', 'note': note, 'features': bfeats}, indent=1)
    out['simulator/organization_locations.geojson'] = json.dumps({'type': 'FeatureCollection', 'note': note, 'features': locs}, indent=1)
    out['simulation/building-names.json'] = json.dumps(names, ensure_ascii=False, indent=1)
    out['simulation/drill-spec.json'] = json.dumps(drill_spec(), ensure_ascii=False, indent=1)
    out['simulation/salt.txt'] = 'juniper-plains-invented-example\n'      # fixed: the same pseudonyms on every laptop (all invented anyway)
    out['README.txt'] = README.replace('{people}', str(len(contacts))).replace('{units}', str(len(units_meta) + sum(len(s.get('special', [])) for s in WORLD['stakes'])))
    return out, units_meta


def drill_spec():
    return {
        'kind': 'church_emcomm_drill_spec', 'v': 1,
        'name': 'Copper Creek Dam drill: Juniper Plains Area (invented example)',
        'scenario': 'copper-creek-dam', 'export': '..', 'privacy': 'pseudonymized',
        'event': {'name': 'DRILL: Copper Creek Dam failure (THIS IS AN EXERCISE)', 'type': 'Flood', 'sitrepHrs': '2', 'sitrepBy': 'Stake President'},
        'eocs': [
            {'id': 'larkspur', 'level': 'stake', 'stake': 'Larkspur Stake', 'manned': 'always', 'winlink': ['SIM-LKS']},
            {'id': 'copper-ridge', 'level': 'stake', 'stake': 'Copper Ridge Stake', 'manned': 'optional', 'winlink': ['SIM-CRS']},
            {'id': 'alder-flat', 'level': 'stake', 'stake': 'Alder Flat Stake', 'manned': 'optional', 'winlink': ['SIM-AFS']},
            {'id': 'larkspur-east', 'level': 'stake', 'stake': 'Larkspur East Stake', 'manned': 'optional', 'winlink': []},
            {'id': 'larkspur-west', 'level': 'stake', 'stake': 'Larkspur West Stake', 'manned': 'optional', 'winlink': []},
            {'id': 'juniper-springs', 'level': 'stake', 'stake': 'Juniper Springs Stake', 'manned': 'optional', 'winlink': []},
            {'id': 'kestrel', 'level': 'stake', 'stake': 'Kestrel Stake', 'manned': 'optional', 'winlink': []},
            {'id': 'saddleback', 'level': 'stake', 'stake': 'Saddleback Stake', 'manned': 'optional', 'winlink': []},
            {'id': 'area', 'level': 'area', 'councils': [c['name'] for c in WORLD['councils']], 'building': 'B-SJS-1', 'manned': 'optional',
             'winlink': ['SIM-JPA'], 'name': 'Council / Area EOC: Juniper Springs Stake Center'},
        ],
        'agencies': [
            {'id': 'larkspur-city', 'name': 'Larkspur City EOC', 'call': 'SIM-LKCITY', 'contact': 'Duty officer, Larkspur Fire Department',
             'place': 'Fire Station 1, Center Street (Winlink station, VHF/UHF radios)', 'forms': 'ICS 213RR (resource requests), ICS 213 (messages and answers); never Church forms',
             'serves': ['Larkspur Stake', 'Larkspur East Stake', 'Larkspur West Stake']},
            {'id': 'copper-ridge-city', 'name': 'Copper Ridge City EOC', 'call': 'SIM-CRCITY', 'contact': 'Duty officer, Copper Ridge Fire Station',
             'place': 'Copper Ridge Fire Station, Route 30', 'forms': 'ICS 213RR, ICS 213', 'serves': ['Copper Ridge Stake']},
        ],
        'note': 'Invented example: every name, call sign and place is made up. Call signs starting SIM- are simulator stations, never on the air.',
    }


README = """JUNIPER PLAINS AREA: INVENTED EXAMPLE COMMUNITY
================================================

Everything in this folder is made up: the Juniper Plains Area, its two coordinating
councils, eight stakes and {units} wards and branches, the {people} leaders, every phone
(555-555-01xx, the range set aside for fiction), every email (@churchemcomm.sim), every
address, street, river, road, facility and map. The coordinates only place the fiction
on a map. It is safe to share, show and use in screenshots.

Independent volunteer project by Travis Hilton (W9TLH), not an official Church product.

What it is for
--------------
A public drill, a demonstration or a test without anyone's directory export. It has
the same layout as a Church directory export, so every part of the system loads it:

  Simulator        Setup -> 1. Organization pack -> this folder
                   (or: python simulation/sim_server.py --data "<this folder>")
                   Scenario: Copper Creek Dam failure (the developed example scenario)
  EOC Message      Setup -> This EOC -> Map data folder -> this folder
  Center           Setup -> Load a drill configuration -> simulation/drill-config.json
                   (build it first: python simulation/drillconfig.py simulation/drill-spec.json)
  Check it         python simulation/community.py check "<this folder>"

The valley
----------
Larkspur Valley runs 46 km north to south. The Larkspur River flows south through
Kestrel, Juniper Springs, Larkspur (the county seat) and Alder Flat. Copper Creek
leaves Copper Creek Reservoir in the eastern hills, runs west through Copper Ridge and
the south side of Larkspur, and joins the river below Center Street. Saddleback sits on
the west bench under Saddleback Ridge, where the amateur radio repeater is.

  Larkspur Coordinating Council:  Larkspur, Larkspur East, Larkspur West, Copper Ridge stakes
  Kestrel Coordinating Council:   Juniper Springs, Kestrel, Alder Flat, Saddleback stakes
  Welfare line:                   Juniper Plains Welfare and Self-Reliance Region (office in
                                  Larkspur); Bramble Junction Bishops' Storehouse, 140 km away

Special units: Larkspur Care Center Branch (care facility), Copper Ridge Retirement
Branch (retirement village), Larkspur Spanish Branch (draws members from the three
Larkspur stakes).

Maps: simulator/overlays/maps/ has a drawn street map of each stake and one of the
whole Area, placed by simulator/overlays/manifest.json like the directory's own maps.

Rebuild with: python simulation/example/build_example.py (world.json is the source).
"""


# ── maps ─────────────────────────────────────────────────────────────────────
def draw_maps(units_meta):
    from PIL import Image, ImageDraw, ImageFont

    def font(sz, bold=False):
        for f in (('arialbd.ttf' if bold else 'arial.ttf'), ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'),
                  '/System/Library/Fonts/Supplemental/Arial.ttf'):
            try:
                return ImageFont.truetype(f, sz)
            except OSError:
                continue
        return ImageFont.load_default()

    maps_dir = OUT / 'simulator' / 'overlays' / 'maps'
    maps_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    units_by_stake = {}
    for uid, name, sid, cell in units_meta:
        units_by_stake.setdefault(sid, []).append((uid, name, cell))
    specials = {s['id']: [(f"U-{s['id']}-B{j + 1}", sp) for j, sp in enumerate(s.get('special', []))] for s in WORLD['stakes']}
    PAL = ['#fde2c8', '#d9ecd0', '#d6e4f5', '#f5d6e6', '#efe9c4', '#d9d3f0', '#cfeee9']

    def render(view, longest, title, stake=None, out_name='', org_ids=()):
        vx0, vy0, vx1, vy1 = view
        (mx0, my0), (mx1, my1) = merc(*ll(vx0, vy0)), merc(*ll(vx1, vy1))
        scale = longest / max(mx1 - mx0, my1 - my0)
        W, H = int((mx1 - mx0) * scale), int((my1 - my0) * scale)
        img = Image.new('RGBA', (W, H), '#f6f3ea')
        d = ImageDraw.Draw(img)
        km_px = W / (vx1 - vx0)

        def px(x, y):
            mx, my = merc(*ll(x, y))
            return (mx - mx0) * scale, (my1 - my) * scale

        # ward fills (stake map: this stake; area map: stakes)
        if stake:
            for i, (uid, name, cell) in enumerate(units_by_stake[stake['id']]):
                d.polygon([px(cell[0], cell[1]), px(cell[2], cell[1]), px(cell[2], cell[3]), px(cell[0], cell[3])], fill=PAL[i % len(PAL)])
        else:
            for i, s in enumerate(WORLD['stakes']):
                r = s['rect']
                d.polygon([px(r[0], r[1]), px(r[2], r[1]), px(r[2], r[3]), px(r[0], r[3])], fill=PAL[i % len(PAL)])
        # town street grids: a street every 100 address units (0.2 km), wider every 500
        for t in WORLD['towns']:
            gx0, gy0, gx1, gy1 = t['grid']
            cx, cy = t['center']
            if stake is None and km_px < 25:
                step = 1.0
            else:
                step = 0.2
            k = math.floor((gx0 - cx) / step)
            while cx + k * step <= gx1:
                x = cx + k * step
                major = abs(round(k * step / 1.0) - k * step / 1.0) < 1e-6
                d.line([px(x, gy0), px(x, gy1)], fill='#c9c2b0' if not major else '#b0a68e', width=1 if not major else 2)
                k += 1
            k = math.floor((gy0 - cy) / step)
            while cy + k * step <= gy1:
                y = cy + k * step
                major = abs(round(k * step / 1.0) - k * step / 1.0) < 1e-6
                d.line([px(gx0, y), px(gx1, y)], fill='#c9c2b0' if not major else '#b0a68e', width=1 if not major else 2)
                k += 1
            if stake is not None or km_px >= 25:
                f = font(max(11, int(km_px * 0.07)))
                d.text(px(cx + 0.05, gy1 - 0.05), 'Main Street', fill='#6b604a', font=f)
                d.text(px(gx0 + 0.05, cy + 0.12), 'Center Street', fill='#6b604a', font=f)
                d.line([px(cx, gy0), px(cx, gy1)], fill='#8c7d5c', width=3)
                d.line([px(gx0, cy), px(gx1, cy)], fill='#8c7d5c', width=3)
        # water
        rp = WORLD['reservoir']['points']
        d.polygon([px(*p) for p in rp], fill='#9cc3e6', outline='#4a7fb5')
        for r in WORLD['rivers']:
            d.line([px(*p) for p in r['points']], fill='#4a7fb5', width=max(3, int(r['width_km'] * km_px)), joint='curve')
        # roads
        for r in WORLD['roads']:
            w = 6 if r['kind'] == 'highway' else 4
            d.line([px(*p) for p in r['points']], fill='#8a5a1c', width=w + 2, joint='curve')
            d.line([px(*p) for p in r['points']], fill='#f2a33a' if r['kind'] == 'highway' else '#ffffff', width=w, joint='curve')
        # ward / stake boundaries and labels
        fl, fs = font(max(14, int(km_px * 0.12)), True), font(max(12, int(km_px * 0.08)))
        if stake:
            for uid, name, cell in units_by_stake[stake['id']]:
                d.line([px(cell[0], cell[1]), px(cell[2], cell[1]), px(cell[2], cell[3]), px(cell[0], cell[3]), px(cell[0], cell[1])], fill='#a12a2a', width=3)
                cx, cy = px((cell[0] + cell[2]) / 2, (cell[1] + cell[3]) / 2)
                tw = d.textlength(name, font=fl)
                d.text((cx - tw / 2, cy - 10), name, fill='#7a1f1f', font=fl, stroke_width=3, stroke_fill='#ffffff')
            r = stake['rect']
            d.line([px(r[0], r[1]), px(r[2], r[1]), px(r[2], r[3]), px(r[0], r[3]), px(r[0], r[1])], fill='#5b1010', width=6)
        else:
            for s in WORLD['stakes']:
                r = s['rect']
                d.line([px(r[0], r[1]), px(r[2], r[1]), px(r[2], r[3]), px(r[0], r[3]), px(r[0], r[1])], fill='#7a1f1f', width=3)
                cx, cy = px((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)
                tw = d.textlength(s['name'], font=fl)
                d.text((cx - tw / 2, cy - 10), s['name'], fill='#7a1f1f', font=fl, stroke_width=3, stroke_fill='#ffffff')
        # meetinghouses
        for s in WORLD['stakes']:
            for i, (x, y) in enumerate(s['buildings']):
                if not (vx0 <= x <= vx1 and vy0 <= y <= vy1):
                    continue
                X, Y = px(x, y)
                rad = 9 if i == 0 else 6
                d.rectangle([X - rad, Y - rad, X + rad, Y + rad], fill='#1d3557', outline='#ffffff', width=2)
                if stake and s['id'] == stake['id']:
                    lab = f"{s['name']} Center" if i == 0 else 'Meetinghouse'
                    d.text((X + rad + 4, Y - 8), lab, fill='#1d3557', font=fs, stroke_width=2, stroke_fill='#ffffff')
        # facilities, bridges
        for f in WORLD['facilities']:
            x, y = f['at']
            if not (vx0 <= x <= vx1 and vy0 <= y <= vy1):
                continue
            X, Y = px(x, y)
            col = {'hospital': '#c1121f', 'eoc': '#2a9d8f', 'fire': '#e85d04', 'dam': '#264653', 'care': '#6a4c93', 'power': '#555555'}.get(f['kind'], '#3a5a40')
            d.ellipse([X - 7, Y - 7, X + 7, Y + 7], fill=col, outline='#ffffff', width=2)
            if stake is not None or f['kind'] in ('hospital', 'dam', 'eoc', 'radio'):
                d.text((X + 10, Y + 2), f['name'], fill=col, font=fs, stroke_width=2, stroke_fill='#ffffff')
        for t in WORLD['towns']:
            if stake is None:
                X, Y = px(*t['center'])
                d.text((X + 8, Y - 30), t['name'].upper(), fill='#222222', font=font(max(16, int(km_px * 0.5)), True), stroke_width=3, stroke_fill='#ffffff')
        for r in WORLD['rivers'] + [WORLD['reservoir']]:
            p = r['points'][len(r['points']) // 2]
            if vx0 <= p[0] <= vx1 and vy0 <= p[1] <= vy1:
                X, Y = px(*p)
                d.text((X + 6, Y + 4), r['name'], fill='#1f4e79', font=fs, stroke_width=2, stroke_fill='#ffffff')
        # title banner and scale bar
        tf = font(max(18, W // 45), True)
        d.rectangle([0, 0, W, int(tf.size * 2.4)], fill='#1d3557')
        d.text((14, int(tf.size * 0.3)), title, fill='#ffffff', font=tf)
        d.text((14, int(tf.size * 1.35)), 'INVENTED EXAMPLE FOR DRILLS: no real place, unit or person. Not an official Church map.', fill='#cfe1f2', font=font(max(12, W // 80)))
        bar_km = 1 if km_px > 120 else 5
        X0, Y0 = 20, H - 30
        d.rectangle([X0, Y0, X0 + bar_km * km_px, Y0 + 8], fill='#222222')
        d.text((X0, Y0 - 22), f'{bar_km} km', fill='#222222', font=fs)
        buf = io.BytesIO()
        img.convert('RGB').save(buf, 'PNG', optimize=True)
        data = buf.getvalue()
        (maps_dir / out_name).write_bytes(data)
        (lw, ls), (le, ln) = ll(vx0, vy0), ll(vx1, vy1)
        base = {'image_path': f'simulator/overlays/maps/{out_name}', 'image_width_px': W, 'image_height_px': H, 'image_crs': 'EPSG:3857',
                'web_mercator_bounds': [mx0, my0, mx1, my1], 'google_maps_bounds': {'west': lw, 'south': ls, 'east': le, 'north': ln},
                'file_bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'kind': 'source_map_artwork',
                'map_id': out_name[:-4], 'recommended_opacity': 0.6, 'paper_label': title}
        for oid in org_ids:
            manifest.append({**base, 'overlay_id': f'{oid}-{out_name[:-4]}', 'org_id': oid})

    pad = 0.6
    for s in WORLD['stakes']:
        r = s['rect']
        ids = [s['id']] + [u[0] for u in units_by_stake[s['id']]] + [u for u, _ in specials[s['id']]]
        render((r[0] - pad, r[1] - pad, r[2] + pad, r[3] + pad), 1800, f"{s['name']}: wards and meetinghouses", stake=s,
               out_name=f"{s['id'].lower()}-stake-map.png", org_ids=ids)
    xs = [v for s in WORLD['stakes'] for v in (s['rect'][0], s['rect'][2])] + [16.5]
    ys = [v for s in WORLD['stakes'] for v in (s['rect'][1], s['rect'][3])]
    render((min(xs) - 1, min(ys) - 1, max(xs) + 1, max(ys) + 1), 2048, 'Juniper Plains Area: Larkspur Valley', out_name='area-map.png',
           org_ids=[WORLD['area']['id']] + [c['id'] for c in WORLD['councils']] + [WORLD['welfare']['region']['id']])
    with open(OUT / 'simulator' / 'overlays' / 'manifest.json', 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(manifest, indent=1))
    return len(manifest)


def main():
    files, units_meta = build()
    if '--check' in sys.argv:
        bad = [p for p, t in files.items() if not (OUT / p).is_file() or (OUT / p).read_text(encoding='utf-8') != t]
        print('example up to date' if not bad else f'example out of date: {bad}')
        return 1 if bad else 0
    for p, t in files.items():
        f = OUT / p
        f.parent.mkdir(parents=True, exist_ok=True)
        with open(f, 'w', encoding='utf-8', newline='\r\n' if str(p).endswith('.txt') else '\n') as fh:   # as .gitattributes
            fh.write(t)
    n = draw_maps(units_meta)
    # the drill configuration, with no paths in it: the simulator and the EOC use the folder loaded on their Setup tab
    sys.path.insert(0, str(HERE.parent))
    import drillconfig, orgpack, privacy  # noqa: E401
    pack = privacy.apply(orgpack.load(OUT), 'pseudonymized', files['simulation/salt.txt'].strip())
    cfg = drillconfig.build(pack, drill_spec(), '')
    with open(OUT / 'simulation' / 'drill-config.json', 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(cfg, ensure_ascii=False, indent=1))
    print(f'wrote {OUT}: {len(files)} files, {n} map records, drill configuration with {len(cfg["eocs"])} EOCs')
    return 0


if __name__ == '__main__':
    sys.exit(main())
