#!/usr/bin/env python3
"""The invented example community (simulation/example/juniper-plains/) and the participant-package tools.

    python testing/test_example.py

1. The committed export matches simulation/example/world.json (build_example.py --check); community.py check
   passes; the pack loads with 2 councils, 8 stakes, 51 units and the three special units; every phone is
   in 555-01xx and every email @churchemcomm.sim; every map image in the manifest exists and is placed.
2. The developed scenario (copper-creek-dam) applies to the example and plans for every EOC of the example's
   drill configuration, with no placeholder left.
3. The drill configuration is portable: no absolute path in it (the simulator and the EOC use the folder
   loaded on their Setup tab).
4. A participant package of the example set builds (cards, pack, scenario, Winlink set), loads back as an
   organization pack, lists the scenario, and passes the leak check; a package is refused inside the
   repository; a real contact left in a package is caught by the leak check.
"""
import ast, copy, csv, importlib.util, io, json, os, re, shutil, subprocess, sys, tempfile, tokenize, zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EX = REPO / 'simulation' / 'example' / 'juniper-plains'
sys.path.insert(0, str(REPO / 'simulation'))
import drillconfig, engine, orgpack, privacy  # noqa: E402,E401
res = []


def check(label, ok, detail=''):
    ok = bool(ok); res.append(ok)
    print(('PASS ' if ok else 'FAIL ') + label + (' -- ' + str(detail)[:300] if detail and not ok else ''))


def run(*args):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, encoding='utf-8', errors='replace',
                          env=dict(os.environ, PYTHONIOENCODING='utf-8'), cwd=str(REPO))


# 1. the export
r = run(REPO / 'simulation' / 'example' / 'build_example.py', '--check')
check('the committed example matches world.json (python simulation/example/build_example.py)', r.returncode == 0 and 'up to date' in r.stdout, r.stdout + r.stderr)
r = run(REPO / 'simulation' / 'community.py', 'check', EX)
check('community.py check: every required table and map file present, pack builds', r.returncode == 0 and 'Ready.' in r.stdout, r.stdout[-400:])
pack = orgpack.load(EX)
flags = sorted(f for u in pack['units'] for f in u['flags'])
check('pack: 2 councils, 8 stakes, 51 units, care / retirement / language branches, welfare region',
      len(pack['councils']) == 2 and len(pack['stakes']) == 8 and len(pack['units']) == 51 and flags == ['care_facility', 'language_unit', 'retirement']
      and pack['welfare'].get('region', {}).get('name'), (len(pack['councils']), len(pack['stakes']), len(pack['units']), flags))
