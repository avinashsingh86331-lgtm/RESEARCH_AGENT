"""
app.py
------
This is the ONLY file you run. Streamlit gives us a web page (frontend)
and runs our Python logic (backend) in the exact same file/process.

Run it with:
    streamlit run app.py

What happens when you type a topic and press Enter:
  1. search_module.py    -> search the web + YouTube (runs quietly, no
                             step-by-step messages - just a single
                             "Researching..." spinner)
  2. extractor_module.py -> read articles + video transcripts
  3. rag_module.py        -> rank the most relevant chunks (no vector DB)
  4. ai_module.py          -> AI WRITES THE NOTES LIVE, streamed word by
                             word straight onto the page as it's generated
  5. export_module.py     -> save a PPTX and a PDF, ready to download
"""

import streamlit as st

from search_module import search_web, search_youtube
from extractor_module import gather_all_content
from rag_module import rank_relevant_chunks
from ai_module import build_source_list, stream_research_notes, generate_slide_outline
from export_module import create_pptx, create_pdf

# ---------------------------------------------------------------------
# PAGE SETUP - new logo (page icon) + custom styling for the frontend
# ---------------------------------------------------------------------
st.set_page_config(page_title="Nova Research", page_icon="🧠", layout="centered")

st.markdown("""
<style>
    /* Hide Streamlit's default menu/footer clutter for a cleaner look */
    #MainMenu, footer {visibility: hidden;}

    /* Page background */
    .stApp {
        background: linear-gradient(180deg, #0F1226 0%, #171B3A 100%);
    }

    /* Title styling */
    .nova-title {
        font-size: 2.4rem;
        font-weight: 800;
        background: linear-gradient(90deg, #7C8CFF, #A78BFA, #F472B6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0;
    }
    .nova-subtitle {
        text-align: center;
        color: #A0A3C4;
        font-size: 1rem;
        margin-top: 0.2rem;
        margin-bottom: 2rem;
    }

    /* Result cards */
    .nova-card {
        background: #1B1F3B;
        border: 1px solid #2E3260;
        border-radius: 14px;
        padding: 1.4rem 1.6rem;
        margin-bottom: 1.2rem;
    }
    .nova-card h4 {
        color: #C7C9F5;
        margin-top: 0;
    }

    /* Chat input styling */
    [data-testid="stChatInput"] {
        border-radius: 14px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="nova-title">🧠 Nova — Autonomous Research Agent</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="nova-subtitle">Type a topic below and press Enter — '
    'I\'ll research it and hand you notes, a PPT, and a PDF.</p>',
    unsafe_allow_html=True
)

# ---------------------------------------------------------------------
# INPUT - chat-style box. Submits immediately on Enter, no separate
# button needed, and none of the "Press Enter to apply" hint text that
# regular st.text_input() shows.
# ---------------------------------------------------------------------
topic = st.chat_input("Type a topic, e.g. Quantum Computing, and press Enter...")

if topic and topic.strip():

    # ---- Quiet background work: search, read, rank ----
    # No "Step 1/5..." messages - just a single spinner while this runs,
    # then the final result appears directly.
    with st.spinner("Researching your topic..."):
        web_results = search_web(topic, max_results=12)
        youtube_results = search_youtube(topic, max_results=5)

        documents, failed_urls = gather_all_content(web_results, youtube_results)

        if not documents:
            if not web_results and not youtube_results:
                st.error(
                    "No search results came back at all for that topic. "
                    "Check that TAVILY_API_KEY is set correctly in this "
                    "terminal session - check the terminal/logs for the "
                    "exact error."
                )
            else:
                st.error(
                    f"Found {len(web_results)} web result(s) and "
                    f"{len(youtube_results)} video(s), but couldn't extract "
                    f"readable text from any of them (sources may be paywalled, "
                    f"blocking scrapers, or temporarily down). "
                    f"Try a different topic or try again shortly."
                )
            st.stop()

        chunks = rank_relevant_chunks(documents, topic, top_k=15)
        source_list, chunks = build_source_list(chunks)

    # ---- AI writes the notes LIVE, streamed word by word ----
    st.markdown('<div class="nova-card"><h4>📝 Research Notes</h4>', unsafe_allow_html=True)
    notes_text = st.write_stream(stream_research_notes(topic, chunks, source_list))
    st.markdown('</div>', unsafe_allow_html=True)

    # ---- Once notes are done, quietly build the slide outline + files ----
    with st.spinner("Preparing your PPT and PDF..."):
        slide_outline = generate_slide_outline(topic, notes_text)
        pptx_path = create_pptx(topic, slide_outline, output_path="research_output.pptx")
        pdf_path = create_pdf(topic, notes_text, source_list, output_path="research_output.pdf")

    # ---- Sources ----
    st.markdown('<div class="nova-card"><h4>📚 Sources</h4>', unsafe_allow_html=True)
    for s in source_list:
        st.markdown(f"[{s['num']}] {s['title']} — {s['url']}")
    st.markdown('</div>', unsafe_allow_html=True)

    # ---- Downloads ----
    st.markdown('<div class="nova-card"><h4>⬇️ Download</h4>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        with open(pptx_path, "rb") as f:
            st.download_button("Download PPT", f, file_name=f"{topic}_research.pptx")
    with col2:
        with open(pdf_path, "rb") as f:
            st.download_button("Download PDF", f, file_name=f"{topic}_research.pdf")
    st.markdown('</div>', unsafe_allow_html=True)