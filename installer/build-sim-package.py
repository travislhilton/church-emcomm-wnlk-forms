#!/usr/bin/env python3
"""Participant package for one simulation set: cards, organization pack, scenario and Winlink training set in one zip.

    python installer/build-sim-package.py "<set.json>"                 # zip in the set's "out" folder
    python installer/build-sim-package.py "<set.json>" --out "<folder>"
    python installer/build-sim-package.py "<set.json>" --maps none      # none | stakes (default) | all

A SET is a small manifest kept beside a community's directory export (never in the repository), for example
secure data/<export>/simulation/sets/<CODE>.set.json:

  {"kind": "church_emcomm_sim_set", "v": 1, "code": "<CODE>", "name": "...", "private": true,
   "export": "../..",                         the export root (csv/, simulator/, simulation/)
   "scenario": "<scenario id>",              <export>/simulation/scenarios/<id>.json (+ <id>.local.json beside the export)
   "drill_spec": "../drill-spec.json",        the drill spec (EOCs, call signs, partner agencies)
   "training": "../training/<source>.json",   the Winlink training set source (optional)
   "cards": "../cards/<CODE>.cards.json",     the set's reference cards (optional; training/build-scenario-cards.py)
   "maps": "stakes",                          directory map images: none, the drill's stakes, or all
   "out": "../../../packages"}                where the zip goes (outside the repository or under secure data/)
  Paths are relative to the set file.

The package is for the drill's participants only. A marker file keeps its names when the simulator loads it, and
real-contact mode does not apply to it. Contacts are PSEUDONYMIZED with the pack's own salt (the same
invented names the simulator shows in a pseudonymized drill): last names kept, first names, phones and emails
invented. Directory ids of people (person and position ids) become salted hashes; the contacts' dates and
profile flags are dropped. Partner-agency contacts keep only their title. Contacts of callings the simulator does
not use are dropped. A leak check refuses the package if any real phone (compared by its digits), email or full
name is left in it: in the cards file and every rendered card page before anything is printed, then in every text
file of the package. A package is never written inside the repository except under its git-ignored secure data/.

Layout of the zip (<CODE> participant package/):
  README.txt                      what is inside, how to load it, keep it private
  1 Reference cards/              the set's cards (PDF)
  2 Organization pack/            export-style folder: csv/, simulator/ (maps), simulation/ (scenario, local
                                  binding, drill spec and configuration, building names, salt)
  3 Winlink training set/<CODE>/  filled forms ready to copy into Winlink Express (ICS 213RR forms built from this
                                  station's standard form when it has one)
"""
import csv
import hashlib
import importlib.util
import io
import json
import re
import shutil
import sys
import tempfile
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'simulation'))
import drillconfig  # noqa: E402
import engine  # noqa: E402
import orgpack  # noqa: E402
import privacy  # noqa: E402


