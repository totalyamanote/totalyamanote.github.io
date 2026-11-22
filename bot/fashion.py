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
BAG_NG = re.compile(r"福袋|HAPPY BOX|福箱|ラッキーバッグ|LUCKY")


def kind_of(name):
    for label, rx in TYPES:
        if re.search(rx, name):
            return label
    return "その他"


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
    """売れそうな順＝楽天のレディースファッションのランキングで上位の商品。種類（コート・ニット・ワンピースなど）を散らして8点。"""
    cand = []
    for x in ranked(api):
        price = int(x.get("itemPrice") or 0)
        if not (0 < price <= MAX_PRICE) or BAG_NG.search(x["itemName"]):
            continue
        imgs = x.get("mediumImageUrls") or []
        img = (imgs[0] if isinstance(imgs[0], str) else imgs[0].get("imageUrl")) if imgs else ""
        if not img:
            continue
        nm, sale = clean(x["itemName"])
        kd = kind_of(nm)
        if kd == "その他":                                      # ブランド名だけになるものは、種類の言葉を含む語を元の名前から足す
            for lab, rxk in TYPES:
                w = next((t for t in re.sub(r"【[^】]*】|\[[^\]]*\]|《[^》]*》", " ", x["itemName"]).split() if re.search(rxk, t) and not re.fullmatch(r"[ァ-ヶー・]+", t)), "")
                if w:
                    nm = (nm + " " + w).strip(); kd = lab; break
        if kd == "その他":
            continue
        rc0, av0 = int(x.get("reviewCount") or 0), float(x.get("reviewAverage") or 0)
        if rc0 < 10 or av0 < 4.0:                               # 売れそう＝順位が高く、レビューも一定数あって評価が低くないもの
            continue
        cand.append({"rank": int(x["rank"]), "kind": kd, "code": x["itemCode"], "name": nm[:44] + ("…" if len(nm) > 44 else ""),
                     "sale": sale, "img": img.replace("_ex=128x128", "_ex=300x300"), "url": x.get("affiliateUrl") or x["itemUrl"], "brand": brand(x["itemName"])})
    chosen, used_kind, per_brand = [], set(), {}
    for c in cand:                                   # まず種類ごとに、いちばん順位が高いもの
        if c["kind"] in used_kind or c["kind"] == "その他" or per_brand.get(c["brand"], 0) >= 3:
            continue
        used_kind.add(c["kind"]); per_brand[c["brand"]] = per_brand.get(c["brand"], 0) + 1; chosen.append(c)
    for c in cand:                                   # 足りなければ順位の高い順に
        if len(chosen) >= 8:
            break
        if c not in chosen and per_brand.get(c["brand"], 0) < 3:
            per_brand[c["brand"]] = per_brand.get(c["brand"], 0) + 1; chosen.append(c)
    out = []
    if len(chosen) < 8:                                  # 足りなければ、レビューが多い順の検索（種類ごと）で補う
        have = {c["code"] for c in chosen}
        for kw in ("ニット", "コート", "ワンピース", "カーディガン", "スカート", "パンツ"):
            try:
                dd = api._get(SEARCH_URL, {"shopCode": SHOP, "keyword": kw, "sort": "-reviewCount", "hits": 10, "availability": 1})
            except Exception:
                continue
            for y in dd.get("Items", []):
                y = y.get("Item", y)
                pz = int(y.get("itemPrice") or 0); im = y.get("mediumImageUrls") or []
                if y["itemCode"] in have or not (0 < pz <= MAX_PRICE) or BAG_NG.search(y["itemName"]) or not im or kw not in clean(y["itemName"])[0] \
                        or int(y.get("reviewCount") or 0) < 50 or float(y.get("reviewAverage") or 0) < 4.0:
                    continue
                nm2, sale2 = clean(y["itemName"]); have.add(y["itemCode"])
                chosen.append({"rank": 999, "kind": kw, "code": y["itemCode"], "name": nm2[:44], "sale": sale2,
                               "img": (im[0] if isinstance(im[0], str) else im[0].get("imageUrl")).replace("_ex=128x128", "_ex=300x300"),
                               "url": y.get("affiliateUrl") or y["itemUrl"], "brand": brand(y["itemName"])})
                break
            if len(chosen) >= 8:
                break
    for c in sorted(chosen, key=lambda c: c["rank"])[:8]:
        d = api.item_detail(c["code"])                # 価格・ポイント・レビューを検索APIで取り直す（ランキングは古いことがある）
        if not d or not (0 < d["price"] <= MAX_PRICE):
            continue
        pr = d["point_rate"]
        try:
            if d["point_end"] and datetime.strptime(d["point_end"][:16], "%Y-%m-%d %H:%M") < datetime.now():
                pr = 1
        except ValueError:
            pass
        out.append({**c, "price": d["price"], "pr": pr, "pt": d["price"] * pr // 100, "rc": d["review_count"], "av": d["review_avg"]})
    return out


def render(items, stamp):
    cards = ""
    for it in items:
        sale = f"<span class=hot>SALE {it['sale']}%OFF</span>" if it["sale"] else ""
        cards += (f"<a class=card href='{esc(it['url'])}' rel='sponsored nofollow noopener' target=_blank>"
                  f"<span class=gtag>{esc(it['kind'])}" + (f"・ランキング{it['rank']}位" if it['rank'] < 999 else "・レビュー多い") + f"</span>{sale}<img src='{esc(it['img'])}' alt='{esc(it['name'])}' loading=lazy>"
                  f"<span class=nm>{esc(it['name'])}</span><span class=yen>¥{it['price']:,}</span>"
                  f"<span class=pts>ポイント{it['pr']}倍（{it['pt']:,}pt）</span><span class=eff2>実質¥{it['price'] - it['pt']:,}</span>"
                  + (f"<span class=rv>⭐{it['av']}（{it['rc']:,}件）</span>" if it['rc'] else "<span class=rv>新着・レビューはこれから</span>")
                  + "<span class=go>楽天ファッションで見る →</span></a>")
    if not cards:
        return "<!--hubf--><!--/hubf-->"
    return ("<!--hubf--><section id=fashion style='margin-top:28px'><h2>👗 楽天ファッション（レディース）の人気アイテム</h2>"
            f"<p class=meta>楽天のレディースファッション売れ筋ランキングで上位の、楽天ファッションの商品から（{MAX_PRICE:,}円まで・福袋を除く）。コート・ニット・ワンピースなど種類を分けて8点。{esc(stamp)}時点（毎朝更新）。サイズ・色で価格が変わる場合があります。</p>"
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
    print(f"ファッション {len(items)} 点", [i['kind'] for i in items])


if __name__ == "__main__":
    main()
