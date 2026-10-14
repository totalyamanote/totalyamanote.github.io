"""Yahoo!ショッピング 商品検索API（v3）の薄いクライアント。アフィリエイトはバリューコマース経由。

- アプリケーションID：config.json の yahoo.app_id（クラウドでは環境変数 YAHOO_APP_ID）
- バリューコマース：yahoo.vc_sid / yahoo.vc_pid（リンクに出る番号なので公開してよい）
- 実質価格 = 価格 − 付与ポイント（通常分＋LINEヤフーのアカウント連携でもらえる分。PayPayカード等の条件付き上乗せは含めない）
"""
import json
import os
import time
import urllib.parse
import urllib.request

API = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch"


class Yahoo:
    def __init__(self, cfg):
        y = (cfg or {}).get("yahoo", {})
        self.appid = os.environ.get("YAHOO_APP_ID") or y.get("app_id", "")
        self.sid, self.pid = str(y.get("vc_sid", "")), str(y.get("vc_pid", ""))
        self._last = 0.0

    @property
    def ready(self):
        return bool(self.appid and self.sid and self.pid)

    def search(self, query, price_from=None, price_to=None, results=20, sort="-score"):
        if not self.ready:
            return []
        wait = 1.0 - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        vc = f"https://ck.jp.ap.valuecommerce.com/servlet/referral?sid={self.sid}&pid={self.pid}&vc_url="
        q = {"appid": self.appid, "query": query, "results": results, "sort": sort, "in_stock": "true",
             "affiliate_type": "vc", "affiliate_id": vc}
        if price_from:
            q["price_from"] = price_from
        if price_to:
            q["price_to"] = price_to
        req = urllib.request.Request(API + "?" + urllib.parse.urlencode(q), headers={"User-Agent": "yamanote/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            self._last = time.time()
            data = json.load(r)
        out = []
        for h in data.get("hits", []):
            # アフィリエイトリンクにならない商品（LOHACO等）は載せない
            if not str(h.get("url", "")).startswith("https://ck.jp.ap.valuecommerce.com/"):
                continue
            price = int(h.get("price") or 0)
            po = h.get("point") or {}
            # 誰でももらえる分（amount・bonusAmount）＋ LINEヤフーのアカウント連携でもらえる分（lyLimitedBonusAmount）
            pt = int(po.get("amount") or 0) + int(po.get("bonusAmount") or 0) + int(po.get("lyLimitedBonusAmount") or 0)
            rv = h.get("review") or {}
            out.append({
                "item_code": "yahoo:" + str(h.get("code", "")), "name": h.get("name", ""), "price": price,
                "point": pt, "effective": price - pt, "url": h.get("url", ""),
                "image": ((h.get("image") or {}).get("medium") or "").replace("/i/g/", "/i/l/"),
                "review_count": int(rv.get("count") or 0), "review_avg": float(rv.get("rate") or 0),
                "shop": (h.get("seller") or {}).get("name", ""),
            })
        return out
