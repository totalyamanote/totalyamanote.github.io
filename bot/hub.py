"""トップページの見た目（ヘッダー・ヒーロー→毎朝の最安→比較記事カード・セール特集→マンガの段・フッター）を固定する。

run_daily.py はトップを簡素なテンプレートで作り直すため、毎朝そのまま保存すると
見た目が「先祖返り」する。生成後にこのモジュールで、固定の部品を差し込み直す。
部品は直前の index.html にあればそれを引き継ぎ（手元ツールの更新を壊さない）、
無ければ bot/hub/ の保存版を使う。
"""
import json
import re
from datetime import datetime
from pathlib import Path

HUB = Path(__file__).resolve().parent / "hub"
KEYS = ("ld", "basic", "hub", "hubart", "hubm", "ftr")


def _split_old_hub(old):
    """旧形式（ハブの中に セール特集・比較記事 が入っていた）の index.html から、比較記事の段を切り出す。"""
    m = re.search(r"<!--hub-->.*?<!--/hub-->", old or "", re.S)
    if not m:
        return None, None
    h = m.group(0)
    sale = re.search(r"<div class=hsec><h2>🔥 セール特集</h2>.*?</a></div>", h, re.S)
    art = re.search(r"<div class=hsec id=articles>.*?</div></div>(?=<h2 id=daily)", h, re.S)
    if not (sale and art):
        return None, None
    new_hub = h.replace(sale.group(0), "").replace(art.group(0), "")
    arts = art.group(0).replace("<div class=hsec id=articles>", "<div class=hsec id=articles style='margin-top:28px'>", 1)
    return new_hub, "<!--hubart-->" + arts + sale.group(0) + "<!--/hubart-->"


def _block(k, old):
    if old and k in ("hub", "hubart") and "<!--hubart-->" not in old:
        nh, na = _split_old_hub(old)
        if nh:
            return nh if k == "hub" else na
    if old:
        m = re.search(rf"<!--{k}-->.*?<!--/{k}-->", old, re.S)
        if m:
            return m.group(0)
    return (HUB / f"{k}.html").read_text(encoding="utf-8")


def _refresh_countdown(s, now):
    """セール特集のチップ『（あとN日）』を今日の日付で数え直す。"""
    def f(m):
        try:
            d = datetime(now.year, int(m.group(2)), int(m.group(3)))
        except ValueError:
            return m.group(0)
        n = (d.date() - now.date()).days
        if n < 0:
            return m.group(0)
        return f"{m.group(1)}{m.group(2)}/{m.group(3)}{m.group(4)}（" + ("本日開始" if n == 0 else f"あと{n}日") + "）"
    return re.sub(r"(<span class=chip>[^<]*?)(\d+)/(\d+)([^<（]*?)（(?:あと\d+日|本日開始)）", f, s)


