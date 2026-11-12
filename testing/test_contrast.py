#!/usr/bin/env python3
"""Every page people read must be readable: WCAG 2 AA text contrast (4.5:1, large text 3:1) in every engine and theme.

Runs a scratch EOC server with a little content (an event, four Disaster Reports in each status, work items at each
priority, a roster) and a static server for the portal, then opens every page people use (each Message Center tab and
its help, the wall, the phone page, the EOC's forms, the portal, the comms sheet, the QR posters, the Worker forms, the
Winlink templates and the quick reference cards) in Chromium, Firefox and WebKit, in the light and the dark color
scheme. For each visible text element (and each empty input's placeholder) it takes the computed text color, blends in
any opacity, finds the first opaque background behind it and measures the ratio. Text over a gradient is skipped.

    python testing/test_contrast.py [--engines=chromium,firefox,webkit] [--ports=8580,8581]

Needs Playwright (python -m pip install playwright; python -m playwright install firefox webkit), with Chrome installed.
"""
import functools
import http.server
import json
import os
os.environ.setdefault('EMCOMM_DISCOVERY', 'test')
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print('SKIP: playwright is not installed (python -m pip install playwright; python -m playwright install firefox webkit)')
    sys.exit(0)

REPO = pathlib.Path(__file__).resolve().parent.parent
ARGS = dict(a[2:].split('=', 1) for a in sys.argv[1:] if a.startswith('--') and '=' in a)
PE, PW = (int(x) for x in ARGS.get('ports', '8580,8581').split(','))
ENGINES = ARGS.get('engines', 'chromium,firefox,webkit').split(',')
E, W = f'http://127.0.0.1:{PE}', f'http://127.0.0.1:{PW}'
VP = {'laptop': {'width': 1366, 'height': 900}, 'phone': {'width': 390, 'height': 844}, 'wall': {'width': 1920, 'height': 1080}}

JS = r"""() => {
  function rgba(s){ var m=s.match(/rgba?\(([^)]+)\)/); if(!m) return null; var p=m[1].split(/[ ,\/]+/).filter(Boolean).map(parseFloat); return {r:p[0],g:p[1],b:p[2],a:p.length>3?p[3]:1}; }
  function lum(c){ return [c.r,c.g,c.b].map(function(v){ v/=255; return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4); }).reduce(function(s,v,i){ return s+v*[0.2126,0.7152,0.0722][i]; },0); }
  function blend(fg,bg){ return {r:fg.r*fg.a+bg.r*(1-fg.a), g:fg.g*fg.a+bg.g*(1-fg.a), b:fg.b*fg.a+bg.b*(1-fg.a), a:1}; }
  function bgOf(el){ var layers=[]; for(var e=el;e;e=e.parentElement){ var cs=getComputedStyle(e); if(cs.backgroundImage&&cs.backgroundImage!=='none'&&cs.backgroundImage.indexOf('gradient')>=0) return {grad:true};
      var c=rgba(cs.backgroundColor); if(c&&c.a>0){ layers.push(c); if(c.a>=1) break; } }
    var bg={r:255,g:255,b:255,a:1}; for(var i=layers.length-1;i>=0;i--) bg=blend(layers[i],bg); return bg; }
  function hex(c){ return '#'+[c.r,c.g,c.b].map(function(v){ return ('0'+Math.round(v).toString(16)).slice(-2); }).join(''); }
  var out=[];
  document.querySelectorAll('body *').forEach(function(el){
    if(['SCRIPT','STYLE','NOSCRIPT','OPTION'].indexOf(el.tagName)>=0 || el.closest('svg')) return;
    var txt=''; el.childNodes.forEach(function(n){ if(n.nodeType===3) txt+=n.textContent; }); txt=txt.trim();
    if(!txt && !(el.tagName==='INPUT'&&el.placeholder&&!el.value)) return;
    var r=el.getBoundingClientRect(); if(r.width<1||r.height<1) return;
    var cs=getComputedStyle(el); if(cs.visibility==='hidden') return;
    var op=1; for(var e=el;e;e=e.parentElement){ var c2=getComputedStyle(e); if(c2.display==='none') return; op*=parseFloat(c2.opacity); }
    if(op===0) return;
    var bg=bgOf(el); if(bg.grad) return;
    var col=el.tagName==='INPUT'&&!el.value ? rgba(getComputedStyle(el,'::placeholder').color||cs.color) : rgba(cs.color); if(!col) return;
    col.a=(col.a==null?1:col.a)*op; var fg=blend(col,bg);
    var L1=lum(fg),L2=lum(bg),ratio=(Math.max(L1,L2)+0.05)/(Math.min(L1,L2)+0.05);
    var size=parseFloat(cs.fontSize), bold=parseInt(cs.fontWeight)>=700, large=size>=24||(bold&&size>=18.66);
    var need=large?3:4.5;
    if(ratio<need) out.push({pair:hex(fg)+' on '+hex(bg), ratio:Math.round(ratio*100)/100, need:need, text:(txt||el.placeholder).slice(0,50),
      tag:el.tagName+(el.id?'#'+el.id:'')+(el.className&&typeof el.className==='string'?'.'+el.className.split(' ')[0]:'')});
  });
  return out;
}"""

