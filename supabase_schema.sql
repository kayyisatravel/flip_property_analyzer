-- Run this in Supabase SQL Editor to enable optional cross-session snapshot storage.
-- The application uses SUPABASE_SERVICE_ROLE_KEY server-side only. Never expose that key
-- in client code or publish it. Keep app access password-protected.

create table if not exists public.analyses (
  id bigint generated always as identity primary key,
  project_name text not null default 'Analisis tanpa nama',
  status text not null default 'HOLD',
  analysis_date timestamptz not null default now(),
  payload jsonb not null
);

alter table public.analyses enable row level security;

-- Intentionally no anon/authenticated policies are created here.
-- Server-side service role is used by this single-user app and bypasses RLS.
-- If your deployment needs multiple users, implement row-level ownership and authentication.
create index if not exists analyses_analysis_date_idx on public.analyses (analysis_date desc);
