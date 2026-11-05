#!/usr/bin/env python3
"""Winlink training sets (training/scenario-samples/<code>/): every form opens filled, builds its message,
and the EOC server reads it as intended.

    python testing/test_training_samples.py [--port=8183]

1. The committed set matches its source (regenerated into a temporary copy and compared file by file).
2. No real contact data: phones only in the fictitious 555-01xx range, emails only @churchemcomm.sim.
3. Each Church form opens in Chromium with its fields filled and THIS IS AN EXERCISE ticked; the form's own
   buildMsg() makes the Winlink message, which a scratch EOC server ingests from its Simulated Winlink inbox:
   the right form type, unit, exercise flag and key counts.
4. Each ICS 213RR is built the way install.ps1 builds it, from this station's standard Winlink ICS213RR form
   (skipped when Winlink Express is not installed): the form opens with every value in place and the right
   priority, and a message carrying those values is filed by the EOC as a work item for the agency.
Checks 3 and 4 need Playwright (python -m pip install playwright; python -m playwright install chromium);
without it they are skipped and the file checks still run.
"""
import filecmp, json, os, pathlib, re, shutil, subprocess, sys, tempfile, time, urllib.request

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / 'simulation'))
import engine  # noqa: E402

PORT = int(next((a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('--port=')), '8183'))
STD = pathlib.Path(r'C:\RMS Express\Standard Templates\ICS USA Forms')
res = []


def check(label, ok, detail=''):
    ok = bool(ok); res.append(ok)
    print(('PASS ' if ok else 'FAIL ') + label + (' -- ' + str(detail)[:200] if detail and not ok else ''))


def call(path, body=None, method=None):
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}{path}', data=json.dumps(body).encode() if body is not None else None,
                                 method=method or ('POST' if body is not None else 'GET'), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


sets = sorted(p for p in (REPO / 'training' / 'scenario-samples').iterdir() if p.is_dir())
check('at least one training set', sets, sets)

# 1. committed set == regenerated from source
tmp = pathlib.Path(tempfile.mkdtemp(prefix='samples_'))
shutil.copytree(REPO, tmp / 'repo', ignore=shutil.ignore_patterns('.git', 'secure data', 'dist', 'session-screenshots', 'forms-source', 'deck', '__pycache__', '*.db*'))
r = subprocess.run([sys.executable, str(tmp / 'repo' / 'installer' / 'make-scenario-samples.py')], capture_output=True, text=True, env=dict(os.environ, PYTHONIOENCODING='utf-8'))
check('the generator runs clean (every value within the standard form limits)', r.returncode == 0, r.stdout + r.stderr)
for s in sets:
    cmp = filecmp.dircmp(s, tmp / 'repo' / 'training' / 'scenario-samples' / s.name)
    diff = cmp.left_only + cmp.right_only + [f for f in cmp.common_files if not filecmp.cmp(s / f, tmp / 'repo' / 'training' / 'scenario-samples' / s.name / f, shallow=False)]
    check(f'{s.name}: committed files match the source (run installer/make-scenario-samples.py after editing it)', not diff, diff)

