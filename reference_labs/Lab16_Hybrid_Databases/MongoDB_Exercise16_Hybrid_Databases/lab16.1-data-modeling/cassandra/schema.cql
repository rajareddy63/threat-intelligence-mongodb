CREATE KEYSPACE IF NOT EXISTS university WITH REPLICATION = {'class': 'SimpleStrategy', 'replication_factor': 1};

USE university;

CREATE TABLE IF NOT EXISTS student_courses (
    student_id text,
    course_id text,
    course_name text,
    PRIMARY KEY (student_id, course_id)
);

CREATE TABLE IF NOT EXISTS course_students (
    course_id text,
    student_id text,
    student_name text,
    PRIMARY KEY (course_id, student_id)
);

INSERT INTO student_courses (student_id, course_id, course_name) VALUES ('S1001', 'CS101', 'Intro to Computer Science');
INSERT INTO student_courses (student_id, course_id, course_name) VALUES ('S1001', 'MATH201', 'Discrete Mathematics');
INSERT INTO student_courses (student_id, course_id, course_name) VALUES ('S1002', 'CS101', 'Intro to Computer Science');
INSERT INTO student_courses (student_id, course_id, course_name) VALUES ('S1002', 'BIO210', 'Cell Biology');
INSERT INTO student_courses (student_id, course_id, course_name) VALUES ('S1003', 'MATH201', 'Discrete Mathematics');
INSERT INTO student_courses (student_id, course_id, course_name) VALUES ('S1003', 'BIO210', 'Cell Biology');

INSERT INTO course_students (course_id, student_id, student_name) VALUES ('CS101', 'S1001', 'Ava Patel');
INSERT INTO course_students (course_id, student_id, student_name) VALUES ('CS101', 'S1002', 'Liam Nguyen');
INSERT INTO course_students (course_id, student_id, student_name) VALUES ('MATH201', 'S1001', 'Ava Patel');
INSERT INTO course_students (course_id, student_id, student_name) VALUES ('MATH201', 'S1003', 'Maya Chen');
INSERT INTO course_students (course_id, student_id, student_name) VALUES ('BIO210', 'S1002', 'Liam Nguyen');
INSERT INTO course_students (course_id, student_id, student_name) VALUES ('BIO210', 'S1003', 'Maya Chen');
