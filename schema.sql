
-- Run this in Supabase SQL editor (or psql) to create the workouts table.
create table if not exists public.workouts (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  date date not null,
  exercise text not null,
  weight_lb numeric not null,
  reps integer not null,
  rpe text,
  notes text
);

-- Helpful index
create index if not exists idx_workouts_ex_date on public.workouts (exercise, date);
