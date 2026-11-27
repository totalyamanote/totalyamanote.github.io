"""リンクを貼ったときの画像を、ぼやけないものに差し替える（2026-11-27 坂田さん「画像のぼやけは悪」）。

- img/og/<ページ名>.jpg（1200×630。手元の tools/og_cards.py が作る）があるページは、それを使う。
- まだ無いページで、楽天の小さい画像（200〜600ドット指定）なら、大きい指定に変える。
ga.py の apply() から呼ばれるので、手元・クラウドのどの作り直しのあとにも効く。
"""
import hashlib
import re
from pathlib import Path

BASE = "https://totalyamanote.jp/"
OG = re.compile(r"""(<meta[^>]*property=["']?og:image["']?[^>]*?content=)(['"])([^'"]+)\2([^>]*>)""")
SIZE = re.compile(r"<!--ogsize-->.*?<!--/ogsize-->", re.S)


# ---- ページの中の写真（2026-11-27 坂田さん「サイトの中の画像のぼやけも全部直して」「比較表に画像がないのは入れて」） ----
IMG = re.compile(r"<img\b[^>]*>")
CTH_CSS = ("<style id=cmpimg>.cmp .cth{display:block;width:72px;height:72px;object-fit:contain;background:#fff;border:1px solid #e5e7eb;border-radius:8px;margin:0 0 6px}.cmp th>.cth,.cmp td>b+.cth,.cmp .cb+.cth{margin:6px 0 4px}"
           ".cmp .cthn{display:block;font-size:10px;font-weight:600;line-height:1.35;color:var(--mut,#665d55);margin:0 0 4px;white-space:normal;max-width:96px}"
           "@media(max-width:480px){.cmp .cth{width:64px;height:64px}"
           # スマホで値段と評価が切れないように、商品の表は1列目を細くする
           ".cmp:has(td>.cth+b){min-width:500px}.cmp:has(td>.cth+b) td:first-child{width:148px;min-width:148px;max-width:148px;font-size:12px;line-height:1.45;overflow-wrap:anywhere}"
           ".cmp:has(td>.cth+b) th,.cmp:has(td>.cth+b) td{padding-left:7px;padding-right:7px}}</style>")


# 元の写真が小さい商品は、同じ商品の大きい公式写真に差し替える（目で見て確かめたものだけ）
BIGGER = (("kanidokoro/cabinet/428/428_r_26thum_1125_3.jpg", "kanidokoro/cabinet/428/26_428_mv.jpg"),
          ("i/n/irodorinosato_702(?![_0-9a-z-])", "i/n/irodorinosato_702_1"))


def sharp_src(tag):
    """写真の小さい指定を大きくする。楽天は600（記事の中の写真は800）、Yahoo!は大きい版。"""
    want = 800 if re.search(r"class=['\"]?(?:pki|cth)\b", tag) is None else 400
    def up(m):
        return "_ex=%dx%d" % (want, want) if max(int(m.group(1)), int(m.group(2))) < want else m.group(0)
    if "thumbnail.image.rakuten.co.jp" in tag:
        tag = re.sub(r"_ex=(\d+)x(\d+)", up, tag)
    tag = re.sub(r"(item-shopping\.c\.yimg\.jp/i)/[cgj]/", r"\1/n/", tag)
    tag = re.sub(r"(res\.booklive\.jp/\d+/\d+/thumbnail)/(?:S|M)\.jpg", r"\1/2L.jpg", tag)
    for old, new in BIGGER:
        tag = re.sub(old, new, tag)
    return tag


def plain(s):
    return re.sub(r"[\s・･\-]", "", re.sub(r"<[^>]+>", "", s)).lower()


def attr(tag, name):
    m = re.search(name + r"""=(?:'([^']*)'|"([^"]*)"|([^\s>]+))""", tag)
    return next((g for g in m.groups() if g is not None), "") if m else ""


