// 1. Courses for a student
MATCH (s:Student {student_id: $student_id})-[:ENROLLED_IN]->(c:Course)
RETURN c.course_id, c.title;

// 2. Students in a course
MATCH (s:Student)-[:ENROLLED_IN]->(c:Course {course_id: $course_id})
RETURN s.student_id, s.name;

// 3. Students sharing a course
MATCH (s1:Student)-[:ENROLLED_IN]->(:Course {course_id: $course_id})<-[ :ENROLLED_IN ]-(s2:Student)
RETURN DISTINCT s2.student_id, s2.name;
