from __future__ import annotations

import csv
import random
from pathlib import Path


SOURCE_FILE = Path("tranco_56WKN.csv")
OUTPUT_FILE = Path("input-files") / "tranco_56WKN_sample_250.csv"
SAMPLE_SIZE = 250
RANDOM_SEED = 42


def main() -> None:
    with SOURCE_FILE.open(newline="", encoding="utf-8") as source_handle:
        rows = list(csv.reader(source_handle))

    if len(rows) < SAMPLE_SIZE:
        raise ValueError(
            f"Source file only has {len(rows)} rows, cannot sample {SAMPLE_SIZE}."
        )

    sampled_rows = random.Random(RANDOM_SEED).sample(rows, SAMPLE_SIZE)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as output_handle:
        writer = csv.writer(output_handle)
        writer.writerows(sampled_rows)

    print(f"Wrote {SAMPLE_SIZE} rows to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()