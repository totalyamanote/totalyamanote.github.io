"""トップページの「楽天ファッション（レディース）」の段を、毎朝作り直す（2026-11-23 坂田さん「楽天ファッションを物販に追加。レディースアパレル中心で」）。

楽天ウェブサービス（IchibaItem/Search）で、楽天ファッション（shopCode=stylife）の商品を種類ごとに検索し、
レビューが多い順に、価格・ポイント・実質価格を出す。事実だけ（商品名・価格・ポイント倍率・レビュー）。
トップ（index.html）の <!--hubf-->〜<!--/hubf--> を差し替える（無ければ <!--hubart--> の直前に入れる）。
bot/hub.py は hubf を引き継ぐので、run_daily のあとに毎朝この段だけ更新する。
使い方: python bot/fashion.py   （環境変数 SITE_DIR=トップのあるフォルダ。キーは RAKUTEN_APP_ID など／手元は config.json）"""
import html, json, os, re, sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from rakuten import RANKING_URL, SEARCH_URL, Rakuten, load_config  # noqa: E402

SITE = Path(os.environ.get("SITE_DIR") or BASE.parent).resolve()
SHOP = "stylife"                      # 楽天ファッション（楽天市場の店舗コード）
# 種類（レディース中心）。1種類につき1商品（その種類でレビューがいちばん多いもの）を載せる
KINDS = ["ワンピース", "ニット", "コート", "スカート", "パンツ", "ブラウス", "カーディガン", "セーター"]
MAX_PRICE = 9800                      # 価格は9,800円まで（運用ルール）
MIN_REVIEWS, MIN_AVG = 50, 4.0
esc = html.escape


