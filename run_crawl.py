"""
usage: python run_crawl.py [files] [--workers N] [--timeout S] [--headless] [--no-retry] [--reclassify]
"""
import argparse
import csv
import json
import multiprocessing
import os
import re
import shutil
import signal
import sys
import tempfile
import time
from datetime import datetime

import pandas as pd

import config

RETRYABLE = re.compile(r"^(timeout|worker exited|exception)")


def safe_name(domain):
    return re.sub(r"[^\w.\-]+", "_", domain).strip("_")[:120]


def read_domains(input_name):
    df = pd.read_csv(os.path.join("input-files", input_name), header=None, dtype=str)
    domains = [str(v).strip() for v in df.iloc[:, 0].tolist()]
    domains = [d for d in domains if d and d.lower() != "nan" and d.lower() != "domain"]
    return domains[config.START_POINT:config.START_POINT + config.STEP_SIZE]


def result_path(paths, index, domain):
    return os.path.join(paths["results_dir"], "%04d %s.json" % (index + 1, safe_name(domain)))


def load_result(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)
    os.replace(tmp, path)


def worker_entry(task):
    """one site in its own process"""
    os.setsid()  # own process group, so killpg also kills firefox
    log = open(task["log_path"], "a", buffering=1, encoding="utf-8")
    os.dup2(log.fileno(), 1)
    os.dup2(log.fileno(), 2)
    sys.stdout = sys.stderr = log
    os.environ["TMPDIR"] = task["tmpdir"]          # geckodriver creates the Firefox profile here
    tempfile.tempdir = task["tmpdir"]
    print("=== %s  %s (index %d)" % (datetime.now().isoformat(timespec="seconds"), task["domain"], task["index"]))

    import banner_detection
    banner_detection.HEADLESS = bool(task.get("headless"))
    result = banner_detection.run_site(task)
    write_json(task["result_path"], result)
    print("=== done: %s (%s)" % (result.get("category"), result.get("reason")))


def kill_group(pid):
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def csv_row(r, closing_scores):
    obs = r.get("observations") or {}
    sc = obs.get("scroll") or {}
    clicks = (obs.get("pointer") or {}).get("clicks") or []
    link = obs.get("link") or {}
    kb = obs.get("keyboard") or {}
    url = r.get("url") or ""
    final_url = r.get("final_url") or url
    keyboard = "escapes" if kb.get("escapes") else ("trapped" if kb.get("trapped") else ("-" if not kb else "unclear"))
    return [
        r["domain"], url, r.get("category"),
        closing_scores.get(r["domain"], "closing_score:Unknown"),
        "banner_closed:%s" % bool(r.get("closed_by")),
        "is_navigated:%s" % (link.get("result") == "navigated"),
        "is_scrolled:%s" % ((sc.get("scrolled_px") or 0) >= 60),
        "is_text_selected:N/A",
        "clicked:%s" % any(c.get("result") == "reached" for c in clicks),
        "url_changed:%s" % (url.rstrip("/") != final_url.rstrip("/")),
        "branch:%s" % r.get("reason", ""),
        "confidence:%s" % r.get("confidence", ""),
        "closed_by:%s" % (r.get("closed_by") or "-"),
        "scroll:%s" % sc.get("verdict", "-"),
        "reachable:%s" % (obs.get("hit") or {}).get("reachable"),
        "keyboard:%s" % keyboard,
        "kind:%s" % obs.get("kind", "-"),
        "secs:%s" % r.get("secs"),
    ]


def existing_closing_scores(output_csv):
    """keep scores written by update_closing_score.py"""
    scores = {}
    try:
        with open(output_csv, newline="", encoding="utf-8") as f:
            for row in csv.reader(f):
                if len(row) > 3 and row[3].startswith("closing_score:") and row[3] != "closing_score:Unknown":
                    scores[row[0]] = row[3]
    except OSError:
        pass
    return scores


