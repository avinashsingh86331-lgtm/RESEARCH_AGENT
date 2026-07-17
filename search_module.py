"""
search_module.py
-----------------
Job: Search the web for a topic and return a list of links.

We use the Tavily API (https://tavily.com) here instead of scraping
DuckDuckGo. Tavily is built specifically for AI research agents, has a
real API quota (1,000 free searches/month, no credit card needed) instead
of an anti-bot wall, and does not get randomly rate-limited the way
DDG scraping does.

Get a free key at: https://app.tavily.com and put it in a .env file
in the project root (see README.md for the exact format) - that way
you don't have to re-type it into the terminal every session.
"""

import os
import time
import concurrent.futures
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()  # reads GROQ_API_KEY / TAVILY_API_KEY from a .env file, if present

client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))

HARD_TIMEOUT_SECONDS = 20  # never wait longer than this for a single search call


def _tavily_search(query, max_results):
    """One raw call to Tavily. Runs inside a worker thread so the caller
    can enforce a hard timeout around it, same as any network call."""
    response = client.search(
        query=query,
        max_results=max_results,
        search_depth="basic"
    )
    return response.get("results", [])


def _search_with_retries(query, max_results, max_retries=3):
    """Retries with backoff, plus a hard timeout so a stalled connection
    can never hang the app indefinitely."""
    last_error = None

    for attempt in range(max_retries):
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_tavily_search, query, max_results)
            try:
                results = future.result(timeout=HARD_TIMEOUT_SECONDS)
                if results:
                    return results, None
                last_error = None  # genuinely no results, not an error
                break
            except concurrent.futures.TimeoutError:
                last_error = f"Timed out after {HARD_TIMEOUT_SECONDS}s with no response."
                print(f"Tavily search timed out (attempt {attempt + 1}/{max_retries}): {last_error}")
            except Exception as e:
                last_error = str(e)
                print(f"Tavily search failed (attempt {attempt + 1}/{max_retries}): {e}")

        wait_time = 3 * (attempt + 1)
        time.sleep(wait_time)

    return [], last_error


def search_web(topic, max_results=6, max_retries=3):
    """
    Search the web for a topic.
    Output: [{"title": ..., "url": ..., "snippet": ...}, ...] or [] on failure.
    """
    raw_results, error = _search_with_retries(topic, max_results, max_retries)

    if not raw_results:
        if error:
            print(f"Web search failed after all retries. Last error: {error}")
            if "401" in error or "Unauthorized" in error or "api_key" in error.lower():
                print("This looks like an invalid/missing TAVILY_API_KEY. "
                      "Check it's set correctly in this terminal session.")
        else:
            print("Web search returned no results for this topic.")
        return []

    return [
        {
            "title": r.get("title", "Untitled"),
            "url": r.get("url", ""),
            "snippet": r.get("content", "")
        }
        for r in raw_results
    ]


def search_youtube(topic, max_results=3, max_retries=3):
    """
    Search for YouTube videos on a topic. Tavily doesn't have a dedicated
    video search mode, so we bias a normal web search toward YouTube and
    filter the results down to actual YouTube URLs.
    Output: [{"title": ..., "url": ...}, ...] or [] if none found.
    """
    query = f"{topic} site:youtube.com"
    raw_results, error = _search_with_retries(query, max_results * 3, max_retries)

    if not raw_results:
        if error:
            print(f"YouTube search failed after all retries. Last error: {error}")
        else:
            print("YouTube search returned no video results for this topic.")
        return []

    results = []
    for r in raw_results:
        url = r.get("url", "")
        if "youtube.com" in url or "youtu.be" in url:
            results.append({"title": r.get("title", "Untitled"), "url": url})
        if len(results) >= max_results:
            break
    return results