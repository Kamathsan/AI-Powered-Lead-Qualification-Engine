# dashboard.py
import streamlit as st
import pandas as pd
import uuid
import plotly.express as px
from io import BytesIO
from scraper import scrape_jobs
from qualifier_engine import run_qualification

st.set_page_config(page_title="Game Lead Generator", layout="wide")

st.title("🎮 AI-Powered Game Lead Generator Dashboard")
st.markdown("Minimal • Fast • Interactive")

# Session
if "results" not in st.session_state:
    st.session_state.results = None
if "scraped_df" not in st.session_state:
    st.session_state.scraped_df = None
if "run_id" not in st.session_state:
    st.session_state.run_id = None

# Sidebar
st.sidebar.header("Scraping Settings")
keyword = st.sidebar.text_input("Job Keyword", value="unreal")
auto_all_pages = st.sidebar.checkbox("Scrape ALL pages", value=False)
max_pages = st.sidebar.number_input("Pages", min_value=1, max_value=50, value=1)
run_pipeline = st.sidebar.button("🚀 Run Full Pipeline")

# Pipeline
if run_pipeline:
    st.session_state.run_id = uuid.uuid4().hex[:8]
    st.write(f"### RUN ID: `{st.session_state.run_id}`")

    with st.spinner("Scraping jobs…"):
        df_scraped = scrape_jobs(keyword, max_pages, auto_all_pages)
        if not isinstance(df_scraped, pd.DataFrame):
            df_scraped = pd.DataFrame(df_scraped)
        st.session_state.scraped_df = df_scraped

    st.success(f"Scraped **{len(df_scraped)} jobs**")

    # Qualification
    with st.spinner("Running Qualification Engine…"):
        st.session_state.process_bar = st.progress(0)
        st.session_state.process_text = st.empty()

        final_df = run_qualification(st.session_state.scraped_df)
        st.session_state.results = final_df
        st.success("Pipeline Completed")

# Display
if st.session_state.results is not None:
    df = st.session_state.results.copy()

    df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0)
    df["qualified_flag"] = df["decision"].str.lower().eq("qualified")

    df = df.sort_values(by=["qualified_flag", "score"], ascending=[False, False])
    df = df.drop(columns=["qualified_flag"]).reset_index(drop=True)

    st.subheader("📊 Final Ranked Results")

    display_cols = ["company", "title", "service_bucket", "decision", "score", "url"]
    df_display = df[display_cols].copy()

    # clickable URL
    def make_link(u):
        if not u:
            return ""
        safe = str(u).replace('"', "%22")
        return f'<a href="{safe}" target="_blank">open</a>'

    df_display["url"] = df_display["url"].apply(make_link)
    html = df_display.to_html(escape=False, index=False)
    st.markdown(html, unsafe_allow_html=True)

    # KPIs
    st.subheader("📈 Summary Metrics")
    total = len(df)
    qualified = (df["decision"] == "Qualified").sum()
    avg_score = round(df["score"].mean(), 2)

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Jobs", total)
    c2.metric("Qualified", qualified)
    c3.metric("Avg Score", avg_score)

    # PIE chart
    pie_df = pd.DataFrame({
        "Decision": ["Qualified", "Not Qualified"],
        "Count": [qualified, total - qualified]
    })
    st.plotly_chart(px.pie(pie_df, names="Decision", values="Count", hole=0.4), use_container_width=True)

    # BAR chart
    bucket_counts = df["service_bucket"].value_counts().reset_index()
    bucket_counts.columns = ["service_bucket", "count"]
    st.plotly_chart(px.bar(bucket_counts, x="service_bucket", y="count", text="count"), use_container_width=True)

    # Download
    buf = BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    st.download_button(
        "⬇ Download Excel",
        data=buf.getvalue(),
        file_name=f"output_{st.session_state.run_id}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("Run the pipeline from the sidebar.")
