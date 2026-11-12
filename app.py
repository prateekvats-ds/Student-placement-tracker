from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Placement Tracker", page_icon="🎓", layout="wide")

DATA_FILE = Path(__file__).parent / "students.csv"
STATUSES = ["Placed", "In Process", "Not Placed"]
COLORS = {"Placed": "#2e9e6b", "In Process": "#f0a030", "Not Placed": "#d9534f"}


# ---------- data helpers ----------
def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_FILE)
    df["placement_date"] = pd.to_datetime(df["placement_date"], errors="coerce")
    for col in ["company", "role", "skills"]:
        df[col] = df[col].fillna("")
    return df


def save_data(df: pd.DataFrame) -> None:
    out = df.copy()
    out["placement_date"] = out["placement_date"].dt.strftime("%Y-%m-%d")
    out.to_csv(DATA_FILE, index=False)


def next_id(df: pd.DataFrame) -> str:
    nums = df["student_id"].str.extract(r"(\d+)")[0].astype(int)
    return f"S{(nums.max() if len(nums) else 0) + 1:03d}"


if not DATA_FILE.exists():
    st.error(f"`students.csv` : {DATA_FILE.parent}")
    st.stop()

df = load_data()

# ---------- sidebar filters ----------
st.sidebar.title("🎯 Filters")
branches = st.sidebar.multiselect("Branch", sorted(df["branch"].unique()), default=sorted(df["branch"].unique()))
batches = st.sidebar.multiselect("Batch", sorted(df["batch"].unique()), default=sorted(df["batch"].unique()))
statuses = st.sidebar.multiselect("Status", STATUSES, default=STATUSES)
cgpa_min, cgpa_max = float(df["cgpa"].min()), float(df["cgpa"].max())
cgpa_range = st.sidebar.slider("CGPA range", cgpa_min, cgpa_max, (cgpa_min, cgpa_max), step=0.1)

fdf = df[
    df["branch"].isin(branches)
    & df["batch"].isin(batches)
    & df["placement_status"].isin(statuses)
    & df["cgpa"].between(*cgpa_range)
]

# ---------- header + KPIs ----------
st.title("🎓 Student Placement Tracker")
st.caption("Placement stats, Track Student or Recuriter")

placed = fdf[fdf["placement_status"] == "Placed"]
total = len(fdf)
rate = (len(placed) / total * 100) if total else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Students", total)
k2.metric("Placed", len(placed))
k3.metric("Placement %", f"{rate:.1f}%")
k4.metric("Avg Package", f"{placed['package_lpa'].mean():.2f} LPA" if len(placed) else "–")
k5.metric("Highest Package", f"{placed['package_lpa'].max():.2f} LPA" if len(placed) else "–")

tab_over, tab_comp, tab_students, tab_manage = st.tabs(
    ["📊 Overview", "🏢 Companies", "👩‍🎓 Students", "✏️ Manage"]
)