SALE_JSON = Path(__file__).resolve().parent / "data" / "sale_event.json"
SALE_CSS = ("<style id=hsalecss>"
 ".bf{position:relative;overflow:hidden;display:block;text-decoration:none;color:#fff;border-radius:18px;padding:22px 20px 20px;margin:4px 0 16px;"
 "background:radial-gradient(circle at 85% 10%,rgba(255,196,0,.35),transparent 45%),radial-gradient(circle at 10% 100%,rgba(191,0,0,.7),transparent 55%),linear-gradient(135deg,#000,#1c0505 60%,#4a0a0a);"
 "box-shadow:0 8px 24px rgba(0,0,0,.35);border:1px solid #5a1a1a}"
 ".bf svg.bfart{position:absolute;right:-6px;top:-6px;width:170px;height:170px;opacity:.95;pointer-events:none}"
 ".bf .k{display:inline-block;font-size:11px;font-weight:900;letter-spacing:.14em;color:#111;background:linear-gradient(90deg,#ffd54a,#ffb300);border-radius:99px;padding:2px 12px}"
 ".bf h2{margin:8px 0 2px;border:0;padding:0;font-size:32px;line-height:1.15;font-weight:900;letter-spacing:.02em;color:#fff;max-width:75%}"
 ".bf h2 em{font-style:normal;background:linear-gradient(90deg,#ffe082,#ffb300);-webkit-background-clip:text;background-clip:text;color:transparent}"
 ".bf p{margin:4px 0 12px;font-size:13px;color:#f1d9d9;max-width:80%}"
 ".bf .ml{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}"
 ".bf .m{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.2);border-radius:12px;padding:8px 10px;border-top:4px solid var(--mc)}"
 ".bf .m b{display:block;font-size:14px}.bf .m small{display:block;font-size:11px;color:#e8cfcf;margin:2px 0 4px}"
 ".bf .st{display:inline-block;font-size:11px;font-weight:900;border-radius:99px;padding:1px 9px;background:#fff;color:#bf0000}"
 ".bf .st.on{background:#ffd54a;color:#111}.bf .st.wait{background:#665d55;color:#fff}"
 ".bf .ph{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:2px 0 12px}"
 ".bf .ph i{display:block;aspect-ratio:1;border-radius:12px;background:#fff center/cover no-repeat;border:2px solid #ffd54a;box-shadow:0 4px 10px rgba(0,0,0,.45);transform:rotate(-2deg)}"
 ".bf .ph i:nth-child(even){transform:rotate(2deg) translateY(4px)}"
 ".bf .cap{font-size:11px;color:#e8cfcf;margin:-6px 0 10px}"
 ".bf .go{display:inline-block;margin-top:12px;background:linear-gradient(90deg,#ffd54a,#ffb300);color:#111;font-weight:900;font-size:15px;border-radius:99px;padding:10px 22px}"
 "@media(max-width:560px){.bf h2{font-size:24px;max-width:70%}.bf p{max-width:100%}.bf .ml{gap:6px}.bf .m{padding:6px 7px}.bf .m b{font-size:13px}.bf .m small{font-size:10px}.bf svg.bfart{width:104px;height:104px}}"
 "</style>")
SALE_ART = ("<svg class=bfart viewBox='0 0 120 120' aria-hidden=true><defs><linearGradient id=bfg x1=0 y1=0 x2=1 y2=1><stop offset=0 stop-color='#ffe082'/><stop offset=1 stop-color='#ff9800'/></linearGradient></defs>"
 "<path d='M30 44h60l7 62H23z' fill='url(#bfg)'/><path d='M44 44c0-20 32-20 32 0' fill=none stroke='#fff' stroke-width=6 stroke-linecap=round />"
 "<text x=60 y=88 text-anchor=middle font-size=30 font-weight=900 fill='#7a0000' font-family='sans-serif'>%</text>"
 "<g fill='#ffe082'><path d='M104 14l3 8 8 3-8 3-3 8-3-8-8-3 8-3z'/><path d='M16 22l2 5 5 2-5 2-2 5-2-5-5-2 5-2z'/><path d='M108 70l2 4 4 2-4 2-2 4-2-4-4-2 4-2z'/></g></svg>")


def _sale_cfg():
    try:
        return json.loads(SALE_JSON.read_text(encoding="utf-8"))
    except Exception:
        return None


def sale_active(now, cfg=None):
    """全モールの終了日を過ぎたら False（特集はセールが終わったら終了）。"""
    cfg = cfg or _sale_cfg()
    if not cfg:
        return False
    ends = [datetime.fromisoformat(m["end"]) for m in cfg["malls"] if m.get("end")]
    return bool(ends) and now.date() <= max(ends).date()


def _sale_photos(n=4):
    """特集記事の商品写真（楽天の商品画像）を並べる。記事から毎朝拾うので、特集と同じ商品になる。"""
    try:
        t = (SALE_JSON.parent.parent.parent / cfg_url(_sale_cfg())).read_text(encoding="utf-8")
    except Exception:
        return ""
    ims = []
    for u in re.findall(r"<a class=item [^>]*>\s*<img src='(https://[^']+)'", t):
        if u not in ims:
            ims.append(u)
    if len(ims) < 2:
        return ""
    return "<div class=ph>" + "".join(f"<i style=\"background-image:url('{u}')\"></i>" for u in ims[:n]) + "</div>"


