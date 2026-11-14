"""トップ（site/index.html）を「軸」のハブにする後処理。run_daily.py が index.html を書いた後に実行する（何度実行しても同じ結果）。

- ロゴ付きの固定ヘッダー（セール／マンガ／比較記事／毎朝の最安）
- 上から：セール特集（イベント記事）→ マンガ（表紙カード）→ 比較記事（商品画像カード）→ 毎朝の実質最安（既存）
- 比較記事（site/articles/*.html）とセール日程ページにも同じヘッダーを入れる
- 使い方：python3 gen_hub.py
"""
import datetime
from gen_search import sbar
import html
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE / "site"
esc = html.escape

LOGO = ("<svg viewBox='0 0 32 32' width=30 height=30 aria-hidden=true><defs><linearGradient id=hl x1=0 y1=0 x2=1 y2=1><stop offset=0 stop-color='#bf0000'/><stop offset=1 stop-color='#f59e0b'/></linearGradient></defs>"
        "<rect x=2 y=3 width=28 height=26 rx=7 fill='url(#hl)'/><text x=16 y=22 text-anchor=middle font-size=15 font-weight=900 fill='#fff' font-family='Hiragino Sans,Meiryo,sans-serif'>実</text>"
        "<circle cx=25 cy=8 r=3.4 fill='#ffd400' stroke='#fff' stroke-width=1.2/></svg>")

CSS = """<style id=hubcss>
.hbar{position:sticky;top:0;z-index:20;display:flex;align-items:center;justify-content:space-between;gap:8px;margin:0 -16px 14px;padding:8px 16px;background:rgba(255,255,255,.93);background:rgba(255,255,255,.95);border-bottom:1px solid var(--line,#e7e5e4)}

.hlogo{display:flex;align-items:center;gap:10px;text-decoration:none;color:inherit;font-weight:900;font-size:19px}.hlogo small{display:block;font-size:10px;letter-spacing:.14em;color:var(--mut,#665d55);font-weight:800;line-height:1}
.hbar{flex-wrap:wrap;row-gap:6px}.hnav{display:flex;flex:1;justify-content:flex-end;gap:16px;overflow-x:auto;white-space:nowrap;scrollbar-width:none}@media (max-width:700px){.hnav{order:3;flex-basis:100%;justify-content:space-between;gap:10px;border-top:1px solid var(--line,#e7e5e4);padding-top:4px}}.hnav a{font-size:13px;font-weight:700;text-decoration:none;color:var(--mut,#665d55)}.hnav a.mgbtn{flex:none;color:#fff;background:#bf0000;border-radius:99px;padding:5px 12px;font-weight:900;box-shadow:0 2px 0 rgba(0,0,0,.18)}
.hhero{padding:2px 0 2px 12px;border-left:4px solid #ec6743;margin:4px 0 12px;color:inherit;background:none}
.hhero h1{margin:0;font-size:15px;line-height:1.5;font-weight:800}.hhero p{margin:2px 0 0;font-size:12px;color:var(--mut,#665d55)}
.hkick{display:none}
.hsec{margin:18px 0}.hsec>h2{font-size:18px;margin:0 0 8px;padding-left:10px;border-left:5px solid #bf0000;display:flex;justify-content:space-between;align-items:baseline}.hsec>h2 a{font-size:12px;font-weight:700;text-decoration:none;color:var(--mut,#665d55)}
.hsale{display:flex;gap:14px;align-items:center;text-decoration:none;color:#fff;border-radius:16px;padding:16px 18px;background:linear-gradient(135deg,#0b0b0b,#3b0a0a 55%,#bf0000);box-shadow:0 4px 14px rgba(0,0,0,.2)}
.hsale b{font-size:17px;line-height:1.4}.hsale .chips{margin-top:6px;display:flex;gap:6px;flex-wrap:wrap}.hsale .chip{font-size:11px;font-weight:800;border-radius:99px;padding:2px 9px;background:#fff;color:#bf0000}
.hrow{display:flex;gap:12px;overflow-x:auto;padding:4px 2px 10px;scroll-snap-type:x mandatory}
.hm{flex:0 0 132px;scroll-snap-align:start;text-decoration:none;color:inherit;text-align:center}
.hm img{width:132px;height:188px;object-fit:cover;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,.25);display:block}
.hm b{display:block;font-size:13px;line-height:1.35;margin-top:6px}.hm span{display:inline-block;margin-top:3px;font-size:11px;font-weight:800;border-radius:99px;padding:1px 8px;background:#15803d;color:#fff}
.hgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:12px}
.ha{display:flex;flex-direction:column;text-decoration:none;color:inherit;background:var(--card,#fff);border:1px solid var(--line,#e7e5e4);border-radius:14px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.06);transition:transform .15s}.ha:hover{transform:translateY(-2px)}
.ha img{width:100%;height:150px;object-fit:contain;background:#fff}.ha b{padding:8px 12px 12px;font-size:13px;line-height:1.45}
.ha .tag{margin:8px 12px 0;align-self:flex-start;font-size:11px;font-weight:800;color:#bf0000;border:1px solid #bf0000;border-radius:99px;padding:0 8px}
@media (max-width:480px){.hgrid{grid-template-columns:1fr 1fr}.hm{flex-basis:112px}.hm img{width:112px;height:160px}}
</style>"""


def header(up=""):
    return (f"<header class=hbar><a class=hlogo href='{up}index.html' aria-label='トップへ'><img src='{up}img/brand/logo_v8.png' width=42 height=42 alt=''><span><small>YAMANOTE</small>やまのて</span></a>"
            f"<nav class=hnav><a href='{up}articles/black-friday-2026.html'>セール</a>"
            f"<a href='{up}index.html#articles'>比較記事</a><a href='{up}index.html#daily'>毎朝の最安</a><a class=mgbtn href='{up}manga/index.html' aria-label='やまのてマンガ（無料で読めるマンガ）へ'>📚 マンガ</a></nav><span class=sico style=\'display:inline-flex;gap:5px;align-items:center;margin-left:10px;flex:none\'><a href=\'https://x.com/totalyamanote\' rel=noopener target=_blank aria-label=\'Xでフォロー\' title=\'Xでフォロー\' style=\'display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;background:#111;color:#fff;font-size:13px;font-weight:900;text-decoration:none;line-height:1\'>𝕏</a><a href=\'https://www.threads.com/@totalyamanote\' rel=noopener target=_blank aria-label=\'Threadsでフォロー\' title=\'Threadsでフォロー\' style=\'display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;background:#000;color:#fff;font-size:13px;font-weight:900;text-decoration:none;line-height:1\'>@</a><a href=\'https://bsky.app/profile/totalyamanote.bsky.social\' rel=noopener target=_blank aria-label=\'Blueskyでフォロー\' title=\'Blueskyでフォロー\' style=\'display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;background:#0a66d1;color:#fff;font-size:13px;font-weight:900;text-decoration:none;line-height:1\'>🦋</a></span></header>" + sbar(up))


