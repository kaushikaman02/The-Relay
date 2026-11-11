
import json
import re
from pathlib import Path
from pypdf import PdfReader

BASE_DIR = Path(__file__).resolve().parent.parent
PAPER_DIR = BASE_DIR / "papers"
DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(exist_ok=True)

papers = [
    {
        "file": "attention_is_all_you_need_v7.pdf",
        "title": "Attention Is All You Need",
        "arxiv": "1706.03762v7"
    },
    {
        "file": "moshi_v1.pdf",
        "title": "Moshi",
        "arxiv": "2410.00037v1"
    },
    {
        "file": "dynamic_chunking_v2.pdf",
        "title": "Dynamic Chunking",
        "arxiv": "2507.07955v2"
    }
]

output_file = DATA_DIR / "paper_pages.jsonl"

total_pages = 0

with open(output_file, "w", encoding="utf-8") as output:

    for paper in papers:

        pdf_path = PAPER_DIR / paper["file"]

        if not pdf_path.exists():
            print("Missing PDF:", paper["file"])
            continue

        print("\nExtracting:", paper["title"])

        reader = PdfReader(str(pdf_path))

        extracted_pages = 0

        for page_number, page in enumerate(reader.pages, start=1):

            text = page.extract_text() or ""

            text = re.sub(r"\s+", " ", text).strip()

            if not text:
                continue

            record = {
                "title": paper["title"],
                "arxiv_id": paper["arxiv"],
                "page": page_number,
                "text": text
            }

            output.write(
                json.dumps(record, ensure_ascii=False) + "\n"
            )

            extracted_pages += 1
            total_pages += 1

        print("Pages:", len(reader.pages))
        print("Pages with extracted text:", extracted_pages)

print("\nExtraction completed.")
print("Total pages extracted:", total_pages)
print("Saved to:", output_file)
