"""マンガ新刊カレンダー（毎朝更新・他より早く）：site/manga/new-releases.html

元データ：楽天ブックス書籍検索API（漫画ジャンル 001001・売れている順）。発売日が「今日から30日後まで（予約受付中）」と「この14日に発売」の作品だけ。
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
KPEND = HERE / "data" / "kindle_pending.json"  # まだ確認していないISBN-10（毎朝Chromeで確認する）
esc = html.escape
NG = re.compile(r"ムック|原画集|イラストブック|画集|ファンブック|カレンダー|地球の歩き方|ポスト|ステッカー|グッズ")
WD = "月火水木金土日"


def pdate(s):
    m = re.match(r"(\d{4})年(\d{2})月(\d{2})日", s or "")
    return datetime.date(*map(int, m.groups())) if m else None


def fetch(api, today):
    seen, out = set(), []
    for pg in range(1, 6):
        try:
            d = api._get(URL, {"booksGenreId": "001001", "sort": "sales", "hits": 30, "page": pg, "outOfStockFlag": 1})
        except Exception as e:
            print("取得失敗", pg, e)
            break
        for rank, x in enumerate(d.get("Items", []), (pg - 1) * 30 + 1):
            x = x.get("Item", x)
            dt = pdate(x.get("salesDate"))
            if not dt or not (-14 <= (dt - today).days <= 30):
                continue
            if NG.search(x["title"] + x.get("seriesName", "")) or "afl" not in x.get("affiliateUrl", ""):
                continue
            base = re.sub(r"[【\[].*?[】\]]|特装版|限定版|小冊子付き|特典.*$", "", x["title"]).strip()
            if base in seen:
                continue
            seen.add(base)
            out.append({"date": dt.isoformat(), "approx": "頃" in x.get("salesDate", ""), "title": x["title"], "author": x.get("author", ""),
                        "publisher": x.get("publisherName", ""), "label": x.get("seriesName", ""), "price": int(x.get("itemPrice") or 0),
                        "img": (x.get("largeImageUrl") or "").replace("?_ex=200x200", "?_ex=240x240"), "url": x["affiliateUrl"], "rank": rank,
                        "isbn": x.get("isbn", "")})
    return out


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
    pend = {}
    for e in items:
        if not e.get("isbn"):
            continue
        i10 = isbn10(e["isbn"])
        k = KC.get(i10)
        if i10 and tag and k and k not in ("none", "ERR"):
            e["kindle"] = f"https://www.amazon.co.jp/dp/{k}?tag={tag}"
        elif i10 and k is None:
            pend[i10] = e["title"]
    KPEND.write_text(json.dumps(pend, ensure_ascii=False, indent=1), encoding="utf-8")


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
                break


def card(e, today):
    d = datetime.date.fromisoformat(e["date"])
    left = (d - today).days
    tag = ("<b class=nd>今日発売</b>" if left == 0 else (f"<b class=nd>あと{left}日</b>" if left > 0 else f"<span class=nd2>{-left}日前に発売</span>"))
    eu = e.get('kobo') or e.get('kindle')
    img = f"<img src='{esc(e['img'])}' alt='{esc(e['title'])}の表紙' loading=lazy width=120 height=170>"
    return ((f"<div class=ncard><a href='{esc(eu)}' rel='sponsored nofollow noopener' target=_blank class=nimg>{img}</a>" if eu else f"<div class=ncard><span class=nimg>{img}</span>")
            + f"<span class=ndate>{d.month}/{d.day}（{WD[d.weekday()]}）{'頃' if e['approx'] else ''} {tag}</span>"
            f"<b class=nt>{esc(e['title'])}</b><span class=na>{esc(e['author'])}｜{esc(e['publisher'])}</span>"
            + (f"<span class=np>電子版 ¥{e['kobo_price']:,}（楽天Kobo）</span>" if e.get('kobo_price') else "")
            + "<div class=nbtns>"
            + ((f"<a class='nbtn k' href='{esc(e['kobo'])}' rel='sponsored nofollow noopener' target=_blank aria-label='{esc(e['title'])}を楽天Koboで見る'>楽天Kobo<small>電子"
                + (f"・{int(e['kobo_date'][5:7])}/{int(e['kobo_date'][8:])}" if e.get('kobo_date') and e['kobo_date'] != e['date'] else "") + "</small></a>") if e.get("kobo") else "")
            + (f"<a class='nbtn a' href='{esc(e['kindle'])}' rel='sponsored nofollow noopener' target=_blank aria-label='{esc(e['title'])}をKindleで見る'>Kindle<small>電子</small></a>" if e.get("kindle") else "")
            + ("" if e.get("kobo") or e.get("kindle") else "<span class=nwait>電子版は配信準備中</span>")
            + "</div></div>")


CSS = (".ngrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;margin:10px 0 22px}"
       ".ncard{display:flex;flex-direction:column;gap:4px;background:var(--card,#fff);border:1px solid var(--line);border-radius:12px;padding:8px}"
       ".nimg img{width:100%;height:auto;aspect-ratio:12/17;object-fit:contain;background:#f5f5f4;border-radius:8px;display:block}"
       ".ndate{font-size:12px;font-weight:800}.nd{color:#bf0000;margin-left:4px}.nd2{color:var(--mut);font-weight:400;margin-left:4px}"
       ".nt{font-size:13px;line-height:1.35}.na,.np{font-size:12px;color:var(--mut)}"
       ".nbtns{margin-top:auto;display:grid;grid-template-columns:repeat(auto-fit,minmax(44px,1fr));gap:3px}"
       ".nbtn{display:flex;flex-direction:column;align-items:center;text-align:center;color:#fff!important;font-weight:900;font-size:11px;border-radius:8px;padding:6px 1px;white-space:nowrap;text-decoration:none;line-height:1.2;box-shadow:0 2px 0 rgba(0,0,0,.2)}"
       ".nbtn small{font-size:10px;font-weight:700;opacity:.95}.nbtn.r{background:#bf0000}.nbtn.k{background:#bf0000}.nbtn.y{background:#d4002a}.nbtn.a{background:#ff9900;color:#111!important}.nwait{grid-column:1/-1;text-align:center;font-size:11px;color:var(--mut);background:#f5f5f4;border-radius:8px;padding:6px}")


def build():
    import gen_manga as gm
    today = datetime.date.today()
    api = Rakuten(load_config(HERE))
    items = fetch(api, today)
    add_stores(items)
    add_kobo(api, items)
    if len(items) < 6:
        print("新刊が少ないので更新しない", len(items))
        return False
    DATA.write_text(json.dumps({"date": today.isoformat(), "items": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    soon = sorted([e for e in items if e["date"] >= today.isoformat()], key=lambda e: (e["date"], ".gif" in e["img"], e["rank"]))
    past = sorted([e for e in items if e["date"] < today.isoformat()], key=lambda e: (e["date"], -e["rank"]), reverse=True)
    wk = [e for e in soon if e["date"] <= (today + datetime.timedelta(days=7)).isoformat()]
    title = f"マンガ新刊の発売日カレンダー｜今週・来月の注目新刊（{today.month}月{today.day}日更新）"
    top = [e for e in soon if ".gif" not in e["img"]][:3]
    _clean = lambda t: re.sub(r"【.*?】|\[.*?\]", "", t).strip()
    tops = "・".join(_clean(e["title"]) + f"（{int(e['date'][5:7])}/{int(e['date'][8:])}）" for e in top)
    desc = f"{tops}など、売れているマンガの新刊{len(soon)}作品の発売日を一覧に。楽天Kobo・Kindleの電子書籍版へのリンクつき。毎朝更新。"
    body = (f"<div style='margin:10px 0 14px'><h1 style='font-size:18px;font-weight:700;margin:0 0 4px'>マンガ新刊の発売日カレンダー</h1>"
            f"<p style='font-size:13px;color:#5f5f5f;margin:0'>楽天ブックスで売れているマンガの新刊を、発売日順に並べています（{today.strftime('%Y/%m/%d')}時点・毎朝更新）。</p></div>"
            f"<style>{CSS}</style>"
            + (f"<h2>今週発売（7日以内）</h2><div class=ngrid>{''.join(card(e, today) for e in wk)}</div>" if wk else "")
            + f"<h2>これから発売（予約受付中）</h2><div class=ngrid>{''.join(card(e, today) for e in soon if e not in wk)}</div>"
            + (f"<h2>最近発売した新刊（14日以内）</h2><div class=ngrid>{''.join(card(e, today) for e in past)}</div>" if past else "")
            + "<p class=note>発売日は楽天ブックスの表示のとおりです。ボタンはすべて電子書籍版のページにつながります（楽天Kobo・Kindleとも、同じ巻の電子書籍版であることを確認）。電子版の配信日が紙と違う場合は、ボタンに配信日を出しています。「頃」は予定で、変わることがあります。予約・購入の前に、商品ページで確認してください。"
              "1巻を無料で試し読みできる作品は「<a href='theme/free-now.html'>いま無料で読めるマンガ</a>」にまとめています。</p>")
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "url": "https://totalyamanote.github.io/manga/new-releases.html",
          "isPartOf": {"@type": "WebSite", "name": "やまのてマンガ", "url": "https://totalyamanote.github.io/manga/"},
          "mainEntity": {"@type": "ItemList", "numberOfItems": len(soon) + len(past), "itemListElement": [
              {"@type": "ListItem", "position": i, "item": {"@type": "Book", "name": e["title"], "author": {"@type": "Person", "name": e["author"]},
                                                           "publisher": {"@type": "Organization", "name": e["publisher"]}, "datePublished": e["date"], "isbn": e["isbn"]}}
              for i, e in enumerate(soon + past, 1)]}}
    head = "<script type=application/ld+json>" + json.dumps(ld, ensure_ascii=False) + "</script>"
    OUT.write_text(gm.page(title, desc, body, 0, head=head).replace("<p class=pr>PR｜このサイトはアフィリエイト広告（バリューコマース）を利用しています。</p>",
                                                                    "<p class=pr>PR｜このページはアフィリエイト広告（楽天アフィリエイト・バリューコマース・Amazonアソシエイト）を利用しています。</p>"), encoding="utf-8")
    print(f"新刊 {len(items)} 作品（今週{len(wk)}・予約{len(soon)}・発売済み{len(past)}）")
    return True


if __name__ == "__main__":
    build()