def manga_row():
    p = HERE / "data" / "manga_works.json"
    if not p.exists():
        return ""
    today = datetime.date.today()
    ws = list(json.loads(p.read_text(encoding="utf-8")).values())
    ws.sort(key=lambda w: (w.get("free_until") or "9999"))
    out = ""
    for w in ws[:12]:
        img = f"https://res.booklive.jp/{w['real_id']}/001/thumbnail/M.jpg" if w.get("real_id") else (w.get("covers") or {}).get("1", "")
        if not img:
            continue
        fu = w.get("free_until")
        badge = ""
        if fu and datetime.date.fromisoformat(fu) >= today:
            d = datetime.date.fromisoformat(fu)
            badge = f"<span>{d.month}/{d.day}まで無料</span>"
        elif w.get("free_ongoing"):
            badge = f"<span>{esc(w.get('free_label', '無料'))}</span>"
        out += (f"<a class=hm href='manga/w/{w['title_id']}.html'><img src='{esc(img)}' alt='『{esc(w['title'])}』の表紙' loading=lazy>"
                f"<b>『{esc(w['title'])}』</b>{badge}</a>")
    return out


def manga_title():
    """無料中の作品がなければ、「いま無料で…」とは書かない（期限切れの後の見出し）。"""
    p = HERE / "data" / "manga_works.json"
    today = datetime.date.today().isoformat()
    free = p.exists() and any((w.get("free_until", "") >= today and w.get("real_id")) or w.get("free_ongoing") for w in json.loads(p.read_text(encoding="utf-8")).values())
    return "いま無料で読めるマンガ" if free else "人気マンガ（あらすじ・登場人物）"


def newrel_row():
    """マンガ新刊（まもなく発売・電子版のページへ）。元データ：data/new_releases.json（gen_newrel.py）"""
    p = HERE / "data" / "new_releases.json"
    if not p.exists():
        return ""
    today = datetime.date.today()
    its = [e for e in json.loads(p.read_text(encoding="utf-8"))["items"]
           if today.isoformat() <= e["date"] and ".gif" not in e["img"] and (e.get("kobo") or e.get("kindle") or e.get("ebj"))]
    its.sort(key=lambda e: (e["date"], e["rank"]))
    out = ""
    for e in its[:10]:
        d = datetime.date.fromisoformat(e["date"])
        u = e.get("kindle") or e.get("ebj") or e.get("kobo")
        out += (f"<a class=hm href='{esc(u)}' rel='sponsored nofollow noopener' target=_blank><img src='{esc(e['img'])}' alt='{esc(e['title'])}の表紙' loading=lazy>"
                f"<b>{esc(e['title'])}</b><span style='background:#bf0000'>{d.month}/{d.day}発売</span></a>")
    return out


def article_cards():
    # 並びは「記事を作った順（新しい順）」（2026-11-14 坂田さん指定）。登録簿（articles_generated.json）の日付と登録順で並べ、
    # 登録簿にない手書きの記事はそのあと。毎朝の更新でファイルの時刻がそろっても、新しい記事が先頭に来る。
    reg = json.loads((HERE / "data" / "articles_generated.json").read_text(encoding="utf-8")) if (HERE / "data" / "articles_generated.json").exists() else {}
    order = {k: (v.get("date", ""), i) for i, (k, v) in enumerate(reg.items())}
    arts = sorted((SITE / "articles").glob("*.html"), key=lambda f: (1, order[f.stem][0], order[f.stem][1]) if f.stem in order else (0, "", f.stat().st_mtime), reverse=True)
    out = ""
    for f in arts:
        if f.name == "black-friday-2026.html":
            continue
        t = f.read_text(encoding="utf-8") if f.exists() else ""
        if "<!--redirect-->" in t:
            continue
        m = re.search(r"<title>(.*?)</title>", t)
        im = next((m for m in re.finditer(r"<img src=['\"]?([^'\" >]+)", t) if "img/brand" not in m.group(1)), None)
        tag = "家電" if f.stem.startswith("electric") else ("まとめ" if f.stem == "point-up" else "比較")
        out += (f"<a class=ha href='articles/{f.name}'><span class=tag>{tag}</span>"
                + (f"<img src='{esc(im.group(1).replace('../', '', 1) if im.group(1).startswith('../') else im.group(1))}' alt='' loading=lazy>" if im else "")
                + f"<b>{esc(m.group(1) if m else f.stem)}</b></a>")
    return out


def hub_block():
    now = datetime.datetime.now()
    rak = (datetime.date(2026, 11, 19) - now.date()).days
    yah = (datetime.date(2026, 11, 22) - now.date()).days
    chips = []
    if rak >= 0:
        chips.append(f"楽天 11/19 20:00〜{'（あと' + str(rak) + '日）' if rak else '（今日から）'}")
    if yah >= 0:
        chips.append(f"Yahoo! 11/22〜{'（あと' + str(yah) + '日）' if yah else '（今日から）'}")
    chips.append("Amazon 日程発表待ち")
    sale = (f"<a class=hsale href='articles/black-friday-2026.html'><div style='font-size:40px'>🛍️</div><div><b>ブラックフライデー2026：3モールの日程と攻略、実質価格のおすすめ</b>"
            f"<div class=chips>{''.join(f'<span class=chip>{esc(c)}</span>' for c in chips)}</div></div></a>")
    return (f"<!--hub-->{CSS}{header()}"
            f"<p style='font-size:11px;color:var(--mut,#665d55);margin:2px 0 8px'>PR｜当サイトはアフィリエイト広告（楽天・Amazon・Yahoo!・A8.net・バリューコマース等）を利用しています。</p>"
            f"<div class=hhero><span class=hkick>毎日更新</span><h1>買う前に「実質いくら？」が分かる</h1>"
            f"<p>楽天・Yahoo!ショッピング・Amazonの価格−ポイント＝実質価格と、セール攻略・比較記事・無料で読めるマンガをまとめています。</p></div>"
            f"<div class=hsec><h2>🔥 セール特集</h2>{sale}</div>"
            f"<div class=hsec id=articles><h2>📝 比較記事・おすすめ</h2><div class=hgrid>{article_cards()}</div></div>"
            f"<h2 id=daily style='font-size:18px;margin:22px 0 6px;padding-left:10px;border-left:5px solid #bf0000'>🛒 毎朝の実質最安（楽天・Yahoo!）</h2><!--/hub-->")


