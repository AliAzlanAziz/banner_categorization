import pandas as pd

base_path = "/home/mrstackoverflow/Desktop/study/masters_thesis/banner_categorization/"

# Read both CSV files
df1 = pd.read_csv(base_path + "input-files/blocking_banner.csv", header=None)
df2 = pd.read_csv(base_path + "blocking_banner.csv", header=None)

results = []

# Loop through first file
for _, row1 in df1.iterrows():
    val1 = str(row1.iloc[0])  # first column of file1

    # Find matches in df2 using .str.contains
    matches = df2[df2.iloc[:, 0].astype(str).str.contains(val1, na=False)]

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