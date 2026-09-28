"""引用できるか確かめる（日経の最新投稿を取って、コンテナを作るだけ。公開しない）。"""
import json, os, sys, urllib.error, urllib.parse, urllib.request
import threads
tok = os.environ["THREADS_TOKEN"]


def get(path, **params):
    params["access_token"] = tok
    try:
        with urllib.request.urlopen(f"{threads.API}/{path}?{urllib.parse.urlencode(params)}", timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"ERROR": e.code, "body": e.read().decode()[:300]}


print("me:", get("me", fields="id,username"))
print("lookup:", str(get("profile_lookup", username="nikkei"))[:300])
r = get("profile_posts", username="nikkei", fields="id,text,permalink,timestamp", limit=3)
print("posts:", str(r)[:600])
if r.get("data"):
    try:
        print("✅ 引用できます（公開していません） container", threads.check_quote_id(r["data"][0]["id"], tok))
    except urllib.error.HTTPError as e:
        print("❌ quote", e.code, e.read().decode()[:300]); sys.exit(1)
