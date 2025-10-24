import streamlit as st
from supabase import create_client, Client
import pandas as pd
import datetime

st.set_page_config(page_title="Progressive Overload (Cloud)", layout="wide")

# --- Connect to Supabase ---
import os
SUPABASE_URL = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Helper Functions ---
def convert_to_lb(weight, unit):
    return weight if unit == "lb" else weight * 2.20462

def e1rm(weight, reps):
    return round(weight * (1 + reps / 30.0), 1)

def get_user_data(user_id):
    res = supabase.table("workouts").select("*").eq("user_id", user_id).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

# --- Authentication ---
if "user" not in st.session_state:
    st.session_state.user = None

def signup(email, password):
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        if res.user:
            st.success("Account created! You can now log in.")
        else:
            st.warning("Signup failed.")
    except Exception as e:
        st.error(str(e))

def login(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if res.user:
            st.session_state.user = res.user
            st.experimental_rerun()
        else:
            st.error("Invalid credentials.")
    except Exception as e:
        st.error(str(e))

def logout():
    supabase.auth.sign_out()
    st.session_state.user = None
    st.experimental_rerun()

# --- Login Page ---
if not st.session_state.user:
    st.title("🏋️ Progressive Overload — Login / Signup")

    tab1, tab2 = st.tabs(["🔑 Login", "🆕 Sign Up"])

    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login"):
            login(email, password)

    with tab2:
        new_email = st.text_input("Email", key="signup_email")
        new_password = st.text_input("Password", type="password", key="signup_password")
        if st.button("Create Account"):
            signup(new_email, new_password)

    st.stop()

# --- Logged In View ---
st.sidebar.success(f"Logged in as: {st.session_state.user.email}")
if st.sidebar.button("Logout"):
    logout()

st.title("🏋️ Progressive Overload — Cloud Edition (Private)")

st.write("Connected to Supabase ✅")

# --- Log Workout ---
st.header("Log a Set")

date = st.date_input("Date", datetime.date.today())
exercise = st.text_input("Exercise")
weight = st.number_input("Weight", min_value=0.0, step=1.0)
unit = st.selectbox("Unit", ["lb", "kg"])
reps = st.number_input("Reps", min_value=1, step=1)
rpe = st.text_input("RPE (optional)")
notes = st.text_area("Notes (optional)")

if st.button("Log Set ✅"):
    weight_lb = convert_to_lb(weight, unit)
    supabase.table("workouts").insert({
        "user_id": st.session_state.user.id,
        "date": str(date),
        "exercise": exercise,
        "weight_lb": weight_lb,
        "reps": reps,
        "rpe": rpe,
        "notes": notes
    }).execute()
    st.success(f"Logged {exercise} — {weight_lb:.1f} lb x {reps} reps")
    st.experimental_rerun()

# --- Load Data ---
data = get_user_data(st.session_state.user.id)

if not data.empty:
    st.subheader("📈 Exercise Progress")
    selected_exercise = st.selectbox("Choose an exercise to view progress", data["exercise"].unique())
    df_ex = data[data["exercise"] == selected_exercise].sort_values("date")

    st.line_chart(df_ex, x="date", y="weight_lb")

    top_set = df_ex["weight_lb"].max()
    st.info(f"Your top set for {selected_exercise}: **{top_set} lb**")

    # --- AI Suggestion ---
    avg_reps = df_ex["reps"].mean()
    next_goal = round(top_set * 1.02, 1)
    st.write(f"💡 Suggestion: Next session, aim for **{next_goal} lb** x **{int(avg_reps)} reps**")

    # --- Delete Section ---
    st.subheader("🗑️ Delete Past Entries")
    delete_row = st.multiselect("Select rows to delete:", df_ex.index, format_func=lambda i: f"{df_ex.iloc[i]['date']} — {df_ex.iloc[i]['exercise']} ({df_ex.iloc[i]['weight_lb']} lb x {df_ex.iloc[i]['reps']} reps)")
    if st.button("Delete Selected"):
        for i in delete_row:
            row_id = df_ex.iloc[i]["id"]
            supabase.table("workouts").delete().eq("id", row_id).execute()
        st.success("Deleted selected entries.")
        st.experimental_rerun()
else:
    st.warning("No data yet — log your first workout above!")
