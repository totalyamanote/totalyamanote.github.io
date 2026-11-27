"""比較表を、スマホでも右が切れない見やすい形にする（2026-11-27 坂田さん）。

- 商品の表：写真・短い名前・特徴／実質価格と小さなお店リンク／評価、の3列。長い商品名と大きいボタンは出さない。
- メーカー・お店の表：商品の写真（なければ公式サイトのロゴ）と名前だけ。色つきの名前ボタンは出さない。
  列が多い文章の表は、スマホでは1社ずつの箱にする。○×の表は画面の幅に収める。
- ogcard.py（ga.py）から全ページに毎回かかる。何度実行しても同じ。作り直し前の形の表にだけ手を入れる。
- 短い商品名は data/table_names.json（お店/商品コード → 名前）。無いものは商品名から自動で短くする。
- Amazon・楽天・Yahoo! のロゴは、アフィリエイトの規約で勝手に使えないので入れない（名前だけ）。
"""
import html
import json
import re
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name):
    try:
        return json.loads((HERE / "data" / name).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


NAMES = _load("table_names.json")
LOGOS = _load("logos.json")   # 表の名前 → {"f": ファイル名, "w": 表示の幅, "h": 表示の高さ}
TABLE = re.compile(r"""<table[^>]*class=['"]?cmp\b[^>]*>.*?</table>""", re.S)
IMG = re.compile(r"<img\b[^>]*>")
ROW = re.compile(r"<tr\b[^>]*>.*?</tr>", re.S)
CELL = re.compile(r"<(t[dh])\b([^>]*)>(.*?)</\1>", re.S)
PROMO = re.compile(r"送料無料|楽天\S*位|\S*位獲得|レビュー\S*件?|クーポン\S*|\S*%OFF\S*|\S*OFF\S*|限定|予約|早割|公式|訳あり|ランキング\S*|まで\S*|\S*倍")

CSS = ("<style id=cmpimg>"
       ".cmp .cth{display:block;width:72px;height:72px;object-fit:contain;background:#fff;border:1px solid #e5e7eb;border-radius:8px;margin:0 auto 4px}"
       # 商品の表（3列・画面の幅に収める）
       ".cmp.cmpx{min-width:0!important;width:100%;table-layout:fixed;font-size:13px}"
       ".cmpx th{white-space:nowrap;font-size:12px;padding:8px 6px!important}"
       ".cmpx th:nth-child(1){width:44%}.cmpx th:nth-child(2){width:33%}.cmpx th:nth-child(3){width:23%}"
       ".cmpx td{vertical-align:middle;padding:12px 6px!important;overflow-wrap:anywhere;white-space:normal!important}"
       ".cmpx .cn{text-align:left}.cmpx .cn .cth{margin:0 0 6px;width:76px;height:76px}"
       ".cmpx .cn b{display:block;font-size:13px;line-height:1.45}.cmpx .cn .win{margin:4px 4px 0 0;font-size:10px}"
       ".cmpx .cf{display:block;font-size:11px;line-height:1.5;color:var(--mut,#665d55);margin-top:4px}"
       ".cmpx .cp .effv{display:block;font-size:16px;color:#bf0000;white-space:nowrap}.cmpx .cp .note{display:block;font-size:11px;margin:0}"
       ".cmpx .cl{display:block;margin-top:6px;line-height:2.1}.cmpx a.tl{display:inline-block;margin-right:10px;font-size:12.5px;font-weight:800;text-decoration:underline;white-space:nowrap}"
       ".cmpx .cr b{display:block;font-size:15px;color:#d97706}.cmpx .cr span{display:block;font-size:11px;color:var(--mut,#665d55)}"
       # メーカー・お店の名前と写真
       ".cmp .bm{display:flex;flex-direction:column;align-items:center;gap:5px;text-align:center}"
       ".cmp .bm .cth{width:60px;height:60px;margin:0}.cmp .bm .lg{display:block;object-fit:contain;max-width:100%}"
       ".cmp .bn{display:block;font-size:11.5px;font-weight:800;line-height:1.35;white-space:normal;overflow-wrap:anywhere}"
       "@media(max-width:600px){"
       ".cmp.cmpfit{min-width:0!important;width:100%;table-layout:fixed;font-size:11.5px}"
       ".cmpfit th,.cmpfit td{padding:8px 3px!important;white-space:normal!important;overflow-wrap:anywhere;min-width:0!important}"
       ".cmpfit tr>:first-child{width:80px}"
       ".cmpfit .bn{font-size:10.5px;letter-spacing:-.2px}"
       ".cmp.cmpfit tr:first-child>*{font-size:10px;padding:6px 1px!important;line-height:1.35;word-break:keep-all;overflow-wrap:anywhere}"
       ".cmp.cmpcard{min-width:0!important;width:100%;border:0;background:none}"
       ".cmpcard tbody,.cmpcard tr,.cmpcard th,.cmpcard td{display:block;width:auto!important;min-width:0!important;text-align:left!important;white-space:normal!important}"
       ".cmpcard tr:first-child{display:none}"
       ".cmpcard tr{border:1px solid var(--line,#e7e5e4);border-radius:12px;background:var(--card,#fff);padding:10px 12px;margin:0 0 12px}"
       ".cmpcard tr>:first-child{border:0!important;background:none!important;padding:0 0 8px!important;position:static!important}"
       ".cmpcard .bm{flex-direction:row;gap:10px;text-align:left}.cmpcard .bn{font-size:15px}"
       ".cmpcard td{border:0!important;border-top:1px solid var(--line,#eee)!important;padding:7px 0!important;font-size:13.5px;line-height:1.65}"
       ".cmpcard td::before{content:attr(data-label);display:block;font-size:11px;font-weight:800;color:var(--mut,#665d55)}"
       ".cmpcard td:first-child::before{content:none}}"
       "</style>")


def text(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def attr(tag, name):
    m = re.search(name + r"""=(?:'([^']*)'|"([^"]*)"|([^\s>]+))""", tag)
    return next((g for g in m.groups() if g is not None), "") if m else ""


def plain(s):
    return re.sub(r"[\s・･\-]", "", text(s)).lower()


def headings(t):
    return [(m.start(), m.end(), text(m.group(2))) for m in re.finditer(r"<h([23])[^>]*>(.*?)</h\1>", t, re.S)]


def product_photo(t, heads, n):
    """商品の詳しい説明（見出し「n. …」）の最初の写真。"""
    for k, (s, e, h) in enumerate(heads):
        if re.match(r"%d[.．]\s*" % n, h):
            end = next((s2 for s2, _, h2 in heads[k + 1:] if re.match(r"\d+[.．]", h2)), len(t))
            for i in IMG.findall(t[e:end]):
                src = attr(i, "src")
                if "rakuten" in src or "yimg" in src or "media-amazon" in src:
                    return src
    return ""


def brand_photo(t, heads, key):
    """メーカー名の見出しの直後にある商品写真（なければ空）。"""
    for k, (s, e, h) in enumerate(heads):
        if key and len(h) <= 30 and key in plain(h):
            end = heads[k + 1][0] if k + 1 < len(heads) else len(t)
            for i in IMG.findall(t[e:end]):
                src = attr(i, "src")
                if "rakuten" in src or "yimg" in src:
                    return attr(i, "alt"), src
    return "", ""


def short_name(row, name):
    u = urllib.parse.unquote(" ".join(re.findall(r"""href=['"]([^'"]*)""", row)))
    k = (re.search(r"item\.rakuten\.co\.jp/([^/&]+)/([^/&?]+)", u) or re.search(r"store\.shopping\.yahoo\.co\.jp/([^/&]+)/([^/&?.]+)", u))
    if k and f"{k.group(1)}/{k.group(2)}" in NAMES:
        return NAMES[f"{k.group(1)}/{k.group(2)}"]
    s = re.sub(r"【[^】]*】|\[[^\]]*\]|［[^］]*］|《[^》]*》|≪[^≫]*≫|＼[^／]*／|\\[^/]*/|（[^）]*）|\([^)]*\)|[★☆◎●｜|…]", " ", name)
    s = PROMO.sub(" ", re.sub(r"^.*?まで】", "", s))
    out = ""
    for w in s.split():
        if out and len(out) + len(w) > 18:
            break
        out = (out + " " + w).strip()
    return (out or name)[:20]


def product_table(t, heads, rows):
    """商品の表を3列にする。読めない行があれば、そのままにする（None）。"""
    new = ["<tr><th>商品</th><th>実質価格</th><th>評価</th></tr>"]
    items = []
    for r in rows[1:]:
        if "ifrow" in r or re.search(r"<td[^>]*colspan", r):
            if items:
                items[-1]["feats"] = [text(x) for x in re.findall(r"<span class=ifb>(.*?)</span>", r, re.S)] or items[-1]["feats"]
            continue
        cells = [c[2] for c in CELL.findall(r)]
        m = re.search(r"<b>\s*(\d+)[.．]\s*(.*?)</b>", cells[0], re.S) if cells else None
        price = next((c for c in cells[1:] if "effv" in c), "")
        review = next((c for c in cells[1:] if "件" in c and "★" in c), "")
        if not (m and price and review):
            return None
        img = IMG.search(cells[0])
        src = attr(img.group(0), "src") if img else product_photo(t, heads, int(m.group(1)))
        items.append({"row": r, "n": int(m.group(1)), "name": text(m.group(2)), "src": src, "price": price, "review": review,
                      "wins": "".join(re.findall(r"<span class=win>.*?</span>", cells[0], re.S)),
                      "feats": [text(x) for x in re.findall(r"<span class=fb>(.*?)</span>", r, re.S)],
                      "links": [a for a in re.findall(r"<a\b[^>]*>(?:楽天|Yahoo!|Amazon)(?:で見る)?</a>", r)]})
    if not items:
        return None
    for it in items:
        name = short_name(it["row"], it["name"])
        pic = f"<img class=cth src='{it['src']}' alt='{html.escape(name, quote=True)}の商品画像' loading=lazy>" if it["src"] else ""
        feats = "・".join(f for f in it["feats"][:2] if f)
        feat = f"<small class=cf>{html.escape(feats)}</small>" if feats else ""
        price = re.sub(r"<br\s*/?>", "", it["price"])
        links = "".join(re.sub(r"""class=(?:'mini ([ryas])'|"mini ([ryas])"|([ryas])(?=[\s>]))""",
                               lambda m: "class='tl %s'" % next(g for g in m.groups() if g), a) for a in it["links"])
        cnt = re.search(r"([\d,]+)件", text(it["review"]))
        star = re.search(r"★\s*([\d.]+)", text(it["review"]))
        rv = (f"<b>★{star.group(1)}</b>" if star else "") + (f"<span>{cnt.group(1)}件</span>" if cnt else "")
        new.append(f"<tr><td class=cn>{pic}<b>{it['n']}. {html.escape(name)}</b>{it['wins']}{feat}</td>"
                   f"<td class=cp>{price}<span class=cl>{links}</span></td><td class=cr>{rv}</td></tr>")
    return "<table class='cmp cmpx'>" + "".join(new) + "</table>"


def media(t, heads, name):
    """名前の上に出す写真かロゴ。"""
    alt, src = brand_photo(t, heads, plain(name))
    if src:
        return f"<img class=cth src='{src}' alt='{html.escape(text(alt) or name, quote=True)}' loading=lazy>"
    lg = LOGOS.get(name)
    if lg:
        return (f"<img class=lg src='../img/logos/{lg['f']}' alt='{html.escape(name, quote=True)}のロゴ' "
                f"width={lg['w']} height={lg['h']} style='width:{lg['w']}px;height:auto' loading=lazy>")
    return ""


def brand_cell(t, heads, inner):
    """名前のボタンや前に足した写真を外して、名前を取り出し、「写真かロゴ＋名前」にする。名前が無ければそのまま。"""
    m = re.search(r"<span class=(?:cb|bn)\b[^>]*>(.*?)</span>", inner, re.S)
    if not m:
        return None
    name = text(m.group(1))
    return f"<div class=bm>{media(t, heads, name)}<span class=bn>{html.escape(name)}</span></div>"


def join_row(cells):
    return "<tr>" + "".join(f"<{tag}{a}>{v}</{tag}>" for tag, a, v in cells) + "</tr>"


def other_table(t, heads, tag, rows):
    cls = re.search(r"""class=(?:'([^']*)'|"([^"]*)"|(\S+?)(?=[\s>]))""", tag)
    cls = next(g for g in cls.groups() if g)
    grid = [CELL.findall(r) for r in rows]
    if not grid or not grid[0]:
        return None
    head = grid[0]
    brands_top = sum("class=cb" in c[2] for c in head[1:]) >= 2
    if brands_top and all(len(r) == len(head) for r in grid):   # 会社が横に並ぶ表は、縦（1社1行）に直す
        grid = [[list(grid[r][c]) for r in range(len(grid))] for c in range(len(head))]
        grid[0] = [("th", g[1], re.sub(r"<br\s*/?>", "", g[2])) for g in grid[0]]
        for row in grid[1:]:
            row[0] = ("th", " class=lab", row[0][2])
            row[1:] = [("td", "", c[2]) for c in row[1:]]
        head = grid[0]
    product_cols = text(head[0][2]) == "商品"
    labels = [text(re.sub(r"<span class=note>.*?</span>", "", c[2])) for c in head]
    body = []
    for row in grid[1:]:
        row = [list(c) for c in row]
        cell = brand_cell(t, heads, row[0][2])
        if cell:
            row[0][2] = cell
        body.append(row)
    wide = (len(head) >= 5 or (product_cols and len(head) >= 4)) and "mxt" not in cls
    cls = "cmp " + ("cmpcard" if wide else "cmpfit") + (" mxt" if "mxt" in cls else "")
    out = [join_row(head)]
    for row in body:
        if wide:
            row = [row[0]] + [[c[0], c[1] + f" data-label='{html.escape(labels[i], quote=True)}'" if i < len(labels) and "data-label" not in c[1] else c[1], c[2]]
                              for i, c in enumerate(row[1:], 1)]
        out.append(join_row(row))
    return f"<table class='{cls}'>" + "".join(out) + "</table>"


def apply(t):
    if "<table" not in t:
        return t
    heads = headings(t)

    def one(m):
        tb = m.group(0)
        tag = tb[:tb.index(">") + 1]
        if re.search(r"\bcmp(x|card|fit)\b", tag):
            return tb
        rows = ROW.findall(tb)
        if len(rows) < 2:
            return tb
        head = [text(c[2]) for c in CELL.findall(rows[0])]
        if head and head[0] == "商品" and len(head) >= 3 and "実質" in head[1] and all(
                h == "" or h == "商品" or "実質" in h or "レビュー" in h or h.startswith("特徴") for h in head):
            return product_table(t, heads, rows) or tb
        return other_table(t, heads, tag, rows) or tb

    new = TABLE.sub(one, t)
    # 形を直し終えた表でも、写真もロゴも無い名前には、あとから足せるようになったロゴを入れる
    new = re.sub(r"<div class=bm><span class=bn>(.*?)</span></div>",
                 lambda m: "<div class=bm>%s<span class=bn>%s</span></div>" % (media(t, heads, text(m.group(1))), m.group(1)), new)
    new = re.sub(r"<style id=cmpimg>.*?</style>", "", new, flags=re.S)
    if re.search(r"class='cmp cmp(x|card|fit)", new):
        mark = "<!--ga4-->" if "<!--ga4-->" in new else "</head>"   # 何度実行しても同じ並びになる位置
        new = new.replace(mark, CSS + mark, 1)
    return new
