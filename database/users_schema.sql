-- ==============================================================================
-- SmartCCTV Users Authentication Schema (Supabase PostgreSQL)
-- Additional table: `users` (Role: Teacher only)
-- ==============================================================================

-- 1. Create the 'users' table
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'teacher' CHECK (role = 'teacher'),
    registration_code TEXT NOT NULL DEFAULT 'TEACHER2026',
    is_active BOOLEAN DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Performance Indices
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- 3. Row Level Security (RLS) Configuration
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Allow full access to Supabase service_role
DROP POLICY IF EXISTS "Service role full access on users" ON users;
CREATE POLICY "Service role full access on users"
    ON users
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Allow public and authenticated read access for login lookup
DROP POLICY IF EXISTS "Allow users read access" ON users;
CREATE POLICY "Allow users read access"
    ON users
    FOR SELECT
    TO anon, authenticated
    USING (true);

-- Allow new teacher registration only with valid TEACHER2026 clearance code
DROP POLICY IF EXISTS "Allow registration with teacher code" ON users;
CREATE POLICY "Allow registration with teacher code"
    ON users
    FOR INSERT
    TO anon, authenticated
    WITH CHECK (role = 'teacher' AND registration_code = 'TEACHER2026');

-- Allow update of login timestamp and profile
DROP POLICY IF EXISTS "Allow users update" ON users;
CREATE POLICY "Allow users update"
    ON users
    FOR UPDATE
    TO anon, authenticated
    USING (true)
    WITH CHECK (role = 'teacher');

-- 4. Initial Default Teacher Seed Account
-- Username: teacher
-- Password: password123 (SHA-256 hash with 'smartcctv_salt_' salt)
INSERT INTO users (username, email, password_hash, full_name, role, registration_code)
VALUES (
    'teacher',
    'teacher@smartcctv.edu',
    '7159e84ba3e9b7b0df87feee43f9495493fa2666abdc606bf303f4de31b053fe',
    'Faculty Instructor',
    'teacher',
    'TEACHER2026'
)
ON CONFLICT (username) DO NOTHING;
