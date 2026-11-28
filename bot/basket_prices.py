"""バッシュ シリーズ比較（articles/basketball-shoes.html）の価格を毎朝更新する（2026-11-28 坂田さん「バッシュのシリーズ 記事化して」）。

- 載せる商品（楽天の itemCode と Yahoo!の商品コード）は bot/data/basket_items.json。同じ型番の同じ商品だけを引き直す。
- 書き換える所は、記事の中の <!--bp:キー-->…<!--/bp-->（商品の価格とボタン）と <!--bt:キー-->…<!--/bt-->（比較表の欄）だけ。
- 時刻は、その商品を実際に取り直したときだけ新しくする。取り直しに失敗した店は前の表示のまま。
  在庫なし（検索に出ない）の店は「在庫を確認できません」と出して、価格は出さない。
- Amazon のボタンは付けない（同じ商品か確かめられないため）。
使い方：python3 bot/basket_prices.py（クラウドでは daily.yml から。手元では ~/rakuten-affiliate/config.json を読む）
"""
import html
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from rakuten import SEARCH_URL, Rakuten, load_config  # noqa: E402
from yahoo import Yahoo  # noqa: E402

SITE = Path(os.environ.get("SITE_DIR") or BASE.parent).resolve()
DATA = Path(os.environ.get("DATA_DIR") or BASE / "data").resolve()
ART = SITE / "articles" / "basketball-shoes.html"
ITEMS = BASE / "data" / "basket_items.json"
JST = timezone(timedelta(hours=9))
esc = lambda s: html.escape(str(s), quote=True)


def yen(n):
    return f"¥{n:,}"


def rakuten_get(api, code):
    """(状態, データ)。状態は ok / none（在庫なし）/ error（取り直せず）。"""
    try:
        items = api._get(SEARCH_URL, {"itemCode": code, "hits": 1}).get("Items", [])
    except Exception as e:  # noqa: BLE001
        print("楽天API失敗", code, e)
        return "error", None
    if not items:
        return "none", None
    it = items[0].get("Item", items[0])
    if int(it.get("availability", 1) or 0) == 0:
        return "none", None
    price, rate = int(it["itemPrice"]), int(it.get("pointRate") or 1)
    return "ok", {"price": price, "pt": price * rate // 100, "note": f"ポイント{rate}倍", "url": it.get("affiliateUrl") or it.get("itemUrl"),
                  "rv": int(it.get("reviewCount") or 0), "avg": float(it.get("reviewAverage") or 0),
                  "ship": "送料込み" if int(it.get("postageFlag", 1)) == 0 else "送料はお店で確認"}


def yahoo_get(yh, code, queries):
    if not yh.ready:
        return "error", None
    for q in queries:
        try:
            hits = yh.search(q, results=50)
        except Exception as e:  # noqa: BLE001
            print("Yahoo!API失敗", code, e)
            return "error", None
        for h in hits:
            if h["item_code"] == "yahoo:" + code:
                return "ok", {"price": h["price"], "pt": h["point"], "note": "通常分とLINEヤフー連携分", "url": h["url"],
                              "rv": h["review_count"], "avg": h["review_avg"], "ship": "送料無料" if h["free_shipping"] else "送料はお店で確認"}
    return "none", None


def fetch(api, yh, item):
    out = {}
    if item.get("rakuten"):
        out["r"] = rakuten_get(api, item["rakuten"]["code"])
    if item.get("yahoo"):
        out["y"] = yahoo_get(yh, item["yahoo"]["code"], item["yahoo"]["queries"])
    return out


def stars(res):
    """楽天とYahoo!の星を、件数で重みをつけて合わせる。"""
    got = [d for s, d in res.values() if s == "ok" and d["rv"]]
    n = sum(d["rv"] for d in got)
    if not n:
        return "レビューはまだありません"
    return f"★{sum(d['avg'] * d['rv'] for d in got) / n:.1f}（{n:,}件・楽天とYahoo!の合計）"