def clean(name):
    """商品名から、期間限定の宣伝（SALE・％OFF・日付）と【】の飾りを外す。SALEの割引は別に取り出す。"""
    sale = re.search(r"SALE[／/](\d+)%OFF", name)
    s = re.sub(r"【[^】]*】|\[[^\]]*\]|＼[^／]*／|《[^》]*》|★|☆|◆|♪", " ", name)
    s = re.sub(r"(送料無料|ポイント\d+倍|楽天\d+位|あす楽|クーポン\S*|P\d+倍)", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # 商品名のあとに続くショップのカテゴリ文（ブランド名のカタカナ読み以降：コカ ワンピース・ドレス …）は落とす
    toks = s.split(" ")
    for i, t in enumerate(toks):
        if i >= 2 and re.fullmatch(r"[ァ-ヶー・]{2,}", t) and t not in KINDS:
            toks = toks[:i]; break
    s = " ".join(toks)
    return s, (sale.group(1) if sale else "")


def brand(name):
    m = re.search(r"(?:【[^】]*】\s*)*([A-Za-z][A-Za-z0-9 .&'\-]{1,24}?|[ぁ-んァ-ヶ一-龠ー]{2,10})\s", clean(name)[0] + " ")
    return (m.group(1).strip() if m else "")


TYPES = [("コート・アウター", r"コート|アウター|ジャケット|ダウン|ブルゾン|ベスト"), ("ニット", r"ニット|セーター|プルオーバー"), ("ワンピース", r"ワンピース|ドレス"),
         ("カーディガン", r"カーディガン|ボレロ"), ("スカート", r"スカート"), ("パンツ", r"パンツ|デニム|ジーンズ"), ("ブラウス・トップス", r"ブラウス|シャツ|カットソー|トップス|Tシャツ|スウェット|パーカー")]
OTHER_NG = re.compile(r"メンズ|MEN'S|ユニセックス|キッズ|ベビー|United Athle")   # レディースの段なので
BAG_NG = re.compile(r"福袋|HAPPY BOX|福箱|ラッキーバッグ|LUCKY")
# 冬（11〜2月）は半袖・ノースリーブなど夏物を出さない（2026-11-23）
SUMMER_NG = re.compile(r"半袖|ノースリーブ|キャミ|タンクトップ|サンダル|リネン|水着|ラッシュガード|水陸両用|サマー|夏") if datetime.now().month in (11, 12, 1, 2) else re.compile(r"(?!x)x")


def kind_of(name):
    for label, rx in TYPES:
        if re.search(rx, name):
            return label
    return "その他"


HIST = BASE / "data" / "fashion_shown.json"


def _days_ago(n):
    from datetime import timedelta
    return (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")


def _load_hist():
    try:
        return json.loads(HIST.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_hist(codes):
    h = _load_hist()
    h[datetime.now().strftime("%Y-%m-%d")] = codes
    h = {d: v for d, v in h.items() if d >= _days_ago(7)}
    HIST.write_text(json.dumps(h, ensure_ascii=False, indent=1), encoding="utf-8")


def ranked(api):
    """楽天の「レディースファッション」売れ筋ランキング（genre 100371）の中から、楽天ファッションの商品だけを、順位の高い順に。"""
    out = []
    for page in range(1, 13):
        try:
            d = api._get(RANKING_URL, {"genreId": "100371", "page": page})
        except Exception as e:
            print("ランキング失敗", page, str(e)[:60]); break
        for x in d.get("Items", []):
            x = x.get("Item", x)
            if x.get("shopCode") != SHOP and "Rakuten Fashion" not in x.get("shopName", ""):
                continue
            out.append(x)
    out.sort(key=lambda x: int(x["rank"]))
    return out


def pick(api):
    """割引率の高い順（2026-11-23 坂田さん「すべて別の商品に、割引高いの優先」）。
    候補＝レディースファッション売れ筋ランキングに入る楽天ファッションの商品＋楽天ファッションの種類ごとの検索（レビュー多い順）。
    前の2日に出した商品は出さない（毎日8点すべて入れ替え）。レビュー10件以上・★4.0以上、9,800円まで。種類を散らし、同じブランドは2点まで。"""
    today = datetime.now().strftime("%Y-%m-%d")
    hist = _load_hist()
    recent = {code for d, codes in hist.items() if d != today and d >= _days_ago(2) for code in codes}
    raw = {}
    for x in ranked(api):
        raw[x["itemCode"]] = (int(x["rank"]), x)
    for kw in ["SALE", "ニット", "コート", "ワンピース", "カーディガン", "スカート", "パンツ", "ブラウス", "ジャケット"]:
        for pg in (1, 2):
            try:
                dd = api._get(SEARCH_URL, {"shopCode": SHOP, "keyword": kw, "sort": "-reviewCount", "hits": 30, "page": pg, "availability": 1})
            except Exception:
                continue
            for y in dd.get("Items", []):
                y = y.get("Item", y)
                raw.setdefault(y["itemCode"], (999, y))
    cand = []
    for code, (rank, x) in raw.items():
        name0 = x["itemName"]
        price = int(x.get("itemPrice") or 0)
        if code in recent or not (0 < price <= MAX_PRICE) or BAG_NG.search(name0) or SUMMER_NG.search(name0) or OTHER_NG.search(name0):
            continue
        if int(x.get("reviewCount") or 0) < 10 or float(x.get("reviewAverage") or 0) < 4.0:
            continue
        imgs = x.get("mediumImageUrls") or []
        img = (imgs[0] if isinstance(imgs[0], str) else imgs[0].get("imageUrl")) if imgs else ""
        if not img:
            continue
        nm, sale = clean(name0)
        kd = kind_of(nm)
        if kd == "その他":
            for lab, rxk in TYPES:
                w = next((t for t in re.sub(r"【[^】]*】|\[[^\]]*\]|《[^》]*》", " ", name0).split() if re.search(rxk, t) and not re.fullmatch(r"[ァ-ヶー・]+", t)), "")
                if w:
                    nm = (nm + " " + w).strip(); kd = lab; break
        if kd == "その他":
            continue
        cand.append({"rank": rank, "kind": kd, "code": code, "name": nm[:44] + ("…" if len(nm) > 44 else ""), "off": int(sale or 0),
                     "sale": sale, "img": img.replace("_ex=128x128", "_ex=300x300"), "url": x.get("affiliateUrl") or x["itemUrl"], "brand": brand(name0)})
    cand.sort(key=lambda c: (-c["off"], c["rank"]))
    seen_nm, uniq = set(), []
    for c in cand:                                   # 色違い・サイズ違い（名前が同じ）は1つだけ
        k = re.sub(r"\s+", "", c["name"])[:18]
        if k not in seen_nm:
            seen_nm.add(k); uniq.append(c)
    chosen, kind_n, per_brand = [], {}, {}
    for limit in (1, 2, 8):                          # まず種類ごとに1点（割引の大きい順）→ 足りなければ種類2点まで → それでも足りなければ制限なし
        for c in uniq:
            if len(chosen) >= 8:
                break
            if c in chosen or kind_n.get(c["kind"], 0) >= limit or per_brand.get(c["brand"], 0) >= 2:
                continue
            chosen.append(c); kind_n[c["kind"]] = kind_n.get(c["kind"], 0) + 1; per_brand[c["brand"]] = per_brand.get(c["brand"], 0) + 1
    out = []
    for c in chosen:                                 # 並びは割引の大きい順
        d = api.item_detail(c["code"])                # 価格・ポイント・レビューを取り直す
        if not d or not (0 < d["price"] <= MAX_PRICE):
            continue
        pr = d["point_rate"]
        try:
            if d["point_end"] and datetime.strptime(d["point_end"][:16], "%Y-%m-%d %H:%M") < datetime.now():
                pr = 1
        except ValueError:
            pass
        out.append({**c, "price": d["price"], "pr": pr, "pt": d["price"] * pr // 100, "rc": d["review_count"], "av": d["review_avg"]})
    out.sort(key=lambda c: (-c["off"], c["rank"]))   # 並びは割引の大きい順
    return out


def render(items, stamp):
    cards = ""
    for it in items:
        sale = f"<span class=hot>SALE {it['sale']}%OFF</span>" if it["sale"] else ""
        cards += (f"<a class=card href='{esc(it['url'])}' rel='sponsored nofollow noopener' target=_blank>"
                  f"<span class=gtag>{esc(it['kind'])}" + (f"・ランキング{it['rank']}位" if it['rank'] < 999 else "") + f"</span>{sale}<img src='{esc(it['img'])}' alt='{esc(it['name'])}' loading=lazy>"
                  f"<span class=nm>{esc(it['name'])}</span><span class=yen>¥{it['price']:,}</span>"
                  f"<span class=pts>ポイント{it['pr']}倍（{it['pt']:,}pt）</span><span class=eff2>実質¥{it['price'] - it['pt']:,}</span>"
                  + (f"<span class=rv>⭐{it['av']}（{it['rc']:,}件）</span>" if it['rc'] else "<span class=rv>新着・レビューはこれから</span>")
                  + "<span class=go>楽天ファッションで見る →</span></a>")
    if not cards:
        return "<!--hubf--><!--/hubf-->"
    return ("<!--hubf--><section id=fashion style='margin-top:28px'><h2>👗 楽天ファッション（レディース）の人気アイテム</h2>"
            f"<p class=meta>楽天ファッションの商品から、割引の大きい順に（{MAX_PRICE:,}円まで・レビュー★4.0以上・福袋を除く）。コート・ニット・ワンピースなど種類を分けて8点、毎日すべて入れ替え。{esc(stamp)}時点（毎朝更新）。サイズ・色で価格が変わる場合があります。</p>"
            f"<div class=cards>{cards}</div>"
            "<p class=meta style='font-size:12px'>PR｜楽天ファッションへのリンクはアフィリエイト広告です。価格・ポイントは更新時点の表示で、商品ページで最新をご確認ください。</p></section><!--/hubf-->")


def main():
    cfg = load_config(Path(os.environ.get("CONFIG_BASE") or BASE))
    if not cfg:
        sys.exit("設定が読めません")
    api = Rakuten(cfg)
    items = pick(api)
    blk = render(items, datetime.now().strftime("%Y/%m/%d %H:%M"))
    p = SITE / "index.html"; t = p.read_text(encoding="utf-8")
    if "<!--hubf-->" in t:
        t2 = re.sub(r"<!--hubf-->.*?<!--/hubf-->", lambda m: blk, t, count=1, flags=re.S)
    elif "<!--hubart-->" in t:
        t2 = t.replace("<!--hubart-->", blk + "<!--hubart-->", 1)
    else:
        t2 = t
    if t2 != t:
        p.write_text(t2, encoding="utf-8")
    if items:
        _save_hist([i["code"] for i in items])
    print(f"ファッション {len(items)} 点", [i['kind'] for i in items])


if __name__ == "__main__":
    main()
