-- Migration: Add role field to users table
-- Author: bnbong
-- Date: 2025-10-24
-- Description: Add role column to support RBAC (Role-Based Access Control)

-- Add role column with default value 'user'
ALTER TABLE users
ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'user';

-- Add check constraint for valid roles
ALTER TABLE users
ADD CONSTRAINT check_user_role
CHECK (role IN ('user', 'moderator', 'admin', 'super_admin'));

-- Create index on role for faster queries
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- Update existing users
-- If you have existing superusers, update them to 'super_admin'
UPDATE users
SET role = 'super_admin'
WHERE is_superuser = TRUE AND role = 'user';

-- Add comment
COMMENT ON COLUMN users.role IS 'User role for RBAC: user, moderator, admin, super_admin';
