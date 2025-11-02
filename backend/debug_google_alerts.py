#!/usr/bin/env python3
"""
Debug script for Google Alerts RSS feed ingestion
Run this inside the API container to diagnose issues
"""

import os
import feedparser
from datetime import datetime

# Get RSS URL from environment
RSS_URL = os.getenv('GOOGLE_ALERTS_RSS_URL', '')

print("=" * 60)
print("Google Alerts RSS Feed Debug Script")
print("=" * 60)
print()

# Step 1: Check if URL is configured
print("Step 1: Checking configuration...")
if not RSS_URL:
    print("❌ ERROR: GOOGLE_ALERTS_RSS_URL is not set in environment")
    print("   Please check your .env file")
    exit(1)
else:
    print(f"✅ RSS URL is configured")
    print(f"   URL: {RSS_URL[:50]}...")
print()

# Step 2: Try to fetch the feed
print("Step 2: Fetching RSS feed...")
try:
    feed = feedparser.parse(RSS_URL)
    print(f"✅ Feed fetched successfully")
except Exception as e:
    print(f"❌ ERROR fetching feed: {e}")
    exit(1)
print()

# Step 3: Check feed status
print("Step 3: Analyzing feed response...")
if hasattr(feed, 'status'):
    print(f"   HTTP Status: {feed.status}")
    if feed.status != 200:
        print(f"❌ ERROR: Bad HTTP status code")
        exit(1)

if hasattr(feed, 'bozo') and feed.bozo:
    print(f"⚠️  WARNING: Feed has parsing issues")
    if hasattr(feed, 'bozo_exception'):
        print(f"   Exception: {feed.bozo_exception}")
print()

# Step 4: Check entries
print("Step 4: Checking entries...")
entry_count = len(feed.entries)
print(f"   Found {entry_count} entries in feed")

if entry_count == 0:
    print("⚠️  WARNING: No entries found in RSS feed")
    print("   This could mean:")
    print("   1. No alerts have been triggered yet")
    print("   2. The RSS feed is empty")
    print("   3. Your search terms haven't matched anything recently")
else:
    print(f"✅ Found {entry_count} entries")
print()

# Step 5: Display sample entries
if entry_count > 0:
    print("Step 5: Sample entries...")
    for i, entry in enumerate(feed.entries[:3]):
        print(f"\n   Entry {i+1}:")
        print(f"   Title: {entry.get('title', 'N/A')}")
        print(f"   Link: {entry.get('link', 'N/A')}")
        print(f"   Source: {entry.get('source', {}).get('title', 'Unknown')}")
        
        if hasattr(entry, 'published_parsed'):
            pub_date = datetime(*entry.published_parsed[:6])
            print(f"   Published: {pub_date}")
        
        snippet = entry.get('summary', '')[:100]
        print(f"   Snippet: {snippet}...")
    print()

# Step 6: Test database connection
print("Step 6: Testing database connection...")
try:
    import psycopg2
    
    DB_CONFIG = {
        'host': os.getenv('DB_HOST', 'db'),
        'port': os.getenv('DB_PORT', '5432'),
        'database': os.getenv('DB_NAME', 'ummatics_monitor'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'postgres')
    }
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Check if table exists
    cur.execute("SELECT COUNT(*) FROM news_mentions")
    count = cur.fetchone()[0]
    
    print(f"✅ Database connected")
    print(f"   Current records in news_mentions: {count}")
    
    # Check week dates
    cur.execute("""
        SELECT week_start_date, COUNT(*) 
        FROM news_mentions 
        GROUP BY week_start_date 
        ORDER BY week_start_date DESC 
        LIMIT 5
    """)
    results = cur.fetchall()
    
    if results:
        print(f"   Recent weeks in database:")
        for week, count in results:
            print(f"     - Week of {week}: {count} mentions")
    else:
        print(f"   ⚠️  No data in database yet")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"❌ ERROR connecting to database: {e}")
print()

# Final summary
print("=" * 60)
print("Summary:")
print("=" * 60)
if entry_count > 0:
    print("✅ RSS feed is working and has data")
    print("   Run the ingestion to import this data:")
    print("   docker-compose exec api python ingestion.py")
else:
    print("⚠️  RSS feed is accessible but has no entries")
    print("   Wait for Google Alerts to trigger, or:")
    print("   1. Check your alert settings at google.com/alerts")
    print("   2. Make sure your search terms match content")
    print("   3. Try a broader search term")
print()

