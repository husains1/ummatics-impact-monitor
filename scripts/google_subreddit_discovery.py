import requests
from bs4 import BeautifulSoup
import re

def google_search(query, num_results=10):
    """
    Perform a Google search and return the resulting links.

    Args:
        query (str): The search query.
        num_results (int): Number of results to fetch.

    Returns:
        list: A list of URLs from the search results.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    search_url = f"https://www.google.com/search?q={query}&num={num_results}"
    response = requests.get(search_url, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Google search failed with status code {response.status_code}")

    soup = BeautifulSoup(response.text, 'html.parser')
    links = []

    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        if '/url?q=' in href:
            match = re.search(r'/url\?q=(.*?)&', href)
            if match:
                links.append(match.group(1))

    return links

def discover_subreddits():
    """
    Discover new subreddits using Google search.

    Returns:
        set: A set of discovered subreddit names.
    """
    query = 'site:reddit.com "ummatics" OR "ummatic"'
    print(f"Performing Google search with query: {query}")

    try:
        links = google_search(query)
        subreddits = set()

        for link in links:
            match = re.search(r'reddit\.com/r/([a-zA-Z0-9_]+)/', link)
            if match:
                subreddit = match.group(1).lower()
                if subreddit not in ['all', 'popular', 'announcements', 'reddit']:
                    subreddits.add(subreddit)

        print(f"Discovered subreddits: {subreddits}")
        return subreddits

    except Exception as e:
        print(f"Error during subreddit discovery: {e}")
        return set()

if __name__ == "__main__":
    discovered_subreddits = discover_subreddits()
    if discovered_subreddits:
        print("New subreddits discovered:")
        for subreddit in discovered_subreddits:
            print(f"- r/{subreddit}")
    else:
        print("No new subreddits discovered.")