create table if not exists analyses (
    id text primary key,
    parent_id text,
    version integer not null default 1,
    analysis_name text not null default 'Analise sem titulo',
    analysis_date text,
    responsible text not null default '',
    archived boolean not null default false,
    deleted_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    cep text,
    city text,
    uf text,
    main_carrier text,
    best_cost_carrier text,
    payload_json jsonb not null default '{}'::jsonb
);

create index if not exists analyses_active_created_idx on analyses (created_at desc) where deleted_at is null;
create index if not exists analyses_archived_idx on analyses (archived) where deleted_at is null;
create index if not exists analyses_cep_idx on analyses (cep) where deleted_at is null;
create index if not exists analyses_payload_gin_idx on analyses using gin (payload_json);

create table if not exists analysis_results (
    id uuid primary key default gen_random_uuid(),
    analysis_id text not null references analyses(id) on delete cascade,
    result_type text not null,
    payload_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists uploaded_files (
    id text primary key,
    purpose text not null,
    dataset_kind text,
    original_filename text not null,
    content_type text,
    size_bytes bigint,
    blob_pathname text not null,
    blob_url text,
    blob_download_url text,
    etag text,
    created_at timestamptz not null default now(),
    created_by text not null default 'admin_env'
);

create index if not exists uploaded_files_dataset_idx on uploaded_files (dataset_kind, created_at desc);

create table if not exists dataset_versions (
    id text primary key,
    kind text not null,
    version_label text not null,
    source_file_id text references uploaded_files(id),
    sqlite_file_id text references uploaded_files(id),
    row_count integer not null default 0,
    columns_json jsonb not null default '[]'::jsonb,
    rows_json jsonb not null default '[]'::jsonb,
    metadata_json jsonb not null default '{}'::jsonb,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    created_by text not null default 'admin_env'
);

create index if not exists dataset_versions_kind_status_idx on dataset_versions (kind, status, created_at desc);
create index if not exists dataset_versions_rows_gin_idx on dataset_versions using gin (rows_json);

create table if not exists dataset_active_versions (
    kind text primary key,
    dataset_version_id text not null references dataset_versions(id),
    updated_at timestamptz not null default now(),
    updated_by text not null default 'admin_env'
);

create table if not exists admin_audit_logs (
    id uuid primary key default gen_random_uuid(),
    action text not null,
    entity_type text not null,
    entity_id text,
    details_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    created_by text not null default 'admin_env',
    ip_address text
);

create index if not exists admin_audit_logs_entity_idx on admin_audit_logs (entity_type, entity_id, created_at desc);

create table if not exists app_settings (
    key text primary key,
    value_json jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now(),
    updated_by text not null default 'admin_env'
);