def hub_manga():
    """トップの下（毎朝の実質最安の下）に置くマンガの段（2026-11-14 坂田さん指定）。"""
    return ("<!--hubm-->"
            f"<div class=hsec style='margin-top:28px'><h2>📚 {manga_title()} <a href='manga/index.html'>すべて見る →</a></h2><div class=hrow>{manga_row()}</div></div>"
            f"<div class=hsec><h2>📅 まもなく発売のマンガ新刊 <a href='manga/new-releases.html'>カレンダーを見る →</a></h2><div class=hrow>{newrel_row()}</div></div>"
            "<!--/hubm-->")


def apply_index():
    p = SITE / "index.html"
    t = p.read_text(encoding="utf-8")
    t = re.sub(r"<!--hub-->.*?<!--/hub-->", "", t, flags=re.S)
    # 旧：タイトル見出しと、比較記事の箇条書きは、ハブに置き換える
    t = re.sub(r"<main>\s*<h1>.*?</h1>", "<main>", t, count=1, flags=re.S)
    t = re.sub(r"<section><h2>比較記事（[^<]*）</h2><ul>.*?</ul></section>", "", t, flags=re.S)
    t = re.sub(r"<p class=pr>🛒 <a href='sale.html'>.*?</p>", "", t, count=1, flags=re.S)
    t = t.replace("<main>", "<main>" + hub_block(), 1)
    t = re.sub(r"<!--hubm-->.*?<!--/hubm-->", "", t, flags=re.S)
    i = t.find("<!--ftr-->")
    i = i if i >= 0 else t.rfind("</main>")
    t = t[:i] + hub_manga() + t[i:]
    p.write_text(t, encoding="utf-8")


def apply_pages():
    files = list((SITE / "articles").glob("*.html")) + [SITE / "sale.html", SITE / "recent.html", SITE / "booklive-free.html", SITE / "secondstreet.html", SITE / "about.html", SITE / "privacy.html"]
    n = 0
    for f in files:
        if not f.exists():
            continue
        up = "../" if f.parent.name == "articles" else ""
        t = f.read_text(encoding="utf-8") if f.exists() else ""
        if "<!--redirect-->" in t:
            continue
        t = re.sub(r"<!--hdr-->.*?<!--/hdr-->", "", t, flags=re.S)
        blk = f"<!--hdr-->{CSS}{header(up)}<!--/hdr-->"
        m = re.search(r"<main[^>]*>", t)
        if not m:
            continue
        t = t[:m.end()] + blk + t[m.end():]
        f.write_text(t, encoding="utf-8")
        n += 1
    return n




# ---------- 信頼の土台：運営者情報・ポリシー・フッター・構造化データ（2026-11-14 追加） ----------
BASE = "https://totalyamanote.github.io/"
ORG = {"@type": "Organization", "name": "やまのて編集部", "url": BASE, "logo": BASE + "img/brand/logo_400.png", "sameAs": ["https://x.com/totalyamanote", "https://www.threads.com/@totalyamanote"]}


def footer(up=""):
    return (f"<!--ftr--><footer style='margin:36px 0 10px;padding:16px 0;border-top:1px solid var(--line,#e7e5e4);font-size:12px;color:var(--mut,#665d55);text-align:center'>"
            f"<a href='{up}about.html'>運営者情報</a>　<a href='{up}privacy.html'>プライバシーポリシー・免責事項</a>　<a href='https://x.com/totalyamanote' rel=noopener target=_blank>お問い合わせ（X）</a>"
            f"<br>© {datetime.date.today().year} やまのて編集部　当サイトはアフィリエイト広告を利用しています。</footer><!--/ftr-->")


def jsonld(obj):
    return "<script type=application/ld+json>" + json.dumps(obj, ensure_ascii=False) + "</script>"


def article_ld(f, t):
    m = re.search(r"<title>(.*?)</title>", t)
    title = html.unescape(m.group(1)) if m else f.stem
    im = re.search(r"<img src=['\"]?(https?://[^'\" >]+)", t)
    mod = datetime.date.fromtimestamp(f.stat().st_mtime).isoformat()
    reg = HERE / "data" / "articles_generated.json"
    pub = mod
    if reg.exists():
        r = json.loads(reg.read_text(encoding="utf-8")).get(f.stem)
        if r and r.get("date"):
            pub = r["date"]
    url = BASE + "articles/" + f.name
    art = {"@context": "https://schema.org", "@type": "Article", "headline": title[:110], "datePublished": pub, "dateModified": mod,
           "author": ORG, "publisher": ORG, "mainEntityOfPage": url}
    if im:
        art["image"] = [im.group(1)]
    bc = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "やまのて", "item": BASE},
        {"@type": "ListItem", "position": 2, "name": "比較記事", "item": BASE + "index.html#articles"},
        {"@type": "ListItem", "position": 3, "name": title[:60], "item": url}]}
    og = (f"<meta property=og:type content=article><meta property=og:title content=\"{esc(title)}\"><meta property=og:url content='{url}'>"
          + (f"<meta property=og:image content='{esc(im.group(1))}'>" if im else "") + f"<link rel=canonical href='{url}'>")
    return og + jsonld(art) + jsonld(bc), mod


NOINDEX = {"sabon.html", "secondstreet.html", "recent.html", "booklive-free.html"}  # 薄い・重複ページは評価対象から外す（リンクはたどってもらう）


