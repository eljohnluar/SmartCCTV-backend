-- SmartCCTV starter data for Supabase PostgreSQL.
-- Run backend/database/schema.sql first, then run this file in the Supabase SQL Editor.
-- Replace the student values below with your real roster before using this in production.

BEGIN;

-- Student roster. `student_id` is the stable external/student-number value.
INSERT INTO students (student_id, full_name, section, grade_level, has_face)
VALUES
    ('STU-001', 'Maria Santos',     'Section A', 'Grade 10', FALSE),
    ('STU-002', 'Juan Dela Cruz',  'Section A', 'Grade 10', FALSE),
    ('STU-003', 'Ana Reyes',       'Section B', 'Grade 11', FALSE),
    ('STU-004', 'Carlos Mendoza',  'Section B', 'Grade 11', FALSE),
    ('STU-005', 'Elena Garcia',    'Section C', 'Grade 9',  FALSE),
    ('STU-006', 'Miguel Torres',   'Section C', 'Grade 9',  FALSE),
    ('STU-007', 'Sofia Ramos',     'Section A', 'Grade 10', FALSE),
    ('STU-008', 'Luis Bautista',   'Section D', 'Grade 12', FALSE)
ON CONFLICT (student_id) DO UPDATE
SET full_name = EXCLUDED.full_name,
    section = EXCLUDED.section,
    grade_level = EXCLUDED.grade_level,
    updated_at = NOW();

-- Today's attendance. The unique constraint on (student_id, class_date) makes
-- this safe to rerun: existing rows for today are updated instead of duplicated.
WITH attendance_seed (student_code, status, check_in_time, confidence) AS (
    VALUES
        ('STU-001', 'present', CURRENT_DATE + TIME '07:45:00', 0.97::FLOAT),
        ('STU-002', 'late',    CURRENT_DATE + TIME '08:31:00', 0.91::FLOAT),
        ('STU-004', 'present', CURRENT_DATE + TIME '07:50:00', 0.88::FLOAT),
        ('STU-006', 'present', CURRENT_DATE + TIME '07:55:00', 0.95::FLOAT),
        ('STU-007', 'present', CURRENT_DATE + TIME '07:40:00', 0.93::FLOAT),
        ('STU-008', 'late',    CURRENT_DATE + TIME '08:45:00', 0.84::FLOAT)
)
INSERT INTO attendance (student_id, class_date, status, check_in_time, confidence)
SELECT s.id, CURRENT_DATE, a.status, a.check_in_time, a.confidence
FROM attendance_seed AS a
JOIN students AS s ON s.student_id = a.student_code
ON CONFLICT (student_id, class_date) DO UPDATE
SET status = EXCLUDED.status,
    check_in_time = EXCLUDED.check_in_time,
    confidence = EXCLUDED.confidence;

-- Security-alert history. The WHERE NOT EXISTS clauses prevent duplicate rows
-- when this starter script is run more than once.
INSERT INTO alerts (type, description, severity, is_resolved, created_at)
SELECT 'weapon_detected', 'Potential weapon detected near Main Entrance', 'high', FALSE, NOW() - INTERVAL '5 minutes'
WHERE NOT EXISTS (
    SELECT 1 FROM alerts WHERE description = 'Potential weapon detected near Main Entrance'
);

INSERT INTO alerts (type, description, severity, is_resolved, created_at)
SELECT 'trespasser', 'Unidentified individual detected in Faculty Area', 'medium', FALSE, NOW() - INTERVAL '25 minutes'
WHERE NOT EXISTS (
    SELECT 1 FROM alerts WHERE description = 'Unidentified individual detected in Faculty Area'
);

INSERT INTO alerts (type, description, severity, is_resolved, created_at)
SELECT 'compliance_violation', 'Uniform dress code non-compliance detected', 'low', TRUE, NOW() - INTERVAL '90 minutes'
WHERE NOT EXISTS (
    SELECT 1 FROM alerts WHERE description = 'Uniform dress code non-compliance detected'
);

INSERT INTO alerts (type, description, severity, is_resolved, created_at)
SELECT 'unknown_face', 'Unrecognized student profile at Gate 2', 'low', TRUE, NOW() - INTERVAL '3 hours'
WHERE NOT EXISTS (
    SELECT 1 FROM alerts WHERE description = 'Unrecognized student profile at Gate 2'
);

COMMIT;
