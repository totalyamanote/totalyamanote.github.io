"""マンガ新刊カレンダー（定期更新・他より早く）：site/manga/new-releases.html

元データ：楽天ブックス書籍検索API（漫画ジャンル 001001・売れている順）。発売日が「今日から1週間先まで」と「この1週間に発売」の作品だけ。
事実（発売日・価格・出版社）だけを載せる。発売日は楽天ブックスの表示どおり（「頃」は予定）。
"""
import datetime
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from rakuten import Rakuten, load_config, KOBO_URL  # noqa: E402
from yahoo import Yahoo  # noqa: E402

URL = "https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404"
OUT = HERE / "site" / "manga" / "new-releases.html"
DATA = HERE / "data" / "new_releases.json"
KINDLE = HERE / "data" / "kindle_asin.json"   # 紙のISBN-10 → Kindle版ASIN（Chromeで紙の本のページから確認・"none"=Kindle版なし）
EBJ = HERE / "data" / "ebookjapan_items.json"  # ISBN → ebookjapan ヤフー店の各巻のURL（Chromeで確認・"none"=まだ出ていない）。VCのYahoo!プログラムで報酬が付く
KPEND = HERE / "data" / "kindle_pending.json"  # まだ確認していないISBN-10（毎朝Chromeで確認する）
esc = html.escape
NG = re.compile(r"ムック|原画集|イラストブック|画集|ファンブック|カレンダー|地球の歩き方|ポスト|ステッカー|グッズ|デリヘル|風俗|R-?18|成人向け")
# 成人向けに近い本・ボーイズラブ/ティーンズラブの専用レーベル・マンガではない本は載せない（2026-11-27 件数を増やすときに追加）
NG_ADULT = re.compile(r"BE×BOY|Charaコミックス|Pink\s*cherie|リンクスコレクション|CL-DX|抱かれ|エロ|夜伽|108P|オティン|このマンガがすごい")
# 2026-11-27 坂田さん「量が少ないよ」：上位50位・5巻以上・30日先まで → 上位600位・3巻以上・45日先まで に広げた。
# 人気作だけ（2026-11-15 坂田さん「新刊も人気作のみに」）：①知名度（楽天の漫画売れ筋で上位 TOP_RANK 以内、
# または data/popular_series.json に入っているアニメ化・ドラマ化・映画化などの作品）かつ ②5巻以上
POP = HERE / "data" / "popular_series.json"
TOP_RANK = 600
MIN_VOL = 3
AHEAD = 7        # 2026-11-27 坂田さん「それ以降は、載せない」：1週間より先は載せない
BEHIND = 7       # 発売済みも1週間前まで
WEEK_SHOW = 20   # 1週間以内の新刊は優先して開いたまま出す（2026-11-27 坂田さん）。多い週だけ残りをたたむ


def vol_no(title):
    t = re.sub(r"[【\[].*?[】\]]|特装版.*$|限定版.*$|小冊子付き", "", title).strip()
    m = re.search(r"[（(]\s*(\d+)\s*[）)]|(\d+)\s*巻|[\s　](\d+)\s*$", t)
    return int(next(g for g in m.groups() if g)) if m else 0


def is_popular(e, series):
    if vol_no(e["title"]) < MIN_VOL:
        return False
    key = re.sub(r"[\s　]", "", e["title"])
    return e["rank"] <= TOP_RANK or any(s in key for s in series)
WD = "月火水木金土日"


def pdate(s):
    m = re.match(r"(\d{4})年(\d{2})月(\d{2})日", s or "")
    return datetime.date(*map(int, m.groups())) if m else None


