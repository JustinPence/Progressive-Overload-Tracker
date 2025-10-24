
import os
from datetime import datetime, date
from typing import Optional

import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client, Client

LB_PER_KG = 2.2046226218

# -------------------- Supabase setup --------------------
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "").strip()

@st.cache_resource(show_spinner=False)
def get_sb() -> Optional[Client]:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return None
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

sb = get_sb()

def require_supabase():
    if sb is None:
        st.error("Supabase credentials not found. Set SUPABASE_URL and SUPABASE_ANON_KEY in your environment (see README).")
        st.stop()

# -------------------- Data access helpers --------------------
TABLE = "workouts"

def insert_set(date_s: str, exercise: str, weight_lb: float, reps: int, rpe: str = "", notes: str = ""):
    require_supabase()
    payload = {
        "date": date_s,
        "exercise": exercise.strip(),
        "weight_lb": float(weight_lb),
        "reps": int(reps),
        "rpe": (rpe or "").strip(),
        "notes": (notes or "").strip(),
    }
    sb.table(TABLE).insert(payload).execute()

def fetch_exercises() -> list[str]:
    require_supabase()
    res = sb.table(TABLE).select("exercise").execute()
    if not res.data:
        return []
    df = pd.DataFrame(res.data)
    if df.empty:
        return []
    return sorted(df["exercise"].dropna().astype(str).str.strip().unique().tolist())

def fetch_sets(exercise: Optional[str] = None) -> pd.DataFrame:
    require_supabase()
    q = sb.table(TABLE).select("*")
    if exercise:
        q = q.eq("exercise", exercise)
    q = q.order("date", desc=False).order("created_at", desc=False)
    res = q.execute()
    df = pd.DataFrame(res.data or [])
    if df.empty:
        return pd.DataFrame(columns=["date","exercise","weight_lb","reps","rpe","notes","created_at","id"])
    # Ensure dtypes
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.date
    if "weight_lb" in df.columns:
        df["weight_lb"] = pd.to_numeric(df["weight_lb"], errors="coerce")
    if "reps" in df.columns:
        df["reps"] = pd.to_numeric(df["reps"], errors="coerce").astype("Int64")
    return df

# -------------------- Logic --------------------
def compute_topsets_by_day(df_ex: pd.DataFrame) -> pd.DataFrame:
    if df_ex.empty:
        return pd.DataFrame(columns=["date","top_weight_lb"])
    d = (df_ex.groupby("date", as_index=False)
                 .agg(top_weight_lb=("weight_lb","max"))).sort_values("date")
    return d

def get_last_topset(df_ex: pd.DataFrame):
    """Return tuple (date, weight_lb, reps) for the last session's top set, or None."""
    if df_ex.empty:
        return None
    # latest date
    last_date = max(df_ex["date"])
    day = df_ex[df_ex["date"] == last_date].copy()
    if day.empty:
        return None
    max_w = day["weight_lb"].max()
    top = day[day["weight_lb"] == max_w].sort_values("created_at").iloc[-1]
    return (last_date, float(top["weight_lb"]), int(top["reps"]) if pd.notna(top["reps"]) else None)

def suggestion_next_goal(df_ex: pd.DataFrame) -> str:
    if df_ex.empty:
        return "Log a couple sessions first; I'll suggest targets once I see a trend."
    tops = compute_topsets_by_day(df_ex)
    if tops.empty:
        return "Log a couple sessions first; I'll suggest targets once I see a trend."
    if len(tops) == 1:
        w = tops["top_weight_lb"].iloc[-1]
        return f"Next time, try repeating {w:.0f} lb and add +1 rep if it felt manageable."
    last = tops["top_weight_lb"].tolist()[-3:]
    inc = sum(1 for i in range(1, len(last)) if last[i] > last[i-1])
    if inc >= 2:
        next_w = last[-1] + 5
        return f"Nice upward trend! Consider {next_w:.0f} lb for your top set; keep reps similar to last session."
    if len(set(round(x) for x in last)) == 1:
        return "You've plateaued at the same top weight. Try +2.5–5 lb OR keep weight and add +1–2 reps."
    if last[-1] < max(last):
        return f"Bit of a dip last time. Repeat ~{last[-1]:.0f} lb and aim +1–2 reps to regain momentum."
    return "Solid consistency. Try a small +2.5–5 lb increase or add +1 rep at the same top weight."

