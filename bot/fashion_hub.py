"""ファッションページ（fashion/）を、ゲームのページのように「人気ランキングTOP5＋ジャンル別」で作る。
楽天ウェブサービスの事実（商品名・価格・ポイント倍率・レビュー）だけ。毎朝クラウドが fashion.py のあとに実行する。
  - fashion/index.html の <!--fhub-->〜<!--/fhub--> を差し替え（ランキング＋ジャンル別4点ずつ）
  - fashion/<ジャンル>.html を作る（レビューが多い順12点）
使い方: python bot/fashion_hub.py （SITE_DIR=サイトのフォルダ）"""
import html, json, os, re, sys, time, urllib.parse, urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from rakuten import RANKING_URL, SEARCH_URL, Rakuten, load_config  # noqa: E402
from fashion import clean, kind_of, OTHER_NG, BAG_NG, SUMMER_NG, USED_NG, TYPES  # noqa: E402

SITE = Path(os.environ.get("SITE_DIR") or BASE.parent).resolve()
BASEURL = "https://totalyamanote.jp/"
esc = html.escape
MAX_PRICE = 0   # 人気ランキングなので価格の上限なし（2026-11-25 坂田さん）
GENRES = [("ワンピース", "onepiece", "ワンピース", "ワンピース"), ("ニット・セーター", "knit", "ニット", "ニット"), ("コート・アウター", "outer", "コート", "コート・アウター"),
          ("カーディガン", "cardigan", "カーディガン", "カーディガン"), ("スカート", "skirt", "スカート", "スカート"), ("パンツ", "pants", "パンツ", "パンツ"),
          ("ブラウス・トップス", "tops", "ブラウス", "ブラウス・トップス")]
BAD = re.compile(r"福袋|HAPPY BOX|福箱|ラッキーバッグ|訳あり|訳アリ|ベビー|キッズ|子供|マタニティ|ペット|犬|レギンス|ペチコート|腹巻|ナイトブラ|喪服|礼服|下着|インナー|ヒートテック|パジャマ|ルームウェア|スパッツ|タイツ|ショーツ|ブラ付|エプロン|白衣|スクラブ|コスプレ|着る毛布")


def img_of(x):
    imgs = x.get("mediumImageUrls") or []
    if not imgs:
        return ""
    u = imgs[0] if isinstance(imgs[0], str) else imgs[0].get("imageUrl", "")
    return re.sub(r"_ex=\d+x\d+", "_ex=300x300", u)


def ok(x, min_rev, min_avg):
    n = x["itemName"]
    p = int(x.get("itemPrice") or 0)
    if not (p > 0) or BAD.search(n) or BAG_NG.search(n) or SUMMER_NG.search(n) or OTHER_NG.search(n):
        return False
    if USED_NG.search(n + " " + (x.get("itemCaption") or "")):
        return False
    if int(x.get("reviewCount") or 0) < min_rev or float(x.get("reviewAverage") or 0) < min_avg:
        return False
    if kind_of(clean(n)[0]) == "その他":
        return False
    return bool(img_of(x))


def item(x, rank=None):
    nm, sale = clean(x["itemName"])
    nm = re.sub(r"\d+\s*[%％]\s*OFF[!！]*|最大\d+[%％]OFF|半額|[!！]{1,}", " ", nm)
    nm = re.sub(r"\d+/\d+\([^)]*\)\d+:\d+[迄まで]*|メール便不可|メール便OK|送料無料", " ", nm)
    nm = re.sub(r"\s+", " ", nm).strip()
    nm = tidy(nm)
    nm = nm[:30] + ("…" if len(nm) > 30 else "")
    pr = int(x.get("pointRate") or 1)
    p = int(x["itemPrice"])
    return {"name": nm, "sale": sale, "price": p, "pr": pr, "pt": p * pr // 100, "rc": int(x.get("reviewCount") or 0), "av": float(x.get("reviewAverage") or 0),
            "img": img_of(x), "url": x.get("affiliateUrl") or x["itemUrl"], "shop": x.get("shopName", ""), "kind": kind_of(clean(x["itemName"])[0]), "code": x["itemCode"], "rank": rank}


