#!/usr/bin/env python3
"""Обновление данных дашборда ВГК для GitHub Pages.

Источники цены JKM по приоритету:
  1. docs/data/jkm_manual.json  (если enabled: true)
  2. Yahoo Finance chart API, тикер JKM=F
  3. Investing.com HTML  (обычно 403 для роботов, запасной вариант)
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "docs" / "data"
JKM_FILE = DATA_DIR / "jkm.json"
MANUAL_FILE = DATA_DIR / "jkm_manual.json"
RISKS_SOURCE = DATA_DIR / "risks_source.json"
RISKS_FILE = DATA_DIR / "risks.json"

YAHOO_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/JKM=F"
    "?interval=1d&range=1mo"
)
INVESTING_URL = (
    "https://www.investing.com/commodities/"
    "lng-japan-korea-marker-platts-futures"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

MIN_PRICE = 2.0
MAX_PRICE = 100.0


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def valid(price: float) -> bool:
    return MIN_PRICE < price < MAX_PRICE


def from_yahoo(client: httpx.Client) -> tuple[float, str]:
    response = client.get(YAHOO_URL)
    response.raise_for_status()
    result = response.json()["chart"]["result"][0]

    meta = result.get("meta", {})

    value = meta.get("regularMarketPrice")
    if isinstance(value, (int, float)) and valid(float(value)):
        return round(float(value), 3), "yahoo:regularMarketPrice"

    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    closes = quote.get("close") or []
    stamps = result.get("timestamp") or []
    for offset in range(len(closes) - 1, -1, -1):
        value = closes[offset]
        if isinstance(value, (int, float)) and valid(float(value)):
            label = "yahoo:lastClose"
            if offset < len(stamps):
                day = datetime.fromtimestamp(
                    stamps[offset], tz=timezone.utc
                ).strftime("%d.%m")
                label = f"yahoo:lastClose {day}"
            return round(float(value), 3), label

    for key in ("previousClose", "chartPreviousClose"):
        value = meta.get(key)
        if isinstance(value, (int, float)) and valid(float(value)):
            return round(float(value), 3), f"yahoo:{key}"

    raise ValueError("Yahoo: подходящая цена не найдена")


def from_investing(client: httpx.Client) -> tuple[float, str]:
    response = client.get(INVESTING_URL)
    response.raise_for_status()
    html = response.text

    patterns = [
        r'data-test="instrument-price-last"[^>]*>([\d.,]+)<',
        r'"last"\s*:\s*"?([\d.]+)"?',
        r'PLATTS Future price today is\s*([\d.]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if not match:
            continue
        try:
            price = float(match.group(1).replace(",", ""))
        except ValueError:
            continue
        if valid(price):
            return round(price, 3), "investing"

    raise ValueError("Investing: цена не распознана")


def load_previous() -> dict:
    if JKM_FILE.exists():
        try:
            return json.loads(JKM_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"price": 15.0, "source": "bootstrap"}


def manual_override() -> dict | None:
    if not MANUAL_FILE.exists():
        return None
    try:
        data = json.loads(MANUAL_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not data.get("enabled"):
        return None
    price = data.get("price")
    if isinstance(price, (int, float)) and valid(float(price)):
        return {
            "price": round(float(price), 3),
            "source": "manual",
            "updated_at": now_iso(),
            "stale": False,
            "note": data.get("note", "ручное значение"),
        }
    return None


def update_jkm() -> dict:
    previous = load_previous()
    errors: list[str] = []

    override = manual_override()
    if override:
        JKM_FILE.write_text(
            json.dumps(override, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"JKM взят из ручного файла: {override['price']}")
        return override

    with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS) as client:
        for fetch in (from_yahoo, from_investing):
            try:
                price, source = fetch(client)
            except Exception as exc:
                errors.append(f"{fetch.__name__}: {exc}")
                continue

            payload = {
                "price": price,
                "source": source,
                "updated_at": now_iso(),
                "stale": False,
                "previous_price": previous.get("price"),
            }
            JKM_FILE.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"JKM обновлён: {price} ({source})")
            return payload

    payload = {
        "price": previous.get("price", 15.0),
        "source": previous.get("source", "bootstrap"),
        "updated_at": now_iso(),
        "stale": True,
        "error": " | ".join(errors)[:400],
    }
    JKM_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("JKM НЕ обновлён:", payload["error"])
    return payload


def update_risks() -> None:
    if not RISKS_SOURCE.exists():
        print("risks_source.json отсутствует — пропуск")
        return

    items = json.loads(RISKS_SOURCE.read_text(encoding="utf-8"))
    if isinstance(items, dict):
        items = items.get("items", [])

    payload = {
        "source": "risks_source.json",
        "updated_at": now_iso(),
        "count": len(items),
        "items": items,
    }
    RISKS_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Риски обновлены: {len(items)} записей")


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    update_jkm()
    update_risks()


if __name__ == "__main__":
    main()