def _mod(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _csv_rows(p: Path) -> list:
    with open(p, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def _write_csv(p: Path, rows: list, fields: list):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator='\n', extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def _opt_rows(p: Path) -> list:
    return _csv_rows(p) if p.is_file() else []


# contacts.csv columns that say something about the real record and nothing the simulator needs
DROP_CONTACT_COLUMNS = ('active_date', 'profile_checked')


def hashed_id(salt: str, kind: str, value: str) -> str:
    """A directory id (person, position) replaced by a salted hash: stable within the package, not the real id."""
    if not value:
        return ''
    return f"{kind[:3].upper()}-{hashlib.sha256(f'{salt}|{kind}|{value}'.encode('utf-8')).hexdigest()[:12]}"


def is_phone(v: str) -> bool:
    v = (v or '').strip()
    return '@' not in v and len(privacy.digits(v)) >= 10 and not re.search(r'[A-Za-z]', v)


def find_secrets(text: str, secrets: set) -> list:
    """The secrets present in a text: names and emails as whole words (any case); phones by their digits, however
    they are written (435-555-0123, (435) 555-0123, 4355550123)."""
    low = text.lower()
    hits = []
    phone_digits = {privacy.digits(m) for m in re.findall(privacy.PHONE_RE, text)}
    for s in secrets:
        if is_phone(s):
            if privacy.digits(s) in phone_digits:
                hits.append(s)
        elif s and re.search(r'(?<![\w@.])' + re.escape(s.lower()) + r'(?![\w@])', low):
            hits.append(s)
    return hits


def pseudonymized_csv(export: Path, dest: Path, salt: str) -> dict:
    """Copy the directory tables with the contacts pseudonymized and their directory ids hashed.
    Returns what the leak check looks for."""
    real = orgpack.read_export(export)
    pseudo = privacy.pseudonymize(real, salt)
    P = {c['id']: c for c in pseudo['contacts']}
    orgphone = {o['id']: o.get('phone', '') for o in pseudo['stakes'] + pseudo['units']}
    for name in ('organizations', 'addresses', 'buildings', 'building_organizations', 'relationships'):
        rows = _opt_rows(export / 'csv' / f'{name}.csv')
        for r in rows:
            if 'source_url' in r:
                r['source_url'] = ''
        if rows or (export / 'csv' / f'{name}.csv').is_file():
            _write_csv(dest / 'csv' / f'{name}.csv', rows, list(rows[0].keys()) if rows else [])
    rows = [r for r in _opt_rows(export / 'csv' / 'contacts.csv') if r['position_id'] in P]
    for r in rows:
        c = P[r['position_id']]
        r.update({'person_name': c['name'], 'primary_phone': c.get('mobile') or c.get('phone') or '', 'primary_email': c.get('email', ''),
                  'source_url': '', 'position_id': hashed_id(salt, 'position', r['position_id']),
                  'person_id': hashed_id(salt, 'person', r.get('person_id', ''))})
    fields = [k for k in (list(rows[0].keys()) if rows else []) if k not in DROP_CONTACT_COLUMNS]
    _write_csv(dest / 'csv' / 'contacts.csv', rows, fields)
    out = []
    for m in _opt_rows(export / 'csv' / 'contactmethods.csv'):
        m['source_url'] = ''
        m['contact_uri'] = ''
        if m['owner_kind'] == 'Person':
            c = P.get(m['position_id'])
            if not c:
                continue
            m['position_id'] = hashed_id(salt, 'position', m['position_id'])
            if m.get('owner_id'):
                m['owner_id'] = hashed_id(salt, 'person', m['owner_id'])
            if m['contact_kind'] == 'Email':
                m['contact_value'] = c.get('email', '')
            elif m['contact_kind'] == 'Phone':
                m['contact_value'] = c.get('mobile') or c.get('phone') or ''
            else:
                continue
        else:
            if m['contact_kind'] == 'Phone' and orgphone.get(m['org_id']):
                m['contact_value'] = orgphone[m['org_id']]
            else:
                continue
        out.append(m)
    _write_csv(dest / 'csv' / 'contactmethods.csv', out, list(out[0].keys()) if out else [])
    secrets = set()
    allc = _opt_rows(export / 'csv' / 'contacts.csv')
    for c in allc:
        for k in ('primary_phone', 'primary_email'):
            if c.get(k) and len(c[k]) > 6:
                secrets.add(c[k].strip())
        if len((c.get('person_name') or '').split()) >= 2:
            secrets.add(c['person_name'].strip())
    for c in orgpack.load(export)['contacts']:      # with the local roles beside the export (ERD, specialist, HAM)
        for k in ('mobile', 'phone', 'email'):
            if c.get(k) and len(c[k]) > 6:
                secrets.add(c[k].strip())
        if len((c.get('name') or '').split()) >= 2:
            secrets.add(c['name'].strip())
    for m in _opt_rows(export / 'csv' / 'contactmethods.csv'):
        if m['owner_kind'] == 'Person' and len(m.get('contact_value') or '') > 6:
            secrets.add(m['contact_value'].strip())
    # no whitelist: privacy.pseudonymize never invents a value equal to a real one, so any hit is a leak
    return {'secrets': secrets, 'pack': pseudo}


# partner agencies keep only the contact's title (shared with the simulator server's LAN view)
strip_agency_contacts = privacy.strip_agency_contacts


def copy_maps(export: Path, dest: Path, mode: str, org_ids: set) -> int:
    sim, ds = export / 'simulator', dest / 'simulator'
    ds.mkdir(parents=True, exist_ok=True)
    keep = ('org_id', 'org_name', 'org_type', 'stake_id', 'council_id', 'label_longitude', 'label_latitude', 'special_unit', 'area_sq_km',
            'building_id', 'organization_ids', 'organization_names', 'address_raw', 'latitude', 'longitude', 'property_number',
            'location_kind', 'physical_location_known')
    for name in ('organization_boundaries', 'buildings', 'organization_locations'):
        f = sim / f'{name}.geojson'
        if f.is_file():
            gj = json.loads(f.read_text(encoding='utf-8-sig'))
            for ft in gj.get('features', []):
                ft['properties'] = {k: v for k, v in ft.get('properties', {}).items() if k in keep}
            (ds / f'{name}.geojson').write_text(json.dumps(gj, ensure_ascii=False), encoding='utf-8')
    mp = sim / 'overlays' / 'manifest.json'
    if mode == 'none' or not mp.is_file():
        return 0
    man = json.loads(mp.read_text(encoding='utf-8-sig'))
    sel = [r for r in man if r.get('kind') == 'source_map_artwork' and (mode == 'all' or r.get('org_id') in org_ids)]
    for r in sel:
        src = export / r['image_path']
        if src.is_file():
            t = dest / r['image_path']
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, t)
    (ds / 'overlays').mkdir(parents=True, exist_ok=True)
    (ds / 'overlays' / 'manifest.json').write_text(json.dumps(sel, ensure_ascii=False, indent=0), encoding='utf-8')
    return len(sel)


README = """{code} PARTICIPANT PACKAGE: {name}
{bar}

{privacy_note}
Built {today} with installer/build-sim-package.py.

Church of Jesus Christ EMCOMM: an independent volunteer project by Travis Hilton (W9TLH),
not an official Church product.

What is inside
--------------
1 Reference cards\\          {cards}
2 Organization pack\\        the organizations, buildings, maps ({maps} map images) and leaders
                            (pseudonymized) for the simulator and the EOC (Emergency
                            Operations Center) Message Center, with the scenario
                            "{scenario}" and the drill configuration in its simulation\\ folder
3 Winlink training set\\     {training}

How to use it
-------------
Install Church of Jesus Christ EMCOMM first (the one-file installer from the release page).
Copy this whole folder to the laptop, then:

EOC laptop (Message Center running):
  1. Setup -> This EOC -> Map data folder -> the full path of "2 Organization pack" -> Save.
  2. Setup -> Load a drill configuration -> 2 Organization pack\\simulation\\drill-config.json
     -> choose which EOC this laptop is.

Simulator laptop (the drill controller):
  Desktop -> Church of Jesus Christ EMCOMM Simulator.
  1. Setup -> Browse for the pack -> open the folders -> press Use "2 Organization pack" (the pack loads)
     (pseudonymized).
  2. Press "Set up from them" under step 1, choose which EOC this laptop is, press Set up this simulator.
  The scenario "{scenario}" appears in the list (it travels in the pack's simulation\\scenarios\\).

HAM operators (Winlink Express):
  Copy the folder 3 Winlink training set\\{code} into Winlink Express's Templates folder
  (C:\\RMS Express\\<your call sign>\\Templates, or Global Folders\\Templates), then
  New Message -> Select Template -> {code} -> pick a message. Its README lists every message
  in drill-clock order.

Print the reference cards double-sided ("flip on long edge"), one set per participant.
"""


def inside_repo_outside_secure(path: Path) -> bool:
    """True for a folder inside the repository that is not under ROOT/secure data/ (git-ignored)."""
    p, repo = Path(path).resolve(), ROOT.resolve()
    sec = (repo / 'secure data').resolve()
    if p != repo and repo not in p.parents:
        return False
    return not (p == sec or sec in p.parents)


def catalog_entry(sc: dict, pack: dict) -> dict:
    """A catalog entry for a scenario that has none (so the package never ships an empty catalog)."""
    bbox = (sc.get('applies') or {}).get('bbox') or orgpack.Index(pack).bbox()
    return {'id': sc['id'], 'name': sc.get('name', sc['id']), 'hazard': sc.get('hazard', ''), 'onset': sc.get('onset', ''),
            'duration_min': (sc.get('clock') or {}).get('duration_min', 240), 'status': 'developed',
            'applies': {'bbox': bbox} if bbox else {}, 'summary': sc.get('summary', ''), 'note': 'written by build-sim-package.py: the scenario had no catalog entry'}


def build(set_path: Path, out_dir: Path = None, maps: str = None) -> Path:
    S = json.loads(set_path.read_text(encoding='utf-8-sig'))
    base = set_path.parent
    code, sid = S['code'], S['scenario']
    export = (base / S.get('export', '../..')).resolve()
    out_dir = (out_dir or (base / S.get('out', '../../../packages'))).resolve()
    if inside_repo_outside_secure(out_dir):
        sys.exit(f'{out_dir}: a participant package is never written into the repository (use secure data/ or a folder outside it)')
    maps = maps or S.get('maps', 'stakes')
    work = Path(tempfile.mkdtemp(prefix='emcomm-pkg-'))
    top = work / f'{code} participant package'
    pk = top / '2 Organization pack'
    try:
        # 2. organization pack, pseudonymized with the pack's own salt (same names as a pseudonymized drill)
        salt = privacy.salt_for(export)
        leak = pseudonymized_csv(export, pk, salt)
        spec = json.loads((base / S['drill_spec']).read_text(encoding='utf-8-sig')) if S.get('drill_spec') else None
        stake_names = {e.get('stake') for e in (spec or {}).get('eocs', []) if e.get('stake')}
        pack = leak['pack']
        if spec:
            errs = drillconfig.validate_spec(spec, pack)
            if errs:
                sys.exit('Refused: the drill spec has problems (python simulation/drillconfig.py <spec> --check):\n' + '\n'.join(f'  - {e}' for e in errs))
        org_ids = set()
        for s in pack['stakes']:
            if s['name'] in stake_names:
                org_ids |= {s['id']} | set(s['units'])
        nmaps = copy_maps(export, pk, maps, org_ids)
        ps = pk / 'simulation'
        (ps / 'scenarios').mkdir(parents=True, exist_ok=True)
        sc_dir = engine.pack_scenarios_dir(export)
        local = export / 'simulation' / f'{sid}.local.json'
        src = sc_dir / f'{sid}.json'
        if not src.is_file():
            src = engine.SCENARIOS_DIR / f'{sid}.json'
        # partner-agency contacts in the scenario itself keep only their title, like the local binding and the drill spec
        agency_names = set()
        sc_obj = privacy.strip_agency_contacts(json.loads(src.read_text(encoding='utf-8-sig')), agency_names)
        lb = privacy.strip_agency_contacts(json.loads(local.read_text(encoding='utf-8-sig')), agency_names) if local.is_file() else None
        spec = privacy.strip_agency_contacts(json.loads(json.dumps(spec)), agency_names) if spec else None
        # a text that names an agency contact loses the name too; the leak check then looks for every one of them
        sc_obj, lb, spec = (privacy.scrub_names(x, agency_names) for x in (sc_obj, lb, spec))
        leak['secrets'] |= agency_names
        (ps / 'scenarios' / f'{sid}.json').write_text(json.dumps(sc_obj, ensure_ascii=False, indent=1), encoding='utf-8')
        cat_src = sc_dir / 'catalog.json' if (sc_dir / 'catalog.json').is_file() else engine.SCENARIOS_DIR / 'catalog.json'
        cat = json.loads(cat_src.read_text(encoding='utf-8-sig'))
        cat['scenarios'] = [x for x in cat['scenarios'] if x['id'] == sid]
        if not cat['scenarios']:
            cat['scenarios'] = [catalog_entry(sc_obj, pack)]
        (ps / 'scenarios' / 'catalog.json').write_text(json.dumps(cat, ensure_ascii=False, indent=1), encoding='utf-8')
        if lb is not None:
            (ps / f'{sid}.local.json').write_text(json.dumps(lb, ensure_ascii=False, indent=1), encoding='utf-8')
        for f in ('building-names.json',):
            if (export / 'simulation' / f).is_file():
                shutil.copy2(export / 'simulation' / f, ps / f)
        (ps / 'salt.txt').write_text(salt + '\n', encoding='utf-8')
        # the marker keeps the names of this package when it loads (no second pseudonymization), so write it
        # before the drill configuration below takes its names from the pack
        (ps / orgpack.PACKAGE_MARKER).write_text(json.dumps({'kind': 'emcomm-pseudonymized-package', 'v': 1}) + '\n', encoding='utf-8')
        if spec:
            spec['export'] = '..'
            spec['privacy'] = 'pseudonymized'
            (ps / 'drill-spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding='utf-8')
            # no paths in it: on the participant's laptop the simulator and the EOC use the folder loaded there
            cfg = drillconfig.build(privacy.apply(orgpack.load(pk), 'pseudonymized', salt), spec, '')
            (ps / 'drill-config.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding='utf-8')
        # 1. reference cards
        ncards = 0
        if S.get('cards'):
            cards = _mod(ROOT / 'training' / 'build-scenario-cards.py', 'scenario_cards')
            tmp = work / 'cards'

            def card_check(label, text):
                hits = find_secrets(text, leak['secrets'])
                if hits:
                    sys.exit(f'Refused: real contact details found in the cards ({label}): {len(hits)} hit(s); nothing was printed')
            cards.main([str((base / S['cards']).resolve()), '--out', str(tmp)], check=card_check)
            (top / '1 Reference cards').mkdir(parents=True, exist_ok=True)
            for f in sorted(tmp.glob('*.pdf')):
                shutil.copy2(f, top / '1 Reference cards' / f.name)
                ncards += 1
        # 3. Winlink training set (private build: ICS 213RR forms from this station's standard form)
        tr_text = 'none in this set'
        if S.get('training'):
            samples = _mod(ROOT / 'installer' / 'make-scenario-samples.py', 'scenario_samples')
            samples.build((base / S['training']).resolve(), top / '3 Winlink training set')
            n = len(list((top / '3 Winlink training set' / code).glob(f'{code} *.txt')))
            tr_text = f'{n} messages, ready to copy into Winlink Express'
        priv = ('PRIVATE. For the participants of this drill only. Do not post it, forward it, put it on a\n'
                'shared drive or in a repository. It names real units and buildings; the people in it are\n'
                'pseudonymized (last names kept; first names, phones and emails invented for the drill).') if S.get('private', True) else (
               'An INVENTED example community: no real unit, place or person. Safe to share.')
        with open(top / 'README.txt', 'w', encoding='utf-8', newline='\r\n') as fh:
            fh.write(README.format(code=code, name=S.get('name', ''), bar='=' * 70, today=date.today().isoformat(), privacy_note=priv,
                                   cards=f'{ncards} PDF files (print double-sided)' if ncards else 'none in this set',
                                   maps=nmaps, scenario=sid, training=tr_text))
        # leak check: no real phone, email or full name of a leader anywhere in the package
        bad = []
        for f in top.rglob('*'):
            if f.is_file() and f.suffix.lower() in ('.csv', '.json', '.txt', '.html', '.geojson'):
                t = f.read_text(encoding='utf-8', errors='ignore')
                hits = find_secrets(t, leak['secrets'])
                if hits:
                    bad.append((str(f.relative_to(top)), hits[:3]))
        if bad:
            sys.exit('Refused: real contact details found in the package:\n' + '\n'.join(f'  {f}: {len(h)} hit(s)' for f, h in bad))
        out_dir.mkdir(parents=True, exist_ok=True)
        zp = out_dir / f'{code} participant package {date.today().isoformat()}.zip'
        with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
            for f in sorted(top.rglob('*')):
                if f.is_file():
                    z.write(f, f.relative_to(work).as_posix())
        print(f'{zp}: {zp.stat().st_size // 1024} KB, {ncards} card PDFs, {nmaps} map images, leak check passed')
        return zp
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main(argv):
    if not argv or argv[0].startswith('-'):
        print(__doc__)
        return 2
    out = Path(argv[argv.index('--out') + 1]) if '--out' in argv else None
    maps = argv[argv.index('--maps') + 1] if '--maps' in argv else None
    build(Path(argv[0]).resolve(), out, maps)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
