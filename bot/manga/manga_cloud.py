"""マンガサイトの毎朝の更新（クラウド用）。Macが寝ていても、GitHub Actions で動く。

やること：新刊カレンダー・無料の期限・ストア比較・作品ページ・トップのマンガの段・サイトマップを作り直す。
元の生成ツールは bot/manga/（手元の ~/rakuten-affiliate と同じもの）、データは bot/manga/data/。
★記事（articles/）とトップの見た目（bot/hub.py の管轄）は書き換えない。commit するのは manga/・index.html の hubm の段・sitemap 等だけ。
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(os.environ.get("GITHUB_WORKSPACE") or Path(__file__).resolve().parents[2])
SRC = REPO / "bot" / "manga"
ROOT = Path(os.environ.get("RUNNER_TEMP") or "/tmp") / "manga_root"


def setup():
    if ROOT.exists():
        shutil.rmtree(ROOT)
    (ROOT / "data").mkdir(parents=True)
    for f in SRC.glob("*.py"):
        if f.name != "manga_cloud.py":
            shutil.copy(f, ROOT / f.name)
    for f in (REPO / "bot").glob("rakuten.py"):
        shutil.copy(f, ROOT / f.name)
    for f in (REPO / "bot").glob("yahoo.py"):
        shutil.copy(f, ROOT / f.name)
    for f in (SRC / "data").glob("*.json"):
        shutil.copy(f, ROOT / "data" / f.name)
    cfg = json.loads((REPO / "bot" / "config.public.json").read_text(encoding="utf-8"))
    cfg["application_id"] = os.environ["RAKUTEN_APP_ID"]
    cfg["access_key"] = os.environ["RAKUTEN_ACCESS_KEY"]
    cfg["affiliate_id"] = os.environ["RAKUTEN_AFFILIATE_ID"]
    shutil.copy(REPO / "bot" / "config.public.json", ROOT / "config.public.json")   # rakuten.load_config が使う
    (ROOT / "config.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    (ROOT / "site").symlink_to(REPO, target_is_directory=True)


def run(*args):
    r = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True)
    print((r.stdout + r.stderr).strip()[-1200:])
    return r.returncode


def update_hubm():
    """トップの「マンガの段」だけ差し替える（見た目の固定は bot/hub.py の管轄なので、この段以外は触らない）。"""
    sys.path.insert(0, str(ROOT))
    import gen_hub  # noqa
    p = REPO / "index.html"
    t = p.read_text(encoding="utf-8")
    new = gen_hub.hub_manga()
    if "<!--hubm-->" in t:
        t2 = re.sub(r"<!--hubm-->.*?<!--/hubm-->", lambda m: new, t, flags=re.S)
    else:
        i = t.find("<!--ftr-->")
        i = i if i >= 0 else t.rfind("</main>")
        t2 = t[:i] + new + t[i:]
    if t2 != t:
        p.write_text(t2, encoding="utf-8")
        print("index.html のマンガの段を更新")


def main():
    setup()
    if run("gen_manga.py") != 0:
        print("gen_manga 失敗"); return 1
    # 作品ページ等の仕上げ（パンくず・共通ヘッダー/フッター・構造化データ）。gen_hub.run_all は記事・トップにも手を入れるので、
    # トップ（index.html）は実行前の内容に戻し、記事は commit しない（workflow が manga・index.html 等だけ add する）。
    idx = (REPO / "index.html").read_text(encoding="utf-8")
    run("-c", "import gen_hub; gen_hub.run_all()")
    (REPO / "index.html").write_text(idx, encoding="utf-8")
    update_hubm()
    run("gen_seo.py")
    # 生成したデータの持ち帰り（IndexNowの状態など）
    for n in ("seo_state.json", "manga_works.json", "manga_stock.json"):   # ストックから公開した作品も持ち帰る
        s = ROOT / "data" / n
        if s.exists():
            shutil.copy(s, SRC / "data" / n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
