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
from rakuten import SEARCH_URL, Rakuten, load_config  # noqa: E402

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


def pick(api):
    out, seen, per_brand = [], set(), {}
    for kw in KINDS:
        try:
            d = api._get(SEARCH_URL, {"shopCode": SHOP, "keyword": kw, "sort": "-reviewCount", "hits": 20, "availability": 1})
        except Exception as e:
            print("検索失敗", kw, str(e)[:80]); continue
        for x in d.get("Items", []):
            x = x.get("Item", x)
            price = int(x.get("itemPrice") or 0); rc = int(x.get("reviewCount") or 0); av = float(x.get("reviewAverage") or 0)
            imgs = x.get("mediumImageUrls") or []
            img = (imgs[0] if isinstance(imgs[0], str) else imgs[0].get("imageUrl")) if imgs else ""
            if not (0 < price <= MAX_PRICE and rc >= MIN_REVIEWS and av >= MIN_AVG and img) or x["itemCode"] in seen:
                continue
            nm, sale = clean(x["itemName"]); b = brand(x["itemName"])
            if kw not in nm:   # 種類の言葉が（整えた）商品名に入っているものだけ（ブランド名に似た語だけの一致を除く）
                continue
            if per_brand.get(b, 0) >= 3:
                continue
            seen.add(x["itemCode"]); per_brand[b] = per_brand.get(b, 0) + 1
            pr = int(x.get("pointRate") or 1)
            out.append({"kind": kw, "name": nm[:44] + ("…" if len(nm) > 44 else ""), "sale": sale, "price": price, "pr": pr, "pt": price * pr // 100,
                        "rc": rc, "av": av, "img": img.replace("_ex=128x128", "_ex=300x300"), "url": x.get("affiliateUrl") or x["itemUrl"]})
            break
    return out


def render(items, stamp):
    cards = ""
    for it in items:
        sale = f"<span class=hot>SALE {it['sale']}%OFF</span>" if it["sale"] else ""
        cards += (f"<a class=card href='{esc(it['url'])}' rel='sponsored nofollow noopener' target=_blank>"
                  f"<span class=gtag>{esc(it['kind'])}</span>{sale}<img src='{esc(it['img'])}' alt='{esc(it['name'])}' loading=lazy>"
                  f"<span class=nm>{esc(it['name'])}</span><span class=yen>¥{it['price']:,}</span>"
                  f"<span class=pts>ポイント{it['pr']}倍（{it['pt']:,}pt）</span><span class=eff2>実質¥{it['price'] - it['pt']:,}</span>"
                  f"<span class=rv>⭐{it['av']}（{it['rc']:,}件）</span><span class=go>楽天ファッションで見る →</span></a>")
    if not cards:
        return "<!--hubf--><!--/hubf-->"
    return ("<!--hubf--><section id=fashion style='margin-top:28px'><h2>👗 楽天ファッション（レディース）の人気アイテム</h2>"
            f"<p class=meta>楽天ファッションで、レビューが多い順（{MIN_REVIEWS}件以上・★{MIN_AVG}以上・{MAX_PRICE:,}円まで）に、種類ごとに1点ずつ。{esc(stamp)}時点（毎朝更新）。サイズ・色で価格が変わる場合があります。</p>"
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
