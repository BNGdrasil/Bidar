-- Migration: Align role and is_superuser, harden the users table
-- Author: bnbong
-- Date: 2026-09-18
-- Target: host PostgreSQL, database `bngdrasil`
-- Run with:
--   sudo -u postgres psql -d bngdrasil -v ON_ERROR_STOP=1 \
--     -f migrations/002_align_role_and_superuser.sql
--
-- Idempotent: safe to run more than once.
--
-- Background (SEC-01): the application now treats `role` as the single source
-- of truth and derives `is_superuser` from it. Rows created by the former
-- public registration endpoint may carry an inconsistent pair, so this
-- migration reconciles them before the new code takes over.
--
-- Run migrations/002_preflight.sql FIRST and read its output. It reports
-- exactly which rows will be promoted, which will have is_superuser cleared,
-- and whether any active super admin will remain.

BEGIN;

-- 1. Backfill any NULL role left by 001 and enforce the default.
UPDATE users SET role = 'user' WHERE role IS NULL;

ALTER TABLE users ALTER COLUMN role SET DEFAULT 'user';
ALTER TABLE users ALTER COLUMN role SET NOT NULL;

-- 2. Promote only the legacy superusers that never received a role in 001.
--    A row whose role is already 'moderator' or 'admin' is NOT promoted:
--    the role is the deliberate value and the flag is what drifted.
DO $$
DECLARE
    promoted INTEGER;
    cleared INTEGER;
BEGIN
    UPDATE users
    SET role = 'super_admin'
    WHERE is_superuser = TRUE
      AND (role IS NULL OR role = '' OR role = 'user');
    GET DIAGNOSTICS promoted = ROW_COUNT;
    RAISE NOTICE 'Promoted % legacy superuser row(s) to super_admin.', promoted;

    SELECT COUNT(*) INTO cleared
    FROM users
    WHERE is_superuser = TRUE AND role IN ('moderator', 'admin');
    RAISE NOTICE
        'Clearing is_superuser on % row(s) whose role is moderator or admin; '
        'the role is kept as the source of truth.', cleared;
END
$$;

-- 3. Derive is_superuser from role so the two columns cannot disagree.
UPDATE users
SET is_superuser = (role = 'super_admin')
WHERE is_superuser IS DISTINCT FROM (role = 'super_admin');

ALTER TABLE users ALTER COLUMN is_superuser SET DEFAULT FALSE;
UPDATE users SET is_superuser = FALSE WHERE is_superuser IS NULL;
ALTER TABLE users ALTER COLUMN is_superuser SET NOT NULL;

-- 4. Make sure is_active is usable as an authorization input.
--    NULL becomes FALSE, not TRUE: the previous application treated a NULL
--    is_active as "not active" and refused those accounts, so FALSE keeps the
--    existing behaviour instead of silently enabling dormant rows.
DO $$
DECLARE
    disabled INTEGER;
BEGIN
    UPDATE users SET is_active = FALSE WHERE is_active IS NULL;
    GET DIAGNOSTICS disabled = ROW_COUNT;
    RAISE NOTICE
        'Set is_active = FALSE on % row(s) that were NULL (previous behaviour '
        'already refused them). Reactivate deliberately if needed.', disabled;
END
$$;
ALTER TABLE users ALTER COLUMN is_active SET DEFAULT TRUE;
ALTER TABLE users ALTER COLUMN is_active SET NOT NULL;

-- 5. Re-create the role check constraint idempotently. 001 added it without
--    IF NOT EXISTS, so a second run of 001 would fail here.
ALTER TABLE users DROP CONSTRAINT IF EXISTS check_user_role;
ALTER TABLE users
ADD CONSTRAINT check_user_role
CHECK (role IN ('user', 'moderator', 'admin', 'super_admin'));

-- 6. Keep the role index from 001 available.
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

COMMENT ON COLUMN users.role IS
    'User role for RBAC: user, moderator, admin, super_admin. Source of truth.';
COMMENT ON COLUMN users.is_superuser IS
    'Derived from role = super_admin. Kept for backwards compatibility.';

COMMIT;

-- Verification (run separately):
--   SELECT role, is_superuser, is_active, COUNT(*)
--   FROM users GROUP BY role, is_superuser, is_active ORDER BY role;
--   SELECT COUNT(*) AS active_super_admins FROM users
--   WHERE role = 'super_admin' AND is_active;
