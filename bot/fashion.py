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
MAX_PRICE = 999999999                 # 上限なし（2026-11-25 坂田さん「9,800円のリミット外す」）
INSTA_MAX = 14800                     # インフルエンサー発ブランドだけ14,800円まで（2026-11-24 坂田さん「14800円で」。9,800円だと候補が約100点しかない）
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
SUMMER_NG = re.compile(r"半袖|ノースリーブ|キャミ|タンクトップ|サンダル|リネン|水着|ラッシュガード|水陸両用|サマー|夏|綿麻|ハーフスリーブ|ショートスリーブ|フレンチスリーブ|五分袖|5分袖") if datetime.now().month in (11, 12, 1, 2) else re.compile(r"(?!x)x")


def kind_of(name):
    for label, rx in TYPES:
        if re.search(rx, name):
            return label
    return "その他"


# Instagram発ブランド（2026-11-24 坂田さん「これらのブランド使って掲載」）。楽天で新品が売られているものだけ。
# 調べた結果：Lil Ambition・BIRTHDAY BASH・Bibiy.は楽天では中古だけ、THE TOE・OBLI・Acak.は楽天に出店なし → 入れない
INSTA = [("eimy istoire", r"eimy\s*istoire|エイミーイストワール"), ("anuans", r"anuans|アニュアンス"),
         ("CREDONA", r"CREDONA|クレドナ"), ("ETRÉ TOKYO", r"ETR[EÉ]\s*TOKYO|エトレトウキョウ|エトレトーキョー"),
         ("deres", r"deres\s*[/／]?\s*デレス|デレス\s*deres|\bderes\b.*(?:レディース|ワンピース|ニット|パンツ|スカート)")]   # deres は2026-11-24時点で楽天は中古だけ。新品が出たら自動で載る
# 2026-11-24 G-BLO「芸能人の服ブランド一覧」（女性24）も調べた：楽天で新品の服があるのは ETRÉ TOKYO（杉田純奈）だけ。
# 虜・ROSY LUCE・LAVANDA・Par la magie・ALLISON BROWN・miraville・INTIMITE・MES VACANCES・FUKUU・Ange Charme・Parsley・mmts・RE.・ESS BY・conte・MiiA・SAAKIN・ROY・WCJ・PUNYUS・loin.・newnow・Herlipto は中古だけ／出店なし／服以外
# 2026-11-24 追加で調べたもの（楽天で新品なし→載せない）：deres・JOSE MOON（中古だけ）、Her lip to（楽天は化粧品と下着だけ）、
# WYM・ADRER・SOERTE・GRANCY・SINSS・LILL・CLEL・epnok・RUUBON・Loose（ZOZOTOWN中心。楽天は出店なしか中古だけ）
# 中古は商品名に「中古」と書かない店がある（コンコルドストア等）→ 説明文の「状態ランク」「ご入札」なども見る
USED_NG = re.compile(r"中古|古着|USED|ユーズド|未使用品|リユース|状態ランク|コンディション|ご入札|使用感|目立った傷")


def _off(name):
    m = re.search(r"(\d{2})\s*[%％]\s*OFF", name, re.I)
    return int(m.group(1)) if m else 0


CAT_WORDS = {"トップス", "ボトムス", "アウター", "ジャケット・アウター", "スカート", "パンツ", "ワンピース", "ワンピース・ドレス", "ニット・セーター", "シャツ・ブラウス", "ベスト・ジレ", "カットソー・Tシャツ"}


def iname(n0, rx):
    """Instagram発ブランドの商品名：飾り・ブランド名・品番・色・サイズを外して、商品名の部分だけ（30字まで）。"""
    s = re.sub(r"【[^】]*】|\[[^\]]*\]|（[^）]*）|\([^)]*\)|《[^》]*》", " ", n0)
    s = re.sub(rx, " ", s, flags=re.I)
    s = re.sub(r"セール|SALE|半額|送料無料|レディース|\b\d{4}(?:AW|SS)\b|\b[0-9][0-9\-]{5,}\b|[|／/｜]|\bF\b|フリークスストア|\S+ストア$", " ", s, flags=re.I)
    out = ""
    for t in s.split():
        if t in CAT_WORDS and out:
            if len(out) >= 10:
                break
            out += " " + t; break
        if out and len(out) + 1 + len(t) > 30:      # 30字を超えるなら単語の途中で切らずに止める
            break
        out = (out + " " + t).strip()
    return out[:30]


