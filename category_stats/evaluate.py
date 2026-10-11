"""compare the output csv files with the manual labels: python category_stats/evaluate.py [files]"""
import csv
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import config  # noqa: E402

CATEGORIES = ["Simple banner", "Static banner", "Fixed banner", "Blocking banner"]
MANUAL_LABELS = {
    "simple non blocking banner": "Simple banner",
    "static non blocking banner stays until action": "Static banner",
    "floating non blocking banner stays until action": "Fixed banner",
    "floating non blocking banner stays until action (close option given)": "Fixed banner",
    "blocking banner": "Blocking banner",
    "blocking banner with option to close": "Blocking banner",
    "no banner": "No banner",
}


def norm_domain(value):
    d = str(value).strip().lower()
    for prefix in ("https://", "http://"):
        if d.startswith(prefix):
            d = d[len(prefix):]
    if d.startswith("www."):
        d = d[4:]
    return d.rstrip("/")


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [row for row in csv.reader(f) if row]


def strip_prefix(value, prefix):
    return value[len(prefix):] if value.startswith(prefix) else value


def load(files):
    sites = []
    for name in files:
        manual_path = os.path.join(ROOT, "input-files", name)
        output_path = os.path.join(ROOT, name)
        if not os.path.exists(output_path):
            print("no BannerProbe output for %s (expected %s)" % (name, output_path))
            continue
        predicted = {}
        for row in read_rows(output_path):
            if len(row) < 3:
                continue
            reason = strip_prefix(row[10], "branch:") if len(row) > 10 else ""
            confidence = strip_prefix(row[11], "confidence:") if len(row) > 11 else ""
            predicted[norm_domain(row[0])] = (row[2].strip(), reason, confidence)
        for row in read_rows(manual_path):
            label = MANUAL_LABELS.get(row[1].strip().lower()) if len(row) > 1 else None
            if label is None:
                continue
            pred, reason, confidence = predicted.get(norm_domain(row[0]), ("Missing", "", ""))
            sites.append({"file": name, "domain": row[0].strip(), "manual": label, "probe": pred,
                          "reason": reason, "confidence": confidence})
    return sites


def pct(a, b):
    return "%5.1f%%" % (100.0 * a / b) if b else "    -"


def report(sites):
    print("\n== Per file")
    for name in sorted({s["file"] for s in sites}):
        fs = [s for s in sites if s["file"] == name]
        ok = sum(s["manual"] == s["probe"] for s in fs)
        print("  %-75s %4d sites  correct %4d  %s" % (name, len(fs), ok, pct(ok, len(fs))))

    cols = CATEGORIES + ["No banner", "Unreachable", "Undetermined", "Missing"]
    rows = CATEGORIES + ["No banner"]
    matrix = defaultdict(Counter)
    for s in sites:
        matrix[s["manual"]][s["probe"] if s["probe"] in cols else "Undetermined"] += 1
    print("\n== Confusion matrix (rows: manual label, columns: BannerProbe)")
    short = {c: c.replace(" banner", "") for c in cols}
    print("  %-16s" % "" + "".join("%13s" % short[c] for c in cols))
    for r in rows:
        if sum(matrix[r].values()):
            print("  %-16s" % short[r] + "".join("%13d" % matrix[r][c] for c in cols))

    detected = [s for s in sites if s["manual"] in CATEGORIES and s["probe"] in CATEGORIES]
    banner_sites = [s for s in sites if s["manual"] in CATEGORIES]
    print("\n== Banner categories, one-vs-rest (sites with a manual banner label that BannerProbe detected: %d)" % len(detected))
    print("  'Recall' is the column Table 3.2 calls 'Accuracy' (TP / (TP + FN)).")
    print("  %-16s %6s %6s %5s %5s %5s %5s %8s %9s %8s %8s" % (
        "", "Manual", "Probe", "TP", "FP", "FN", "TN", "Recall", "Precision", "F1", "OvR acc"))
    for c in CATEGORIES:
        tp = sum(s["manual"] == c and s["probe"] == c for s in detected)
        fp = sum(s["manual"] != c and s["probe"] == c for s in detected)
        fn = sum(s["manual"] == c and s["probe"] != c for s in detected)
        tn = len(detected) - tp - fp - fn
        print("  %-16s %6d %6d %5d %5d %5d %5d %8s %9s %8s %8s" % (
            c, tp + fn, tp + fp, tp, fp, fn, tn, pct(tp, tp + fn), pct(tp, tp + fp),
            pct(2 * tp, 2 * tp + fp + fn), pct(tp + tn, len(detected))))
    correct = sum(s["manual"] == s["probe"] for s in detected)
    print("\n  categorized correctly: %d / %d detected banners  %s" % (correct, len(detected), pct(correct, len(detected))))
    print("  categorized correctly: %d / %d manually labelled banners (missed/unreachable/undetermined count as wrong)  %s" % (
        correct, len(banner_sites), pct(correct, len(banner_sites))))

    print("\n== By BannerProbe confidence (detected banners)")
    for conf in ("high", "medium", "low", "none", ""):
        cs = [s for s in detected if s["confidence"] == conf]
        if cs:
            ok = sum(s["manual"] == s["probe"] for s in cs)
            print("  %-8s %4d sites  correct %s" % (conf or "(none)", len(cs), pct(ok, len(cs))))

    wrong = [s for s in sites if s["manual"] != s["probe"]]
    out = os.path.join(ROOT, "category_stats", "misclassified.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "domain", "manual", "bannerprobe", "confidence", "reason"])
        for s in sorted(wrong, key=lambda s: (s["manual"], s["probe"], s["domain"])):
            w.writerow([s["file"], s["domain"], s["manual"], s["probe"], s["confidence"], s["reason"]])
    print("\n%d misclassified or missed sites written to %s" % (len(wrong), out))


if __name__ == "__main__":
    report(load([os.path.basename(f) for f in sys.argv[1:]] or list(config.URLS_FILES)))
