"""マンガ専用サイト（site/manga/）を自動で作る。BookLiveのアフィリエイト（バリューコマース）。

- 元データ：data/manga_works.json（作品ごとの事実：title_id・題名・著者・受賞/メディア化・巻数・無料期限など）
  ＋ site/bot/out/threads_queue.json の BookLive 投稿（確認済みの作品・無料期限）から自動で取り込む。
- 毎日2本の記事（作品の基本情報ページ／テーマ別まとめ）を作る。体験談・感想・あらすじの転載はしない（事実と、短い一言の紹介だけ）。
- 出力：site/manga/index.html、site/manga/w/<title_id>.html、site/manga/theme/<slug>.html
- 使い方：python3 gen_manga.py [--n 2]
"""
import argparse
import datetime
import html
import json
import re
import sys
import urllib.parse
from pathlib import Path
from gen_search import sbar

HERE = Path(__file__).resolve().parent
SITE = HERE / "site"
OUT = SITE / "manga"
DATA = HERE / "data" / "manga_works.json"
QUEUE = SITE / "bot" / "out" / "threads_queue.json"
esc = html.escape
VC = "https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=3784510&pid=892746726&vc_url="

CSS = """:root{--bg:#f6f3ee;--fg:#1f1b16;--mut:#665d55;--line:#e6dfd5;--card:#fff;--acc:#c1272d;--acc2:#f59e0b}
@media (prefers-color-scheme:dark){:root{--bg:#17140f;--fg:#f5f0e8;--mut:#a89e92;--line:#3a342b;--card:#231f19;--acc:#ff6b6b;--acc2:#fbbf24}}
*{box-sizing:border-box}
.top{position:sticky;top:0;z-index:10;margin:0 -16px;padding:8px 16px;display:flex;align-items:center;justify-content:space-between;background:rgba(255,255,255,.95);border-bottom:1px solid var(--line)}

.logo{display:flex;align-items:center;gap:10px;text-decoration:none;font-weight:900;font-size:18px;letter-spacing:.02em;color:inherit!important}
.logo small{display:block;font-size:10px;font-weight:800;color:var(--mut);letter-spacing:.14em;line-height:1}
.top{flex-wrap:wrap;gap:6px 14px}.toplinks{display:flex;flex:1;justify-content:flex-end;align-items:center;gap:16px;white-space:nowrap;overflow-x:auto;scrollbar-width:none}.toplinks a{font-size:13px;font-weight:700;text-decoration:none;margin:0;color:var(--mut);padding:4px 0}.toplinks a:hover{color:#bf0000}.toplinks .sep{width:1px;height:14px;background:var(--line);flex:none}.toplinks a.shop{color:#bf0000}.toplinks a.shopbtn{flex:none;color:#fff;background:#bf0000;border-radius:99px;padding:5px 12px;font-weight:900;box-shadow:0 2px 0 rgba(0,0,0,.18)}.toplinks a.shopbtn:hover{color:#fff;background:#9a0000}@media (max-width:700px){.toplinks{order:3;flex-basis:100%;justify-content:space-between;gap:10px;border-top:1px solid var(--line);padding-top:4px}}
.top+.hero{margin-top:0}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.85 Meiryo,"メイリオ","Hiragino Sans","Hiragino Kaku Gothic ProN","Noto Sans JP",sans-serif}
main{max-width:780px;margin:auto;padding:0 16px 40px}
.hero{margin:0 -16px 18px;padding:28px 20px 22px;color:#fff;background:linear-gradient(135deg,var(--g1,#c1272d),var(--g2,#f59e0b))}
.hero h1{margin:6px 0 4px;font-size:25px;line-height:1.4;text-shadow:0 1px 3px rgba(0,0,0,.25)}
.hero p{margin:4px 0;font-size:14px;opacity:.95}
.kicker{display:inline-block;font-size:12px;font-weight:700;letter-spacing:.08em;background:rgba(255,255,255,.22);padding:2px 10px;border-radius:99px}
h1{font-size:23px;line-height:1.4} h2{font-size:19px;margin:1.9em 0 .6em;padding:2px 0 2px 12px;border-left:6px solid var(--acc);background:linear-gradient(90deg,rgba(193,39,45,.08),transparent)}
.pr{font-size:12px;color:var(--mut);border:1px solid var(--line);border-radius:8px;padding:6px 12px;background:var(--card);margin:12px 0}
.box{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 18px;margin:14px 0;box-shadow:0 2px 8px rgba(0,0,0,.05)}
.btn{display:inline-block;margin:6px 0;padding:12px 22px;border-radius:99px;background:linear-gradient(135deg,var(--acc),#e8590c);color:#fff!important;text-decoration:none;font-weight:700;box-shadow:0 3px 10px rgba(193,39,45,.35)}
.btn:hover{filter:brightness(1.08)}
.badge{display:inline-block;margin:2px 4px 2px 0;padding:2px 10px;border-radius:99px;font-size:12px;font-weight:700;background:var(--card);color:var(--acc);border:1px solid var(--acc)}
.free{display:inline-block;padding:3px 12px;border-radius:99px;font-size:13px;font-weight:800;background:#15803d;color:#fff}
.left{display:inline-block;padding:3px 12px;border-radius:99px;font-size:13px;font-weight:800;background:var(--acc2);color:#1f1b16}
.stars{color:#b45309;font-weight:800}@media (prefers-color-scheme:dark){.stars{color:var(--acc2)}}
.chars{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px}
.chars div{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 14px}
.chars b{display:block;color:var(--acc)}
.ch img{width:100%;max-width:150px;border-radius:6px;box-shadow:0 3px 10px rgba(0,0,0,.25);display:block;margin:0 auto 4px}.ch .note{display:block;text-align:center;margin-bottom:6px}
.chars{grid-template-columns:repeat(auto-fit,minmax(160px,1fr))!important}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}
.card{display:block;text-decoration:none;color:inherit;background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.05)}
.card .top{height:64px;background:linear-gradient(135deg,var(--g1),var(--g2))}
.card .in{padding:10px 14px 14px}.card b{font-size:16px}
.hero .wrap{display:flex;gap:18px;align-items:flex-end}.hero .cv{flex:0 0 auto}
.hero .cv img{width:132px;border-radius:6px;box-shadow:0 6px 18px rgba(0,0,0,.35);display:block}
.vols{display:flex;gap:10px;overflow-x:auto;padding:4px 0}.vols a{flex:0 0 auto;text-align:center;font-size:12px;text-decoration:none}
.vols img{width:96px;border-radius:5px;box-shadow:0 2px 8px rgba(0,0,0,.2);display:block;margin-bottom:4px}
.card .thumb{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;padding:10px;background:linear-gradient(135deg,var(--g1),var(--g2))}
.card .thumb img{width:100%;height:auto;aspect-ratio:12/17;object-fit:cover;border-radius:5px;box-shadow:0 3px 10px rgba(0,0,0,.3);display:block}.card .thumb img:first-child{outline:2px solid #fff}
.card .in{padding-top:12px}.boxcv{float:left;margin:0 14px 6px 0}.boxcv img{width:84px;border-radius:5px;box-shadow:0 2px 8px rgba(0,0,0,.2)}
.box:after{content:"";display:block;clear:both}
@media (max-width:520px){.hero .cv img{width:104px}}
.bar{display:flex;align-items:center;gap:8px;font-size:13px}.bar span{width:2.6em;color:var(--mut)}.bar i{display:block;height:10px;border-radius:99px;background:linear-gradient(90deg,var(--acc2),var(--acc));min-width:2px}.bar em{font-style:normal;color:var(--mut)}
.rvs{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}.rv{background:var(--card);border:1px solid var(--line);border-left:5px solid var(--acc2);border-radius:12px;padding:10px 14px}.rv p{margin:4px 0;font-size:14px}
.note{font-size:13px;color:var(--mut)} a{color:inherit} table{width:100%;border-collapse:collapse} th,td{border-bottom:1px solid var(--line);padding:8px;text-align:left;vertical-align:top} th{white-space:nowrap;color:var(--mut);width:7em}"""

