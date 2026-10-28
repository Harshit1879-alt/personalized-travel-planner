-- Optional starting schema for Supabase SQL Editor.
create table if not exists public.trips (
  id text primary key,
  created_at timestamptz not null default now(),
  destination text not null,
  start_date date,
  days integer not null default 3,
  budget numeric not null default 500,
  preferences jsonb not null default '{}'::jsonb,
  itinerary jsonb not null default '[]'::jsonb
);
alter table public.trips enable row level security;
-- Add user_id + authenticated policies before using this table with real users.
-- Never expose the service role key to the browser.
