import os, sys, urllib.error
import threads
try:
    print("✅ 引用できます（公開していません）container", threads.check_quote(os.environ["CODE"], os.environ["THREADS_TOKEN"]))
except urllib.error.HTTPError as e:
    print("❌", e.code, e.read().decode()[:300]); sys.exit(1)