def tidy(nm):
    nm = re.sub(r"「[^」]*」|『[^』]*』|【[^】]*】|\([^)]*\)?|（[^）]*）|[「」『』]", " ", nm)
    return re.sub(r"\s+", " ", nm).strip()


def off_pct(price, default):
    try:
        return round((default - price) * 100 / default) if default and default > price else 0
    except Exception:
        return 0


def price_html(c):
    """値段の横に「◯%OFF」、その下にポイントの％とpt（2026-11-25 坂田さん）。"""
    off = f"<b class=off>{c['off']}%OFF</b>" if c.get("off") else (f"<b class=off>{c['sale']}%OFF</b>" if c.get("sale") else "")
    pt = ""
    if c.get("pt", 0) > 0 and c.get("price"):
        pt = f"<span class=pts>ポイント{max(1, round(c['pt'] * 100 / c['price']))}%（{c['pt']:,}pt）</span><span class=eff2>実質¥{c['price'] - c['pt']:,}</span>"
    return f"<span class=yenrow><span class=yen>¥{c['price']:,}</span>{off}</span>{pt}"


def dedup(xs, n):
    seen, out = set(), []
    for c in xs:
        k = re.sub(r"\s+", "", c["name"])[:16]
        if k in seen:
            continue
        seen.add(k); out.append(c)
        if len(out) >= n:
            break
    return out


def ranking(api):
    out = []
    for page in range(1, 9):
        try:
            d = api._get(RANKING_URL, {"genreId": "100371", "page": page})
        except Exception:
            break
        for x in d.get("Items", []):
            x = x.get("Item", x)
            if ok(x, 20, 4.0):
                out.append(item(x, int(x["rank"])))
    out.sort(key=lambda c: c["rank"])
    return dedup(out, 5)


def genre_items(api, kw, label, n, th=(30, 4.2)):
    out = []
    for pg in (1, 2, 3):
        try:
            d = api._get(SEARCH_URL, {"keyword": kw + " レディース", "genreId": "100371", "sort": "-reviewCount", "hits": 30, "page": pg, "availability": 1, "NGKeyword": "中古 メンズ キッズ 福袋"})
        except Exception:
            continue
        for x in d.get("Items", []):
            x = x.get("Item", x)
            if not ok(x, th[0], th[1]):
                continue
            c = item(x)
            if kind_of(clean(x["itemName"])[0]) != label and label not in c["name"]:
                continue
            out.append(c)
    out = dedup(out, n)
    if len(out) < 8 and th[0] > 10:
        return genre_items(api, kw, label, n, (10, 4.0))
    return out


def card(c, badge=""):
    return (f"<a class=card href='{esc(c['url'])}' rel='sponsored nofollow noopener' target=_blank>{badge}<img src='{esc(c['img'])}' alt='{esc(c['name'])}' loading=lazy>"
            f"<span class=nm>{esc(c['name'])}</span>{price_html(c)}"
            f"<span class=rv>⭐{c['av']:.1f}（{c['rc']:,}件）</span><span class=go>楽天市場で見る →</span></a>")


CSS = ("<style id=fhcss>.fcs{grid-template-columns:repeat(auto-fill,minmax(160px,1fr))!important}.fcs .card .nm{white-space:normal;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;min-height:2.8em}.fcs .card img{aspect-ratio:3/4;object-fit:cover}"
       ".rkn{position:absolute;top:6px;left:6px;z-index:2;background:#f59e0b;color:#111;font-weight:900;font-size:16px;min-width:28px;height:28px;border-radius:99px;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 4px rgba(0,0,0,.3)}.fcs .rkn~.hot{top:auto;bottom:112px;left:10px}"
       ".fgchips{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 4px}.fgchips a{background:#be185d;color:#fff!important;border-radius:99px;padding:7px 14px;font-weight:800;font-size:13px;text-decoration:none}"
       ".fsts{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:8px;margin:8px 0}.fst{display:flex;flex-direction:column;gap:2px;border:1px solid var(--line);border-radius:10px;padding:10px 12px;text-decoration:none;color:inherit;background:var(--card)}.fst b{font-size:14px}.fst small{font-size:12px;color:var(--mut)}.fst.amz{border-color:#ff9900}.yenrow{display:flex;align-items:center;gap:6px;flex-wrap:wrap}.off{background:#d6336c;color:#fff;border-radius:99px;padding:1px 8px;font-size:12px}.fmore{display:inline-block;text-decoration:none;font-weight:800;font-size:13px;color:#be185d;border:2px solid #be185d;border-radius:99px;padding:5px 16px;margin:0 0 8px}</style>")


