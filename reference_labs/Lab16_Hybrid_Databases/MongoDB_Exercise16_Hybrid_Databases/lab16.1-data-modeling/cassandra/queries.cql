USE university;

-- 1. Courses belonging to a student
SELECT course_id, course_name FROM student_courses WHERE student_id = 'S1001';

-- 2. Students enrolled in a course
SELECT student_id, student_name FROM course_students WHERE course_id = 'CS101';

-- 3. Students sharing a course
SELECT student_id, student_name
FROM course_students
WHERE course_id = 'CS101';
