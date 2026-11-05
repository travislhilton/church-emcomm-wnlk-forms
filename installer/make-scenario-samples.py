#!/usr/bin/env python3
"""Winlink training sets for one scenario: filled Church forms and ICS 213RR resource requests.

    python installer/make-scenario-samples.py                        # every training/scenario-samples-src/*.json
    python installer/make-scenario-samples.py training/scenario-samples-src/copper-creek-dam.json

Source: training/scenario-samples-src/<scenario>.json (authored; invented people, 555-01xx phones,
@churchemcomm.sim emails). Output: training/scenario-samples/<code>/ (for example CCD-1), every file
name starting with the code:

  <code> NN - Disaster Report - <unit>.txt + <code>_NN_....html   Church forms, filled, THIS IS AN EXERCISE ticked,
                                                                   each with its own Winlink template definition
  Church_of_Jesus_Christ_*_Viewer.html                             viewers, so a received message opens as a form
  ICS213RR samples.json                                            the ICS 213RR requests: the installer builds each one
                                                                   from the station's own standard Winlink ICS213RR form
                                                                   (Standard Templates\\ICS USA Forms), so the Winlink
                                                                   form itself is never copied into this repository
  README.txt                                                       the whole set, in time order, with what each message
                                                                   is for and the answer it expects

Numbers run in drill-clock order across both kinds, so a trainer can send them in sequence.

The repository holds only the invented example community's sets. A real community's set (its own units, places and
partner agencies) has its source beside the directory export and is built into a private folder, ready to copy into
Winlink (the ICS 213RR forms are built there too from this station's standard form), or into a participant package
with installer/build-sim-package.py:

    python installer/make-scenario-samples.py "secure data/<export>/simulation/training/<source>.json" --out "<private folder>"

Optional source keys: stake_eoc (the receiving EOC's name, default "<stake> EOC"), agency {name, place, short} (the
city or county EOC that sends and answers the ICS 213RR requests; `short` names it in the file names, default
"City EOC"). One ICS 213RR message may carry its own `agency` (same keys, over the set's) when a set has both a city
and a county EOC.

A set is marked PRIVATE BUILD in its README when its source is a local one (outside the repository or under secure
data), whatever the output folder: the invented example's sets built with --out keep the public wording.
"""
import html as _html, importlib.util, json, pathlib, re, shutil, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location('mpf', ROOT / 'installer' / 'make-practice-forms.py')
mpf = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(mpf)

LABEL = {'dr': 'Disaster Report', 'so': 'Supply Order', 'wcl': 'Work Crew Log'}
# maxlength of each input on Winlink's standard ICS213RR_Initial.html (v. 14.6); textareas have none
ICS_MAX = {'IncName': 50, 'ActivityDateTime1': 23, 'ReqNum': 40, 'Delivery': 140, 'ReqName': 50, 'SecApp': 50,
           'LogNum': 45, 'SupInfo': 105, 'SupName': 45, 'POC': 40, 'Notes': 135, 'AuthSig': 45, 'OrderBy': 50, 'FinRepName': 35}
for _i in range(1, 9):
    ICS_MAX.update({f'Qty{_i}': 6, f'Kind{_i}': 8, f'Type{_i}': 8, f'Item{_i}': 60, f'ReqDateTime{_i}': 20, f'EstDateTime{_i}': 20, f'Cost{_i}': 10})
ICS_OK = set(ICS_MAX) | {'FormTitle', 'Priority', 'Subs1', 'FinComm'}