def table_images(t):
    """比較表の各行に写真を入れる。商品の表＝その商品の詳しい説明の写真、メーカーの表＝「◯◯の例」の写真。"""
    heads = [(m.start(), m.end(), re.sub(r"<[^>]+>", "", m.group(2)).strip()) for m in re.finditer(r"<h([23])[^>]*>(.*?)</h\1>", t, re.S)]

    def brand(key):
        """メーカー名の見出しの直後にある商品写真（なければ空）。"""
        for k, (s, e, h) in enumerate(heads):
            if len(h) <= 30 and key in plain(h):
                end = heads[k + 1][0] if k + 1 < len(heads) else len(t)
                for i in IMG.findall(t[e:end]):
                    src = attr(i, "src")
                    if "rakuten" in src or "yimg" in src:
                        return attr(i, "alt"), src
        return "", ""

    def product(n):
        for k, (s, e, h) in enumerate(heads):
            if re.match(r"%d[.．]\s*" % n, h):
                end = next((s2 for s2, _, h2 in heads[k + 1:] if re.match(r"\d+[.．]", h2)), len(t))
                for i in IMG.findall(t[e:end]):
                    src = attr(i, "src")
                    if ("rakuten" in src or "yimg" in src or "media-amazon" in src):
                        return src
        return ""

    def row(r, kind):
        m = re.match(r"(<tr[^>]*>\s*<t[dh][^>]*>)(.*?)(</t[dh]>.*)", r, re.S)
        if not m or "<img" in m.group(2):
            return r
        text = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        pic = ""
        if kind == "product":
            n = re.match(r"(\d+)[.．]", text)
            src = product(int(n.group(1))) if n else ""
            if src:
                pic = "<img class=cth src='%s' alt='%sの商品画像' loading=lazy>" % (src, text[:30].replace("'", ""))
        else:
            key = plain(m.group(2))
            alt, src = brand(key) if key else ("", "")
            if src:
                name = re.split(r"の例（|（", alt)[0]
                pic = "<img class=cth src='%s' alt='%s' loading=lazy><span class=cthn>例：%s</span>" % (src, alt.replace("'", ""), name.replace("<", "")[:30])
        if not pic:
            return r
        inner = pic + m.group(2) if kind == "product" else m.group(2) + pic   # メーカーの表は、名前の下に写真
        return m.group(1) + inner + m.group(3)

    def table(m):
        tb = m.group(0)
        first = re.search(r"<tr[^>]*>\s*<t[dh][^>]*>(.*?)</t[dh]>", tb, re.S)
        label = re.sub(r"<[^>]+>", "", first.group(1)).strip() if first else "?"
        kind = "product" if label == "商品" else "brand"
        parts = re.split(r"(?=<tr[\s>])", tb)
        return "".join(parts[:2] + [row(r, kind) for r in parts[2:]])

    new = re.sub(r"""<table[^>]*class=['"]?cmp\b[^>]*>.*?</table>""", table, t, flags=re.S)
    if "class=cth" in new and "id=cmpimg" not in new:
        mark = "<!--ga4-->" if "<!--ga4-->" in new else "</head>"   # 何度実行しても同じ並びになる位置
        new = new.replace(mark, CTH_CSS + mark, 1)
    return new


def photos(t):
    t = IMG.sub(lambda m: sharp_src(m.group(0)), t)
    return IMG.sub(lambda m: sharp_src(m.group(0)), table_images(t))


def swap(root, path, t):
    rel = Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    t = photos(t)
    card = Path(root) / "img" / "og" / (rel[:-5].replace("/", "__") + ".jpg")
    t = SIZE.sub("", t)
    m = OG.search(t)
    if card.exists():
        url = BASE + "img/og/" + card.name + "?v=" + hashlib.md5(card.read_bytes()).hexdigest()[:8]
        size = "<!--ogsize--><meta property=og:image:width content=1200><meta property=og:image:height content=630><!--/ogsize-->"
        if m:
            old = m.group(3)
            t = t[:m.start()] + m.group(1) + "'" + url + "'" + m.group(4) + size + t[m.end():]
            if "/img/og/" not in old and "/img/brand/" not in old:   # Google向けの画像指定も同じものに
                t = t.replace('"image": ["' + old + '"]', '"image": ["' + url + '"]')
            return t
        return t.replace("</head>", "<!--ogsize--><meta property=og:image content='" + url + "'><!--/ogsize--></head>", 1)
    if m and "thumbnail.image.rakuten.co.jp" in m.group(3):
        url = re.sub(r"_ex=\d+x\d+", "_ex=800x800", m.group(3))
        return t[:m.start(3)] + url + t[m.end(3):]
    return t
