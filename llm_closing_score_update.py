import csv
import logging
import sys
import time
from typing import Dict, List

import pandas as pd
import requests


# ==== User-configurable constants ====
BASE_NAMES = [
    "static_non_blocking_banner_stays_until_action",
    "blocking_banner",
    "blocking_banner_with_option_to_close",
    "floating_non_blocking_banner_stays_until_action_close_option_given",
    "floating_non_blocking_banner_stays_until_action",
    # "simple_non_blocking_banner",
]

PROMPT_PATH = "prompt.txt"

BASE_URL = "http://192.168.0.112:1234"
# MODEL = "qwen/qwen3-coder-next"
MODEL = "qwen/qwen3.5-35b-a3b"
TIMEOUT_SECONDS = 1500

# Optional pacing between requests (seconds)
SLEEP_SECONDS = 0

# Logging
LOG_FILE_PATH = "llm_closing_score_update.log"
ITERATION_LOG_FILE = "llm_closing_score_update_iterations.log"
LOG_LEVEL_CONSOLE = logging.INFO
LOG_LEVEL_FILE = logging.DEBUG

# CSV parsing options (keep HTML intact)
READ_CSV_KWARGS = {
    "header": None,
    "engine": "python",
    "quotechar": '"',
    "quoting": csv.QUOTE_MINIMAL,
    "doublequote": True,
    "dtype": str,
    "keep_default_na": False,
}

# HTML column selection
HTML_COLUMN_INDEX = 3
HTML_FALLBACK_COLUMN_INDEX = 4


def append_iteration_log(
    base_name: str,
    row_idx: int,
    domain: str,
    html: str,
    prompt_preview: str,
    answer: str,
    value: str,
) -> None:
    with open(ITERATION_LOG_FILE, "a", encoding="utf-8") as handle:
        handle.write("\n\n" + "=" * 60 + "\n")
        handle.write(f"base_name: {base_name}\n")
        handle.write(f"row_idx: {row_idx}\n")
        handle.write(f"domain: {domain}\n")
        handle.write("html:\n")
        handle.write(html + "\n")
        handle.write("prompt_preview:\n")
        handle.write(prompt_preview + "\n")
        handle.write(f"answer: {answer}\n")
        handle.write(f"value: {value}\n")


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("closing_score_updater")
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(LOG_LEVEL_CONSOLE)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(LOG_FILE_PATH, mode="a", encoding="utf-8")
    file_handler.setLevel(LOG_LEVEL_FILE)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


def load_prompt(prompt_path: str) -> str:
    with open(prompt_path, "r", encoding="utf-8") as handle:
        prompt = handle.read().strip()

    return prompt


def _build_url(base_url: str, path: str) -> str:
    base = base_url.rstrip("/")
    return f"{base}{path}"


def _extract_text(response_json: Dict) -> str:
    if "choices" in response_json and response_json["choices"]:
        choice = response_json["choices"][0]
        if "message" in choice and "content" in choice["message"]:
            return str(choice["message"]["content"])
        if "text" in choice:
            return str(choice["text"])
    raise ValueError("No text content found in LLM response.")


def call_llm(prompt: str) -> str:
    url = _build_url(BASE_URL, "/v1/chat/completions")
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }

    response = requests.post(url, json=payload, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    data = response.json()
    return _extract_text(data).strip()


def load_csv(path: str) -> pd.DataFrame:
    csv.field_size_limit(sys.maxsize)
    df = pd.read_csv(path, **READ_CSV_KWARGS)
    if df.shape[1] < 4:
        raise ValueError(f"CSV at {path} has {df.shape[1]} columns, expected at least 4.")
    return df


def build_domain_index(root_df: pd.DataFrame) -> Dict[str, List[int]]:
    domain_map: Dict[str, List[int]] = {}
    for idx, domain in enumerate(root_df.iloc[:, 0].tolist()):
        key = str(domain)
        domain_map.setdefault(key, []).append(idx)
    return domain_map


def update_root_csv(base_name: str, logger: logging.Logger, prompt_prefix: str) -> None:
    dataset_start = time.perf_counter()
    html_path = f"{base_name}-datadir/1-Starting_Point_0/htmls.csv"
    root_csv_path = f"{base_name}.csv"

    logger.info("Starting base_name=%s", base_name)
    logger.info("Loading html csv from %s", html_path)
    html_df = load_csv(html_path)
    logger.info("Loading root csv from %s", root_csv_path)
    root_df = load_csv(root_csv_path)

    domain_index = build_domain_index(root_df)
    logger.info("Loaded html rows=%s, root rows=%s", len(html_df), len(root_df))

    updated = 0
    missing = 0
    failed = 0
    timeouts = 0

    for row_idx, row in html_df.iterrows():
        domain = str(row.iloc[2])
        html = str(row.iloc[HTML_COLUMN_INDEX])
        if HTML_FALLBACK_COLUMN_INDEX < len(row):
            fallback_html = str(row.iloc[HTML_FALLBACK_COLUMN_INDEX])
            if len(fallback_html) > len(html):
                html = fallback_html

        logger.debug(
            "Row %s | domain=%s | html_length=%s | html=%s",
            row_idx,
            domain,
            len(html),
            html,
        )

        if domain not in domain_index:
            missing += 1
            logger.warning("Domain not found in root CSV: %s", domain)
            continue

        prompt = f"{prompt_prefix}\n\nHTML:\n{html}"
        prompt_preview = prompt[:50]
        logger.debug("Row %s | prompt_preview=%s", row_idx, prompt_preview)

        try:
            answer = call_llm(prompt)
        except requests.exceptions.Timeout:
            timeouts += 1
            answer = "TIMEOUT"
            logger.warning("LLM request timed out for domain '%s'", domain)
        except Exception as exc:
            failed += 1
            logger.exception("LLM request failed for domain '%s': %s", domain, exc)
            continue

        logger.debug("Row %s | raw_answer=%s", row_idx, answer)

        value = f"closing_score:{answer}"
        append_iteration_log(
            base_name,
            int(row_idx),
            domain,
            html,
            prompt_preview,
            answer,
            value,
        )
        for idx in domain_index[domain]:
            root_df.iat[idx, 3] = value
            updated += 1

        logger.info(
            "Row %s | domain=%s | updated_rows=%s | value=%s",
            row_idx,
            domain,
            len(domain_index[domain]),
            value,
        )

        if SLEEP_SECONDS > 0:
            time.sleep(SLEEP_SECONDS)

    logger.info("Saving updated root csv to %s", root_csv_path)
    root_df.to_csv(
        root_csv_path,
        index=False,
        header=False,
        quoting=csv.QUOTE_MINIMAL,
        quotechar='"',
        escapechar="\\",
    )

    logger.info(
        "Completed base_name=%s | updated=%s | missing_domain=%s | failed_requests=%s | timeouts=%s",
        base_name,
        updated,
        missing,
        failed,
        timeouts,
    )
    dataset_elapsed = time.perf_counter() - dataset_start
    logger.info("Elapsed base_name=%s | seconds=%.2f", base_name, dataset_elapsed)


def main() -> None:
    logger = setup_logging()
    prompt_prefix = load_prompt(PROMPT_PATH)
    run_start = time.perf_counter()
    for base_name in BASE_NAMES:
        update_root_csv(base_name, logger, prompt_prefix)
    run_elapsed = time.perf_counter() - run_start
    logger.info("Elapsed total | seconds=%.2f", run_elapsed)


if __name__ == "__main__":
    main()
