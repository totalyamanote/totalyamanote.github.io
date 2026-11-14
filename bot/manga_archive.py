"""マンガ作品ページの蓄積：無料の期限が過ぎた作品ページを消さず、その場で『無料終了』表示にして残す。

毎朝の自動更新（daily.yml）から呼ぶ。何度実行しても結果は同じ（冪等）。

1. manga/w/ の作品ページで『1巻無料はM/Dまで』の期限が過ぎたもの
   → 同じURLのまま「無料期間は終了」表示に変える（あらすじ・登場人物・読者の声はそのまま）。
2. 生成ツールが期限切れページを消していても、git 履歴から最後の版を復元して manga/w/ に戻す。
3. manga/index.html に「無料が終わった作品」の段を入れる（終了した作品が一覧から消えない）。
4. 同じ作品がまた無料になり、生成ツールがページを作り直すと、終了表示と一覧の段から自動で外れる
   （期限が未来の通常ページには手を触れない）。

環境変数 SITE_DIR（既定: リポジトリ直下）、TODAY（YYYY-MM-DD・テスト用）。
"""
import html
import os
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

SITE = Path(os.environ.get("SITE_DIR") or Path(__file__).resolve().parent.parent).resolve()
MANGA = SITE / "manga"
W = MANGA / "w"
TITLE_RE = re.compile(r"1巻無料は(\d{1,2})/(\d{1,2})まで")
MARK_RE = re.compile(r"<!--ended:(\d{4}-\d{2}-\d{2})-->")
LIST_RE = re.compile(r"<!--ended-list-->.*?<!--/ended-list-->\n?", re.S)
WD = "月火水木金土日"


def today():
    t = os.environ.get("TODAY")
    return datetime.strptime(t, "%Y-%m-%d").date() if t else datetime.now().date()


def deadline_of(page):
    """作品ページから無料の最終日を取り出す。無料表示でない（終了済み・転送など）なら None。"""
    m = TITLE_RE.search(page)
    if not m:
        return None
    s = re.search(r"(\d{4})-(\d{2})-(\d{2})時点", page)
    base = date(int(s[1]), int(s[2]), int(s[3])) if s else today()
    mo, d = int(m[1]), int(m[2])
    y = base.year + (1 if (mo, d) < (base.month, base.day) and base.month - mo > 6 else 0)
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def md(d):
    return f"{d.month}/{d.day}"


def make_ended_page(page, dl):
    """現行（無料中）の作品ページ → 『無料終了』版。URL・canonical はそのまま。"""
    end = f"{md(dl)}（{WD[dl.weekday()]}）"
    page = re.sub(r"1巻無料は\d{1,2}/\d{1,2}まで", f"1巻の無料は終了（{md(dl)}まで）", page)
    page = re.sub(r"1巻が\d{1,2}/\d{1,2}（.）まで無料", f"1巻は{end}まで無料でした（現在は終了）", page)
    page = re.sub(
        r"<span class=free>1巻 無料</span> <span class=left>[^<]*</span>",
        "<span class=free style='background:#78716c'>無料期間は終了</span> "
        f"<span class=left>{dl.month}月{dl.day}日（{WD[dl.weekday()]}）まで無料でした</span>",
        page, count=1)
    banner = (f"<p class=note style='border:1px solid #d6d3d1;background:#f5f5f4;border-radius:8px;padding:8px 12px;margin:0 0 12px'>"
              f"📦 この作品の1巻無料は{end}に終了しました。また無料になったら、このページを更新してお知らせします。"
              f"いま無料の作品は<a href='../theme/free-now.html'>「いま無料で読めるマンガ」</a>へ。</p><!--ended:{dl.isoformat()}-->")
    return page.replace("<p class=pr>", banner + "<p class=pr>", 1)


def git(*a):
    return subprocess.run(["git", "-C", str(SITE), *a], capture_output=True, text=True, encoding="utf-8")