YAHOO_API = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch"


def yahoo_items(cfg, n=8):
    """Yahoo!ショッピングのレディースファッション（ジャンル2494）の人気順。リンクはバリューコマース。価格上限なし。"""
    y = (cfg or {}).get("yahoo", {})
    appid = os.environ.get("YAHOO_APP_ID") or y.get("app_id", "")
    sid, pid = str(y.get("vc_sid", "")), str(y.get("vc_pid", ""))
    if not (appid and sid and pid):
        return []
    vc = f"https://ck.jp.ap.valuecommerce.com/servlet/referral?sid={sid}&pid={pid}&vc_url="
    out = []
    for pg in (1, 2):
        q = {"appid": appid, "genre_category_id": "2494", "results": 50, "start": 1 + (pg - 1) * 50, "sort": "-score", "in_stock": "true", "condition": "new",
             "affiliate_type": "vc", "affiliate_id": vc}
        try:
            req = urllib.request.Request(YAHOO_API + "?" + urllib.parse.urlencode(q), headers={"User-Agent": "yamanote/1.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                d = json.load(r)
        except Exception:
            continue
        time.sleep(1.0)
        for h in d.get("hits", []):
            if not str(h.get("url", "")).startswith("https://ck.jp.ap.valuecommerce.com/"):
                continue
            nm0 = h.get("name", "")
            rv = h.get("review") or {}
            if int(rv.get("count") or 0) < 20 or float(rv.get("rate") or 0) < 4.0 or BAD.search(nm0) or BAG_NG.search(nm0) or SUMMER_NG.search(nm0) or OTHER_NG.search(nm0) or USED_NG.search(nm0):
                continue
            nm, sale = clean(nm0)
            nm = re.sub(r"\s+", " ", re.sub(r"\d+/\d+\([^)]*\)\d+:\d+[迄まで]*|メール便不可|メール便OK|送料無料|\d+\s*[%％]\s*OFF[!！]*|[!！]+", " ", nm)).strip()
            nm = tidy(nm)
            if kind_of(nm) == "その他":
                continue
            price = int(h.get("price") or 0)
            po = h.get("point") or {}
            pt = int(po.get("amount") or 0) + int(po.get("bonusAmount") or 0)
            img = ((h.get("image") or {}).get("medium") or "").replace("/i/g/", "/i/l/")
            if not img or price <= 0:
                continue
            out.append({"name": nm[:30] + ("…" if len(nm) > 30 else ""), "sale": "", "price": price, "pr": max(1, round(pt * 100 / price)) if price else 1, "pt": pt, "rc": int(rv.get("count") or 0), "av": float(rv.get("rate") or 0),
                        "img": img, "url": h["url"], "kind": kind_of(nm), "shop": (h.get("seller") or {}).get("name", ""), "code": "y:" + str(h.get("code", "")), "rank": None, "yahoo": True})
    return dedup(out, n)


def card_y(c):
    return (f"<a class=card href='{esc(c['url'])}' rel='sponsored nofollow noopener' target=_blank><img src='{esc(c['img'])}' alt='{esc(c['name'])}' loading=lazy>"
            f"<span class=nm>{esc(c['name'])}</span>{price_html(c)}"
            + f"<span class=rv>⭐{c['av']:.1f}（{c['rc']:,}件）</span><span class='go ygo'>Yahoo!で見る →</span></a>")


def stores_block(cfg):
    """ほかのお店（提携済みのファッション・百貨店）へのボタン。リンクは bot/data/fashion_stores.json（管理画面で取得したアフィリエイトURL）。Amazonは売れ筋ページへ。"""
    items = []
    tag = (cfg or {}).get("amazon_tag", "")
    amz = "https://www.amazon.co.jp/gp/bestsellers/apparel/" + (f"?tag={tag}" if tag else "")
    items.append(("Amazonファッション", "売れ筋ランキングを見る", amz, "amz"))
    try:
        for x in json.loads((BASE / "data" / "fashion_stores.json").read_text(encoding="utf-8")):
            if x.get("url"):
                items.append((x["name"], x.get("tag", ""), x["url"], x.get("cls", "")))
    except Exception:
        pass
    if not items:
        return ""
    cells = "".join(f"<a class='fst {c}' href='{esc(u)}' rel='sponsored nofollow noopener' target=_blank><b>{esc(n)}</b><small>{esc(t)}</small></a>" for n, t, u, c in items)
    return f"<div class=fsts>{cells}</div>"


YSTORES = [("マルイ（丸井）", "マルイ(丸井)Yahoo!店", "百貨店"), ("高島屋 ファッションスクエア", "タカシマヤファッションスクエア", "百貨店"), ("ZOZOTOWN", "ZOZOTOWN Yahoo!店", "ファッション通販"), ("Pierrot（ピエロ）", "Pierrot(ピエロ)Yahoo!店", "ガーリー・プチプラ")]


def _yget(appid, vc, q):
    q = dict(q, appid=appid, in_stock="true", condition="new", affiliate_type="vc", affiliate_id=vc)
    req = urllib.request.Request(YAHOO_API + "?" + urllib.parse.urlencode(q), headers={"User-Agent": "yamanote/1.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        d = json.load(r)
    time.sleep(1.0)
    return d


def yahoo_store_sections(cfg, n=4, big=("ZOZOTOWN", "マルイ（丸井）", "高島屋 ファッションスクエア")):
    """Yahoo!ショッピングに出店している百貨店・ファッション通販（マルイ・高島屋・ZOZOTOWN・Pierrot）の人気商品。リンクはバリューコマース。"""
    y = (cfg or {}).get("yahoo", {})
    appid = os.environ.get("YAHOO_APP_ID") or y.get("app_id", "")
    sid, pid = str(y.get("vc_sid", "")), str(y.get("vc_pid", ""))
    if not (appid and sid and pid):
        return []
    vc = f"https://ck.jp.ap.valuecommerce.com/servlet/referral?sid={sid}&pid={pid}&vc_url="
    out = []
    for label, sname, tag in YSTORES:
        try:
            d = _yget(appid, vc, {"query": sname.split("(")[0] + " レディース", "genre_category_id": "2494", "results": 30})
            sellers = {(h.get("seller") or {}).get("name"): (h.get("seller") or {}).get("sellerId") for h in d.get("hits", [])}
            sidn = sellers.get(sname)
            if not sidn:
                continue
            d = _yget(appid, vc, {"seller_id": sidn, "genre_category_id": "2494", "results": 50, "sort": "-score"})
        except Exception:
            continue
        items = []
        for h in d.get("hits", []):
            if not str(h.get("url", "")).startswith("https://ck.jp.ap.valuecommerce.com/"):
                continue
            nm0 = h.get("name", "")
            rv = h.get("review") or {}
            if BAD.search(nm0) or BAG_NG.search(nm0) or SUMMER_NG.search(nm0) or OTHER_NG.search(nm0) or USED_NG.search(nm0):
                continue
            if int(rv.get("count") or 0) and float(rv.get("rate") or 0) < 3.8:
                continue
            nm, _ = clean(nm0)
            nm = tidy(re.sub(r"\s+", " ", re.sub(r"\d+/\d+\([^)]*\)\d+:\d+[迄まで]*|メール便不可|メール便OK|送料無料|\d+\s*[%％]\s*OFF[!！]*|[!！]+", " ", nm)).strip())
            img = ((h.get("image") or {}).get("medium") or "").replace("/i/g/", "/i/l/")
            price = int(h.get("price") or 0)
            if len(nm) < 9:
                nm = tidy(re.sub(r"\s+", " ", nm0)).strip()
            nm = re.sub(r"[ /／]+$", "", nm).strip()
            if not img or price <= 0 or len(nm) < 4:
                continue
            po = h.get("point") or {}
            pt = int(po.get("amount") or 0) + int(po.get("bonusAmount") or 0) + int(po.get("lyLimitedBonusAmount") or 0)
            items.append({"off": off_pct(price, (h.get("priceLabel") or {}).get("defaultPrice")), "name": nm[:30] + ("…" if len(nm) > 30 else ""), "price": price, "pt": pt, "rc": int(rv.get("count") or 0), "av": float(rv.get("rate") or 0), "img": img, "url": h["url"]})
        items = dedup(items, 13 if label == "ZOZOTOWN" else (8 if label in big else n))
        if items:
            top = vc + urllib.parse.quote(f"https://store.shopping.yahoo.co.jp/{sidn}/", safe="")
            out.append((label, tag, top, items))
    return out


def stores_cards_block(sections, ranked=False):
    html_ = ""
    for label, tag, top, items in sections:
        cs = ""
        for i, c in enumerate(items, 1):
            badge = f"<span class=rkn>{i}</span>" if ranked else ""
            rv = f"<span class=rv>⭐{c['av']:.1f}（{c['rc']:,}件）</span>" if c["rc"] else ""
            cs += (f"<a class=card href='{esc(c['url'])}' rel='sponsored nofollow noopener' target=_blank>{badge}<img src='{esc(c['img'])}' alt='{esc(c['name'])}' loading=lazy>"
                   f"<span class=nm>{esc(c['name'])}</span>{price_html(c)}" + rv + "<span class='go ygo'>Yahoo!で見る →</span></a>")
        html_ += (f"<div class=\"cards fcs\">{cs}</div>"
                  f"<a class=fmore href='{esc(top)}' rel='sponsored nofollow noopener' target=_blank>{esc(label)}のお店を見る ›</a>")
    return html_


SOFT = ("<style id=fsoft>:root{--fp:#d6336c;--fp2:#fbcfe8;--fbg:#fff6f4}body{background:var(--fbg)}"
        "main h1{margin:0 -16px 12px!important;padding:26px 18px 22px;text-align:center;font-size:24px!important;letter-spacing:.06em;color:#831843;background:linear-gradient(135deg,#ffe4ec 0%,#fff1e6 55%,#ffe9f3 100%);border-bottom:1px solid #fbcfe8}"
        "main h1::before{content:'🌸 ';font-size:20px}main h1::after{content:' 🌸';font-size:20px}"
        "main h2{border-left:0!important;padding:0 0 6px!important;margin:30px 0 10px!important;color:#9d174d;font-size:19px;border-bottom:2px solid #fbcfe8;letter-spacing:.03em}"
        "main h3{color:#9d174d}.chips2 a,.fgchips a{background:#fff!important;color:#be185d!important;border:1px solid #fbcfe8!important;border-radius:99px;padding:7px 15px;font-weight:800;box-shadow:0 2px 6px rgba(190,24,93,.08)}"
        ".card{border-color:#fbcfe8!important;border-radius:18px!important;box-shadow:0 4px 14px rgba(190,24,93,.10)!important;background:#fff!important}.card img{border-radius:12px!important}"
        ".card .go{background:linear-gradient(135deg,#f472b6,#d6336c)!important;border-radius:99px!important}.card .eff2{background:#ffe4ec!important;color:#9d174d!important}.card .yen{color:#be185d!important}.card .hot{background:#d6336c!important}"
        ".rkn{background:linear-gradient(135deg,#f9a8d4,#d6336c)!important;color:#fff!important}.fmore{color:#be185d!important;border-color:#f9a8d4!important;background:#fff}"
        ".fst{border-color:#fbcfe8!important;border-radius:14px!important;background:#fff!important}"
        "@media (prefers-color-scheme:dark){:root{--fbg:#2a1a20}body{background:var(--fbg)}main h1{color:#fce7f3;background:linear-gradient(135deg,#4a1d33,#3b2230);border-color:#6b2a48}main h2,main h3{color:#f9a8d4;border-color:#6b2a48}.card,.fst{background:#3a2530!important;border-color:#6b2a48!important}.chips2 a,.fgchips a{background:#3a2530!important;color:#f9a8d4!important;border-color:#6b2a48!important}}</style>")


def build_hub(rank5, gen, yh=None, cfg=None, ys=None):
    """並び（2026-11-25 坂田さん）：人気ランキング → ZOZOTOWN（Yahoo!）→［楽天ファッション（インフルエンサー発）＝fashion.pyの段］→ マルイ（Yahoo!）→ ジャンル別・ほかのお店。
    前半を <!--fhub-->、後半を <!--fhub2--> に出す。"""
    by = {lab: (tag, top, items) for lab, tag, top, items in (ys or [])}

    def sect(hid, title, lab, sl=None):
        if lab not in by:
            return ""
        tag, top, items = by[lab]
        if sl is not None:
            items = items[sl]
        return f"<h2 id={hid}>{title}</h2>" + stores_cards_block([(lab, tag, top, items)])
    first = f"<!--fhub-->{CSS}{SOFT}"
    zz = by.get("ZOZOTOWN")
    if zz and len(zz[2]) >= 5:
        # ランキング＝ZOZOTOWN（Yahoo!ショッピング）の人気順の上位5（2026-11-25 坂田さん「ランキングはZOZOにしよう」）。下のZOZOTOWNの段は6位以降
        first += "<h2 id=ranking>🏆 人気ランキング TOP5<small style='font-weight:400;font-size:12px'>　ZOZOTOWN（Yahoo!ショッピング）</small></h2>" + stores_cards_block([("ZOZOTOWN", zz[0], zz[1], zz[2][:5])], ranked=True)
        first += sect("zozo", "🛍 ZOZOTOWNの人気商品", "ZOZOTOWN", slice(5, 13))
    else:
        rk = "".join(card(c, f"<span class=rkn>{i}</span>") for i, c in enumerate(rank5, 1))
        if rk:
            first += f"<h2 id=ranking>🏆 人気ランキング TOP5</h2><div class=\"cards fcs\">{rk}</div>"
        first += sect("zozo", "🛍 ZOZOTOWN（Yahoo!ショッピング）", "ZOZOTOWN")
    first += "<!--/fhub-->"
    chips = "".join(f"<a href='{g[1]}.html'>{esc(g[0])}</a>" for g in GENRES if len(gen.get(g[1]) or []) >= 4)
    second = "<!--fhub2-->" + sect("marui", "🏬 マルイ（Yahoo!ショッピング）", "マルイ（丸井）") + sect("takashimaya", "🏬 高島屋 ファッションスクエア（Yahoo!ショッピング）", "高島屋 ファッションスクエア")
    second += f"<h2 id=genres>🗂 ジャンル別ランキング</h2><div class=fgchips>{chips}</div>"
    for lab, slug, kw, _ in GENRES:
        its = gen.get(slug) or []
        if not its:
            continue
        second += (f"<h3 id=g-{slug} style='font-size:16px;margin:18px 0 4px'>{esc(lab)}</h3><div class=\"cards fcs\">{''.join(card(c) for c in its[:4])}</div>"
                   f"<a class=fmore href='{slug}.html'>{esc(lab)}をもっと見る ›</a>")
    rest = [(l, t, tp, it) for l, t, tp, it in (ys or []) if l not in ("ZOZOTOWN", "マルイ（丸井）", "高島屋 ファッションスクエア")]
    sb = stores_block(cfg)
    if rest or sb:
        second += "<h2 id=stores>🛒 ほかのお店</h2>" + sb
        for l, t, tp, it in rest:
            second += f"<h3 style='font-size:16px;margin:16px 0 2px'>{esc(l)}<small style='font-weight:400;font-size:12px'>　{esc(t)}</small></h3>" + stores_cards_block([(l, t, tp, it)])
    return first, second + "<!--/fhub2-->"


def build_genre_page(index_html, lab, slug, its):
    """index.html の外枠（head・ヘッダー・フッター）を使って、ジャンルごとのページを作る。"""
    head = index_html[: index_html.index("<h1")]
    tail = index_html[index_html.index("<!--/fhub2-->") + len("<!--/fhub2-->"):]
    url = BASEURL + f"fashion/{slug}.html"
    title = f"{lab}の人気ランキング｜楽天市場のレディースファッション｜やまのて ファッション"
    desc = f"楽天市場のレディースファッション「{lab}」を、レビューが多い順に{len(its)}点。価格・ポイント・実質価格（価格−ポイント）・レビューつき。{datetime.now().strftime('%m/%d')}時点。"
    head = re.sub(r"<title>.*?</title>", lambda m: f"<title>{esc(title)}</title>", head, 1, re.S)
    head = re.sub(r"<meta name=description content='[^']*'>", lambda m: f"<meta name=description content='{esc(desc)}'>", head, 1)
    head = re.sub(r"<link rel=canonical href='[^']*'>", f"<link rel=canonical href='{url}'>", head, 1)
    head = re.sub(r'<meta property=og:title content="[^"]*">', lambda m: f'<meta property=og:title content="{esc(title)}">', head, 1)
    head = re.sub(r'<meta property=og:description content="[^"]*">', lambda m: f'<meta property=og:description content="{esc(desc)}">', head, 1)
    head = re.sub(r"<meta property=og:url content='[^']*'>", f"<meta property=og:url content='{url}'>", head, 1)
    head = re.sub(r'<script type="?application/ld\+json"?>.*?</script>', "", head, flags=re.S)
    bc = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "トップ", "item": BASEURL}, {"@type": "ListItem", "position": 2, "name": "レディースファッション", "item": BASEURL + "fashion/index.html"},
        {"@type": "ListItem", "position": 3, "name": lab, "item": url}]}
    il = {"@context": "https://schema.org", "@type": "ItemList", "name": f"{lab}の人気ランキング", "itemListElement": [
        {"@type": "ListItem", "position": i, "name": c["name"], "url": c["url"]} for i, c in enumerate(its, 1)]}
    ld = "".join(f"<script type=application/ld+json>{json.dumps(o, ensure_ascii=False)}</script>" for o in (bc, il))
    head = head.replace("</head>", ld + "</head>", 1) if "</head>" in head else head
    chips = "".join(f"<a href='{g[1]}.html'>{esc(g[0])}</a>" for g in GENRES)
    cards = "".join(card(c, f"<span class=rkn>{i}</span>") for i, c in enumerate(its, 1))
    nav = (f"<nav class=bc aria-label='パンくず' style='font-size:12px;color:#665d55;margin:6px 0 4px'><a href='../index.html'>トップ</a> › <a href='index.html'>レディースファッション</a> › {esc(lab)}</nav>")
    head = re.sub(r"<nav class=bc.*?</nav>", lambda m: nav, head, 1, re.S)
    body = (f"<h1 style='font-size:20px;margin:10px 0 6px'>{esc(lab)}の人気ランキング（楽天市場）</h1>"
            f"{CSS}{SOFT}<div class=fgchips><a href='index.html'>👗 ファッショントップ</a>{chips}</div>"
            f"<section><div class=\"cards fcs\">{cards}</div>"
            "<p class=meta style='font-size:12px'>PR｜楽天市場へのリンクはアフィリエイト広告です。商品ページで最新の価格・ポイントをご確認ください。</p></section>")
    (SITE / "fashion" / f"{slug}.html").write_text(head + body + tail, encoding="utf-8")


def main():
    cfg = load_config(Path(os.environ.get("CONFIG_BASE") or BASE))
    if not cfg:
        sys.exit("設定が読めません")
    api = Rakuten(cfg)
    p = SITE / "fashion" / "index.html"
    if not p.exists():
        sys.exit("fashion/index.html がありません")
    rank5 = ranking(api)
    gen = {slug: genre_items(api, kw, lab2, 12) for lab, slug, kw, lab2 in GENRES}
    t = p.read_text(encoding="utf-8")
    yh = None
    ys = yahoo_store_sections(cfg)
    blk, blk2 = build_hub(rank5, gen, yh, cfg, ys)
    if "<!--fhub-->" in t:
        t = re.sub(r"<!--fhub-->.*?<!--/fhub-->", lambda m: blk, t, 1, re.S)
    if "<!--fhub2-->" in t:
        t = re.sub(r"<!--fhub2-->.*?<!--/fhub2-->", lambda m: blk2, t, 1, re.S)
    p.write_text(t, encoding="utf-8")
    for lab, slug, kw, _ in GENRES:
        if len(gen[slug]) >= 4:
            build_genre_page(t, lab, slug, gen[slug])
    print("ランキング", len(rank5), "／", {s: len(v) for s, v in gen.items()})


if __name__ == "__main__":
    main()
