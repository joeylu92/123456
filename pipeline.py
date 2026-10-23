from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

DB = Path("data/pipeline.db")


def norm(value: str | None) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return " ".join(value.split())


def words(value: str | None) -> set[str]:
    return {w for w in norm(value).split() if len(w) > 1}


def similarity(left: str, right: str) -> float:
    a, b = norm(left), norm(right)
    if not a or not b:
        return 0.0
    seq = SequenceMatcher(None, a, b).ratio()
    aw, bw = words(a), words(b)
    token = len(aw & bw) / max(1, len(aw | bw))
    return round(0.55 * seq + 0.45 * token, 4)


def parse_date(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


@dataclass
class OutputRow:
    shopee_title: str
    selling_points: str
    image_urls: str
    specifications: str
    dimensions: str
    sales: int | None
    price_brl: float | None
    shop: str
    shopee_url: str
    listed_at: str
    makerworld_title: str
    makerworld_url: str
    makerworld_license: str
    makerworld_confidence: float
    source_1688_title: str
    source_1688_url: str
    settlement_price_cny: float | None
    weight_kg: float | None
    review_status: str


def best_match(title: str, candidates: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float]:
    scored = [(item, similarity(title, item.get("title", ""))) for item in candidates]
    return max(scored, key=lambda pair: pair[1], default=(None, 0.0))


def process(payload: dict[str, Any], days: int = 60, threshold: float = 0.45) -> list[OutputRow]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    models = payload.get("makerworld", [])
    sources = payload.get("sources_1688", [])
    seen: set[tuple[str, str, str]] = set()
    rows: list[OutputRow] = []
    for item in payload.get("shopee", []):
        listed_at = parse_date(item["listed_at"])
        if listed_at < cutoff:
            continue
        title = item.get("title", "")
        if "mini jesus" not in norm(title) and not {"mini", "jesus", "3d"}.issubset(words(title)):
            continue
        key = (item.get("url", ""), norm(title), norm(item.get("shop", "")))
        if key in seen:
            continue
        seen.add(key)
        model, model_score = best_match(title, models)
        if model is None or model_score < threshold:
            continue
        source, source_score = best_match(title, sources)
        has_source = source is not None and source_score >= threshold
        rows.append(OutputRow(
            shopee_title=title,
            selling_points=" | ".join(item.get("selling_points", [])),
            image_urls=" | ".join(item.get("images", [])),
            specifications=json.dumps(item.get("specifications", {}), ensure_ascii=False),
            dimensions=item.get("dimensions", ""),
            sales=item.get("sales"),
            price_brl=item.get("price_brl"),
            shop=item.get("shop", ""),
            shopee_url=item.get("url", ""),
            listed_at=listed_at.isoformat(),
            makerworld_title=model.get("title", ""),
            makerworld_url=model.get("url", ""),
            makerworld_license=model.get("license", "unknown"),
            makerworld_confidence=model_score,
            source_1688_title=source.get("title", "") if has_source else "",
            source_1688_url=source.get("url", "") if has_source else "",
            settlement_price_cny=source.get("settlement_price_cny") if has_source else None,
            weight_kg=source.get("weight_kg") if has_source else None,
            review_status="待审核" if has_source else "待切片/补货源",
        ))
    return rows


def init_db() -> None:
    DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, item_count INTEGER NOT NULL)")
    print(f"initialized {DB}")


def run_process(input_path: Path, output_path: Path, days: int, threshold: float) -> None:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    rows = process(payload, days=days, threshold=threshold)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(OutputRow.__dataclass_fields__)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, item_count INTEGER NOT NULL)")
        conn.execute("INSERT INTO runs(created_at, item_count) VALUES (?, ?)", (datetime.now(timezone.utc).isoformat(), len(rows)))
    print(f"wrote {len(rows)} rows to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    process_cmd = sub.add_parser("process")
    process_cmd.add_argument("--input", type=Path, required=True)
    process_cmd.add_argument("--output", type=Path, required=True)
    process_cmd.add_argument("--days", type=int, default=60)
    process_cmd.add_argument("--threshold", type=float, default=0.45)
    args = parser.parse_args()
    if args.command == "init":
        init_db()
    else:
        run_process(args.input, args.output, args.days, args.threshold)


if __name__ == "__main__":
    main()
