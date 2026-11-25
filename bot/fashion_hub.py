"""ファッションページ（fashion/）を、ゲームのページのように「人気ランキングTOP5＋ジャンル別」で作る。
楽天ウェブサービスの事実（商品名・価格・ポイント倍率・レビュー）だけ。毎朝クラウドが fashion.py のあとに実行する。
  - fashion/index.html の <!--fhub-->〜<!--/fhub--> を差し替え（ランキング＋ジャンル別4点ずつ）
  - fashion/<ジャンル>.html を作る（レビューが多い順12点）
使い方: python bot/fashion_hub.py （SITE_DIR=サイトのフォルダ）"""
import html, json, os, re, sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from rakuten import RANKING_URL, SEARCH_URL, Rakuten, load_config  # noqa: E402
from fashion import clean, kind_of, OTHER_NG, BAG_NG, SUMMER_NG, USED_NG, TYPES  # noqa: E402

SITE = Path(os.environ.get("SITE_DIR") or BASE.parent).resolve()
BASEURL = "https://totalyamanote.jp/"
esc = html.escape
MAX_PRICE = 14800
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
    if not (0 < p <= MAX_PRICE) or BAD.search(n) or BAG_NG.search(n) or SUMMER_NG.search(n) or OTHER_NG.search(n):
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
    nm = nm[:44] + ("…" if len(nm) > 44 else "")
    pr = int(x.get("pointRate") or 1)
    p = int(x["itemPrice"])
    return {"name": nm, "sale": sale, "price": p, "pr": pr, "pt": p * pr // 100, "rc": int(x.get("reviewCount") or 0), "av": float(x.get("reviewAverage") or 0),
            "img": img_of(x), "url": x.get("affiliateUrl") or x["itemUrl"], "shop": x.get("shopName", ""), "kind": kind_of(clean(x["itemName"])[0]), "code": x["itemCode"], "rank": rank}


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
            d = api._get(SEARCH_URL, {"keyword": kw + " レディース", "genreId": "100371", "sort": "-reviewCount", "hits": 30, "page": pg, "availability": 1, "maxPrice": MAX_PRICE, "NGKeyword": "中古 メンズ キッズ 福袋"})
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
    sale = f"<span class=hot>SALE {c['sale']}%OFF</span>" if c["sale"] else ""
    return (f"<a class=card href='{esc(c['url'])}' rel='sponsored nofollow noopener' target=_blank>{badge}{sale}<img src='{esc(c['img'])}' alt='{esc(c['name'])}' loading=lazy>"
            f"<span class=nm>{esc(c['name'])}</span><span class=yen>¥{c['price']:,}</span><span class=pts>ポイント{c['pr']}倍（{c['pt']:,}pt）</span>"
            f"<span class=eff2>実質¥{c['price'] - c['pt']:,}</span><span class=rv>⭐{c['av']:.1f}（{c['rc']:,}件）</span><span class=go>楽天市場で見る →</span></a>")


CSS = ("<style id=fhcss>.fk{position:relative}.rkn{position:absolute;top:6px;left:6px;z-index:2;background:#f59e0b;color:#111;font-weight:900;font-size:16px;min-width:28px;height:28px;border-radius:99px;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 4px rgba(0,0,0,.3)}"
       ".fg{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:8px 0 14px}@media (max-width:700px){.fg{grid-template-columns:repeat(2,1fr)}}"
       ".fgchips{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 4px}.fgchips a{background:#be185d;color:#fff!important;border-radius:99px;padding:8px 16px;font-weight:800;font-size:14px;text-decoration:none}"
       ".fmore{display:inline-block;text-decoration:none;font-weight:800;font-size:14px;color:#be185d;border:2px solid #be185d;border-radius:99px;padding:6px 18px;margin:0 0 8px}</style>")


def build_hub(rank5, gen):
    chips = "".join(f"<a href='{g[1]}.html'>{esc(g[0])}</a>" for g in GENRES if len(gen.get(g[1]) or []) >= 4)
    rk = "".join(card(c, f"<span class=rkn>{i}</span>") for i, c in enumerate(rank5, 1))
    html_ = f"<!--fhub-->{CSS}"
    if rk:
        html_ += (f"<h2 id=ranking>🏆 人気ランキング TOP5<small style='font-weight:400;font-size:12px'>　楽天市場の売れ筋（{datetime.now().strftime('%Y/%m/%d')}時点）</small></h2>"
                  f"<p class=meta>楽天市場「レディースファッション」の売れ筋ランキングの上位から、レビュー20件以上・★4.0以上・{MAX_PRICE:,}円までの商品を順に載せています。</p><div class=cards><div class=fg>{rk}</div></div>")
    html_ += f"<h2 id=genres>👗 ジャンル別<small style='font-weight:400;font-size:12px'>　レビューが多い順</small></h2><div class=fgchips>{chips}</div>"
    for lab, slug, kw, _ in GENRES:
        its = gen.get(slug) or []
        if not its:
            continue
        html_ += (f"<h3 id=g-{slug} style='font-size:16px;margin:18px 0 4px'>{esc(lab)}</h3><div class=fg>{''.join(card(c) for c in its[:4])}</div>"
                  f"<a class=fmore href='{slug}.html'>{esc(lab)}をもっと見る ›</a>")
    return html_ + "<!--/fhub-->"


def build_genre_page(index_html, lab, slug, its):
    """index.html の外枠（head・ヘッダー・フッター）を使って、ジャンルごとのページを作る。"""
    head = index_html[: index_html.index("<h1")]
    tail_i = index_html.index("<h2 id=howto>")
    tail = index_html[tail_i:]
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
    body = (f"<h1 style='font-size:20px;margin:10px 0 6px'>{esc(lab)}の人気ランキング（楽天市場）</h1><p class=note>楽天市場のレディースファッション「{esc(lab)}」を、レビューが多い順に。{MAX_PRICE:,}円まで・レビューが多く評価の高い商品です。{datetime.now().strftime('%Y/%m/%d')}時点。</p>"
            f"{CSS}<div class=fgchips><a href='index.html' style='background:#111'>👗 ファッショントップ</a>{chips}</div>"
            f"<section><p class=meta>価格・ポイントは取得時点の表示です。サイズ・色で価格が変わる場合があります。</p><div class=cards><div class=fg>{cards}</div></div>"
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
    blk = build_hub(rank5, gen)
    if "<!--fhub-->" in t:
        t = re.sub(r"<!--fhub-->.*?<!--/fhub-->", lambda m: blk, t, 1, re.S)
    p.write_text(t, encoding="utf-8")
    for lab, slug, kw, _ in GENRES:
        if len(gen[slug]) >= 4:
            build_genre_page(t, lab, slug, gen[slug])
    print("ランキング", len(rank5), "／", {s: len(v) for s, v in gen.items()})


if __name__ == "__main__":
    main()
