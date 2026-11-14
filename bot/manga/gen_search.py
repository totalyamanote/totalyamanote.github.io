"""サイト内検索：検索用の一覧（search-index.json）を作り、各ページに検索ボックス（SBAR）を差し込む部品。
一覧に入れるもの：比較記事の各商品／マンガ作品／新刊／主なページ。ブラウザの中だけで検索する（外部サービスなし）。
"""
import html
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE / "site"
BASE = "https://totalyamanote.github.io/"

CSS = ("<style>.sbar{position:relative;margin:6px 0 12px}.sbar input{width:100%;box-sizing:border-box;padding:10px 16px;border:1px solid var(--line,#e7e5e4);border-radius:99px;font-size:16px;background:var(--card,#fff);color:inherit}"
       ".sbar input:focus-visible{outline:3px solid #2563eb;outline-offset:1px}.sbar .sr{position:absolute;left:-9999px}"
       ".sres{position:absolute;z-index:30;left:0;right:0;list-style:none;margin:4px 0 0;padding:4px;background:var(--card,#fff);border:1px solid var(--line,#e7e5e4);border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,.15);max-height:60vh;overflow:auto}"
       ".sres a{display:block;padding:9px 10px;text-decoration:none;color:inherit;font-size:14px;border-radius:8px;line-height:1.4}.sres a:hover,.sres a:focus{background:#fff7ed}"
       ".sres b{font-size:11px;background:#c2410c;color:#fff;border-radius:99px;padding:1px 8px;margin-right:6px;font-weight:800}.sres small{display:block;color:#665d55;font-size:12px}.sres .none{padding:10px;color:#665d55;font-size:13px}</style>")
JS = ("<script>(function(){var b=document.currentScript.parentNode,i=b.querySelector('input'),r=b.querySelector('ul'),base=b.getAttribute('data-base'),D=null;"
      "function n(s){return s.normalize('NFKC').toLowerCase().replace(/[\\u30a1-\\u30f6]/g,function(c){return String.fromCharCode(c.charCodeAt(0)-96)})}"
      "function load(cb){if(D)return cb();fetch(base+'search-index.json').then(function(x){return x.json()}).then(function(j){D=j.map(function(e){return{t:e[0],n:e[1],u:e[2],s:e[3],m:n(e[1]),k:n(e[1]+' '+e[3])}});cb()})}"
      "function go(){var q=n(i.value).split(/\\s+/).filter(Boolean);if(!q.length){r.hidden=true;return}load(function(){var m=D.filter(function(e){return q.every(function(w){return e.k.indexOf(w)>=0})});"
      "m.sort(function(a,c){var x=q.every(function(w){return a.m.indexOf(w)>=0})?0:1,y=q.every(function(w){return c.m.indexOf(w)>=0})?0:1;return x-y});m=m.slice(0,8);r.textContent='';"
      "if(!m.length){var l=document.createElement('li');l.className='none';l.textContent='見つかりませんでした。別の言葉で試してください。';r.appendChild(l)}"
      "m.forEach(function(e){var l=document.createElement('li'),a=document.createElement('a'),t=document.createElement('b');a.href=base+e.u;t.textContent=e.t;a.appendChild(t);a.appendChild(document.createTextNode(e.n));"
      "if(e.s){var s=document.createElement('small');s.textContent=e.s;a.appendChild(s)}l.appendChild(a);r.appendChild(l)});r.hidden=false})}"
      "i.addEventListener('input',go);i.addEventListener('focus',function(){load(function(){})});"
      "i.addEventListener('keydown',function(e){if(e.key==='Enter'){var a=r.querySelector('a');if(a){location.href=a.href}}if(e.key==='Escape'){r.hidden=true}});"
      "document.addEventListener('click',function(e){if(!b.contains(e.target))r.hidden=true})})();</script>")


def sbar(base):
    """base：サイトのトップへの相対パス（'' / '../' / '../../'）。"""
    return (f"<!--sbar-->{CSS}<form class=sbar role=search onsubmit='return false' data-base='{base}'><label class=sr for=sq>サイト内検索</label>"
            f"<input id=sq type=search placeholder='商品名・マンガ名で探す（例：着る毛布、キングダム）' autocomplete=off enterkeyhint=search>"
            f"<ul class=sres hidden></ul>{JS}</form><!--/sbar-->")


def _title(t):
    m = re.search(r"<title>(.*?)</title>", t, re.S)
    return html.unescape(m.group(1)).split("｜")[0].strip() if m else ""


def build():
    """search-index.json を作る：[種類, 名前, URL（トップからの相対）, 補足]"""
    out = []
    for f in sorted(SITE.rglob("*.html")):
        rel = f.relative_to(SITE).as_posix()
        if rel.startswith(("bot/", "google")) or rel == "404.html":
            continue
        t = f.read_text(encoding="utf-8")
        if "<!--redirect-->" in t or "noindex" in t[:6000]:
            continue
        ttl = _title(t)
        if rel.startswith("manga/w/"):
            continue  # 作品は元データから
        if rel.startswith("articles/"):
            out.append(["比較記事", ttl, rel, ""])
            for m in re.finditer(r"<h2 id=item(\d+)\s*>\d+\.\s*(.*?)</h2>", t, re.S):
                nm = html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
                out.append(["商品", nm, f"{rel}#item{m.group(1)}", ttl.split("【")[0].split("｜")[0]])
        else:
            out.append(["ページ", ttl, rel if rel != "index.html" else "", ""])
    wp = HERE / "data" / "manga_works.json"
    if wp.exists():
        for w in json.loads(wp.read_text(encoding="utf-8")).values():
            out.append(["マンガ", w["title"], f"manga/w/{w['title_id']}.html", " ".join(w.get("aliases", []) + [w.get("author", "")])])
    np_ = HERE / "data" / "new_releases.json"
    if np_.exists():
        for e in json.loads(np_.read_text(encoding="utf-8"))["items"]:
            d = e["date"]
            out.append(["新刊", e["title"], f"manga/new-releases.html#n{e.get('isbn', '')}", f"{int(d[5:7])}/{int(d[8:])}発売 {e.get('author', '')}"])
    (SITE / "search-index.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(out)


if __name__ == "__main__":
    print("検索の一覧", build(), "件")
