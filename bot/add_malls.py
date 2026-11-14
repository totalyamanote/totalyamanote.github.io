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
import time
import unicodedata
import urllib.error
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
BTN2_RE = re.compile(
    r"<a class=r href='(?P<href>[^']*m\.rakuten\.co\.jp%2F(?P<shop>[^%']+)%2Fi%2F(?P<no>\d+)[^']*)'"
    r"[^>]*>楽天で見る</a>(?!<a class=y)")
CSS_Y = ".mini.y{background:#d4002a!important;color:#fff!important}"
CSS_Y2 = ".btns .y{background:#d4002a!important;color:#fff!important}"
# 「楽天のポイント高倍率まとめ」は楽天ポイントが主題の記事なので Yahoo! は足さない
SKIP = {"point-up.html"}


def norm(s):
    s = unicodedata.normalize("NFKC", html.unescape(s or "")).lower()
    s = re.sub(r"【[^】]*】|\[[^\]]*\]|［[^］]*］|《[^》]*》|\([^)]*\)|（[^）]*）", " ", s)
    s = re.sub(r"[★☆♪♡!！?？/／|｜・,、。:：~〜\-ー\s]+", "", s)
    return s


def dice(a, b):
    ga = {a[i:i + 2] for i in range(len(a) - 1)}
    gb = {b[i:i + 2] for i in range(len(b) - 1)}
    return 2 * len(ga & gb) / (len(ga) + len(gb)) if ga and gb else 0.0


MODEL_RE = re.compile(r"[A-Z]{1,6}-?\d{2,}[A-Z0-9-]*|\d{2,}[A-Z]{1,3}-[A-Z0-9]+")


def models(s):
    """商品名の型番らしい語（DS-150・CPC5・300S-B など。4文字以上）。"""
    s = unicodedata.normalize("NFKC", html.unescape(s or "")).upper()
    return {m.replace("-", "") for m in MODEL_RE.findall(s) if len(m.replace("-", "")) >= 4}


QTY_RE = re.compile(r"(\d+(?:\.\d+)?)(ml|kg|g|l|枚|個|本|ロール|パック|袋|包|cm|mm|m|セット|倍|入|組|足|巻|日分|粒|錠)")


def qty(s):
    """商品名の数量・規格（800枚・480ml・170m・3.4倍 など）。"""
    s = unicodedata.normalize("NFKC", html.unescape(s or "")).lower().replace(",", "")
    return {a + b for a, b in QTY_RE.findall(s)}


def judge(r_name, r_price, h, toks):
    """Yahoo!の商品 h が楽天の商品と同じかを判定。同じなら点数、違えば None。
    規格（数量）が食い違えば別商品。名前がほぼ同じ・型番が同じなら、店ごとの価格差（±45%）は許容。
    それ以外は価格も近い（±12%）ことを求める。"""
    if not h.get("price") or not r_price:
        return None
    d = abs(h["price"] - r_price) / r_price
    ny = norm(h["name"])
    dc = dice(norm(r_name)[:50], ny[:50])
    cov = sum(1 for t in toks if norm(t) in ny) / len(toks) if toks else 0.0
    qa, qb = qty(r_name), qty(h["name"])
    if qa and qb and not (qa & qb):
        return None
    same_model = bool(models(r_name) & models(h["name"]))
    ok = ((dc >= 0.85 and d <= 0.45) or (same_model and d <= 0.45)
          or (dc >= MIN_SIM and d <= PRICE_TOL)
          or (len(toks) >= 4 and cov >= 0.8 and dc >= 0.4 and d <= PRICE_TOL)
          or (len(toks) >= 3 and cov >= 0.6 and d <= 0.03))
    return (dc + cov - d) if ok else None


def pick_yahoo(r_name, r_price, hits):
    """楽天の商品に対応する Yahoo! の商品を選ぶ。無ければ None。"""
    toks = core_tokens(r_name)
    best, bs = None, None
    for h in hits:
        sc = judge(r_name, r_price, h, toks)
        if sc is not None and (bs is None or sc > bs):
            best, bs = h, sc
    return best


NOISE = re.compile(r"送料無料|楽天\S*位|レビュー\S*|公式|新登場|ポイント\S*|セット買い\S*|TVCM\S*|訳アリ|あす楽|[0-9]+[％%]\s*OFF|OFF|国産|大容量|業務用")


def core_tokens(name):
    """商品名から宣伝文句・記号を除いた語のリスト。"""
    s = unicodedata.normalize("NFKC", html.unescape(name or ""))
    s = re.sub(r"【[^】]*】|\[[^\]]*\]|《[^》]*》|＼[^／]*／|[★☆♪]", " ", s)
    s = re.sub(r"[【】\[\]《》＼／（）()「」『』]", " ", NOISE.sub(" ", s))
    return [t for t in s.split() if len(t) >= 2]


def queries(name):
    """Yahoo!検索の語：先頭の4語→3語→2語の順（長いと0件になるため）。最後に先頭1語（4文字以上のとき）。"""
    toks = core_tokens(name)
    out = []
    for n in (4, 3, 2, 1):
        if n == 1 and (not toks or len(toks[0]) < 4):
            continue
        q = " ".join(toks[:n])
        if q and q not in out:
            out.append(q)
    return out


