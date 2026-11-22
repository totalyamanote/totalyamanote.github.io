"""サイトの各ページの Amazon リンクに、ページごとのトラッキングIDを付ける（2026-11-22 坂田さん「投稿ごとにトラッキングIDを分けて」）。

目的：Amazonアソシエイトのレポートで「どのページのボタンから売れたか」が分かるようにする。
- 既定のID（shogo450e-22）は SNS の直リンクなど「サイト以外」に残す。サイトのページはこの表のIDに置き換える。
- IDは Amazon アソシエイト・セントラル「トラッキングIDの管理」で作成済み（ymnote-*-22 の16個）。
- 何度走らせても同じ結果になる（すでに ymnote-* のものも表どおりに直す）。クラウドの生成（run_daily / manga / add_malls）のあとに走らせる。
- 表にないページは変えない。IDを増やすときは、アソシエイト・セントラルで作ってから、この表に足す。
使い方：python3 bot/amazon_tags.py [サイトのフォルダ。省略は bot の1つ上]
"""
import re
import sys
from pathlib import Path

SITE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent

BY_PAGE = {
    "index.html": "ymnote-top-22",
    "sale.html": "ymnote-sale-22",
    "articles/black-friday-2026.html": "ymnote-bf-22",
    "articles/black-friday-ec-compare-2026.html": "ymnote-bfec-22",
    "articles/dishwasher-detergent.html": "ymnote-dish-22",
    "articles/toilet-cleaning.html": "ymnote-toilet-22",
    "articles/laundry-auto-dosing.html": "ymnote-laundry-22",
    "articles/wearable-blanket.html": "ymnote-blanket-22",
    "articles/cleansing-oil.html": "ymnote-cleanse-22",
    "articles/electric-shaver.html": "ymnote-shaver-22",
    "articles/water-filter-cartridge.html": "ymnote-filter-22",
    "articles/pet-sheet.html": "ymnote-petsheet-22",
    "articles/washer-stand.html": "ymnote-washer-22",
    "articles/protein.html": "ymnote-protein-22",
    "articles/toothpaste.html": "ymnote-toothpaste-22",
    "articles/hair-oil.html": "ymnote-hairoil-22",
    "articles/hair-dryer.html": "ymnote-dryer-22",
    "articles/humidifier.html": "ymnote-humid-22",
    "manga/new-releases.html": "ymnote-newrel-22",
    "manga/store-compare.html": "ymnote-store-22",
}
MANGA_DEFAULT = "ymnote-manga-22"  # manga/ の上の表にないページ（トップ・作品ページ・まとめ）

LINK = re.compile(r"(amazon\.co\.jp[^'\"\s<>]*?tag=)[A-Za-z0-9\-]+-22")


def tag_for(rel):
    if rel in BY_PAGE:
        return BY_PAGE[rel]
    if rel.startswith("manga/"):
        return MANGA_DEFAULT
    return None


def main():
    changed = links = 0
    for f in SITE.rglob("*.html"):
        rel = f.relative_to(SITE).as_posix()
        if rel.startswith(("bot/", ".github/", "node_modules/")):
            continue
        tag = tag_for(rel)
        if not tag:
            continue
        t = f.read_text(encoding="utf-8", errors="ignore")
        if "amazon.co.jp" not in t:
            continue
        n = len(LINK.findall(t))
        u = LINK.sub(lambda m: m.group(1) + tag, t)
        if u != t:
            f.write_text(u, encoding="utf-8")
            changed += 1
        links += n
    print(f"Amazonトラッキングを付けたページ {changed} 枚（リンク {links} 本）")


if __name__ == "__main__":
    main()