def deleted_from_history():
    """生成ツールに消された作品ページ：{id: 最後の版のHTML}。"""
    r = git("log", "--diff-filter=D", "--name-only", "--format=", "--", "manga/w")
    out = {}
    for p in dict.fromkeys(x for x in r.stdout.split("\n") if x.endswith(".html")):
        h = git("log", "-1", "--format=%H", "--", p).stdout.strip()
        if not h:
            continue
        s = git("show", f"{h}^:{p}")
        if s.returncode == 0:
            out[Path(p).stem] = s.stdout
    return out


def card(wid, page):
    g = re.search(r"class=hero style='--g1:([^;]+);--g2:([^']+)'", page)
    g1, g2 = (g[1], g[2]) if g else ("#57534e", "#a8a29e")
    name = html.unescape((re.search(r'og:title content="([^"]*)"', page) or [0, wid])[1])
    imgs = re.findall(r"<img src='([^']+/M\.jpg)'", (re.search(r"<div class=vols>.*?</div>", page, re.S) or [""])[0])[:4]
    th = "".join(f"<img src='{u}' alt='{html.escape(name)}の表紙' loading=lazy onerror=\"this.style.display='none'\">" for u in imgs)
    st = re.search(r"<span class=stars>(★[\d.]+)</span>", page)
    au = re.search(r"<th>著者</th><td>([^<]*)</td>", page)
    dl = date.fromisoformat(MARK_RE.search(page)[1])
    return (f"<a class=card style='--g1:{g1};--g2:{g2}' href='w/{wid}.html'><div class=thumb>{th}</div><div class=in>"
            f"<b>{html.escape(name)}</b><br><span class=note>{f'<span class=stars>{st[1]}</span> ' if st else ''}{html.escape(au[1]) if au else ''}</span><br>"
            f"<span class=free style='background:#78716c'>無料終了</span> <span class=left>{md(dl)}まで</span></div></a>"), dl


def update_index_section():
    """manga/index.html に『無料が終わった作品』の段を入れ直す（無ければ外す）。"""
    idx = MANGA / "index.html"
    if not idx.exists():
        return 0
    ended = []
    for f in sorted(W.glob("*.html")):
        t = f.read_text(encoding="utf-8")
        if MARK_RE.search(t):
            c, dl = card(f.stem, t)
            ended.append((dl, f.stem, c))
    ended.sort(reverse=True)  # 新しく終わった順
    t = idx.read_text(encoding="utf-8")
    base = LIST_RE.sub("", t)
    if ended:
        sec = (f"<!--ended-list--><h2>📦 無料が終わった作品（{len(ended)}作品）</h2>"
               f"<p class=note>1巻無料の期間が終わった作品です。あらすじ・登場人物・読者の声は残してあります。また無料になったらお知らせします。</p>"
               f"<div class=grid>{''.join(c for _, _, c in ended)}</div><!--/ended-list-->\n")
        for anchor in ("<h2>まとめ</h2>", "<p class=note>20", "<footer"):
            if anchor in base:
                base = base.replace(anchor, sec + anchor, 1)
                break
    if base != t:
        idx.write_text(base, encoding="utf-8")
    return len(ended)


def main():
    td = today()
    ended_now, restored = [], []
    # 1. 無料中の表示のまま期限が過ぎたページ → その場で終了表示に
    for f in sorted(W.glob("*.html")):
        t = f.read_text(encoding="utf-8")
        dl = deadline_of(t)
        if dl is not None and dl < td:
            f.write_text(make_ended_page(t, dl), encoding="utf-8")
            ended_now.append(f.stem)
    # 2. 生成ツールに消されたページ → 履歴から復元（期限が過ぎているものだけ）
    for wid, t in deleted_from_history().items():
        if (W / f"{wid}.html").exists():
            continue
        dl = deadline_of(t)
        if dl is not None and dl < td:
            W.mkdir(parents=True, exist_ok=True)
            (W / f"{wid}.html").write_text(make_ended_page(t, dl), encoding="utf-8")
            restored.append(wid)
    # 3. マンガ一覧の段
    n = update_index_section()
    print(f"マンガ蓄積: 終了表示に{len(ended_now)} 履歴から復元{len(restored)} 一覧の『終了した作品』{n}件")


if __name__ == "__main__":
    sys.exit(main())
