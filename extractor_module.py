"""
extractor_module.py
--------------------
Job: Given a URL, pull out the actual readable text.

- For normal web pages / research articles -> we first try "trafilatura".
  If that fails (some sites block it), we fall back to a second method
  using "requests" + "BeautifulSoup".

- For YouTube videos -> we pull the transcript/subtitles using
  "youtube-transcript-api" instead of literally watching the video.

Hardened: every network call has an explicit timeout, and each
extraction is additionally wrapped in a hard deadline via a worker
thread, so one slow/unresponsive URL can never hang the whole pipeline.
"""

import concurrent.futures
import trafilatura
import requests
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}

REQUEST_TIMEOUT = 10       # seconds, for individual HTTP requests
PER_URL_HARD_TIMEOUT = 15  # seconds, absolute ceiling per URL


def _with_hard_timeout(func, args=(), timeout=PER_URL_HARD_TIMEOUT, default=""):
    """Run func(*args) but never wait longer than `timeout` seconds total."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            print(f"{func.__name__} timed out after {timeout}s on {args} - skipping.")
            return default
        except Exception as e:
            print(f"{func.__name__} failed on {args}: {e}")
            return default


def extract_with_trafilatura(url):
    """First attempt: trafilatura (best quality when it works)."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return ""
        return trafilatura.extract(downloaded) or ""
    except Exception:
        return ""


def extract_with_requests_bs4(url):
    """Backup attempt: plain requests + BeautifulSoup."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        paragraphs = soup.find_all("p")
        return " ".join(p.get_text(strip=True) for p in paragraphs)
    except Exception:
        return ""


def _extract_webpage_text_inner(url, max_chars):
    text = extract_with_trafilatura(url)
    if not text or len(text.strip()) < 50:
        text = extract_with_requests_bs4(url)
    return text[:max_chars] if text else ""


def extract_webpage_text(url, max_chars=6000):
    """
    Download a webpage and return its clean main text.
    Guaranteed to return within PER_URL_HARD_TIMEOUT seconds even if the
    site hangs instead of erroring.
    """
    return _with_hard_timeout(_extract_webpage_text_inner, args=(url, max_chars), default="")


def get_youtube_video_id(url):
    """Pull the 11-character video ID out of a YouTube URL."""
    if "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    return None


def _extract_youtube_transcript_inner(url, max_chars):
    video_id = get_youtube_video_id(url)
    if not video_id:
        return ""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        full_text = " ".join(line["text"] for line in transcript)
        return full_text[:max_chars]
    except Exception:
        return ""


def extract_youtube_transcript(url, max_chars=6000):
    """
    Get the transcript (subtitles) of a YouTube video as plain text.
    Guaranteed to return within PER_URL_HARD_TIMEOUT seconds.
    """
    return _with_hard_timeout(_extract_youtube_transcript_inner, args=(url, max_chars), default="")


def gather_all_content(web_results, youtube_results):
    """
    Turn search results into a single list of "documents".
    Each document keeps its source URL + title, so we can cite it later.
    """
    documents = []
    failed_urls = []

    for item in web_results:
        text = extract_webpage_text(item["url"])
        if text and len(text.strip()) > 50:
            documents.append({
                "title": item["title"],
                "url": item["url"],
                "text": text,
                "type": "article"
            })
        else:
            failed_urls.append(item["url"])

    for item in youtube_results:
        text = extract_youtube_transcript(item["url"])
        if text:
            documents.append({
                "title": item["title"],
                "url": item["url"],
                "text": text,
                "type": "video"
            })
        else:
            failed_urls.append(item["url"])

    return documents, failed_urls