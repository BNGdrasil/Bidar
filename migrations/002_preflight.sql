-- Preflight audit for 002_align_role_and_superuser.sql
-- Author: bnbong
-- Date: 2026-09-18
-- Target: host PostgreSQL, database `bngdrasil`
--
-- READ ONLY. This file runs SELECT statements only and changes nothing.
-- Run it first, read the output, and only then apply 002:
--   sudo -u postgres psql -d bngdrasil -v ON_ERROR_STOP=1 \
--     -f migrations/002_preflight.sql
--
-- What to look for:
--   * Section 2 lists rows whose role and is_superuser disagree. 002 will
--     resolve each of them in favour of `role`, except for the legacy rows in
--     section 3 which are promoted instead. Confirm that is what you want
--     before running 002; there is no automatic rollback of the values.
--   * Section 5 must report at least one super admin candidate. If it reports
--     zero, create an account with the CLI before applying 002, otherwise no
--     one can reach the admin API afterwards.

\echo '=== 1. Current distribution ==='
SELECT role, is_superuser, is_active, COUNT(*) AS rows
FROM users
GROUP BY role, is_superuser, is_active
ORDER BY role NULLS FIRST, is_superuser, is_active;

\echo '=== 2. Rows where role and is_superuser disagree ==='
SELECT id, username, email, role, is_superuser, is_active
FROM users
WHERE COALESCE(is_superuser, FALSE) IS DISTINCT FROM (role = 'super_admin')
ORDER BY id;

\echo '=== 3. Legacy superusers that 002 will PROMOTE to super_admin ==='
-- Only rows that never received a role in 001.
SELECT id, username, email, role, is_superuser, is_active
FROM users
WHERE is_superuser = TRUE
  AND (role IS NULL OR role = '' OR role = 'user')
ORDER BY id;

\echo '=== 4. Rows where 002 will CLEAR is_superuser and keep the role ==='
-- role is trusted for these: a moderator or admin flagged as superuser is
-- treated as a flag that drifted, not as a demotion.
SELECT id, username, email, role, is_superuser, is_active
FROM users
WHERE is_superuser = TRUE
  AND role IN ('moderator', 'admin')
ORDER BY id;

\echo '=== 5. Active super admin candidates after 002 ==='
SELECT COUNT(*) AS active_super_admin_candidates
FROM users
WHERE COALESCE(is_active, FALSE) = TRUE
  AND (
        role = 'super_admin'
     OR (is_superuser = TRUE AND (role IS NULL OR role = '' OR role = 'user'))
  );

\echo '=== 6. NULL values that 002 will fill ==='
SELECT
    COUNT(*) FILTER (WHERE role IS NULL)         AS role_is_null,
    COUNT(*) FILTER (WHERE is_superuser IS NULL) AS is_superuser_is_null,
    COUNT(*) FILTER (WHERE is_active IS NULL)    AS is_active_is_null
FROM users;

\echo '=== 7. Roles outside the allowed set (would break the check constraint) ==='
SELECT id, username, role
FROM users
WHERE role IS NOT NULL
  AND role <> ''
  AND role NOT IN ('user', 'moderator', 'admin', 'super_admin')
ORDER BY id;
