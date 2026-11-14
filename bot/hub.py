"""トップページの見た目（ヘッダー・ヒーロー・セール特集・比較記事カード・マンガの段・フッター）を固定する。

run_daily.py はトップを簡素なテンプレートで作り直すため、毎朝そのまま保存すると
見た目が「先祖返り」する。生成後にこのモジュールで、固定の部品を差し込み直す。
部品は直前の index.html にあればそれを引き継ぎ（手元ツールの更新を壊さない）、
無ければ bot/hub/ の保存版を使う。
"""
import re
from datetime import datetime
from pathlib import Path

HUB = Path(__file__).resolve().parent / "hub"
KEYS = ("ld", "basic", "hub", "hubm", "ftr")


def _block(k, old):
    if old:
        m = re.search(rf"<!--{k}-->.*?<!--/{k}-->", old, re.S)
        if m:
            return m.group(0)
    return (HUB / f"{k}.html").read_text(encoding="utf-8")


def _refresh_countdown(s, now):
    """セール特集のチップ『（あとN日）』を今日の日付で数え直す。"""
    def f(m):
        try:
            d = datetime(now.year, int(m.group(2)), int(m.group(3)))
        except ValueError:
            return m.group(0)
        n = (d.date() - now.date()).days
        if n < 0:
            return m.group(0)
        return f"{m.group(1)}{m.group(2)}/{m.group(3)}{m.group(4)}（" + ("本日開始" if n == 0 else f"あと{n}日") + "）"
    return re.sub(r"(<span class=chip>[^<]*?)(\d+)/(\d+)([^<（]*?)（(?:あと\d+日|本日開始)）", f, s)


def apply_hub(page, old=None, now=None):
    now = now or datetime.now()
    b = {k: _block(k, old) for k in KEYS}
    b["hub"] = _refresh_countdown(b["hub"], now)
    title = (re.search(r"<title>(.*?)</title>", old or "") or [None, None])[1]
    if not old or "<!--hub-->" not in old:
        title = (HUB / "title.txt").read_text(encoding="utf-8")
    page = re.sub(r"<title>.*?</title>", lambda m: f"<title>{title}</title>", page, 1, re.S)
    # head: ld+basic は </head> の直前へ
    page = page.replace("</head>", b["ld"] + b["basic"] + "</head>", 1)
    # 本文先頭：簡素版の h1 を、ヘッダー〜比較記事カードの固定部品に置き換え
    page = re.sub(r"<main>\s*<h1>.*?</h1>", lambda m: "<main>" + b["hub"], page, 1, re.S)
    # 簡素版だけにある重複ブロック（リンク帯・比較記事の箇条書き）を外す
    page = re.sub(r"<p class=pr>🛒.*?</p>\n?", "", page, 1, re.S)
    page = re.sub(r"<section><h2>比較記事（選び方とおすすめ）</h2>.*?</section>\n?", "", page, 1, re.S)
    # 末尾：マンガの段とフッター
    return page.replace("</main></body></html>", b["hubm"] + b["ftr"] + "</main></body></html>", 1)
