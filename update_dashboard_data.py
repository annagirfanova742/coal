"""Обновляет docs/data/jkm.json и docs/data/risks.json для GitHub Pages."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "docs" / "data"
JKM_FILE = DATA_DIR / "jkm.json"
RISKS_FILE = DATA_DIR / "risks.json"
RISKS_SOURCE = DATA_DIR / "risks_source.json"

SOURCES = [
    ("investing", "https://www.investing.com/commodities/lng-japan-korea-marker-platts-futures"),
    ("investing-uk", "https://uk.investing.com/commodities/lng-japan-korea-marker-platts-futures"),
]
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_price(text: str) -> float | None:
    if not text:
        return None
    cleaned = text.replace("\xa0", " ").replace(",", "")
    match = re.search(r"(-?\d+(?:\.\d+)?)", cleaned)
    if not match:
        return None
    value = float(match.group(1))
    return value if 1.0 <= value <= 100.0 else None


def fetch_html() -> tuple[str, str]:
    errors = []
    with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS, http2=False) as client:
        for name, url in SOURCES:
            try:
                response = client.get(url)
                response.raise_for_status()
                return name, response.text
            except Exception as exc:
                errors.append(f"{name}: {exc}")
    raise RuntimeError("; ".join(errors)[:300])


def fetch_jkm() -> dict:
    source_name, html = fetch_html()

    soup = BeautifulSoup(html, "html.parser")

    for selector in (
        '[data-test="instrument-price-last"]',
        'span[data-test="instrument-price-last"]',
        'div[data-test="instrument-price-last"]',
    ):
        for node in soup.select(selector):
            price = parse_price(node.get_text(" ", strip=True))
            if price:
                return {
                    "source": source_name,
                    "price": price,
                    "updated_at": now_iso(),
                    "stale": False,
                }

    match = re.search(r'"last"\s*:\s*"?(\d+(?:\.\d+)?)"?', html)
    if match:
        price = parse_price(match.group(1))
        if price:
            return {
                "source": source_name + ":json",
                "price": price,
                "updated_at": now_iso(),
                "stale": False,
            }

    raise ValueError("JKM price not found on Investing page")


def update_jkm() -> None:
    previous = read_json(JKM_FILE, {"price": 15.0, "source": "bootstrap"})
    try:
        payload = fetch_jkm()
    except Exception as exc:  # keep last known value instead of breaking the site
        payload = {
            "source": previous.get("source", "cache"),
            "price": previous.get("price", 15.0),
            "updated_at": now_iso(),
            "stale": True,
            "error": str(exc)[:200],
        }
    write_json(JKM_FILE, payload)


def update_risks() -> None:
    source = read_json(RISKS_SOURCE, {"items": []})
    write_json(
        RISKS_FILE,
        {
            "source": "risks_source.json",
            "updated_at": now_iso(),
            "items": source.get("items", []),
        },
    )


if __name__ == "__main__":
    update_jkm()
    update_risks()
