CREATE CONSTRAINT student_id_unique IF NOT EXISTS FOR (s:Student) REQUIRE s.student_id IS UNIQUE;
CREATE CONSTRAINT course_id_unique IF NOT EXISTS FOR (c:Course) REQUIRE c.course_id IS UNIQUE;

CREATE (:Student {student_id: 'S1001', name: 'Ava Patel'})
CREATE (:Student {student_id: 'S1002', name: 'Liam Nguyen'})
CREATE (:Student {student_id: 'S1003', name: 'Maya Chen'})

CREATE (:Course {course_id: 'CS101', title: 'Intro to Computer Science'})
CREATE (:Course {course_id: 'MATH201', title: 'Discrete Mathematics'})
CREATE (:Course {course_id: 'BIO210', title: 'Cell Biology'})

MATCH (s:Student {student_id: 'S1001'}), (c:Course {course_id: 'CS101'}) MERGE (s)-[:ENROLLED_IN]->(c);
MATCH (s:Student {student_id: 'S1001'}), (c:Course {course_id: 'MATH201'}) MERGE (s)-[:ENROLLED_IN]->(c);
MATCH (s:Student {student_id: 'S1002'}), (c:Course {course_id: 'CS101'}) MERGE (s)-[:ENROLLED_IN]->(c);
MATCH (s:Student {student_id: 'S1002'}), (c:Course {course_id: 'BIO210'}) MERGE (s)-[:ENROLLED_IN]->(c);
MATCH (s:Student {student_id: 'S1003'}), (c:Course {course_id: 'MATH201'}) MERGE (s)-[:ENROLLED_IN]->(c);
MATCH (s:Student {student_id: 'S1003'}), (c:Course {course_id: 'BIO210'}) MERGE (s)-[:ENROLLED_IN]->(c);