# ---------- overview ----------
with tab_over:
    c1, c2 = st.columns(2)

    with c1:
        by_branch = (
            fdf.groupby("branch")["placement_status"]
            .apply(lambda s: (s == "Placed").mean() * 100)
            .reset_index(name="placement_pct")
            .sort_values("placement_pct", ascending=False)
        )
        fig = px.bar(by_branch, x="branch", y="placement_pct", text_auto=".1f",
                     title="Branch-wise Placement %", labels={"placement_pct": "Placement %"})
        fig.update_traces(marker_color="#2e9e6b")
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        fig = px.pie(fdf, names="placement_status", title="Status Split", hole=0.45,
                     color="placement_status", color_discrete_map=COLORS)
        st.plotly_chart(fig, use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        if len(placed):
            fig = px.histogram(placed, x="package_lpa", nbins=15, title="Package Distribution (LPA)")
            fig.update_traces(marker_color="#3b7dd8")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("There is no Placed student in selected folder")
    with c4:
        if len(placed):
            fig = px.scatter(placed, x="cgpa", y="package_lpa", color="branch",
                             hover_data=["name", "company"], title="CGPA vs Package")
            st.plotly_chart(fig, use_container_width=True)

    if placed["placement_date"].notna().any():
        trend = (
            placed.dropna(subset=["placement_date"])
            .assign(month=lambda d: d["placement_date"].dt.to_period("M").dt.to_timestamp())
            .groupby("month").size().reset_index(name="placements")
        )
        fig = px.line(trend, x="month", y="placements", markers=True, title="Placements Over Time")
        st.plotly_chart(fig, use_container_width=True)

# ---------- companies ----------
with tab_comp:
    if len(placed):
        comp = (
            placed.groupby("company")
            .agg(hires=("student_id", "count"), avg_package=("package_lpa", "mean"),
                 max_package=("package_lpa", "max"))
            .round(2).reset_index().sort_values("hires", ascending=False)
        )
        c1, c2 = st.columns(2)
        with c1:
            fig = px.bar(comp.head(10).sort_values("hires"), x="hires", y="company", orientation="h",
                         title="Top Recruiters (by hires)")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = px.bar(comp.sort_values("avg_package", ascending=False).head(10)
                         .sort_values("avg_package"),
                         x="avg_package", y="company", orientation="h",
                         title="Top Paying Companies (avg LPA)")
            fig.update_traces(marker_color="#f0a030")
            st.plotly_chart(fig, use_container_width=True)
        st.dataframe(comp, use_container_width=True, hide_index=True)
    else:
        st.info("No Placement Data.")

# ---------- students ----------
with tab_students:
    search = st.text_input("Search The Name Of Company Or Student")
    view = fdf
    if search:
        mask = (
            view["name"].str.contains(search, case=False, na=False)
            | view["company"].str.contains(search, case=False, na=False)
            | view["student_id"].str.contains(search, case=False, na=False)
        )
        view = view[mask]
    st.write(f"**{len(view)}** students")
    st.dataframe(
        view.assign(placement_date=view["placement_date"].dt.date),
        use_container_width=True, hide_index=True,
    )
    st.download_button("⬇️ Download filtered CSV", view.to_csv(index=False).encode("utf-8"),
                       file_name="filtered_students.csv", mime="text/csv")

# ---------- manage ----------
with tab_manage:
    left, right = st.columns(2)

    with left:
        st.subheader("Update Placement ")
        labels = df["student_id"] + " – " + df["name"]
        pick = st.selectbox("Student", labels)
        sid = pick.split(" – ")[0]
        row = df[df["student_id"] == sid].iloc[0]

        with st.form("update_form"):
            status = st.selectbox("Status", STATUSES, index=STATUSES.index(row["placement_status"]))
            company = st.text_input("Company", row["company"])
            role = st.text_input("Role", row["role"])
            pkg = st.number_input("Package (LPA)", min_value=0.0, step=0.1,
                                  value=float(row["package_lpa"]) if pd.notna(row["package_lpa"]) else 0.0)
            pdate = st.date_input("Placement date",
                                  value=row["placement_date"].date() if pd.notna(row["placement_date"])
                                  else pd.Timestamp.today().date())
            if st.form_submit_button("Save update"):
                idx = df.index[df["student_id"] == sid][0]
                if status == "Placed":
                    if not company.strip() or pkg <= 0:
                        st.error("Enter Company and Package")
                        st.stop()
                    df.loc[idx, ["placement_status", "company", "role", "package_lpa", "placement_date"]] = [
                        status, company.strip(), role.strip(), pkg, pd.Timestamp(pdate)]
                else:
                    df.loc[idx, ["placement_status", "company", "role", "package_lpa", "placement_date"]] = [
                        status, "", "", pd.NA, pd.NaT]
                save_data(df)
                st.success("Updated")
                st.rerun()

    with right:
        st.subheader("Add New Students")
        with st.form("add_form", clear_on_submit=True):
            name = st.text_input("Name")
            a1, a2 = st.columns(2)
            branch = a1.selectbox("Branch", sorted(df["branch"].unique()))
            batch = a2.number_input("Batch (passing year)", 2020, 2040, int(df["batch"].max()))
            b1, b2, b3 = st.columns(3)
            cgpa = b1.number_input("CGPA", 0.0, 10.0, 7.5, step=0.1)
            backlogs = b2.number_input("Backlogs", 0, 20, 0)
            interns = b3.number_input("Internships", 0, 10, 0)
            skills = st.text_input("Skills (comma separated)")
            if st.form_submit_button("Add student"):
                if not name.strip():
                    st.error("Enter Name")
                else:
                    new = pd.DataFrame([{
                        "student_id": next_id(df), "name": name.strip(), "branch": branch,
                        "batch": int(batch), "cgpa": cgpa, "backlogs": int(backlogs),
                        "internships": int(interns), "skills": skills.strip(),
                        "placement_status": "Not Placed", "company": "", "role": "",
                        "package_lpa": pd.NA, "placement_date": pd.NaT,
                    }])
                    save_data(pd.concat([df, new], ignore_index=True))
                    st.success("Student Added Successfully ")
                    st.rerun()
