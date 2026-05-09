import pandas as pd

# ----------------------------
# Read input files
# ----------------------------

base_path = "/home/mrstackoverflow/Desktop/study/masters_thesis/bannerclick-block-vs-nonblocking-banners/"

# Read both CSV files
df1 = pd.read_csv(base_path + "bannerclick/input-files/retest_wrong.csv", header=None)
df2 = pd.read_csv(base_path + "banner_detection.csv", header=None)

results = []

# ----------------------------
# Matching logic (column 0)
# ----------------------------
for _, row1 in df1.iterrows():
    val1 = str(row1.iloc[0])

    matches = df2[df2.iloc[:, 0].astype(str).str.contains(val1, na=False, regex=False)]

    if not matches.empty:
        for _, row2 in matches.iterrows():
            results.append([
                val1,
                row1.iloc[1],
                row2.iloc[1]
            ])
    else:
        results.append([
            val1,
            row1.iloc[1],
            "NOT FOUND"
        ])

# ----------------------------
# Create output DataFrame
# ----------------------------
output = pd.DataFrame(results)

# Save result file
output.to_csv(base_path + "category_stats/generate_stats.csv", index=False)

# ----------------------------
# NORMALIZATION FUNCTION
# lowercase + first 2 words
# ----------------------------
def normalize(text):
    words = str(text).lower().split()
    return " ".join(words[:2])

# Apply normalization
col_file1 = output.iloc[:, 1].astype(str)
col_file2 = output.iloc[:, 2].astype(str)

norm1 = col_file1.apply(normalize)
norm2 = col_file2.apply(normalize)

# ----------------------------
# GLOBAL STATISTICS
# ----------------------------
total_rows = len(output)

not_found_mask = output.iloc[:, 2] == "NOT FOUND"
not_found_count = not_found_mask.sum()

# mismatches INCLUDING NOT FOUND
mismatch_including_nf = (norm1 != norm2).sum()

# mismatches EXCLUDING NOT FOUND
valid_mask = ~not_found_mask
mismatch_excluding_nf = (norm1[valid_mask] != norm2[valid_mask]).sum()

print("===== GLOBAL STATISTICS =====")
print(f"Total number of rows processed: {total_rows}")
print(f"Number of rows where NO MATCH was found in file2: {not_found_count}")
print(f"Number of mismatched categories (INCLUDING 'NOT FOUND' rows): {mismatch_including_nf}")
print(f"Number of mismatched categories (EXCLUDING 'NOT FOUND' rows): {mismatch_excluding_nf}")

# ----------------------------
# CATEGORY-LEVEL ANALYSIS
# ----------------------------
df_stats = pd.DataFrame({
    "cat_file1": norm1,
    "cat_file2": norm2,
    "is_not_found": not_found_mask,
    "is_mismatch": norm1 != norm2
})

# INCLUDING NOT FOUND
per_cat_including_nf = df_stats.groupby("cat_file1")["is_mismatch"].sum()

print("\n===== MISMATCH COUNT PER CATEGORY (INCLUDING 'NOT FOUND') =====")
print(per_cat_including_nf)

# EXCLUDING NOT FOUND
df_valid = df_stats[~df_stats["is_not_found"]]
per_cat_excluding_nf = df_valid.groupby("cat_file1")["is_mismatch"].sum()

print("\n===== MISMATCH COUNT PER CATEGORY (EXCLUDING 'NOT FOUND') =====")
print(per_cat_excluding_nf)

# ----------------------------
# DETAILED SUMMARY PER CATEGORY
# ----------------------------
per_cat_summary = df_stats.groupby("cat_file1").agg(
    total_rows=("cat_file1", "count"),
    mismatches_including_nf=("is_mismatch", "sum"),
    not_found=("is_not_found", "sum")
)

# add mismatches excluding NOT FOUND
per_cat_summary["mismatches_excluding_nf"] = (
    df_valid.groupby("cat_file1")["is_mismatch"].sum()
)

per_cat_summary = per_cat_summary.fillna(0)

print("\n===== DETAILED CATEGORY-LEVEL SUMMARY =====")
print(per_cat_summary)

# Optional: save stats
per_cat_summary.to_csv(base_path + "category_stats/category_summary.csv", header=None)