def insta_pool(api, recent):
    """Instagram発ブランドの新品（9,800円まで・冬は夏物なし・中古なし）。レビューはまだ少ないので件数は問わず、ついている場合は★3.5以上だけ。"""
    out, seen = [], set()
    for bname, rx in INSTA:
        for pg in (1, 2, 3, 4, 5, 6):
            try:
                d = api._get(SEARCH_URL, {"keyword": bname.replace("É", "E"), "NGKeyword": "中古 古着", "hits": 30, "page": pg, "availability": 1, "maxPrice": INSTA_MAX, "sort": "-reviewCount"})
            except Exception:
                break
            for x in d.get("Items", []):
                x = x.get("Item", x); n0 = x["itemName"]; code = x["itemCode"]
                if code in seen or code in recent or not re.search(rx, n0, re.I):
                    continue
                if re.search(r"帽|キャップ|ビーニー|ハット|バッグ|ソックス|靴下|マフラー|ストール|手袋", n0) or USED_NG.search(n0 + " " + (x.get("itemCaption") or "")) or BAG_NG.search(n0) or SUMMER_NG.search(n0) or OTHER_NG.search(n0):
                    continue
                if int(x.get("reviewCount") or 0) and float(x.get("reviewAverage") or 0) < 3.5:
                    continue
                imgs = x.get("mediumImageUrls") or []
                img = (imgs[0] if isinstance(imgs[0], str) else imgs[0].get("imageUrl")) if imgs else ""
                nm = iname(n0, rx)
                hits = [(m.end(), lab) for lab, r2 in TYPES for m in re.finditer(r2, nm)]
                kd = max(hits)[1] if hits else kind_of(n0)   # 「ニット…スカート」はスカート（名前のいちばん後ろの種類）
                if not img or not nm or kd == "その他" or not (0 < int(x.get("itemPrice") or 0) <= INSTA_MAX):
                    continue
                seen.add(code)
                off = _off(n0)
                nm = f"{bname} {nm}"
                out.append({"rank": 999, "kind": kd, "code": code, "name": nm[:44] + ("…" if len(nm) > 44 else ""), "off": off, "sale": str(off) if off else "",
                            "img": img.replace("_ex=128x128", "_ex=300x300"), "url": x.get("affiliateUrl") or x["itemUrl"], "brand": bname, "insta": True})
            if pg * 30 >= int(d.get("count") or 0):
                break
    return out


HIST = BASE / "data" / "fashion_shown.json"


HIST_DAYS = 30   # 2026-11-24 坂田さん「毎日は、被らないようなね」：30日以内に出した商品（色違い＝同じ名前も）は出さない


