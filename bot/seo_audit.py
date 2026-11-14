"""サイト全ページをGoogleのお作法で点検（title/description/h1/見出し順/canonical/sitemap/JSON-LD/alt/広告リンクのsponsored/PR表示位置/リンク切れ/重複/孤立）。使い方：cd site && python3 ../seo_audit.py"""
import re,glob,json,os,html,collections,urllib.parse
SITE='.'
pages=[p for p in sorted(glob.glob('*.html')+glob.glob('articles/*.html')+glob.glob('manga/**/*.html',recursive=True)) if not p.startswith('google')]
sm=open('sitemap.xml',encoding='utf-8').read()
titles=collections.defaultdict(list); descs=collections.defaultdict(list); inbound=collections.Counter()
issues=collections.defaultdict(list)
AFF=re.compile(r"hb\.afl\.rakuten|valuecommerce|px\.a8\.net|linksynergy|amazon\.co\.jp/.*tag=")
for p in pages:
    t=open(p,encoding='utf-8').read()
    if '<!--redirect-->' in t: continue
    head=t[:t.find('<body')] if '<body' in t else t[:8000]
    noidx='noindex' in head
    ti=re.search(r'<title>(.*?)</title>',t,re.S); ti=html.unescape(ti.group(1)).strip() if ti else ''
    d=re.search(r'<meta name=description content=["\']([^"\']*)',t); d=html.unescape(d.group(1)) if d else ''
    if not noidx: titles[ti].append(p); descs[d].append(p)
    I=issues[p]
    if not ti: I.append('titleなし')
    elif len(ti)>70: I.append(f'title長い({len(ti)})')
    if not d: I.append('descriptionなし')
    if '<html lang=ja' not in t and "<html lang='ja'" not in t: I.append('lang=jaなし')
    if 'name=viewport' not in t: I.append('viewportなし')
    h1=len(re.findall(r'<h1[ >]',t))
    if h1!=1: I.append(f'h1が{h1}個')
    lv=[int(x) for x in re.findall(r'<h([1-4])[ >]',t)]
    for a,b in zip(lv,lv[1:]):
        if b-a>1: I.append(f'見出し飛び h{a}→h{b}'); break
    if not noidx:
        if 'rel=canonical' not in t: I.append('canonicalなし')
        url='https://totalyamanote.github.io/'+('' if p=='index.html' else p)
        if f"<loc>{url}</loc>" not in sm: I.append('sitemapにない')
    for m in re.findall(r'<script type=application/ld\+json>(.*?)</script>',t):
        try: json.loads(m)
        except Exception: I.append('JSON-LD壊れ')
    imgs=re.findall(r'<img [^>]*>',t)
    if any(("alt=''" in i or 'alt=""' in i or ' alt=' not in i) for i in imgs): I.append('alt空あり')
    links=re.findall(r'<a ([^>]*)>',t)
    affs=[l for l in links if AFF.search(l)]
    if affs and any('sponsored' not in l for l in affs): I.append(f'広告リンクにsponsoredなし({sum("sponsored" not in l for l in affs)})')
    if any("target=_blank" in l and 'noopener' not in l for l in links): I.append('target=_blankにnoopenerなし')
    if affs:
        body=t[t.find('<body'):] if '<body' in t else t
        if not (0<=body.find('PR')<body.find('<h1')): I.append('PRが見出しより下')
    for l in links:
        h=re.search(r"href=['\"]?([^'\" >]+)",l)
        if not h: continue
        h=h.group(1)
        if h.startswith(('http','#','mailto','javascript')): continue
        tgt=os.path.normpath(os.path.join(os.path.dirname(p),h.split('#')[0].split('?')[0]))
        if tgt.endswith('/') or os.path.isdir(tgt): tgt=os.path.join(tgt,'index.html')
        if h.startswith('/'): tgt=h.lstrip('/') or 'index.html'
        if not os.path.exists(tgt): I.append(f'リンク切れ:{h}')
        else: inbound[os.path.normpath(tgt)]+=1
for k,v in titles.items():
    if len(v)>1: [issues[p].append('title重複') for p in v]
for k,v in descs.items():
    if len(v)>1 and k: [issues[p].append('description重複') for p in v]
for p in pages:
    t=open(p,encoding='utf-8').read()
    if 'noindex' not in t[:6000] and p!='index.html' and inbound[os.path.normpath(p)]==0: issues[p].append('孤立（内部リンクなし）')
n=0
for p in pages:
    if issues[p]: n+=1; print(p,'→',' / '.join(dict.fromkeys(issues[p])))
print(f'--- {len(pages)}ページ中 問題あり {n}')