PAGES = [('Message Center overview', E + '/', 'laptop', None), ('MC work items', E + '/', 'laptop', "switchTab('actions')"),
         ('MC disaster reports', E + '/', 'laptop', "switchTab('dr')"), ('MC messages', E + '/', 'laptop', "switchTab('msgs')"),
         ('MC roster', E + '/', 'laptop', "switchTab('roster')"), ('MC setup', E + '/', 'laptop', "switchTab('setup')"),
         ('MC comms', E + '/', 'laptop', "switchTab('comms')"), ('MC help', E + '/', 'laptop', 'openHelp()'),
         ('Wall display', E + '/wall', 'wall', None), ('Phone page /m', E + '/m', 'phone', None), ('EOC form /forms/dr', E + '/forms/dr', 'phone', None),
         ('Portal', W + '/forms/', 'phone', None), ('Comms sheet page', W + '/forms/comms.html', 'phone', None),
         ('QR posters', W + '/forms/qr-posters.html', 'laptop', None),
         ('Worker DR', W + '/templates/disaster-report/Church_of_Jesus_Christ_Disaster_Report_Worker.html', 'phone', None),
         ('Worker SO', W + '/templates/supply-order/Church_of_Jesus_Christ_Supply_Order_Worker.html', 'phone', None),
         ('Worker WCL', W + '/templates/work-crew-log/Church_of_Jesus_Christ_Work_Crew_Log_Worker.html', 'phone', None),
         ('Winlink DR template', W + '/templates/disaster-report/Church_of_Jesus_Christ_Disaster_Report_Initial.html', 'laptop', None),
         ('Winlink SO template', W + '/templates/supply-order/Church_of_Jesus_Christ_Supply_Order_Initial.html', 'laptop', None),
         ('Winlink WCL template', W + '/templates/work-crew-log/Church_of_Jesus_Christ_Work_Crew_Log.html', 'laptop', None),
         ('Quick reference cards', W + '/training/quick-ref-cards.html', 'laptop', None)]


def api(path, method='GET', body=None):
    r = urllib.request.Request(E + path, data=json.dumps(body).encode() if body is not None else None, method=method,
                               headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(r, timeout=10).read() or b'null')


