#!/usr/bin/env python3
import requests
import json

# Simulate what the browser does
session = requests.Session()

# Step 1: Authenticate
auth_response = session.post('http://3.226.110.16:3000/api/auth', json={'password': 'abc1234'})
print(f"Auth: {auth_response.status_code}")
auth_data = auth_response.json()
token = auth_data.get('token')

# Step 2: Fetch social data with token (like the browser does)
headers = {'Authorization': f'Bearer {token}'}
social_response = session.get('http://3.226.110.16:3000/api/social?historic=1', headers=headers)
print(f"Social API: {social_response.status_code}, Size: {len(social_response.content)} bytes")

social_data = social_response.json()
recent_mentions = social_data.get('recent_mentions', [])
print(f"Total recent_mentions in response: {len(recent_mentions)}")

twitter_mentions = [m for m in recent_mentions if m.get('platform') == 'Twitter']
print(f"Twitter mentions after filtering: {len(twitter_mentions)}")

# Check if there's any truncation
if len(twitter_mentions) == 100:
    print("\n⚠️  WARNING: Exactly 100 Twitter mentions - possible limit!")
    print(f"First posted_at: {twitter_mentions[0].get('posted_at')}")
    print(f"Last posted_at: {twitter_mentions[-1].get('posted_at')}")
elif len(twitter_mentions) == 3941:
    print("\n✅ All 3,941 Twitter mentions present!")
    print(f"Date range: {twitter_mentions[-1].get('posted_at')} to {twitter_mentions[0].get('posted_at')}")
else:
    print(f"\n❓ Unexpected count: {len(twitter_mentions)}")