def apply_trust():
    n = 0
    files = [SITE / "index.html"] + list((SITE / "articles").glob("*.html")) + [SITE / x for x in ("sale.html", "recent.html", "booklive-free.html", "secondstreet.html", "sabon.html", "about.html", "privacy.html")]
    for f in files:
        if not f.exists():
            continue
        up = "../" if f.parent.name == "articles" else ""
        t = f.read_text(encoding="utf-8") if f.exists() else ""
        if "<!--redirect-->" in t:
            continue
        t = re.sub(r"<!--ftr-->.*?<!--/ftr-->", "", t, flags=re.S)
        t = re.sub(r"<!--ld-->.*?<!--/ld-->", "", t, flags=re.S)
        t = re.sub(r"<link rel=canonical[^>]*>", "", t)
        t = re.sub(r"<meta name=robots content=[^>]*>", "", t)
        if f.name in NOINDEX and f.parent == SITE:
            t = t.replace("</head>", "<meta name=robots content='noindex,follow'></head>", 1)
        t = t.replace("</main>", footer(up) + "</main>", 1)
        if f.parent.name == "articles":
            ld, mod = article_ld(f, t)
            t = t.replace("</head>", f"<!--ld-->{ld}<!--/ld--></head>", 1)
            # 見える「更新日」（無ければ見出しの下に入れる）
            t = re.sub(r"<!--upd-->.*?<!--/upd-->", "", t, flags=re.S)
            t = re.sub(r"(</h1>)", rf"\1<!--upd--><p class=note style='font-size:12px;color:#665d55'>更新日：{mod}　文：やまのて編集部（<a href='../about.html'>運営者情報</a>）</p><!--/upd-->", t, count=1)
        elif f.name == "index.html":
            ws = {"@context": "https://schema.org", "@type": "WebSite", "name": "やまのて", "url": BASE, "publisher": ORG,
                  "description": "楽天・Yahoo!ショッピング・Amazonの実質価格（価格−ポイント）、セール攻略、比較記事、無料で読めるマンガ・電子書籍の情報。"}
            t = t.replace("</head>", f"<!--ld-->{jsonld(ws)}<link rel=canonical href='{BASE}'><!--/ld--></head>", 1)
        f.write_text(t, encoding="utf-8")
        n += 1
    return n


STATIC_CSS = """<style>:root{--bg:#fafaf9;--fg:#1c1917;--mut:#665d55;--line:#e7e5e4;--card:#fff}@media (prefers-color-scheme:dark){:root{--bg:#1c1917;--fg:#f5f5f4;--mut:#a8a29e;--line:#44403c;--card:#292524}}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.9 Meiryo,"Hiragino Sans","Noto Sans JP",sans-serif}main{max-width:760px;margin:auto;padding:0 16px 30px}
h1{font-size:24px}h2{font-size:19px;margin-top:1.8em;padding-left:10px;border-left:5px solid #bf0000}.box{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 18px}a{color:inherit}</style>"""


STATIC_UPDATED = "2026-11-14"  # 運営者情報・プライバシー・比較のしかたは、中身を変えた日だけ書き換える（毎日変えると不自然）
SDESC = {"about.html": "やまのて（やまのて編集部）の運営者情報。楽天・Yahoo!・Amazonの実質価格比較と、マンガの無料期限・新刊情報をどう調べて載せているか、広告の方針とお問い合わせ先。",
         "privacy.html": "やまのてのプライバシーポリシーと免責事項。アフィリエイト広告・アクセス解析（Googleアナリティクス）とCookieの扱い、掲載情報の時点、表紙画像の著作権についての方針。",
         "compare-method.html": "やまのての比較記事の作り方。2つ以上のストアで同じ商品（JAN一致）だけを選び、実質価格・レビュー・その商品だけの強み・毎朝記録した価格の動きで比べる方法を説明します。"}