def epley_e1rm(weight_lb: float, reps: int) -> float:
    return float(weight_lb * (1 + (reps or 0) / 30))

# -------------------- UI --------------------
st.set_page_config(page_title="Progressive Overload (Cloud)", page_icon="🏋️", layout="wide")
st.title("🏋️ Progressive Overload — Cloud Edition")

if sb is None:
    st.warning("Add your Supabase credentials to run this app. See README for setup.")
else:
    st.success("Connected to Supabase")

with st.sidebar:
    st.header("Log a Set")
    date_val = st.date_input("Date", value=date.today())
    exercise = st.text_input("Exercise", placeholder="Bench Press")
    colw1, colw2 = st.columns([2,1])
    with colw1:
        weight_value = st.number_input("Weight value", min_value=0.0, step=1.0)
    with colw2:
        unit = st.selectbox("Unit", ["lb","kg"], index=0)
    reps = st.number_input("Reps", min_value=1, step=1)
    rpe = st.text_input("RPE (optional)", placeholder="e.g., 8 or 8.5")
    notes = st.text_area("Notes (optional)")
    if st.button("Log Set ✅", type="primary"):
        if not exercise or weight_value <= 0:
            st.error("Please enter exercise and a weight > 0.")
        else:
            weight_lb = float(weight_value) if unit == "lb" else float(weight_value) * LB_PER_KG
            insert_set(date_val.strftime("%Y-%m-%d"), exercise, weight_lb, int(reps), rpe, notes)
            st.success(f"Logged {exercise}: {weight_lb:.1f} lb x {int(reps)}")
            st.experimental_rerun()

tabs = st.tabs(["Dashboard", "Exercise Detail", "PRs"])

# -------- Dashboard --------
with tabs[0]:
    st.subheader("Overview")
    try:
        df_all = fetch_sets()
    except Exception as e:
        st.stop()
    if df_all.empty:
        st.info("No data yet — use the sidebar to log your first set.")
    else:
        c1,c2,c3 = st.columns(3)
        c1.metric("Total Sets", len(df_all))
        c2.metric("Exercises", df_all["exercise"].nunique())
        c3.metric("Last Logged", str(df_all["date"].max()))
        st.markdown("**Recent Entries**")
        st.dataframe(df_all.sort_values(["date","exercise"], ascending=[False, True]).tail(30), use_container_width=True)

