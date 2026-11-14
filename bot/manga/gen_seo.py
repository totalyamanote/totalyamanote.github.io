"""検索エンジン向けの土台を毎日作る（gen_pages / gen_articles / gen_manga の後に実行）。

- site/sitemap.xml … 公開ページ一覧（bot/ と検証用ファイルは除く）。更新日つき。
- site/robots.txt  … 全許可＋sitemap の場所。
- IndexNow（Bing・Yandex 等）に、前回から変わったページだけ通知する。Google は Search Console にサイトマップを登録して拾ってもらう。
- 使い方：python3 gen_seo.py [--no-ping]
"""
import argparse
import datetime
import hashlib
import json
import re
import secrets
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE / "site"
BASE = "https://totalyamanote.github.io/"
STATE = HERE / "data" / "seo_state.json"


def pages():
    for f in sorted(SITE.rglob("*.html")):
        rel = f.relative_to(SITE).as_posix()
        if rel.startswith("bot/") or rel.startswith("google") or "/img/" in rel:
            continue
        if "noindex" in f.read_text(encoding="utf-8")[:6000]:
            continue
        yield rel, f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-ping", action="store_true")
    a = ap.parse_args()
    st = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    key = st.get("indexnow_key") or secrets.token_hex(16)
    st["indexnow_key"] = key
    (SITE / f"{key}.txt").write_text(key, encoding="utf-8")
    hashes = st.get("hashes", {})
    urls, changed = [], []
    for rel, f in pages():
        loc = BASE + ("" if rel == "index.html" else rel)
        lastmod = datetime.date.fromtimestamp(f.stat().st_mtime).isoformat()
        pri = "1.0" if rel == "index.html" else ("0.8" if rel.startswith(("articles/", "manga/index", "sale")) else "0.6")
        urls.append(f"<url><loc>{loc}</loc><lastmod>{lastmod}</lastmod><priority>{pri}</priority></url>")
        h = hashlib.md5(f.read_bytes()).hexdigest()
        if hashes.get(rel) != h:
            changed.append(loc)
            hashes[rel] = h
    (SITE / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>\n",
        encoding="utf-8")
    ai = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot", "Claude-User", "Google-Extended", "Googlebot", "Bingbot",
          "PerplexityBot", "Perplexity-User", "Applebot", "Applebot-Extended", "xAI-Bot", "GrokBot"]
    rb = "".join(f"User-agent: {a}\nAllow: /\nDisallow: /bot/\n\n" for a in ai)
    (SITE / "robots.txt").write_text(f"# 検索エンジンとAI（ChatGPT・Claude・Gemini・Copilot・Grok・Perplexity等）の読み込みを許可\n{rb}User-agent: *\nAllow: /\nDisallow: /bot/\n\nSitemap: {BASE}sitemap.xml\n", encoding="utf-8")
    write_llms()
    st["hashes"] = hashes
    msg = f"sitemap {len(urls)} URL / 変更 {len(changed)}"
    if changed and not a.no_ping:
        body = json.dumps({"host": "totalyamanote.github.io", "key": key, "keyLocation": f"{BASE}{key}.txt", "urlList": changed[:10000]}).encode()
        try:
            req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, headers={"Content-Type": "application/json; charset=utf-8"})
            with urllib.request.urlopen(req, timeout=30) as r:
                msg += f" / IndexNow {r.status}"
            st["last_ping"] = datetime.datetime.now().isoformat(timespec="seconds")
        except Exception as e:
            msg += f" / IndexNow 失敗 {e}"
            for u in changed:  # 次回また送る
                hashes.pop(u.replace(BASE, "") or "index.html", None)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    print(msg)



def write_llms():
    """AI向けのサイト案内（/llms.txt）：何のサイトか・主要ページ・情報の出どころを短く。"""
    import html as _h
    lines = ["# やまのて", "",
             "> 楽天市場・Yahoo!ショッピング・Amazonの「価格−ポイント＝実質価格」を毎朝比較するサイトと、マンガ情報サイト「やまのてマンガ」（無料で読める期限・新刊の発売日・電子書籍ストア比較）。運営：やまのて編集部。", "",
             "情報の出どころ：各ストアの公開データ（楽天ウェブサービス・Yahoo!ショッピングAPI・楽天ブックス）と各社の公式ページ。確認日を各ページに記載。使っていない商品の体験談は書かない。", "",
             "## 主なページ"]
    def title(f):
        t = f.read_text(encoding="utf-8")
        m = re.search(r"<title>(.*?)</title>", t, re.S)
        return _h.unescape(m.group(1)).strip() if m else f.name
    for f in sorted(SITE.rglob("*.html")):
        rel = f.relative_to(SITE).as_posix()
        t = f.read_text(encoding="utf-8")
        if rel.startswith(("bot/", "google")) or "noindex" in t[:6000] or "<!--redirect-->" in t or rel == "404.html":
            continue
        lines.append(f"- [{title(f)}]({BASE}{'' if rel == 'index.html' else rel})")
    lines += ["", "## 方針", f"- 比較のしかた：{BASE}compare-method.html", f"- 運営者情報：{BASE}about.html"]
    (SITE / "llms.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
