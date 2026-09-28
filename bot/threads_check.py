"""引用できるか確かめる（日経の最新投稿を1件取って、コンテナを作るだけ。公開しない）。"""
import os, sys, urllib.error
import threads
tok = os.environ["THREADS_TOKEN"]
try:
    posts = threads.nikkei_posts(tok, limit=5)
    for p in posts:
        print(p.get("timestamp"), p.get("id"), (p.get("text") or "").replace("\n", " ")[:40])
    print("✅ 引用できます（公開していません） container", threads.check_quote_id(posts[0]["id"], tok))
except urllib.error.HTTPError as e:
    print("❌", e.code, e.read().decode()[:300]); sys.exit(1)