# -------- Exercise Detail --------
# -------- Exercise Detail --------
with tabs[1]:
    st.subheader("Exercise Detail")
    exs = fetch_exercises()
    if not exs:
        st.info("Log data to see exercises.")
    else:
        ex = st.selectbox("Choose exercise", options=exs, key="ex_detail")
        dfe = fetch_sets(ex)
        if dfe.empty:
            st.info("No sets yet for this exercise.")
        else:
            # quick-log: same top set as last time
            last = get_last_topset(dfe)
            with st.expander("⚡ Quick Log: Same Top Set as Last Time"):
                if last is None:
                    st.write("No previous top set found for this exercise.")
                else:
                    last_date, last_w, last_reps = last
                    qcol1, qcol2, qcol3 = st.columns([2,1,1])
                    with qcol1:
                        st.write(f"Last top set on **{last_date}** — **{last_w:.0f} lb** x **{last_reps or '-'}**")
                    with qcol2:
                        new_reps = st.number_input("New reps", value=int(last_reps or 1), min_value=1, step=1, key="quick_reps")
                    with qcol3:
                        if st.button("Log Same Weight ▶️", key="quick_log_btn"):
                            insert_set(date.today().strftime("%Y-%m-%d"), ex, last_w, int(new_reps), "", f"Quick-log from last top set {last_date}")
                            st.success(f"Logged {ex}: {last_w:.0f} lb x {int(new_reps)}")
                            st.experimental_rerun()

            # --- NEW: Delete entries section ---
            with st.expander("🗑️ Delete Past Entries"):
                st.caption("Select one or more entries and click **Delete Selected** to permanently remove them from Supabase.")
                dfe_display = dfe.reset_index(drop=True)
                selected_rows = st.multiselect(
                    "Select rows to delete",
                    dfe_display.index,
                    format_func=lambda i: f"{dfe_display.loc[i, 'date']} — {dfe_display.loc[i, 'weight_lb']} lb x {dfe_display.loc[i, 'reps']} reps"
                )
                if st.button("Delete Selected ❌"):
                    if selected_rows:
                        ids_to_delete = [str(dfe_display.loc[i, 'id']) for i in selected_rows if 'id' in dfe_display.columns]
                        if ids_to_delete:
                            for id_ in ids_to_delete:
                                try:
                                    sb.table(TABLE).delete().eq("id", id_).execute()
                                except Exception as e:
                                    st.error(f"Error deleting entry {id_}: {e}")
                            st.success(f"Deleted {len(ids_to_delete)} record(s).")
                            st.experimental_rerun()
                        else:
                            st.warning("Could not find IDs for the selected rows.")
                    else:
                        st.info("No rows selected for deletion.")

            # chart: top set per day
            tops = compute_topsets_by_day(dfe)
            if tops.empty:
                st.info("Log sets to see the chart.")
            else:
                fig = plt.figure()
                plt.plot(pd.to_datetime(tops["date"]), tops["top_weight_lb"], marker="o")
                plt.title(f"Top Set (Max lb per day) — {ex}")
                plt.xlabel("Date")
                plt.ylabel("Weight (lb)")
                plt.tight_layout()
                st.pyplot(fig)

            # suggestion
            st.markdown("**Suggestion**")
            st.write(suggestion_next_goal(dfe))

            # all sets table
            st.markdown("**All Sets for This Exercise**")
            st.dataframe(dfe[["date","exercise","weight_lb","reps","rpe","notes"]], use_container_width=True)


            # chart: top set per day
            tops = compute_topsets_by_day(dfe)
            if tops.empty:
                st.info("Log sets to see the chart.")
            else:
                fig = plt.figure()
                plt.plot(pd.to_datetime(tops["date"]), tops["top_weight_lb"], marker="o")
                plt.title(f"Top Set (Max lb per day) — {ex}")
                plt.xlabel("Date")
                plt.ylabel("Weight (lb)")
                plt.tight_layout()
                st.pyplot(fig)

            # suggestion
            st.markdown("**Suggestion**")
            st.write(suggestion_next_goal(dfe))

            # all sets table
            st.markdown("**All Sets for This Exercise**")
            st.dataframe(dfe[["date","exercise","weight_lb","reps","rpe","notes"]], use_container_width=True)

# -------- PRs --------
with tabs[2]:
    st.subheader("Lifetime PRs")
    df_all = fetch_sets()
    if df_all.empty:
        st.info("No data yet.")
    else:
        # Best top weight per exercise (heaviest single set)
        pr_weight = (df_all.sort_values(["exercise","weight_lb","date"])
                           .groupby("exercise", as_index=False)
                           .agg(best_weight_lb=("weight_lb","max")))

        # Best estimated 1RM per exercise
        tmp = df_all.copy()
        tmp["e1rm"] = tmp.apply(lambda r: epley_e1rm(r["weight_lb"], int(r["reps"]) if pd.notna(r["reps"]) else 1), axis=1)
        pr_e1rm = (tmp.sort_values(["exercise","e1rm","date"])
                        .groupby("exercise", as_index=False)
                        .agg(best_e1rm=("e1rm","max")))

        prs = pr_weight.merge(pr_e1rm, on="exercise", how="outer")
        st.dataframe(prs.sort_values("exercise"), use_container_width=True)
