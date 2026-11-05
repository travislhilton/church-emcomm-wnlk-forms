#!/usr/bin/env python3
"""Set up Church of Jesus Christ EMCOMM for a Church community from its own directory export (Python standard library only).

Any stake or coordinating council can do this with its own data: export its organizations, leaders,
buildings and maps from the Church directory (CDOL) into the folder layout described in docs/COMMUNITY_SETUP.md, keep that
folder on the EOC laptop (never in a repository), and point this tool at it.

    python simulation/community.py check "<export root>"     # what is there, what each part enables, what is missing
    python simulation/community.py init  "<export root>"     # starter drill spec + building-names file beside the pack

`init` writes, only when they do not exist yet, into <export root>/simulation/:
  drill-spec.json       every stake as an optional stake EOC and every coordinating council under one optional
                        Council / Area EOC; fill in the Winlink call signs, which EOCs always have people, partner
                        agencies (a city EOC: ICS 213 / 213RR traffic only), then:  python simulation/drillconfig.py <spec>
  building-names.json   every building with its suggested name (stake-center convention or "<City> Meetinghouse, <street>");
                        replace the suggestions with the names people use locally
The export holds names and contacts: it never leaves the laptop; this tool reads it and writes beside it.
"""
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import orgpack  # noqa: E402

CSV_FILES = {
    'organizations.csv': 'councils, stakes, wards and branches (required)',
    'contacts.csv': 'leaders in their roles (required for names on reports, cards and the EOC identity)',
    'contactmethods.csv': 'phones and emails of the leaders',
    'addresses.csv': 'organization addresses',
    'buildings.csv': 'meetinghouses and their coordinates (required)',
    'building_organizations.csv': 'which units meet in which building (required)',
    'relationships.csv': 'how units, stakes and councils are linked',
}
MAP_FILES = {
    'simulator/organization_boundaries.geojson': 'unit and stake boundaries: the EOC Map tab, the wall map, the simulator map (required for any map)',
    'simulator/buildings.geojson': 'meetinghouse points on every map',
    'simulator/organization_locations.geojson': 'organization points for the simulator',
    'simulator/overlays/manifest.json': "the directory's own map artwork, placed on the map (EOC Map tab: 'Church directory maps'; simulator: overlay images)",
}


def check(root: Path) -> int:
    print(f'Export root: {root}')
    ok = True
    print('\nDirectory tables (csv/):')
    for f, what in CSV_FILES.items():
        p = root / 'csv' / f
        have = p.is_file()
        rows = sum(1 for _ in csv.DictReader(open(p, encoding='utf-8-sig', newline=''))) if have else 0   # fields may span lines
        req = '(required)' in what
        ok &= have or not req
        print(f"  {'OK ' if have else ('MISSING' if req else 'absent ')} {f:28} {rows:6} rows  {what}")
    print('\nMap data (simulator/):')
    for f, what in MAP_FILES.items():
        p = root / f
        have = p.is_file()
        n = ''
        if have and f.endswith('.geojson'):
            try:
                n = f"{len(json.loads(p.read_text(encoding='utf-8')).get('features', []))} features"
            except Exception as e:
                n, have = f'unreadable: {e}', False
        elif have:
            try:
                man = json.loads(p.read_text(encoding='utf-8'))
                art = [r for r in man if r.get('kind') == 'source_map_artwork']
                miss = sum(1 for r in art if not (root / r.get('image_path', '')).is_file())
                n = f'{len(art)} map images' + (f', {miss} image files missing' if miss else '')
            except Exception as e:
                n, have = f'unreadable: {e}', False
        print(f"  {'OK ' if have else 'absent '} {f:44} {n:28} {what}")
    if (root / 'csv' / 'organizations.csv').is_file():
        try:
            pack = orgpack.load(root)
            s = orgpack.summary(pack)
            print(f"\nPack: {s.get('councils')} councils, {s.get('stakes')} stakes, {s.get('units')} units ({s.get('wards')} wards, "
                  f"{s.get('branches')} branches), {s.get('buildings')} buildings, {s.get('contacts')} leaders in roles, states {', '.join(s.get('states') or [])}")
            named = sum(1 for b in pack['buildings'] if b.get('name_basis') not in (None, 'derived'))
            print(f"Building names: {named} named, {len(pack['buildings']) - named} derived "
                  f"({'from ' + str(orgpack.building_names_path(root)) if orgpack.building_names_path(root).is_file() else 'no building-names.json yet: run init'})")
        except Exception as e:
            ok = False
            print(f'\nPack: could not be built: {type(e).__name__}: {e}')
    print('\nWhat works with this export:')
    print('  EOC Message Center: set Setup -> Map data folder to this export root (or load a drill configuration built from it)')
    print('  Simulator: Setup -> 1. Organization pack -> this export root (or Setup -> Drill configuration)')
    print('  ' + ('Ready.' if ok else 'Not ready: add the required files above (docs/COMMUNITY_SETUP.md describes them).'))
    return 0 if ok else 1


