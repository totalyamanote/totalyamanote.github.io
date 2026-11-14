"""全ページに Googleアナリティクス4（GA4）のタグを入れる（2026-11-14 坂田さん承認）。

何度実行しても同じ（<!--ga4-->〜<!--/ga4--> を入れ直すだけ）。生成スクリプトがページを作り直したあとに必ず通す。
- 手元：gen_hub.run_all() の最後
- クラウド：daily.yml・manga.yml の SEO点検の前
広告リンク（rel に sponsored を含むリンク）のクリックを `affiliate_click` イベント（店・リンク先・ページ）として送る。
使い方：python bot/ga.py [サイトのフォルダ（省略時はリポジトリ直下）]
"""
import glob
import os
import re
import sys
from pathlib import Path

GA_ID = "G-KMYVSH7X05"
SNIPPET = (
    "<!--ga4--><script async src=\"https://www.googletagmanager.com/gtag/js?id=" + GA_ID + "\"></script>"
    "<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}gtag('js',new Date());gtag('config','" + GA_ID + "');"
    "document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a[rel~=sponsored]');if(!a)return;var h=a.href,"
    "s=/rakuten/.test(h)?'楽天':/amazon\\.co\\.jp/.test(h)?'Amazon':/pid=892746726/.test(h)?'ブックライブ':/valuecommerce/.test(h)?'Yahoo!':/a8\\.net/.test(h)?'A8':'その他';"
    "gtag('event','affiliate_click',{store:s,link_url:h.slice(0,100),page_path:location.pathname})},true);</script><!--/ga4-->"
)
PAT = re.compile(r"<!--ga4-->.*?<!--/ga4-->", re.S)


def apply(root="."):
    n = 0
    files = glob.glob(os.path.join(root, "*.html")) + glob.glob(os.path.join(root, "articles", "*.html")) + glob.glob(os.path.join(root, "manga", "**", "*.html"), recursive=True)
    for p in files:
        if os.path.basename(p).startswith("google"):
            continue
        t = Path(p).read_text(encoding="utf-8")
        if "</head>" not in t:
            continue
        t2 = PAT.sub("", t).replace("</head>", SNIPPET + "</head>", 1)
        if t2 != t:
            Path(p).write_text(t2, encoding="utf-8")
            n += 1
    return n


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1])
    print("GA4タグ", apply(root), "ページ")
