# Lab 16.1 ? Data Modeling in Three Databases

This lab models the same university enrollment dataset in MongoDB, Cassandra, and Neo4j.

## MongoDB design

- `students` collection
- `courses` collection
- embedded `course_ids` array in each student document
- embedded `student_roster` array in each course document

## Cassandra design

- keyspace: `university`
- `student_courses`
- `course_students`

## Neo4j design

- `Student` nodes
- `Course` nodes
- `ENROLLED_IN` relationships