PAL=[("#c1272d","#f59e0b"),("#0f766e","#38bdf8"),("#7c3aed","#f472b6"),("#1d4ed8","#22d3ee"),("#b45309","#facc15"),("#be185d","#fb923c")]


LOGO = ("<svg viewBox='0 0 32 32' aria-hidden=true><defs><linearGradient id=lg x1=0 y1=0 x2=1 y2=1><stop offset=0 stop-color='#c1272d'/><stop offset=1 stop-color='#f59e0b'/></linearGradient></defs>"
        "<rect x=2 y=3 width=28 height=26 rx=7 fill='url(#lg)'/><path d='M8 10h7v12H8z' fill='#fff' opacity=.95/><path d='M17 10h7v12h-7z' fill='#fff' opacity=.75/>"
        "<path d='M16 9v14' stroke='#7a1d1d' stroke-width=1.4/><circle cx=24.5 cy=8 r=3.2 fill='#ffd400' stroke='#fff' stroke-width=1.2/></svg>")


def grad(tid):
    g1,g2=PAL[int(re.sub(r'\D', '', str(tid)) or 0)%len(PAL)]
    return f"--g1:{g1};--g2:{g2}"


def left_days(w):
    fu=w.get("free_until")
    if not fu:
        return None
    d=(datetime.date.fromisoformat(fu)-datetime.date.today()).days
    return d if d>=0 else None


def page(title, desc, body, depth=0, style="", head=""):
    up = "../" * depth
    return (f"<!doctype html><html lang=ja><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{esc(title)}</title><meta name=description content=\"{esc(desc)}\">{head}<style>{CSS}</style></head><body><main style='{style}'>"
            f"<header class=top><a class=logo href='{up}index.html' aria-label='マンガトップへ'><img src='{up}../img/brand/logo_v8.png' width=40 height=40 alt=''><span><small>YAMANOTE MANGA</small>やまのてマンガ</span></a>"
            f"<nav class=toplinks><a href='{up}index.html'>作品</a><a href='{up}theme/free-now.html'>無料</a><a href='{up}new-releases.html'>新刊</a><a href='{up}store-compare.html'>ストア比較</a><a href='{up}faq.html'>Q&amp;A</a><span class=sep></span><a class=shopbtn href='{up}../index.html' aria-label='物販（楽天・Yahoo!・Amazonの実質最安）へ'>🛒 物販</a></nav><span class=sico style=\'display:inline-flex;gap:5px;align-items:center;margin-left:10px;flex:none\'><a href=\'https://x.com/totalyamanote\' rel=noopener target=_blank aria-label=\'Xでフォロー\' title=\'Xでフォロー\' style=\'display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;background:#111;color:#fff;font-size:13px;font-weight:900;text-decoration:none;line-height:1\'>𝕏</a><a href=\'https://www.threads.com/@totalyamanote\' rel=noopener target=_blank aria-label=\'Threadsでフォロー\' title=\'Threadsでフォロー\' style=\'display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;background:#000;color:#fff;font-size:13px;font-weight:900;text-decoration:none;line-height:1\'>@</a><a href=\'https://bsky.app/profile/totalyamanote.bsky.social\' rel=noopener target=_blank aria-label=\'Blueskyでフォロー\' title=\'Blueskyでフォロー\' style=\'display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;background:#0a66d1;color:#fff;font-size:13px;font-weight:900;text-decoration:none;line-height:1\'>🦋</a></span></header>"
            f"{sbar(up + '../')}"
            f"<p class=pr>PR｜このサイトはアフィリエイト広告（バリューコマース）を利用しています。</p>"
            f"{body}"
            f"<p class=note style='font-size:12px'>更新日：{datetime.date.today().isoformat()}（無料の期限・新刊・評価は毎朝更新）　文：やまのて編集部</p>"
            f"<p class=note><a href='{up}index.html'>マンガトップ</a>　<a href='{up}theme/free-now.html'>いま無料で読めるマンガ</a>　<a href='{up}theme/adapted.html'>アニメ化・ドラマ化されたマンガ</a>　<a href='{up}theme/always-free.html'>いつでも無料で読めるマンガ</a>　<a href='{up}new-releases.html'>新刊カレンダー</a>　<a href='{up}store-compare.html'>電子書籍ストア比較</a>　<a href='{up}faq.html'>よくある質問</a>　<a href='{up}../index.html'>やまのて（価格・ポイントまとめ）</a></p>"
            f"<footer style='margin:30px 0 8px;padding-top:14px;border-top:1px solid var(--line);font-size:12px;color:var(--mut);text-align:center'>"
            f"<a href='{up}../about.html'>運営者情報</a>　<a href='{up}../privacy.html'>プライバシーポリシー・免責事項</a>　<a href='https://x.com/totalyamanote' rel=noopener target=_blank>お問い合わせ（X）</a><br>© やまのて編集部</footer></main></body></html>")


def link(tid, vol="001"):
    return VC + urllib.parse.quote(f"https://booklive.jp/product/index/title_id/{tid}/vol_no/{vol}", safe="")


