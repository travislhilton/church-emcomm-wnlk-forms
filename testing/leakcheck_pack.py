# Leak check (checklist A21), run on an EOC laptop after a pseudonymized simulator run of a real pack: does anything the simulator served or the EOC filed carry a REAL phone or email of the real directory export,
# and is every phone and email there an invented one (NXX-555-01XX, @churchemcomm.sim)?
# python -I testing/leakcheck_pack.py <real export folder> <installed simulation folder>. Prints counts only.
import sys, re, json, urllib.request
sys.path.insert(0, sys.argv[2])
import orgpack, privacy
real = orgpack.load(sys.argv[1])
assert not real.get('pre_pseudonymized'), 'the comparison pack must be the real export'
names, pairs, phones, emails = privacy._real_values(real)
phones = {p[-10:] for p in phones if len(p) >= 7}
def get(u):
    with urllib.request.urlopen(u, timeout=30) as r: return r.read().decode('utf-8', 'replace')
srcs = [('served pack', 'http://127.0.0.1:8090/api/pack'), ('run', 'http://127.0.0.1:8090/api/run'),
        ('run report', 'http://127.0.0.1:8090/api/run/report'), ('results page data', 'http://127.0.0.1:8090/results'),
        ('EOC messages', 'http://127.0.0.1:8080/api/messages'), ('EOC work items', 'http://127.0.0.1:8080/api/actions'),
        ('EOC read-out', 'http://127.0.0.1:8080/api/readout'), ('EOC incident', 'http://127.0.0.1:8080/api/incident')]
print(f'real export: {len(phones)} real phones, {len(emails)} real emails')
bad = 0
for k, u in srcs:
    try: t = get(u)
    except Exception as e: print(f'{k}: not read ({type(e).__name__})'); bad += 1; continue
    low = t.lower()
    re_e = sum(1 for e in emails if e in low)
    nums = [re.sub(r'\D', '', m)[-10:] for m in re.findall(privacy.PHONE_RE, t)]
    re_p = len(set(nums) & phones)
    not_fic_p = sum(1 for n in nums if len(n) == 10 and n[3:8] != '55501')
    mails = re.findall(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', t)
    not_fic_e = sum(1 for m in mails if not m.lower().endswith('@' + privacy.SIM_DOMAIN))
    bad += re_e + re_p
    doms = __import__('collections').Counter(m.split('@')[1].lower() for m in mails if not m.lower().endswith('@' + privacy.SIM_DOMAIN))
    print(f'{k}: {len(t)} chars; real emails {re_e}, real phones {re_p}; phones {len(nums)} ({not_fic_p} not 555-01XX), emails {len(mails)} ({not_fic_e} not @{privacy.SIM_DOMAIN}' + (': ' + ', '.join(f'{d} {n}' for d, n in doms.most_common()) if doms else '') + ')')
print('LEAKCHECK ' + ('PASS no real phone or email of the export anywhere' if bad == 0 else f'FAIL {bad}'))
