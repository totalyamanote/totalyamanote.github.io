"""GitHub Actions から30分おきに呼ばれ、Xに予約したのと同じ投稿を Threads に出す（Macの電源に関係なく動く）。

- キュー：OUT_DIR/threads_queue.json（Macの x_to_threads.py が、Xに予約するたびに追加して push する）
  [{"at": "YYYY-MM-DD HH:MM", "text": "...", "threads": 投稿ID or "skipped" or "failed"}]
- 1回に1件だけ。時刻を3時間以上過ぎたものは出さずに skipped（まとめて連投しない）
- 認証：GitHub Secrets の THREADS_TOKEN。未設定ならスキップ
"""
import json
import re
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import threads
from claim import claim

OUT = Path(os.environ.get("OUT_DIR") or Path(__file__).resolve().parent / "out").resolve()


THREADS_AMAZON_REGISTERED = True   # 2026-11-13 Amazonのサイト一覧にThreadsを登録済み。未登録に戻ったら False


def strip_amazon(text):
    if THREADS_AMAZON_REGISTERED:
        return text
    """Amazonアソシエイトは登録したサイト・アカウント（現状はXと shogo45.github.io のみ）にしかリンクを載せられない。
    Threads には Amazon のリンク行と #Amazon を載せない（楽天の部分だけ出す）。2026-11-13 管理画面で確認。"""
    lines = [l for l in text.split("\n") if not re.match(r"\s*Amazon\s*[→>]", l) and "amazon.co.jp" not in l and "amzn.to" not in l]
    return "\n".join(lines).replace(" #Amazon", "").replace("#Amazon ", "")


def main():
    if not os.environ.get("THREADS_TOKEN"):
        print("THREADS_TOKEN が未設定なのでスキップ"); return 0
    try:
        print(f"Threads認証OK @{threads.whoami(os.environ['THREADS_TOKEN'])}")
    except Exception as e:
        print(f"❌ Threadsのトークンが無効です（再発行が必要）: {e}"); return 1
    qpath = OUT / "threads_queue.json"
    if not qpath.exists():
        print("Threadsのキューがありません"); return 0
    queue = json.loads(qpath.read_text(encoding="utf-8"))
    now = datetime.now()
    due = [q for q in queue if not q.get("threads") and datetime.strptime(q["at"], "%Y-%m-%d %H:%M") <= now]
    # Threadsは「A8」「メルカリ」「ブックライブ」の3軸だけ（楽天は出さない。2026-11-14 ユーザー指示）（2026-11-14 ユーザー指示）。それ以外（ニュース・Yahoo!・メルカリ・BookLive・リンクシェア等）は出さない
    AXIS = re.compile(r"px\.a8\.net|mercari\.com|mercari\.jp|\bmercari\b|booklive|totalyamanote\.github\.io|nikkei\.com|news\.yahoo\.co\.jp", re.I)  # 2026-11-14: サイトへの誘導・ニュースも出す
    skipped_axis = [q for q in due if not AXIS.search(q["text"]) and not q.get("engage")]   # engage=目を引く投稿（リンクなし）
    for q in skipped_axis:
        q["threads"] = "skipped"
    if skipped_axis:
        qpath.write_text(json.dumps(queue, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"A8・楽天以外の {len(skipped_axis)} 件はThreadsに出さない")
    due = [q for q in due if q.get("threads") != "skipped"]
    if not due:
        print("投稿する枠はありません"); return 0
    stale = now - timedelta(hours=6)   # 定時実行が遅れても、6時間以内なら出す
    for q in due[:-1]:
        q["threads"] = "skipped"
    q = due[-1]
    code = 0
    if datetime.strptime(q["at"], "%Y-%m-%d %H:%M") < stale:
        q["threads"] = "skipped"
        print(f"時刻を6時間以上過ぎたので出さない {q['at']}")
    else:
        q["threads"] = "posting"
        qpath.write_text(json.dumps(queue, ensure_ascii=False, indent=1), encoding="utf-8")
        if not claim(qpath, f"Threads 投稿中 {q['at']}"):
            print("ほかの実行が先に投稿中なので、この実行は投稿しない"); return 0
        try:
            q["threads"] = threads.post(strip_amazon(q["text"]), os.environ["THREADS_TOKEN"], q.get("image"), q.get("quote"))
            print(f"✅ Threads {q['at']} {q['threads']}")
        except Exception as e:
            q["threads"] = "failed"
            print(f"❌ Threads投稿失敗 {q['at']}: {e}")
            code = 1
    qpath.write_text(json.dumps(queue, ensure_ascii=False, indent=1), encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(main())
