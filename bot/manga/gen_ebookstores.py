"""電子書籍ストア比較ページ：site/manga/store-compare.html

元データ：data/ebook_stores.json（各ストアの公式ページで確認した事実・出典URL・確認日）。毎週の作業で更新する。
公式で確認できない値は「未確認」のまま載せる（推測で埋めない）。
"""
import datetime
import html
import json
import sys
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gen_manga as gm  # noqa: E402

DATA = HERE / "data" / "ebook_stores.json"
OUT = HERE / "site" / "manga" / "store-compare.html"
esc = html.escape
CFG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))


def go(s):
    """公式サイトへのリンク（提携済みのストアだけアフィリエイトリンク）。"""
    if s["aff"] == "vc_booklive":
        return gm.VC + urllib.parse.quote(s["url"], safe=""), True
    if s["aff"] == "vc_yahoo":   # ValueCommerceのYahoo!ショッピング（提携済み）。ebookjapanの電子書籍は Yahoo!ショッピング内のお店で売られている
        return f"https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=3784510&pid=892726197&vc_url=" + urllib.parse.quote(s["aff_url"], safe=""), True
    if s["aff"] == "rakuten" and CFG.get("affiliate_id"):
        return f"https://hb.afl.rakuten.co.jp/hgc/{CFG['affiliate_id']}/?pc={urllib.parse.quote(s['url'], safe='')}", True
    if s["aff"] == "amazon" and CFG.get("amazon_tag"):
        return s["url"] + ("&" if "?" in s["url"] else "?") + f"tag={CFG['amazon_tag']}", True
    return s["url"], False


def src(u):
    return f"<a class=src href='{esc(u)}' rel=noopener target=_blank>出典</a>" if u else ""


def cell(v):
    return f"<span class=unk>{esc(v)}</span>" if v.startswith(("未確認", "確認できず")) else esc(v)


CSS = (".sc{width:100%;border-collapse:collapse;font-size:13px;min-width:860px}.sc th,.sc td{border:1px solid var(--line);padding:8px;vertical-align:top;text-align:left}"
       ".sc th{background:#fff7ed;white-space:nowrap}.sc td:first-child{font-weight:800;white-space:nowrap}.scroll{overflow-x:auto;margin:10px 0 18px}"
       ".unk{color:var(--mut)}.src{font-size:11px;margin-left:4px}.stop{background:#fef2f2;border:1px solid #fecaca;border-radius:10px;padding:10px 14px;margin:10px 0;font-size:13px}"
       ".pk{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin:10px 0 18px}.pk div{background:var(--card,#fff);border:1px solid var(--line);border-left:5px solid #bf0000;border-radius:12px;padding:10px 14px}"
       ".pk span{display:block;font-size:12px;font-weight:800;color:#bf0000}.st{background:var(--card,#fff);border:1px solid var(--line);border-radius:14px;padding:12px 16px;margin:12px 0}"
       ".st dl{display:grid;grid-template-columns:7em 1fr;gap:4px 10px;font-size:13px;margin:8px 0}.st dt{font-weight:800;color:var(--mut)}"
       ".gbtn{display:block;text-align:center;background:#bf0000;color:#fff!important;font-weight:900;border-radius:12px;padding:12px;text-decoration:none;margin:10px 0 4px;box-shadow:0 4px 0 rgba(0,0,0,.2)}")


