DO $$ BEGIN
 CREATE TYPE prototype.access_role AS ENUM ('manager','administrator','director');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
CREATE TABLE IF NOT EXISTS prototype.accounts (
 id BIGSERIAL PRIMARY KEY,
 employee_id BIGINT NOT NULL UNIQUE,
 username TEXT NOT NULL UNIQUE,
 password_hash TEXT NOT NULL,
 role prototype.access_role NOT NULL,
 active BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE IF NOT EXISTS prototype.sessions (
 token_hash TEXT PRIMARY KEY,
 account_id BIGINT NOT NULL,
 csrf_token TEXT NOT NULL,
 expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_account_idx ON prototype.sessions (account_id);
DO $$
DECLARE t TEXT;
BEGIN
 FOREACH t IN ARRAY ARRAY['clients','nomenclature','visits','contracts','sales','payments',
                         'stock','movements','provided_services','service_log'] LOOP
  EXECUTE format('ALTER TABLE prototype.%I ADD COLUMN IF NOT EXISTS owner_employee_id BIGINT', t);
  EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON prototype.%I (owner_employee_id)', t || '_owner_idx', t);
 END LOOP;
END $$;
