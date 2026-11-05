#!/usr/bin/env python3
"""Nothing about a real community in the public files.

GitHub Pages publishes every committed file, and the release assets go to anyone with the link. This test reads
every file git tracks (or would track), plus every text file inside the release ZIP and inside the one-file
installer, and fails on:

  0. a file shaped like an organization pack outside the invented example and the test fixture, or a path that must
     never be tracked (needs no private data, so it runs on every computer);
  1. a guarded term: the real region, its places, its scenario and its people. The terms are hashes (sha256, first
     16 hex digits) kept in secure data/public-guard-terms.json, so a computer without secure data skips this part;
  2. when the directory export is present on this laptop (secure data/<export>/csv/): any real unit name with a
     place in it (e.g. a ward or stake name), any real leader's full name, phone or email. A repository clone
     without secure data skips this part.

    python testing/test_public_files.py            # exit code 1 on any hit
    python testing/test_public_files.py --show     # print the hits (do NOT paste them anywhere public)

Add a term: python -c "import hashlib;print(hashlib.sha256('<term in lower case>'.encode()).hexdigest()[:16])", then add
the hash to secure data/public-guard-terms.json.
"""
import base64
import csv
import hashlib
import json
import io
import re
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SHOW = '--show' in sys.argv
GUARDED_FILE = REPO / 'secure data' / 'public-guard-terms.json'
GUARDED = set(json.loads(GUARDED_FILE.read_text(encoding='utf-8'))) if GUARDED_FILE.is_file() else set()
# anything shaped like an organization pack or a drill's private files: only the invented example and the test fixture may hold one
PACK_FILE = re.compile(r'(^|/)(contacts|contactmethods|organizations|buildings|building_organizations|relationships|addresses)\.csv$|(^|/)orgpack\.json$|\.local\.json$|(^|/)drill-(spec|config)[^/]*\.json$|(^|/)building-names\.json$|\.set\.json$', re.I)
PACK_OK = ('simulation/example/', 'testing/fixtures/')
NEVER_TRACKED = ('forms-source/', '.claude/', 'secure data/')
TEXT = {'.html', '.htm', '.js', '.json', '.md', '.txt', '.py', '.ps1', '.bat', '.sh', '.command', '.yml', '.yaml', '.css', '.csv',
        '.geojson', '.webmanifest', '.xml', '.svg', '.mime', ''}
SKIP = {'forms/vendor/jsQR.js'}
# words that say nothing about a community on their own (a private term made only of these is not checked)
GENERIC_WORDS = set('the of and a an at in on for to church office building center centre stake ward branch eoc city county fire station '
                    'emergency management manager north south east west upper lower main street road highway bridge river creek '
                    'meetinghouse chapel welfare self-reliance area council coordinating regional region drill flood earthquake '
                    'dam failure m duty officer department police sheriff hospital school public works'.split())          # third-party code tables
results = []


def check(name, ok, detail=''):
    results.append(ok)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f'  ({detail})' if detail and not ok else ''))


def h(t):
    return hashlib.sha256(t.encode()).hexdigest()[:16]


def ngrams(text):
    words = re.findall(r"[a-z0-9][a-z0-9.\-]*[a-z0-9]|[a-z0-9]", text.lower())
    for n in (1, 2, 3):
        for i in range(len(words) - n + 1):
            yield ' '.join(words[i:i + n])


def files():
    out = subprocess.run(['git', 'ls-files', '-co', '--exclude-standard'], cwd=REPO, capture_output=True, text=True, encoding='utf-8').stdout
    for rel in out.splitlines():
        p = REPO / rel
        if rel in SKIP or not p.is_file() or p.suffix.lower() not in TEXT and p.suffix.lower() != '.zip':
            continue
        if p.suffix.lower() == '.zip':
            with zipfile.ZipFile(p) as z:
                for n in z.namelist():
                    if Path(n).suffix.lower() in TEXT and not n.endswith('/'):
                        yield f'{rel}!{n}', z.read(n).decode('utf-8', 'ignore') + '\n' + n
            continue
        t = p.read_text(encoding='utf-8', errors='ignore')
        yield rel, t + '\n' + rel
        if rel.endswith('.bat') and 'Chunks = @(' in t:       # the one-file installer: decode its embedded files
            for m in re.finditer(r"Name = '([^']*)'.*?Chunks = @\((.*?)\n\s*\)", t, re.S):
                data = ''.join(re.findall(r"'([A-Za-z0-9+/=]+)'", m.group(2)))
                if Path(m.group(1)).suffix.lower() in TEXT:
                    yield f'{rel}!{m.group(1)}', base64.b64decode(data).decode('utf-8', 'ignore') + '\n' + m.group(1)