def real_id(tid):
    """キャンペーン用のtitle_idを、表紙画像に使う本来のtitle_idに変換（リダイレクト先）。"""
    import urllib.request
    try:
        req = urllib.request.Request(f"https://booklive.jp/product/index/title_id/{tid}/vol_no/001", method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            m = re.search(r"title_id/(\d+)/", r.geturl())
            return m.group(1) if m else tid
    except Exception:
        return None


def cover(w, vol="001", size="2L"):
    rid = w.get("real_id")
    if rid:
        return f"https://res.booklive.jp/{rid}/{vol}/thumbnail/{size}.jpg"
    return (w.get("covers") or {}).get(str(int(vol)), "")  # ebookjapan等の作品：楽天ブックスの表紙画像


def wlink(w, vol="001"):
    """作品の「読む」リンク。ebookjapanの無料作品は無料で読めるページ（報酬なし）、それ以外はブックライブ（報酬あり）。"""
    if w.get("store") in ("ebookjapan", "kindle"):
        return w.get("free_url", "")
    return link(w["title_id"], vol)


def free_now(w):
    """いま無料か（期限つき・または期限の表示がないキャンペーン中）。"""
    return left_days(w) is not None or bool(w.get("free_ongoing"))


def list_ld(name, url, ws):
    """一覧ページの構造化データ（CollectionPage＋作品のItemList）。"""
    d = {"@context": "https://schema.org", "@type": "CollectionPage", "name": name, "url": url, "inLanguage": "ja",
         "isPartOf": {"@type": "WebSite", "name": "やまのてマンガ", "url": "https://totalyamanote.github.io/manga/"},
         "mainEntity": {"@type": "ItemList", "numberOfItems": len(ws), "itemListElement": [
             {"@type": "ListItem", "position": i, "url": f"https://totalyamanote.github.io/manga/w/{w['title_id']}.html", "name": f"『{w['title']}』"}
             for i, w in enumerate(ws, 1)]}}
    return "<script type=application/ld+json>" + json.dumps(d, ensure_ascii=False) + "</script>"


def always_free_page():
    """期限の表示がない無料マンガ（いつでも読める）：data/always_free.json（ストアの無料一覧で確認・紹介文は要約）"""
    p = HERE / "data" / "always_free.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    ws = sorted(d["works"], key=lambda w: (-int(w["free"] or 0), -float(w["rating"] or 0)))
    ck = datetime.date.fromisoformat(d["checked"])
    cards = ""
    for w in ws:
        u = VC + urllib.parse.quote(f"https://booklive.jp/product/index/title_id/{w['id']}/vol_no/001", safe="")
        rt = f"<span class=stars>★{esc(w['rating'])}</span>（{esc(w['reviews'])}件）　" if w.get("rating") else ""
        cards += (f"<div class=box style='{grad(w['id'])};border-top:6px solid var(--g1)'>"
                  f"<a class=boxcv href=\"{esc(u)}\" rel=\"nofollow sponsored\"><img src='https://res.booklive.jp/{w['id']}/001/thumbnail/M.jpg' alt='『{esc(w['title'])}』の表紙' loading=lazy></a>"
                  f"<p><b style='font-size:17px'>『{esc(w['title'])}』</b></p><p class=note>{rt}{esc(w['author'])}</p>"
                  f"<p><span class=free>{esc(w['free'])}冊無料</span> <span class=badge>{esc(w['genre'])}</span></p><p>{esc(w['summary'])}</p>"
                  f"<p><a class=btn href=\"{esc(u)}\" rel=\"nofollow sponsored\" aria-label=\"『{esc(w['title'])}』を無料で読む\">無料で読む（ブックライブ）</a></p></div>")
    # 人気作の1巻（Kindleの無料サンプルでいつでも試し読みできる）を上に（2026-11-14 坂田さん「人気作品で固めて」）
    pt = HERE / "data" / "popular_trial.json"
    pop = json.loads(pt.read_text(encoding="utf-8"))["works"] if pt.exists() else []
    tag = json.loads((HERE / "config.json").read_text(encoding="utf-8")).get("amazon_tag", "")
    pcards = ""
    for w in pop:
        u = f"https://www.amazon.co.jp/dp/{w['kindle_asin']}?tag={tag}"
        pcards += (f"<div class=box style='{grad(w['isbn'])};border-top:6px solid var(--g1)'>"
                   f"<a class=boxcv href='{esc(u)}' rel='sponsored nofollow noopener' target=_blank><img src='{esc(w['img'])}' alt='『{esc(w['series'])}』1巻の表紙' loading=lazy></a>"
                   f"<p><b style='font-size:17px'>『{esc(w['series'])}』</b></p><p class=note><span class=stars>★{esc(w['amz_rating'])}</span>（Amazonの評価 {esc(w['amz_reviews'])}件）　{esc(w['author'])}｜{esc(w['publisher'])}</p>"
                   f"<p>{esc(w['summary'])}</p>"
                   f"<p><a class=btn href='{esc(u)}' rel='sponsored nofollow noopener' target=_blank aria-label='『{esc(w['series'])}』1巻をKindleで試し読み'>1巻をKindleで無料で試し読み</a></p></div>")
    title = f"いつでも無料で読めるマンガ｜人気作{len(pop)}作品の1巻を試し読み（Kindle）"
    intro = (f"ブックライブの無料コーナーで、無料の期限が表示されていない{len(ws)}作品を集めました（{ck.month}/{ck.day}確認）。"
             "急がずに、自分のペースで読み始められる作品です。")
    intro = (f"『鬼滅の刃』『ONE PIECE』など人気作{len(pop)}作品の1巻は、Kindleの無料サンプルで、いつでも冒頭を試し読みできます。"
             f"続きが気になったら、そのまま購入できます（{ck.month}/{ck.day}確認）。")
    body = (f"<div class=hero><span class=kicker>まとめ</span><h1>いつでも無料で読めるマンガ</h1><p>{esc(intro)}</p></div>"
            + (f"<h2>人気作の1巻を、いつでも無料で試し読み（Kindle）</h2><p class=note>Kindleの作品ページの「無料サンプルを読む」から、冒頭をいつでも無料で読めます（読める範囲は作品ごとに違います）。"
               f"評価はAmazonのレビュー（{ck.month}/{ck.day}時点）。</p>{pcards}" if pcards else "")
            + f"<p class=note>期限つきで無料の作品は「<a href='free-now.html'>いま無料で読めるマンガ（期限が近い順）</a>」にまとめています。</p>"
            f"<p class=note>紹介文は、公式の作品紹介をもとに当サイトで要約しています。</p>")
    out = OUT / "theme" / "always-free.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "url": "https://totalyamanote.github.io/manga/theme/always-free.html",
          "mainEntity": {"@type": "ItemList", "numberOfItems": len(ws), "itemListElement": [
              {"@type": "ListItem", "position": i, "item": {"@type": "Book", "name": w["title"], "author": w["author"]}} for i, w in enumerate(ws, 1)]}}
    out.write_text(page(title, intro, body, 1, head="<script type=application/ld+json>" + json.dumps(ld, ensure_ascii=False) + "</script>"), encoding="utf-8")
    return ("always-free", "いつでも無料で読めるマンガ")


def load_works():
    works = json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else {}
    if QUEUE.exists():
        for e in json.loads(QUEUE.read_text(encoding="utf-8")):
            t = e["text"]
            m = re.search(r"title_id%2F(\d+)%2Fvol_no%2F(\d+)", t)
            if not m or "booklive" not in urllib.parse.unquote(t).lower():
                continue
            tid = m.group(1)
            title = re.search(r"『([^』]+)』", t)
            if not title:
                continue
            until = re.search(r"【(\d+)月(\d+)日", t)
            lines = [l.strip() for l in t.split("\n") if l.strip()]
            fact = ""
            for l in lines:
                if "『" in l and "｜" in l:
                    fact = l.split("｜", 1)[1]
            w = works.setdefault(tid, {"title_id": tid, "title": title.group(1)})
            if fact:
                w["fact"] = fact
            hook = next((l for l in lines[1:] if "『" not in l and "http" not in l and "▶" not in l and "【" not in l[:1]), "")
            if hook and "hook" not in w:
                w["hook"] = hook
            if until:
                y = datetime.date.today().year
                w["free_until"] = datetime.date(y, int(until.group(1)), int(until.group(2))).isoformat()
    for w in works.values():
        if not w.get("real_id"):
            rid = real_id(w["title_id"])
            if rid:
                w["real_id"] = rid
    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text(json.dumps(works, ensure_ascii=False, indent=1), encoding="utf-8")
    return works


