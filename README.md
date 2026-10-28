# 📊 CSV Analyser

> **Upload a CSV. Understand your data. Find issues. Build charts.**

CSV Analyser is a simple web app for exploring CSV files. It gives you a quick overview of your data, helps spot common quality issues, and lets you create interactive charts or download a cleaned copy.

[🚀 Get started](#-get-started) · [✨ Features](#-features) · [🧰 Technology](#-technology) · [🗂️ Project files](#️-project-files)

---

## ⚡ At a glance

| 📋 Overview | 🧹 Data quality | 📈 Charts |
|---|---|---|
| Rows, columns, preview, and column summary | Missing values and duplicate rows | Numeric, category, time, and custom charts |

## ✨ Features

<details>
<summary>🔎 Explore your file</summary>

- Upload a `.csv` or `.txt` file
- Detect common encodings and delimiters automatically
- See row count, column count, missing values, and duplicate rows
- Preview the uploaded data and inspect column summaries

</details>

<details>
<summary>📊 Visualize your data</summary>

- **Numeric:** summary statistics, line chart, histogram, box plot, correlation heatmap, and scatter plot with trendline
- **Categories:** bar chart of the most common values
- **Time:** trends grouped by day, week, month, or year
- **Chart builder:** create line, bar, pie, scatter, histogram, or box charts using selected columns

</details>

<details>
<summary>🧹 Clean missing values</summary>

Choose how to handle missing cells:

- Fill numeric values with the **median** or **mean** and text values with the **most common** value
- Remove rows that contain missing values
- Fill missing cells with a custom value

Download the result as a separate CSV. Your original upload remains unchanged.

</details>

## 🧰 Technology

| Tool | What it does |
|---|---|
| 🐍 Python | Application logic |
| 🎈 Streamlit | Web interface |
| 🐼 pandas | Reading, summarizing, and cleaning data |
| 📊 Plotly | Interactive charts |
| 📉 statsmodels | Trendlines for scatter plots |

## 🚀 Get started

### Requirements

- Python 3.10 or later
- pip

### 1. Install dependencies

```bash
python -m pip install -r requirements.txt
```

On Windows, you can use:

```powershell
py -m pip install -r requirements.txt
```

### 2. Launch the app

```bash
python -m streamlit run app.py
```

On Windows, you can use:

```powershell
py -m streamlit run app.py
```

Open the local web address shown in the terminal. 🎉

## 🧭 How to use it

1. Start the app and upload a CSV file from the sidebar.
2. Check the **Overview** tab for a quick summary and preview.
3. Visit **Data quality** to review missing values and duplicates.
4. Explore **Numeric**, **Categories**, and **Time** views.
5. Use **Chart builder** to choose a chart and columns.
6. Download a cleaned copy if you changed how missing values should be handled.

## 🗂️ Project files

```text
.
├── app.py             # Streamlit application
├── requirements.txt   # Python dependencies
├── README.md          # Project guide
└── outputs/            # Project images and presentation assets
```

## ℹ️ Notes

- The app analyzes the uploaded file during the session and does not save it.
- Cleaning creates a separate download; it does not overwrite the uploaded file.
- If a file contains malformed rows, some rows may be skipped when it is read.

---

💡 **Tip:** For the best results, use a CSV with a header row and clear column names.