def build():
    d = json.loads(DATA.read_text(encoding="utf-8"))
    ck = datetime.date.fromisoformat(d["checked"])
    S = d["stores"]
    live = [s for s in S if not s["status"]]
    rows = "".join(f"<tr><td>{esc(s['name'])}</td><td>{cell(s['first'])}{src(s['first_src'])}</td><td>{cell(s['point'])}{src(s['point_src'])}</td>"
                   f"<td>{cell(s['free'])}{src(s['free_src'])}</td><td>{cell(s['sub'])}{src(s['sub_src'])}</td><td>{esc(s['app'])}</td><td>{esc(s['company'])}</td></tr>" for s in live)
    by = {s["id"]: s for s in S}
    picks = [("初回をとにかく安く", "booklive", "新規会員限定70%OFFクーポン（ほぼ全作品対象）"),
             ("楽天ポイントで買いたい・貯めたい", "kobo", "初購入ポイント70倍（上限2,000pt）・楽天ポイントで支払える"),
             ("PayPayユーザー", "ebookjapan", "初回ログインで70%OFFクーポン＋金曜の「コミックウィークエンド」でPayPayポイントが増える"),
             ("無料でたくさん読みたい", "mangaoh", "公式表記で常時10,000冊以上の無料漫画"),
             ("読み放題で読みたい", "bookwalker", "マンガコース月額836円／MAXコース月額1,100円"),
             ("まとめ買いでポイント重視", "dmm", "公式表記「9割の作品が25%以上ポイント還元」")]
    pk = "".join(f"<div><span>{esc(k)}なら</span><b>{esc(by[i]['name'])}</b><br><small>{esc(r)}</small></div>" for k, i, r in picks)
    secs = ""
    for s in S:
        u, aff = go(s)
        rel = "sponsored nofollow noopener" if aff else "noopener"
        if s["status"]:
            secs += (f"<div class=st id={s['id']}><h3>{esc(s['name'])}</h3><p class=stop>⚠️ {esc(s['status'])}{src(s.get('status_src', ''))}</p>"
                     f"<p class=note>再開の状況は運営会社の発表を確認してください。当ページでは、全面再開を確認するまで比較表から外しています。</p></div>")
            continue
        good = "".join(f"<li>{esc(g)}</li>" for g in s["good"])
        secs += (f"<div class=st id={s['id']}><h3>{esc(s['name'])}</h3><ul>{good}</ul><dl>"
                 f"<dt>初回特典</dt><dd>{cell(s['first'])}{src(s['first_src'])}</dd><dt>ポイント</dt><dd>{cell(s['point'])}{src(s['point_src'])}</dd>"
                 f"<dt>無料作品</dt><dd>{cell(s['free'])}{src(s['free_src'])}</dd><dt>読み放題</dt><dd>{cell(s['sub'])}{src(s['sub_src'])}</dd>"
                 f"<dt>支払い</dt><dd>{cell(s['pay'])}{src(s['pay_src'])}</dd><dt>読み方</dt><dd>{esc(s['app'])}</dd><dt>運営</dt><dd>{esc(s['company'])}</dd></dl>"
                 f"<a class=gbtn href='{esc(u)}' rel='{rel}' target=_blank>{esc(s.get('aff_label') or (s['name'] + 'の公式サイトを見る'))} ›</a>"
                 + (f"<p class=note>{esc(s['aff_note'])}</p>" if s.get("aff_note") else "") + "</div>")
    title = f"電子書籍の初回クーポン・ポイント還元を比較【{ck.year}年{ck.month}月】マンガアプリ{len(live)}社"
    desc = f"【{ck.month}/{ck.day}確認】ブックライブ・ebookjapanは初回70%OFF、楽天Koboは初回ポイント70倍、BOOK☆WALKERは50%還元。マンガアプリ{len(live)}社の初回クーポン・ポイント還元・無料作品数・読み放題を公式情報だけで比較。"
    body = (f"<div style='margin:10px 0 14px'><h1 style='font-size:19px;margin:0 0 4px'>{esc(title)}</h1>"
            f"<p style='font-size:13px;color:#5f5f5f;margin:0'>各ストアの公式ページで確認した事実だけをまとめています（{ck.year}/{ck.month}/{ck.day}確認・毎週見直し）。公式で確認できなかった項目は「未確認」と書いています。</p></div>"
            f"<style>{CSS}</style>"
            + "".join(f"<p class=stop>⚠️ <b>{esc(s['name'])}</b>：{esc(s['status'])}{src(s.get('status_src', ''))}</p>" for s in S if s["status"])
            + f"<h2>目的別のおすすめ</h2><div class=pk>{pk}</div>"
            f"<h2>比較表（{ck.month}/{ck.day}確認）</h2><div class=scroll><table class=sc><tr><th>ストア</th><th>初回特典</th><th>ポイント還元</th><th>無料作品</th><th>読み放題</th><th>読み方</th><th>運営会社</th></tr>{rows}</table></div>"
            f"<p class=note>キャンペーンは期間限定のことが多く、内容が変わります。利用前に、各ストアの公式ページ（表の「出典」）で最新の条件を確認してください。</p>"
            f"<h2>ストアごとの特徴</h2>{secs}"
            f"<h2>どこで読むか迷ったら</h2><p>読みたい作品が決まっているなら、まずその作品が「無料で読めるストア」から試すのがおすすめです。"
            f"いま1巻が無料の作品は「<a href='theme/free-now.html'>いま無料で読めるマンガ</a>」、これから出る新刊は「<a href='new-releases.html'>新刊の発売日カレンダー</a>」にまとめています。</p>")
    ld = {"@context": "https://schema.org", "@type": "Article", "headline": title, "description": desc, "dateModified": d["checked"],
          "url": "https://totalyamanote.github.io/manga/store-compare.html", "inLanguage": "ja",
          "author": {"@type": "Organization", "name": "やまのて編集部", "url": "https://totalyamanote.github.io/about.html"},
          "publisher": {"@type": "Organization", "name": "やまのて", "logo": {"@type": "ImageObject", "url": "https://totalyamanote.github.io/img/brand/logo_400.png"}},
          "mainEntity": {"@type": "ItemList", "itemListElement": [{"@type": "ListItem", "position": i, "name": s["name"], "url": s["url"]} for i, s in enumerate(live, 1)]}}
    head = "<script type=application/ld+json>" + json.dumps(ld, ensure_ascii=False) + "</script>"
    page = gm.page(title, desc, body, 0, head=head).replace(
        "<p class=pr>PR｜このサイトはアフィリエイト広告（バリューコマース）を利用しています。</p>",
        "<p class=pr>PR｜このページはアフィリエイト広告（バリューコマース・楽天アフィリエイト・Amazonアソシエイト）を利用しています。順位や評価は報酬で変えていません。</p>")
    OUT.write_text(page, encoding="utf-8")
    print("ストア比較", len(live), "ストア（停止中", len(S) - len(live), "）")


if __name__ == "__main__":
    build()
