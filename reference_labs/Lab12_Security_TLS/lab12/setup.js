// Lab 12.1 bootstrap (run with mongosh against a temporary no-auth mongod)
const adminPwd = process.env.ADMIN_PWD, readPwd = process.env.READ_PWD,
      writePwd = process.env.WRITE_PWD, hrPwd = process.env.HR_PWD;

const admin = db.getSiblingDB("admin");
const co = db.getSiblingDB("company");

// --- Admin user
admin.createUser({ user: "admin", pwd: adminPwd,
  roles: [{ role: "userAdminAnyDatabase", db: "admin" }, { role: "readWriteAnyDatabase", db: "admin" }] });

// --- Sample data
co.employees.insertMany([
  { name: "Asha",  dept: "Engineering", salary: 120000 },
  { name: "Ravi",  dept: "Finance",     salary: 95000 },
  { name: "Meera", dept: "HR",          salary: 88000 }
]);
co.projects.insertMany([{ title: "Alpha", status: "active" }, { title: "Beta", status: "planned" }]);

// --- Field-level redaction view (Activity 12.1): salary excluded
co.createView("employees_redacted", "employees", [{ $project: { salary: 0 } }]);

// --- Custom roles (least privilege, specific collections only)
admin.createRole({ role: "appReadRole", roles: [], privileges: [
  { resource: { db: "company", collection: "projects" },           actions: ["find"] },
  { resource: { db: "company", collection: "employees_redacted" }, actions: ["find"] } ] });
admin.createRole({ role: "appWriteRole", roles: [], privileges: [
  { resource: { db: "company", collection: "projects" }, actions: ["find", "insert", "update", "remove"] } ] });
admin.createRole({ role: "hrRole", roles: [], privileges: [
  { resource: { db: "company", collection: "employees" }, actions: ["find"] } ] });
// Example from the lab handout
admin.createRole({ role: "analyticsReader", roles: [], privileges: [
  { resource: { db: "analytics", collection: "" }, actions: ["find", "aggregate"] } ] });

// --- Users
admin.createUser({ user: "app_user_read",  pwd: readPwd,  roles: [{ role: "appReadRole",  db: "admin" }] });
admin.createUser({ user: "app_user_write", pwd: writePwd, roles: [{ role: "appWriteRole", db: "admin" }] });
admin.createUser({ user: "hr_user",        pwd: hrPwd,    roles: [{ role: "hrRole",        db: "admin" }] });
admin.createUser({ user: "analytics_app",  pwd: readPwd,  roles: [{ role: "analyticsReader", db: "admin" }] });
print("Bootstrap complete");
