# MongoDB Queries

## 1. Find all courses for a student

```python
student = db.students.find_one({"student_id": "S1001"}, {"course_ids": 1, "_id": 0})
print(student["course_ids"])
```

## 2. Find all students in a course

```python
course = db.courses.find_one({"course_id": "CS101"}, {"student_roster": 1, "_id": 0})
print(course["student_roster"])
```

## 3. Find students who share a course

```python
shared = db.students.aggregate([
    {"$match": {"course_ids": "CS101"}},
    {"$project": {"student_id": 1, "name": 1, "_id": 0}}
])
```