def fetch(api, today):
    """発売の1週間前〜1週間先のコミックを集める。①売れている順（上位 TOP_RANK まで）②発売日の新しい順（話題作の予約を拾う）。"""
    seen, out = set(), []
    for sort, pages in (("sales", TOP_RANK // 30), ("-releaseDate", 40)):
        errs = 0
        for pg in range(1, pages + 1):
            try:
                d = api._get(URL, {"booksGenreId": "001001", "sort": sort, "hits": 30, "page": pg, "outOfStockFlag": 1})
            except Exception as e:
                print("取得失敗", sort, pg, e)
                errs += 1
                if errs >= 4:
                    break
                continue
            rows = d.get("Items", [])
            if not rows:
                break
            dates = []
            for rank, x in enumerate(rows, (pg - 1) * 30 + 1):
                x = x.get("Item", x)
                dt = pdate(x.get("salesDate"))
                if dt:
                    dates.append(dt)
                if not dt or not (-BEHIND <= (dt - today).days <= AHEAD):
                    continue
                if NG.search(x["title"] + x.get("seriesName", "")) or NG_ADULT.search(x["title"] + x.get("seriesName", "")) or "afl" not in x.get("affiliateUrl", ""):
                    continue
                base = re.sub(r"[【\[].*?[】\]]|特装版.*$|限定版.*$|小冊子付き|特典.*$", "", x["title"]).strip()
                if base in seen:
                    continue
                seen.add(base)
                out.append({"date": dt.isoformat(), "approx": "頃" in x.get("salesDate", ""), "title": x["title"], "author": x.get("author", ""),
                            "publisher": x.get("publisherName", ""), "label": x.get("seriesName", ""), "price": int(x.get("itemPrice") or 0),
                            "img": (x.get("largeImageUrl") or "").replace("?_ex=200x200", "?_ex=240x240"), "url": x["affiliateUrl"],
                            "rank": rank if sort == "sales" else 9999, "isbn": x.get("isbn", ""),
                            "rb_rating": x.get("reviewAverage") or "", "rb_reviews": int(x.get("reviewCount") or 0)})
            if sort == "-releaseDate" and dates and max(dates) < today - datetime.timedelta(days=BEHIND):
                break
    return out


def has_cover(e):
    return bool(e.get("img")) and ".gif" not in e["img"]


def _clean_title(t):
    return re.sub(r"【.*?】|\[.*?\]", "", t).strip()


def day_label(d):
    return f"{d.month}/{d.day}（{WD[d.weekday()]}）"


def grid(items, today):
    return f"<div class=ngrid>{''.join(card(e, today) for e in items)}</div>"


def fold(summary, body, opened=False):
    """押すと開く欄（2026-11-27 坂田さん「いきなりたくさん追加はサイトが縦長になるから慎重に」）。"""
    return f"<details class=nfold{' open' if opened else ''}><summary>{summary}</summary>{body}</details>"


def few_then_more(items, today, n, label):
    """売れている順に n 冊だけ見せて（並びは発売日順）、残りは押すと開く。"""
    ranked = sorted(items, key=lambda e: e["rank"])
    first = sorted(ranked[:n], key=lambda e: (e["date"], e["rank"]))
    rest = sorted(ranked[n:], key=lambda e: (e["date"], e["rank"]))
    return grid(first, today) + (fold(f"{label}の残り{len(rest)}冊を見る", grid(rest, today)) if rest else "")


def text_list(items):
    """表紙がまだ出ていない予定：日付・作品名・出版社の一覧（楽天ブックスの商品ページへ）。"""
    rows = "".join(f"<li><b>{day_label(datetime.date.fromisoformat(e['date']))}{'頃' if e['approx'] else ''}</b>"
                   f"<a href='{esc(e['url'])}' rel='sponsored nofollow noopener' target=_blank>{esc(_clean_title(e['title']))}</a>"
                   f"<span>{esc(e['publisher'])}</span></li>" for e in sorted(items, key=lambda e: (e["date"], e["rank"])))
    return f"<ul class=ntext>{rows}</ul>"


def _base(title):
    t = re.sub(r"[（(]\d+[）)].*$", "", title)
    t = re.sub(r"[\s　]+\d+\s*$", "", t)
    return t.strip()


def add_series_ratings(api, items):
    """各新刊に、同じシリーズ（作品名が同じ巻）の楽天ブックスのレビューを、件数つきの平均にして付ける。その巻にレビューが無いとき（発売前など）のため。
    ※出版社のレーベル名（ジャンプコミックス等）では集計しない（別の作品が混ざるため）。"""
    cache = {}
    nz = lambda t: re.sub(r"[\s　]", "", t)
    for e in items:
        if int(e.get("rb_reviews") or 0) >= 3:
            continue
        key = _base(e["title"])
        if len(nz(key)) < 2:
            continue
        if key not in cache:
            tot = cnt = 0
            try:
                d = api._get(URL, {"booksGenreId": "001001", "keyword": key[:40], "hits": 30, "sort": "sales"})
                for x in d.get("Items", []):
                    x = x.get("Item", x)
                    if not nz(x.get("title", "")).startswith(nz(key)):
                        continue
                    c = int(x.get("reviewCount") or 0)
                    if c > 0:
                        tot += float(x.get("reviewAverage") or 0) * c
                        cnt += c
            except Exception as ex:  # noqa: BLE001
                print("シリーズ評価の取得失敗", key, ex)
            cache[key] = (round(tot / cnt, 2), cnt) if cnt >= 3 else None
        r = cache[key]
        if r:
            e["rb_rating"], e["rb_reviews"], e["rb_series"] = r[0], r[1], True
        else:
            e["rb_rating"], e["rb_reviews"], e["rb_series"] = "", 0, None


def isbn10(i13):
    """ISBN-13（978〜）→ ISBN-10。AmazonはISBN-10の商品ページ（/dp/ISBN-10）が紙の本そのもの。"""
    if not (len(i13) == 13 and i13.startswith("978") and i13.isdigit()):
        return ""
    core = i13[3:12]
    c = (11 - sum((10 - k) * int(x) for k, x in enumerate(core)) % 11) % 11
    return core + ("X" if c == 10 else str(c))


def add_stores(items):
    """同じ本（ISBN一致）を、Amazonの紙の本につなぐ（Yahoo!ショッピングの紙の本は使わない：坂田さん指定 2026-11-14）。"""
    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    tag = cfg.get("amazon_tag", "")
    KC = json.loads(KINDLE.read_text(encoding="utf-8")) if KINDLE.exists() else {}
    KPRICE = json.loads((HERE / "data" / "kindle_price.json").read_text(encoding="utf-8")) if (HERE / "data" / "kindle_price.json").exists() else {}  # ISBN-10 → Kindle版の値段（Chromeで紙の本のページから確認）
    pend = {}
    for e in items:
        if not e.get("isbn"):
            continue
        i10 = isbn10(e["isbn"])
        k = KC.get(i10)
        if i10 and tag and k and k not in ("none", "ERR"):
            e["kindle"] = f"https://www.amazon.co.jp/dp/{k}?tag={tag}"
            kp = KPRICE.get(i10)
            if kp and str(kp).isdigit():
                e["kindle_price"] = int(kp)
        elif i10 and k is None:
            pend[i10] = e["title"]
    KPEND.write_text(json.dumps(pend, ensure_ascii=False, indent=1), encoding="utf-8")
    # ebookjapan（Yahoo!ショッピング内のebookjapan ヤフー店の各巻）：同じ巻と確認できたものだけ
    EB = json.loads(EBJ.read_text(encoding="utf-8")) if EBJ.exists() else {}
    for e in items:
        u = EB.get(e.get("isbn", ""))
        if u and u not in ("none", "ERR"):
            e["ebj"] = "https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=3784510&pid=892726197&vc_url=" + __import__("urllib.parse", fromlist=["quote"]).quote("https://store.shopping.yahoo.co.jp" + u, safe="")


def _norm(t):
    import unicodedata
    t = unicodedata.normalize("NFKC", t)
    t = re.sub(r"【.*?】|\[.*?\]|モノクロ版|電子版|特装版|限定版", "", t)
    return re.sub(r"[\s　()（）・:：!！?？~〜\-‐―]", "", t).lower()


def add_kobo(api, items):
    """電子書籍版（楽天Kobo）の同じ巻を探す。タイトルを正規化して一致したものだけ。"""
    for e in items:
        want = _norm(e["title"])
        try:
            r = api._get(KOBO_URL, {"keyword": re.sub(r"[（）()]", " ", e["title"])[:60], "hits": 10, "koboGenreId": "101904"}).get("Items", [])
        except Exception:
            r = []
        for x in r:
            x = x.get("Item", x)
            if _norm(x.get("title", "")) == want and "afl" in x.get("affiliateUrl", ""):
                d = pdate(x.get("salesDate"))
                e["kobo"], e["kobo_price"], e["kobo_date"] = x["affiliateUrl"], int(x.get("itemPrice") or 0), d.isoformat() if d else ""
                kimg = x.get("largeImageUrl") or ""
                if not has_cover(e) and kimg and ".gif" not in kimg:   # 紙の表紙がまだ無い巻は、同じ巻の電子版の表紙を使う（2026-11-27）
                    e["img"] = kimg.replace("?_ex=200x200", "?_ex=240x240")
                break


GEN_AFL = "https://hb.afl.rakuten.co.jp/hgc/57dc701b.77fbee9f.57dc701c.c4aa7bb8/?pc="  # 楽天の汎用アフィリエイトリンク（pc= に楽天のURLを渡す）
VC_Y = "https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=3784510&pid=892726197&vc_url="


def series_kw(title):
    """巻数・特装版などを除いたシリーズ名（ストアの検索用）。"""
    t = re.sub(r"【.*?】|\[.*?\]|特装版.*$|限定版.*$|小冊子付き.*$|[（(]\s*\d+\s*[）)]|[\s　]+\d+\s*$", "", title).strip()
    t = re.split(r"[〜～]", t)[0].strip(" 　")
    return t or title


def series_links(e):
    """この巻のページがストアにまだ無いとき用：シリーズ名での検索ページ（前の巻から読める）。"""
    from urllib.parse import quote
    kw = series_kw(e["title"])
    kobo = GEN_AFL + quote("https://books.rakuten.co.jp/search?sitem=" + quote(kw) + "&g=101904", safe="")
    ebj = VC_Y + quote("https://store.shopping.yahoo.co.jp/ebookjapan/search.html?p=" + quote(kw), safe="")
    return kobo, ebj


def kindle_search(e):
    """この巻のKindleページ（ASIN）がまだ確認できないとき用：Kindleストアでのシリーズ名の検索ページ（アソシエイトのタグ付き）。"""
    from urllib.parse import quote
    return "https://www.amazon.co.jp/s?k=" + quote(series_kw(e["title"])) + "&i=digital-text&tag=shogo450e-22"


_WORKS = None


def _works():
    global _WORKS
    if _WORKS is None:
        _WORKS = []
        for f in (HERE / "data" / "manga_works.json", HERE / "site" / "bot" / "manga" / "data" / "manga_works.json"):
            try:
                m = json.loads(f.read_text(encoding="utf-8"))
                _WORKS = list(m.values()) if isinstance(m, dict) else m
                break
            except Exception:
                continue
    return _WORKS


_KR = None


def _kr():
    global _KR
    if _KR is None:
        _KR = {}
        for f in (HERE / "data" / "newrel_ratings.json", HERE / "site" / "bot" / "manga" / "data" / "newrel_ratings.json", HERE / "data" / "newrel_ratings.json"):
            try:
                _KR = json.loads(f.read_text(encoding="utf-8"))
                break
            except Exception:
                continue
    return _KR


def rating_of(e):
    """新刊の星評価（2026-11-24 坂田さん「Kindle優先・なければKobo・発売前は同じシリーズの別の巻のKindle」）：①data/newrel_ratings.json（Kindleの商品ページの評価。その巻、発売前なら直近の既刊）②楽天ブックスのその巻のレビューが3件以上ならそれ ②なければ同じ作品の評価（マンガサイトの作品データ・掲載ストアの表示） ③なければ出さない"""
    kr = _kr().get(e.get("isbn", ""))
    if kr and kr.get("rating") and kr.get("count") and "Kindle" not in str(kr.get("source", "Kindle")) and "Amazon" not in str(kr.get("source", "")):   # Amazonの星は載せない（2026-11-26）
        return f"{float(kr['rating']):.1f}", int(kr["count"]), kr.get("source", "Kindle")
    try:
        if e.get("rb_rating") and int(e.get("rb_reviews") or 0) >= 3:
            return f"{float(e['rb_rating']):.1f}", int(e["rb_reviews"]), "楽天ブックス" + ("・シリーズ" if e.get("rb_series") else "")
    except (TypeError, ValueError):
        pass
    t = re.sub(r"[\s　]", "", e["title"])
    for w in sorted(_works(), key=lambda w: -len(w.get("title", ""))):
        wt = re.sub(r"[\s　]", "", w.get("title", ""))
        if wt and w.get("rating") and w.get("reviews") and t.startswith(wt) and "kindle" not in (w.get("rating_src"), w.get("store") if not w.get("rating_src") else ""):
            sn = {"kindle": "Kindle（Amazon）", "ebookjapan": "ebookjapan", "kobo": "楽天Kobo"}.get(w.get("store"), "電子書籍ストア")
            try:
                return f"{float(w['rating']):.1f}", w["reviews"], sn + "・シリーズ"
            except (TypeError, ValueError):
                return None
    return None


def card(e, today):
    d = datetime.date.fromisoformat(e["date"])
    left = (d - today).days
    tag = ("<b class=nd>今日発売</b>" if left == 0 else (f"<b class=nd>あと{left}日</b>" if left > 0 else f"<span class=nd2>{-left}日前に発売</span>"))
    eu = e.get('kindle') or e.get('ebj') or e.get('kobo')
    img = f"<img src='{esc(e['img'])}' alt='{esc(e['title'])}の表紙' loading=lazy width=120 height=170>"
    return ((f"<div class=ncard id=n{e.get('isbn', '')}><a href='{esc(eu)}' rel='sponsored nofollow noopener' target=_blank class=nimg>{img}</a>" if eu else f"<div class=ncard id=n{e.get('isbn', '')}><span class=nimg>{img}</span>")
            + f"<span class=ndate>{d.month}/{d.day}（{WD[d.weekday()]}）{'頃' if e['approx'] else ''} {tag}</span>"
            + (f"<a class=nt href='{esc(eu)}' rel='sponsored nofollow noopener' target=_blank>{esc(e['title'])}</a>" if eu else f"<b class=nt>{esc(e['title'])}</b>")
            + ((lambda r: f"<span class=nr><b>★{r[0]}</b>（{int(str(r[1]).replace(',', '')):,}件）</span>" if r else "")(rating_of(e)))
            + f"<span class=na>{esc(e['author'])}｜{esc(e['publisher'])}</span>"
            # 値段の表示はKindleを優先（2026-11-14 坂田さん指定）。Kindleの値段が分からないときだけ楽天Kobo
            + (f"<span class=np>¥{e['kindle_price']:,}（Kindle）</span>" if e.get('kindle_price') and e.get('kindle')
               else (f"<span class=np>¥{e['kobo_price']:,}（楽天Kobo）</span>" if e.get('kobo_price') else (f"<span class=np>¥{e['price']:,}（紙の本・税込）</span>" if e.get('price') else "")))
            + "<div class=nbtns>"
            # ボタンの順番：Kindle → ebookjapan → 楽天Kobo（2026-11-14 坂田さん指定）。「電子」の表記は付けない
            + (f"<a class='nbtn a' href='{esc(e['kindle'])}' rel='sponsored nofollow noopener' target=_blank aria-label='{esc(e['title'])}をKindleで見る'>Kindle</a>" if e.get("kindle")
               else "")   # Kindleのページがまだ無い巻はボタンを出さない（検索結果へのリンクは使わない。2026-11-26）。確認できた朝に自動で出る
            + (f"<a class='nbtn e' href='{esc(e['ebj'])}' rel='sponsored nofollow noopener' target=_blank aria-label='{esc(e['title'])}をebookjapanで見る'>ebookjapan</a>" if e.get("ebj")
               else (f"<a class='nbtn e' href='{esc(series_links(e)[1])}' rel='sponsored nofollow noopener' target=_blank aria-label='{esc(series_kw(e['title']))}をebookjapanで探す（この巻はまだ出ていません）'>ebookjapan<small>シリーズ</small></a>" if left >= 0 else ""))
            + ((f"<a class='nbtn k' href='{esc(e['kobo'])}' rel='sponsored nofollow noopener' target=_blank aria-label='{esc(e['title'])}を楽天Koboで見る'>楽天Kobo"
                + (f"<small>{int(e['kobo_date'][5:7])}/{int(e['kobo_date'][8:])}配信</small>" if e.get('kobo_date') and e['kobo_date'] != e['date'] else "") + "</a>") if e.get("kobo") else (f"<a class='nbtn k' href='{esc(series_links(e)[0])}' rel='sponsored nofollow noopener' target=_blank aria-label='{esc(series_kw(e['title']))}を楽天Koboで探す（この巻はまだ出ていません）'>楽天Kobo<small>シリーズ</small></a>" if left >= 0 else ""))
            + ("" if e.get("kobo") or e.get("kindle") or e.get("ebj") else "<span class=nwait>この巻の電子版は配信準備中。「シリーズ」から前の巻を読めます</span>")
            + "</div></div>")


# 検索結果などから本を指定して開いたとき、閉じた欄の中でも見えるようにする
OPEN_JS = ("<script>(function(){function o(){var e=location.hash&&document.getElementById(location.hash.slice(1));if(!e)return;"
           "for(var p=e.closest('details');p;p=p.parentElement.closest('details'))p.open=true;e.scrollIntoView()}"
           "addEventListener('hashchange',o);o()})()</script>")

CSS = (".nfold{margin:6px 0}.nfold>summary{cursor:pointer;list-style:none;display:flex;align-items:center;gap:8px;font-size:14px;font-weight:800;padding:12px 14px;border:1px solid var(--line);border-radius:12px;background:var(--card,#fff)}"
       ".nfold>summary::-webkit-details-marker{display:none}.nfold>summary::after{content:'＋';margin-left:auto;font-size:18px}.nfold[open]>summary::after{content:'－'}.nfold>summary small{font-weight:400;font-size:12px;color:var(--mut)}.nfold>.ngrid{margin:10px 0 14px}"
       ".ntext{list-style:none;margin:8px 0 22px;padding:0}.ntext li{display:grid;grid-template-columns:78px minmax(0,1fr);gap:0 8px;padding:8px 0;border-bottom:1px solid var(--line);font-size:13px;line-height:1.5}"
       ".ntext li b{grid-row:span 2;font-size:12px}.ntext li a{font-weight:700;color:inherit!important;overflow-wrap:anywhere}.ntext li span{font-size:11px;color:var(--mut)}"
       ".ngrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;margin:10px 0 22px}"
       ".ncard{display:flex;flex-direction:column;gap:4px;background:var(--card,#fff);border:1px solid var(--line);border-radius:12px;padding:8px}"
       ".nimg img{width:100%;height:auto;aspect-ratio:12/17;object-fit:contain;background:#f5f5f4;border-radius:8px;display:block}"
       ".ndate{font-size:12px;font-weight:800}.nd{color:#bf0000;margin-left:4px}.nd2{color:var(--mut);font-weight:400;margin-left:4px}"
       ".nt{font-size:13px;line-height:1.35;font-weight:800;color:inherit!important;text-decoration:none}a.nt:hover{text-decoration:underline}.na,.np{font-size:12px;color:var(--mut)}"
       ".nr{font-size:12px;font-weight:700;color:var(--mut)}.nr b{color:#b45309}.nr small{display:block;font-weight:400;font-size:10px}.nbtns{margin-top:auto;display:flex;flex-direction:column;gap:4px}"
       ".nbtn{display:flex;flex-direction:column;align-items:center;text-align:center;color:#fff!important;font-weight:900;font-size:13px;border-radius:8px;padding:7px 6px;white-space:normal;word-break:break-word;text-decoration:none;line-height:1.2;box-shadow:0 2px 0 rgba(0,0,0,.2)}"
       ".nbtn small{font-size:11px;font-weight:700;opacity:.95}.nbtn.r{background:#bf0000}.nbtn.k{background:#bf0000}.nbtn.e{background:#d4002a}.nbtn.off{background:#e7e5e4;color:#5f5f5f!important;box-shadow:none;font-weight:700}.nbtn.y{background:#d4002a}.nbtn.a{background:#ff9900;color:#111!important}.nwait{grid-column:1/-1;text-align:center;font-size:11px;color:var(--mut);background:#f5f5f4;border-radius:8px;padding:6px}")


def build():
    import gen_manga as gm
    today = datetime.date.today()
    api = Rakuten(load_config(HERE))
    items = fetch(api, today)
    series = [re.sub(r"[\s　]", "", s) for s in (json.loads(POP.read_text(encoding="utf-8")).get("series", []) if POP.exists() else [])]
    items = [e for e in items if is_popular(e, series)]
    add_kobo(api, items)   # 電子版のページ。紙の表紙がまだ無い巻は、ここで電子版の表紙が入る
    covered = [e for e in items if has_cover(e)]   # ストアのボタンと星は、表紙つきで出す作品だけ調べる
    add_stores(covered)
    add_series_ratings(api, covered)
    if len(items) < 6:
        print("新刊が少ないので更新しない", len(items))
        return False
    DATA.write_text(json.dumps({"date": today.isoformat(), "items": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    soon = sorted([e for e in items if e["date"] >= today.isoformat()], key=lambda e: (e["date"], ".gif" in e["img"], e["rank"]))
    past = sorted([e for e in items if e["date"] < today.isoformat()], key=lambda e: (e["date"], -e["rank"]), reverse=True)
    nocover = [e for e in soon if not has_cover(e)]
    soon_c = [e for e in soon if has_cover(e)]
    past = [e for e in past if has_cover(e)]
    wk = soon_c
    title = f"マンガ新刊の発売日カレンダー｜今週発売の新刊（{today.month}月{today.day}日更新）"
    top = sorted(soon_c or past, key=lambda e: e["rank"])[:3]
    _clean = lambda t: re.sub(r"【.*?】|\[.*?\]", "", t).strip()
    tops = "・".join(_clean(e["title"]) + f"（{int(e['date'][5:7])}/{int(e['date'][8:])}）" for e in top)
    desc = f"{tops}など、今週発売の人気マンガの新刊{len(soon)}冊（売れ筋と話題作・3巻以上）を一覧に。楽天Kobo・Kindleの電子書籍版へのリンクつき。定期更新。"
    body = (f"<div style='margin:10px 0 14px'><h1 style='font-size:18px;font-weight:700;margin:0 0 4px'>マンガ新刊の発売日カレンダー</h1>"
            f"<p style='font-size:13px;color:#5f5f5f;margin:0'>楽天ブックスの売れ筋（上位600位まで）と、アニメ化・ドラマ化などの話題作の新刊（3巻以上）のうち、発売日の前後1週間のものを発売日順に並べています（{today.strftime('%Y/%m/%d')}時点・定期更新）。</p></div>"
            f"<style>{CSS}</style>"
            + (f"<h2>今週発売（7日以内・{len(wk)}冊）</h2>{few_then_more(wk, today, WEEK_SHOW, '今週発売')}" if wk else "")
            + (fold(f"表紙がまだ出ていない今週の発売予定<small>{len(nocover)}冊</small>", text_list(nocover)) if nocover else "")
            + (f"<h2>最近発売した新刊（1週間以内・{len(past)}冊）</h2>{few_then_more(past, today, 6, '最近発売した新刊')}" if past else "")
            + "<p class=note>発売日は楽天ブックスの表示のとおりです。ボタンはすべて電子書籍版のページにつながります（楽天Kobo・Kindle・ebookjapanとも、同じ巻の電子書籍版であることを確認）。電子版の配信日が紙と違う場合は、ボタンに配信日を出しています。「シリーズ」と書いたボタンは、この巻のページがストアにまだ無いため、シリーズ名での検索ページ（前の巻から読めます）につながります。「頃」は予定で、変わることがあります。予約・購入の前に、商品ページで確認してください。"
              "1巻を無料で試し読みできる作品は「<a href='theme/free-now.html'>いま無料で読めるマンガ</a>」にまとめています。</p>")
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "url": "https://totalyamanote.jp/manga/new-releases.html",
          "isPartOf": {"@type": "WebSite", "name": "やまのてマンガ", "url": "https://totalyamanote.jp/manga/"},
          "mainEntity": {"@type": "ItemList", "numberOfItems": len(soon) + len(past), "itemListElement": [
              {"@type": "ListItem", "position": i, "item": {"@type": "Book", "name": e["title"], "author": {"@type": "Person", "name": e["author"]},
                                                           "publisher": {"@type": "Organization", "name": e["publisher"]}, "datePublished": e["date"], "isbn": e["isbn"]}}
              for i, e in enumerate(soon + past, 1)]}}
    body += OPEN_JS
    head = "<script type=application/ld+json>" + json.dumps(ld, ensure_ascii=False) + "</script>"
    OUT.write_text(gm.page(title, desc, body, 0, head=head, canon='https://totalyamanote.jp/manga/new-releases.html').replace("<p class=pr>PR｜このサイトはアフィリエイト広告（バリューコマース）を利用しています。</p>",
                                                                    "<p class=pr>PR｜このページはアフィリエイト広告（楽天アフィリエイト・バリューコマース・Amazonアソシエイト）を利用しています。</p>"), encoding="utf-8")
    print(f"新刊 {len(items)} 冊（今週{len(wk)}・表紙待ち{len(nocover)}・発売済み{len(past)}）")
    return True


if __name__ == "__main__":
    build()