def cfg_url(cfg):
    return (cfg or {}).get("url", "articles/black-friday-2026.html")


def sale_banner(now, cfg=None):
    cfg = cfg or _sale_cfg()
    if not sale_active(now, cfg):
        return ""
    cells = []
    for m in cfg["malls"]:
        if not m.get("start"):
            st, cls = "発表待ち", "wait"
        else:
            s, e = datetime.fromisoformat(m["start"]), datetime.fromisoformat(m["end"])
            if now < s:
                d = (s.date() - now.date()).days
                st, cls = ("今日から" if d == 0 else f"あと{d}日"), ""
            elif now.date() <= e.date():
                st, cls = ("開催中" if now <= e else "終了"), "on"
            else:
                st, cls = "終了", "wait"
        cells.append(f"<div class=m style='--mc:{m['color']}'><b>{m['short']}</b><small>{m['when']}</small><span class='st {cls}'>{st}</span></div>")
    return ("<!--hubsale-->" + SALE_CSS +
            f"<a class=bf href='{cfg['url']}'>{SALE_ART}<span class=k>SALE SPECIAL</span>"
            f"<h2><em>BLACK FRIDAY</em> 2026</h2><p>楽天・Yahoo!・Amazonの日程と攻略、実質価格のおすすめをまとめました。</p>"
            f"{_sale_photos()}<div class=ml>{''.join(cells)}</div><span class=go>日程と攻略を見る →</span></a><!--/hubsale-->")


def apply_sale(page, now=None):
    """トップの一番上（ヘッダーの直下・検索窓より上）にセール特集を置く。セール終了後は特集・メニューの「セール」・下の旧カードを外す。"""
    now = now or datetime.now()
    page = re.sub(r"<!--hubsale-->.*?<!--/hubsale-->", "", page, flags=re.S)
    page = re.sub(r"<style id=hsalecss>.*?</style>", "", page, flags=re.S)
    page = re.sub(r"<div class=hsec><h2>🔥 セール特集</h2>.*?</a></div>", "", page, flags=re.S)
    ban = sale_banner(now)
    if ban:
        page = page.replace("<!--sbar-->", ban + "<!--sbar-->", 1)
    else:
        page = re.sub(r"<a href='articles/black-friday-2026\.html'>セール</a>", "", page, count=1)
    return page


def apply_hub(page, old=None, now=None):
    now = now or datetime.now()
    b = {k: _block(k, old) for k in KEYS}
    b["hubart"] = _refresh_countdown(b["hubart"], now)
    title = (re.search(r"<title>(.*?)</title>", old or "") or [None, None])[1]
    if not old or "<!--hub-->" not in old:
        title = (HUB / "title.txt").read_text(encoding="utf-8")
    page = re.sub(r"<title>.*?</title>", lambda m: f"<title>{title}</title>", page, 1, re.S)
    # head: ld+basic は </head> の直前へ
    page = page.replace("</head>", b["ld"] + b["basic"] + "</head>", 1)
    # 本文先頭：簡素版の h1 を、ヘッダー〜比較記事カードの固定部品に置き換え
    page = re.sub(r"<main>\s*<h1>.*?</h1>", lambda m: "<main>" + b["hub"], page, 1, re.S)
    # 簡素版だけにある重複ブロック（リンク帯・比較記事の箇条書き）を外す
    page = re.sub(r"<p class=pr>🛒.*?</p>\n?", "", page, 1, re.S)
    page = re.sub(r"<section><h2>比較記事（選び方とおすすめ）</h2>.*?</section>\n?", "", page, 1, re.S)
    # 末尾：比較記事（とセール特集）→マンガの段→フッター（2026-11-18 坂田さん「毎朝最安を上にして、その下に比較記事」）
    page = page.replace("</main></body></html>", b["hubart"] + b["hubm"] + b["ftr"] + "</main></body></html>", 1)
    return apply_sale(page, now)