def write_static():
    today = datetime.date.today().isoformat()
    about = f"""<h1>運営者情報</h1><div class=box>
<p><b>サイト名：</b>やまのて（https://totalyamanote.github.io/）</p><p><b>運営：</b>やまのて編集部</p>
<p><b>お問い合わせ：</b>X（<a href='https://x.com/totalyamanote' rel=noopener target=_blank>@totalyamanote</a>）のDMで受け付けています。</p></div>
<h2>このサイトについて</h2><p>楽天市場・Yahoo!ショッピング・Amazonで買い物をする前に、「価格−ポイント＝実質いくらか」を確かめられるサイトです。セールの日程と攻略、日用品・家電などの比較記事、無料で読めるマンガ・電子書籍の情報をまとめています。</p>
<h2>情報の選び方・書き方の方針</h2><ul>
<li>価格・ポイント倍率・レビュー数は、各ショップの公開データ（楽天ウェブサービス等）から毎日取得し、取得した日時を記載しています。</li>
<li>商品は、レビュー数・評価・価格などの<b>数字の条件</b>で選んでいます（例：レビュー300件以上・評価4.3以上・9,800円以内）。</li>
<li>使っていない商品について、使ったような体験談は書きません。自分で使った商品の記事は、その旨を明記しています。</li>
<li>セールの日程は、公式発表・報道で確認できたものだけを載せ、未発表のものは「未発表」と書きます。</li>
<li>マンガのあらすじ・読者の声は、公式の紹介文や購入者レビューをもとに、当サイトで要約しています（引用・転載はしません）。</li>
<li>誤りに気づいた場合は、確認のうえ速やかに修正します。</li></ul>
<h2>広告について</h2><p>当サイトは、楽天アフィリエイト、Amazonアソシエイト、バリューコマース、A8.net、楽天リンクシェアなどのアフィリエイトプログラムに参加しています。リンク先で商品・サービスが購入・申し込みされると、当サイトに報酬が支払われることがあります。報酬の有無で、評価や順位を変えることはありません。</p>
<p>Amazonのアソシエイトとして、当サイトは適格販売により収入を得ています。</p><p style='font-size:12px;color:#665d55'>最終更新：{STATIC_UPDATED}</p>"""
    privacy = f"""<h1>プライバシーポリシー・免責事項</h1>
<h2>個人情報の取り扱い</h2><p>当サイトは、お問い合わせ（XのDM）でいただいた情報を、返信のためだけに使い、法令にもとづく場合を除き、第三者に提供しません。</p>
<h2>Cookie（クッキー）について</h2><p>当サイトに掲載している広告（楽天アフィリエイト、Amazonアソシエイト、バリューコマース、A8.net、楽天リンクシェア等）では、成果の計測のためにCookieが使われることがあります。Cookieは、ブラウザの設定で無効にできます。</p>
<h2>アクセス解析ツールについて</h2><p>当サイト（マンガのページを含む）は、Googleによるアクセス解析ツール「Googleアナリティクス」を利用しています。Googleアナリティクスはデータの収集のためにCookieを使用します。このデータは匿名で収集されており、個人を特定するものではありません。この機能はCookieを無効にすることで収集を拒否できます。詳しくは<a href='https://marketingplatform.google.com/about/analytics/terms/jp/' rel=noopener target=_blank>Googleアナリティクス利用規約</a>・<a href='https://policies.google.com/technologies/partner-sites?hl=ja' rel=noopener target=_blank>Googleのポリシーと規約</a>をご覧ください。オプトアウトは<a href='https://tools.google.com/dlpage/gaoptout?hl=ja' rel=noopener target=_blank>Googleアナリティクス オプトアウト アドオン</a>でも行えます。</p>
<h2>免責事項</h2><ul><li>価格・ポイント・在庫・セールの条件は、掲載した時点の情報です。変わることがあるので、購入前に各ショップのページで確認してください。</li>
<li>当サイトの情報で生じた損害について、責任を負いかねます。</li><li>リンク先のサイトの内容・サービスについては、各運営者にお問い合わせください。</li></ul>
<h2>著作権について</h2><p>マンガの表紙画像は、各配信ストアの公式画像を、作品ページへのリンクとして表示しています。権利者からの申し出があれば、速やかに対応します。</p>
<p style='font-size:12px;color:#665d55'>制定・最終更新：{STATIC_UPDATED}</p>"""
    method = f"""<h1>比較のしかた（商品の選び方・比べ方）</h1>
<p>やまのての比較記事が、どうやって商品を選び、何で比べているかをまとめます。すべての比較記事は、この方法で作っています。</p>
<h2>1. 候補の集め方</h2><ul>
<li>楽天市場・Yahoo!ショッピング・Amazonのうち、<b>2つ以上のストアで同じ商品（JANコードが一致）を売っているもの</b>から選びます。どのボタンを押しても、記事で紹介した商品そのものが表示されるようにするためです。</li>
<li>同じ商品かどうかは、Yahoo!ショッピングの商品のJANコードで楽天市場を検索し、同じ商品が出てくるかで確かめます。Amazonは商品ページでJANコードが一致するものだけを載せます。</li>
<li>価格は9,800円以内、レビュー50件以上・評価4.0以上を目安にしています。</li></ul>
<h2>2. 比べる項目</h2><ul>
<li><b>実質価格</b>：価格からもらえるポイントを引いた金額です（ポイントは条件で変わります）。</li>
<li><b>レビュー数・評価</b>：多くの人が選んでいるか、満足度が高いかの目安です。★ごとの件数（分布）も載せます。</li>
<li><b>その商品にしかない強み</b>：商品ページの仕様（サイズ・重さ・素材・機能・保証など）を読み比べ、ほかの候補にない点を書きます。</li>
<li><b>価格の動き</b>：当サイトでは比較記事の商品価格を毎朝記録しています。記録がたまった商品は、この30日の実質価格の幅と、いまが安いほうかどうかを載せます。</li></ul>
<h2>3. 読者の声のまとめ方</h2><ul>
<li>購入者のレビューを読み、よく書かれている点を当サイトの言葉で短く要約します（そのまま転載はしません）。確認した日付を記載します。</li>
<li>使っていない商品について、使ったような体験談は書きません。</li></ul>
<h2>4. 更新</h2><ul>
<li>価格・ポイント・レビュー数は毎朝更新します。商品の入れ替えは週1回見直します。</li>
<li>誤りに気づいた場合は、確認のうえ速やかに修正します。ご指摘はX（<a href='https://x.com/totalyamanote' rel=noopener target=_blank>@totalyamanote</a>）のDMへ。</li></ul>
<p>広告について：比較記事のボタンはアフィリエイトリンクです。報酬の有無や額で順位や評価を変えることはありません（<a href='about.html'>運営者情報</a>）。</p>
<p style='font-size:12px;color:#665d55'>最終更新：{STATIC_UPDATED}</p>"""
    for name, title, body in (("about.html", "運営者情報｜やまのて", about), ("privacy.html", "プライバシーポリシー・免責事項｜やまのて", privacy), ("compare-method.html", "比較のしかた（商品の選び方・比べ方）｜やまのて", method)):
        page = (f"<!doctype html><html lang=ja><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>{title}</title>"
                f"<meta name=description content='{SDESC.get(name, title)}'>{STATIC_CSS}</head><body><main>{body}</main></body></html>")
        (SITE / name).write_text(page, encoding="utf-8")


