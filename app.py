from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


st.set_page_config(
    page_title="CSV Explorer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp { background: #f5f7fb; }
    [data-testid="stHeader"] { background: rgba(245,247,251,.85); }
    .block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1440px; }
    [data-testid="stMetric"] { background: white; border: 1px solid #e8edf5; padding: 18px 20px; border-radius: 14px; }
    [data-testid="stMetricLabel"] { color: #65728a; }
    .hero { padding: 1rem 0 1.2rem; }
    .eyebrow { color: #5266d8; text-transform: uppercase; letter-spacing: .12em; font-size: .72rem; font-weight: 700; }
    .subtle { color: #68758a; }
    </style>
    """,
    unsafe_allow_html=True,
)


def read_csv_robustly(uploaded_file: Any) -> tuple[pd.DataFrame, str, str]:
    """Try common encodings and let pandas infer a delimiter when possible."""
    raw = uploaded_file.getvalue()
    attempts: list[str] = []
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
        try:
            frame = pd.read_csv(
                BytesIO(raw),
                encoding=encoding,
                sep=None,
                engine="python",
                on_bad_lines="warn",
            )
            return frame, encoding, "Delimiter detected automatically"
        except (UnicodeDecodeError, pd.errors.ParserError, ValueError) as exc:
            attempts.append(f"{encoding}: {exc}")

    # Last fallback: replacement characters keep mostly-readable data available.
    text = raw.decode("utf-8", errors="replace")
    frame = pd.read_csv(BytesIO(text.encode("utf-8")), sep=None, engine="python", on_bad_lines="skip")
    return frame, "utf-8 with replacement", "Some malformed rows may have been skipped"


def find_date_columns(frame: pd.DataFrame) -> dict[str, pd.Series]:
    found: dict[str, pd.Series] = {}
    for name in frame.columns:
        series = frame[name]
        name_hint = any(word in str(name).lower() for word in ("date", "time", "year", "month"))
        if pd.api.types.is_datetime64_any_dtype(series):
            parsed = pd.to_datetime(series, errors="coerce", utc=True)
        elif series.dtype == "object" or pd.api.types.is_string_dtype(series):
            # Avoid treating arbitrary labels and numeric IDs as dates.
            if not name_hint and not series.dropna().astype(str).str.contains(r"[-/:T]", regex=True).mean() > 0.5:
                continue
            parsed = pd.to_datetime(series, errors="coerce", utc=True)
        else:
            continue
        valid_ratio = parsed.notna().mean() if len(series) else 0
        if valid_ratio >= 0.65 and parsed.notna().sum() >= 2:
            found[str(name)] = parsed
    return found


def infer_numeric_columns(frame: pd.DataFrame, date_names: set[str]) -> tuple[list[str], pd.DataFrame]:
    """Include columns containing mostly numeric text, such as "1,234" or "$42.50"."""
    converted = pd.DataFrame(index=frame.index)
    numeric_names: list[str] = []
    for name in frame.columns:
        if str(name) in date_names:
            continue
        source = frame[name]
        if pd.api.types.is_numeric_dtype(source):
            numeric = pd.to_numeric(source, errors="coerce")
        else:
            cleaned = source.astype("string").str.strip()
            cleaned = cleaned.str.replace(r"[$€£¥,%]", "", regex=True).str.replace(",", "", regex=False)
            cleaned = cleaned.str.replace(r"^\((.*)\)$", r"-\1", regex=True)
            numeric = pd.to_numeric(cleaned, errors="coerce")
            present_count = int(source.notna().sum())
            if present_count == 0 or numeric.notna().sum() / present_count < 0.8:
                continue
        if numeric.notna().sum() >= 2:
            numeric_names.append(str(name))
            converted[str(name)] = numeric
    return numeric_names, converted


def quality_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name in frame.columns:
        values = frame[name]
        missing = int(values.isna().sum())
        unique = int(values.nunique(dropna=True))
        rows.append(
            {
                "Column": str(name),
                "Type": str(values.dtype),
                "Missing": missing,
                "Missing %": round(missing / max(len(frame), 1) * 100, 1),
                "Unique": unique,
                "Unique %": round(unique / max(values.notna().sum(), 1) * 100, 1),
            }
        )
    return pd.DataFrame(rows)


def metric(label: str, value: str | int, help_text: str | None = None) -> None:
    st.metric(label, value, help=help_text)


st.sidebar.markdown("## 📊 CSV Explorer")
st.sidebar.caption("A quick, friendly look at your data")
uploaded = st.sidebar.file_uploader("Upload a CSV file", type=["csv", "txt"], help="CSV files with common encodings and delimiters are supported.")
st.sidebar.markdown("---")
st.sidebar.caption("Your file is analyzed in this session and is not saved by this app.")

st.markdown('<div class="hero"><div class="eyebrow">Data workspace</div><h1 style="margin:.35rem 0">Explore your CSV</h1><div class="subtle">Upload a file to get an instant overview, quality checks, and useful charts.</div></div>', unsafe_allow_html=True)

if uploaded is None:
    st.info("Choose a CSV file in the sidebar to get started.")
    st.markdown("#### What you’ll find inside")
    st.markdown("Overview and preview · Data quality checks · Numeric distributions and relationships · Category breakdowns · Time trends")
    st.stop()

try:
    df, encoding_used, parse_note = read_csv_robustly(uploaded)
except Exception as exc:
    st.error(f"This file could not be read as a CSV. Details: {exc}")
    st.stop()

if df.empty and len(df.columns) == 0:
    st.warning("The uploaded file appears to be empty or has no readable columns.")
    st.stop()

# Clean up duplicate/blank headers without changing the displayed values.
new_columns = []
seen: dict[str, int] = {}
for i, col in enumerate(df.columns):
    label = str(col).strip() or f"Unnamed column {i + 1}"
    seen[label] = seen.get(label, 0) + 1
    new_columns.append(label if seen[label] == 1 else f"{label} ({seen[label]})")
df.columns = new_columns

date_cols = find_date_columns(df)
numeric_cols, numeric_data = infer_numeric_columns(df, set(date_cols))
categorical_cols = [str(c) for c in df.columns if c not in numeric_cols and c not in date_cols]
missing_total = int(df.isna().sum().sum())
duplicate_rows = int(df.duplicated().sum())
quality = quality_summary(df)

st.caption(f"**{uploaded.name}** · {len(df):,} rows · {len(df.columns):,} columns · Read as {encoding_used} · {parse_note}")
overview_tab, quality_tab, numeric_tab, category_tab, time_tab, builder_tab = st.tabs(
    ["Overview", "Data quality", "Numeric", "Categories", "Time", "Chart builder"]
)

with overview_tab:
    c1, c2, c3, c4 = st.columns(4)
    with c1: metric("Rows", f"{len(df):,}")
    with c2: metric("Columns", f"{len(df.columns):,}")
    with c3: metric("Missing values", f"{missing_total:,}", f"Across the entire table ({missing_total / max(df.size, 1) * 100:.1f}% of cells)")
    with c4: metric("Duplicate rows", f"{duplicate_rows:,}")

    st.markdown("### Data preview")
    preview_rows = st.slider("Rows to show", min_value=5, max_value=50, value=min(10, max(5, len(df))), step=5)
    st.dataframe(df.head(preview_rows), use_container_width=True, hide_index=True)
    st.download_button("Download cleaned preview as CSV", df.head(preview_rows).to_csv(index=False).encode("utf-8-sig"), file_name="csv_preview.csv", mime="text/csv")

    st.markdown("### Column summary")
    st.dataframe(quality[["Column", "Type", "Missing", "Unique"]], use_container_width=True, hide_index=True)

    st.markdown("### Quick charts")
    quick_left, quick_right = st.columns(2)
    with quick_left:
        if numeric_cols:
            quick_num = st.selectbox("Numeric distribution", numeric_cols, key="overview_numeric")
            quick_values = numeric_data[quick_num].dropna()
            st.plotly_chart(px.histogram(x=quick_values, nbins=25, title=f"Distribution of {quick_num}", labels={"x": quick_num, "y": "Rows"}, color_discrete_sequence=["#5969df"]), use_container_width=True)
        else:
            st.caption("No numeric columns found for a distribution chart.")
    with quick_right:
        if categorical_cols:
            quick_cat = st.selectbox("Category breakdown", categorical_cols, key="overview_category")
            quick_counts = df[quick_cat].fillna("(Missing)").astype(str).value_counts().head(8).rename_axis("Value").reset_index(name="Count")
            st.plotly_chart(px.bar(quick_counts.sort_values("Count"), x="Count", y="Value", orientation="h", title=f"Common values in {quick_cat}", color="Count", color_continuous_scale="Purples"), use_container_width=True)
        else:
            st.caption("No category columns found for a breakdown chart.")

with quality_tab:
    st.markdown("### Where to look closer")
    q1, q2 = st.columns(2)
    with q1:
        st.metric("Cells with missing values", f"{missing_total:,}", f"{missing_total / max(df.size, 1) * 100:.1f}% of all cells")
    with q2:
        st.metric("Repeated rows", f"{duplicate_rows:,}", f"{duplicate_rows / max(len(df), 1) * 100:.1f}% of rows")
    if missing_total == 0 and duplicate_rows == 0:
        st.success("No missing cells or exact duplicate rows found.")
    st.markdown("#### Column-level checks")
    st.dataframe(quality.sort_values(["Missing", "Unique"], ascending=[False, True]), use_container_width=True, hide_index=True)
    missing_by_col = quality[quality["Missing"] > 0].sort_values("Missing", ascending=True)
    if not missing_by_col.empty:
        fig = px.bar(missing_by_col, x="Missing", y="Column", orientation="h", color="Missing %", color_continuous_scale="Blues", title="Missing values by column")
        fig.update_layout(margin=dict(l=0, r=0, t=50, b=0), height=max(300, 34 * len(missing_by_col)))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("There are no missing values to chart.")

    st.markdown("### Clean missing values")
    st.caption("Cleaning creates a downloadable copy. Your uploaded file stays unchanged.")
    if missing_total == 0:
        st.success("This file has no missing values to clean.")
    else:
        clean_method = st.selectbox(
            "How should missing values be handled?",
            [
                "Fill numeric with median; text with most common",
                "Fill numeric with mean; text with most common",
                "Remove rows that contain missing values",
                "Fill every missing value with a custom value",
            ],
            key="missing_clean_method",
        )
        fill_value = None
        if clean_method == "Fill every missing value with a custom value":
            fill_value = st.text_input("Value to use for missing cells", value="Unknown", key="missing_fill_value")

        cleaned_df = df.copy()
        if clean_method == "Remove rows that contain missing values":
            cleaned_df = cleaned_df.dropna().copy()
        elif clean_method == "Fill every missing value with a custom value":
            cleaned_df = cleaned_df.fillna(fill_value)
        else:
            fill_with_mean = clean_method.startswith("Fill numeric with mean")
            for column in cleaned_df.columns:
                if not cleaned_df[column].isna().any():
                    continue
                if column in numeric_data.columns:
                    numeric_values = numeric_data[column]
                    replacement = numeric_values.mean() if fill_with_mean else numeric_values.median()
                    if pd.api.types.is_numeric_dtype(cleaned_df[column]):
                        cleaned_df[column] = cleaned_df[column].fillna(replacement)
                    else:
                        # Keep the dtype of inferred numeric text columns (including Arrow strings).
                        cleaned_df[column] = cleaned_df[column].fillna(str(replacement))
                else:
                    modes = cleaned_df[column].mode(dropna=True)
                    replacement = modes.iloc[0] if not modes.empty else "Unknown"
                    cleaned_df[column] = cleaned_df[column].fillna(replacement)

        remaining_missing = int(cleaned_df.isna().sum().sum())
        before, after = st.columns(2)
        with before:
            st.metric("Rows before", f"{len(df):,}")
        with after:
            st.metric("Rows after", f"{len(cleaned_df):,}", f"{len(cleaned_df) - len(df):+,}")
        st.caption(f"Missing cells after cleaning: {remaining_missing:,}")
        st.dataframe(cleaned_df.head(10), use_container_width=True, hide_index=True)
        st.download_button(
            "Download cleaned CSV",
            cleaned_df.to_csv(index=False).encode("utf-8-sig"),
            file_name="cleaned_data.csv",
            mime="text/csv",
            key="download_cleaned_csv",
        )

with numeric_tab:
    st.markdown("### Numeric columns")
    if not numeric_cols:
        st.info("No numeric columns were detected. Numeric-looking text may need cleaning in the source file.")
    else:
        selected_num = st.selectbox("Choose a column", numeric_cols, key="numeric_column")
        values = numeric_data[selected_num].dropna()
        stats = values.describe()
        s1, s2, s3, s4, s5 = st.columns(5)
        with s1: metric("Values", f"{len(values):,}")
        with s2: metric("Mean", f"{stats.get('mean', float('nan')):,.3g}")
        with s3: metric("Median", f"{stats.get('50%', float('nan')):,.3g}")
        with s4: metric("Std. dev.", f"{stats.get('std', float('nan')):,.3g}")
        with s5: metric("Range", f"{stats.get('min', 0):,.3g} – {stats.get('max', 0):,.3g}")

        chart1, chart2 = st.columns(2)
        with chart1:
            st.plotly_chart(px.histogram(x=numeric_data[selected_num].dropna(), nbins=30, title=f"Distribution of {selected_num}", labels={"x": selected_num, "y": "Rows"}, color_discrete_sequence=["#5969df"]), use_container_width=True)
        with chart2:
            st.plotly_chart(px.box(y=numeric_data[selected_num].dropna(), points="outliers", title=f"Spread of {selected_num}", labels={"y": selected_num}, color_discrete_sequence=["#5969df"]), use_container_width=True)

        st.markdown("#### Values across rows")
        line_df = numeric_data[[selected_num]].copy().reset_index(names="Row")
        line_df["Row"] += 1
        st.plotly_chart(px.line(line_df, x="Row", y=selected_num, title=f"{selected_num} by row", color_discrete_sequence=["#5969df"]), use_container_width=True)

        if len(numeric_cols) >= 2:
            st.markdown("#### Correlation")
            corr = numeric_data[numeric_cols].corr(numeric_only=True)
            heat = px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu_r", zmin=-1, zmax=1, aspect="auto", title="Numeric column correlations")
            st.plotly_chart(heat, use_container_width=True)
            scat_a, scat_b = st.columns(2)
            with scat_a: x_col = st.selectbox("X axis", numeric_cols, index=0, key="scatter_x")
            with scat_b: y_col = st.selectbox("Y axis", numeric_cols, index=1 if len(numeric_cols) > 1 else 0, key="scatter_y")
            scatter_data = numeric_data[[x_col, y_col]].dropna()
            fig = px.scatter(scatter_data, x=x_col, y=y_col, trendline="ols", title=f"{y_col} vs {x_col}", color_discrete_sequence=["#5969df"], opacity=.7)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("Add another numeric column to see correlations and a scatter plot with trendline.")

with category_tab:
    st.markdown("### Common values")
    if not categorical_cols:
        st.info("No text or category columns were detected.")
    else:
        selected_cat = st.selectbox("Choose a column", categorical_cols, key="category_column")
        top_n = st.slider("Number of values to show", min_value=5, max_value=20, value=10, key="top_categories")
        counts = df[selected_cat].fillna("(Missing)").astype(str).value_counts().head(top_n).rename_axis("Value").reset_index(name="Count")
        fig = px.bar(counts.sort_values("Count"), x="Count", y="Value", orientation="h", title=f"Most common values in {selected_cat}", color="Count", color_continuous_scale="Purples")
        fig.update_layout(margin=dict(l=0, r=0, t=50, b=0), height=max(360, 34 * len(counts)))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(counts, use_container_width=True, hide_index=True)

with time_tab:
    st.markdown("### Trends over time")
    if not date_cols:
        st.info("No date-like columns were detected. Try using a column with recognizable dates such as 2025-04-30.")
    else:
        selected_date = st.selectbox("Date column", list(date_cols.keys()), key="date_column")
        usable_metrics = numeric_cols or ["Row count"]
        selected_metric = st.selectbox("Measure", usable_metrics, key="time_metric")
        time_frame = pd.DataFrame({"Date": date_cols[selected_date]})
        if selected_metric == "Row count":
            time_frame["Value"] = 1
        else:
            time_frame["Value"] = numeric_data[selected_metric]
        time_frame = time_frame.dropna(subset=["Date", "Value"]).sort_values("Date")
        if time_frame.empty:
            st.info("There are no usable date and measure pairs in this file.")
        else:
            period = st.selectbox("Group by", ["Day", "Week", "Month", "Year"], index=2)
            freq = {"Day": "D", "Week": "W", "Month": "MS", "Year": "YS"}[period]
            trend = time_frame.set_index("Date")["Value"].resample(freq).sum().reset_index()
            trend = trend[trend["Value"].notna()]
            fig = px.line(trend, x="Date", y="Value", markers=True, title=f"{selected_metric} by {period.lower()}", color_discrete_sequence=["#5969df"])
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Values are summed within each time period. Choose Row count to see the number of records per period.")

with builder_tab:
    st.markdown("### Build a chart")
    st.caption("Choose a chart type and the columns you want to compare.")
    chart_kind = st.selectbox("Chart type", ["Line", "Bar", "Pie", "Scatter", "Histogram", "Box"], key="builder_chart_type")

    column_names = [str(c) for c in df.columns]
    measure_options = ["Row count"] + numeric_cols
    aggregate_options = ["Sum", "Mean", "Median", "Count"]

    if chart_kind in ("Line", "Bar"):
        controls = st.columns(3)
        with controls[0]:
            x_name = st.selectbox("Group / X column", column_names, key="builder_xy_x")
        with controls[1]:
            measure_name = st.selectbox("Measure / Y", measure_options, key="builder_xy_y")
        with controls[2]:
            aggregation = st.selectbox("Aggregation", aggregate_options, index=0, key="builder_aggregation")

        if x_name in date_cols:
            x_values = date_cols[x_name]
        elif x_name in numeric_data.columns:
            x_values = numeric_data[x_name]
        else:
            x_values = df[x_name]
        chart_data = pd.DataFrame({"X": x_values})
        chart_data["Y"] = 1 if measure_name == "Row count" else numeric_data[measure_name]
        chart_data = chart_data.dropna(subset=["X", "Y"])
        agg_func = {"Sum": "sum", "Mean": "mean", "Median": "median", "Count": "count"}[aggregation]
        if measure_name == "Row count":
            grouped = chart_data.groupby("X", dropna=False)["Y"].count().reset_index()
        else:
            grouped = chart_data.groupby("X", dropna=False)["Y"].agg(agg_func).reset_index()
        grouped = grouped.sort_values("X")
        title = f"{aggregation} of {measure_name} by {x_name}"
        if chart_kind == "Line":
            builder_fig = px.line(grouped, x="X", y="Y", markers=True, title=title, labels={"X": x_name, "Y": measure_name}, color_discrete_sequence=["#5969df"])
        else:
            builder_fig = px.bar(grouped, x="X", y="Y", title=title, labels={"X": x_name, "Y": measure_name}, color_discrete_sequence=["#5969df"])
        if not grouped.empty:
            st.plotly_chart(builder_fig, use_container_width=True)
        else:
            st.info("There are no usable values for this chart selection.")

    elif chart_kind == "Pie":
        controls = st.columns(2)
        with controls[0]:
            label_name = st.selectbox("Labels", column_names, key="builder_pie_labels")
        with controls[1]:
            value_name = st.selectbox("Slice size", measure_options, key="builder_pie_values")
        pie_data = pd.DataFrame({"Label": df[label_name].fillna("(Missing)").astype(str)})
        pie_data["Value"] = 1 if value_name == "Row count" else numeric_data[value_name]
        pie_data = pie_data.dropna(subset=["Value"]).groupby("Label", as_index=False)["Value"].sum()
        pie_data = pie_data[pie_data["Value"] > 0].sort_values("Value", ascending=False).head(20)
        if not pie_data.empty:
            st.plotly_chart(px.pie(pie_data, names="Label", values="Value", title=f"{value_name} by {label_name}", hole=.35, color_discrete_sequence=px.colors.qualitative.Pastel), use_container_width=True)
            st.caption("Pie charts show up to the 20 largest groups.")
        else:
            st.info("There are no usable values for this chart selection.")

    elif chart_kind == "Scatter":
        if len(numeric_cols) < 2:
            st.info("A scatter plot needs at least two numeric columns. Check the Numeric tab to see which columns were detected.")
        else:
            controls = st.columns(2)
            with controls[0]:
                scatter_x = st.selectbox("X column", numeric_cols, key="builder_scatter_x")
            with controls[1]:
                scatter_y = st.selectbox("Y column", numeric_cols, index=1, key="builder_scatter_y")
            use_trend = st.checkbox("Show trendline", value=True, key="builder_trendline")
            scatter_frame = numeric_data[[scatter_x, scatter_y]].dropna()
            trendline_type = "ols" if use_trend and len(scatter_frame) >= 2 else None
            st.plotly_chart(px.scatter(scatter_frame, x=scatter_x, y=scatter_y, trendline=trendline_type, title=f"{scatter_y} vs {scatter_x}", opacity=.7, color_discrete_sequence=["#5969df"]), use_container_width=True)

    elif chart_kind == "Histogram":
        if not numeric_cols:
            st.info("No numeric columns were detected for a histogram.")
        else:
            hist_name = st.selectbox("Column", numeric_cols, key="builder_hist_column")
            bins = st.slider("Bins", min_value=5, max_value=80, value=30, key="builder_hist_bins")
            st.plotly_chart(px.histogram(x=numeric_data[hist_name].dropna(), nbins=bins, title=f"Distribution of {hist_name}", labels={"x": hist_name, "y": "Rows"}, color_discrete_sequence=["#5969df"]), use_container_width=True)

    else:  # Box plot
        if not numeric_cols:
            st.info("No numeric columns were detected for a box plot.")
        else:
            controls = st.columns(2)
            with controls[0]:
                box_name = st.selectbox("Numeric column", numeric_cols, key="builder_box_column")
            with controls[1]:
                group_options = ["No grouping"] + [name for name in column_names if name != box_name]
                group_name = st.selectbox("Group by (optional)", group_options, key="builder_box_group")
            box_frame = pd.DataFrame({box_name: numeric_data[box_name]})
            if group_name != "No grouping":
                box_frame[group_name] = df[group_name].fillna("(Missing)").astype(str)
            st.plotly_chart(px.box(box_frame, x=None if group_name == "No grouping" else group_name, y=box_name, color=None if group_name == "No grouping" else group_name, points="outliers", title=f"Spread of {box_name}", color_discrete_sequence=px.colors.qualitative.Pastel), use_container_width=True)