def grid(lat: float, lon: float) -> str:
    lon += 180; lat += 90
    return (chr(65 + int(lon // 20)) + chr(65 + int(lat // 10)) + str(int(lon % 20 // 2)) + str(int(lat % 10))
            + chr(97 + int(lon % 2 * 12)) + chr(97 + int(lat % 1 * 24)))


def winname(s: str) -> str:
    """A title usable in a Windows file name (a colon or slash in an ICS short title once crashed the build)."""
    return re.sub(r' +', ' ', re.sub(r'[<>:"/\\|?*]+', ' ', s)).strip(' .')


def safe(s: str) -> str:
    return re.sub(r'[^A-Za-z0-9]+', '_', s).strip('_')


def ics_script(code: str, n: int, s: dict) -> str:
    """The script added before </body> of the standard ICS213RR form: fills the fields after the form's own load code."""
    v = json.dumps(s['fields'], ensure_ascii=True).replace('</', '<\\/')
    note = json.dumps(f'TRAINING {code} {n:02d} ({s["from"]} to {s["to"]}): pre-filled. Address it to the receiving EOC, Submit, send.', ensure_ascii=True)
    return ('<script type="text/javascript">\n//<![CDATA[\n(function () {\n'
            f'  var v = {v};\n'
            '  function fill() {\n'
            '    for (var k in v) { var els = document.getElementsByName(k); if (!els.length) continue;\n'
            '      if (els[0].type === "radio") { for (var i = 0; i < els.length; i++) els[i].checked = (els[i].value === v[k]); } else els[0].value = v[k]; }\n'
            '    var t = document.getElementById("SubjectText"); if (t) t.innerHTML = v.FormTitle || "";\n'
            '    var ta = document.getElementsByTagName("textarea"); for (var j = 0; j < ta.length; j++) { try { AutoGrowTextArea(ta[j]); } catch (e) {} }\n'
            f'    var b = document.createElement("div"); b.appendChild(document.createTextNode({note}));\n'
            '    b.style.cssText = "background:#eef3fa;border:2px solid #1a3a5c;color:#1a3a5c;padding:6px;margin:4px;font:bold 13px Arial";\n'
            '    document.body.insertBefore(b, document.body.firstChild);\n'
            '  }\n'
            '  if (window.addEventListener) window.addEventListener("load", fill, false); else window.attachEvent("onload", fill);\n'
            '})();\n//]]>\n</script>\n')


def ics_text(s: dict) -> str:
    f = s['fields']
    out = [f'  1. Incident: {f.get("IncName", "")}   2. Date/Time: {f.get("ActivityDateTime1", "")}   3. Request #: {f.get("ReqNum", "")}   Priority: {f.get("Priority", "")}']
    for i in range(1, 9):
        if f.get(f'Item{i}'):
            out.append(f'     Qty {f.get(f"Qty{i}", "")} | Kind {f.get(f"Kind{i}", "")} | Type {f.get(f"Type{i}", "")} | {f[f"Item{i}"]} | needed {f.get(f"ReqDateTime{i}", "")}')
    out += [f'  5. Delivery/Reporting Location: {f.get("Delivery", "")}', f'  6. Substitutes/Suggested Sources: {f.get("Subs1", "")}',
            f'  7. Requested by: {f.get("ReqName", "")}   9. Section Chief: {f.get("SecApp", "")}',
            '  10-19. Logistics and Finance: left blank for the receiving EOC to fill in its reply.']
    return '\n'.join(out)


STD_ICS = [pathlib.Path(r'C:\RMS Express\Standard Templates\ICS USA Forms')]


def build(src: pathlib.Path, out_root: pathlib.Path = None) -> pathlib.Path:
    d = json.loads(src.read_text(encoding='utf-8'))
    code, stake, places = d['code'], d['stake'], d.get('places', {})
    out = (out_root or (ROOT / 'training' / 'scenario-samples')) / code
    if out_root and ROOT in out.resolve().parents and 'secure data' not in str(out.resolve()):
        sys.exit(f'{out}: a private build goes outside the repository (or under secure data/)')
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    stake_eoc = d.get('stake_eoc') or f'{stake} EOC'

    def agency_of(x: dict) -> dict:
        """The partner agency of one ICS message: its own `agency` keys over the set's, then the defaults."""
        a = dict(d.get('agency') or {}, **(x.get('agency') or {}))
        return {'name': a.get('name') or 'City EOC', 'place': a.get('place') or 'the city fire station', 'short': a.get('short') or 'City EOC'}
    try:
        src_shown = src.relative_to(ROOT).as_posix()
    except ValueError:
        src_shown = src.name
    # private = the source is a local one (outside the repository or under secure data), not just "built with --out"
    private = ROOT not in src.parents or 'secure data' in str(src)
    items = [dict(x, _k='church') for x in d.get('church', [])] + [dict(x, _k='ics') for x in d.get('ics213rr', [])]
    items.sort(key=lambda x: x['time'])
    viewers, ics, readme, problems, agencies = set(), [], [], [], {}
    for n, it in enumerate(items, 1):
        if it['_k'] == 'church':
            folder, initial, viewer, txt, label = mpf.TEMPLATES[it['form']]
            fields = dict(it['fields'])
            ll = places.get(it['unit'])
            if ll:
                fields.update({'stn_lat_d': f'{ll[0]:.5f}', 'stn_lon_d': f'{ll[1]:.5f}', 'stn_grid_d': grid(*ll)})
            unit_t = it['unit'] + (f' {it["tag"]}' if it.get('tag') else '')
            base = f'{code}_{n:02d}_{safe(label)}_{safe(unit_t)}'
            banner = (f'TRAINING FORM {code} {n:02d} &mdash; {_html.escape(d["title"])} drill, {_html.escape(stake)}, '
                      f'{it["time"]} on the drill day. {_html.escape(it["context"])} Change anything, then Submit and send it to your EOC.')
            page, unused = mpf.fill((ROOT / 'templates' / folder / initial).read_text(encoding='utf-8'), fields, f'({code} {n:02d})', banner)
            if unused:
                problems.append(f'{base}: no template input for {", ".join(unused)}')
            with open(out / f'{base}.html', 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(page)
            tdef = (ROOT / 'templates' / folder / txt).read_bytes().replace(initial.encode(), f'{base}.html'.encode(), 1)
            (out / f'{code} {n:02d} - {label} - {unit_t}.txt').write_bytes(tdef)
            if viewer not in viewers:
                shutil.copy2(ROOT / 'templates' / folder / viewer, out / viewer); viewers.add(viewer)
            f = fields
            readme.append(f'{code} {n:02d}  {it["time"]}  {label.upper()}  {unit_t} -> {stake_eoc} (Church form, Winlink)\n'
                          f'  {it["context"]}\n' + '\n'.join(
                              f'  {k}: {v}' for k, v in f.items() if k in ('miss_safe', 'miss_details', 'mem_details', 'needs_details', 'proj_name',
                                                                            'log_location', 'chief_name', 'del_contact')))
        else:
            ag = agency_of(it)
            fr, to = (ag['name'], stake_eoc) if it['dir'] == 'city-to-stake' else (stake_eoc, ag['name'])
            it.update({'from': fr, 'to': to})
            agencies.setdefault(ag['name'], ag)
            for k, v in it['fields'].items():
                if k not in ICS_OK:
                    problems.append(f'ICS {n:02d}: {k} is not a field of the standard ICS 213RR')
                elif k in ICS_MAX and len(v) > ICS_MAX[k]:
                    problems.append(f'ICS {n:02d}: {k} is {len(v)} characters, the form allows {ICS_MAX[k]}: {v!r}')
            short = winname(ag['short'])
            name = f'{code} {n:02d} - ICS 213RR - {f"{short} to Stake" if it["dir"] == "city-to-stake" else f"Stake to {short}"} - {winname(it["short"])}'
            ics.append({'n': n, 'name': name, 'html': f'{code}_{n:02d}_ICS213RR_{safe(it["short"])}.html', 'from': fr, 'to': to,
                        'time': it['time'], 'fields': it['fields'], 'script': ics_script(code, n, it)})
            readme.append(f'{code} {n:02d}  {it["time"]}  ICS 213RR RESOURCE REQUEST  {fr} -> {to} (standard Winlink form)\n  {it["context"]}\n{ics_text(it)}')
    with open(out / 'ICS213RR samples.json', 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps({'code': code, 'title': d['title'], 'samples': ics}, ensure_ascii=False, indent=1))
    ags = list(agencies.values()) or [agency_of({})]
    who = ' and the '.join(f"{a['name']} at {a['place']}" for a in ags)
    if len(ags) == 1:
        partner = f"""{who}. The city does not run this system: it gets only
    ICS forms, never Church forms. Its Winlink call sign is the one set on your stations."""
    else:
        partner = f"""{who}.
    These agencies do not run this system: they get only ICS forms, never Church forms. Their
    Winlink call signs are the ones set on your stations."""
    head = f"""Church of Jesus Christ EMCOMM Winlink training set {code}: {d['title']}, {stake}
{'=' * 78}

Acronyms used below: EMCOMM (emergency communications), EOC (Emergency Operations Center), HAM
(amateur radio operator), ERD (Emergency Response Director), WSRM and AWSRM (the Welfare and Self-Reliance
Manager, then the Area Welfare and Self-Reliance Manager), ICS (Incident Command System), FRS (Family Radio
Service), VARA (the sound-card radio modem Winlink uses).

Independent volunteer project, not an official Church product. Generated by
installer/make-scenario-samples.py from {src_shown}.

The drill: {d['note']}

What is here ({len(items)} messages, numbered in drill-clock order so you can send them in sequence):
  * {len(items) - len(ics)} Church forms (Disaster Report, Supply Order, Work Crew Log) from the stake's wards and
    branches to the {stake_eoc} (Emergency Operations Center). THIS IS AN EXERCISE is ticked.
  * {len(ics)} ICS 213RR Resource Requests on Winlink's standard form, between the stake EOC and the
    {partner}

Where they are after installing (HAM Field Operator and EOC Operator roles):
  Winlink Express -> New Message -> Select Template -> Global Templates ->
    Church of Jesus Christ EMCOMM Training {code} -> pick one.
  The ICS 213RR forms are built from your station's own standard ICS213RR form when the installer runs;
  a station without Winlink's standard templates gets only the Church forms (send the ICS requests by hand
  from the text below with Winlink's ICS USA Forms -> ICS213RR).
  A copy of the set is in Documents\\Church of Jesus Christ EMCOMM\\Training\\Winlink Training {code}\\.

Use: open the form, check it, click Submit, address the message (Church forms to your stake EOC's Winlink
address; ICS requests to the receiving EOC's address), and send by Telnet, VARA FM or VARA HF. On the stake EOC
the Church forms arrive as EXERCISE reports; an ICS 213RR from the city's call sign arrives as a work item
named for the city. Answer each ICS 213RR with an ICS 213 General Message, as the context line asks.

The messages
------------
"""
    if private:
        head = head.replace('Independent volunteer project', 'PRIVATE BUILD from a local source: it may name streets inside a ward. Keep it off\nany shared drive or repository. Independent volunteer project', 1)
    with open(out / 'README.txt', 'w', encoding='utf-8', newline='\r\n') as fh:
        fh.write(head + '\n\n'.join(readme) + '\n')
    std = next((p for p in STD_ICS if (p / 'ICS213RR_Initial.html').is_file()), None)
    if out_root and std:   # a private folder is copied into Winlink as is: build the ICS forms here, as install.ps1 does
        init = (std / 'ICS213RR_Initial.html').read_text(encoding='utf-8', errors='replace')
        tdef = (std / 'ICS213RR Resource Request Message.txt').read_text(encoding='utf-8', errors='replace')
        shutil.copy2(std / 'ICS213RR_Viewer.html', out / 'ICS213RR_Viewer.html')
        for smp in ics:
            i = init.rfind('</body>')
            with open(out / smp['html'], 'w', encoding='utf-8', newline='') as fh:
                fh.write(init[:i] + smp['script'] + init[i:])
            with open(out / (smp['name'] + '.txt'), 'w', encoding='utf-8', newline='') as fh:
                fh.write(re.sub(r'^\s*Form:\s*[^,\r\n]+,', 'Form: ' + smp['html'] + ',', tdef, count=1))
        (out / 'ICS213RR samples.json').unlink()
        print(f'  + {len(ics)} ICS 213RR forms built from {std}')
    print(f'{code}: {len(items)} messages ({len(items) - len(ics)} Church forms, {len(ics)} ICS 213RR) -> {out.relative_to(ROOT) if ROOT in out.parents else out}')
    for p in problems:
        print('  PROBLEM:', p)
    if problems:
        sys.exit(1)
    return out


def main():
    args = sys.argv[1:]
    out_root = None
    if '--out' in args:
        i = args.index('--out'); out_root = pathlib.Path(args[i + 1]).resolve(); del args[i:i + 2]
    srcs = [pathlib.Path(a) for a in args] or sorted((ROOT / 'training' / 'scenario-samples-src').glob('*.json'))
    for s in srcs:
        if not out_root and 'secure data' in str(s.resolve()):
            sys.exit(f'{s}: a local source is built with --out <private folder>, never into the repository')
        build(s.resolve(), out_root)


if __name__ == '__main__':
    main()
