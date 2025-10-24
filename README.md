
# Progressive Overload — Cloud (Supabase + Streamlit)

This is a deployable web app to track sets, visualize **Top Set (max lb per day)**, and get next-goal suggestions.
Data is stored in **Supabase** so it persists across deployments and is accessible from any device.

## Files
- `streamlit_app.py` — the app
- `requirements.txt` — Python deps
- `.env.example` — copy to `.env` and fill in your Supabase values
- `schema.sql` — create the `workouts` table in Supabase

## Setup (local)
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
cp .env.example .env
# edit .env with your SUPABASE_URL and SUPABASE_ANON_KEY
export $(grep -v '^#' .env | xargs)   # Windows: use setx or VS Code env file
# Create table in Supabase: paste SQL from schema.sql into Supabase SQL editor and run
streamlit run streamlit_app.py
```

## Deploy (Streamlit Cloud)
- Push this folder to GitHub.
- On Streamlit Cloud, set **Secrets** or **Environment Variables**:
  - `SUPABASE_URL`
  - `SUPABASE_ANON_KEY`
- Deploy and you’re done.

## Features
- Log any exercise with **kg/lb** input (stored & graphed as **lb**)
- Quick button: **Log same top set as last time** (with adjustable reps)
- Per-exercise chart + **AI-style suggestions**
- **PRs page**: lifetime heaviest set (lb) and best **e1RM**

## Notes
- e1RM uses the Epley formula: `weight * (1 + reps/30)`
- You can later enable Supabase Auth and add a `user_id` column to isolate users.