def block(item, res, stamp):
    rows = ""
    for key, shop_label, cls in (("r", "楽天市場", "br"), ("y", "Yahoo!ショッピング", "by")):
        if key not in res:
            continue
        state, d = res[key]
        shop = item["rakuten" if key == "r" else "yahoo"]["shop"]
        if state != "ok":
            rows += f"<div class=bsrow><p class=bsout>{shop_label}（{esc(shop)}）：在庫を確認できません</p></div>"
            continue
        rows += (f"<div class=bsrow><a class='bsbtn {cls}' href='{esc(d['url'])}' rel='sponsored nofollow noopener' target=_blank>"
                 f"<span>{shop_label}で見る</span><b>{yen(d['price'])}</b></a>"
                 f"<p class=bssub>{esc(shop)}｜実質<b>{yen(d['price'] - d['pt'])}</b>（{d['pt']:,}pt・{d['note']}）｜{d['ship']}</p></div>")
    if len(res) == 1:
        rows += "<p class=bssub>この商品は楽天のみの掲載です。</p>"
    return f"{rows}<p class=bstime>{stars(res)}<br>価格・ポイントは{stamp}時点。サイズごとの在庫はお店のページで確認してください。</p>"


def cell(item, res):
    ok = [(d["price"] - d["pt"], d, k) for k, (s, d) in res.items() if s == "ok"]
    if not ok:
        return "<span class=bsout>在庫を確認できません</span>"
    eff, d, k = min(ok, key=lambda x: x[0])
    links = " ".join(f"<a href='{esc(res[k2][1]['url'])}' rel='sponsored nofollow noopener' target=_blank>{lab}</a>"
                     for k2, lab in (("r", "楽天"), ("y", "Yahoo!")) if k2 in res and res[k2][0] == "ok")
    return f"<b class=bseff>{yen(eff)}</b><span class=bsl>{links}</span>"


def replace(t, tag, key, body):
    return re.sub(rf"<!--{tag}:{key}-->.*?<!--/{tag}-->", lambda m: f"<!--{tag}:{key}-->{body}<!--/{tag}-->", t, flags=re.S)


def main():
    if not ART.exists():
        print("記事がありません")
        return
    cfg = load_config(BASE) or load_config(BASE.parent.parent)
    if not cfg:
        print("APIキーが無いので更新しません")
        return
    api, yh = Rakuten(cfg), Yahoo(cfg)
    items = json.loads(ITEMS.read_text(encoding="utf-8"))
    t = orig = ART.read_text(encoding="utf-8")
    now = datetime.now(JST)
    stamp = f"{now.year}/{now.month}/{now.day} {now:%H:%M}"
    log, fresh = {"at": stamp, "items": {}}, 0
    for item in items:
        res = fetch(api, yh, item)
        log["items"][item["key"]] = {k: {"state": s, "price": d and d["price"]} for k, (s, d) in res.items()}
        if any(s == "error" for s, _ in res.values()):
            continue  # 片方でも取り直せなかった商品は、前の表示と前の時刻のまま
        t = replace(t, "bp", item["key"], block(item, res, stamp))
        t = replace(t, "bt", item["key"], cell(item, res))
        fresh += 1
    if fresh == len(items):
        md = f"{now.month}/{now.day}"
        t = re.sub(r"【\d{1,2}/\d{1,2}更新】", f"【{md}更新】", t)
        t = re.sub(r"(<!--upd--><p[^>]*>更新日：)\d{4}-\d{2}-\d{2}", rf"\g<1>{now:%Y-%m-%d}", t)
        t = re.sub(r'("dateModified": ?")\d{4}-\d{2}-\d{2}', rf"\g<1>{now:%Y-%m-%d}", t)
    if t != orig:
        ART.write_text(t, encoding="utf-8")
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "basket_prices_last.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    none = [f"{k}:{s}" for k, v in log["items"].items() for s, x in v.items() if x["state"] != "ok"]
    print(f"バッシュ比較：{fresh}/{len(items)}商品を更新" + (f"・取れず/在庫なし {none}" if none else ""))


if __name__ == "__main__":
    main()