def work_page(w, works=None):
    tid, title = w["title_id"], w["title"]
    today = datetime.date.today()
    rows = []
    if w.get("author"):
        rows.append(("著者", esc(w["author"])))
    if w.get("magazine"):
        rows.append(("掲載", esc(w["magazine"])))
    if w.get("period"):
        rows.append(("連載期間", esc(w["period"])))
    if w.get("volumes"):
        rows.append(("巻数", esc(w["volumes"])))
    if w.get("rating"):
        rows.append(("ストアの評価", f"<span class=stars>★{esc(w['rating'])}</span>（{esc(w['reviews'])}件）"))
    if w.get("fact"):
        rows.append(("メディア化・受賞", esc(w["fact"])))
    dl = left_days(w)
    free_badge = ""
    if dl is not None:
        d = datetime.date.fromisoformat(w["free_until"])
        free_badge = f"<span class=free>1巻 無料</span> <span class=left>{d.month}月{d.day}日（{'月火水木金土日'[d.weekday()]}）まで・あと{dl}日</span>"
    elif w.get("free_until"):
        # 期限が切れたあとも、紹介ページは残す。過去の事実（いつまで無料だったか）を載せ、次の無料に備える
        d = datetime.date.fromisoformat(w["free_until"])
        free_badge = f"<span class=badge>1巻無料のキャンペーンは{d.month}月{d.day}日に終了しました</span> <span class=note>次の無料キャンペーンが出たら、このページで知らせます</span>"
    buybox = ""
    if w.get("free_ongoing"):
        if dl is not None:
            _d = datetime.date.fromisoformat(w["free_until"])
            free_badge = f"<span class=free>{esc(w.get('free_label', '無料'))}</span> <span class=left>{_d.month}月{_d.day}日（{'月火水木金土日'[_d.weekday()]}）まで・あと{dl}日</span>"
        else:
            free_badge = f"<span class=free>{esc(w.get('free_label', '無料'))}</span> <span class=note>{esc(w.get('free_store_name', ''))}・キャンペーン中</span>"
        b = w.get("buy") or {}
        bv = b.get("vol")
        btns = ""
        if b.get("kindle"):
            btns += f"<a class='bb a' href='{esc(b['kindle'])}' rel='sponsored nofollow noopener' target=_blank>Kindle<small>{bv}巻を見る</small></a>"
        if b.get("ebj"):
            btns += f"<a class='bb e' href='{esc(b['ebj'])}' rel='sponsored nofollow noopener' target=_blank>ebookjapan<small>{bv}巻を見る</small></a>"
        if b.get("kobo"):
            btns += f"<a class='bb k' href='{esc(b['kobo'])}' rel='sponsored nofollow noopener' target=_blank>楽天Kobo<small>{bv}巻を見る</small></a>"
        buybox = ("<style>.fbox{background:var(--card,#fff);border:2px solid #15803d;border-radius:14px;padding:12px 16px;margin:14px 0}.fbox h2{margin-top:0}"
                  ".bbs{display:flex;flex-direction:column;gap:8px;margin:10px 0}.bb{display:flex;flex-direction:column;align-items:center;padding:12px;border-radius:12px;font-weight:900;font-size:17px;text-decoration:none;box-shadow:0 3px 0 rgba(0,0,0,.18)}"
                  ".bb small{font-size:12px;font-weight:700}.bb.a{background:#ff9900;color:#111!important}.bb.e{background:#d4002a;color:#fff!important}.bb.k{background:#bf0000;color:#fff!important}"
                  ".fl{display:block;text-align:center;border:2px solid #15803d;color:#15803d!important;font-weight:900;border-radius:12px;padding:10px;text-decoration:none}</style>"
                  f"<div class=fbox id=read><h2>まずは無料で読む</h2><p>{esc(w.get('free_store_name', ''))}で<b>{esc(w.get('free_label', ''))}</b>で読めます。{esc(w.get('free_note', ''))}</p>"
                  f"<a class=fl href='{esc(w.get('free_url', ''))}' rel='{'sponsored nofollow noopener' if w.get('store') == 'kindle' else 'noopener'}' target=_blank>{esc(w.get('free_store_name', ''))}で無料で読む ›</a>"
                  + ("<p class=note>※Amazonアソシエイトのリンクです。無料の本を読んでも料金はかかりません。</p></div>" if w.get('store') == 'kindle' else "<p class=note>※このリンクは広告ではありません（当サイトに報酬は発生しません）。</p></div>")
                  + (f"<div class=fbox id=buy style='border-color:#c2410c'><h2>続き（{bv}巻〜）を読む</h2><p>無料の続きは、好きなストアで読めます。</p><div class=bbs>{btns}</div>"
                     "<p class=note>価格・ポイントは各ストアの表示が最新です。</p></div>" if btns else ""))
    table = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in rows)
    tags = "".join(f"<span class=badge>{esc(t)}</span>" for t in w.get("tags", []))
    syn = f"<h2>あらすじ</h2><p>{esc(w['synopsis'])}</p>" if w.get("synopsis") else (f"<p>{esc(w['hook'])}</p>" if w.get("hook") else "")
    chars = ""
    if w.get("characters"):
        cs = []
        for c in w["characters"]:
            n, r, v = (list(c) + ["", ""])[:3]
            im = (f"<a href=\"{esc(VC + urllib.parse.quote(f'https://booklive.jp/product/index/title_id/{w.get(chr(114)+chr(101)+chr(97)+chr(108)+chr(95)+chr(105)+chr(100))}/vol_no/{v}', safe=''))}\" rel=\"nofollow sponsored\">"
                  f"<img src='{esc(cover(w, v, 'M'))}' alt='{esc(n)}が表紙の{int(v)}巻' loading=lazy></a><span class=note>{int(v)}巻の表紙</span>") if v and w.get("real_id") else (
                  f"<a href='#buy'><img src='{esc(cover(w, v))}' alt='{esc(n)}が表紙の{int(v)}巻' loading=lazy></a><span class=note>{int(v)}巻の表紙</span>" if v and w.get("covers") and cover(w, v) else "")
            cs.append(f"<div class=ch>{im}<b>{esc(n)}</b>{esc(r)}</div>")
        chars = "<h2>登場人物</h2><div class=chars>" + "".join(cs) + "</div>"
    nm = f"『{esc(title)}』"
    if w.get("free_ongoing"):
        a1 = f"はい。{w.get('free_store_name', '')}で{w.get('free_label', '')}で読めます（キャンペーン中・終了日はストアの表示を確認）。"
    elif dl is not None:
        dd = datetime.date.fromisoformat(w["free_until"])
        a1 = f"はい。{dd.month}月{dd.day}日（{'月火水木金土日'[dd.weekday()]}）まで、1巻が期間限定で無料です（配信ストアの表示）。期限を過ぎると有料に戻ります。"
    else:
        a1 = "いまは期間限定の無料キャンペーンは確認できていません。試し読み（冒頭の数ページ）は、作品ページから読めることが多いです。"
    qa = [(f"{nm}の漫画は無料で読める？", a1),
          ("全巻無料で読める？", "全巻が無料になる公式のキャンペーンは、確認できていません。無料の対象は、多くの場合1巻（または数話）です。"),
          ("無料で読めるサイトやアプリは安全？", "公式の電子書籍ストアの無料キャンペーンなら安心です。作品を無断で載せている違法サイトは、ウイルスなどの危険があり、作者にも収益が入らないため使わないでください。"),
          (f"{nm}は何巻まで出ている？", f"{esc(w.get('volumes', '作品ページで確認してください。'))}")]
    faq = "<h2>よくある質問</h2>" + "".join(f"<div class=box><p style='margin:0'><b>Q. {q}</b></p><p style='margin:6px 0 0'>A. {a}</p></div>" for q, a in qa)
    revh = ""
    rv = w.get("user_reviews")
    if rv:
        tot = sum(rv["dist"]) or 1
        bars = "".join(f"<div class=bar><span>★{5 - i}</span><i style='width:{n * 100 // tot}%'></i><em>{n:,}件</em></div>" for i, n in enumerate(rv["dist"]))
        tg = "".join(f"<span class=badge>＃{esc(t)}</span>" for t in rv.get("tags", []))
        cards = "".join(f"<div class=rv><b>「{esc(h)}」</b><p>{esc(b)}</p><span class=note>参考になった {n}人</span></div>" for h, b, n in rv.get("top", []))
        revh = (f"<h2>読者レビュー</h2><div class=box><p style='margin:0 0 6px'><span class=stars>★{esc(w.get('rating',''))}</span>（{esc(w.get('reviews',''))}件）</p>{bars}"
                f"<p style='margin:10px 0 0'>レビューに多い気持ち：{tg}</p></div><div class=rvs>{cards}</div>"
                f"<p class=note>ストアの購入者レビュー（参考になった数が多い順）を、当サイトで短く要約しました。{esc(rv.get('checked',''))}時点。</p>")
    rel = ""
    if works:
        others = [x for x in works.values() if x["title_id"] != tid][:4]
        rel = "<h2>ほかの作品</h2><div class=grid>" + "".join(
            f"<a class=card style='{grad(x['title_id'])}' href='{x['title_id']}.html'><div class=thumb>"
            + "".join(f"<img src='{esc(cover(x, v, 'M'))}' alt='『{esc(x['title'])}』{int(v)}巻の表紙' loading=lazy onerror=\"this.style.display='none'\">" for v in ("001", "002", "003", "004"))
            + f"</div><div class=in><b>『{esc(x['title'])}』</b><br><span class=note>" + (f"<span class=stars>★{esc(x['rating'])}</span> " if x.get("rating") else "") + f"{esc(x.get('author',''))}</span><br>"
            + (f"<span class=free>無料</span> <span class=left>あと{left_days(x)}日</span>" if left_days(x) is not None else "") + "</div></a>" for x in others) + "</div>"
    cv = cover(w)
    cvh = (f"<a class=cv href=\"{esc(wlink(w))}\" rel=\"{'noopener' if w.get('store') == 'ebookjapan' else 'nofollow sponsored'}\"><img src='{esc(cv)}' alt='『{esc(title)}』1巻の表紙' loading=eager></a>" if cv else "")
    vols = ""
    if w.get("covers") and not w.get("real_id"):
        ks = sorted((int(k) for k in w["covers"]))[:8]
        vols = (f"<h2>表紙ギャラリー</h2><div class=vols>" + "".join(f"<a href='#buy'><img src='{esc(w['covers'][str(k)])}' alt='{k}巻の表紙' loading=lazy>{k}巻</a>" for k in ks)
                + "</div><p class=note>表紙は楽天ブックスの書籍情報より。</p>")
    if w.get("real_id"):
        vols = "<h2>表紙ギャラリー（1〜8巻）</h2><div class=vols>" + "".join(
            f"<a href=\"{esc(VC + urllib.parse.quote(f'https://booklive.jp/product/index/title_id/{w[chr(114)+chr(101)+chr(97)+chr(108)+chr(95)+chr(105)+chr(100)]}/vol_no/{v}', safe=''))}\" rel=\"nofollow sponsored\"><img src='{esc(cover(w, v, 'M'))}' alt='{int(v)}巻の表紙' loading=lazy onerror=\"this.parentNode.style.display='none'\">{int(v)}巻</a>"
            for v in ("001", "002", "003", "004", "005", "006", "007", "008")) + "</div><p class=note>表紙を押すと、その巻のページが開きます。</p>"
    body = f"""<div class=hero style='{grad(tid)}'><div class=wrap>{cvh}<div><span class=kicker>マンガ情報</span><h1>『{esc(title)}』<small style='display:block;font-size:14px;font-weight:700;opacity:.92;margin-top:4px'>あらすじ・登場人物・連載期間{'と、無料で読める期間' if dl is not None else '・読者の声'}</small></h1><p>{esc(w.get('hook',''))}</p><p>{free_badge}</p></div></div></div>
<div>{tags}</div>
{buybox}
{syn}
<h2>基本情報</h2><div class=box><table>{table}</table></div>
{chars}
{revh}
<p class=note>❓ 無料で読める仕組み・全巻無料・安全な読み方などは「<a href='../faq.html'>よくある質問</a>」にまとめています。</p><p class=note>🏪 どのストアで読むとおトク？ → 「<a href='../store-compare.html'>電子書籍ストア比較（初回クーポン・ポイント還元）</a>」</p>
{vols}
{"<p style='text-align:center'><a class=btn href='#read'>無料で読む・続きを読む ↑</a></p>" if w.get("store") in ("ebookjapan", "kindle") else f"<p style='text-align:center'><a class=btn href=" + chr(34) + esc(link(tid)) + chr(34) + " rel=" + chr(34) + "nofollow sponsored" + chr(34) + ">1巻を見る" + ("（無料）" if dl is not None else "") + "</a></p>"}
<p class=note>無料の対象・期限、配信状況、価格は変わります。購入前に作品ページで確認してください。巻数・連載期間は{today.strftime('%Y/%m/%d')}時点の公開情報にもとづきます。あらすじ・人物紹介は、公式の紹介をもとにした要約です。</p>
{rel}"""
    p = OUT / "w" / f"{tid}.html"
    p.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://totalyamanote.github.io/manga/w/{tid}.html"
    book = {"@context": "https://schema.org", "@type": "Book", "name": title, "url": url, "inLanguage": "ja", "bookFormat": "https://schema.org/EBook"}
    if w.get("author"):
        book["author"] = [{"@type": "Person", "name": a.strip()} for a in w["author"].split("／")]
    if w.get("magazine"):
        book["publisher"] = {"@type": "Organization", "name": re.sub(r".*（(.+)）", lambda m: m.group(1), w["magazine"])}
    if cv:
        book["image"] = cv
    if w.get("tags"):
        book["genre"] = w["tags"][:5]
    bc = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "やまのて", "item": "https://totalyamanote.github.io/"},
        {"@type": "ListItem", "position": 2, "name": "やまのてマンガ", "item": "https://totalyamanote.github.io/manga/"},
        {"@type": "ListItem", "position": 3, "name": title, "item": url}]}
    head = ("<script type=application/ld+json>" + json.dumps(book, ensure_ascii=False) + "</script><script type=application/ld+json>" + json.dumps(bc, ensure_ascii=False) + "</script>"
            f"<link rel=canonical href='{url}'><meta property=og:type content=book><meta property=og:title content=\"『{esc(title)}』\"><meta property=og:image content='{esc(cv)}'>")
    al = "（" + "・".join(w["aliases"]) + "）" if w.get("aliases") else ""
    rt = f"★{w['rating']}（{w['reviews']}件）。" if w.get("rating") else ""
    hk = re.sub(r"[\U0001F000-\U0001FFFF\u2600-\u27BF\uFE0F]", "", w.get("hook") or "").strip().rstrip("。")
    if w.get("free_ongoing"):
        ptitle = f"『{title}』{w.get('free_label', '')}（{w.get('free_store_name', '')}）｜漫画を無料で読む方法・あらすじ"
        pdesc = f"『{title}』{al}は{w.get('free_store_name', '')}で{w.get('free_label', '')}（キャンペーン中）。{rt}{hk + ('' if hk[-1:] in '？！?!' else '。') if hk else ''}続きの巻を読めるストア、あらすじ・登場人物・読者の声もまとめています。"
    elif dl is not None:
        dd = datetime.date.fromisoformat(w["free_until"])
        # 検索結果（スマホは30字前後で切れる）で、期限が先に見えるように：作品名→期限→内容
        ptitle = f"『{title}』1巻無料は{dd.month}/{dd.day}まで｜漫画を無料で読む方法・あらすじ"
        pdesc = f"『{title}』{al}は1巻が{dd.month}/{dd.day}（{'月火水木金土日'[dd.weekday()]}）まで無料。{rt}{hk + ('' if hk[-1:] in '？！?!' else '。') if hk else ''}あらすじ・登場人物・連載期間・読者の声もまとめています。"
    else:
        ptitle = f"『{title}』漫画を無料で読む方法｜あらすじ・登場人物・連載期間"
        pdesc = f"『{title}』{al}の漫画を無料・おトクに読む方法。{rt}{hk + ('' if hk[-1:] in '？！?!' else '。') if hk else ''}あらすじ・登場人物・連載期間・読者の声もまとめています。"
    p.write_text(page(ptitle, pdesc, body, 1, head=head), encoding="utf-8")


