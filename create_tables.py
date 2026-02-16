import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# USERS TABLE
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT CHECK(role IN ('HR','CANDIDATE')) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

# JOBS TABLE
cursor.execute("""
CREATE TABLE IF NOT EXISTS jobs (
    job_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    location TEXT,
    experience INTEGER,
    salary INTEGER,
    hr_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (hr_id) REFERENCES users(user_id)
)
""")

# APPLICATIONS TABLE
cursor.execute("""
CREATE TABLE IF NOT EXISTS applications (
    application_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER,
    candidate_id INTEGER,
    status TEXT DEFAULT 'Applied',
    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id),
    FOREIGN KEY (candidate_id) REFERENCES users(user_id)
)
""")

conn.commit()
conn.close()

print("✅ Database tables created successfully")