# ---------- Google向けの基本情報（全ページ共通・2026-11-14） ----------
def apply_basics():
    """全ページに：favicon／共有画像（OGP・Xカード）／正規URL／画像のalt／構造化データ（無いページだけ）"""
    n = 0
    for f in sorted(SITE.rglob("*.html")):
        rel = f.relative_to(SITE).as_posix()
        if rel.startswith(("bot/", "google")):
            continue
        t = f.read_text(encoding="utf-8") if f.exists() else ""
        if "<!--redirect-->" in t:
            continue
        o = t
        t = re.sub(r"<!--basic-->.*?<!--/basic-->", "", t, flags=re.S)
        url = BASE + ("" if rel == "index.html" else rel)
        m = re.search(r"<title>(.*?)</title>", t, flags=re.S)
        title = html.unescape(m.group(1)).strip() if m else "やまのて"
        d = re.search(r'<meta name=description content=["\']([^"\']*)', t)
        desc = html.unescape(d.group(1)) if d else ""
        b = ["<link rel=icon type=image/png href='/favicon.png'><link rel=apple-touch-icon href='/apple-touch-icon.png'>",
             "<meta name=twitter:card content=summary_large_image><meta name=twitter:site content='@totalyamanote'>"]
        if "og:title" not in t:
            b.append(f"<meta property=og:title content=\"{esc(title)}\"><meta property=og:type content=website>")
        if "og:site_name" not in t:
            b.append(f"<meta property=og:site_name content='{'やまのてマンガ' if rel.startswith('manga/') else 'やまのて'}'>")
        if "og:description" not in t and desc:
            b.append(f"<meta property=og:description content=\"{esc(desc)}\">")
        if "og:image" not in t:
            b.append(f"<meta property=og:image content='{BASE}img/brand/x_header.png'>")
        if "og:url" not in t:
            b.append(f"<meta property=og:url content='{url}'>")
        if "rel=canonical" not in t and "noindex" not in t[:6000]:
            b.append(f"<link rel=canonical href='{url}'>")
        if "ld+json" not in t and "noindex" not in t[:6000]:
            typ = "CollectionPage" if rel.startswith("manga/") and "/w/" not in rel else "WebPage"
            b.append(jsonld({"@context": "https://schema.org", "@type": typ, "name": title, "url": url, "description": desc, "publisher": ORG, "inLanguage": "ja"}))
        t = t.replace("</head>", "<!--basic-->" + "".join(b) + "<!--/basic--></head>", 1)
        # 画像のalt：カード内は商品名・記事名、ヘッダーのロゴは「やまのて」
        t = re.sub(r"(<img src='[^']*img/brand/logo_v\d+\.png'[^>]*?)alt=''", r"\1alt='やまのて'", t)
        t = re.sub(r"(<a class=['\"]?card[^>]*>(?:(?!</a>).)*?<img [^>]*?)alt=''((?:(?!</a>).)*?<span class=nm>)([^<]*)", lambda m: m.group(1) + "alt='" + m.group(3).replace("'", "") + "'" + m.group(2) + m.group(3), t, flags=re.S)
        t = re.sub(r"(<a class=ha [^>]*>(?:(?!</a>).)*?<img src='[^']*' )alt=''((?:(?!</a>).)*?<b>)([^<]*)", lambda m: m.group(1) + "alt='" + m.group(3).replace("'", "") + "'" + m.group(2) + m.group(3), t, flags=re.S)
        t = re.sub(r"(<a class=item [^>]*>(?:(?!</a>).)*?<img src='[^']*' )alt=''((?:(?!</a>).)*?<b>)([^<]*)", lambda m: m.group(1) + "alt='" + m.group(3).replace("'", "") + "'" + m.group(2) + m.group(3), t, flags=re.S)
        # 残りの alt='' は、直前の見出し（h2/h3/b）またはページ名で埋める
        if True:
            out, last = [], 0
            for mm in re.finditer(r"<img ([^>]*?)alt=''", t):
                before = t[:mm.start()]
                hs = re.findall(r"<(?:h2|h3)[^>]*>(.*?)</(?:h2|h3)>", before[-3000:], flags=re.S)
                bs = re.findall(r"<b>『?([^<]{2,40})", t[mm.end():mm.end() + 600])
                label = re.sub(r"<[^>]+>", "", (bs[0] if bs else (hs[-1] if hs else title))).strip().replace("'", "")[:60] or title
                out.append(t[last:mm.start()] + f"<img {mm.group(1)}alt='{label}'")
                last = mm.end()
            out.append(t[last:])
            t = "".join(out)
        if t != o:
            f.write_text(t, encoding="utf-8")
            n += 1
    return n


def write_404():
    body = f"""<div style='text-align:center;padding:40px 0'><img src='/img/brand/logo_400.png' width=140 height=140 alt='やまのて'><h1>ページが見つかりませんでした</h1>
<p>移動または削除された可能性があります。下のリンクからお探しください。</p>
<p><a href='/'>トップ（実質最安・セール・比較記事）</a>　<a href='/manga/'>やまのてマンガ</a>　<a href='/articles/black-friday-2026.html'>ブラックフライデー</a></p></div>"""
    (SITE / "404.html").write_text(f"<!doctype html><html lang=ja><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>ページが見つかりません｜やまのて</title><meta name=description content='お探しのページは見つかりませんでした。トップ・電子書籍・セール情報からお探しください。'><meta name=robots content='noindex'>{STATIC_CSS}</head><body><main>{body}</main></body></html>", encoding="utf-8")


ART_CSS = ("<style id=artcss>.bc{font-size:12px;color:var(--mut,#665d55);margin:6px 0 4px}.bc a{color:inherit}"
           ".toc{background:var(--card,#fff);border:1px solid var(--line,#e7e5e4);border-radius:12px;padding:10px 16px;margin:12px 0;font-size:14px}"
           ".toc b{display:block;margin-bottom:4px}.toc ol{margin:0;padding-left:1.4em}.toc a{text-decoration:none}"
           ".author{display:flex;gap:12px;align-items:center;background:var(--card,#fff);border:1px solid var(--line,#e7e5e4);border-radius:12px;padding:12px 16px;margin:24px 0 8px;font-size:13px}"
           ".author img{border-radius:50%}.author b{font-size:14px}</style>")


def apply_article_manners():
    """記事ページのお作法：見えるパンくず／目次（見出しへのジャンプ）／書いた人（運営方針へのリンク）"""
    n = 0
    targets = list((SITE / "articles").glob("*.html")) + list((SITE / "manga" / "w").glob("*.html"))
    for f in targets:
        t = f.read_text(encoding="utf-8") if f.exists() else ""
        if "<!--redirect-->" in t:
            continue
        o = t
        t = re.sub(r"<!--man-->.*?<!--/man-->", "", t, flags=re.S)
        t = re.sub(r"<style id=artcss>.*?</style>", "", t, flags=re.S)
        m = re.search(r"<title>(.*?)</title>", t, flags=re.S)
        title = html.unescape(m.group(1)).split("｜")[0].strip() if m else ""
        is_manga = f.parent.name == "w"
        if is_manga:
            wname = (title.split("』")[0] + "』") if "』" in title else title[:30]
            bc = f"<nav class=bc aria-label='パンくず'><a href='../../index.html'>トップ</a> › <a href='../index.html'>やまのてマンガ</a> › {esc(wname)}</nav>"
        else:
            bc = f"<nav class=bc aria-label='パンくず'><a href='../index.html'>トップ</a> › <a href='../index.html#articles'>比較記事</a> › {esc(title[:40])}</nav>"
        # 見出しにidを付けて目次を作る（記事のみ・見出し4つ以上）
        toc = ""
        if not is_manga:
            heads = []
            def addid(mm):
                attrs, txt = mm.group(1), mm.group(2)
                plain = re.sub(r"<[^>]+>", "", txt).strip()
                if plain in ("ほかの比較記事", "関連記事") or not plain:
                    return mm.group(0)
                hid = re.search(r"id=['\"]?([\w-]+)", attrs)
                hid = hid.group(1) if hid else f"s{len(heads) + 1}"
                heads.append((hid, plain))
                return f"<h2 id={hid}{re.sub(r'id=[^ >]+', '', attrs)}>{txt}</h2>"
            t = re.sub(r"<h2([^>]*)>(.*?)</h2>", addid, t, flags=re.S)
            if len(heads) >= 4:
                toc = "<nav class=toc aria-label='目次'><b>目次</b><ol>" + "".join(f"<li><a href='#{h}'>{esc(x[:50])}</a></li>" for h, x in heads) + "</ol></nav>"
        author = ("<div class=author><img src='../img/brand/logo_v8.png' width=44 height=44 alt='やまのて'>"
                  "<div><b>この記事を書いた人：やまのて編集部</b><br>価格・ポイント・レビューなど公開データをもとに、数字の条件で商品を選んでいます。使っていない商品の体験談は書きません。"
                  f"<a href='{'../../' if is_manga else '../'}about.html'>運営方針</a>" + ("" if is_manga else "・<a href='../compare-method.html'>比較のしかた</a>") + "</div></div>")
        if is_manga:
            author = author.replace("'../img/brand", "'../../img/brand")
        # 差し込み：パンくず＝main直後（ヘッダーの後）、目次＝h1の後の最初の段落群の後、書いた人＝フッター/関連記事の前
        t = t.replace("</head>", ART_CSS + "</head>", 1)
        mh = re.search(r"<!--/hdr-->|</header>", t)
        pos = mh.end() if mh else t.find("<main>") + 6
        t = t[:pos] + "<!--man-->" + bc + "<!--/man-->" + t[pos:]
        if toc:
            h1 = t.find("</h1>")
            nxt = t.find("<h2", h1)
            if h1 > 0 and nxt > 0:
                t = t[:nxt] + "<!--man-->" + toc + "<!--/man-->" + t[nxt:]
        anchor = min([i for i in (t.find("<!--related-->"), t.find("<!--ftr-->"), t.find("<footer")) if i > 0] or [t.rfind("</main>")])
        t = t[:anchor] + "<!--man-->" + author + "<!--/man-->" + t[anchor:]
        if t != o:
            f.write_text(t, encoding="utf-8"); n += 1
    return n