def theme_pages(works):
    """テーマ別まとめ：無料期限が近い順／メディア化（作品紹介の表記に『アニメ化』『ドラマ化』『映画化』を含む）。"""
    today = datetime.date.today()
    made = []
    free = sorted([w for w in works.values() if w.get("free_until") and datetime.date.fromisoformat(w["free_until"]) >= today],
                  key=lambda w: w["free_until"]) + [w for w in works.values() if w.get("free_ongoing") and not w.get("free_until")]
    themes = [("free-now", "いま無料で読めるマンガ（期限が近い順）", free, "1巻が期間限定で無料になっている作品を、期限が近い順に並べました。")]
    adapt = [w for w in works.values() if re.search(r"アニメ化|ドラマ化|映画化|実写化", w.get("fact", ""))]
    if adapt:
        themes.append(("adapted", "アニメ化・ドラマ化・映画化されたマンガ（作品紹介の表記）", adapt, "作品紹介に、アニメ化・ドラマ化・映画化などの表記がある作品をまとめました。"))
    for slug, title, ws, intro in themes:
        if not ws:
            if slug == "free-now":  # 無料の作品がないときも、古い一覧を残さず、案内に切り替える
                p = OUT / "theme" / "free-now.html"
                p.parent.mkdir(parents=True, exist_ok=True)
                allw = sorted(works.values(), key=lambda w: w.get("rating") or "0", reverse=True)[:6]
                lst = "".join(f"<li><a href='../w/{w['title_id']}.html'>『{esc(w['title'])}』</a>（★{esc(w.get('rating', '—'))}）</li>" for w in allw)
                body = (f"<div class=hero><span class=kicker>まとめ</span><h1>いま無料で読めるマンガ</h1><p>いま1巻無料のキャンペーン中の作品は、ありません。新しい無料の作品が見つかり次第、毎朝このページに追加します。</p></div>"
                        f"<h2>評価の高い作品（あらすじ・登場人物）</h2><ul>{lst}</ul><p class=note>{today.strftime('%Y/%m/%d')}時点。<a href='../new-releases.html'>新刊カレンダー</a>・<a href='../store-compare.html'>ストア比較（初回クーポン）</a>もどうぞ。</p>")
                p.write_text(page("いま無料で読めるマンガ｜1巻無料の作品が出たらここに追加", "いま1巻無料のキャンペーン中のマンガは、ありません。新しい無料の作品は毎朝追加します。", body, 1), encoding="utf-8")
                made.append((slug, "いま無料で読めるマンガ"))
            continue
        names = "・".join(f"『{w['title']}』" for w in ws[:3]) + ("など" if len(ws) > 3 else "")
        if slug == "free-now":
            title = f"いま無料で読めるマンガ{len(ws)}作品【{today.month}/{today.day}更新】1巻無料の期限つき"
            intro = f"{names}、1巻が期間限定で無料の{len(ws)}作品を、期限が近い順に。あらすじ・評価つき。毎朝更新。"
        elif slug == "adapted":
            title = f"アニメ化・ドラマ化されたマンガ{len(ws)}作品｜原作を無料で読める期限・あらすじ"
            intro = f"{names}、作品紹介にアニメ化・ドラマ化・映画化の表記がある{len(ws)}作品。原作マンガの無料期限・あらすじつき。"
        cards = ""
        for w in ws:
            dl = left_days(w)
            fu = ""
            if dl is not None:
                d = datetime.date.fromisoformat(w["free_until"])
                fu = f"<p><span class=free>{esc(w.get('free_label', '1巻 無料'))}</span> <span class=left>{d.month}月{d.day}日まで・あと{dl}日</span></p>"
            elif w.get("free_ongoing"):
                fu = f"<p><span class=free>{esc(w.get('free_label', '無料'))}</span> <span class=note>{esc(w.get('free_store_name', ''))}・キャンペーン中</span></p>"
            ebj = w.get("store") in ("ebookjapan", "kindle")
            tg = "".join(f"<span class=badge>{esc(t)}</span>" for t in w.get("tags", [])[:4])
            rt = f"<span class=stars>★{esc(w['rating'])}</span>（{esc(w['reviews'])}件）　" if w.get("rating") else ""
            cv = cover(w, size="M")
            cvb = f"<a class=boxcv href=\"{esc('../w/' + w['title_id'] + '.html#read' if ebj else link(w['title_id']))}\" rel=\"{'noopener' if ebj else 'nofollow sponsored'}\"><img src='{esc(cv)}' alt='『{esc(w['title'])}』の表紙' loading=lazy></a>" if cv else ""
            cards += (f"<div class=box style='{grad(w['title_id'])};border-top:6px solid var(--g1)'>{cvb}<p><b style='font-size:18px'><a href='../w/{w['title_id']}.html'>『{esc(w['title'])}』</a></b></p>"
                      f"<p class=note>{rt}{esc(w.get('author',''))}</p>{fu}<div>{tg}</div>"
                      f"<p>{esc(w.get('hook',''))}</p>"
                      + (f"<p><a class=btn href='../w/{w['title_id']}.html#read' aria-label='『{esc(w['title'])}』を無料で読む・続きを読む'>無料で読む・続きを読む</a>" if ebj else f"<p><a class=btn href=\"{esc(link(w['title_id']))}\" rel=\"nofollow sponsored\" aria-label=\"『{esc(w['title'])}』1巻を見る\">1巻を見る</a>")
                      + f"　<a href='../w/{w['title_id']}.html'>あらすじ・登場人物</a></p></div>")
        body = (f"<div class=hero><span class=kicker>まとめ</span><h1>{esc(title)}</h1><p>{esc(intro)}</p></div>{cards}"
                f"<p class=note>{today.strftime('%Y/%m/%d')}時点。対象・期限は、配信ストアの表示のとおりです。</p>")
        p = OUT / "theme" / f"{slug}.html"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(page(title, intro, body, 1, head=list_ld(title, f"https://totalyamanote.github.io/manga/theme/{slug}.html", ws)), encoding="utf-8")
        made.append((slug, title))
    return made


