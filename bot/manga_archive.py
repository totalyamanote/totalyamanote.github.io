"""マンガ作品ページのアーカイブ：無料の期限が過ぎた作品を消さずに manga/past/ に蓄積する。

毎朝の自動更新（daily.yml）から呼ぶ。何度実行しても結果は同じ（冪等）。

1. manga/w/ の作品ページで『1巻無料はM/Dまで』の期限が過ぎたものを
   → manga/past/<id>.html に「無料終了」表示つきで保存し、
   → manga/w/<id>.html は past への転送ページ（canonical つき）に置き換える。
2. 生成ツールが期限切れページを消していても、git 履歴から最後の版を復元して past に入れる。
3. manga/past/index.html に終了した作品の一覧（新しく終わった順）を作る。
4. 全マンガページのメニューに「アーカイブ」リンクを足す（無ければ）。

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
W, PAST = MANGA / "w", MANGA / "past"
ORIGIN = "https://totalyamanote.github.io"
TITLE_RE = re.compile(r"1巻無料は(\d{1,2})/(\d{1,2})まで")
MARK_RE = re.compile(r"<!--ended:(\d{4}-\d{2}-\d{2})-->")


def today():
    t = os.environ.get("TODAY")
    return datetime.strptime(t, "%Y-%m-%d").date() if t else datetime.now().date()


def deadline_of(page):
    """作品ページから無料の最終日を取り出す。無料でなければ None。"""
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


WD = "月火水木金土日"


def make_archive_page(page, wid, dl):
    """現行の作品ページ → 『無料終了』版（past 用）。"""
    end = f"{md(dl)}（{WD[dl.weekday()]}）"
    page = re.sub(r"1巻無料は\d{1,2}/\d{1,2}まで", f"1巻の無料は終了（{md(dl)}まで）", page)
    page = re.sub(r"1巻が\d{1,2}/\d{1,2}（.）まで無料", f"1巻は{end}まで無料でした（現在は終了）", page)
    # ヒーローの「1巻 無料／M月D日（曜）まで・あとN日」を終了表示に
    page = re.sub(
        r"<span class=free>1巻 無料</span> <span class=left>[^<]*</span>",
        "<span class=free style='background:#78716c'>無料期間は終了</span> "
        f"<span class=left>{dl.month}月{dl.day}日（{WD[dl.weekday()]}）まで無料でした</span>",
        page, count=1)
    # 公開URL（canonical / og:url / JSON-LD）を past に
    page = page.replace(f"{ORIGIN}/manga/w/{wid}.html", f"{ORIGIN}/manga/past/{wid}.html")
    # 「ほかの作品」の相対リンクは w/ を指す（期限切れは w/ から past/ へ転送される）
    page = re.sub(r"href='(\d+)\.html'", r"href='../w/\1.html'", page)
    banner = (f"<p class=note style='border:1px solid #d6d3d1;background:#f5f5f4;border-radius:8px;padding:8px 12px;margin:0 0 12px'>"
              f"📦 <b>アーカイブ</b>：この作品の1巻無料は{end}に終了しました。いま無料の作品は"
              f"<a href='../theme/free-now.html'>「いま無料で読めるマンガ」</a>、終わった作品は"
              f"<a href='index.html'>アーカイブ一覧</a>へ。</p><!--ended:{dl.isoformat()}-->")
    return page.replace("<p class=pr>", banner + "<p class=pr>", 1)


def redirect_stub(wid):
    u = f"{ORIGIN}/manga/past/{wid}.html"
    return (f"<!doctype html><html lang=ja><head><meta charset=utf-8><title>アーカイブへ移動しました</title>"
            f"<meta http-equiv=refresh content='0;url=../past/{wid}.html'><link rel=canonical href='{u}'>"
            f"<meta name=robots content='noindex,follow'></head><body><p><a href='../past/{wid}.html'>この作品のページ（アーカイブ）へ</a></p></body></html>")


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
    return (f"<a class=card style='--g1:{g1};--g2:{g2}' href='{wid}.html'><div class=thumb>{th}</div><div class=in>"
            f"<b>{html.escape(name)}</b><br><span class=note>{f'<span class=stars>{st[1]}</span> ' if st else ''}{html.escape(au[1]) if au else ''}</span><br>"
            f"<span class=free style='background:#78716c'>無料終了</span> <span class=left>{md(dl)}まで</span></div></a>"), dl


def build_index(pages):
    items = sorted((card(w, p) + (w,) for w, p in pages.items()), key=lambda x: (x[1], x[2]), reverse=True)
    first = next(iter(pages.values()))
    n = len(items)
    title = f"終了したマンガ無料キャンペーンのアーカイブ（{n}作品）｜やまのてマンガ"
    desc = f"1巻無料の期間が終わったマンガ{n}作品の記録。あらすじ・登場人物・読者の声は、そのまま読めます。いま無料の作品は「いま無料で読めるマンガ」へ。"
    head = first[:first.index("<body>")]
    head = re.sub(r"<script type=application/ld\+json>.*?</script>", "", head, flags=re.S)
    head = re.sub(r"<title>.*?</title>", lambda m: f"<title>{html.escape(title)}</title>", head, count=1, flags=re.S)
    head = re.sub(r'(<meta (?:name=description|property=og:description) content=")[^"]*"', lambda m: m[1] + html.escape(desc, quote=True) + '"', head)
    head = re.sub(r'(<meta property=og:title content=")[^"]*"', lambda m: m[1] + html.escape(title, quote=True) + '"', head)
    head = head.replace("og:type content=book", "og:type content=website")
    head = re.sub(r"(<link rel=canonical href=')[^']*'", lambda m: m[1] + f"{ORIGIN}/manga/past/index.html'", head)
    head = re.sub(r"(og:url content=')[^']*'", lambda m: m[1] + f"{ORIGIN}/manga/past/index.html'", head)
    head = re.sub(r"<meta property=og:image content='[^']*'>", f"<meta property=og:image content='{ORIGIN}/img/brand/x_header.png'>", head)
    hdr = re.search(r"<header class=top>.*?</header>", first, re.S)[0]
    tail = first[first.index("<footer"):]
    body = (f"<body><main style=''>{hdr}<nav class=bc aria-label='パンくず'><a href='../../index.html'>トップ</a> › "
            f"<a href='../index.html'>やまのてマンガ</a> › アーカイブ</nav>"
            f"<p class=pr>PR｜このサイトはアフィリエイト広告（バリューコマース）を利用しています。</p>"
            f"<h1 style='font-size:22px;margin:10px 0'>📦 無料が終わったマンガのアーカイブ</h1>"
            f"<p class=note>1巻無料の期間が終わった作品です（新しく終わった順）。あらすじ・登場人物・読者の声は残してあります。"
            f"いま無料で読める作品は<a href='../theme/free-now.html'>こちら</a>。</p>"
            f"<div class=grid>{''.join(c for c, _, _ in items)}</div>"
            f"<p class=note><a href='../index.html'>マンガトップ</a>　<a href='../theme/free-now.html'>いま無料で読めるマンガ</a>　<a href='../new-releases.html'>新刊カレンダー</a></p>")
    (PAST / "index.html").write_text(head + body + tail, encoding="utf-8")


def add_nav_link():
    """全マンガページのメニュー『Q&A』の後に『アーカイブ』を足す（生成ツールが作り直しても戻す）。"""
    n = 0
    for f in MANGA.rglob("*.html"):
        t = f.read_text(encoding="utf-8")
        if "past/index.html'>アーカイブ" in t:
            continue
        m = re.search(r"<a href='((?:\.\./)*|)faq\.html'>Q&amp;A</a>", t)
        if not m:
            continue
        pre = m.group(1)
        link = f"<a href='{pre}past/index.html'>アーカイブ</a>"
        f.write_text(t.replace(m.group(0), m.group(0) + link, 1), encoding="utf-8")
        n += 1
    return n


def main():
    td = today()
    PAST.mkdir(parents=True, exist_ok=True)
    moved = []
    # 1. 現行ページで期限切れ → past へ移して w/ は転送ページに
    for f in sorted(W.glob("*.html")):
        t = f.read_text(encoding="utf-8")
        dl = deadline_of(t)
        if dl is None or dl >= td:
            continue
        (PAST / f.name).write_text(make_archive_page(t, f.stem, dl), encoding="utf-8")
        f.write_text(redirect_stub(f.stem), encoding="utf-8")
        moved.append(f.stem)
    # 2. 消された作品ページを履歴から復元（期限が過ぎているものだけ）
    restored = []
    for wid, t in deleted_from_history().items():
        if (PAST / f"{wid}.html").exists():
            continue
        dl = deadline_of(t)
        if dl is None or dl >= td:
            continue
        (PAST / f"{wid}.html").write_text(make_archive_page(t, wid, dl), encoding="utf-8")
        restored.append(wid)
    # 3. 一覧
    pages = {p.stem: p.read_text(encoding="utf-8") for p in sorted(PAST.glob("*.html")) if p.name != "index.html"}
    pages = {k: v for k, v in pages.items() if MARK_RE.search(v)}
    if pages:
        build_index(pages)
    # 4. メニュー
    nav = add_nav_link() if pages else 0
    print(f"アーカイブ: 移動{len(moved)} 履歴から復元{len(restored)} 累計{len(pages)}作品 メニュー更新{nav}ページ")


if __name__ == "__main__":
    sys.exit(main())