phones, emails = set(), set()
for f in (EX / 'csv').glob('*.csv'):
    t = f.read_text(encoding='utf-8')
    phones |= set(re.findall(r'\b\d{3}-\d{3}-\d{4}\b', t))
    emails |= set(re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', t))
check('pseudonymized example pack: no real full name, phone or email left (privacy.leaks is empty), every invented phone in 555-01xx',
      privacy.leaks(privacy.pseudonymize(pack, 'test-salt'), pack) == [] and all(re.fullmatch(r'\d{3}-555-01\d\d', c['phone']) for c in privacy.pseudonymize(pack, 'test-salt')['contacts'] if c['phone']),
      privacy.leaks(privacy.pseudonymize(pack, 'test-salt'), pack)[:3])
check('every phone 555-555-01xx, every email @churchemcomm.sim', phones and all(re.fullmatch(r'555-555-01\d\d', p) for p in phones)
      and emails and all(e.endswith('@churchemcomm.sim') for e in emails), sorted(p for p in phones if not p.startswith('555-555-01'))[:3])
man = json.loads((EX / 'simulator' / 'overlays' / 'manifest.json').read_text(encoding='utf-8'))
check('map manifest: every image exists, every record placed and tied to an organization',
      man and all((EX / m['image_path']).is_file() and len(m['web_mercator_bounds']) == 4 and m['org_id'] for m in man)
      and {m['org_id'] for m in man} >= {u['id'] for u in pack['units']}, len(man))

# 2. the scenario over the example, for every EOC of its drill configuration
sc = engine.load_scenario('copper-creek-dam')
check('copper-creek-dam applies to the example (catalog bounding box)', engine.bbox_overlaps(next(s for s in engine.catalog()['scenarios'] if s['id'] == 'copper-creek-dam')['applies']['bbox'], orgpack.Index(pack).bbox()))
cfg = json.loads((EX / 'simulation' / 'drill-config.json').read_text(encoding='utf-8'))
ps = privacy.apply(pack, 'pseudonymized', (EX / 'simulation' / 'salt.txt').read_text(encoding='utf-8').strip())
bad, sizes = [], {}
for e in cfg['eocs']:
    site = drillconfig.site_for(cfg, e['id'], [e['id']])
    rn = engine.plan(ps, sc, {'seed': 5, 'today': '2027-03-21', 'site': site, 'eoc': {'name': e['identity'].get('eocName', e['id'])}})
    sizes[e['id']] = len(rn['items'])
    left = [i['id'] for i in rn['items'] if re.search(r'\{[a-z_]+\}', i.get('text', '') + json.dumps(i.get('payload') or {}) + json.dumps(i.get('ics') or {}))]
    if left or not rn['items']:
        bad.append((e['id'], left[:2]))
check(f'the scenario plans for all {len(cfg["eocs"])} EOCs of the example drill, no placeholder left', not bad and len(sizes) == 9, (bad, sizes))
forms = [i for i in engine.plan(ps, sc, {'seed': 5, 'stakes': ['SLK']})['items'] if i['kind'] == 'form']
check('every simulated form is marked THIS IS AN EXERCISE', forms and all(i['payload'].get('exercise') in ('YES', True, 'true') for i in forms), len(forms))

# 3. a portable drill configuration
txt = json.dumps(cfg)
check('the drill configuration carries no absolute path (pack and map folder come from the laptop it is loaded on)',
      not re.search(r'[A-Za-z]:\\\\|\\\\\\\\|/Users/|/home/', txt) and cfg.get('pack', '') == '', cfg.get('pack'))

# 4. the participant package
pkg = importlib.util.spec_from_file_location('pkg', REPO / 'installer' / 'build-sim-package.py')
P = importlib.util.module_from_spec(pkg); pkg.loader.exec_module(P)
tmp = Path(tempfile.mkdtemp(prefix='emcomm-pkg-test-'))
try:
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        zp = P.build(EX / 'simulation' / 'sets' / 'CCD-1.set.json', tmp)
    names = zipfile.ZipFile(zp).namelist()
    top = 'CCD-1 participant package/'
    check('package: README, cards (PDF), organization pack, scenario, drill configuration, Winlink set',
          top + 'README.txt' in names and any(n.startswith(top + '1 Reference cards/') and n.endswith('.pdf') for n in names)
          and top + '2 Organization pack/csv/contacts.csv' in names and top + '2 Organization pack/simulation/scenarios/copper-creek-dam.json' in names
          and top + '2 Organization pack/simulation/drill-config.json' in names and any(n.startswith(top + '3 Winlink training set/CCD-1/CCD-1 01') for n in names), len(names))
    ex = tmp / 'x'
    zipfile.ZipFile(zp).extractall(ex)
    pk = ex / 'CCD-1 participant package' / '2 Organization pack'
    p2 = orgpack.load(pk)
    salt = (EX / 'simulation' / 'salt.txt').read_text(encoding='utf-8').strip()
    real = {P.hashed_id(salt, 'position', c['id']): c for c in pack['contacts']}
    same = [c['id'] for c in p2['contacts'] if c['id'] in real and c['name'] == real[c['id']]['name']]
    check('the package\'s pack loads (51 units) and every leader is pseudonymized (own name replaced)',
          len(p2['units']) == 51 and len(p2['contacts']) == len(pack['contacts']) and len(real.keys() & {c['id'] for c in p2['contacts']}) == len(pack['contacts']) and not same,
          (len(p2['units']), len(p2['contacts']), same[:3]))
    # the package's names are final: the simulator shows the same people the package was built with
    psalt = (pk / 'simulation' / 'salt.txt').read_text(encoding='utf-8').strip()
    again = privacy.pseudonymize(p2, psalt)
    check('the package loads labelled pseudonymized, and loading it for a drill keeps every name, phone and email',
          p2['privacy'] == 'pseudonymized' and again['contacts'] == p2['contacts'] and again['units'] == p2['units'] and privacy.apply(p2, 'real')['privacy'] == 'pseudonymized',
          (p2['privacy'], sum(a != b for a, b in zip(again['contacts'], p2['contacts']))))
    cfg_text = (pk / 'simulation' / 'drill-config.json').read_text(encoding='utf-8')
    p_bare = {k: v for k, v in p2.items() if k != 'pre_pseudonymized'}
    twice = {c['name'] for c in privacy.pseudonymize(p_bare, psalt)['contacts']}
    check('the drill configuration carries the package\'s names, none from a second pseudonymization',
          any(c['name'] in cfg_text for c in p2['contacts']) and not any(n in cfg_text for n in twice - {c['name'] for c in p2['contacts']}))
    p_local = copy.deepcopy(p2)
    p_local['contacts'].append({'id': 'LOCAL-1', 'person': 'LOCAL-1', 'name': 'Rhea Quillfeather', 'first': 'Rhea', 'last': 'Quillfeather', 'role': 'Emergency Response Director',
                                'org': p2['stakes'][0]['id'], 'mobile': '435-867-5309', 'phone': '', 'email': 'rhea@example.org', 'local': True})
    p_after = privacy.pseudonymize(p_local, psalt)
    lc = p_after['contacts'][-1]
    check('a local role added to a package is a real person: it alone is replaced, the package\'s names stay',
          p_after['contacts'][:-1] == p2['contacts'] and lc['first'] != 'Rhea' and '867' not in lc['mobile'] and 'rhea@' not in lc['email'], lc)
    (pm := pk / 'simulation' / orgpack.PACKAGE_MARKER).unlink()
    check('without the marker file a pack is never treated as already pseudonymized, whatever its label says',
          'pre_pseudonymized' not in orgpack.load(pk) and orgpack.load(pk)['privacy'] == 'real')
    pm.write_text('{}', encoding='utf-8')
    crow = list(csv.DictReader(open(pk / 'csv' / 'contacts.csv', encoding='utf-8')))
    real_ids = {c['id'] for c in pack['contacts']} | {c['person'] for c in pack['contacts']}
    check('package contacts.csv: person and position ids are salted hashes (no directory id), no active_date or profile_checked column',
          crow and not ({'active_date', 'profile_checked'} & set(crow[0])) and not any(r['position_id'] in real_ids or r['person_id'] in real_ids for r in crow)
          and all(r['position_id'].startswith('POS-') and r['person_id'].startswith('PER-') for r in crow), sorted(crow[0])[:20])
    check('the package lists its scenario from the pack\'s own folder', any(s['id'] == 'copper-creek-dam' and s.get('source') == 'pack' for s in engine.catalog(extra_dirs=[engine.pack_scenarios_dir(pk)])['scenarios']))
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            P.build(EX / 'simulation' / 'sets' / 'CCD-1.set.json', REPO / 'dist')
        refused = False
    except SystemExit as e:
        refused = 'never written into the repository' in str(e)
    check('a package is refused inside the repository', refused)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            P.build(EX / 'simulation' / 'sets' / 'CCD-1.set.json', REPO / 'docs' / 'secure data' / 'x')
        refused = False
    except SystemExit as e:
        refused = 'never written into the repository' in str(e)
    check('a folder merely named "secure data" elsewhere in the repository is refused too (only ROOT/secure data/ is allowed)', refused and not (REPO / 'docs' / 'secure data').exists())
    # an export with no simulator/ folder and no optional tables; a scenario without a catalog entry
    ex2 = tmp / 'ex2'
    shutil.copytree(EX / 'csv', ex2 / 'csv'); shutil.copytree(EX / 'simulation', ex2 / 'simulation')
    r = run(REPO / 'simulation' / 'community.py', 'check', ex2)
    p3 = orgpack.load(ex2)
    check('an export without its simulator/ (map) folder: community.py check says Ready and the pack loads (51 units, no boundaries)',
          r.returncode == 0 and 'Ready.' in r.stdout and len(p3['units']) == 51 and all(u['bbox'] is None for u in p3['units']), r.stdout[-300:])
    ex3 = tmp / 'ex3'
    shutil.copytree(EX / 'csv', ex3 / 'csv')
    for f in ('contacts.csv', 'contactmethods.csv', 'relationships.csv'):
        (ex3 / 'csv' / f).unlink()
    r = run(REPO / 'simulation' / 'community.py', 'check', ex3)
    p4 = orgpack.load(ex3)
    check('an export without contacts, contact methods and relationships: the pack loads (no leaders), community.py check does not crash',
          len(p4['units']) == 51 and p4['contacts'] == [] and 'Traceback' not in r.stdout + r.stderr, (r.stdout + r.stderr)[-300:])
    sc_zz = json.loads((REPO / 'simulation' / 'scenarios' / 'copper-creek-dam.json').read_text(encoding='utf-8'))
    sc_zz['id'] = 'zz-scratch'
    (ex2 / 'simulation' / 'scenarios').mkdir(parents=True, exist_ok=True)
    (ex2 / 'simulation' / 'scenarios' / 'zz-scratch.json').write_text(json.dumps(sc_zz), encoding='utf-8')
    (ex2 / 'simulation' / 'sets' / 'ZZ-1.set.json').write_text(json.dumps({'kind': 'church_emcomm_sim_set', 'v': 1, 'code': 'ZZ-1', 'name': 'scratch', 'private': False,
        'export': '../..', 'scenario': 'zz-scratch', 'drill_spec': '../drill-spec.json', 'maps': 'none'}), encoding='utf-8')
    with contextlib.redirect_stdout(io.StringIO()):
        zz = P.build(ex2 / 'simulation' / 'sets' / 'ZZ-1.set.json', tmp / 'out')
    zc = json.loads(zipfile.ZipFile(zz).read('ZZ-1 participant package/2 Organization pack/simulation/scenarios/catalog.json'))
    check('a scenario with no catalog entry gets one written into the package (id, name, hazard, duration, area), never an empty list',
          [s['id'] for s in zc['scenarios']] == ['zz-scratch'] and zc['scenarios'][0]['name'] and zc['scenarios'][0]['duration_min'] == 240 and len(zc['scenarios'][0]['applies']['bbox']) == 4, zc['scenarios'])
    # the cards are checked before anything is printed: a real phone written as bare digits is still caught
    real_phone = next(c['primary_phone'] for c in csv.DictReader(open(EX / 'csv' / 'contacts.csv', encoding='utf-8')) if c['primary_phone'])
    (ex2 / 'simulation' / 'zz.cards.json').write_text(json.dumps({'kind': 'church_emcomm_scenario_cards', 'v': 1, 'code': 'ZZ-1', 'private': True,
        'cards': [{'no': 'A', 'file': 'Leak', 'role': 'All', 'front': {'title': 'Call', 'blocks': [{'note': 'Call ' + re.sub(r'\D', '', real_phone)}]}}]}), encoding='utf-8')
    (ex2 / 'simulation' / 'sets' / 'ZZ-2.set.json').write_text(json.dumps({'kind': 'church_emcomm_sim_set', 'v': 1, 'code': 'ZZ-2', 'name': 'scratch', 'private': True,
        'export': '../..', 'scenario': 'zz-scratch', 'cards': '../zz.cards.json', 'maps': 'none'}), encoding='utf-8')
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            P.build(ex2 / 'simulation' / 'sets' / 'ZZ-2.set.json', tmp / 'out2')
        refused = ''
    except SystemExit as e:
        refused = str(e)
    check('the leak check reads the cards file and its rendered pages before printing: a real phone written as bare digits refuses the package',
          'in the cards' in refused and not (tmp / 'out2').exists(), refused[:200])
    check('find_secrets: phones by their digits however written, names as whole words only',
          P.find_secrets('call (555) 555-0114 now', {'555-555-0114'}) == ['555-555-0114'] and P.find_secrets('Joann Lee', {'Ann Lee'}) == [] and P.find_secrets('ask ann lee.', {'Ann Lee'}) == ['Ann Lee'])
    # the leak check: a real (here: example) leader's name left in a file is caught
    lk = P.pseudonymized_csv(EX, tmp / 'leak', P.privacy.salt_for(EX))
    some = next(iter(c['person_name'] for c in csv.DictReader(open(EX / 'csv' / 'contacts.csv', encoding='utf-8'))))
    check('the leak check knows every leader\'s real name, phone and email (and none of the pseudonyms)', some in lk['secrets'] and len(lk['secrets']) > 300, len(lk['secrets']))
    agency_names = set()
    stripped = P.strip_agency_contacts({'agencies': [{'name': 'X City EOC', 'contact': 'Jordan Example, Fire Chief'}]}, agency_names)
    check('partner-agency contacts keep only the title; the name joins the leak check', stripped['agencies'][0]['contact'] == 'Fire Chief' and agency_names == {'Jordan Example'})
    r = run(REPO / 'installer' / 'make-scenario-samples.py', REPO / 'secure data' / 'x' / 'source.json')
    check('the training-set generator refuses a secure-data source without --out', r.returncode != 0 and 'never into the repository' in (r.stdout + r.stderr), (r.stdout + r.stderr)[-200:])
    # PRIVATE BUILD follows the source, not --out: the public example built into a folder keeps the public wording;
    # the same source copied outside the repository (a local one) is marked; one ICS message may name its own agency
    src = json.loads((REPO / 'training' / 'scenario-samples-src' / 'copper-creek-dam.json').read_text(encoding='utf-8'))
    run(REPO / 'installer' / 'make-scenario-samples.py', REPO / 'training' / 'scenario-samples-src' / 'copper-creek-dam.json', '--out', tmp / 'pub')
    src.update(code='TWO-1'); src['ics213rr'][0]['agency'] = {'name': 'Juniper County EOC', 'place': 'the county building', 'short': 'County EOC'}
    (tmp / 'two.json').write_text(json.dumps(src), encoding='utf-8')
    run(REPO / 'installer' / 'make-scenario-samples.py', tmp / 'two.json', '--out', tmp / 'two')
    pub_rd = (tmp / 'pub' / 'CCD-1' / 'README.txt').read_text(encoding='utf-8') if (tmp / 'pub' / 'CCD-1' / 'README.txt').is_file() else ''
    two_rd = (tmp / 'two' / 'TWO-1' / 'README.txt').read_text(encoding='utf-8') if (tmp / 'two' / 'TWO-1' / 'README.txt').is_file() else ''
    check('training set: the public example built with --out is not marked PRIVATE BUILD; a local source is',
          pub_rd.startswith('Church of Jesus Christ EMCOMM Winlink training set CCD-1') and 'PRIVATE BUILD' not in pub_rd and 'PRIVATE BUILD' in two_rd)
    two_names = [p.name for p in (tmp / 'two' / 'TWO-1').glob('*ICS 213RR*')] if (tmp / 'two' / 'TWO-1').is_dir() else []
    two_json = tmp / 'two' / 'TWO-1' / 'ICS213RR samples.json'   # with no Winlink here the forms wait for the installer: their names are in this file
    if two_json.is_file():
        two_names += [x['name'] for x in json.loads(two_json.read_text(encoding='utf-8'))['samples']]
    check('training set: an ICS message with its own agency is named for it (file name, README); the others keep the set\'s',
          any(' - County EOC to Stake - ' in n for n in two_names) and any(' - City EOC to Stake - ' in n for n in two_names)
          and 'Juniper County EOC at the county building' in two_rd and 'Larkspur City EOC' in two_rd, two_names[:3])
    cards = importlib.util.spec_from_file_location('cards', REPO / 'training' / 'build-scenario-cards.py')
    C = importlib.util.module_from_spec(cards); cards.loader.exec_module(C)
    pc = tmp / 'private.cards.json'
    pc.write_text(json.dumps({'kind': 'church_emcomm_scenario_cards', 'v': 1, 'code': 'T', 'private': True, 'cards': []}), encoding='utf-8')
    try:
        C.main([str(pc), '--out', str(REPO / 'training' / 'scenario-cards' / 'T')]); refused = False
    except SystemExit as e:
        refused = 'never written into the repository' in str(e)
    check('private cards are refused for an output folder in the repository', refused and not (REPO / 'training' / 'scenario-cards' / 'T').exists())
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# 6. development from Windows or macOS: the same bytes in every checkout, the same release from every machine
def attr(path, name):
    return subprocess.run(['git', 'check-attr', name, '--', path], cwd=REPO, capture_output=True, text=True).stdout.strip().rsplit(': ', 1)[-1]


tracked_txt = subprocess.run(['git', '-c', 'core.quotepath=off', 'ls-files', '-z', 'templates', 'training'], cwd=REPO, capture_output=True).stdout.decode('utf-8').split('\0')
defs = [n for n in tracked_txt if n.endswith('.txt')]
check('every Winlink template definition is CRLF in every checkout, the practice forms and training sets too (LF: "Form file does not exist")',
      len(defs) >= 25 and all(attr(n, 'eol') == 'crlf' for n in defs) and all(b'\r\n' in (REPO / n).read_bytes() for n in defs), [n for n in defs if attr(n, 'eol') != 'crlf'][:3])
check('source files are LF in every checkout, whatever core.autocrlf says on that machine, and batch files stay CRLF',
      attr('simulation/engine.py', 'eol') == 'lf' and attr('forms/index.html', 'eol') == 'lf' and attr('installer/install.bat', 'eol') == 'crlf' and attr('installer/install.sh', 'eol') == 'lf')
modes = subprocess.run(['git', 'ls-files', '-s', '.githooks/pre-commit'], cwd=REPO, capture_output=True, text=True).stdout
check('the commit hook is stored executable: on a Mac git skips a hook that is not', modes.startswith('100755'), modes)
brl = importlib.util.spec_from_file_location('brl', REPO / 'installer' / 'build-release.py')
BR = importlib.util.module_from_spec(brl); brl.loader.exec_module(BR)
shipped = BR.shared_files()
check('the release ships git\'s file list: no .DS_Store, no __pycache__, no drill runs, every listed file present',
      len(shipped) > 100 and not [n for n in shipped if '.DS_Store' in n or '__pycache__' in n or '/runs/' in n] and all((REPO / n).is_file() for n in shipped + BR.ZIP_ONLY))
check('every simulator program file is in the release',
      {n for n in subprocess.run(['git', 'ls-files', 'simulation/*.py'], cwd=REPO, capture_output=True, text=True).stdout.split() if n.count('/') == 1} <= set(shipped))
check('a Windows script ships with CRLF even from an LF checkout, and nothing else is rewritten',
      b'\r\n' in BR.read_for_release('installer/install.bat') and b'\r\n' not in BR.read_for_release('installer/install.sh'))

# The README promises Python 3.8, and Python 3.12 relaxed f-strings: a newer Python runs code an older one refuses to
# start. An older Python finds this by compiling; a newer one needs its tokenizer to look inside the f-strings.
def fstring_problems():
    names = subprocess.run(['git', 'ls-files', '*.py'], cwd=REPO, capture_output=True, text=True).stdout.split()
    found = []
    for n in names:
        src = (REPO / n).read_text(encoding='utf-8-sig')
        if sys.version_info < (3, 12):
            try:
                compile(src, n, 'exec')
            except SyntaxError as exc:
                found.append(f'{n}:{exc.lineno}')
            continue
        stack, depth = [], 0
        for t in tokenize.generate_tokens(io.StringIO(src).readline):
            if t.type == tokenize.FSTRING_START:
                q = t.string.lstrip('rRfFbBuU')
                if stack and depth and q[0] == stack[-1][0][0] and (len(stack[-1][0]) == 1 or len(q) == 3):
                    found.append(f'{n}:{t.start[0]}')
                stack.append((q, depth)); depth = 0
            elif t.type == tokenize.FSTRING_END:
                depth = stack.pop()[1]
            elif stack and t.type == tokenize.OP and t.string in '{}':
                depth += 1 if t.string == '{' else -1
            elif stack and depth and (t.type == tokenize.COMMENT or (t.type == tokenize.STRING and ('\\' in t.string or (t.string.lstrip('rRbBuU')[0] == stack[-1][0][0] and len(stack[-1][0]) == 1)))):
                found.append(f'{n}:{t.start[0]}')
    return found


fp = fstring_problems()
check('every Python file runs on the promised Python 3.8: no f-string only 3.12 and later accept', not fp, fp[:5])


# Two more that only an older Python shows: write_text(newline=) needs 3.10, and before 3.9 __file__ is relative when a
# script starts from its own folder, so Path(__file__).parent is '.' and its .parent is '.' too (the EOC lost its forms).
def older_python_problems(src):
    found = []
    for x in ast.walk(ast.parse(src)):
        if isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and x.func.attr in ('write_text', 'read_text') and any(k.arg == 'newline' for k in x.keywords):
            found.append(x.lineno)
        if isinstance(x, ast.Attribute) and x.attr == 'parent' and isinstance(x.value, ast.Call) and any(isinstance(a, ast.Name) and a.id == '__file__' for a in x.value.args):
            found.append(x.lineno)
    return found


check('the older-Python scan finds write_text(newline=) and an unresolved Path(__file__).parent',
      sorted(older_python_problems("p.write_text(a,\n  newline='')\nB = Path(__file__).parent\nC = Path(__file__).resolve().parent\n")) == [1, 3])
op = [f'{n}:{ln}' for n in subprocess.run(['git', 'ls-files', '*.py'], cwd=REPO, capture_output=True, text=True).stdout.split()
      for ln in older_python_problems((REPO / n).read_text(encoding='utf-8-sig'))]
check('every Python file runs on the promised Python 3.8: no write_text(newline=), every script path resolved', not op, op[:5])

# The installers retire old practice forms. The real function from each installer runs on scratch folders, never Winlink's.
def practice_cases(root):
    src, pub, priv = root / 'src', root / 'pub', root / 'priv'
    for d in (src, pub, priv):
        d.mkdir(parents=True)
    for n in ('Practice 1 - Report - New Ward.txt', 'Practice_1_Report_New_Ward.html', 'README.txt', 'Viewer.html'):
        (src / n).write_text('new', encoding='utf-8')
    for n in ('Practice 1 - Report - New Ward.txt', 'Practice 7 - Report - Old Ward.txt', 'Practice_7_Report_Old_Ward.html', 'My notes.txt', 'Practice plan.txt'):
        (pub / n).write_text('old', encoding='utf-8')
    (priv / 'README.txt').write_text('built over YOUR directory export (pseudonymized contacts) - keep this folder private', encoding='utf-8')
    (priv / 'Practice 3 - Report - Real Ward.txt').write_text('private', encoding='utf-8')


def practice_ok(root):
    pub = {p.name: p.read_text(encoding='utf-8') for p in (root / 'pub').iterdir()}
    priv = {p.name: p.read_text(encoding='utf-8') for p in (root / 'priv').iterdir()}
    want = {'Practice 1 - Report - New Ward.txt': 'new', 'Practice_1_Report_New_Ward.html': 'new', 'README.txt': 'new', 'Viewer.html': 'new', 'My notes.txt': 'old', 'Practice plan.txt': 'old'}
    return pub == want and len(priv) == 2 and priv['Practice 3 - Report - Real Ward.txt'] == 'private' and 'private' in priv['README.txt'], (pub, priv)


def practice_fn(rel):
    m = re.search(r'# PRACTICE-SYNC:BEGIN(.*?)# PRACTICE-SYNC:END', (REPO / rel).read_bytes().decode('utf-8'), re.S)
    return m.group(1).replace('\r\n', '\n') if m else ''


git_exe = shutil.which('git')
bash = str(Path(git_exe).resolve().parent.parent / 'bin' / 'bash.exe') if os.name == 'nt' and git_exe else shutil.which('bash')
ps = shutil.which('powershell') or shutil.which('pwsh')
ran = 0
if bash and Path(bash).is_file():
    root = tmp / 'practice-sh'; practice_cases(root); ran += 1
    with open(root / 'run.sh', 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('set -u\n' + practice_fn('installer/install.sh') + 'sync_practice src pub\nsync_practice src priv\nexit 0\n')
    r = subprocess.run([bash, 'run.sh'], cwd=str(root), capture_output=True, text=True, encoding='utf-8', errors='replace')
    good, seen = practice_ok(root)
    check('install.sh retires old practice forms, keeps other files, leaves a private set alone', r.returncode == 0 and good, (r.stdout + r.stderr, seen))
if ps:
    root = tmp / 'practice-ps'; practice_cases(root); ran += 1
    with open(root / 'run.ps1', 'w', encoding='utf-8', newline='\r\n') as fh:
        fh.write("function Write-OK { param($m) }\nfunction Write-Warn { param($m) }\n" + practice_fn('installer/install.ps1')
                 + "$a = Sync-PracticeForms (Join-Path $PWD 'src') (Join-Path $PWD 'pub')\n$b = Sync-PracticeForms (Join-Path $PWD 'src') (Join-Path $PWD 'priv')\nif ($a -ne 4 -or $b -ne -1) { exit 3 }\n")
    r = subprocess.run([ps, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', 'run.ps1'], cwd=str(root), capture_output=True, text=True, encoding='utf-8', errors='replace')
    good, seen = practice_ok(root)
    check('install.ps1 retires old practice forms, keeps other files, leaves a private set alone', r.returncode == 0 and good, (r.returncode, r.stdout + r.stderr, seen))
check('the practice-form retirement ran under at least one installer here', ran >= 1, ran)
shutil.rmtree(tmp, ignore_errors=True)

print(f'\n{sum(res)}/{len(res)} passed')
sys.exit(0 if all(res) else 1)