def load_map():
    try:
        return json.loads(MAP.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def search_retry(yh, q):
    """Yahoo!検索。呼び出し過多（429）のときは待って再試行する。"""
    for wait in (0, 15, 40):
        time.sleep(1.2 + wait)
        try:
            return yh.search(q, results=50)
        except urllib.error.HTTPError as e:
            if e.code != 429 or wait == 40:
                raise
            print(f"  429（呼び出し過多）→ {15 if wait == 0 else 40}秒待って再試行")


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
    h, hits, used = None, [], ""
    for q in queries(it["itemName"]):
        try:
            hits = search_retry(yh, q)
        except Exception as e:  # noqa: BLE001
            print(f"  Yahoo API失敗 {shop}:{no} {e}")
            return None
        used = q
        h = pick_yahoo(it["itemName"], r_price, hits)
        if h:
            break
    if h:
        print(f"    採用: 楽天[{it['itemName'][:28]}] ¥{r_price:,} ⇔ Yahoo[{h['name'][:28]}] ¥{h['price']:,}（検索語: {used}）")
    else:  # 診断：一番近かった候補（条件を調整する材料）
        base = norm(it["itemName"])[:50]
        c = max(hits, key=lambda x: dice(base, norm(x["name"])[:50]), default=None)
        print(f"    不採用: 楽天[{it['itemName'][:34]}] ¥{r_price:,} / 検索語「{used}」候補{len(hits)}件"
              + (f" / 最も近い: {c['name'][:34]} ¥{c['price']:,} 類似{dice(base, norm(c['name'])[:50]):.2f}" if c else ""))
    return h["url"] if h else ""


def ensure_css(t):
    if "mini y" in t and "mini.y" not in t:
        t = t.replace("</style>", CSS_Y + "</style>", 1)
    if "<a class=y " in t and ".btns .y" not in t:
        t = t.replace("</style>", CSS_Y2 + "</style>", 1)
    return t


AMAZON_MAP = DATA / "amazon_map.json"
CSS_A = ".mini.a{background:#ff9900!important;color:#111!important}"
CSS_A2 = ".btns .a{background:#ff9900;color:#111}"


def add_amazon(tag):
    """bot/data/amazon_map.json にある商品の楽天ボタン（＋Yahoo!）の隣に Amazon ボタンを足す。APIキー不要・何度実行しても同じ。"""
    try:
        amap = {k: v["asin"] for k, v in json.loads(AMAZON_MAP.read_text(encoding="utf-8")).items() if isinstance(v, dict)}
    except (FileNotFoundError, json.JSONDecodeError):
        return 0
    n = 0
    for f in sorted((SITE / "articles").glob("*.html")):
        if f.name in SKIP:
            continue
        t = f.read_text(encoding="utf-8")

        def mk(kind):
            def sub(m):
                nonlocal n
                asin = amap.get(f"{m['shop']}:{m['no']}")
                tail = m.string[m.end():m.end() + 40]
                if not asin or tail.startswith("<a class='mini a'") or tail.startswith("<a class=a "):
                    return m.group(0)
                n += 1
                url = f"https://www.amazon.co.jp/dp/{asin}?tag={tag}"
                if kind == "mini":
                    return (m.group(0) + f"<a class='mini a' href='{url}' rel='sponsored nofollow noopener' target=_blank "
                            f"aria-label='{m['label']}をAmazonで見る'>Amazon</a>")
                return m.group(0) + f"<a class=a href='{url}' rel='sponsored nofollow noopener' target=_blank>Amazonで見る</a>"
            return sub
        # 楽天ボタン（＋あれば直後の Yahoo! ボタン）までを1かたまりとして、その直後に足す
        r1 = re.compile(BTN_RE.pattern.replace("(?!<a class='mini y')", "") + r"(?:<a class='mini y'[^>]*>Yahoo!</a>)?")
        r2 = re.compile(BTN2_RE.pattern.replace("(?!<a class=y)", "") + r"(?:<a class=y [^>]*>Yahoo!で見る</a>)?")
        u = r2.sub(mk("btns"), r1.sub(mk("mini"), t))
        if u != t:
            if "mini a" in u and ".mini.a" not in u:
                u = u.replace("</style>", CSS_A + "</style>", 1)
            if "<a class=a " in u and ".btns .a" not in u:
                u = u.replace("</style>", CSS_A2 + "</style>", 1)
            f.write_text(u, encoding="utf-8")
    return n


def main():
    cfg = load_config(BASE) or {}
    na = add_amazon(cfg.get("amazon_tag") or "shogo450e-22")
    print(f"Amazonボタン: 追加{na}")
    cfg = load_config(BASE)
    yh = Yahoo(cfg)
    if not cfg or not yh.ready:
        print("Yahoo!APIキーが無いので何もしません")
        return 0
    api = Rakuten(cfg)
    mp = load_map()
    today = date.today()
    arts = sorted(f for f in (SITE / "articles").glob("*.html") if f.name not in SKIP)
    texts = {f: f.read_text(encoding="utf-8") for f in arts}
    # 記事に出てくる楽天商品を集める
    codes = {}
    for t in texts.values():
        for rx in (BTN_RE, BTN2_RE):
            for m in rx.finditer(t):
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
        def sub2(m):
            nonlocal added
            y = (mp.get(f"{m['shop']}:{m['no']}") or {}).get("y")
            if not y:
                return m.group(0)
            added += 1
            return (m.group(0) + f"<a class=y href='{html.escape(y, quote=True)}' "
                    "rel='sponsored nofollow noopener' target=_blank>Yahoo!で見る</a>")
        n = BTN2_RE.sub(sub2, BTN_RE.sub(sub, t))
        if n != t:
            f.write_text(ensure_css(n), encoding="utf-8")
    print(f"Yahoo!ボタン: 新規に調べた商品{new} / 追加したボタン{added}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
