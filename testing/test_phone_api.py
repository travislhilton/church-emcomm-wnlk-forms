#!/usr/bin/env python3
"""Phone / Send-to-EOC API test: two EOC servers on one machine (8080 'Alpha Stake EOC',
8081 'Bravo Satellite EOC'), each a scratch copy of the repo with its own database.
Checks: status identity, SITREP interval fields, /m and /receive, served Worker forms
(with the Church of Jesus Christ EMCOMM app module), discovery between the two servers, upload, duplicate
detection, relay to the other EOC, refusal of an unknown EOC, whole-file upload, errors,
work items (derived from reports, operator items, PATCH / DELETE, roll-up of items
waiting on the EOC above).

    python testing/test_phone_api.py            # scratch folders in a temp dir, servers stopped at the end
    python testing/test_phone_api.py --keep     # leave both servers running for browser tests

Needs ports 8080, 8081 (or --ports=A,B) and UDP 8089. The servers
watch the real EOC Drop Folder, so do not drop files there while this runs.
"""
import json, os, re, shutil, subprocess, sys, tempfile, time, urllib.error, urllib.request, pathlib
REPO = pathlib.Path(__file__).resolve().parent.parent
SP = pathlib.Path(next((a for a in sys.argv[1:] if not a.startswith('--')), '') or tempfile.mkdtemp(prefix='eoc_phone_test_'))
keep = '--keep' in sys.argv
PA, PB = (int(x) for x in next((x.split('=', 1)[1] for x in sys.argv[1:] if x.startswith('--ports=')), '8080,8081').split(','))
SP = SP if not str(SP).startswith('--') else pathlib.Path(tempfile.mkdtemp(prefix='eoc_phone_test_'))
def layout(name):
    d = SP / name
    if d.exists(): shutil.rmtree(d)
    (d / 'eoc').mkdir(parents=True)
    for f in ('eoc_server.py', 'EOC_Message_Center.html', 'EOC_Wall_Display.html', 'EOC_Phone.html'):
        shutil.copy2(REPO / 'eoc' / f, d / 'eoc' / f)
    shutil.copytree(REPO / 'templates', d / 'templates')
    shutil.copytree(REPO / 'forms' / 'icons', d / 'forms' / 'icons')
    return d / 'eoc'
def call(port, method, path, body=None, raw=False):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=data, method=method, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=15) as r:
        b = r.read()
        return (r.status, b) if raw else json.loads(b.decode('utf-8'))
res = []
def check(label, ok, detail=''):
    ok = bool(ok); res.append(ok); print(('PASS ' if ok else 'FAIL ') + label + (' -- ' + str(detail)[:160] if detail else ''))
