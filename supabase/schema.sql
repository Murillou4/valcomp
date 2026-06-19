-- Supabase schema for the Ares Valorant mobile backend.
-- Run this in the Supabase SQL editor before deploying the FastAPI service.

create extension if not exists pgcrypto;

create table if not exists public.app_users (
  user_id uuid primary key default gen_random_uuid(),
  email text not null,
  password_hash text not null,
  display_name text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists app_users_email_lower_idx
  on public.app_users (lower(email));

create table if not exists public.diagnostic_events (
  event_id text primary key,
  user_id text,
  source text not null,
  level text not null default 'error',
  category text not null default 'general',
  message text not null,
  context jsonb not null default '{}'::jsonb,
  stack_trace text not null default '',
  request_id text not null default '',
  app_version text not null default '',
  device_id text not null default '',
  occurred_at timestamptz not null,
  created_at timestamptz not null default now()
);

create index if not exists diagnostic_events_user_time_idx
  on public.diagnostic_events(user_id, occurred_at desc);

create index if not exists diagnostic_events_source_time_idx
  on public.diagnostic_events(source, occurred_at desc);

create table if not exists public.companion_pair_codes (
  code_hash text primary key,
  user_id text not null,
  expires_at timestamptz not null,
  consumed_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.companion_devices (
  device_id text primary key,
  user_id text not null,
  device_name text not null,
  app_version text not null,
  protocol_version integer not null default 1,
  secret_hash text not null,
  active boolean not null default true,
  revoked_at timestamptz,
  last_seen_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.live_snapshots (
  user_id text primary key,
  device_id text not null,
  revision bigint not null default 0,
  phase text not null,
  state jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.live_commands (
  command_id text primary key,
  user_id text not null,
  device_id text not null,
  command text not null,
  payload jsonb not null default '{}'::jsonb,
  status text not null default 'queued',
  result jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  delivered_at timestamptz,
  completed_at timestamptz
);

create index if not exists companion_pair_codes_expires_idx
  on public.companion_pair_codes(expires_at);
create index if not exists companion_devices_user_active_idx
  on public.companion_devices(user_id, active);
create unique index if not exists companion_devices_one_active_idx
  on public.companion_devices(user_id) where active and revoked_at is null;
create index if not exists live_commands_delivery_idx
  on public.live_commands(user_id, device_id, status, expires_at);

create table if not exists public.profiles (
  user_id uuid primary key,
  display_name text not null default '',
  avatar_url text not null default '',
  preferences jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.riot_accounts (
  user_id uuid primary key,
  puuid text not null,
  game_name text not null default '',
  tag_line text not null default '',
  region text not null,
  shard text not null,
  client_version text not null default '',
  linked_at timestamptz not null default now()
);

create table if not exists public.riot_credentials (
  user_id uuid primary key,
  encrypted_payload text not null,
  last_refresh_at timestamptz,
  expires_hint timestamptz,
  updated_at timestamptz not null default now()
);

create table if not exists public.link_codes (
  link_code text primary key,
  user_id uuid not null,
  expires_at timestamptz not null,
  created_at timestamptz not null default now()
);

create table if not exists public.store_snapshots (
  user_id uuid primary key,
  payload jsonb not null,
  updated_at timestamptz not null default now()
);

create table if not exists public.item_cache (
  cache_key text primary key,
  category text not null,
  item_id text not null,
  payload jsonb not null,
  updated_at timestamptz not null default now()
);

create table if not exists public.push_devices (
  device_id text primary key,
  user_id uuid not null,
  push_token text not null,
  provider text not null default 'fcm',
  expo_push_token text,
  masked_token text not null default '',
  platform text not null default 'unknown',
  device_name text not null default '',
  app_version text not null default '',
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.push_devices add column if not exists push_token text;
alter table public.push_devices add column if not exists provider text not null default 'fcm';
alter table public.push_devices add column if not exists expo_push_token text;
update public.push_devices
set push_token = coalesce(nullif(push_token, ''), expo_push_token)
where push_token is null or push_token = '';
alter table public.push_devices alter column expo_push_token drop not null;
alter table public.push_devices alter column push_token set not null;

create table if not exists public.skin_watches (
  user_id uuid not null,
  item_id text not null,
  item_name text not null default '',
  display_icon text not null default '',
  tier text not null default '',
  notify_enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (user_id, item_id)
);

create table if not exists public.notification_deliveries (
  delivery_key text primary key,
  user_id uuid not null,
  item_id text not null,
  item_name text not null default '',
  source text not null default 'daily_store',
  store_expires_at timestamptz,
  status text not null default 'pending',
  ticket_ids jsonb not null default '[]'::jsonb,
  error text not null default '',
  sent_at timestamptz not null default now()
);

alter table public.profiles drop constraint if exists profiles_user_id_fkey;
alter table public.riot_accounts drop constraint if exists riot_accounts_user_id_fkey;
alter table public.riot_credentials drop constraint if exists riot_credentials_user_id_fkey;
alter table public.link_codes drop constraint if exists link_codes_user_id_fkey;
alter table public.store_snapshots drop constraint if exists store_snapshots_user_id_fkey;
alter table public.push_devices drop constraint if exists push_devices_user_id_fkey;
alter table public.skin_watches drop constraint if exists skin_watches_user_id_fkey;
alter table public.notification_deliveries
  drop constraint if exists notification_deliveries_user_id_fkey;

create index if not exists item_cache_category_item_id_idx
  on public.item_cache(category, item_id);

create index if not exists link_codes_expires_at_idx
  on public.link_codes(expires_at);

create index if not exists push_devices_user_enabled_idx
  on public.push_devices(user_id, enabled);

create index if not exists skin_watches_notify_idx
  on public.skin_watches(user_id, notify_enabled);

create index if not exists notification_deliveries_user_sent_idx
  on public.notification_deliveries(user_id, sent_at desc);

alter table public.profiles enable row level security;
alter table public.riot_accounts enable row level security;
alter table public.store_snapshots enable row level security;
alter table public.push_devices enable row level security;
alter table public.skin_watches enable row level security;
alter table public.notification_deliveries enable row level security;
alter table public.companion_pair_codes enable row level security;
alter table public.companion_devices enable row level security;
alter table public.live_snapshots enable row level security;
alter table public.live_commands enable row level security;

drop policy if exists "profiles are visible to owner" on public.profiles;
create policy "profiles are visible to owner"
  on public.profiles for select
  using (auth.uid() = user_id);

drop policy if exists "profiles are editable by owner" on public.profiles;
create policy "profiles are editable by owner"
  on public.profiles for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "riot accounts are visible to owner" on public.riot_accounts;
create policy "riot accounts are visible to owner"
  on public.riot_accounts for select
  using (auth.uid() = user_id);

drop policy if exists "store snapshots are visible to owner" on public.store_snapshots;
create policy "store snapshots are visible to owner"
  on public.store_snapshots for select
  using (auth.uid() = user_id);

drop policy if exists "push devices are visible to owner" on public.push_devices;
create policy "push devices are visible to owner"
  on public.push_devices for select
  using (auth.uid() = user_id);

drop policy if exists "push devices are editable by owner" on public.push_devices;
create policy "push devices are editable by owner"
  on public.push_devices for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "skin watches are visible to owner" on public.skin_watches;
create policy "skin watches are visible to owner"
  on public.skin_watches for select
  using (auth.uid() = user_id);

drop policy if exists "skin watches are editable by owner" on public.skin_watches;
create policy "skin watches are editable by owner"
  on public.skin_watches for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "notification deliveries are visible to owner" on public.notification_deliveries;
create policy "notification deliveries are visible to owner"
  on public.notification_deliveries for select
  using (auth.uid() = user_id);

insert into storage.buckets (id, name, public)
values ('avatars', 'avatars', true)
on conflict (id) do nothing;

drop policy if exists "avatar files are public" on storage.objects;
create policy "avatar files are public"
  on storage.objects for select
  using (bucket_id = 'avatars');

drop policy if exists "users upload their own avatars" on storage.objects;
create policy "users upload their own avatars"
  on storage.objects for insert
  with check (
    bucket_id = 'avatars'
    and auth.uid()::text = (storage.foldername(name))[1]
  );

drop policy if exists "users update their own avatars" on storage.objects;
create policy "users update their own avatars"
  on storage.objects for update
  using (
    bucket_id = 'avatars'
    and auth.uid()::text = (storage.foldername(name))[1]
  )
  with check (
    bucket_id = 'avatars'
    and auth.uid()::text = (storage.foldername(name))[1]
  );
