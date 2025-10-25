import streamlit as st
from supabase import create_client, Client
import pandas as pd
import datetime
import os
import openai

st.set_page_config(page_title="Progressive Overload Tracker", layout="wide")

# --- Connect to Supabase ---
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

# --- AI Suggestion Function ---
openai.api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")

def generate_ai_suggestion(exercise, data):
    recent = data[data["exercise"] == exercise].sort_values("date", ascending=False).head(5)
    if recent.empty:
        return "No data available for AI analysis yet."

    text_summary = "\n".join(
        f"{r['date']}: {r['weight_lb']} lb x {r['reps']} reps"
        for _, r in recent.iterrows()
    )

    prompt = f"""
    You are a strength training coach. Based on the following recent {exercise} logs:
    {text_summary}

    Suggest a specific next workout goal (weight and reps) and include a short motivational tip.
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"AI suggestion unavailable: {e}"

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

st.title("🏋️ Progressive Overload Tracker")

# --- Tabs for Logging & Progress ---
tab1, tab2 = st.tabs(["📋 Log Workout", "📈 Progress"])

# --- Tab 1: Log Workout ---
with tab1:
    st.header("Log a New Workout")

    date = st.date_input("Date", datetime.date.today())
    exercise = st.text_input("Exercise")
    weight = st.number_input("Weight", min_value=0.0, step=1.0)
    unit = st.selectbox("Unit", ["lb", "kg"])
    reps = st.number_input("Reps", min_value=1, step=1)
    rpe = st.text_input("RPE (optional)")
    notes = st.text_area("Notes (optional)")

    if st.button("Log Set ✅"):
        if not st.session_state.user:
            st.error("You must be logged in to log a set.")
            st.stop()

        exercise_name = exercise.strip().title()
        weight_lb = convert_to_lb(weight, unit)

        try:
            # Call the stored procedure. It returns no data if successful.
            supabase.rpc(
                "insert_workout",
                {
                    "_date": str(date),
                    "_exercise": exercise_name,
                    "_weight_lb": weight_lb,
                    "_reps": reps,
                    "_rpe": rpe,
                    "_notes": notes,
                },
            ).execute()

            # If no exception was raised, assume success
            st.success(f"✅ Logged {exercise_name}: {weight_lb:.1f} lb × {reps} reps")
            st.experimental_rerun()

        except Exception as e:
            # If the RPC call itself fails, show the exception
            st.error(f"❌ Failed to log set: {e}")


# --- Tab 2: Progress ---
with tab2:
    st.header("Your Progress")
    data = get_user_data(st.session_state.user.id)

    if data.empty:
        st.warning("No workouts logged yet! Log your first set in the 'Log Workout' tab.")
    else:
        import plotly.express as px

        selected_exercise = st.selectbox("Choose an exercise to view progress", data["exercise"].unique())
        df_ex = data[data["exercise"] == selected_exercise].sort_values("date")

        # --- Summary Cards ---
        total_sets = len(df_ex)
        heaviest = df_ex["weight_lb"].max()
        best_e1rm = df_ex.apply(lambda r: e1rm(r["weight_lb"], r["reps"]), axis=1).max()

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Sets Logged", total_sets)
        col2.metric("Heaviest Lift (lb)", round(heaviest, 1))
        col3.metric("Best e1RM (lb)", round(best_e1rm, 1))

        # --- Interactive Chart (Plotly) ---
        fig = px.line(
            df_ex,
            x="date",
            y="weight_lb",
            markers=True,
            title=f"{selected_exercise} Progress Over Time",
            labels={"weight_lb": "Weight (lb)", "date": "Date"},
        )
        fig.update_traces(mode="lines+markers", hovertemplate="%{x}: %{y} lb")
        fig.update_layout(hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

        # --- AI Suggestion ---
        if st.button("💡 Get AI Suggestion"):
            suggestion = generate_ai_suggestion(selected_exercise, data)
            st.info(suggestion)

        # --- Delete Section ---
        st.subheader("🗑️ Delete Past Entries")
        delete_row = st.multiselect(
            "Select rows to delete:",
            df_ex.index,
            format_func=lambda i: f"{df_ex.iloc[i]['date']} – ({df_ex.iloc[i]['weight_lb']} lb x {df_ex.iloc[i]['reps']} reps)"
        )

        if st.button("Delete Selected"):
            for i in delete_row:
                row_id = df_ex.iloc[i]["id"]
                supabase.table("workouts").delete().eq("id", row_id).execute()
            st.success("Deleted selected entries.")
            st.experimental_rerun()
