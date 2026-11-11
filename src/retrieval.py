
import json
import re
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data" / "paper_pages.jsonl"

CHUNK_SIZE = 500
OVERLAP = 100
TOP_K = 3


def load_pages():
    pages = []

    with open(DATA_FILE, encoding="utf-8") as f:
        for line in f:
            pages.append(json.loads(line))

    return pages


def create_chunks(pages):
    chunks = []

    for page in pages:
        words = page["text"].split()

        start = 0

        while start < len(words):
            end = start + CHUNK_SIZE

            text = " ".join(words[start:end])

            if text.strip():
                chunks.append({
                    "title": page["title"],
                    "arxiv_id": page["arxiv_id"],
                    "page": page["page"],
                    "text": text
                })

            if end >= len(words):
                break

            start = end - OVERLAP

    return chunks


def build_index(chunks):
    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2)
    )

    matrix = vectorizer.fit_transform(
        [chunk["text"] for chunk in chunks]
    )

    return vectorizer, matrix


def search(query, chunks, vectorizer, matrix):
    query_vector = vectorizer.transform([query])

    scores = cosine_similarity(
        query_vector,
        matrix
    ).flatten()

    indices = scores.argsort()[::-1][:TOP_K]

    results = []

    for index in indices:
        if scores[index] <= 0:
            continue

        result = chunks[index].copy()
        result["score"] = float(scores[index])

        results.append(result)

    return results


if __name__ == "__main__":

    pages = load_pages()
    chunks = create_chunks(pages)

    vectorizer, matrix = build_index(chunks)

    print("Pages loaded:", len(pages))
    print("Chunks created:", len(chunks))

    question = input("\nEnter your research question: ")

    results = search(
        question,
        chunks,
        vectorizer,
        matrix
    )

    print("\n--- Retrieved passages ---")

    for result in results:
        print("\nPaper:", result["title"])
        print("arXiv:", result["arxiv_id"])
        print("Page:", result["page"])
        print("Score:", round(result["score"], 4))
        print("Text:", result["text"][:700])
        print("-" * 60)
