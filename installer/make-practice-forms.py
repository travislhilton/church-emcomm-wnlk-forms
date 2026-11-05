#!/usr/bin/env python3
"""Pre-filled Winlink practice forms from a simulator scenario.

    python installer/make-practice-forms.py                      # invented Juniper Plains Area (Larkspur Stake) -> training/practice-forms/
    python installer/make-practice-forms.py --data "<your directory export>" --out "<a folder outside the repo>"   # your own stake
    options: --scenario <id> (default copper-creek-dam)  --seed <n>  --dr 3 --so 2 --wcl 2

Each practice form is a copy of a Winlink Initial template with the fields already filled in
from one simulated report of the scenario, with THIS IS AN EXERCISE ticked, plus its own .txt
template definition so it appears in Winlink Express -> Select Template. The viewers are copied
beside them so a received practice message opens as a form. Copy the folder to

    C:\\RMS Express\\Global Folders\\Templates\\Church of Jesus Christ EMCOMM Practice\\

(the installer does this for the HAM and EOC roles). Open one, change anything, Submit, send it
to your EOC over Telnet or VARA, and watch it arrive in the Message Center marked EXERCISE.

The default pack is the invented Juniper Plains Area (simulation\\example\\juniper-plains; its
first stake, Larkspur Stake): no real unit, person, phone or email, so the generated files are
safe to share and are committed. With --data the files carry your stake's
data (names pseudonymized unless --real): keep them out of the repository.
"""
import datetime as _dt, html, pathlib, re, shutil, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'simulation'))
import orgpack, engine, privacy   # noqa: E402

TEMPLATES = {
    'dr': ('disaster-report', 'Church_of_Jesus_Christ_Disaster_Report_Initial.html', 'Church_of_Jesus_Christ_Disaster_Report_Viewer.html',
           'Church of Jesus Christ Disaster Report.txt', 'Disaster Report'),
    'so': ('supply-order', 'Church_of_Jesus_Christ_Supply_Order_Initial.html', 'Church_of_Jesus_Christ_Supply_Order_Viewer.html',
           'Church of Jesus Christ Supply Order.txt', 'Supply Order'),
    'wcl': ('work-crew-log', 'Church_of_Jesus_Christ_Work_Crew_Log.html', 'Church_of_Jesus_Christ_Work_Crew_Log_Viewer.html',
            'Church of Jesus Christ Work Crew Log.txt', 'Work Crew Log'),
}
SKIP_KEYS = {'sim_run', 'sim_mark'}


def arg(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name)
        return sys.argv[i + 1] if i + 1 < len(sys.argv) else default
    return default


def esc(v) -> str:
    return html.escape(str(v if v is not None else ''), quote=True)


def fill(src: str, data: dict, title_note: str, banner: str) -> tuple:
    """The Initial template with every field in `data` filled in. Returns (html, unused keys)."""
    t, unused = src, []
    for k, v in data.items():
        if k in SKIP_KEYS or v is None or v == '':
            continue
        v = str(v)
        # text-like inputs: <input type="text" id="k" name="k" ... />
        pat = re.compile(r'<input type="(?:text|tel|email|date)"([^>]*?)\bid="' + re.escape(k) + r'"([^>]*?)/>')
        if pat.search(t):
            t = pat.sub(lambda m: '<input type="%s"%s id="%s"%s value="%s" />' % (
                re.search(r'type="(\w+)"', m.group(0)).group(1), re.sub(r'\s*value="[^"]*"', '', m.group(1)), k,
                re.sub(r'\s*value="[^"]*"', '', m.group(2)).rstrip(), esc(v)), t, count=1)
            continue
        pat = re.compile(r'<textarea id="' + re.escape(k) + r'"([^>]*)></textarea>')
        if pat.search(t):
            t = pat.sub(lambda m: '<textarea id="%s"%s>%s</textarea>' % (k, m.group(1), esc(v)), t, count=1)
            continue
        pat = re.compile(r'<input type="radio" name="' + re.escape(k) + r'" value="' + re.escape(v.upper()) + r'" />')
        if pat.search(t):
            t = pat.sub('<input type="radio" name="%s" value="%s" checked="checked" />' % (k, v.upper()), t, count=1)
            continue
        pat = re.compile(r'<input type="checkbox" id="' + re.escape(k) + r'" name="' + re.escape(k) + r'" value="([^"]*)"([^>]*?)/>')
        if pat.search(t):
            if v.strip().lower() in ('yes', '1', 'true', 'on'):
                t = pat.sub(lambda m: '<input type="checkbox" id="%s" name="%s" value="%s"%s checked="checked" />' % (k, k, m.group(1), m.group(2).rstrip()), t, count=1)
            continue
        unused.append(k)
    # THIS IS AN EXERCISE is always on, and the subject prefix with it
    t = re.sub(r'<input type="checkbox" id="exercise" name="exercise" value="YES" onchange="exChanged\(\)" />',
               '<input type="checkbox" id="exercise" name="exercise" value="YES" onchange="exChanged()" checked="checked" />', t, count=1)
    t = t.replace('<input type="hidden" name="subj_prefix" id="subj_prefix" value="" />', '<input type="hidden" name="subj_prefix" id="subj_prefix" value="EXERCISE - " />', 1)
    t = re.sub(r'<title>(.*?)</title>', lambda m: '<title>%s %s</title>' % (m.group(1), esc(title_note)), t, count=1)
    t = t.replace('<div class="exbox" id="exbox">', '<div class="exbox" style="color:#1a3a5c;border-color:#1a3a5c;background:#eef3fa">%s</div>\n      <div class="exbox" id="exbox">' % banner, 1)
    return t, unused


