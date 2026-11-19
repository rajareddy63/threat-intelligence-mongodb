from pymongo import MongoClient

uri = "mongodb://localhost:27017"
client = MongoClient(uri)
db = client["university"]
students = db["students"]
courses = db["courses"]

students.delete_many({})
courses.delete_many({})

course_docs = [
    {"course_id": "CS101", "title": "Intro to Computer Science", "credits": 3, "department": "CS"},
    {"course_id": "MATH201", "title": "Discrete Mathematics", "credits": 4, "department": "Math"},
    {"course_id": "BIO210", "title": "Cell Biology", "credits": 3, "department": "Biology"},
]

course_ids = []
for course in course_docs:
    courses.insert_one(course)
    course_ids.append(course["course_id"])

student_docs = [
    {"student_id": "S1001", "name": "Ava Patel", "major": "CS", "course_ids": ["CS101", "MATH201"]},
    {"student_id": "S1002", "name": "Liam Nguyen", "major": "CS", "course_ids": ["CS101", "BIO210"]},
    {"student_id": "S1003", "name": "Maya Chen", "major": "Math", "course_ids": ["MATH201", "BIO210"]},
]

for student in student_docs:
    students.insert_one(student)

for course in course_docs:
    roster = [s["student_id"] for s in student_docs if course["course_id"] in s["course_ids"]]
    courses.update_one({"course_id": course["course_id"]}, {"$set": {"student_roster": roster}})

print("MongoDB seed data loaded.")
