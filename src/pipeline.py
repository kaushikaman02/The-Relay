
import os
import re
import time

from dotenv import load_dotenv
from groq import Groq

from retrieval import load_pages, create_chunks
from retrieval import build_index, search

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "openai/gpt-oss-20b"

# Load and index the research library
print("Loading research library...")

pages = load_pages()
chunks = create_chunks(pages)
vectorizer, matrix = build_index(chunks)

print("Library ready:", len(chunks), "chunks")


# STEP 1: Retrieve evidence (tool call)
def retrieve_evidence(question):

    results = search(
        question,
        chunks,
        vectorizer,
        matrix
    )

    return results


# STEP 2: Check whether evidence exists
def check_evidence(results):

    if not results:
        return False

    return any(result["score"] > 0 for result in results)


# STEP 3: Generate answer using Groq
def generate_answer(question, results):

    context = ""

    for i, item in enumerate(results, start=1):

        context += f"""
Evidence {i}
Paper: {item['title']}
arXiv: {item['arxiv_id']}
Page: {item['page']}
Passage: {item['text']}
"""

    prompt = f"""
You are a research assistant.

Answer the user's question using ONLY the supplied evidence.

Rules:
1. Never invent facts.
2. If the evidence does not answer the question,
   explicitly say the papers do not provide enough information.
3. Cite every factual claim.
4. Use this citation format:
   [Paper title, arXiv:ID, p. PAGE]
5. Distinguish evidence from inference.
6. Do not cite papers that were not supplied.

QUESTION:
{question}

EVIDENCE:
{context}
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": "You provide accurate, evidence-grounded research answers."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2,
        max_completion_tokens=700
    )

    return response


# STEP 4: Verify citations

def verify_citations(answer, results):

    # A refusal does not require a paper citation.
    refusal_markers = [
    "the papers do not provide",
    "do not contain enough information",
    "do not give enough information",
    "insufficient information",
    "cannot be answered from the supplied evidence",
    "the evidence does not provide enough information",
    "the supplied papers do not contain"
]

    if any(marker in answer.lower() for marker in refusal_markers):
        return "refused_correctly"

    valid_sources = {
        (
            item["title"],
            item["arxiv_id"],
            str(item["page"])
        )
        for item in results
    }

    pattern = r"\[([^,\]]+),\s*arXiv:([^,\]]+),\s*p\.\s*(\d+)\]"

    citations = re.findall(pattern, answer)

    if not citations:
        return "wrong"

    for citation in citations:
        if citation not in valid_sources:
            return "wrong"

    return "citation_format_valid"



# STEP 5: Execute pipeline
def run_pipeline(question):

    start = time.perf_counter()

    print("\nRetrieving evidence...")

    results = retrieve_evidence(question)

    if not check_evidence(results):

        print("\nThe library does not contain sufficient matching evidence.")
        return

    print("Retrieved passages:", len(results))

    print("\nGenerating answer with Groq...")

    response = generate_answer(question, results)

    answer = response.choices[0].message.content

    print("\n--- Generated Answer ---")
    print(answer)

    print("\n--- Citation Verification ---")

    valid = verify_citations(answer, results)

    if valid == "refused_correctly":
      print("Answer grade: REFUSED CORRECTLY")
    elif valid == "citation_format_valid":
     print("Citation check: PASSED")

    else:
     print("Answer grade: WRONG / NEEDS REVIEW")
    print("Answer must not be sent.")
    elapsed = (time.perf_counter() - start) * 1000

    print("\n--- Performance ---")
    print("Total pipeline time:", round(elapsed, 2), "ms")
    print("Input tokens:", response.usage.prompt_tokens)
    print("Output tokens:", response.usage.completion_tokens)


if __name__ == "__main__":

    question = input("\nAsk your research question: ")

    run_pipeline(question)
