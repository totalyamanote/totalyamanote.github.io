"""トップページの見た目（ヘッダー・ヒーロー→毎朝の最安→比較記事カード・セール特集→マンガの段・フッター）を固定する。

run_daily.py はトップを簡素なテンプレートで作り直すため、毎朝そのまま保存すると
見た目が「先祖返り」する。生成後にこのモジュールで、固定の部品を差し込み直す。
部品は直前の index.html にあればそれを引き継ぎ（手元ツールの更新を壊さない）、
無ければ bot/hub/ の保存版を使う。
"""
import re
from datetime import datetime
from pathlib import Path

HUB = Path(__file__).resolve().parent / "hub"
KEYS = ("ld", "basic", "hub", "hubart", "hubm", "ftr")


def _split_old_hub(old):
    """旧形式（ハブの中に セール特集・比較記事 が入っていた）の index.html から、比較記事の段を切り出す。"""
    m = re.search(r"<!--hub-->.*?<!--/hub-->", old or "", re.S)
    if not m:
        return None, None
    h = m.group(0)
    sale = re.search(r"<div class=hsec><h2>🔥 セール特集</h2>.*?</a></div>", h, re.S)
    art = re.search(r"<div class=hsec id=articles>.*?</div></div>(?=<h2 id=daily)", h, re.S)
    if not (sale and art):
        return None, None
    new_hub = h.replace(sale.group(0), "").replace(art.group(0), "")
    arts = art.group(0).replace("<div class=hsec id=articles>", "<div class=hsec id=articles style='margin-top:28px'>", 1)
    return new_hub, "<!--hubart-->" + arts + sale.group(0) + "<!--/hubart-->"


def _block(k, old):
    if old and k in ("hub", "hubart") and "<!--hubart-->" not in old:
        nh, na = _split_old_hub(old)
        if nh:
            return nh if k == "hub" else na
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
    b["hubart"] = _refresh_countdown(b["hubart"], now)
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
    # 末尾：比較記事（とセール特集）→マンガの段→フッター（2026-11-18 坂田さん「毎朝最安を上にして、その下に比較記事」）
    return page.replace("</main></body></html>", b["hubart"] + b["hubm"] + b["ftr"] + "</main></body></html>", 1)