OTHER_BC = {
    "manga/index.html": [("トップ", "index.html"), ("やまのてマンガ", None)],
    "manga/faq.html": [("トップ", "index.html"), ("やまのてマンガ", "manga/index.html"), ("よくある質問", None)],
    "manga/theme/free-now.html": [("トップ", "index.html"), ("やまのてマンガ", "manga/index.html"), ("いま無料で読めるマンガ", None)],
    "manga/store-compare.html": [("トップ", "index.html"), ("やまのてマンガ", "manga/index.html"), ("電子書籍ストア比較", None)],
    "manga/new-releases.html": [("トップ", "index.html"), ("やまのてマンガ", "manga/index.html"), ("マンガ新刊の発売日カレンダー", None)],
    "manga/theme/always-free.html": [("トップ", "index.html"), ("やまのてマンガ", "manga/index.html"), ("いつでも無料で読めるマンガ", None)],
    "manga/theme/adapted.html": [("トップ", "index.html"), ("やまのてマンガ", "manga/index.html"), ("アニメ化・ドラマ化されたマンガ", None)],
    "sale.html": [("トップ", "index.html"), ("セール日程", None)],
    "about.html": [("トップ", "index.html"), ("運営者情報", None)],
    "privacy.html": [("トップ", "index.html"), ("プライバシーポリシー・免責事項", None)],
}


def apply_other_breadcrumbs():
    n = 0
    for rel, items in OTHER_BC.items():
        f = SITE / rel
        if not f.exists():
            continue
        t = f.read_text(encoding="utf-8") if f.exists() else ""
        if "<!--redirect-->" in t:
            continue
        o = t
        t = re.sub(r"<!--obc-->.*?<!--/obc-->", "", t, flags=re.S)
        depth = rel.count("/")
        up = "../" * depth
        vis = " › ".join((f"<a href='{up}{h}'>{esc(nm)}</a>" if h else esc(nm)) for nm, h in items)
        ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": nm, "item": BASE + (h if h else rel).replace("index.html", "") if (h or rel) else BASE}
            for i, (nm, h) in enumerate(items)]}
        extra = ""
        if rel == "sale.html":
            extra = f"<p style='font-size:12px;color:#665d55;margin:4px 0'>更新日：{datetime.date.fromtimestamp(f.stat().st_mtime).isoformat()}　文：やまのて編集部（<a href='about.html'>運営者情報</a>）</p>"
        blk = f"<!--obc--><nav class=bc aria-label='パンくず' style='font-size:12px;color:#665d55;margin:6px 0 4px'>{vis}</nav>{jsonld(ld)}<!--/obc-->"
        mh = re.search(r"<!--/hdr-->|</header>", t)
        pos = mh.end() if mh else t.find("<main>") + 6
        t = t[:pos] + blk + t[pos:]
        if extra:
            h1e = t.find("</h1>")
            if h1e > 0:
                t = t[:h1e + 5] + "<!--obc-->" + extra + "<!--/obc-->" + t[h1e + 5:]
        if t != o:
            f.write_text(t, encoding="utf-8"); n += 1
    return n


# ---------- 導線（2026-11-14）：楽天だけでなくYahoo!・Amazonも／古い記事に「すぐ見る」／セールページの上にボタン ----------
import urllib.parse as _up
_CFG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
def yahoo_search(q):
    return "https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=3784510&pid=892726197&vc_url=" + _up.quote("https://shopping.yahoo.co.jp/search?p=" + _up.quote(q), safe="")
def amazon_search(q):
    return f"https://www.amazon.co.jp/s?k={_up.quote(q)}&tag={_CFG.get('amazon_tag','')}"
def _query(name):
    q = re.sub(r"^\s*\d+\.\s*", "", name)
    q = re.sub(r"[（(【\[].*?[）)】\]]", " ", q)
    q = q.replace("｜", " ").replace("…", " ")
    words = [w for w in re.split(r"[\s　]+", q) if w]
    out = ""
    for w in words:
        if len(out) + len(w) > 28:
            break
        out += (" " if out else "") + w
    return out or q[:28]
