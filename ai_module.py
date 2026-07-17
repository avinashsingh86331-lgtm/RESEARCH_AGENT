"""
ai_module.py
------------
Job: This is the "brain". We send the most relevant chunks (from
rag_module.py) to an AI model and ask it to:
  1. Extract the important facts
  2. Write clean research notes
  3. Attach a citation number to every fact, matching a source list

We use the Groq API here (fast inference, OpenAI-compatible interface).
If you prefer Anthropic's Claude or OpenAI's GPT, just replace the
`call_ai()` / `stream_research_notes()` function bodies - the rest of
the project does not need to change.
"""

import os
import json
from dotenv import load_dotenv
from groq import Groq
from search_module import search_web, search_youtube

load_dotenv()  # reads GROQ_API_KEY / TAVILY_API_KEY from a .env file, if present

# Reads your key from the GROQ_API_KEY environment variable (or .env file).
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

MODEL_NAME = "openai/gpt-oss-20b"


def call_ai(prompt, max_tokens=2000):
    """Send one prompt to the Groq model and return the plain text answer."""
    response = client.chat.completions.create(
        model=MODEL_NAME,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    content = response.choices[0].message.content
    finish_reason = response.choices[0].finish_reason
    if not content:
        raise RuntimeError(
            f"AI returned an empty response (finish_reason={finish_reason}). "
            f"This usually means max_tokens was too low - the model (which "
            f"does internal reasoning that also counts against the token "
            f"budget) ran out of room before producing visible output."
        )
    return content


def build_source_list(chunks):
    """
    Turn ranked chunks into a numbered, de-duplicated source list.
    Returns: (source_list, chunks_with_numbers)
      source_list -> [{"num": 1, "title": ..., "url": ...}, ...]
      chunks_with_numbers -> same chunks, each tagged with its source number
    """
    url_to_num = {}
    source_list = []

    for chunk in chunks:
        url = chunk["url"]
        if url not in url_to_num:
            num = len(source_list) + 1
            url_to_num[url] = num
            source_list.append({"num": num, "title": chunk["title"], "url": url})
        chunk["source_num"] = url_to_num[url]

    return source_list, chunks


def generate_research_notes(topic, chunks, source_list):
    """
    Ask the AI to write structured research notes with inline citations
    like [1], [2] that match the source_list numbers.
    (Non-streaming version - waits for the full answer, then returns it.)
    """
    prompt = _build_notes_prompt(topic, chunks, source_list)
    return call_ai(prompt, max_tokens=2500)


def stream_research_notes(topic, chunks, source_list):
    """
    Same as generate_research_notes, but STREAMS the answer piece by piece
    as the AI writes it - instead of waiting for the whole thing and then
    showing it all at once. This is a generator: it "yields" small chunks
    of text one at a time, so the webpage can update live, word by word,
    like watching someone type in real time.
    """
    prompt = _build_notes_prompt(topic, chunks, source_list)
    stream = client.chat.completions.create(
        model=MODEL_NAME,
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def _build_notes_prompt(topic, chunks, source_list):
    """Shared prompt-builder used by both the normal and streaming versions."""
    context_text = ""
    for c in chunks:
        context_text += f"\n[Source {c['source_num']}] {c['text']}\n"

    sources_text = "\n".join(f"[{s['num']}] {s['title']} - {s['url']}" for s in source_list)

    return f"""You are a research assistant. Using ONLY the material below,
write clear research notes about: "{topic}"

Requirements:
- Organize the notes with short headings (e.g. Definition, Key Concepts,
  Applications, Challenges, Future Outlook) - use headings that fit the topic.
- Every factual sentence must end with a citation number in square
  brackets, e.g. [2], matching the source list below.
- Keep language simple and clear.
- Do not invent facts that aren't supported by the material.

MATERIAL:
{context_text}

SOURCE LIST (for your citation numbers):
{sources_text}

Write the research notes now.
"""


def generate_slide_outline(topic, notes_text):
    """
    Ask the AI to turn the research notes into a slide-by-slide outline
    as JSON, so we can feed it straight into python-pptx.
    """
    prompt = f"""Convert the research notes below into a slide outline for
a presentation about "{topic}".

Return ONLY valid JSON (no extra text, no markdown fences) in this exact
shape:

{{
  "title_slide": "Short catchy title",
  "subtitle": "One-line subtitle",
  "slides": [
    {{"heading": "Slide heading", "bullets": ["point 1", "point 2", "point 3"]}}
  ]
}}

Make 6 to 8 content slides. Keep each bullet under 15 words. Do not include
citation brackets in the slide text.

RESEARCH NOTES:
{notes_text}
"""
    # Generous budget: this model does internal reasoning that also
    # consumes max_tokens, so a low limit can leave zero room for the
    # actual JSON output.
    try:
        raw = call_ai(prompt, max_tokens=4000)
    except RuntimeError as e:
        print(f"generate_slide_outline: AI call failed ({e}); using fallback outline.")
        return _fallback_outline(topic, notes_text)

    outline = _try_parse_json_outline(raw)
    if outline is not None:
        return outline

    print(f"generate_slide_outline: could not parse AI response as JSON. "
          f"Raw response was:\n{raw}\nUsing fallback outline instead.")
    return _fallback_outline(topic, notes_text)


def _try_parse_json_outline(raw):
    """
    Try to pull valid JSON out of the model's raw text, tolerating markdown
    fences or any stray text before/after the JSON object. Returns the
    parsed dict, or None if nothing usable was found.
    """
    if not raw:
        return None

    cleaned = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fall back to grabbing the first {...} block in case the model added
    # commentary before or after the JSON.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            return None

    return None


def _fallback_outline(topic, notes_text):
    """
    Last resort if the AI never returns usable JSON: build a basic outline
    directly from the research notes' own headings, so the app can still
    produce a PPT instead of crashing.
    """
    headings = [
        line.strip("# ").strip()
        for line in notes_text.split("\n")
        if line.strip().startswith("#")
    ]
    if not headings:
        headings = [topic]

    slides = [
        {"heading": h, "bullets": ["See research notes for details."]}
        for h in headings[:8]
    ]

    return {
        "title_slide": topic,
        "subtitle": "Research overview",
        "slides": slides
    }