def main():
    tmp = pathlib.Path(tempfile.mkdtemp(prefix='emcomm_contrast_'))
    (tmp / 'home').mkdir()
    env = dict(os.environ, LOCALAPPDATA=str(tmp / 'appdata'), HOME=str(tmp / 'home'), USERPROFILE=str(tmp / 'home'),
               EMCOMM_DOCUMENTS=str(tmp / 'docs'))
    site = tmp / 'site'
    (site / 'eoc').mkdir(parents=True)
    for f in ('eoc_server.py', 'EOC_Message_Center.html', 'EOC_Wall_Display.html', 'EOC_Phone.html', 'readout.py'):
        shutil.copy2(REPO / 'eoc' / f, site / 'eoc' / f)
    shutil.copytree(REPO / 'templates', site / 'templates')
    srv = subprocess.Popen([sys.executable, '-u', 'eoc_server.py', str(PE)], cwd=str(site / 'eoc'), env=env,
                           stdout=open(tmp / 'eoc.log', 'w'), stderr=subprocess.STDOUT)

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    web = http.server.ThreadingHTTPServer(('127.0.0.1', PW), functools.partial(Quiet, directory=str(REPO)))
    threading.Thread(target=web.serve_forever, daemon=True).start()
    fails = 0
    try:
        for _ in range(60):
            try:
                api('/api/status')
                break
            except Exception:
                time.sleep(0.25)
        api('/api/events', 'POST', {'name': 'Copper Creek flood (THIS IS AN EXERCISE)', 'type': 'Flood'})
        api('/api/merge', 'POST', {'kind': 'church_eoc_rollup', 'from': {'name': 'Larkspur 4th Ward'},
            'msgs': [{'id': f'ca-{i}', 'type': t, 'status': s, 'dr': {'stake': 'Larkspur Stake', 'ward': f'Larkspur {i}th Ward', 'type': 'Flood',
                      'location': f'{i} Willow Ln', 'mem_injured': '1', 'miss_safe': 'NO' if i == 1 else 'YES', 'exercise': 'YES'}}
                     for i, (t, s) in enumerate((('dr', 'new'), ('dr', 'ack'), ('dr', 'assigned'), ('dr', 'done')), 1)],
            'roster': [{'id': f'cr{i}', 'name': f'Larkspur {i}th Ward'} for i in range(1, 5)],
            'actions': [{'id': f'cx{i}', 'title': f'Item {i}', 'status': st, 'prio': p}
                        for i, (st, p) in enumerate((('open', 1), ('progress', 2), ('up', 2), ('done', 3)), 1)]})
        with sync_playwright() as p:
            launchers = {'chromium': lambda: p.chromium.launch(channel='chrome'), 'firefox': p.firefox.launch, 'webkit': p.webkit.launch}
            for eng in ENGINES:
                try:
                    b = launchers[eng]()
                except Exception as e:
                    if eng != 'chromium':
                        raise
                    print(f'NOTE chromium: no Chrome ({str(e)[:80]}); using the Playwright build')
                    b = p.chromium.launch()
                for scheme in ('light', 'dark'):
                    for name, url, kind, js in PAGES:
                        ctx = b.new_context(viewport=VP[kind], color_scheme=scheme)
                        pg = ctx.new_page()
                        pg.on('dialog', lambda d: d.dismiss())
                        pg.goto(url, wait_until='load')
                        pg.wait_for_timeout(1500)
                        if js:
                            pg.evaluate(js)
                            pg.wait_for_timeout(500)
                        bad = pg.evaluate(JS)
                        ctx.close()
                        label = f'{eng} {scheme}: {name}'
                        if not bad:
                            print(f'PASS {label}: every text element meets AA')
                            continue
                        fails += 1
                        pairs = {}
                        for x in bad:
                            pairs.setdefault(x['pair'], []).append(x)
                        print(f'FAIL {label}: {len(bad)} text element(s) below AA')
                        for pair, xs in sorted(pairs.items(), key=lambda kv: kv[1][0]['ratio']):
                            print(f"       {pair}  {xs[0]['ratio']}:1 (needs {xs[0]['need']})  x{len(xs)}  e.g. {xs[0]['tag']} '{xs[0]['text']}'")
                b.close()
    finally:
        srv.terminate()
        web.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    n = len(ENGINES) * 2 * len(PAGES)
    print(f'\n{n - fails}/{n} page views meet WCAG AA text contrast' + ('' if not fails else f'; {fails} FAIL'))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
