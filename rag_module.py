"""
rag_module.py
-------------
Job: This replaces the "Vector Database" from the original idea.

A real vector database (Pinecone, Chroma, Weaviate...) needs a server,
an account, and setup. For a small project we don't need any of that.

Instead we do "poor man's RAG":
1. Cut every document into small chunks (paragraphs).
2. Use TF-IDF (a classic, lightweight scikit-learn tool) to score how
   relevant each chunk is to our topic.
3. Keep only the top chunks.

This is 100% in-memory (RAM), needs zero installation of a database
server, and is good enough for a research-notes project.
"""

from sklearn.feature_extraction.text import TfidfVectorizer


def split_into_chunks(text, chunk_size=500):
    """Cut a long text into ~500-character chunks (roughly a paragraph)."""
    words = text.split()
    chunks = []
    current = []
    current_len = 0
    for word in words:
        current.append(word)
        current_len += len(word) + 1
        if current_len >= chunk_size:
            chunks.append(" ".join(current))
            current = []
            current_len = 0
    if current:
        chunks.append(" ".join(current))
    return chunks


def rank_relevant_chunks(documents, topic, top_k=10):
    """
    Input:  documents -> list of {"title", "url", "text", "type"}
            topic     -> the research topic string
    Output: list of the most relevant chunks, each tagged with its source,
            sorted best-match first.
    """
    all_chunks = []  # each item: {"text":..., "title":..., "url":...}

    for doc in documents:
        for chunk in split_into_chunks(doc["text"]):
            if len(chunk.strip()) > 40:  # skip tiny/empty chunks
                all_chunks.append({
                    "text": chunk,
                    "title": doc["title"],
                    "url": doc["url"]
                })

    if not all_chunks:
        return []

    # TF-IDF compares the topic against every chunk and scores similarity.
    texts = [c["text"] for c in all_chunks] + [topic]
    vectorizer = TfidfVectorizer(stop_words="english")
    matrix = vectorizer.fit_transform(texts)

    topic_vector = matrix[-1]        # last row = our topic
    chunk_vectors = matrix[:-1]      # all rows before it = the chunks

    scores = (chunk_vectors @ topic_vector.T).toarray().ravel()

    for chunk, score in zip(all_chunks, scores):
        chunk["score"] = float(score)

    all_chunks.sort(key=lambda c: c["score"], reverse=True)
    return all_chunks[:top_k]