def private_terms():
    """Real unit names with a place, real leader names, phones and emails, from the export on this laptop (if any)."""
    terms = set()
    for exp in (REPO / 'secure data').glob('*/csv'):
        try:
            for o in csv.DictReader(open(exp / 'organizations.csv', encoding='utf-8-sig', newline='')):
                n = (o.get('org_name') or '').strip()
                if o.get('org_type') in ('Ward', 'Branch', 'Stake') and re.search(r'\d|Stake', n):
                    terms.add(n.lower())
            for c in csv.DictReader(open(exp / 'contacts.csv', encoding='utf-8-sig', newline='')):
                n = (c.get('person_name') or '').strip()
                if len(n.split()) >= 2:
                    terms.add(n.lower())
                for k in ('primary_phone', 'primary_email'):
                    v = (c.get(k) or '').strip().lower()
                    if len(v) > 7:
                        terms.add(v)
        except FileNotFoundError:
            continue
    return terms


def _norm(t):
    return ' '.join(re.findall(r"[a-z0-9][a-z0-9.\-]*[a-z0-9]|[a-z0-9]", str(t or '').lower().replace('_', ' ')))


def _json(p):
    try:
        return json.loads(p.read_text(encoding='utf-8-sig'))
    except Exception:
        return None


def public_example_text():
    """The invented example's own words (Juniper Plains, its scenario): a private term that also occurs there is generic."""
    parts = []
    for p in [REPO / 'simulation' / 'example' / 'world.json', *(REPO / 'simulation' / 'scenarios').glob('*.json'),
              *(REPO / 'simulation' / 'example' / 'juniper-plains' / 'simulation').glob('*.json')]:
        try:
            parts.append(p.read_text(encoding='utf-8', errors='ignore'))
        except OSError:
            pass
    return set(ngrams('\n'.join(parts)))


def private_simulation_terms():
    """Names a drill director wrote beside the export (secure data/<export>/simulation/): the drill spec's EOC ids
    and names and its partner agencies, the private scenarios' ids and names, the local bindings' unit, agency and
    place names, the building names. Loaded at run time only; a term the invented example also uses, or one plain
    word, is left out (too generic to mean the real community)."""
    raw = set()
    for sim in (REPO / 'secure data').glob('*/simulation'):
        for f in sim.glob('drill-spec*.json'):
            s = _json(f) or {}
            for e in s.get('eocs') or []:
                raw |= {e.get('id'), e.get('name')}
            for a in s.get('agencies') or []:
                raw |= {a.get('id'), a.get('name'), (a.get('contact') or '').split(',')[0], (a.get('place') or '').split(',')[0]}
        for f in list((sim / 'scenarios').glob('*.json')):
            s = _json(f) or {}
            raw |= {s.get('id'), s.get('name')}
            for x in s.get('scenarios') or []:          # the private catalog
                raw |= {x.get('id'), x.get('name')}
            for k, a in (s.get('agencies') or {}).items():
                raw |= {k, a.get('name'), (a.get('contact') or '').split(',')[0]}
        for f in sim.glob('*.local.json'):
            s = _json(f) or {}
            raw |= set((s.get('severity_override') or {}).keys())
            for inj in s.get('injects') or []:
                w = inj.get('where') or {}
                raw |= {w.get('unit')} | set(w.get('units') or [])
            for k, a in (s.get('agencies') or {}).items():
                raw |= {k, a.get('name'), (a.get('contact') or '').split(',')[0], (a.get('place') or '').split(',')[0]}
        for b in _json(sim / 'building-names.json') or []:
            if isinstance(b, dict):
                raw.add(b.get('name'))
    generic = public_example_text()
    out = set()
    for t in raw:
        n = _norm(t)
        if len(n) < 5 or n in generic:
            continue
        if ' ' not in n and not re.search(r'[\d\-]', n):
            continue                                     # one plain word ("area", a town alone) is too generic to fail on
        if all(w in GENERIC_WORDS for w in re.split(r'[\s\-]+', n)):
            continue                                     # only generic words ("church office building", "city eoc")
        out.add(n)
        parts = n.split('-')
        if len(parts) >= 3 and not all(w in GENERIC_WORDS for w in parts[:2]):
            out.add('-'.join(parts[:2]))                 # an id's stem ("<region>-<place>" of "<region>-<place>-m7.3") names the place too
    return out