def index(works, themes):
    today = datetime.date.today()
    def _tw(slug):
        if slug == "always-free":
            af = json.loads((HERE / "data" / "always_free.json").read_text(encoding="utf-8"))["works"][:4]
            return [{"real_id": w["id"], "title": w["title"]} for w in af]
        ws = sorted(works.values(), key=lambda w: (w.get("free_until") or "9999"))
        if slug == "adapted":
            ws = [w for w in ws if re.search(r"アニメ化|ドラマ化|映画化|実写化", w.get("fact", ""))]
        return [w for w in ws if w.get("real_id")][:4]
    themes = list(reversed(themes))  # まとめも新しく作った順（2026-11-14 坂田さん指定）
    lis = "".join(f"<a class=card style='{grad(str(i + 3))}' href='theme/{s}.html'><div class=thumb>"
                  + ("".join(f"<img src='{esc(w['img'])}' alt='『{esc(w['series'])}』の表紙' loading=lazy>" for w in json.loads((HERE / "data" / "popular_trial.json").read_text(encoding="utf-8"))["works"][:4])
                     if s == "always-free" and (HERE / "data" / "popular_trial.json").exists() else
                     "".join(f"<img src='{esc(cover(w, size='M'))}' alt='『{esc(w['title'])}』の表紙' loading=lazy>" for w in _tw(s)))
                  + f"</div><div class=in><b>{esc(t)}</b></div></a>" for i, (s, t) in enumerate(themes))
    cards = ""
    for _n, w in sorted(enumerate(works.values()), key=lambda t: (t[1].get("added", ""), t[0]), reverse=True):  # 作品一覧は新しく追加した順（2026-11-14 坂田さん指定）
        dl = left_days(w)
        fb = f"<span class=free>無料</span> <span class=left>あと{dl}日</span>" if dl is not None else (f"<span class=free>{esc(w.get('free_label', '無料'))}</span>" if w.get("free_ongoing") else "")
        rt = f"<span class=stars>★{esc(w['rating'])}</span> " if w.get("rating") else ""
        cards += (f"<a class=card style='{grad(w['title_id'])}' href='w/{w['title_id']}.html'><div class=thumb>" + "".join(f"<img src='{esc(cover(w, v, 'M'))}' alt='『{esc(w['title'])}』{int(v)}巻の表紙' loading=lazy onerror=\"this.style.display='none'\">" for v in ("001", "002", "003", "004")) + "</div>"
                  f"<div class=in><b>『{esc(w['title'])}』</b><br><span class=note>{rt}{esc(w.get('author',''))}</span><br>{fb}</div></a>")
    quick = ""
    # 新刊（今週・来週発売）：gen_newrel が作った data/new_releases.json から
    newrel = ""
    try:
        import gen_newrel as _nr
        _nd = json.loads(_nr.DATA.read_text(encoding="utf-8"))
        _today = datetime.date.today()
        _up = sorted([e for e in _nd["items"] if _today.isoformat() <= e["date"] <= (_today + datetime.timedelta(days=21)).isoformat() and ".gif" not in e["img"]],
                     key=lambda e: (e["date"], e["rank"]))[:10]
        if _up:
            newrel = ("<h2>まもなく発売の新刊（売れている作品から）</h2><style>" + _nr.CSS + "</style>"
                      "<div class=ngrid>" + "".join(_nr.card(e, _today) for e in _up) + "</div>"
                      "<p class=note>📅 1か月先までの新刊は「<a href='new-releases.html'>マンガ新刊の発売日カレンダー</a>」（毎朝更新）。</p>")
    except Exception as _e:
        print("トップの新刊欄なし", _e)
    for w in sorted(works.values(), key=lambda w: (w.get("free_until") or "9999")):
        dl = left_days(w)
        if dl is None:
            continue  # 期限が分からない無料は「いますぐ」に入れない
        if any(x is not w and x["title"] == w["title"] and (x.get("free_until") or "") > w["free_until"] for x in works.values()):
            continue  # 同じ作品が複数のストアで無料なら、期限の長いほうを残す
        dd = datetime.date.fromisoformat(w["free_until"]) if dl is not None else None
        img = cover(w, size="M")
        quick += (f"<div class=qcard><a href='w/{w['title_id']}.html' class=qimg>" + (f"<img src='{esc(img)}' alt='『{esc(w['title'])}』1巻の表紙' loading=lazy width=120 height=170>" if img else "") + "</a>"
                  f"<a href='w/{w['title_id']}.html' class=qt>『{esc(w['title'])}』</a>"
                  + (f"<span class=qd>{esc(w.get('free_label', '1巻無料'))} {dd.month}/{dd.day}まで<b>あと{dl}日</b></span>" if dd else f"<span class=qd>{esc(w.get('free_label', '無料'))}<b>{esc(w.get('free_store_name', ''))}</b></span>")
                  + (f"<a class=qbtn href='w/{w['title_id']}.html#read' aria-label='『{esc(w['title'])}』を無料で読む'>無料で読む ›</a></div>" if w.get("store") in ("ebookjapan", "kindle") else f"<a class=qbtn href=\"{esc(link(w['title_id']))}\" rel=\"nofollow sponsored\" aria-label=\"『{esc(w['title'])}』1巻を無料で読む\">無料で読む ›</a></div>"))
    QCSS = '<style>.qrow{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:12px;margin:10px 0 18px}.qcard{display:flex;flex-direction:column;gap:4px;background:var(--card,#fff);border:1px solid var(--line);border-radius:12px;padding:8px}.qimg img{width:100%;height:auto;aspect-ratio:12/17;object-fit:cover;border-radius:8px;display:block;box-shadow:0 2px 6px rgba(0,0,0,.12)}.qt{font-weight:800;font-size:13px;line-height:1.35;text-decoration:none;color:inherit}.qd{font-size:12px;color:var(--mut)}.qd b{display:inline-block;margin-left:4px;color:#bf0000}.qbtn{margin-top:auto;text-align:center;background:#c2410c;color:#fff!important;font-weight:800;font-size:13px;border-radius:99px;padding:7px 0;text-decoration:none}</style>'
    # 人気作の1巻（Kindleの無料試し読み）も混ぜる（2026-11-14 坂田さん「ブルーロックみたいなの」）
    ptq = ""
    _pt = HERE / "data" / "popular_trial.json"
    if _pt.exists():
        _tag = json.loads((HERE / "config.json").read_text(encoding="utf-8")).get("amazon_tag", "")
        _shown = {x["title"] for x in works.values() if free_now(x)}
        for w in json.loads(_pt.read_text(encoding="utf-8"))["works"]:
            if w["series"] in _shown:  # 期限つきで無料の作品と重ならないように
                continue
            u = f"https://www.amazon.co.jp/dp/{w['kindle_asin']}?tag={_tag}"
            ptq += (f"<div class=qcard><a href='{esc(u)}' rel='sponsored nofollow noopener' target=_blank class=qimg><img src='{esc(w['img'])}' alt='『{esc(w['series'])}』1巻の表紙' loading=lazy width=120 height=170></a>"
                    f"<a href='{esc(u)}' rel='sponsored nofollow noopener' target=_blank class=qt>『{esc(w['series'])}』</a>"
                    f"<span class=qd>1巻を試し読み<b>★{esc(w['amz_rating'])}</b></span>"
                    f"<a class=qbtn style='background:#ff9900;color:#111!important' href='{esc(u)}' rel='sponsored nofollow noopener' target=_blank aria-label='『{esc(w['series'])}』1巻をKindleで試し読み'>Kindleで読む ›</a></div>")
    # 2026-11-14 坂田さん：「いますぐ無料で読む」は期間限定（期限が分かるもの）だけ。鬼滅などの試し読みは入れない
    ptq = ""
    quick_block = (f"<h2>いますぐ無料で読む（期間限定・期限が近い順）</h2>{QCSS}<div class=qrow>{quick}</div>"
                   f"<p class=note>人気作の1巻をいつでも試し読みできる作品は「<a href='theme/always-free.html'>いつでも無料で読めるマンガ</a>」にまとめています。</p>" if quick else "<p class=note>いま1巻無料のキャンペーン中の作品はありません。新しい無料の作品は毎朝追加します（下は作品一覧です）。</p>")
    body = f"""<div style='margin:10px 0 14px'><h1 style='font-size:18px;font-weight:700;margin:0 0 4px;color:inherit'>無料で読める作品・期限つき</h1><p style='font-size:13px;color:#5f5f5f;margin:0'>マンガのあらすじ・登場人物・連載期間・読者の声・無料の期限をまとめています。</p></div>
{quick_block}{newrel}
<h2>作品一覧（{len(works)}作品・新しく追加した順）</h2><div class=grid>{cards}</div>
<h2>まとめ</h2><div class=grid>{lis}</div>
<p class=note>{today.strftime('%Y/%m/%d')}更新。</p>"""
    (OUT / "index.html").write_text(page("無料で読めるマンガ・期限つき｜あらすじ・登場人物・読者の声｜やまのてマンガ", (lambda fw: (f"いま1巻無料のマンガ{len(fw)}作品（" + "・".join(f"『{w['title']}』" for w in fw[:3]) + "など）と期限、" if fw else "マンガのあらすじ・登場人物・読者の声、") + "まもなく発売の新刊、電子書籍ストア比較。毎朝更新。")([w for w in sorted(works.values(), key=lambda w: (w.get("free_until") or "9999")) if left_days(w) is not None]), body, 0, head=list_ld("やまのてマンガ", "https://totalyamanote.github.io/manga/", sorted(works.values(), key=lambda w: (w.get("free_until") or "9999")))), encoding="utf-8")


