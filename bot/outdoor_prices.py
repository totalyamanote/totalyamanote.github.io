"""アウトドアブランド比較（articles/outdoor-brands-2026.html）の上着の価格を毎朝更新する（2026-11-16 坂田さんOK）。

- 記事の <div class=item>（1ブランド1着）ごとに、楽天ボタンの商品（店:番号）と Yahoo!ボタンの商品（店_商品コード）を API で引き直す。
  同じ型番の商品だけを扱う（リンク先の商品そのものを見るので、別の商品に入れ替わらない）。
- 書き換える所：実質価格・価格−ポイント・レビュー数、楽天/Yahoo!ボタンの価格、比較表の「2万円以内の上着」の欄（<!--op:店:番号-->〜<!--/op-->）。
- この記事だけ上限2万円（OPERATING_RULES.md 1章の例外）。楽天の販売価格が2万円を超えた日は、目立たせず「2万円超」と出す。
- 見つからない（売り切れ・削除）日は前の表示のまま残し、bot/data/outdoor_prices_last.json に記録する。
- Amazon ボタンは付けない（同じ型番か確かめられないため）。
使い方：python3 bot/outdoor_prices.py（クラウドでは daily.yml から。手元では ~/rakuten-affiliate/config.json を読む）
"""
import html
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from rakuten import SEARCH_URL, Rakuten, load_config  # noqa: E402
from yahoo import Yahoo  # noqa: E402

SITE = Path(os.environ.get("SITE_DIR") or BASE.parent).resolve()
DATA = Path(os.environ.get("DATA_DIR") or BASE / "data").resolve()
ART = SITE / "articles" / "outdoor-brands-2026.html"
CAP = 20000
esc = html.escape


def yen(n):
    return f"¥{n:,}"


def rakuten_item(api, shop, no):
    try:
        items = api._get(SEARCH_URL, {"itemCode": f"{shop}:{no}", "hits": 1}).get("Items", [])
    except Exception as e:  # noqa: BLE001
        print("楽天API失敗", shop, no, e)
        return None
    if not items:
        return None
    it = items[0].get("Item", items[0])
    if int(it.get("availability", 1) or 0) == 0:
        return None
    return it


def yahoo_item(yh, code, model):
    """型番で検索して、記事のボタンと同じ商品コード（店_商品）のものだけを返す。"""
    if not yh.ready:
        return None
    for q in (model, model.replace("-", "")):
        try:
            hits = yh.search(q, results=50)
        except Exception as e:  # noqa: BLE001
            print("Yahoo!API失敗", code, e)
            return None
        for h in hits:
            if h["item_code"] == "yahoo:" + code:
                return h
    return None


def main():
    if not ART.exists():
        print("記事がありません")
        return
    cfg = load_config(BASE) or load_config(BASE.parent.parent)
    if not cfg:
        print("APIキーが無いので更新しません")
        return
    api, yh = Rakuten(cfg), Yahoo(cfg)
    t = ART.read_text(encoding="utf-8")
    orig = t
    now = datetime.now()
    md = f"{now.month}/{now.day}"
    log = {"at": now.strftime("%Y-%m-%d %H:%M"), "items": []}

    def fix_item(m):
        b = m.group(0)
        name = re.search(r"class=iname>(.*?)</p>", b).group(1)
        model = re.search(r"（#?([^（）]+)）</p>", b)
        model = model.group(1) if model else ""
        r = re.search(r"rakuten\.co\.jp%2F([^%]+)%2Fi%2F(\d+)", b)
        y = re.search(r"vc_url=https%3A%2F%2Fstore\.shopping\.yahoo\.co\.jp%2F([^%]+)%2F([^%'&]+)\.html", b)
        rec = {"name": html.unescape(name), "rakuten": None, "yahoo": None}
        if r:
            it = rakuten_item(api, r.group(1), r.group(2))
            if it:
                price, rate = int(it["itemPrice"]), int(it.get("pointRate") or 1)
                pts = price * rate // 100
                rec["rakuten"] = price
                over = price > CAP
                eff = (f"<span class=eff>2万円超（{md}時点）</span>" if over
                       else f"<span class=eff>✅実質{yen(price - pts)}</span>")
                b = re.sub(r"<span class=eff>.*?</span>", eff, b, count=1)
                b = re.sub(r"<span class=calc>.*?</span>",
                           f"<span class=calc>価格{yen(price)} − {pts:,}pt（楽天・ポイント{rate}倍）</span>", b, count=1)
                if it.get("reviewCount"):
                    b = re.sub(r"<span class=rv>楽天・レビュー[^<]*</span>",
                               f"<span class=rv>楽天・レビュー{int(it['reviewCount']):,}件 ★{it.get('reviewAverage')}</span>", b, count=1)
                b = re.sub(r"(<a class=r [^>]*>.*?<small>)¥[\d,]+〜(</small><small class=pt>)[^<]*",
                           rf"\g<1>{yen(price)}〜\g<2>+{pts:,}pt（{rate}倍）", b, count=1, flags=re.S)
        if y and model:
            code = f"{y.group(1)}_{y.group(2)}"
            h = yahoo_item(yh, code, model)
            if h:
                rec["yahoo"] = h["price"]
                b = re.sub(r"(<a class=y [^>]*>.*?<small>)¥[\d,]+〜", rf"\g<1>{yen(h['price'])}〜", b, count=1, flags=re.S)
        log["items"].append(rec)
        return b

    t = re.sub(r"<div class=item>.*?</div></div></div>", fix_item, t, flags=re.S)
    table_fix = []
    # 比較表の欄：直した商品ブロックの楽天の販売価格を写す
    for rec_m in re.finditer(r"<div class=item>.*?</div></div></div>", t, re.S):
        b = rec_m.group(0)
        r = re.search(r"rakuten\.co\.jp%2F([^%]+)%2Fi%2F(\d+)", b)
        e = re.search(r"<span class=eff>(.*?)</span>", b)
        c = re.search(r"<span class=calc>価格¥([\d,]+)", b)
        if not (r and e and c):
            continue
        key = f"{r.group(1)}:{r.group(2)}"
        price = int(c.group(1).replace(",", ""))
        cell = "<span class=c>2万円超</span>" if price > CAP else f"<b>{yen(price)}</b>〜"
        table_fix.append(key)
        t = re.sub(rf"<!--op:{re.escape(key)}-->.*?<!--/op-->", f"<!--op:{key}-->{cell}<!--/op-->", t, count=1, flags=re.S)
    t = re.sub(r"上着の価格は楽天の販売価格（\d{1,2}/\d{1,2}時点）", f"上着の価格は楽天の販売価格（{md}時点・毎朝更新）", t)
    t = re.sub(r"上着の価格は楽天の販売価格（\d{1,2}/\d{1,2}時点・毎朝更新）", f"上着の価格は楽天の販売価格（{md}時点・毎朝更新）", t)
    if t != orig:
        ART.write_text(t, encoding="utf-8")
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "outdoor_prices_last.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    miss = [x["name"] for x in log["items"] if not x["rakuten"]]
    over = [x["name"] for x in log["items"] if (x["rakuten"] or 0) > CAP]
    print(f"アウトドア比較：{len(log['items'])}着を確認・表{len(table_fix)}欄"
          + (f"・楽天で見つからない {len(miss)}" if miss else "") + (f"・2万円超 {len(over)}" if over else ""))


if __name__ == "__main__":
    main()