def init(root: Path) -> int:
    pack = orgpack.load(root)
    out = root / 'simulation'
    out.mkdir(parents=True, exist_ok=True)
    spec_p, names_p = out / 'drill-spec.json', orgpack.building_names_path(root)
    if not spec_p.exists():
        scenario = suggested_scenario(root, pack)
        spec = {'kind': 'church_emcomm_drill_spec', 'v': 1, 'name': 'Drill: <your scenario> (edit)', 'scenario': scenario or '<scenario id>',
                'export': '..', 'privacy': 'pseudonymized',
                'event': {'name': 'DRILL: <scenario> (THIS IS AN EXERCISE)', 'type': '', 'sitrepHrs': '4', 'sitrepBy': 'Stake President'},
                'eocs': [{'id': orgpack_slug(s['name']), 'level': 'stake', 'stake': s['name'], 'manned': 'optional', 'winlink': []}
                         for s in sorted(pack['stakes'], key=lambda x: x['name'])]
                        + ([{'id': 'area', 'level': 'area', 'councils': [c['name'] for c in pack.get('councils', [])], 'manned': 'optional',
                             'building': '', 'winlink': [], 'name': 'Council / Area EOC (edit: where it would open)'}] if pack.get('councils') else []),
                'agencies': [],
                'note': ('Starter written by simulation/community.py. Set "manned": "always" for the EOCs that always have people, put each '
                         'EOC\'s Winlink call sign in "winlink", give the Council / Area EOC a building id (buildings in building-names.json), '
                         'add partner agencies that do not run this system (e.g. {"id": "city", "name": "<City> City EOC", "call": "<call>", '
                         '"contact": "<name, title>", "place": "<fire station>", "serves": ["<stake name>"]}), then run '
                         'python simulation/drillconfig.py <this file>. Never commit: it names organizations.')}
        spec_p.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding='utf-8')
        print(f'wrote {spec_p} ({len(spec["eocs"])} EOCs, all optional: edit it)')
        if not scenario:
            print('  "scenario" is "<scenario id>": put the id of your scenario there (a file in '
                  f'{root / "simulation" / "scenarios"}; check it with python simulation/scenario_check.py <file> --pack "{root}")')
        else:
            print(f'  "scenario": {scenario} (the developed scenario whose area covers this pack)')
    else:
        print(f'kept {spec_p} (already there)')
    if not names_p.exists():
        rows = [{'building_id': b['id'], 'address': b.get('address', ''), 'name': b.get('name', ''), 'basis': b.get('name_basis', 'derived'),
                 'source_url': None, 'note': 'Suggested: replace with the name people use locally.'} for b in pack['buildings']]
        names_p.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
        print(f'wrote {names_p} ({len(rows)} buildings with suggested names: edit them)')
    else:
        print(f'kept {names_p} (already there)')
    return 0


def suggested_scenario(root: Path, pack: dict) -> str:
    """The first developed scenario (the pack's own folder first, then the built-in catalog) whose area covers the pack,
    or '' when none does: the starter never names a scenario that was written for another community."""
    try:
        import engine
        bbox = orgpack.Index(pack).bbox()
        cat = engine.catalog(extra_dirs=[engine.pack_scenarios_dir(root)])
    except Exception:
        return ''
    for s in sorted(cat.get('scenarios', []), key=lambda s: s.get('source') != 'pack'):
        if s.get('status', 'developed') != 'outline' and bbox and engine.bbox_overlaps((s.get('applies') or {}).get('bbox'), bbox):
            return s['id']
    return ''


def orgpack_slug(name: str) -> str:
    import re
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def main(argv):
    if len(argv) < 2 or argv[0] not in ('check', 'init'):
        print(__doc__)
        return 2
    root = Path(argv[1])
    if not root.is_dir():
        print(f'{root}: not a folder')
        return 2
    return check(root) if argv[0] == 'check' else init(root)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