def faq_page(works):
    today = datetime.date.today()
    qa = [
        ("マンガを無料で読む方法は？", "電子書籍ストアが期間限定で行う「1巻無料」「数話無料」のキャンペーンを使うのが、いちばん安全で確実です。作品ページの試し読み（冒頭の数ページ）も無料で読めます。"),
        ("無料はいつまで？", "期限は作品ごとに決まっていて、期限を過ぎると有料に戻ります。「いま無料で読めるマンガ（期限が近い順）」のページと、各作品ページで確認できます（配信ストアの表示どおり・毎日更新）。"),
        ("全巻無料で読める？", "全巻が無料になる公式のキャンペーンは、ほとんどありません。無料の対象は多くの場合1巻（または数話）です。続きはクーポンやポイント還元を使うと安く買えます。"),
        ("会員登録しないと読めない？", "ストアによっては、無料作品を会員登録なしで読めます。購入や続きを読むときは会員登録（無料）が必要です。"),
        ("無料で読めるサイトやアプリは安全？", "公式の電子書籍ストアの無料キャンペーンなら安心です。作品を無断で載せている違法サイトは、ウイルスなどの危険があり、作者にも収益が入らないため使わないでください。"),
        ("何巻まで出ている？", "各作品ページの「基本情報」にまとめています（公開情報の時点つき）。"),
        ("無料で読んだあと、続きを安く買うには？", "ストアの毎日のクーポンや来店ポイント、セール期間を使うと安くなります。くわしくは「ブックライブの特徴と使い方」の記事で解説しています。"),
    ]
    qhtml = "".join(f"<div class=box><p style='margin:0'><b>Q. {esc(q)}</b></p><p style='margin:6px 0 0'>A. {esc(a)}</p></div>" for q, a in qa)
    faqld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in qa]}
    body = f"""<div class=hero style='--g1:#0f766e;--g2:#38bdf8'><span class=kicker>よくある質問</span><h1>マンガを無料で読むには？期限・全巻無料・安全な読み方のよくある質問</h1><p>無料で読める仕組みと注意点を、まとめて答えます。{today.strftime('%Y/%m/%d')}更新。</p></div>
<h2>よくある質問</h2>{qhtml}
<p class=note>関連：<a href='../articles/booklive-guide.html'>ブックライブの特徴と使い方</a>　<a href='theme/free-now.html'>いま無料で読めるマンガ（期限が近い順）</a></p>"""
    head = "<script type=application/ld+json>" + json.dumps(faqld, ensure_ascii=False) + "</script><link rel=canonical href='https://totalyamanote.github.io/manga/faq.html'>"
    (OUT / "faq.html").write_text(page("マンガを無料で読むには？期限・全巻無料・安全な読み方のよくある質問", "マンガを無料で読む方法、無料の期限、全巻無料はあるか、違法サイトの危険など、よくある質問にまとめて答えます。作品ごとの期限は「いま無料で読めるマンガ」へ。", body, 0, head=head), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2)
    ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    works = load_works()
    for w in works.values():
        work_page(w, works)
    themes = theme_pages(works)
    af = always_free_page()
    if af:
        themes.append(af)
    index(works, themes)
    faq_page(works)
    print(f"作品 {len(works)} 件・まとめ {len(themes)} 本・作品ページ {len(works)} 本を更新")
    try:
        import gen_search
        print("検索の一覧", gen_search.build(), "件")
    except Exception as e:
        print("検索の一覧 失敗", e)


if __name__ == "__main__":
    try:
        import gen_newrel
        gen_newrel.build()
    except Exception as e:
        print("新刊カレンダー失敗", e)
    main()
    try:
        import gen_ebookstores
        gen_ebookstores.build()
    except Exception as e:
        print("ストア比較失敗", e)
