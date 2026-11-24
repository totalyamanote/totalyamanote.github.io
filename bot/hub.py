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
KEYS = ("ld", "basic", "hub", "hubf", "hubart", "hubm", "ftr")


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
 ".bf .ph{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:2px 0 12px}"
 ".bf .ph i{display:block;aspect-ratio:1;border-radius:12px;background:#fff center/contain no-repeat;background-origin:content-box;padding:6px;box-sizing:border-box;border:2px solid #ffd54a;box-shadow:0 4px 10px rgba(0,0,0,.45);transform:rotate(-2deg)}"
 ".bf .ph i:nth-child(even){transform:rotate(2deg) translateY(4px)}"
 ".bf .cap{font-size:11px;color:#e8cfcf;margin:-6px 0 10px}"
 ".bf .go{display:inline-block;margin-top:12px;background:linear-gradient(90deg,#ffd54a,#ffb300);color:#111;font-weight:900;font-size:15px;border-radius:99px;padding:10px 22px}"
 "@media(max-width:560px){.bf h2{font-size:24px;max-width:70%}.bf p{max-width:100%}.bf .ml{gap:6px}.bf .m{padding:6px 7px}.bf .m b{font-size:13px}.bf .m small{font-size:10px}.bf svg.bfart{width:104px;height:104px}}"
    "@media(min-width:700px){.bf{padding:14px 20px 14px}.bf svg.bfart{width:110px;height:110px}.bf h2{font-size:24px;margin:6px 0 0;max-width:60%}.bf p{font-size:12px;margin:2px 0 8px}.bf .ph{grid-template-columns:repeat(6,1fr);gap:8px;margin:0 0 8px}.bf .ph i{padding:4px}.bf .m{padding:6px 10px}.bf .go{margin-top:8px;padding:7px 18px;font-size:14px}}"
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


def _sale_photos_from_page(page, n=6):
    """バナーの写真：トップの「ポイント倍率が高い商品」（ランキング上位×倍率順）の先頭3つと、Amazon注目（売れ筋ランキング）の先頭3つを交互に（2026-11-23 坂田さん「バナー画像をもっと売れ筋商品に」）。"""
    i = page.find("ポイント倍率が高い商品")
    if i < 0:
        return ""
    sec = page[i:]
    j = sec.find("</section>")
    sec = sec[:j] if j > 0 else sec
    rak, amz, seen = [], [], set()
    for m in re.finditer(r"<a class=card [^>]*>(.*?)</a>", sec, re.S):
        blk = m.group(1)
        im = re.search(r"<img src='(https://[^']+)'", blk)
        if not im:
            continue
        al = re.search(r"alt='([^']*)'", blk)
        key = re.split(r"[\s　]", (al.group(1) if al else "").strip() or im.group(1))[0]   # ブランド（先頭の語）。同じブランドは1つだけ（2026-11-23 坂田さん「プロテイン2個になってる」）
        if key in seen or re.search(r"ライナー|ペンシル|マスカラ|リップ|ネイル", (al.group(1) if al else "")):   # 細長い商品は写真が小さく見えるので使わない（2026-11-23 坂田さん「キャンメイク 画像サイズあってない」）
            continue
        seen.add(key)
        (amz if "Amazon注目" in blk else rak).append(im.group(1))
    out = []
    for k in range(3):
        if k < len(rak):
            out.append(rak[k])
        if k < len(amz):
            out.append(amz[k])
    for u in rak[3:] + amz[3:]:   # どちらかが足りないときは残りで埋めて6枚にする
        if len(out) >= n:
            break
        out.append(u)
    if len(out) < 4:
        return ""
    return "<div class=ph>" + "".join(f"<i style=\"background-image:url('{u}')\"></i>" for u in out[:n]) + "</div>"


def cfg_url(cfg):
    return (cfg or {}).get("url", "articles/black-friday-2026.html")


def sale_banner(now, cfg=None, page=None):
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
            f"{(_sale_photos_from_page(page) if page else '') or _sale_photos()}<div class=ml>{''.join(cells)}</div><span class=go>日程と攻略を見る →</span></a><!--/hubsale-->")


def move_tail_sections(page):
    """ふるさと納税・ホテルの段は、比較記事の下・マンガの上へ（2026-11-18 坂田さん「ホテル、ふるさと納税は、マンガの上で」）。冪等。"""
    got = []
    for h in ("ふるさと納税", "ホテル"):
        m = re.search(rf"<section><h2>{h}[^<]*</h2>.*?</section>\n?", page, re.S)
        if m:
            got.append(m.group(0))
            page = page.replace(m.group(0), "", 1)
    if got and "<!--hubm-->" in page:
        page = page.replace("<!--hubm-->", "".join(got) + "<!--hubm-->", 1)
    elif got:
        return page.replace("</main>", "".join(got) + "</main>", 1)
    return page


def prune_manga(page, now):
    """トップの『いま無料で読めるマンガ』から、無料が終わった作品（期限切れ・無料の表示がないもの）を外す（2026-11-18 坂田さん「読めなくなったのは載せていかない」）。
    毎朝実行されるので、期限の翌日には自然に消える。1作品も残らなければ、その段ごと外す。"""
    m = re.search(r"<!--hubm-->(.*?)<!--/hubm-->", page, re.S)
    if not m:
        return page
    blk = m.group(1)
    sec = re.search(r"<div class=hsec[^>]*><h2>📚[^<]*<a href='manga/index\.html'>.*?</div></div>", blk, re.S)
    if not sec:
        return page

    def keep(a):
        a = a.group(0)
        b = re.search(r"<span>(\d+)/(\d+)まで無料</span>", a)
        if b:
            mo, d = int(b.group(1)), int(b.group(2))
            y = now.year + (1 if mo < now.month - 6 else 0)
            try:
                return a if datetime(y, mo, d).date() >= now.date() else ""
            except ValueError:
                return a
        return a if "<span>" in a else ""   # 無料の表示がない＝いま無料ではない

    new = re.sub(r"<a class=hm href='manga/w/[^']*'>.*?</a>", keep, sec.group(0), flags=re.S)
    if "<a class=hm" not in new:
        new = ""
    elif "人気マンガ（あらすじ・登場人物）" in new:
        pass
    return page.replace(sec.group(0), new, 1)


def apply_sale(page, now=None):
    """トップの上のほう（検索欄・PR表記・ひとこと説明の直下、毎朝の最安の上）にセール特集を置く。セール終了後は特集・メニューの「セール」・下の旧カードを外す。"""
    now = now or datetime.now()
    page = prune_manga(page, now)
    page = move_tail_sections(page)
    page = re.sub(r"<!--hubsale-->.*?<!--/hubsale-->", "", page, flags=re.S)
    page = re.sub(r"<style id=hsalecss>.*?</style>", "", page, flags=re.S)
    page = re.sub(r"<div class=hsec><h2>🔥 セール特集</h2>.*?</a></div>", "", page, flags=re.S)
    ban = sale_banner(now, page=page)
    if ban:
        page = page.replace("<h2 id=daily", ban + "<h2 id=daily", 1)   # 検索欄・PR・ひとことは最上段に固定、その直下にセール特集（2026-11-18 坂田さん）
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
    page = page.replace("</main></body></html>", b["hubf"] + b["hubart"] + b["hubm"] + b["ftr"] + "</main></body></html>", 1)
    return apply_sale(page, now)
