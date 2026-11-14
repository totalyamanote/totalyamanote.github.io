"""SNS投稿の中の「自分のサイト」のリンクに目印（UTM）を付ける（2026-11-14 坂田さん承認）。

GA4で「どのSNSの・どの投稿から来た人が、ボタンを押したか」を分けて見るため。
- utm_source  = x / threads / bluesky
- utm_medium  = social
- utm_campaign= 投稿の予定時刻（例 20261115_1340）＋投稿の型（あれば）
自分のサイト（totalyamanote.github.io・独自ドメイン）のURLだけに付ける。楽天・Amazon等の広告リンクには付けない（規約・計測を壊さない）。
すでに utm_ が付いているURLはそのまま。ページ内の正規URL（canonical）があるので、検索の評価には影響しない。
"""
import re

SITES = ("totalyamanote.github.io", "totalyamanote.jp")
URL = re.compile(r"https?://(?:www\.)?(?:" + "|".join(re.escape(s) for s in SITES) + r")[^\s　）)」』】]*")


def tag(text, source, at="", kind=""):
    camp = re.sub(r"[^0-9A-Za-z_]", "", re.sub(r"[-: ]", lambda m: "_" if m.group(0) == " " else "", at or ""))
    if kind:
        camp = (camp + "_" if camp else "") + re.sub(r"[^0-9A-Za-z_]", "", kind)

    def add(m):
        u = m.group(0)
        if "utm_" in u:
            return u
        frag = ""
        if "#" in u:
            u, frag = u.split("#", 1)
            frag = "#" + frag
        q = f"utm_source={source}&utm_medium=social" + (f"&utm_campaign={camp}" if camp else "")
        return u + ("&" if "?" in u else "?") + q + frag

    return URL.sub(add, text or "")


if __name__ == "__main__":
    print(tag("見てね https://totalyamanote.github.io/manga/w/kB0BKSR5555.html と https://hb.afl.rakuten.co.jp/x", "x", "2026-11-15 13:40", "manga"))
