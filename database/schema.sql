-- ==============================================================================
-- SmartCCTV Database Schema (Supabase PostgreSQL)
-- ==============================================================================

-- Enable vector extension for facial embeddings (FaceNet 128-dimensional vectors)
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Students Table
CREATE TABLE IF NOT EXISTS students (
    id BIGSERIAL PRIMARY KEY,
    student_id TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    section TEXT,
    grade_level TEXT,
    photo_url TEXT,
    face_storage_path TEXT,
    has_face BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE students ADD COLUMN IF NOT EXISTS face_storage_path TEXT;

-- Private bucket for cropped enrollment face images. The backend service key uploads to it.
INSERT INTO storage.buckets (id, name, public)
VALUES ('face-enrollments', 'face-enrollments', FALSE)
ON CONFLICT (id) DO NOTHING;

-- 2. Face Embeddings Table (128-dim vectors from FaceNet)
CREATE TABLE IF NOT EXISTS face_embeddings (
    id BIGSERIAL PRIMARY KEY,
    student_id BIGINT REFERENCES students(id) ON DELETE CASCADE,
    embedding vector(128),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Attendance Table
CREATE TABLE IF NOT EXISTS attendance (
    id BIGSERIAL PRIMARY KEY,
    student_id BIGINT REFERENCES students(id) ON DELETE CASCADE,
    class_date DATE NOT NULL,
    check_in_time TIMESTAMPTZ,
    status TEXT DEFAULT 'present' CHECK (status IN ('present', 'absent', 'late')),
    confidence FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(student_id, class_date)
);

-- 4. Alerts Table (Weapon detections, trespassers, unknown faces)
CREATE TABLE IF NOT EXISTS alerts (
    id BIGSERIAL PRIMARY KEY,
    type TEXT NOT NULL,
    student_id BIGINT REFERENCES students(id) ON DELETE SET NULL,
    image_url TEXT,
    description TEXT NOT NULL,
    severity TEXT DEFAULT 'medium' CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    is_resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Compliance Violations Table
CREATE TABLE IF NOT EXISTS compliance_violations (
    id BIGSERIAL PRIMARY KEY,
    student_id BIGINT REFERENCES students(id) ON DELETE SET NULL,
    violation_type TEXT,
    image_url TEXT,
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indices for performance
CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(class_date);
CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance(student_id);
CREATE INDEX IF NOT EXISTS idx_alerts_unresolved ON alerts(is_resolved) WHERE is_resolved = FALSE;
CREATE INDEX IF NOT EXISTS idx_students_student_id ON students(student_id);

-- Enable Supabase Realtime for attendance and alerts
ALTER PUBLICATION supabase_realtime ADD TABLE attendance;
ALTER PUBLICATION supabase_realtime ADD TABLE alerts;
