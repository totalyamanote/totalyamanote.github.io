"""GitHub Actions から呼ばれ、X・Threads と同じ投稿を Bluesky にも出す（Macの電源に関係なく動く）。

- キュー：OUT_DIR/threads_queue.json（Xに予約した投稿の写し。x_to_threads.py が追加する）。印は "bsky"
  （2026-09-28 ユーザー指定「Bluesky も X・Threads に投稿内容を合わせて」。以前の日替わりキュー queue_*.json は使わない）
- 1回に1件。時刻を6時間以上過ぎたものは出さずに skipped。
- 商品は画像付き。ニュースは記事URLのリンクカード（画像つき）で出す。
- 認証：環境変数 BSKY_HANDLE / BSKY_APP_PASSWORD（GitHub Secrets）
"""
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import bsky
from claim import claim

OUT = Path(os.environ.get("OUT_DIR") or Path(__file__).resolve().parent / "out").resolve()


def main():
    qpath = OUT / "threads_queue.json"
    if not qpath.exists():
        print("キューがありません"); return 0
    queue = json.loads(qpath.read_text(encoding="utf-8"))
    now = datetime.now()
    due = [q for q in queue if not q.get("bsky") and datetime.strptime(q["at"], "%Y-%m-%d %H:%M") <= now]
    if not due:
        print("投稿する枠はありません"); return 0
    for old in due[:-1]:
        old["bsky"] = "skipped"
    q = due[-1]
    if datetime.strptime(q["at"], "%Y-%m-%d %H:%M") < now - timedelta(hours=6):
        q["bsky"] = "skipped"
        qpath.write_text(json.dumps(queue, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"時刻を6時間以上過ぎたので出さない {q['at']}"); return 0
    q["bsky"] = "posting"
    qpath.write_text(json.dumps(queue, ensure_ascii=False, indent=1), encoding="utf-8")
    if not claim(qpath, f"Bluesky 投稿中 {q['at']}"):
        print("ほかの実行が先に投稿中なので、この実行は投稿しない"); return 0
    code = 0
    try:
        q["bsky"] = bsky.post(q["text"], os.environ["BSKY_HANDLE"], os.environ["BSKY_APP_PASSWORD"],
                              q.get("image"), q.get("alt", ""))
        print(f"✅ Bluesky {q['at']} {q['bsky']}")
    except Exception as e:
        q["bsky"] = "failed"
        print(f"❌ Bluesky投稿失敗 {q['at']}: {e}")
        code = 1
    qpath.write_text(json.dumps(queue, ensure_ascii=False, indent=1), encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(main())