def _nkey(name):
    return "n:" + re.sub(r"\s+", "", name)[:18]


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
    h = {d: v for d, v in h.items() if d >= _days_ago(HIST_DAYS + 5)}
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
    recent = {code for d, codes in hist.items() if d != today and d >= _days_ago(HIST_DAYS) for code in codes}
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
    ins = sorted(insta_pool(api, recent), key=lambda c: -c["off"])
    seen_i, ins_u = set(), []
    for c in ins:                                    # 色違い（名前が同じ）は1つだけ
        k = re.sub(r"\s+", "", c["name"])[:18]
        if k not in seen_i:
            seen_i.add(k); ins_u.append(c)
    # 2026-11-24 坂田さん「新品あり乗せ」：8点ともInstagram発ブランド（新品）で埋める。8点に届かない日だけ楽天ファッションの人気品で補う
    ins_u = [c for c in ins_u if _nkey(c["name"]) not in recent]      # 色違い（名前が同じ）も30日は出さない
    if len(ins_u) < 8:                                                # 30日で候補が尽きたら、14日より前に出したものは戻す（ほかのブランドで埋めない）
        recent14 = {code for d, codes in hist.items() if d != today and d >= _days_ago(14) for code in codes}
        more = sorted(insta_pool(api, recent14), key=lambda c: -c["off"])
        have = {c["code"] for c in ins_u} | {_nkey(c["name"]) for c in ins_u}
        for c in more:
            k = _nkey(c["name"])
            if c["code"] not in have and k not in have and k not in recent14:
                ins_u.append(c); have |= {c["code"], k}
    uniq = [c for c in uniq if _nkey(c["name"]) not in recent]
    uniq = ins_u if len(ins_u) >= 8 else ins_u + uniq
    chosen, kind_n, per_brand = [], {}, {}
    for limit in (1, 2, 8):                          # まず種類ごとに1点（割引の大きい順）→ 足りなければ種類2点まで → それでも足りなければ制限なし
        for c in uniq:
            if len(chosen) >= 8:
                break
            if c in chosen or kind_n.get(c["kind"], 0) >= (max(limit, 2) if c.get("insta") else limit) or per_brand.get(c["brand"], 0) >= (3 if c.get("insta") and limit >= 2 else 2):
                continue
            chosen.append(c); kind_n[c["kind"]] = kind_n.get(c["kind"], 0) + 1; per_brand[c["brand"]] = per_brand.get(c["brand"], 0) + 1
    out = []
    for c in chosen:                                 # 並びは割引の大きい順
        d = api.item_detail(c["code"])                # 価格・ポイント・レビューを取り直す
        if not d or not (0 < d["price"] <= (INSTA_MAX if c.get("insta") else MAX_PRICE)):
            continue
        pr = d["point_rate"]
        try:
            if d["point_end"] and datetime.strptime(d["point_end"][:16], "%Y-%m-%d %H:%M") < datetime.now():
                pr = 1
        except ValueError:
            pass
        out.append({**c, "price": d["price"], "pr": pr, "pt": d["price"] * pr // 100, "rc": d["review_count"], "av": d["review_avg"]})
    out.sort(key=lambda c: (not c.get("insta"), -c["off"], c["rank"]))   # Instagram発ブランドが先、その中は割引の大きい順
    return out


def render(items, stamp):
    cards = ""
    for it in items:
        sale = f"<span class=hot>SALE {it['sale']}%OFF</span>" if it["sale"] else ""
        cards += (f"<a class=card href='{esc(it['url'])}' rel='sponsored nofollow noopener' target=_blank>"
                  f"<span class=gtag>{esc(it['kind'])}" + (f"・ランキング{it['rank']}位" if it['rank'] < 999 else "") + f"</span>{sale}<img src='{esc(it['img'])}' alt='{esc(it['name'])}' loading=lazy>"
                  f"<span class=nm>{esc(it['name'])}</span><span class=yen>¥{it['price']:,}</span>"
                  f"<span class=pts>ポイント{it['pr']}倍（{it['pt']:,}pt）</span>"
                  + (f"<span class=rv>⭐{it['av']}（{it['rc']:,}件）</span>" if it['rc'] else "<span class=rv>新着・レビューはこれから</span>")
                  + "<span class=go>楽天市場で見る →</span></a>")
    if not cards:
        return "<!--hubf--><!--/hubf-->"
    return ("<!--hubf--><section id=fashion style='margin-top:12px'><h2>👗 楽天ファッション（インフルエンサー発ブランド）</h2>"
            f"<div class=cards>{cards}</div>"
            "<p class=meta style='font-size:12px'>PR｜楽天市場へのリンクはアフィリエイト広告です。価格・ポイントは更新時点の表示で、商品ページで最新をご確認ください。</p></section><!--/hubf-->")


def ztile(c, rank=None, store=""):
    """ZOZOTOWNの商品一覧と同じ見せ方のタイル（2026-11-25 坂田さん「ZOZOの表示の仕方を参考に」）：画像・ブランド名（太字）・商品名（灰色）・価格（割引は赤）・◯%OFFの赤いラベル・ポイント・レビュー。"""
    off = int(c.get("off") or c.get("sale") or 0)
    orig = c.get("orig") or 0
    price = int(c["price"])
    pt = int(c.get("pt") or 0)
    rk = f"<span class=zrk>{rank}</span>" if rank else ""
    lb = f"<span class=zoff>{off}%OFF</span>" if off else ""
    _b = (c.get("brand") or "").strip()
    _nm = c["name"]
    if _b and _nm.lower().startswith(_b.lower()):
        _nm = _nm[len(_b):].strip() or _nm
    brand_ = esc(_b.upper())
    pr = f"<span class='zp{' zred' if off else ''}'>¥{price:,}</span>" + (f"<s class=zorig>¥{orig:,}</s>" if orig and orig > price else "")
    ptx = f"<span class=zpt>ポイント{max(1, round(pt * 100 / price))}%（{pt:,}pt）</span>" if pt > 0 and price else ""
    rv = f"<span class=zrv>★{float(c['av']):.1f}<small>（{int(c['rc']):,}）</small></span>" if c.get("rc") else ""
    return (f"<a class=zc href='{esc(c['url'])}' rel='sponsored nofollow noopener' target=_blank><span class=zi><img src='{esc(c['img'])}' alt='{esc(c['name'])}' width=300 height=400 loading=lazy>{lb}{rk}</span>"
            f"<b class=zb>{brand_}</b><span class=zn>{esc(_nm)}</span><span class=zprow>{pr}</span>{ptx}{rv}</a>")


def render_z(items):
    cards = "".join(ztile(it) for it in items)
    if not cards:
        return "<!--hubf--><!--/hubf-->"
    return f"<!--hubf--><section id=fashion><h2>楽天ファッション<small>インフルエンサー発ブランド</small></h2><div class=zg>{cards}</div></section><!--/hubf-->"


def main():
    cfg = load_config(Path(os.environ.get("CONFIG_BASE") or BASE))
    if not cfg:
        sys.exit("設定が読めません")
    api = Rakuten(cfg)
    # 商品は3日間同じものを見せる（2026-11-24 坂田さん「全商品3日固定にしようか」）。同じ3日の間は、更新を何度走らせても入れ替えない。
    _cf = Path(__file__).resolve().parent / "data" / "fashion_cache.json"
    try:
        from run_daily import BF_ON as _bf
    except Exception:
        _bf = False
    _key = datetime.now().toordinal() // (1 if _bf else 3)
    try:
        _c = json.loads(_cf.read_text(encoding="utf-8")) if _cf.exists() else {}
    except Exception:
        _c = {}
    if _c.get("key") == _key and _c.get("items"):
        items = _c["items"]
        _reused = True
    else:
        items = pick(api)
        _reused = False
        if items:
            _cf.write_text(json.dumps({"key": _key, "items": items}, ensure_ascii=False, default=str), encoding="utf-8")
    items = items[:6]   # 6点（3列×2行）（2026-11-25 坂田さん「商品6点表示されるように」）
    blk = render_z(items)
    # 2026-11-25 坂田さん「物販のレディースファッションはファッションページへ移籍」：商品の段は fashion/index.html に出す。トップ（物販）からは外す。
    p = SITE / "fashion" / "index.html"
    if p.exists():
        t = p.read_text(encoding="utf-8")
        t2 = re.sub(r"<!--hubf-->.*?<!--/hubf-->", lambda m: blk, t, count=1, flags=re.S)
        if t2 != t:
            p.write_text(t2, encoding="utf-8")
    # トップ（物販）には、軽く4商品だけ（2026-11-25 坂田さん「物販のレディースファッションは完全ZOZOの表示で」）。全商品は fashion/index.html
    lite = render_z(items[:3]).replace("<h2>楽天ファッション<small>インフルエンサー発ブランド</small></h2>", "<h2>レディースファッション</h2>", 1)  # 分析結果：ファッションは縮小（2026-11-25）。1行(3件)だけ
    if lite != "<!--hubf--><!--/hubf-->":
        lite = lite.replace("<!--/hubf-->", "<a class=zmore href='fashion/index.html' style='display:block;text-align:center;border:1px solid #ccc;color:#222;text-decoration:none;font-size:13px;font-weight:700;padding:11px;margin:10px 0 4px'>レディースファッションをもっと見る ›</a><!--/hubf-->")
    pi = SITE / "index.html"
    ti = pi.read_text(encoding="utf-8")
    ti2 = re.sub(r"<!--hubf-->.*?<!--/hubf-->", lambda m: lite, ti, count=1, flags=re.S)
    if ti2 != ti:
        pi.write_text(ti2, encoding="utf-8")
    if items and not _reused:
        _save_hist([i["code"] for i in items] + [_nkey(i["name"]) for i in items])
    print(f"ファッション {len(items)} 点", [i['kind'] for i in items])


if __name__ == "__main__":
    main()