FLOW_CSS = "<style id=flowcss>.hist{display:block;margin-top:4px;font-size:13px;font-weight:700;color:#0f766e}.hist small{display:block;font-weight:400;font-size:11px;color:#5f5f5f}.buybox{background:#fffaf5;border:1px solid #f3d9c4;border-radius:14px;padding:12px 14px 4px;margin:14px 0 22px}.bbh{margin:0 0 8px!important;font-weight:800;font-size:15px}.bbh span{display:block;font-weight:400;font-size:12px;color:#5f5f5f}.btns{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:8px 0 12px}.btns a{position:relative;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;min-height:62px;margin:0!important;padding:10px 26px 10px 12px!important;border-radius:12px!important;font-size:17px!important;font-weight:900!important;text-decoration:none!important;line-height:1.25;box-shadow:0 4px 0 rgba(0,0,0,.22);transition:transform .08s,filter .15s}.btns a:hover{filter:brightness(1.07)}.btns a:active{transform:translateY(3px);box-shadow:0 1px 0 rgba(0,0,0,.22)}.btns a:focus-visible{outline:3px solid #2563eb;outline-offset:2px}.btns a small{font-size:13px;font-weight:700;opacity:.95}.btns a small.pt{font-size:12px;font-weight:800;background:rgba(255,255,255,.22);border-radius:99px;padding:1px 8px}.btns a .sn{display:flex;align-items:center;gap:6px}.btns a em{font-style:normal;font-size:11px;background:#fff;color:#bf0000;border-radius:99px;padding:1px 7px}.btns .r{background:#bf0000!important;color:#fff!important}.btns .y{background:#d4002a!important;color:#fff!important}.btns .a{background:#ff9900!important;color:#111!important}.btns .a em{color:#b45309}.btns a:after{content:'›';position:absolute;right:12px;top:50%;transform:translateY(-55%);font-size:24px;font-weight:700}.mini{padding:7px 14px!important;font-size:13px!important}.quick{background:#fff7ed;border:1px solid #fdba74;border-radius:12px;padding:10px 16px;margin:12px 0}.quick b{display:block;margin-bottom:4px}.quick li{margin:3px 0}.quick a.go{font-weight:800;color:#bf0000}</style>"


def apply_flow():
    n = 0
    for f in sorted((SITE / "articles").glob("*.html")):
        t = f.read_text(encoding="utf-8") if f.exists() else ""
        if "<!--redirect-->" in t:
            continue
        o = t
        t = re.sub(r"<style id=flowcss>.*?</style>", "", t, flags=re.S)
        t = re.sub(r"<!--qk-->.*?<!--/qk-->", "", t, flags=re.S)
        t = re.sub(r"<!--ms-->.*?<!--/ms-->", "", t, flags=re.S)
        t = t.replace("</head>", FLOW_CSS + "</head>", 1)
        items = []
        def addbtn(mm):
            before = t[:mm.start()]
            hs = re.findall(r"<h2[^>]*>(.*?)</h2>", before[-6000:], flags=re.S)
            name = re.sub(r"<[^>]+>", "", hs[-1]).strip() if hs else ""
            blk = mm.group(0)
            if "hb.afl.rakuten" not in blk or not name:
                return blk
            rl = re.search(r"href='([^']+)'", blk).group(1)
            items.append((name, rl))
            return blk   # 検索リンクは付けない（同じ商品が出ないため）。3モールの直リンクは gen_articles が付ける
        t = re.sub(r"<p class=btns>.*?</p>", addbtn, t, flags=re.S)
        # 最初の購入ボタンが遅い記事（手書きの記事）には、上に「すぐ見る」を置く
        body = t[t.find("<body"):]
        plain = re.sub(r"<[^>]+>", "", body)
        first = body.find("hb.afl.rakuten")
        ratio = len(re.sub(r"<[^>]+>", "", body[:first])) / max(1, len(plain)) if first > 0 else 1
        if items and ratio > 0.3 and "<!--cmp-->" not in t:
            lis = "".join("<li>" + esc(re.sub(r"^\s*\d+\.\s*", "", nm)[:40]) + "　<a class=go href='" + esc(u) + "' rel='sponsored nofollow noopener' target=_blank>楽天で見る →</a></li>" for nm, u in items[:6])
            box = f"<!--qk--><div class=quick><b>この記事で紹介している商品（すぐ見る）</b><ul>{lis}</ul></div><!--/qk-->"
            pos = t.find("<nav class=toc")
            if pos < 0:
                pos = t.find("<h2")
            t = t[:pos] + box + t[pos:]
        if t != o:
            f.write_text(t, encoding="utf-8"); n += 1
    # セール日程ページ：上にお店のボタン
    f = SITE / "sale.html"
    if f.exists():
        t = f.read_text(encoding="utf-8"); t = re.sub(r"<!--salebtn-->.*?<!--/salebtn-->", "", t, flags=re.S)
        rak = f"https://hb.afl.rakuten.co.jp/hgc/{_CFG['affiliate_id']}/?pc=" + _up.quote("https://www.rakuten.co.jp/", safe="")
        yah = "https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=3784510&pid=892726197&vc_url=" + _up.quote("https://shopping.yahoo.co.jp/", safe="")
        amz = f"https://www.amazon.co.jp/blackfriday?tag={_CFG.get('amazon_tag', '')}"  # 検索結果ではなく公式のセール会場
        st = "display:inline-block;margin:4px 8px 4px 0;padding:9px 16px;border-radius:99px;font-weight:800;text-decoration:none;font-size:14px"
        btn = (f"<!--salebtn--><p><a style='{st};background:#bf0000;color:#fff' href='{esc(rak)}' rel='sponsored nofollow noopener' target=_blank>楽天市場を見る</a>"
               f"<a style='{st};background:#d4002a;color:#fff' href='{esc(yah)}' rel='sponsored nofollow noopener' target=_blank>Yahoo!ショッピングを見る</a>"
               f"<a style='{st};background:#ff9900;color:#111' href='{esc(amz)}' rel='sponsored nofollow noopener' target=_blank>Amazonを見る</a>"
               f"<a style='{st};background:#fff;color:#bf0000;border:2px solid #bf0000' href='articles/black-friday-2026.html'>ブラックフライデーのおすすめ →</a></p><!--/salebtn-->")
        h1e = t.find("</h1>")
        nxt = t.find("<h2", h1e)
        if h1e > 0 and nxt > 0:
            t = t[:nxt] + btn + t[nxt:]
            f.write_text(t, encoding="utf-8")
    return n


def run_all():
    write_static()
    apply_index()
    apply_pages()
    for nm in ("about.html", "privacy.html"):  # ヘッダーも入れる
        pass
    n = apply_trust()
    write_404()
    apply_article_manners()
    apply_other_breadcrumbs()
    apply_flow()
    apply_basics()
    try:  # GA4のタグ（全ページ）。site/bot/ga.py（クラウドと共通）
        import importlib.util
        _sp = importlib.util.spec_from_file_location("ga", SITE / "bot" / "ga.py")
        _ga = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(_ga); _ga.apply(str(SITE))
    except Exception as e:
        print("GA4タグを入れられず", e)
    return n


if __name__ == "__main__":
    print("trust", run_all(), "pages")
