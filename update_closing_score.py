import base64
import os
import time
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests

# === Configuration (edit before running) ===
BASE_NAMES = [
    # "static_non_blocking_banner_stays_until_action",
    # "blocking_banner_with_option_to_close",
    "blocking_banner",
    # "floating_non_blocking_banner_stays_until_action_close_option_given",
    # "floating_non_blocking_banner_stays_until_action",
]
BASE_URL = "http://192.168.0.112:1234"
MODEL = "qwen/qwen3.5-35b-a3b"
TIMEOUT_SECONDS = 120
PROMPT_TEXT = """You are an identifier of a close button in a cookie banner given the screenshot of the website that we captured via navigating to the website using script and capture the screen.
Though accepting and rejecting cookies also closes the banner eventually but they are not close buttons.
Similarly beware that when you have identified a closing button just be sure that it is not a button to reject the cookies by looking at the visible text that the button renders on the browser.
A button is rejecting type when the visible text explicitly suggests that upon pressing it, it will reject the cookies.
Answer in true only well you are very sure if there is a close button since we cannot tolerate false positives.
Sometimes the text present on buttons suggest that the button is a close button, sometimes the icon/image like X is rendered, so basically use your thinking and logic each time how the button might look like, also such a button might be on the whole screenshot, but you have to look it inside the cookie banner area.
Your answer should only be 'True' if a button is there or else 'False' and nothing else"""


LOG_PATH = "closing_score_run.log"
ERROR_LOG_PATH = "closing_score_errors.log"


def log_line(path: str, line: str) -> None:
	with open(path, "a", encoding="utf-8") as f:
		f.write(line + "\n")


def normalize_domain(value: str) -> str:
	return str(value).strip()


def find_screenshot_path(datadir: str, domain: str) -> Optional[str]:
	suffix = f" {domain}.png"
	try:
		for name in os.listdir(datadir):
			if name.endswith(suffix):
				return os.path.join(datadir, name)
	except FileNotFoundError:
		return None
	return None


def build_request_payload(prompt: str, image_b64: str) -> Dict:
	return {
		"model": MODEL,
		"messages": [
			{
				"role": "user",
				"content": [
					{"type": "text", "text": prompt},
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


def call_llm(prompt: str, image_path: str) -> Tuple[str, float]:
	start = time.time()
	with open(image_path, "rb") as f:
		image_b64 = base64.b64encode(f.read()).decode("ascii")

	payload = build_request_payload(prompt, image_b64)
	url = f"{BASE_URL}/v1/chat/completions"
	response = requests.post(url, json=payload, timeout=TIMEOUT_SECONDS)
	response.raise_for_status()
	data = response.json()
	content = data["choices"][0]["message"]["content"]
	return str(content).strip(), time.time() - start


def build_domain_index(root_df: pd.DataFrame) -> Dict[str, List[int]]:
	index: Dict[str, List[int]] = {}
	for i, value in root_df.iloc[:, 0].items():
		key = normalize_domain(value)
		if key:
			index.setdefault(key, []).append(i)
	return index


def update_rows(root_df: pd.DataFrame, row_ids: List[int], answer: str) -> int:
	new_value = f"closing_score:{answer}"
	for i in row_ids:
		root_df.iat[i, 3] = new_value
	return len(row_ids)


def process_base_name(base_name: str) -> None:
	input_csv = os.path.join("input-files", f"{base_name}.csv")
	root_csv = f"{base_name}.csv"
	datadir = os.path.join(
		f"{base_name}-datadir",
		"1-Starting_Point_0",
		"banner_screenshots",
	)
	abs_datadir = os.path.abspath(datadir)

	start_time = time.time()
	log_line(LOG_PATH, f"START base={base_name} at {time.ctime(start_time)}")

	input_df = pd.read_csv(input_csv, header=None)
	root_df = pd.read_csv(root_csv, header=None)
	domain_index = build_domain_index(root_df)

	if not os.path.isdir(abs_datadir):
		log_line(
			ERROR_LOG_PATH,
			f"{base_name} | screenshot directory missing | {abs_datadir}",
		)
		return

	processed = 0
	missing_screenshots = 0
	updated_rows = 0

	for _, row in input_df.iterrows():
		domain = normalize_domain(row.iloc[0])
		if not domain:
			continue

		processed += 1
		screenshot_path = find_screenshot_path(datadir, domain)
		if not screenshot_path:
			missing_screenshots += 1
			expected_suffix = f" {domain}.png"
			log_line(
				ERROR_LOG_PATH,
				(
					f"{base_name} | {domain} | screenshot not found | "
					f"searched_dir={abs_datadir} | expected_suffix={expected_suffix}"
				),
			)
			continue

		try:
			answer, elapsed = call_llm(PROMPT_TEXT, screenshot_path)
		except Exception as exc:
			log_line(
				ERROR_LOG_PATH,
				f"{base_name} | {domain} | request failed | {exc}",
			)
			continue

		answer_norm = answer.strip().lower()
		if answer_norm not in {"true", "false"}:
			log_line(
				ERROR_LOG_PATH,
				f"{base_name} | {domain} | invalid answer | {answer}",
			)
			continue

		row_ids = domain_index.get(domain, [])
		if not row_ids:
			log_line(
				ERROR_LOG_PATH,
				f"{base_name} | {domain} | no matching row in root csv",
			)
			continue

		updated_rows += update_rows(root_df, row_ids, answer_norm)
		log_line(
			LOG_PATH,
			f"{base_name} | {domain} | {screenshot_path} | {answer_norm} | {elapsed:.2f}s",
		)

	root_df.to_csv(root_csv, header=False, index=False)

	total_time = time.time() - start_time
	log_line(
		LOG_PATH,
		(
			f"END base={base_name} processed={processed} missing_screenshots={missing_screenshots} "
			f"updated_rows={updated_rows} total_time_s={total_time:.2f}"
		),
	)


def main() -> None:
	for base_name in BASE_NAMES:
		process_base_name(base_name)


if __name__ == "__main__":
	main()
