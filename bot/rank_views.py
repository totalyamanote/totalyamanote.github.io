"""比較記事の一覧（compare/index.html）の先頭に『よく見られている比較記事』を入れる。
閲覧数は bot/data/article_views.json（GA4の表示回数）。多い順に TOP_N 本。同数のときは一覧に出ている順。
何度実行しても同じ（<!--popular-->〜<!--/popular--> を入れ直す）。使い方: python3 bot/rank_views.py
"""
import json, re, pathlib
SITE = pathlib.Path(__file__).resolve().parent.parent
TOP_N = 6
P = SITE / "compare" / "index.html"
V = json.loads((SITE / "bot" / "data" / "article_views.json").read_text(encoding="utf-8"))
views, period = V["views"], V["period"]

t = P.read_text(encoding="utf-8")
t = re.sub(r"<!--popular-->.*?<!--/popular-->", "", t, flags=re.S)

# 一覧に出ているカードを、記事ごとに1枚ずつ集める（NEWバッジは外す）
cards = {}
for m in re.finditer(r"<a class=ha href='\.\./articles/([^'/]+)\.html'>.*?</a>", t, re.S):
    cards.setdefault(m.group(1), re.sub(r"<span class=(newb|dtb)>.*?</span>", "", m.group(0)))
order = {k: i for i, k in enumerate(cards)}
top = sorted((k for k in cards if views.get(k, 0) > 0), key=lambda k: (-views[k], order[k]))[:TOP_N]

def card(k):
    c = cards[k]
    return c.replace("</b></a>", f"</b><span class=dtb>{views[k]}回</span></a>")

blk = ("<!--popular--><h2 class=cmph>🔥 よく見られている比較記事<small>（過去28日・多い順）</small></h2><div class=hgrid>"
       + "".join(card(k) for k in top) + "</div><!--/popular-->")
i = t.find("<h2 class=cmph>🆕 新着の比較記事")
assert i > 0, "新着の見出しが見つからない"
t = t[:i] + blk + t[i:]
P.write_text(t, encoding="utf-8")
print("popular:", [(k, views[k]) for k in top], "period", period)
