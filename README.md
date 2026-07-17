# Autonomous AI Research Agent (Simple Version)

This does what the fancy version does — search, read, take notes, cite
sources, and produce a PPT + PDF — but using only free/light tools, one
Python app, and no database server.

## How it maps to the "official" idea

| Fancy idea            | What we actually use                      | Why |
|------------------------|--------------------------------------------|-----|
| GPT                    | Groq API (`ai_module.py`)                  | One fast API call does summarizing + writing |
| Vector Database         | TF-IDF ranking in RAM (`rag_module.py`)     | scikit-learn, no server, no setup, no cost |
| Search Agents           | Tavily search API (`search_module.py`)     | Built for AI agents, real quota, no rate-limit walls |
| "Reads papers"          | `trafilatura` extracts clean article text  | Works on most articles/blogs/papers |
| "Watches YouTube"       | Pulls the video's transcript/subtitles      | Same information, no video/audio AI needed |
| Frontend + Backend      | One Streamlit app (`app.py`)                | Streamlit is a webpage AND the Python logic, together |

## Files

```
research_agent/
  app.py                 <- run this one file, it's the whole app
  search_module.py       <- finds web pages + YouTube videos
  extractor_module.py    <- reads the text out of pages/videos
  rag_module.py           <- picks the most relevant text chunks
  ai_module.py             <- AI writes notes with citations + a slide outline
  export_module.py        <- builds the .pptx and .pdf files
  requirements.txt
```

## Setup (one time)

1. Install Python 3.10+ if you don't have it.
2. Open a terminal in this folder and run:
   ```
   pip install -r requirements.txt
   ```
3. Get a Groq API key from https://console.groq.com/keys and a Tavily
   API key from https://app.tavily.com (free, 1,000 searches/month),
   then set both as environment variables:
   - Mac/Linux:
     ```
     export GROQ_API_KEY="your-key-here"
     export TAVILY_API_KEY="your-key-here"
     ```
   - Windows (PowerShell):
     ```
     $env:GROQ_API_KEY="your-key-here"
     $env:TAVILY_API_KEY="your-key-here"
     ```

   (If you'd rather use Anthropic's Claude or OpenAI's GPT instead, open
   `ai_module.py` and swap the `call_ai()` function for that provider's
   client — everything else in the project stays the same.)

## Run it

```
streamlit run app.py
```

A webpage opens in your browser automatically. Type a topic (e.g.
"Quantum Computing"), click **Start Research**, and wait about 30–60
seconds. You'll get:
- On-screen research notes with citation numbers like [1], [2]
- A list of sources
- A downloadable PowerPoint
- A downloadable PDF report with a References section

## How the pipeline works, step by step

1. **Search** — `search_module.py` asks the Tavily API for web pages and
   YouTube videos about the topic (free tier, 1,000 searches/month).
2. **Read** — `extractor_module.py` downloads each web page and strips
   out ads/menus, keeping just the article text. For YouTube videos, it
   grabs the transcript (subtitles) instead of literally watching the
   video — much lighter and just as informative.
3. **Rank** (our lightweight "RAG") — `rag_module.py` cuts every piece
   of text into small chunks and uses TF-IDF (a simple math technique,
   not a database) to score how relevant each chunk is to your topic.
   Only the best chunks move forward. This is the "less equipment"
   substitute for a full vector database.
4. **Think** — `ai_module.py` sends the best chunks to Claude and asks
   it to (a) write structured notes with a citation number on every
   fact, and (b) turn those notes into a slide-by-slide outline (JSON).
5. **Export** — `export_module.py` turns the notes into a PDF (with a
   References page) and turns the slide outline into a real .pptx file,
   using `fpdf2` and `python-pptx` — no Microsoft Office needed.
6. **Show** — `app.py` (Streamlit) displays everything on one webpage
   and gives you Download buttons for the PPT and PDF.

## Notes on "less equipment"

- No GPU needed — the AI work happens on Groq's servers via API.
- No database to install — the "RAG" step is just math in memory.
- No separate frontend/backend servers — Streamlit is both.
- Only costs money on Claude API calls (a few cents per research run).

## Troubleshooting

**"No readable content found" / search returns nothing:** Check that
`TAVILY_API_KEY` is actually set in your current terminal session — a
missing/invalid key is the most common cause. The terminal output will
say if it looks like an auth problem specifically.

**App hangs forever on "Searching the web and YouTube...":** This means
a network request never got a response and never timed out on its own —
usually a firewall, antivirus, or VPN silently blocking the connection.
The search and extraction code enforces hard timeouts (20s per search,
15s per URL) so it can no longer hang indefinitely — it will give up and
report the error instead.

**ModuleNotFoundError for any package:** Run
`python -m pip install -r requirements.txt` again, using `python -m pip`
(not bare `pip`) to guarantee it installs into the same interpreter that
`python -m streamlit run app.py` will actually use.


- Cache search results so re-running the same topic is instant.
- Add a PDF-upload option so users can research their own papers too.
- Swap TF-IDF for real embeddings (`sentence-transformers`) if you want
  smarter ranking — still no database required, just a different score.