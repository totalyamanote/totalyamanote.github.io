"""リンクを貼ったときの画像を、ぼやけないものに差し替える（2026-11-27 坂田さん「画像のぼやけは悪」）。

- img/og/<ページ名>.jpg（1200×630。手元の tools/og_cards.py が作る）があるページは、それを使う。
- まだ無いページで、楽天の小さい画像（200〜600ドット指定）なら、大きい指定に変える。
ga.py の apply() から呼ばれるので、手元・クラウドのどの作り直しのあとにも効く。
"""
import hashlib
import importlib.util
import re
from pathlib import Path

BASE = "https://totalyamanote.jp/"
OG = re.compile(r"""(<meta[^>]*property=["']?og:image["']?[^>]*?content=)(['"])([^'"]+)\2([^>]*>)""")
SIZE = re.compile(r"<!--ogsize-->.*?<!--/ogsize-->", re.S)


# ---- ページの中の写真（2026-11-27 坂田さん「サイトの中の画像のぼやけも全部直して」「比較表に画像がないのは入れて」） ----
IMG = re.compile(r"<img\b[^>]*>")
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


def _tables():
    """比較表の見やすい形（bot/tables.py）。"""
    spec = importlib.util.spec_from_file_location("tables", Path(__file__).resolve().parent / "tables.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


TABLES = _tables()


def photos(t):
    t = IMG.sub(lambda m: sharp_src(m.group(0)), t)
    return IMG.sub(lambda m: sharp_src(m.group(0)), TABLES.apply(t))


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