def main():
    print('Public files: no real community')
    tracked = subprocess.run(['git', 'ls-files', '-co', '--exclude-standard'], cwd=REPO, capture_output=True, text=True, encoding='utf-8').stdout.splitlines()
    packs = [p for p in tracked if PACK_FILE.search(p) and not p.startswith(PACK_OK)] + [p for p in tracked if p.startswith(NEVER_TRACKED)]
    check('no organization pack, drill file or Church original outside the invented example and the fixture', not packs, packs[:5])
    hits, scanned = {}, 0
    priv = private_terms()
    phones_emails = {t for t in priv if '@' in t or re.fullmatch(r'[\d\-\(\) .+]+', t)}
    names = priv - phones_emails
    sim_terms = private_simulation_terms()
    lines_of = {}
    for rel, text in files():
        scanned += 1
        low = text.lower()
        found = {g for g in ngrams(text) if h(g) in GUARDED}
        found |= {t for t in phones_emails if t in low}
        if names or sim_terms:
            grams = set(ngrams(text))
            found |= {t for t in names if ' '.join(re.findall(r"[a-z0-9][a-z0-9.\-]*[a-z0-9]|[a-z0-9]", t)) in grams}
            sim_found = {t for t in sim_terms if t in grams or (re.search(r'[\d\-]', t) and t in low)}
            if sim_found:
                found |= sim_found
                ln = [i for i, line in enumerate(text.splitlines(), 1) if sim_found & (set(ngrams(line)) | {t for t in sim_found if t in line.lower()})]
                lines_of[rel] = ln
        if found:
            hits[rel] = found
    check(f'{scanned} public files and release members scanned', scanned > 100, scanned)
    if not GUARDED:
        print('  SKIP  no secure data/public-guard-terms.json on this computer: guarded terms not checked')
    check('no guarded term (the real region, its places, scenario and people)', not any(any(h(g) in GUARDED for g in v) for v in hits.values()),
          f'{sum(1 for v in hits.values() if any(h(g) in GUARDED for g in v))} files')
    if priv:
        check(f'no real unit name, leader name, phone or email from the export on this laptop ({len(priv)} values)',
              not any(any(h(g) not in GUARDED for g in v) for v in hits.values()),
              f'{sum(1 for v in hits.values() if any(h(g) not in GUARDED for g in v))} files')
    else:
        print('  SKIP  no directory export under secure data/ on this computer: real names not checked')
    if sim_terms:
        bad = [rel for rel, v in hits.items() if v & sim_terms]
        check(f'no private drill-spec, scenario, local-binding or building name from secure data/ ({len(sim_terms)} terms)', not bad, f'{len(bad)} files')
    if hits and SHOW:
        for rel, v in sorted(hits.items()):
            print(f'    {rel}: {sorted(v)[:6]}' + (f'  lines {lines_of[rel][:12]}' if rel in lines_of else ''))
    elif hits:
        print('    files with hits:', ', '.join(f"{r}" + (f" (lines {','.join(map(str, lines_of[r][:8]))})" if r in lines_of else '') for r in sorted(hits)[:25]),
              '(run with --show to list the terms; never paste them anywhere public)')
    ok = all(results)
    print(f'\n{sum(results)}/{len(results)} passed')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
