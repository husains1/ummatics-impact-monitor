#!/usr/bin/env python3
import time
import logging
logging.basicConfig(level=logging.INFO)

from ingestion import ingest_twitter

print("=" * 60)
print("TWITTER MAXTWEETS FIX TEST")
print("=" * 60)
print()

start = time.time()
count = ingest_twitter(max_tweets=50)
elapsed = time.time() - start

print()
print("=" * 60)
print("RESULTS:")
print(f"  Duration: {elapsed:.1f}s")
print(f"  Tweets returned: {count}")
print(f"  Expected: <=40 tweets (2x buffer of 20/query)")
print(f"  Status: {'PASS ✓' if count <= 40 else 'FAIL ✗'}")
print("=" * 60)
