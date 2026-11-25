"""ブラックフライデー記事（articles/black-friday-2026.html）の「実質価格で選ぶ：楽天のおすすめ」の商品を、更新のたびに入れ替える
（2026-11-23 坂田さん「セールの商品も更新しといてな。都度」）。

楽天のランキングから、価格1,980〜9,800円・レビュー300件以上・★4.3以上の商品を集め、
ポイント倍率（検索APIで取り直した最新値）が高い順に12点。価格・ポイント・レビューは、その時点の値。
使い方: python bot/bf_article.py   （環境変数 SITE_DIR=サイトのフォルダ。キーは RAKUTEN_APP_ID など／手元は CONFIG_BASE=config.json のあるフォルダ）"""
import html, json, os, re, sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from rakuten import Rakuten, load_config  # noqa: E402
from run_daily import short_name          # noqa: E402

SITE = Path(os.environ.get("SITE_DIR") or BASE.parent).resolve()
ART = SITE / "articles" / "black-friday-2026.html"
MIN_PRICE, MAX_PRICE, MIN_REV, MIN_AVG, N = 1980, 999999999, 300, 4.3, 12   # 上限なし（2026-11-25 坂田さん）
esc = html.escape


def collect(api, cfg):
    pool, seen = [], set()
    for g in cfg["ranking_genres"]:
        for page in (1, 2, 3):
            try:
                items = api.ranking(g["genre_id"], page=page)
            except Exception as e:
                print("ランキング失敗", g.get("name"), str(e)[:60]); break
            for it in items or []:
                if (MIN_PRICE <= it["price"] <= MAX_PRICE and it["review_count"] >= MIN_REV and it["review_avg"] >= MIN_AVG
                        and it["item_code"] not in seen and it.get("image")):
                    seen.add(it["item_code"]); pool.append(it)
    pool.sort(key=lambda x: (-x.get("point_rate", 1), -x["review_count"]))
    out, heads = [], set()
    for it in pool[:60]:
        d = api.item_detail(it["item_code"])          # ランキングの倍率は古いことがあるので取り直す
        if not d:
            continue
        pr = d["point_rate"]
        try:
            if d["point_end"] and datetime.strptime(d["point_end"][:16], "%Y-%m-%d %H:%M") < datetime.now():
                pr = 1
        except ValueError:
            pass
        if not (MIN_PRICE <= d["price"] <= MAX_PRICE) or d["review_count"] < MIN_REV or d["review_avg"] < MIN_AVG:
            continue
        head = (short_name(it["name"], 60).split() or [""])[0]
        if len(head) >= 3 and head in heads:
            continue
        heads.add(head)
        out.append({**it, "price": d["price"], "point_rate": pr, "review_count": d["review_count"], "review_avg": d["review_avg"]})
    out.sort(key=lambda x: (-x["point_rate"], -x["review_count"]))
    return out[:N]


def render(items, day):
    cards = ""
    for it in items:
        pt = it["price"] * it["point_rate"] // 100
        nm = short_name(it["name"], 40)
        badge = f"<span class=badge>ポイント{it['point_rate']}倍</span>" if it["point_rate"] >= 2 else ""
        cards += (f"<a class=item href='{esc(it['url'])}' rel='sponsored nofollow noopener' target=_blank style='text-decoration:none'>"
                  f"<img src='{esc(it['image'])}' alt='{esc(nm)}' loading=lazy><div class=in>{badge}<b>{esc(nm)}</b>"
                  f"<span class=eff>実質¥{it['price'] - pt:,}〜</span>"
                  f"<span class=calc>価格¥{it['price']:,}〜 − {pt:,}pt（ポイント{it['point_rate']}倍・{day}時点）</span>"
                  f"<span class=rv>楽天レビュー{it['review_count']:,}件 ★{it['review_avg']}</span></div></a>")
    return f"<div class=grid>{cards}</div>"


def main():
    cfg = load_config(Path(os.environ.get("CONFIG_BASE") or BASE))
    if not cfg:
        sys.exit("設定が読めません")
    items = collect(Rakuten(cfg), cfg)
    if len(items) < 6:
        print("商品が少ないので、入れ替えません", len(items)); return
    day = datetime.now().strftime("%Y/%m/%d")
    t = ART.read_text(encoding="utf-8")
    new = render(items, day)
    t2, n = re.subn(r"(<h2 id=s4\s*>実質価格で選ぶ[^<]*</h2>.*?)<div class=grid>.*?</div>(?=\s*<h2 id=s5)", lambda m: m.group(1) + new, t, count=1, flags=re.S)
    if n != 1:
        print("差し替え先が見つかりません"); return
    if t2 != t:
        ART.write_text(t2, encoding="utf-8")
    print(f"ブラックフライデー記事の商品を入れ替え：{len(items)}点", [(i['point_rate'], i['review_count']) for i in items][:5])


if __name__ == "__main__":
    main()