def rebuild_csv(paths, domains):
    scores = existing_closing_scores(paths["output_csv"])
    rows = []
    for index, domain in enumerate(domains):
        r = load_result(result_path(paths, index, domain))
        if r:
            rows.append(csv_row(r, scores))
    with open(paths["output_csv"], "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)
    return len(rows)


def failure_result(task, reason):
    return {"domain": task["domain"], "index": task["index"], "input_file": task["urls_file"],
            "category": "Undetermined", "reason": reason, "confidence": "none",
            "secs": round(time.time() - task["started"], 1)}


def run_tasks(tasks, paths, args, progress):
    ctx = multiprocessing.get_context("spawn")
    queue, active = list(tasks), {}
    tmp_root = os.path.join(tempfile.gettempdir(), "bannerprobe")
    os.makedirs(tmp_root, exist_ok=True)
    try:
        while queue or active:
            while queue and len(active) < args.workers:
                index, domain = queue.pop(0)
                task = {
                    "index": index, "domain": domain, "urls_file": paths["input_name"],
                    "result_path": result_path(paths, index, domain),
                    "log_path": os.path.join(paths["site_logs_dir"], "%04d %s.log" % (index + 1, safe_name(domain))),
                    "tmpdir": tempfile.mkdtemp(prefix="w%d_" % index, dir=tmp_root),
                    "headless": args.headless, "budget": args.timeout - 30, "started": time.time(),
                }
                proc = ctx.Process(target=worker_entry, args=(task,))
                proc.start()
                active[proc.pid] = (proc, task)
                time.sleep(3)    # don't start browsers at the same moment (hidden windows on GNOME)
            time.sleep(0.5)
            for pid, (proc, task) in list(active.items()):
                elapsed = time.time() - task["started"]
                if proc.is_alive() and elapsed < args.timeout:
                    continue
                timed_out = proc.is_alive()
                kill_group(pid)          # kill leftover firefox
                proc.join(10)
                shutil.rmtree(task["tmpdir"], ignore_errors=True)
                del active[pid]
                result = load_result(task["result_path"])
                if result is None:
                    reason = ("timeout after %ds" % args.timeout) if timed_out else ("worker exited with code %s" % proc.exitcode)
                    result = failure_result(task, reason)
                    write_json(task["result_path"], result)
                progress(task, result)
    except KeyboardInterrupt:
        for pid, (proc, task) in active.items():
            kill_group(pid)
            shutil.rmtree(task["tmpdir"], ignore_errors=True)
        raise


def run_file(input_name, args):
    paths = config.output_paths(input_name)
    paths["input_name"] = input_name
    for d in (paths["results_dir"], paths["site_logs_dir"], paths["sc_dir"]):
        os.makedirs(d, exist_ok=True)
    domains = read_domains(input_name)
    pending = [(i, d) for i, d in enumerate(domains) if not os.path.exists(result_path(paths, i, d))]
    done_before = rebuild_csv(paths, domains)
    run_log = os.path.join(paths["data_dir"], "run.log")
    stats = {"done": 0, "start": time.time(), "total": len(pending)}

    def progress(task, result):
        stats["done"] += 1
        with open(paths["output_csv"], "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(csv_row(result, {}))
        rate = (time.time() - stats["start"]) / stats["done"]
        eta = rate * (stats["total"] - stats["done"])
        line = "[%s %d/%d, eta %dmin] %d %s -> %s | %s (%s, %ss)" % (
            input_name, stats["done"], stats["total"], eta // 60, task["index"] + 1, task["domain"],
            result.get("category"), result.get("reason"), result.get("confidence"), result.get("secs"))
        print(line, flush=True)
        with open(run_log, "a", encoding="utf-8") as f:
            print(datetime.now().isoformat(timespec="seconds") + " " + line, file=f)

    print("\n%s: %d sites, %d already done, %d to crawl with %d workers" % (
        input_name, len(domains), done_before, len(pending), args.workers), flush=True)
    run_tasks(pending, paths, args, progress)

    if args.retry:
        retry = []
        for i, d in enumerate(domains):
            r = load_result(result_path(paths, i, d))
            failed = r and r.get("category") == "Undetermined" and RETRYABLE.match(r.get("reason", ""))
            if failed or (r and r.get("window_hidden")):
                os.remove(result_path(paths, i, d))
                retry.append((i, d))
        if retry:
            print("%s: retrying %d sites that timed out, crashed or ran in a hidden window" % (input_name, len(retry)),
                  flush=True)
            stats.update(done=0, start=time.time(), total=len(retry))
            run_tasks(retry, paths, args, progress)

    n = rebuild_csv(paths, domains)
    print("%s: finished, %d rows in %s" % (input_name, n, paths["output_csv"]), flush=True)


def reclassify_file(input_name):
    """classify() again on the saved results"""
    import banner_probe
    paths = config.output_paths(input_name)
    domains = read_domains(input_name)
    changed = 0
    for index, domain in enumerate(domains):
        path = result_path(paths, index, domain)
        r = load_result(path)
        if not r or not r.get("observations"):
            continue
        category, reason, confidence = banner_probe.classify(r["observations"])
        if r.get("window_hidden"):
            reason += " [window hidden]"
            confidence = "low"
        if (category, reason, confidence) != (r.get("category"), r.get("reason"), r.get("confidence")):
            changed += 1
            print("%s: %s -> %s (%s)" % (domain, r.get("category"), category, reason), flush=True)
        r.update(category=category, reason=reason, confidence=confidence,
                 closed_by=banner_probe.closed_by(r["observations"]))
        write_json(path, r)
    n = rebuild_csv(paths, domains)
    print("%s: reclassified, %d results changed, %d rows in %s" % (input_name, changed, n, paths["output_csv"]), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="BannerProbe crawl: cookie banner categorization")
    parser.add_argument("files", nargs="*", help="input files inside input-files/ (default: config.URLS_FILES)")
    parser.add_argument("--workers", type=int, default=config.NUM_WORKERS)
    parser.add_argument("--timeout", type=int, default=config.SITE_TIMEOUT, help="seconds per site")
    parser.add_argument("--headless", dest="headless", action="store_true", default=config.HEADLESS)
    parser.add_argument("--headed", dest="headless", action="store_false",
                        help="visible windows (default)")
    parser.add_argument("--no-retry", dest="retry", action="store_false", default=config.RETRY_FAILED)
    parser.add_argument("--reclassify", action="store_true",
                        help="re-run classify() on saved results, no crawling")
    args = parser.parse_args(argv)
    os.chdir(os.path.dirname(os.path.abspath(__file__)))   # all paths (input-files/, *-datadir/) are relative
    files = [os.path.basename(f) for f in args.files] or list(config.URLS_FILES)
    for name in files:
        if not os.path.exists(os.path.join("input-files", name)):
            sys.exit("input file not found: input-files/" + name)
    started = time.time()
    for name in files:
        if args.reclassify:
            reclassify_file(name)
        else:
            run_file(name, args)
    print("\nall done in %.1f min" % ((time.time() - started) / 60), flush=True)


if __name__ == "__main__":
    main()
