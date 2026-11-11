
import requests
import time
from pathlib import Path

PAPER_DIR = Path(__file__).resolve().parent.parent / "papers"
PAPER_DIR.mkdir(exist_ok=True)

papers = [
    {
        "id": "1706.03762v7",
        "name": "attention_is_all_you_need_v7.pdf"
    },
    {
        "id": "2410.00037v1",
        "name": "moshi_v1.pdf"
    },
    {
        "id": "2507.07955v2",
        "name": "dynamic_chunking_v2.pdf"
    }
]

for paper in papers:

    url = f"https://arxiv.org/pdf/{paper['id']}"
    filepath = PAPER_DIR / paper["name"]

    print(f"\nDownloading {paper['id']}...")

    try:
        response = requests.get(
            url,
            timeout=120,
            headers={"User-Agent": "TheRelayResearchAssistant/1.0"}
        )

        response.raise_for_status()

        if not response.content.startswith(b"%PDF"):
            raise ValueError("Downloaded content is not a valid PDF")

        filepath.write_bytes(response.content)

        print("Downloaded:", paper["name"])
        print("Size:", round(len(response.content) / 1024, 2), "KB")

    except Exception as e:
        print("Download failed:", paper["id"], e)

    time.sleep(3)

print("\nPaper download process finished.")