def pick(items: list, form: str, n: int) -> list:
    """Up to n form items of this type, earliest first, spread over different units and severities."""
    cand = sorted((it for it in items if it['kind'] == 'form' and it['form'] == form and not it.get('after')
                   and it.get('inject') != 'wcl-unsupervised'), key=lambda it: it['t'])   # ordinary reports only
    out, seen_units, seen_sev = [], set(), set()
    for prefer_new_sev in (True, False):
        for it in cand:
            if len(out) >= n:
                break
            sev = it.get('severity')
            if it['unit'] in seen_units or (prefer_new_sev and sev in seen_sev):
                continue
            out.append(it); seen_units.add(it['unit']); seen_sev.add(sev)
    return sorted(out, key=lambda it: it['t'])


def summary(form: str, d: dict) -> str:
    if form == 'dr':
        return f"{d.get('inc_ward') or d.get('inc_stake')}: {d.get('inc_type', '')}; injured {d.get('mem_injuries') or 0}, deaths {d.get('mem_deaths') or 0}, homes damaged {d.get('mem_damaged') or 0}, missionaries safe {d.get('miss_safe', '')}"
    if form == 'so':
        n = sum(1 for k, v in d.items() if re.fullmatch(r'(gs|tl|pi|wa|kb)\d\d|other_qty\d', k) and str(v).strip() not in ('', '0'))
        return f"{d.get('req_stake')}: {n} item types, deliver to {d.get('del_city', '')}"
    crew = sum(1 for k in d if re.fullmatch(r'crew_name\d+', k))
    return f"{d.get('chief_ward') or d.get('chief_stake')}: chief {d.get('chief_name', '')}, {crew} crew"