# 2. no real contacts
for s in sets:
    bad = []
    # the authored content (the form templates themselves carry the Church's public numbers)
    for f in [s / 'README.txt', s / 'ICS213RR samples.json'] + list((REPO / 'training' / 'scenario-samples-src').glob('*.json')):
        t = f.read_text(encoding='utf-8', errors='replace')
        bad += [p for p in re.findall(r'\b\d{3}-\d{3}-\d{4}\b|\b555-\d{4}\b', t) if not re.fullmatch(r'555-01\d\d', p)]
        bad += [e for e in re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', t) if not e.endswith('@churchemcomm.sim') and not e.endswith('winlink.org')]
    check(f'{s.name}: phones only 555-01xx, emails only @churchemcomm.sim', not bad, sorted(set(bad))[:8])
    # the public sets play the invented example community only: every sending unit is one of its units
    import orgpack
    ex = {u['name'] for u in orgpack.load(REPO / 'simulation' / 'example' / 'juniper-plains')['units']}
    for f in (REPO / 'training' / 'scenario-samples-src').glob('*.json'):
        d = json.loads(f.read_text(encoding='utf-8'))
        if d.get('code') == s.name:
            unknown = sorted({c['unit'] for c in d.get('church', [])} - ex)
            check(f'{s.name}: every sending unit belongs to the invented example community (Juniper Plains Area)', not unknown, unknown)

# the browser half needs Playwright; without it the file checks above still count
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nRESULT: {'ALL PASS' if all(res) else 'FAILURES'} ({sum(res)}/{len(res)}) SKIP browser checks: playwright is not installed")
    sys.exit(0 if all(res) else 1)

# scratch EOC
work = tmp / 'eoc'; (work / 'eoc').mkdir(parents=True)
for f in ('eoc_server.py', 'EOC_Message_Center.html', 'EOC_Wall_Display.html', 'EOC_Phone.html'):
    shutil.copy2(REPO / 'eoc' / f, work / 'eoc' / f)
shutil.copytree(REPO / 'templates', work / 'templates')
log = open(tmp / 'eoc.log', 'w')
proc = subprocess.Popen([sys.executable, '-u', 'eoc_server.py', str(PORT)], cwd=str(work / 'eoc'), stdout=log, stderr=subprocess.STDOUT,
                        env=dict(os.environ, PYTHONIOENCODING='utf-8', LOCALAPPDATA=str(tmp / 'appdata'), USERPROFILE=str(tmp / 'home'), EMCOMM_DOCUMENTS=str(tmp / 'documents')))
try:
    for _ in range(40):
        try:
            call('/api/status'); break
        except Exception:
            time.sleep(0.5)
    AG = next(((json.loads(f.read_text(encoding='utf-8')).get('agency') or {}).get('name') for f in (REPO / 'training' / 'scenario-samples-src').glob('*.json')), None) or 'City EOC'
    inc = call('/api/incident'); inc.update({'name': 'Training test', 'agencies': [{'name': AG, 'call': 'N0CITY'}]})
    call('/api/incident', inc, 'PUT')
    ddir = pathlib.Path(call('/api/watcher/status').get('drillDir') or '')
    check('scratch EOC with a Simulated Winlink inbox', ddir.is_dir(), ddir)

    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception:
            b = p.chromium.launch(channel='chrome')
        for s in sets:
            src = json.loads((REPO / 'training' / 'scenario-samples-src').joinpath(
                next(f.name for f in (REPO / 'training' / 'scenario-samples-src').glob('*.json')
                     if json.loads(f.read_text(encoding='utf-8'))['code'] == s.name)).read_text(encoding='utf-8'))
            church = sorted(src['church'], key=lambda x: x['time'])
            pages = sorted(s.glob(f'{s.name}_*.html'))
            check(f'{s.name}: one page per Church form', len(pages) == len(church), [x.name for x in pages])
            sent = []
            for pg_path, it in zip(sorted(pages, key=lambda x: x.name), church):
                pg = b.new_page(); errs = []
                pg.on('pageerror', lambda e: errs.append(str(e)))
                pg.on('dialog', lambda d: d.dismiss())
                pg.goto(pg_path.as_uri()); pg.wait_for_timeout(400)
                f = it['fields']
                key = next(k for k in ('mem_details', 'needs_details', 'proj_name', 'log_location') if k in f)
                vals = pg.evaluate("ks => ks.map(k => { var e = document.getElementById(k); return e ? e.value : null; })", [key, 'exercise'])
                ex = pg.evaluate("document.getElementById('exercise').checked")
                body = pg.evaluate("() => { cleanAllFields(); return winlinkBody(buildMsg()); }")
                ok = vals[0] == f[key] and ex and not errs and '[Church-' in body and 'EXERCISE' in body.upper()
                check(f'{pg_path.name}: opens filled, exercise ticked, builds its tagged message', ok, (vals[0] or '')[:60] + str(errs))
                item = {'form': it['form'], 'payload': dict(f, exercise='YES'), 'unit': it['unit']}
                nm, data = engine.winlink_mime(item, {'id': 'training', 'eoc': {'winlink': 'W9AAA@winlink.org'}})
                # carry the form's own message text, not the simulator's
                import email
                m = email.message_from_bytes(data); m.set_payload(None)
                m2 = email.message.EmailMessage()
                for h in ('Date', 'From', 'To', 'Subject', 'Message-ID', 'X-Source'):
                    if m[h]: m2[h] = ' '.join(str(m[h]).split())   # unfold long headers
                m2.set_content(body, charset='iso-8859-1', cte='quoted-printable')
                (ddir / nm).write_bytes(m2.as_bytes())
                sent.append((it, nm))
                pg.close()
            msgs = []
            for _ in range(40):
                time.sleep(1)
                msgs = call('/api/messages')
                if len(msgs) >= len(sent): break
            check(f'{s.name}: every Church form message ingested by the EOC ({len(sent)})', len(msgs) == len(sent), len(msgs))
            msgs = [dict(x, **json.loads(x['data_json'])) if x.get('data_json') else x for x in msgs]
            for it, nm in sent:
                f, t = it['fields'], it['form']
                unit = f.get('inc_ward') or f.get('chief_ward') or f.get('req_stake')
                m = next((x for x in msgs if x.get('type') == t and unit in json.dumps(x.get(t) or {}, ensure_ascii=False) and chr(10) not in x.get('subject', '')
                          and (t != 'dr' or (str((x.get(t) or {}).get('homes_dmg')) == f['mem_damaged']        # two reports of one unit:
                                            and str((x.get(t) or {}).get('mem_inj')) == f['mem_injuries']))), None)   # told apart by their counts
                sub = (m or {}).get(t) or {}
                good = m and str(sub.get('exercise', '')).upper() == 'YES'
                if t == 'dr':
                    good = good and str(sub.get('mem_inj')) == f['mem_injuries'] and str(sub.get('miss_safe', '')).upper().startswith(f['miss_safe'][0])
                check(f'  EOC read {t.upper()} {unit} {it["time"]} as an EXERCISE with its counts', good, {k: sub.get(k) for k in list(sub)[:6]} if m else 'not found')
            acts = call('/api/actions')
            check(f'{s.name}: the missionary report raised a missionary work item', any('issionar' in a.get('title', '') for a in acts), [a['title'] for a in acts][:6])

            # 4. ICS 213RR built like install.ps1
            data = json.loads((s / 'ICS213RR samples.json').read_text(encoding='utf-8'))
            if not (STD / 'ICS213RR_Initial.html').is_file():
                print('SKIP ICS 213RR forms: Winlink standard templates not on this machine')
                continue
            init = (STD / 'ICS213RR_Initial.html').read_text(encoding='utf-8', errors='replace')
            out = tmp / 'ics'; out.mkdir(exist_ok=True)
            for smp in data['samples']:
                i = init.rfind('</body>')
                (out / smp['html']).write_text(init[:i] + smp['script'] + init[i:], encoding='utf-8')
                pg = b.new_page(); errs = []
                pg.on('pageerror', lambda e: errs.append(str(e)))
                pg.on('dialog', lambda d: d.dismiss())
                pg.goto((out / smp['html']).as_uri()); pg.wait_for_timeout(600)
                got = pg.evaluate("ks => { var o = {}; ks.forEach(k => { var e = document.getElementsByName(k); if (!e.length) { o[k] = null; return; }"
                                  " if (e[0].type === 'radio') { o[k] = [...e].filter(x => x.checked).map(x => x.value)[0] || ''; } else o[k] = e[0].value; }); return o; }",
                                  list(smp['fields']))
                miss = {k: (v, got.get(k)) for k, v in smp['fields'].items() if k != 'FormTitle' and got.get(k) != v}
                title = pg.evaluate("(document.getElementById('SubjectText') || {}).innerHTML")
                check(f'{smp["html"]}: standard ICS213RR form opens with every value and priority {smp["fields"]["Priority"]}',
                      not miss and title == smp['fields']['FormTitle'], miss or title)
                pg.close()
                if smp['from'] == AG:
                    it2 = {'id': smp['html'], 'ics': {'form': 'ics213rr', 'agency': AG, 'call': 'N0CITY', 'contact': '', 'place': '',
                                                      'subject': f'ICS 213RR- {smp["fields"]["IncName"]}- Request #:{smp["fields"]["ReqNum"]}', 'fields': smp['fields']}}
                    nm, mdata = engine.ics_mime(it2, {'id': 'training', 'eoc': {'winlink': 'W9AAA@winlink.org'}})
                    (ddir / nm).write_bytes(mdata)
            for _ in range(30):
                time.sleep(1)
                acts = [a for a in call('/api/actions') if f'{AG} resource request' in a.get('title', '')]
                if len(acts) >= sum(1 for x in data['samples'] if x['from'] == AG): break
            want = [x['fields']['ReqNum'] for x in data['samples'] if x['from'] == AG]
            check(f'{s.name}: every city ICS 213RR filed as a work item for the city with its request number', all(any(w in a['title'] for a in acts) for w in want),
                  [a['title'] for a in acts])
        b.close()
finally:
    proc.terminate(); proc.wait(10); log.close()
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\nRESULT: {'ALL PASS' if all(res) else 'FAILURES'} ({sum(res)}/{len(res)})")
sys.exit(0 if all(res) else 1)
