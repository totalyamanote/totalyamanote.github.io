"""全ページに Googleアナリティクス4（GA4）のタグを入れる（2026-11-14 坂田さん承認）。

何度実行しても同じ（<!--ga4-->〜<!--/ga4--> を入れ直すだけ）。生成スクリプトがページを作り直したあとに必ず通す。
- 手元：gen_hub.run_all() の最後
- クラウド：daily.yml・manga.yml の SEO点検の前
広告リンク（rel に sponsored を含むリンク）のクリックを `affiliate_click` イベント（店・リンク先・ページ）として送る。
使い方：python bot/ga.py [サイトのフォルダ（省略時はリポジトリ直下）]
"""
import glob
import importlib.util
import os
import re
import sys
from pathlib import Path

GA_ID = "G-KMYVSH7X05"
SNIPPET = (
    "<!--ga4--><script async src=\"https://www.googletagmanager.com/gtag/js?id=" + GA_ID + "\"></script>"
    "<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}gtag('js',new Date());var g=/^\\/(game|fashion|video|manga|articles|compare|instagram)\\//.exec(location.pathname),cg=g?g[1]:'top';gtag('config','" + GA_ID + "',{content_group:cg});"
    "document.addEventListener('click',function(e){var t=e.target.closest?e.target:null;if(!t)return;var n=t.closest('a[href*=\\\"x.com/totalyamanote\\\"],a[href*=\\\"threads.com/@totalyamanote\\\"],a[href*=\\\"bsky.app/profile/totalyamanote\\\"],a[href*=\\\"instagram.com/totalyamanote\\\"]');"
    "if(n){gtag('event','sns_follow_click',{network:/x\\.com/.test(n.href)?'X':/threads/.test(n.href)?'Threads':/instagram/.test(n.href)?'Instagram':'Bluesky',page_path:location.pathname});return}"
    "var a=t.closest('a[rel~=sponsored]');if(!a)return;var h=a.href,sec=a.closest('section[id],div[id]'),"
    "s=/rakuten/.test(h)?'楽天':/amazon\\.co\\.jp/.test(h)?'Amazon':/pid=892746726/.test(h)?'ブックライブ':/valuecommerce/.test(h)?'Yahoo!':/a8mat=4BGK83\\+E39C6Q\\+4J34/.test(h)?'ゲオ':/a8\\.net/.test(h)?'A8':/linksynergy/.test(h)?'リンクシェア':'その他';"
    "var hs=document.querySelectorAll('h2,h3'),hd='',hid='';for(var i=0;i<hs.length;i++){if(hs[i].compareDocumentPosition(a)&4){hd=hs[i].textContent.trim().slice(0,40);if(hs[i].id)hid=hs[i].id}}"
    "var nm=a.querySelector('.zn,.nm,.pn'),br=a.querySelector('.zb'),rk=a.querySelector('.zrk,.rkn,.rkb'),it=(nm?nm.textContent:'').trim().slice(0,60);"
    "gtag('event','affiliate_click',{store:s,link_url:h.slice(0,100),page_path:location.pathname,section:sec&&sec.id?sec.id:hid,heading:hd,content_group:cg,item_title:it||document.title.split('｜')[0].slice(0,60),item_brand:br?br.textContent.trim().slice(0,40):'',rank:rk?rk.textContent.trim().slice(0,3):''})},true);</script><!--/ga4-->"
)
PAT = re.compile(r"<!--ga4-->.*?<!--/ga4-->", re.S)


def _ogcard():
    """リンク画像の差し替え（bot/ogcard.py）。"""
    spec = importlib.util.spec_from_file_location("ogcard", Path(__file__).resolve().parent / "ogcard.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def apply(root="."):
    n = 0
    og = _ogcard()
    files = glob.glob(os.path.join(root, "*.html")) + glob.glob(os.path.join(root, "articles", "*.html")) + glob.glob(os.path.join(root, "compare", "*.html")) + glob.glob(os.path.join(root, "video", "**", "*.html"), recursive=True) + glob.glob(os.path.join(root, "manga", "**", "*.html"), recursive=True) + glob.glob(os.path.join(root, "game", "**", "*.html"), recursive=True) + glob.glob(os.path.join(root, "fashion", "*.html")) + glob.glob(os.path.join(root, "furusato", "*.html")) + glob.glob(os.path.join(root, "instagram", "*.html"))
    for p in files:
        if os.path.basename(p).startswith("google"):
            continue
        t = Path(p).read_text(encoding="utf-8")
        if "</head>" not in t:
            continue
        t2 = og.swap(root, p, PAT.sub("", t).replace("</head>", SNIPPET + "</head>", 1))
        if t2 != t:
            Path(p).write_text(t2, encoding="utf-8")
            n += 1
    return n


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1])
    print("GA4タグ", apply(root), "ページ")
