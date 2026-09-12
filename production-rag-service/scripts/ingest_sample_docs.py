"""
Ingests a few sample documents into a RUNNING service via its /ingest
endpoint — a quick way to have something real to query in /chat.

Run the service first:
    uvicorn app.main:app --reload
Then:
    python scripts/ingest_sample_docs.py
"""
import httpx

SAMPLE_DOCS = [
    ("refund-policy.txt", (
        "Our refund policy allows returns within 30 days of purchase. "
        "Refunds are issued to the original payment method within 5-7 "
        "business days. Digital products are non-refundable once "
        "downloaded. For defective products, contact support within 14 "
        "days for a full refund including shipping costs."
    )),
    ("support-hours.txt", (
        "Support is available 9am to 5pm Eastern, Monday through Friday. "
        "For urgent issues outside those hours, email urgent@example.com "
        "and a member of the on-call team will respond within 2 hours."
    )),
    ("shipping-policy.txt", (
        "Standard shipping takes 5-7 business days and is free on orders "
        "over $50. Expedited shipping (2-3 business days) is available "
        "for an additional $15. International shipping is available to "
        "most countries and takes 10-15 business days."
    )),
]


def main(base_url: str = "http://127.0.0.1:8000"):
    with httpx.Client(base_url=base_url, timeout=30.0) as client:
        for source, text in SAMPLE_DOCS:
            r = client.post("/ingest", params={"source": source, "text": text})
            r.raise_for_status()
            print(f"Ingested {source} -> document_id={r.json()['document_id']}")


if __name__ == "__main__":
    main()
