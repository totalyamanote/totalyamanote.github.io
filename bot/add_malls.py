"""比較記事の購入ボタンに『Yahoo!』を自動で足す。

記事の楽天ボタンから商品（店:商品番号）を特定 → 楽天APIで商品名・価格を取得 →
Yahoo!ショッピングAPIで同じ商品を探し（商品名の近さ＋価格の近さで厳しく判定）、
見つかった商品にだけ、楽天ボタンの隣に Yahoo! ボタン（バリューコマース経由）を足す。
似た別商品に飛ばさないよう、判定を満たさなければ足さない（楽天のみのまま）。

- 判定結果は bot/data/mall_map.json に記録（見つからなかった商品は7日あけて再検索）。
- 何度実行しても結果は同じ（既に Yahoo! ボタンがある所は触らない）。
- 必要な環境変数：RAKUTEN_*（楽天）、YAHOO_APP_ID。無ければ何もしない。
- Amazon は商品ごとの商品番号（ASIN）が要り、APIでは確実に特定できないため、ここでは足さない。
"""
import html
import json
import os
import re
import sys
import unicodedata
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rakuten import SEARCH_URL, Rakuten, load_config  # noqa: E402
from yahoo import Yahoo  # noqa: E402

BASE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("DATA_DIR") or BASE / "data").resolve()
SITE = Path(os.environ.get("SITE_DIR") or BASE.parent).resolve()
MAP = DATA / "mall_map.json"
RETRY_DAYS = 7
MIN_SIM = 0.62      # 商品名のバイグラム類似度（Dice）の下限
PRICE_TOL = 0.12    # 楽天との価格差の許容（±12%）
MAX_NEW = int(os.environ.get("MALLS_MAX_LOOKUPS", "60"))  # 1回の実行で新規に調べる商品数の上限

BTN_RE = re.compile(
    r"<a class='mini r' href='(?P<href>[^']*m\.rakuten\.co\.jp%2F(?P<shop>[^%']+)%2Fi%2F(?P<no>\d+)[^']*)'"
    r"[^>]*aria-label='(?P<label>[^']*?)を楽天で見る'>楽天</a>(?!<a class='mini y')")
CSS_Y = ".mini.y{background:#d4002a!important;color:#fff!important}"


def norm(s):
    s = unicodedata.normalize("NFKC", html.unescape(s or "")).lower()
    s = re.sub(r"【[^】]*】|\[[^\]]*\]|［[^］]*］|《[^》]*》|\([^)]*\)|（[^）]*）", " ", s)
    s = re.sub(r"[★☆♪♡!！?？/／|｜・,、。:：~〜\-ー\s]+", "", s)
    return s


def dice(a, b):
    ga = {a[i:i + 2] for i in range(len(a) - 1)}
    gb = {b[i:i + 2] for i in range(len(b) - 1)}
    return 2 * len(ga & gb) / (len(ga) + len(gb)) if ga and gb else 0.0


def pick_yahoo(r_name, r_price, hits):
    """楽天の商品に対応する Yahoo! の商品を選ぶ。名前が近く、価格も近いものだけ。無ければ None。"""
    base = norm(r_name)[:50]
    best, bs = None, 0.0
    for h in hits:
        if not h.get("price") or abs(h["price"] - r_price) > r_price * PRICE_TOL:
            continue
        s = dice(base, norm(h["name"])[:50])
        if s > bs:
            best, bs = h, s
    return best if bs >= MIN_SIM else None


def load_map():
    try:
        return json.loads(MAP.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def lookup(api, yh, shop, no):
    """(楽天の商品名・価格) → Yahoo! の購入リンク or ''（見つからない）。API失敗時は None。"""
    try:
        items = api._get(SEARCH_URL, {"itemCode": f"{shop}:{no}", "hits": 1}).get("Items", [])
    except Exception as e:  # noqa: BLE001
        print(f"  楽天API失敗 {shop}:{no} {e}")
        return None
    if not items:
        return ""
    it = items[0]
    r_price = int(it["itemPrice"])
    q = re.sub(r"【[^】]*】|\[[^\]]*\]|《[^》]*》|[★☆♪]", " ", unicodedata.normalize("NFKC", it["itemName"]))
    q = " ".join(q.split())[:60]
    try:
        hits = yh.search(q, price_from=int(r_price * (1 - PRICE_TOL)), price_to=int(r_price * (1 + PRICE_TOL)), results=30)
    except Exception as e:  # noqa: BLE001
        print(f"  Yahoo API失敗 {shop}:{no} {e}")
        return None
    h = pick_yahoo(it["itemName"], r_price, hits)
    return h["url"] if h else ""


def ensure_css(t):
    return t if "mini.y" in t else t.replace("</style>", CSS_Y + "</style>", 1)


def main():
    cfg = load_config(BASE)
    yh = Yahoo(cfg)
    if not cfg or not yh.ready:
        print("Yahoo!APIキーが無いので何もしません")
        return 0
    api = Rakuten(cfg)
    mp = load_map()
    today = date.today()
    arts = sorted((SITE / "articles").glob("*.html"))
    texts = {f: f.read_text(encoding="utf-8") for f in arts}
    # 記事に出てくる楽天商品を集める
    codes = {}
    for t in texts.values():
        for m in BTN_RE.finditer(t):
            codes[(m["shop"], m["no"])] = 1
    new = 0
    for shop, no in codes:
        k = f"{shop}:{no}"
        rec = mp.get(k)
        if rec and (rec.get("y") or date.fromisoformat(rec["t"]) > today - timedelta(days=RETRY_DAYS)):
            continue
        if new >= MAX_NEW:
            break
        new += 1
        r = lookup(api, yh, shop, no)
        if r is None:
            continue
        mp[k] = {"y": r, "t": today.isoformat()}
        print(f"  {k}: {'Yahoo!あり' if r else '見つからず（楽天のみ）'}")
    MAP.write_text(json.dumps(mp, ensure_ascii=False, indent=1), encoding="utf-8")
    # ボタンを足す
    added = 0
    for f, t in texts.items():
        def sub(m):
            nonlocal added
            y = (mp.get(f"{m['shop']}:{m['no']}") or {}).get("y")
            if not y:
                return m.group(0)
            added += 1
            label = m["label"]
            btn = (f"<a class='mini y' href='{html.escape(y, quote=True)}' rel='sponsored nofollow noopener' target=_blank "
                   f"aria-label='{label}をYahoo!で見る'>Yahoo!</a>")
            return m.group(0) + btn
        n = BTN_RE.sub(sub, t)
        if n != t:
            f.write_text(ensure_css(n), encoding="utf-8")
    print(f"Yahoo!ボタン: 新規に調べた商品{new} / 追加したボタン{added}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
