#!/usr/bin/env python3
"""Lab 12.1 - verify authentication, RBAC and field-level redaction (mongod --auth on :27017)."""
import os
from pymongo import MongoClient
from pymongo.errors import OperationFailure

H = "localhost:27017"
PW = {k: os.environ[k.upper() + "_PWD"] for k in ("admin", "read", "write", "hr")}
fails = 0


def cli(user, pwd):
    return MongoClient(f"mongodb://{user}:{pwd}@{H}/?authSource=admin", serverSelectionTimeoutMS=5000)


def expect(label, fn, allowed):
    global fails
    try:
        r = fn()
        ok = allowed
        print(f"[{'PASS' if ok else 'FAIL'}] {label}: allowed -> {r}")
    except OperationFailure as e:
        ok = not allowed
        print(f"[{'PASS' if ok else 'FAIL'}] {label}: denied ({e.details.get('codeName')})")
    fails += 0 if ok else 1


# Unauthenticated access must fail
anon = MongoClient(f"mongodb://{H}", serverSelectionTimeoutMS=5000)
expect("anonymous find company.projects", lambda: list(anon.company.projects.find()), False)

rd = cli("app_user_read", PW["read"]).company
wr = cli("app_user_write", PW["write"]).company
hr = cli("hr_user", PW["hr"]).company

print("\n-- app_user_read (find on projects + redacted view only)")
expect("read projects", lambda: rd.projects.count_documents({}), True)
expect("insert projects", lambda: rd.projects.insert_one({"title": "X"}).inserted_id, False)
expect("read employees directly", lambda: list(rd.employees.find()), False)
expect("read employees_redacted", lambda: list(rd.employees_redacted.find({}, {"_id": 0})), True)

print("\n-- app_user_write (find/insert/update/delete on projects only)")
expect("insert projects", lambda: wr.projects.insert_one({"title": "Gamma"}).acknowledged, True)
expect("update projects", lambda: wr.projects.update_one({"title": "Gamma"}, {"$set": {"status": "done"}}).modified_count, True)
expect("delete projects", lambda: wr.projects.delete_one({"title": "Gamma"}).deleted_count, True)
expect("read employees", lambda: list(wr.employees.find()), False)

print("\n-- Activity 12.1: salary redaction")
view_docs = list(rd.employees_redacted.find({}, {"_id": 0}))
assert all("salary" not in d for d in view_docs), "salary leaked through view!"
print("[PASS] view documents contain no salary field:", view_docs)
hr_docs = list(hr.employees.find({}, {"_id": 0}))
assert all("salary" in d for d in hr_docs)
print("[PASS] HR role sees salary on base collection:", hr_docs)

print("\nRESULT:", "ALL CHECKS PASSED" if fails == 0 else f"{fails} FAILED")
raise SystemExit(fails)