def main():
    example = ROOT / 'simulation' / 'example' / 'juniper-plains'
    data = arg('--data', str(example))
    invented = pathlib.Path(data).resolve() == example.resolve()
    out = pathlib.Path(arg('--out', str(ROOT / 'training' / 'practice-forms')))
    sid = arg('--scenario', 'copper-creek-dam')
    seed = int(arg('--seed', '7'))
    counts = {'dr': int(arg('--dr', '3')), 'so': int(arg('--so', '2')), 'wcl': int(arg('--wcl', '2'))}
    pack = orgpack.load(data)
    invented = invented or pack.get('source') == 'synthetic-fixture'
    if '--real' not in sys.argv and not invented:
        pack = privacy.pseudonymize(pack, privacy.salt_for(pathlib.Path(data) if pathlib.Path(data).is_dir() else pathlib.Path(data).parent))
    sc = engine.load_scenario(sid)
    stake = pack['stakes'][0]
    run = engine.plan(pack, sc, {'seed': seed, 'today': _dt.date.today().isoformat(), 'stakes': [stake['id']],
                                 'eoc': {'name': f"{stake['name']} EOC", 'call': 'EOC-CALL', 'winlink': 'EOC-CALL@winlink.org', 'email': 'eoc@example.test'}})
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob('*'):
        if f.is_file():
            f.unlink()
    made, n = [], 0
    for form in ('dr', 'so', 'wcl'):
        folder, initial, viewer, txt, label = TEMPLATES[form]
        src = (ROOT / 'templates' / folder / initial).read_text(encoding='utf-8')
        tdef = (ROOT / 'templates' / folder / txt).read_bytes()
        shutil.copy2(ROOT / 'templates' / folder / viewer, out / viewer)
        for it in pick(run['items'], form, counts[form]):
            n += 1
            d = {k: v for k, v in it['payload'].items() if k not in SKIP_KEYS}
            unit = re.sub(r'[^A-Za-z0-9]+', '_', it['unit']).strip('_')
            base = f'Practice_{n}_{label.replace(" ", "_")}_{unit}'
            banner = (f'PRACTICE FORM {n} &mdash; pre-filled from the EMCOMM simulator scenario &ldquo;{esc(sc["name"])}&rdquo; '
                      f'(minute {int(it["t"])}, {esc(it["unit"])}). Change anything, then Submit and send it to your EOC.')
            page, unused = fill(src, d, f'(practice {n})', banner)
            with open(out / f'{base}.html', 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(page)
            name = f'Practice {n} - {label} - {it["unit"]}.txt'
            (out / name).write_bytes(tdef.replace(initial.encode(), f'{base}.html'.encode(), 1))
            made.append((n, label, it['unit'], summary(form, d), unused))
    lines = [f'  {i}. {label} - {unit}: {s}' for i, label, unit, s, _ in made]
    readme = f"""Church of Jesus Christ EMCOMM practice forms - pre-filled Winlink templates
===========================================================

EMCOMM = emergency communications. Independent volunteer project, not an official Church product. {len(made)} forms generated by
installer/make-practice-forms.py {('from the invented Copper Creek Dam scenario (Larkspur Stake, Juniper Plains Area)' if invented and sid == 'copper-creek-dam' else f'from the EMCOMM simulator scenario "{sc["name"]}"')} (seed {seed})
over {'invented organizations and people' if invented else 'YOUR directory export (pseudonymized contacts) - keep this folder private'}.

Every form has THIS IS AN EXERCISE ticked: the message starts with the exercise banner, the
subject starts with EXERCISE, and the EOC (Emergency Operations Center) Message Center marks the
report as an exercise. Leave it ticked.

Install: copy this whole folder to
  C:\\RMS Express\\Global Folders\\Templates\\Church of Jesus Christ EMCOMM Practice\\
(the Church of Jesus Christ EMCOMM installer does this for the HAM Field Operator (licensed amateur radio) and EOC Operator roles, and
also puts a training copy in Documents\\Church of Jesus Christ EMCOMM\\Training\\Winlink Practice Forms\\
with a shortcut in the desktop folder Church of Jesus Christ EMCOMM Forms).

Use: Winlink Express -> New Message -> Select Template -> Global Templates ->
Church of Jesus Christ EMCOMM Practice -> pick one. The form opens already filled in. Change
anything you like (the date fields reset to today, Sender Location is your station), click Submit,
address the message to your EOC's Winlink address, Open Session and send: Telnet over the internet,
or by radio with VARA (the sound-card radio modem Winlink uses), VARA FM on VHF/UHF (very high /
ultra high frequency), then VARA HF (high frequency). On the EOC the report arrives marked
EXERCISE; the viewer shows the exercise box when the message is opened in Winlink Express.

The forms:
{chr(10).join(lines)}

Regenerate (different seed, more forms, your own stake):
  python installer/make-practice-forms.py --seed 11 --dr 4 --so 3 --wcl 3
  python installer/make-practice-forms.py --data "<your directory export>" --out "<a folder outside the repo>"
"""
    with open(out / 'README.txt', 'w', encoding='utf-8', newline='\r\n') as fh:
        fh.write(readme)
    print(f'{len(made)} practice forms -> {out}')
    for i, label, unit, s, unused in made:
        print(f'  {i}. {label} - {unit}: {s}' + (f'   [fields without a template input: {", ".join(unused)}]' if unused else ''))


if __name__ == '__main__':
    main()
