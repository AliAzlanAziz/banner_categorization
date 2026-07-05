import base64
import os
import time
from typing import List, Optional, Tuple

import pandas as pd
import requests
from selenium import webdriver
from selenium.webdriver.firefox.options import Options

# === Configuration ===
BASE_NAMES = [
    "static_non_blocking_banner_stays_until_action",
    "blocking_banner_with_option_to_close",
    "blocking_banner",
    "floating_non_blocking_banner_stays_until_action_close_option_given",
    "floating_non_blocking_banner_stays_until_action",
]

# Firefox binary path — adjust if not running on Linux with snap Firefox
FIREFOX_BINARY = "/snap/firefox/current/usr/lib/firefox/firefox"

BASE_URL = "http://192.168.0.112:1234"
MODEL = "qwen/qwen3.5-35b-a3b"
TIMEOUT_SECONDS = 120
PAGE_LOAD_WAIT = 15  # seconds to wait after navigating to the page

PROMPT_TEXT = """You are an identifier of a close button in a cookie banner given the screenshot of the website that we captured via navigating to the website using script and capture the screen.
Though accepting and rejecting cookies also closes the banner eventually but they are not close buttons.
Similarly beware that when you have identified a closing button just be sure that it is not a button to reject the cookies by looking at the visible text that the button renders on the browser.
A button is rejecting type when the visible text explicitly suggests that upon pressing it, it will reject the cookies.
Answer in true only well you are very sure if there is a close button since we cannot tolerate false positives.
Sometimes the text present on buttons suggest that the button is a close button, sometimes the icon/image like X is rendered, so basically use your thinking and logic each time how the button might look like, also such a button might be on the whole screenshot, but you have to look it inside the cookie banner area.
Your answer should only be 'True' if a button is there or else 'False' and nothing else"""

LOG_PATH = "crawl_classify_run.log"
ERROR_LOG_PATH = "crawl_classify_errors.log"
SCREENSHOTS_DIR_SUFFIX = "-screenshots"


def log_line(path: str, line: str) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def normalize_domain(value: str) -> str:
    return str(value).strip()


def get_screenshot_dir(base_name: str) -> str:
    return f"{base_name}{SCREENSHOTS_DIR_SUFFIX}"


def get_screenshot_path(base_name: str, domain: str) -> str:
    return os.path.join(get_screenshot_dir(base_name), f"{domain}.png")


def create_driver() -> webdriver.Firefox:
    options = Options()
    options.binary_location = FIREFOX_BINARY

    options.set_preference("dom.webnotifications.enabled", False)
    options.set_preference("dom.push.enabled", False)
    options.set_preference("media.navigator.permission.disabled", True)
    options.set_preference("permissions.default.microphone", 2)
    options.set_preference("permissions.default.camera", 2)
    options.set_preference("geo.enabled", False)
    options.set_preference("permissions.default.geo", 2)
    options.set_preference("media.autoplay.default", 5)
    options.set_preference("signon.rememberSignons", False)
    options.set_preference("dom.disable_open_during_load", False)

    driver = webdriver.Firefox(options=options)
    driver.set_page_load_timeout(60)
    driver.maximize_window()
    return driver


def build_request_payload(image_b64: str) -> dict:
    return {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT_TEXT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                    },
                ],
            }
        ],
        "stream": False,
        "temperature": 0,
    }


def call_llm(image_path: str) -> Tuple[str, float]:
    start = time.time()
    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("ascii")
    payload = build_request_payload(image_b64)
    response = requests.post(
        f"{BASE_URL}/v1/chat/completions", json=payload, timeout=TIMEOUT_SECONDS
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return str(content).strip(), time.time() - start


def phase_screenshots(base_name: str, domains: List[str]) -> None:
    sc_dir = get_screenshot_dir(base_name)
    os.makedirs(sc_dir, exist_ok=True)

    driver = create_driver()
    try:
        for domain in domains:
            out_path = get_screenshot_path(base_name, domain)
            if os.path.exists(out_path):
                log_line(LOG_PATH, f"{base_name} | {domain} | screenshot exists, skipping")
                continue
            try:
                driver.get(f"https://{domain}")
                time.sleep(PAGE_LOAD_WAIT)
                driver.save_screenshot(out_path)
                log_line(LOG_PATH, f"{base_name} | {domain} | screenshot saved")
            except Exception as exc:
                log_line(ERROR_LOG_PATH, f"{base_name} | {domain} | screenshot failed | {exc}")
    finally:
        driver.quit()


def phase_llm(base_name: str, input_df: pd.DataFrame) -> pd.DataFrame:
    for i, row in input_df.iterrows():
        domain = normalize_domain(row.iloc[0])
        if not domain:
            continue

        screenshot_path = get_screenshot_path(base_name, domain)
        if not os.path.exists(screenshot_path):
            log_line(
                ERROR_LOG_PATH,
                f"{base_name} | {domain} | screenshot not found | {screenshot_path}",
            )
            continue

        try:
            answer, elapsed = call_llm(screenshot_path)
        except Exception as exc:
            log_line(ERROR_LOG_PATH, f"{base_name} | {domain} | LLM request failed | {exc}")
            continue

        answer_norm = answer.strip().lower()
        if answer_norm not in {"true", "false"}:
            log_line(ERROR_LOG_PATH, f"{base_name} | {domain} | unexpected answer | {answer}")
            continue

        input_df.iat[i, 1] = answer_norm
        log_line(LOG_PATH, f"{base_name} | {domain} | {answer_norm} | {elapsed:.2f}s")

    return input_df


def process_base_name(base_name: str) -> None:
    input_csv = os.path.join("input-files", f"{base_name}.csv")
    start_time = time.time()
    log_line(LOG_PATH, f"START base={base_name} at {time.ctime(start_time)}")

    input_df = pd.read_csv(input_csv, header=None)

    if input_df.shape[1] < 2:
        input_df[1] = None

    domains = [
        normalize_domain(row.iloc[0])
        for _, row in input_df.iterrows()
        if normalize_domain(row.iloc[0])
    ]

    log_line(LOG_PATH, f"{base_name} | Phase 1: taking screenshots for {len(domains)} domains")
    phase_screenshots(base_name, domains)

    log_line(LOG_PATH, f"{base_name} | Phase 2: LLM classification")
    input_df = phase_llm(base_name, input_df)

    input_df.to_csv(input_csv, header=False, index=False)

    total_time = time.time() - start_time
    log_line(LOG_PATH, f"END base={base_name} total_time_s={total_time:.2f}")


def main() -> None:
    for base_name in BASE_NAMES:
        process_base_name(base_name)


if __name__ == "__main__":
    main()