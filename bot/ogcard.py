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


def swap(root, path, t):
    rel = Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
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
