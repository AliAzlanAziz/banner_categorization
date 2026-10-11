import pandas as pd

base_path = "/home/mrstackoverflow/Desktop/study/masters_thesis/banner_categorization/"

# Read both CSV files
df1 = pd.read_csv(base_path + "input-files/blocking_banner.csv", header=None)
df2 = pd.read_csv(base_path + "blocking_banner.csv", header=None)

results = []


def norm_domain(value):
    d = str(value).strip().lower()
    for prefix in ("https://", "http://"):
        if d.startswith(prefix):
            d = d[len(prefix):]
    if d.startswith("www."):
        d = d[4:]
    return d.rstrip("/")


df2_domains = df2.iloc[:, 0].map(norm_domain)

# Loop through first file
for _, row1 in df1.iterrows():
    val1 = str(row1.iloc[0])  # first column of file1

    # exact domain match
    matches = df2[df2_domains == norm_domain(val1)]

    if not matches.empty:
        for _, row2 in matches.iterrows():
            results.append([
                val1,
                row1.iloc[1].lower(),   # column1 from file1
                row2.iloc[2].lower()    # column1 from file2
            ])
    else:
        results.append([
            val1,
            row1.iloc[1].lower(),   # column1 from file1
            "NOT FOUND"
        ])

# Create output DataFrame
output = pd.DataFrame(results)
# output = pd.DataFrame(results, columns=["domain", "manual", "code"])

# Save to CSV
output.to_csv(base_path + "category_stats/results.csv", header=False, index=False)