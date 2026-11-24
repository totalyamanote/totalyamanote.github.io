"""ふるさと納税ページ（site/furusato/index.html）の商品の段を、毎朝作り直す（2026-11-25 坂田さん「ふるさと納税のページを作成・物販のふるさと納税は移籍」）。
楽天ウェブサービス（IchibaItem/Search）で、ふるさと納税の返礼品を種類ごとに検索し、寄付額1万円未満・レビュー10件以上・★4.0以上のものを、
ポイント倍率が高い順（同じなら★のレビュー件数が多い順）に出す。事実だけ（返礼品名・寄付額・ポイント倍率・レビュー）。
site/furusato/index.html の <!--furu-->〜<!--/furu--> を差し替える。使い方: python bot/furusato.py（環境変数 SITE_DIR・キーは RAKUTEN_APP_ID など／手元は config.json）"""
import html, os, re, sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from rakuten import Rakuten, load_config  # noqa: E402

SITE = Path(os.environ.get("SITE_DIR") or BASE.parent).resolve()
MAX_DONATION = 9999   # 寄付額は1万円未満（運用ルール）
CATS = [("お米・パン・麺", ["米 5kg", "パン", "ラーメン うどん"]), ("お肉", ["牛肉", "豚肉", "ハンバーグ", "鶏肉 からあげ"]), ("海鮮・魚", ["ほたて", "干物", "鮭 いくら", "うなぎ"]),
        ("フルーツ・野菜", ["みかん", "いちご", "りんご", "野菜"]), ("スイーツ・飲み物", ["スイーツ", "お菓子", "ジュース コーヒー", "お茶"]), ("日用品", ["トイレットペーパー", "ティッシュ", "洗剤", "タオル"])]
esc = html.escape


def short(n, k=44):
    n = re.sub(r"【[^】]*】|\[[^\]]*\]|＼[^／]*／|《[^》]*》|★|☆|◆|♪|\s+", " ", n).strip()
    return n[:k] + ("…" if len(n) > k else "")


def key(n):
    return re.sub(r"[\s【】\[\]（）()0-9a-zA-Zｇｋｍｌ×x]", "", re.sub(r"【[^】]*】", "", n))[:14]


def cat_items(api, kws):
    cands = []
    for kw in kws:
        for page in (1, 2):
            try:
                batch = api.search_cheapest("ふるさと納税 " + kw, 1000, MAX_DONATION, page=page, sort="-reviewCount")
            except Exception:
                break
            cands += [it for it in batch if "ふるさと納税" in it["name"] and it["review_count"] >= 10 and it["review_avg"] >= 4.0 and 1000 <= it["price"] <= MAX_DONATION and it.get("image")]
            if len(batch) < 30:
                break
    cands.sort(key=lambda it: (-it["point_rate"], -it["review_count"]))
    out, seen = [], set()
    for it in cands:
        k = key(it["name"])
        if k in seen or any(it["item_code"] == o["item_code"] for o in out):
            continue
        seen.add(k); out.append(it)
        if len(out) == 8:
            break
    return out


def card(it):
    badge = f"<span class=hot>🔥ポイント{it['point_rate']}倍</span>" if it["point_rate"] >= 2 else ""
    return (f"<a class=card href='{esc(it['url'])}' rel='sponsored nofollow noopener' target=_blank>"
            f"<span class=gtag>{esc(it['shop'][:20])}</span>{badge}<img src='{esc(it['image'])}' alt='{esc(short(it['name'], 40))}' loading=lazy>"
            f"<span class=nm>{esc(short(it['name'].replace('【ふるさと納税】', ''), 40))}</span><span class=yen>寄付額 ¥{it['price']:,}</span>"
            f"<span class=pts>ポイント{it['point_rate']}倍（{it['price'] * it['point_rate'] // 100:,}pt）</span>"
            f"<span class=rv>⭐{it['review_avg']}（{it['review_count']:,}件）</span><span class=go>楽天ふるさと納税で見る →</span></a>")


def main():
    cfg = load_config(Path(os.environ.get("CONFIG_BASE") or BASE))
    if not cfg:
        sys.exit("設定が読めません")
    api = Rakuten(cfg)
    stamp = datetime.now().strftime("%Y/%m/%d %H:%M")
    secs, total = "", 0
    for ci, (label, kws) in enumerate(CATS):
        items = cat_items(api, kws)
        if len(items) >= 4:
            total += len(items)
            secs += f"<section id='c{ci}' style='margin-top:20px'><h2>{esc(label)}</h2><div class=cards>{''.join(card(i) for i in items)}</div></section>"
    if not secs:
        print("ふるさと納税 0 点（前の内容のまま）")
        return
    blk = (f"<!--furu--><p class=meta>楽天ふるさと納税の返礼品を、種類ごとに、ポイント倍率が高い順に（寄付額1万円未満・レビュー10件以上・★4.0以上）。{esc(stamp)}時点。"
           "寄付額・ポイントは更新時点の表示で、返礼品のページで最新を確認してください。</p>" + secs +
           "<p class=meta style='font-size:12px'>PR｜楽天市場へのリンクはアフィリエイト広告です。控除の上限額は年収や家族構成で変わります。寄付の前に楽天ふるさと納税のシミュレーターで確認してください。</p><!--/furu-->")
    p = SITE / "furusato" / "index.html"
    if not p.exists():
        print("furusato/index.html がありません"); return
    t = p.read_text(encoding="utf-8")
    t2 = re.sub(r"<!--furu-->.*?<!--/furu-->", lambda m: blk, t, count=1, flags=re.S)
    if t2 != t:
        p.write_text(t2, encoding="utf-8")
    # 物販トップからは外す（2026-11-25 坂田さん「物販のふるさと納税は移籍」）
    print(f"ふるさと納税 {total} 点")


if __name__ == "__main__":
    main()