procs = []
try:
    for name, port in (('srvA', PA), ('srvB', PB)):
        wd = layout(name)
        log = open(SP / f'{name}.log', 'w', encoding='utf-8')   # a file, not a pipe: a full pipe would freeze the server
        procs.append(subprocess.Popen([sys.executable, '-u', 'eoc_server.py', str(port)], cwd=str(wd), stdout=log, stderr=subprocess.STDOUT, env=dict(os.environ, PYTHONIOENCODING='utf-8', LOCALAPPDATA=str(SP / (name + '_appdata')), USERPROFILE=str(SP / (name + '_home')), EMCOMM_DOCUMENTS=str(SP / (name + '_documents')))))
    for port in (PA, PB):
        for _ in range(60):
            try: call(port, 'GET', '/api/status'); break
            except Exception: time.sleep(0.25)
    # identities
    for port, nm, lvl in ((PA, 'Alpha Stake EOC', 'stake'), (PB, 'Bravo Satellite EOC', 'satellite')):
        inc = call(port, 'GET', '/api/incident'); inc.update({'eocName': nm, 'eocLevel': lvl, 'eocLat': '40.33', 'eocLon': '-117.53', 'name': nm + ' drill', 'sitrepHrs': '4', 'sitrepBy': 'Stake President'})
        call(port, 'PUT', '/api/incident', inc)
    st = call(PA, 'GET', '/api/status')
    check('status carries EOC identity + formsVersion', st.get('eocName') == 'Alpha Stake EOC' and st.get('eocLat') == '40.33' and st.get('formsVersion'), st)
    inc = call(PA, 'GET', '/api/incident')
    check('SITREP interval stored on the event', inc.get('sitrepHrs') == '4' and inc.get('sitrepBy') == 'Stake President')
    dq = call(PA, 'GET', '/api/drop/status')
    check('test servers watch a scratch Drop Folder (EMCOMM_DOCUMENTS), never the real Documents one',
          str(SP).lower() in str(dq.get('watch_path', '')).lower(), dq.get('watch_path'))
    s, b = call(PA, 'GET', '/m', raw=True); check('/m serves the phone page', s == 200 and b'EOC on this Wi-Fi' in b)
    s, b = call(PA, 'GET', '/receive', raw=True); check('/receive serves the phone page', s == 200 and b'decodePayload' in b)
    man = call(PA, 'GET', '/app.webmanifest')
    check('the EOC home-screen app: a manifest that opens the phone page, named apart from the full app', man.get('start_url') == '/m' and man.get('name') == 'EMCOMM EOC' and man.get('display') == 'standalone')
    s, b = call(PA, 'GET', '/icons/icon-180.png', raw=True); check('the home-screen icon is served as a PNG image', s == 200 and b[:4] == b'\x89PNG')
    try: call(PA, 'GET', '/icons/../eoc_server.py', raw=True); check('/icons/ serves only the listed icons', False)
    except urllib.error.HTTPError as e: check('/icons/ serves only the listed icons', e.code == 404)
    s, b = call(PA, 'GET', '/m', raw=True); check('the phone page names the manifest and the home-screen icon', b'/app.webmanifest' in b and b'apple-touch-icon' in b and b'Add to Home Screen' in b)
    import urllib.parse as _up
    br = call(PA, 'GET', '/api/browse?kind=map&path=' + _up.quote(str(REPO / 'simulation' / 'example')))
    check('folder browser: lists this laptop\'s folders and marks the map data folder', br.get('drives') and any(f['name'] == 'juniper-plains' and f['mark'] for f in br.get('folders', [])) and br.get('label') == 'map data', br.get('folders'))
    br = call(PA, 'GET', '/api/browse?kind=any&path=' + _up.quote(str(REPO / 'no' / 'such' / 'folder')))
    check('folder browser: a path that does not exist opens its nearest real parent; any folder can be chosen', pathlib.Path(br.get('path', '')) == REPO and not br.get('mark'), br.get('path'))
    own = subprocess.run([sys.executable, '-c', "import eoc_server as e; a = e._own_addresses(); print('203.0.113.5' in a, '127.0.0.1' in a)"], cwd=str(SP / 'srvA' / 'eoc'), capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
    check('folder browser: refused to another device on the Wi-Fi, allowed at this laptop', own.stdout.split()[-2:] == ['False', 'True'], own.stdout[-200:] + own.stderr[-200:])
    for k, marker in (('dr', b'Disaster Report'), ('so', b'Supply Order'), ('wcl', b'Work Crew Log')):
        s, b = call(PA, 'GET', '/forms/' + k, raw=True); check(f'/forms/{k} serves the Worker form with the app module', s == 200 and marker in b and b'EMCOMM-APP:BEGIN' in b and b'EMCOMM.init' in b)
    try: call(PA, 'GET', '/forms/zz', raw=True); check('/forms/zz is 404', False)
    except urllib.error.HTTPError as e: check('/forms/zz is 404', e.code == 404)
    # discovery (broadcast every 5 s)
    peers = []
    for _ in range(30):
        peers = call(PA, 'GET', '/api/peers')
        if any(p.get('name') == 'Bravo Satellite EOC' for p in peers): break
        time.sleep(1)
    heard = len(peers) >= 2 and peers[0].get('self') and any(p.get('name') == 'Bravo Satellite EOC' for p in peers)
    peer_log = [ln.strip() for n in ('srvA', 'srvB') for ln in (SP / f'{n}.log').read_text(encoding='utf-8', errors='replace').splitlines() if '[PEERS]' in ln]
    check('discovery: Alpha hears Bravo', heard, '' if heard else (peer_log or peers))
    bravo_url = next((p['url'] for p in peers if p.get('name') == 'Bravo Satellite EOC'), '')
    # upload
    dr = {'inc_stake': 'Alpha Stake', 'inc_ward': 'Alpha 3rd Ward', 'inc_type': 'Flood', 'inc_date': '2026-10-30', 'inc_location': 'Shelter at Alpha HS',
          'mem_injuries': '2', 'miss_safe': 'YES', 'stn_lat_d': '40.4', 'stn_lon_d': '-117.5', 'sub_name': 'Field Worker', 'exercise': True}
    so = {'req_stake': 'Alpha Stake', 'order_date': '2026-10-30', 'del_city': 'Alpha', 'gs01': '3'}
    r1 = call(PA, 'POST', '/api/upload', {'reports': [{'id': 'r1', 'form': 'dr', 'data': dr}, {'id': 'r2', 'form': 'so', 'data': so}]})
    check('upload 2 reports to Alpha', r1.get('ok') and r1.get('new') == 2 and r1['eoc']['name'] == 'Alpha Stake EOC', r1)
    r2 = call(PA, 'POST', '/api/upload', {'reports': [{'id': 'r1', 'form': 'dr', 'data': dict(reversed(list(dr.items())))}]})
    check('same report again (keys in another order) = duplicate', r2.get('dup') == 1 and r2.get('new') == 0, r2)
    msgs = call(PA, 'GET', '/api/messages')
    m = next((json.loads(x['data_json']) for x in msgs if x['type'] == 'dr'), {})
    check('DR filed with mapped fields and source=upload', m.get('source') == 'upload' and m.get('dr', {}).get('stake') == 'Alpha Stake' and m.get('fields', {}).get('inc_type') == 'Flood', m.get('dr'))
    check('THIS IS AN EXERCISE: the Worker checkbox becomes dr.exercise=YES; the SO without it is blank', m.get('dr', {}).get('exercise') == 'YES'
          and next((json.loads(x['data_json']) for x in msgs if x['type'] == 'so'), {}).get('so', {}).get('exercise') == '', m.get('dr', {}).get('exercise'))
    # map data: nothing until the Setup tab names the dataset folder; then /map/ serves only that folder
    st = call(PA, 'GET', '/api/status')
    check('status.map is false and /api/map/status says why before a folder is set', st.get('map') is False and call(PA, 'GET', '/api/map/status').get('ok') is False)
    try: call(PA, 'GET', '/map/organization_boundaries.geojson', raw=True); check('/map/ is 404 with no folder', False)
    except urllib.error.HTTPError as e: check('/map/ is 404 with no folder', e.code == 404)
    inc = call(PA, 'GET', '/api/incident'); inc['mapPath'] = str(REPO / 'testing' / 'fixtures' / 'map-synthetic'); call(PA, 'PUT', '/api/incident', inc)
    mi = call(PA, 'GET', '/api/map/status')
    check('map folder set on the identity: status counts the fixture (6 units, 2 stakes, 3 meetinghouses), status.map true', mi.get('ok') and mi.get('units') == 6 and mi.get('stakes') == 2 and mi.get('buildings') == 3 and call(PA, 'GET', '/api/status').get('map') is True, mi)
    s, b = call(PA, 'GET', '/map/organization_boundaries.geojson', raw=True)
    check('/map/organization_boundaries.geojson served as GeoJSON', s == 200 and b'Riverbottom Ward' in b)
    for bad in ('/map/../../eoc/eoc_server.py', '/map/..%2F..%2Feoc%2Feoc_server.py', '/map/nothing.geojson', '/map/organization_boundaries.exe'):
        try: call(PA, 'GET', bad, raw=True); check(f'{bad} refused', False)
        except urllib.error.HTTPError as e: check(f'{bad} refused', e.code == 404)
    s, b = call(PA, 'GET', '/', raw=True); check('Message Center carries the map module and the Map tab', b'EMCOMM-MAP:BEGIN' in b and b'EMCOMM_MAP.create' in b and b'id="tab-map"' in b)
    s, b = call(PA, 'GET', '/wall', raw=True); check('wall carries the map module and the map tile', b'EMCOMM-MAP:BEGIN' in b and b'id="wallmap"' in b)
    # relay to Bravo through Alpha
    wcl = {'log_date': '2026-10-30', 'log_location': 'Bravo park', 'chief_name': 'Crew Chief B', 'crew_name1': 'One'}
    r3 = call(PA, 'POST', '/api/upload', {'reports': [{'id': 'r3', 'form': 'wcl', 'data': wcl}], 'to': bravo_url})
    check('relay via Alpha files the report at Bravo', r3.get('new') == 1 and r3['eoc']['name'] == 'Bravo Satellite EOC' and r3.get('relayedBy') == 'Alpha Stake EOC', r3)
    check('Bravo has 1 message, Alpha still 2', len(call(PB, 'GET', '/api/messages')) == 1 and len(call(PA, 'GET', '/api/messages')) == 2)
    r4 = call(PA, 'POST', '/api/upload', {'reports': [{'id': 'x', 'form': 'dr', 'data': dr}], 'to': 'http://10.9.9.9:PA'})
    check('relay to an unknown EOC is refused', r4.get('ok') is False and 'not on this network' in r4.get('error', ''), r4)
    # whole-file upload (Worker .txt with BOM, as dragged onto the EOC page)
    txt = '\ufeff' + json.dumps({'inc_stake': 'Alpha Stake', 'inc_type': 'Wind', 'inc_date': '2026-10-30', 'sub_name': 'File drop'}, indent=2)
    r5 = call(PA, 'POST', '/api/upload', {'filename': 'Church_Disaster_Report_Worker.txt', 'text': txt})
    check('whole-file upload (BOM) filed', r5.get('new') == 1 and r5['results'][0]['form'] == 'DR', r5)
    r6 = call(PA, 'POST', '/api/upload', {'filename': 'nonsense.txt', 'text': '{"hello": 1}'})
    check('unknown file reports an error, not a crash', r6.get('errors') == 1 and r6.get('ok') is False, r6)
    # work items: extracted from the reports on file (DR with 2 injured, one SO), then operators' own
    acts = call(PA, 'GET', '/api/actions')
    cats = sorted(a['cat'] for a in acts)
    check('work items derived from the filed reports (life, supply)', cats == ['life', 'supply'] and all(a['status'] == 'open' and a['auto'] and a['src']['id'] for a in acts), cats)
    check('the exercise report\'s work item is titled EXERCISE: …, the real one is not', next(a['title'] for a in acts if a['cat'] == 'life').startswith('EXERCISE: ')
          and not next(a['title'] for a in acts if a['cat'] == 'supply').startswith('EXERCISE'), [a['title'] for a in acts])
    dr2 = {'inc_stake': 'Alpha Stake', 'inc_ward': 'Alpha 5th Ward', 'inc_type': 'Flood', 'inc_date': '2026-10-30', 'miss_safe': 'NO', 'miss_details': 'Sisters not reached',
           'need_hq': 'YES', 'need_local': 'YES', 'needs_details': 'Shelter for 3 families', 'mem_destroyed': '2', 'sub_name': 'Field Worker'}
    call(PA, 'POST', '/api/upload', {'reports': [{'id': 'r7', 'form': 'dr', 'data': dr2}]})
    acts = call(PA, 'GET', '/api/actions')
    cats = sorted(a['cat'] for a in acts)
    miss = next((a for a in acts if a['cat'] == 'missionaries'), {})
    check('second DR adds missionaries / HQ / facilities / shelter items', cats == ['facilities', 'facilities', 'life', 'missionaries', 'supply', 'upward'] and miss.get('prio') == 1 and miss.get('detail') == 'Sisters not reached' and miss.get('unit') == 'Alpha 5th Ward', cats)
    call(PA, 'POST', '/api/upload', {'reports': [{'id': 'r7', 'form': 'dr', 'data': dr2}]})
    check('a duplicate report adds no items', len(call(PA, 'GET', '/api/actions')) == 6)
    c1 = call(PA, 'POST', '/api/actions', {'title': 'Confirm the shelter at the stake center', 'cat': 'facilities', 'prio': 1, 'owner': 'Pat', 'key': 'manual:shelter', 'who': 'Op One'})
    check('operator adds a work item', c1.get('ok') and c1['item']['owner'] == 'Pat' and c1['item']['status'] == 'open' and c1['item']['log'][0]['text'] == 'Added' and c1['item']['log'][0]['who'] == 'Op One', c1)
    c2 = call(PA, 'POST', '/api/actions', {'title': 'Confirm the shelter again', 'key': 'manual:shelter'})
    check('same key again = the existing item', c2.get('duplicate') and c2['item']['id'] == c1['item']['id'])
    try: call(PA, 'POST', '/api/actions', {'title': '  '}); check('an item without a title is refused', False)
    except urllib.error.HTTPError as e: check('an item without a title is refused', e.code == 400)
    aid = c1['item']['id']
    p1 = call(PA, 'PATCH', f'/api/actions/{aid}', {'status': 'up', 'next': 'Ask the welfare line for cots', 'log': 'Called the WSRM', 'who': 'Op One'})
    it = p1.get('item', {})
    check('PATCH sets status, next action and appends two log lines', it.get('status') == 'up' and it.get('next') == 'Ask the welfare line for cots' and [l['text'] for l in it['log']] == ['Added', 'Status: waiting on the line above', 'Called the WSRM'] and it.get('updatedTs'), it.get('log'))
    p2 = call(PA, 'PATCH', f'/api/actions/{aid}', {'owner': 'Pat Two', 'who': 'Phone'})          # the phone page sends only owner / status
    it2 = p2.get('item', {})
    check('a partial PATCH (owner only, as the phone page sends) keeps the title, priority, category and next action', it2.get('title') == 'Confirm the shelter at the stake center' and it2.get('prio') == 1 and it2.get('cat') == 'facilities' and it2.get('next') == 'Ask the welfare line for cots' and it2.get('owner') == 'Pat Two' and it2['log'][-1]['text'] == 'Owner: Pat Two', {k: it2.get(k) for k in ('title', 'prio', 'cat', 'next', 'owner')})
    st = call(PA, 'GET', '/api/status')
    check('status carries the open work item count', st.get('openActions') == 7, st.get('openActions'))
    ev = next((e for e in call(PA, 'GET', '/api/events') if e['active']), {})
    check('event counts include open work items', ev.get('counts', {}).get('actions') == 7, ev.get('counts'))
    # roll-up from a child EOC with an item waiting on this EOC
    m1 = call(PA, 'POST', '/api/merge', {'kind': 'church_eoc_rollup', 'v': 1, 'from': {'name': 'Bravo Satellite EOC', 'level': 'satellite'}, 'msgs': [], 'roster': [], 'notes': [],
                                           'actions': [{'id': 'bravo-a1', 'title': 'Need a generator for the shelter', 'cat': 'supply', 'prio': 1, 'status': 'up', 'unit': 'Bravo 1st Ward'}]})
    got = next((a for a in call(PA, 'GET', '/api/actions') if a['id'] == 'bravo-a1'), {})
    check('roll-up lands the child item open, from Bravo, logged', m1.get('actions_new') == 1 and got.get('status') == 'open' and got.get('from') == 'Bravo Satellite EOC' and got.get('prio') == 1 and 'waiting on this EOC' in got['log'][-1]['text'], got)
    m2 = call(PA, 'POST', '/api/merge', {'kind': 'church_eoc_rollup', 'from': {'name': 'Bravo Satellite EOC'}, 'msgs': [], 'actions': [{'id': 'bravo-a1', 'title': 'Need a generator for the shelter'}]})
    check('the same item in a second roll-up is skipped', m2.get('actions_new') == 0)

    # a reply from the line above closes an item this EOC set UP (the child's side of the reply path)
    c2 = call(PA, 'POST', '/api/actions', {'title': 'Supply Order: cots for the care centre', 'cat': 'supply', 'prio': 1, 'status': 'up', 'owner': 'ERD'})
    aid2 = c2['item']['id']
    call(PA, 'PATCH', f'/api/actions/{aid2}', {'status': 'up', 'who': 'Pat'})
    rp = call(PA, 'POST', '/api/merge', {'kind': 'church_eoc_reply', 'from': {'name': 'Alpha Stake EOC', 'level': 'stake'},
                                           'replies': [{'id': aid2, 'title': 'Supply Order: cots for the care centre', 'status': 'done', 'decision': 'Approved; truck ETA 14:00'}, {'id': 'no-such-item', 'title': 'Nothing here', 'status': 'done'}],
                                           'notes': [{'id': 'rp-n1', 'ts': 1, 'text': 'Truck leaves Bramble Junction 11:10'}]})
    got2 = next((a for a in call(PA, 'GET', '/api/actions') if a['id'] == aid2), {})
    check('reply bundle: the UP item is DONE with the decision and a log line from the sender; the unknown item is reported missing; the note is logged',
          rp.get('kind') == 'church_eoc_reply' and rp.get('replies_applied') == 1 and rp.get('missing') == ['Nothing here'] and got2.get('status') == 'done' and got2.get('decision') == 'Approved; truck ETA 14:00'
          and got2.get('replied', {}).get('from') == 'Alpha Stake EOC' and any(l['text'].startswith('Reply from Alpha Stake EOC') for l in got2['log']) and any('Truck leaves Bramble Junction' in n['text'] for n in call(PA, 'GET', '/api/notes')), (rp, got2.get('status')))
    got1 = next((a for a in call(PA, 'GET', '/api/actions') if a['id'] == 'bravo-a1'), {})
    pr = call(PA, 'PATCH', '/api/actions/bravo-a1', {'replied': 1700000000000, 'decision': 'Generator from the stake center', 'who': 'Pat'})
    check('a roll-up item is flagged fromEoc (the Message Center offers Reply to <EOC>); PATCH keeps the replied mark', got1.get('fromEoc') is True and pr['item'].get('replied') == 1700000000000 and pr['item'].get('decision') == 'Generator from the stake center', (got1.get('fromEoc'), pr['item'].get('replied')))
    rb = call(PA, 'POST', '/api/merge', {'kind': 'church_eoc_reply', 'from': {'name': 'Alpha Stake EOC'}, 'replies': [{'id': 'x', 'key': '', 'title': 'Supply Order: cots for the care centre', 'status': 'progress', 'decision': 'Partial: cots only'}]})
    got3 = next((a for a in call(PA, 'GET', '/api/actions') if a['id'] == aid2), {})
    check('a reply without a matching id falls back to the title of a waiting item only (the DONE item is not reopened)', rb.get('replies_applied') == 0 and got3.get('status') == 'done', (rb, got3.get('status')))
    call(PA, 'DELETE', f'/api/actions/{aid}')
    check('DELETE removes the item', not any(a['id'] == aid for a in call(PA, 'GET', '/api/actions')))
    try: call(PA, 'PATCH', '/api/actions/no-such', {'status': 'done'}); check('PATCH of an unknown item is 404', False)
    except urllib.error.HTTPError as e: check('PATCH of an unknown item is 404', e.code == 404)
    bk = call(PA, 'GET', '/api/backup')
    check('backup written with the work items on file', bk.get('ok'), bk)

    # ── roll-ups from outside are data, not code (audit 2026-11-02): hostile ids and statuses are replaced, ──
    #    malformed records are skipped, and /api/merge always answers
    SAFE = re.compile(r'^[A-Za-z0-9_.:-]{1,64}$')
    hx = call(PA, 'POST', '/api/merge', {'kind': 'church_eoc_rollup', 'from': {'name': 'Hostile EOC'},
              'msgs': [{'id': "x');alert(1)//", 'type': 'dr', 'status': '<img src=x onerror=alert(1)>', 'dr': {'stake': 'Hostile Stake', 'ward': 'H 1st Ward', 'type': 'XSS test'}}],
              'roster': [{'id': "r'\"><svg onload=alert(1)>", 'name': 'Hostile Ward'}],
              'notes': [{'id': "n');alert(1)//", 'ts': 'soon', 'text': 'Hostile note'}],
              'actions': [{'id': "a');alert(1)//", 'title': 'Hostile item', 'ts': {'x': 1}, 'src': {'id': "m');alert(1)//", 'type': 'dr'}, 'log': ['junk', {'ts': 'x', 'text': 5}]}]})
    hm_ = next((x for x in call(PA, 'GET', '/api/messages') if 'XSS test' in x['data_json']), {})
    hr = next((r for r in call(PA, 'GET', '/api/roster') if r.get('name') == 'Hostile Ward'), {})
    hn = next((n for n in call(PA, 'GET', '/api/notes') if 'Hostile note' in n['text']), {})
    ha = next((a for a in call(PA, 'GET', '/api/actions') if a.get('title') == 'Hostile item'), {})
    check('hostile roll-up: message, roster, note and work item ids replaced by plain ids; status forced to new; src with a bad id dropped; timestamps numbers',
          hx.get('new') == 1 and SAFE.match(hm_.get('id', '')) and hm_.get('status') == 'new' and json.loads(hm_['data_json']).get('status') == 'new'
          and SAFE.match(hr.get('id', '')) and SAFE.match(hn.get('id', '')) and isinstance(hn.get('ts'), int)
          and SAFE.match(ha.get('id', '')) and 'src' not in ha and isinstance(ha.get('ts'), int) and all(isinstance(l.get('text'), str) for l in ha.get('log', [])),
          (hm_.get('id'), hm_.get('status'), hr.get('id'), hn.get('id'), ha.get('id'), ha.get('src')))
    mal = call(PA, 'POST', '/api/merge', {'kind': 'church_eoc_rollup', 'from': 'not an object', 'incident': 'nor this', 'exportedAt': 'yesterday',
               'msgs': [5, 'text', None, {'type': 'dr', 'dr': 'a string'}, {'type': 'wcl', 'wcl': [1, 2]}, {'type': 'zz', 'zz': {}},
                        {'type': 'SO', 'so': {'stake': 'Malformed Stake', 'items': 'cots'}, 'ts': 'not a number', 'id': {'a': 1}, 'dupKey': ['x']}],
               'roster': 'not a list', 'notes': [{'text': 123}, {'text': ['a']}, 'x'], 'actions': [{'title': 'Malformed item', 'ts': [], 'prio': 'high'}, {'title': ['x']}]})
    so_m = next((x for x in call(PA, 'GET', '/api/messages') if 'Malformed Stake' in x['data_json']), {})
    check('malformed roll-up: answered, the one good Supply Order filed, the 6 bad records skipped, numbers coerced',
          mal.get('ok') and mal.get('new') == 1 and mal.get('skipped') == 6 and so_m.get('type') == 'so' and isinstance(so_m.get('received_ms'), int) and SAFE.match(so_m.get('id', '')), mal)
    try:
        st_, b_ = call(PA, 'POST', '/api/merge', {'kind': 'church_eoc_reply', 'from': [1], 'replies': [5, {'id': [1], 'title': {'x': 1}, 'status': ['done']}], 'notes': [{'text': 'r', 'ts': 'x', 'id': '<b>'}]}, raw=True)
        check('malformed reply bundle: answered (200)', st_ == 200 and json.loads(b_).get('kind') == 'church_eoc_reply', b_[:120])
    except urllib.error.HTTPError as e:
        check('malformed reply bundle: answered (400 with a reason)', e.code == 400 and b'error' in e.read())
    s, b = call(PA, 'GET', '/', raw=True)
    check('Message Center: esc() escapes the apostrophe and onclick ids go through jsq()', b".replace(/'/g,'&#39;')" in b and b'function jsq(' in b and b"removeMsg(\\''+jsq(m.id)+'\\')" in b and b"removeMsg(\\''+m.id" not in b)

    # ── another site's page may not change data here (no CORS wildcard; Origin checked on POST/PUT/PATCH/DELETE) ──
    def call_h(port, method, path, body=None, headers=None, host='127.0.0.1'):
        req = urllib.request.Request(f'http://{host}:{port}{path}', data=json.dumps(body).encode() if body is not None else None, method=method,
                                     headers=dict({'Content-Type': 'application/json'}, **(headers or {})))
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()
    s1, h1, _ = call_h(PA, 'GET', '/api/status')
    s2, h2, _ = call_h(PA, 'OPTIONS', '/api/notes', headers={'Origin': 'http://evil.example', 'Access-Control-Request-Method': 'POST'})
    check('no Access-Control-Allow-Origin on the API or on a preflight', s1 == 200 and not any(k.lower() == 'access-control-allow-origin' for k in h1) and not any(k.lower() == 'access-control-allow-origin' for k in h2), (h1, h2))
    s3, _, b3 = call_h(PA, 'POST', '/api/notes', {'id': 'cors-evil', 'text': 'from another site'}, {'Origin': 'http://evil.example'})
    s4, _, _ = call_h(PA, 'POST', '/api/notes', {'id': 'cors-null', 'text': 'from a file page'}, {'Origin': 'null'})
    s5, _, _ = call_h(PA, 'DELETE', '/api/actions/bravo-a1', headers={'Origin': f'http://127.0.0.1:{PB}'})
    s6, _, _ = call_h(PA, 'POST', '/api/notes', {'id': 'cors-same', 'text': 'from the Message Center'}, {'Origin': f'http://127.0.0.1:{PA}'})
    s7, _, _ = call_h(PA, 'POST', '/api/notes', {'id': 'cors-none', 'text': 'from a script'})
    ids_ = [n['id'] for n in call(PA, 'GET', '/api/notes')]
    check('cross-origin POST / DELETE refused (403), nothing written; same-origin page and scripts without Origin accepted',
          (s3, s4, s5, s6, s7) == (403, 403, 403, 200, 200) and 'cors-evil' not in ids_ and 'cors-null' not in ids_ and 'cors-same' in ids_ and 'cors-none' in ids_
          and any(a['id'] == 'bravo-a1' for a in call(PA, 'GET', '/api/actions')), (s3, s4, s5, s6, s7))
    lan_host = (call(PA, 'GET', '/api/status').get('lanUrl') or '').split('//')[-1].rsplit(':', 1)[0]
    if lan_host and not lan_host.startswith('127.'):
        s8, _, _ = call_h(PA, 'PUT', '/api/drop/config', {'enabled': True}, host=lan_host)
        s9, _, _ = call_h(PA, 'PUT', '/api/drop/config', {'enabled': True}, {'Origin': f'http://{lan_host}:{PA}'}, host=lan_host)
        check('watched folders: a script elsewhere on the network is refused (403); the Message Center page on the network is not', s8 == 403 and s9 == 200, (lan_host, s8, s9))

    # ── EOC address without internet: the host's own private address, not 127.0.0.1 ──
    sys.path.insert(0, str(SP / 'srvA' / 'eoc'))
    import importlib, socket as _sock
    _argv = sys.argv; sys.argv = [sys.argv[0]]
    try:
        _es = importlib.import_module('eoc_server')
    finally:
        sys.argv = _argv
    class _NoRoute:
        def __init__(self, *a, **k): pass
        def connect(self, *a): raise OSError('network unreachable')
        def close(self): pass
    _real_sock, _real_gai = _es.socket.socket, _es.socket.getaddrinfo
    try:
        _es.socket.socket = _NoRoute
        _es.socket.getaddrinfo = lambda *a, **k: [(2, 1, 0, '', (ip, 0)) for ip in ('127.0.0.1', '169.254.3.3', '8.8.4.4', '192.168.5.7')]
        ip1 = _es.get_local_ip()
        _es.socket.getaddrinfo = lambda *a, **k: [(2, 1, 0, '', ('127.0.0.1', 0))]
        ip2 = _es.get_local_ip()
    finally:
        _es.socket.socket, _es.socket.getaddrinfo = _real_sock, _real_gai
    check('no default route: the EOC address falls back to the host\'s private IPv4 (192.168.5.7), 127.0.0.1 only when there is nothing else', ip1 == '192.168.5.7' and ip2 == '127.0.0.1', (ip1, ip2))

    # ── Drop Folder: two reports saved one after the other under the same name are both filed ──
    dropdir = SP / 'drop_same_name'; dropdir.mkdir(exist_ok=True)
    call(PA, 'PUT', '/api/drop/config', {'watch_path': str(dropdir), 'enabled': True})
    def drop_wait(marker, secs=30):
        for _ in range(secs):
            time.sleep(1)
            if any(marker in x['data_json'] for x in call(PA, 'GET', '/api/messages')): return True
        return False
    fname = 'Church_Disaster_Report_Worker.txt'
    (dropdir / fname).write_text(json.dumps({'inc_stake': 'Alpha Stake', 'inc_type': 'Drop same name one', 'inc_date': '2026-11-02', 'sub_name': 'Drop test'}), encoding='utf-8')
    d1 = drop_wait('Drop same name one')
    for _ in range(15):
        if not (dropdir / fname).exists(): break
        time.sleep(0.5)
    (dropdir / fname).write_text(json.dumps({'inc_stake': 'Alpha Stake', 'inc_type': 'Drop same name two', 'inc_date': '2026-11-02', 'sub_name': 'Drop test'}), encoding='utf-8')
    d2 = drop_wait('Drop same name two')
    ing = sorted(p.name for p in (dropdir / 'Ingested').glob('*.txt')) if (dropdir / 'Ingested').is_dir() else []
    check('Drop Folder: a second report saved under the same file name is filed too; both files kept in Ingested', d1 and d2 and len(ing) == 2 and not (dropdir / fname).exists(), (d1, d2, ing))

    # ── Winlink Express's own store (Travis, 2026-10-31: "Winlink not found at default path"): every message of a
    #    callsign, received and sent, is <id>.mime in <install>\<CALLSIGN>\Messages; the watcher reads them in place,
    #    only the chosen callsign, only received, only since the event began; the choice is saved for the next start ──
    fake = SP / 'winlink_install'
    for c in ('W9AAA', 'W9BBB'):
        (fake / c / 'Messages').mkdir(parents=True, exist_ok=True); (fake / c / 'Data').mkdir(exist_ok=True)
    def wl_mime(folder, mid, sender, church=True, age_s=0):
        body = ('Disaster report\r\n[Church-DR|stake=Alpha Stake|ward=Alpha 1st Ward|type=Winlink store test ' + mid + '|date=2026-10-31]\r\nCSV,DR\r\n') if church else 'Hello, no form here.\r\n'
        txt = (f'Date: Sat, 31 Oct 2026 18:00:00 +0000\r\nFrom: {sender}@winlink.org\r\nTo: EOC@winlink.org\r\nSubject: test {mid}\r\n'
               f'Message-ID: {mid}\r\nX-Source: {sender}\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset="iso-8859-1"\r\n\r\n{body}')
        f = fake / folder / 'Messages' / f'{mid}.mime'; f.write_bytes(txt.encode('latin-1'))
        if age_s: os.utime(f, (time.time() - age_s, time.time() - age_s))
        return f
    files = [wl_mime('W9AAA', 'WLRECV000001', 'W9ZZZ'),                  # received by W9AAA: filed
             wl_mime('W9AAA', 'WLSENT000001', 'W9AAA'),                  # W9AAA's own sent copy: skipped
             wl_mime('W9AAA', 'WLOLD0000001', 'W9ZZZ', age_s=3 * 86400), # in Winlink before the event: skipped
             wl_mime('W9AAA', 'WLPLAIN00001', 'W9ZZZ', church=False),     # not a Church form: left alone
             wl_mime('W9BBB', 'WLBBB0000001', 'W9ZZZ')]                  # another callsign, not chosen: skipped
    n0 = len(call(PA, 'GET', '/api/messages'))
    wv = call(PA, 'PUT', '/api/watcher/config', {'watch_path': str(fake), 'callsigns': 'w9aaa', 'enabled': True})
    check('watcher on a Winlink install folder: mode winlink, the chosen callsign, both callsigns found, one folder scanned',
          wv.get('mode') == 'winlink' and wv.get('callsigns') == ['W9AAA'] and wv.get('available') == ['W9AAA', 'W9BBB']
          and [s['callsign'] for s in wv.get('sources', [])] == ['W9AAA'] and not wv.get('missing'), wv)
    msgs = []
    for _ in range(30):
        time.sleep(1)
        msgs = [m for m in call(PA, 'GET', '/api/messages') if 'Winlink store test' in json.dumps(m)]
        if msgs: break
    time.sleep(11)   # one more watcher cycle: nothing else may arrive
    msgs = [m for m in call(PA, 'GET', '/api/messages') if 'Winlink store test' in json.dumps(m)]
    check('Winlink store: only the received Church message of the chosen callsign since the event began is filed',
          len(msgs) == 1 and 'WLRECV000001' in json.dumps(msgs[0]), [re.findall(r'test (WL\w+)', json.dumps(m)) for m in msgs])
    check('Winlink store: no file is moved or changed (Winlink keeps its messages)', all(f.exists() for f in files) and not (fake / 'EOC Ingested').exists())
    sett = SP / 'srvA_appdata' / 'Church of Jesus Christ EMCOMM' / 'eoc-settings.json'
    sv = json.loads(sett.read_text(encoding='utf-8')) if sett.exists() else {}
    check('the callsign and folder are saved in eoc-settings.json for the next start', sv.get('winlinkCallsigns') == ['W9AAA'] and sv.get('winlinkFolder') == str(fake), sv)
    # a drill's simulated Winlink traffic goes to the EOC's own Simulated Winlink inbox (read beside Winlink's folders, never inside them)
    wv = call(PA, 'GET', '/api/watcher/status')
    ddir = pathlib.Path(wv.get('drillDir') or '')
    sim_ok = False
    if wv.get('drillDir') and ddir.is_dir():
        (ddir / 'WLSIM0000001.mime').write_bytes(files[0].read_bytes().replace(b'WLRECV000001', b'WLSIM0000001'))   # a copy of the received message, new id
        for _ in range(25):
            time.sleep(1)
            if any('WLSIM0000001' in json.dumps(m) for m in call(PA, 'GET', '/api/messages')): sim_ok = True; break
    check('Simulated Winlink inbox: shown in the status beside the Winlink store, its messages filed and moved to EOC Ingested beside it',
          sim_ok and not (ddir / 'WLSIM0000001.mime').exists() and (ddir.parent / 'EOC Ingested' / 'WLSIM0000001.mime').exists(), wv.get('drillDir'))
    # the drill's callsign has no folder on this computer (the invented example's SIM-xxx on a laptop with Winlink): the
    # simulated inbox is still read (2026-11-02 walk: the Contingency-period reports of the session were never filed)
    wv = call(PA, 'PUT', '/api/watcher/config', {'watch_path': str(fake), 'callsigns': 'SIM-NONE', 'enabled': True})
    sim2 = False
    if wv.get('drillDir') and ddir.is_dir():
        (ddir / 'WLSIM0000002.mime').write_bytes(files[0].read_bytes().replace(b'WLRECV000001', b'WLSIM0000002'))
        for _ in range(25):
            time.sleep(1)
            if any('WLSIM0000002' in json.dumps(m) for m in call(PA, 'GET', '/api/messages')): sim2 = True; break
    check('Simulated Winlink inbox: read even when the drill\'s callsign has no folder here (missing callsign shown, no store scanned)',
          sim2 and wv.get('missing') == ['SIM-NONE'] and not wv.get('sources') and wv.get('drillDir'), {k: wv.get(k) for k in ('missing', 'sources', 'drillDir')})
    call(PA, 'PUT', '/api/watcher/config', {'watch_path': str(fake), 'callsigns': 'w9aaa', 'enabled': True})
    # a partner agency's ICS 213RR (a city EOC that does not run this system) arrives by Winlink: a work item named for the agency
    sys.path.insert(0, str(REPO / 'simulation'))
    import engine as _eng
    inc_a = call(PA, 'GET', '/api/incident'); inc_a['agencies'] = [{'name': 'Test City EOC', 'call': 'N0CITY', 'place': 'Test fire station'}]
    call(PA, 'PUT', '/api/incident', inc_a)
    it = {'id': 'ics-test', 'ics': {'form': 'ics213rr', 'agency': 'Test City EOC', 'call': 'N0CITY', 'contact': 'the chief', 'place': '',
                                    'subject': 'Sandbag crew: test', 'fields': {'qty': '20', 'kind': 'Volunteers', 'item': 'Fill sandbags', 'priority': 'Urgent'}}}
    nm, data = _eng.ics_mime(it, {'id': 'test', 'eoc': {'winlink': 'W9AAA@winlink.org'}})
    (ddir / nm).write_bytes(data)
    got = None
    for _ in range(25):
        time.sleep(1)
        got = next((a for a in call(PA, 'GET', '/api/actions') if 'ICS 213RR' in a.get('title', '')), None)
        if got: break
    check('partner agency ICS 213RR by Winlink: a HIGH work item named for the agency (from its call sign), the request in the detail, answer by ICS 213; a note in the log',
          got and got['title'].startswith('Test City EOC resource request (ICS 213RR): Sandbag crew: test') and got.get('prio') == 1 and 'N0CITY' in got.get('from', '')
          and 'Fill sandbags' in got.get('detail', '') and 'ICS 213' in got.get('next', '')
          and any('ICS 213RR Resource Request received by Winlink from Test City EOC' in n.get('text', '') for n in call(PA, 'GET', '/api/notes')), got)
    # the same from Winlink's own ICS213RR form: its variable names (Qty1, Item1, Priority, ReqNum) and its subject
    # "ICS 213RR- <incident>- Request #:<number>" (the scenario training sets send these)
    it2 = {'id': 'ics-test-2', 'ics': {'form': 'ics213rr', 'agency': 'Test City EOC', 'call': 'N0CITY', 'contact': '', 'place': '',
                                       'subject': 'ICS 213RR- Copper Creek Dam failure (DRILL)- Request #:LCE-002',
                                       'fields': {'IncName': 'Copper Creek Dam failure (DRILL)', 'ReqNum': 'LCE-002', 'Priority': 'URGENT', 'Qty1': '30',
                                                  'Kind1': 'Crew', 'Type1': 'Shovel', 'Item1': 'Shovel crews of 3 to 5 to dig out doors, walks, driveways'}}}
    nm2, data2 = _eng.ics_mime(it2, {'id': 'test', 'eoc': {'winlink': 'W9AAA@winlink.org'}})
    (ddir / nm2).write_bytes(data2)
    got2 = None
    for _ in range(25):
        time.sleep(1)
        got2 = next((a for a in call(PA, 'GET', '/api/actions') if 'LCE-002' in a.get('title', '')), None)
        if got2: break
    check('Winlink standard ICS213RR (Qty1/Item1/Priority, generic subject): titled by its first item, quantity and request number; URGENT is HIGH',
          got2 and got2['title'] == 'Test City EOC resource request (ICS 213RR): Shovel crews of 3 to 5 to dig out doors, walks, driveways [#LCE-002] (30)'
          and got2.get('prio') == 1, got2 and got2.get('title'))
    wv = call(PA, 'PUT', '/api/watcher/config', {'callsigns': 'W9XXX'})
    check('a callsign that is not on this computer is reported as missing', wv.get('missing') == ['W9XXX'] and wv.get('sources') == [], wv.get('missing'))
    # ── drill configuration (simulation/drillconfig.py) applied by the EOC server: POST /api/config/apply ──
    sys.path.insert(0, str(REPO / 'simulation'))
    import drillconfig, privacy as _pv
    fixpack = _pv.pseudonymize(json.loads((REPO / 'testing' / 'fixtures' / 'orgpack-synthetic.json').read_text(encoding='utf-8')), 'salt-T')
    dcfg = drillconfig.build(fixpack, {'kind': 'church_emcomm_drill_spec', 'v': 1, 'name': 'API test drill', 'scenario': 'copper-creek-dam',
                                       'event': {'name': 'DRILL API test', 'type': 'Earthquake', 'sitrepHrs': '4'},
                                       'eocs': [{'id': 'alpha', 'level': 'stake', 'stake': 'Alpha Stake', 'manned': 'always', 'winlink': ['N0CALL-3']},
                                                {'id': 'area', 'level': 'area', 'councils': ['Alpha Coordinating Council'], 'building': 'B2', 'manned': 'optional', 'name': 'Area EOC at B2'}]},
                             str(REPO / 'testing' / 'fixtures' / 'map-synthetic'))
    ar = call(PB, 'POST', '/api/config/apply', {'config': dcfg, 'eoc': 'alpha', 'manned': []})
    ib = call(PB, 'GET', '/api/incident')
    check('drill config applied: identity, units, location, both lines, Stake President and the Winlink station, map folder; drill event opened',
          ar.get('ok') and ar.get('eventOpened') and ib.get('eocName') == 'Alpha Stake EOC' and ib.get('eocLevel') == 'stake' and len(ib.get('eocUnits', '').split(', ')) == 4
          and ib.get('eocLat') and 'Area Seventy' in ib.get('councilName', '') and 'WSRM' in ib.get('welfareName', '') and (ib.get('roles') or {}).get('sp', {}).get('name')
          and (ib.get('roles') or {}).get('ham', {}).get('phone') == 'N0CALL-3' and ib.get('name') == 'DRILL API test' and ib.get('mapPath', '').endswith('map-synthetic')
          and ib.get('parentName') == '', {k: ib.get(k) for k in ('eocName', 'name', 'parentName', 'mapPath')})
    wb = call(PB, 'GET', '/api/watcher/status')
    sb = SP / 'srvB_appdata' / 'Church of Jesus Christ EMCOMM' / 'eoc-settings.json'
    check('drill config: the Winlink call sign feeds the watcher and is saved for the next start', wb.get('callsigns') == ['N0CALL-3']
          and json.loads(sb.read_text(encoding='utf-8')).get('winlinkCallsigns') == ['N0CALL-3'], wb.get('callsigns'))
    ar2 = call(PB, 'POST', '/api/config/apply', {'config': dcfg, 'eoc': 'alpha', 'manned': ['area']})
    ib2 = call(PB, 'GET', '/api/incident')
    check('drill config applied again (Area EOC staffed this time): no second event; the EOC above is the Area EOC', ar2.get('ok') and not ar2.get('eventOpened')
          and ib2.get('parentName') == 'Area EOC at B2' and ib2.get('eventId') == ib.get('eventId'), (ar2.get('eventOpened'), ib2.get('parentName')))
    try: call(PB, 'POST', '/api/config/apply', {'config': dcfg, 'eoc': 'nope'}); check('drill config: an unknown EOC is refused', False)
    except urllib.error.HTTPError as e: check('drill config: an unknown EOC is refused, naming the choices', e.code == 400 and b'alpha' in e.read())
    print('\nRESULT:', 'ALL PASS' if all(res) else 'FAILURES', f'({sum(res)}/{len(res)})')
finally:
    if keep:
        print('servers left running (stop them yourself):', [p.pid for p in procs], '· logs in', SP)
    else:
        for p in procs: p.terminate()
        for p in procs:
            try: p.wait(timeout=5)
            except Exception: p.kill()
sys.exit(0 if res and all(res) else 1)
