import os
import psycopg2


def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")
    return psycopg2.connect(database_url)


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # USERS TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id SERIAL PRIMARY KEY,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            phone TEXT,
            location TEXT,
            skills TEXT,
            experience_years INTEGER,
            resume_path TEXT,
            profile_completed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # JOBS TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT,
            job_type TEXT DEFAULT 'Full-time',
            experience_required TEXT,
            salary_range TEXT,
            skills_required TEXT,
            description TEXT,
            requirements TEXT,
            status TEXT DEFAULT 'Active',
            posted_by INTEGER REFERENCES users(user_id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # APPLICATIONS TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            application_id SERIAL PRIMARY KEY,
            job_id INTEGER NOT NULL REFERENCES jobs(job_id),
            candidate_id INTEGER NOT NULL REFERENCES users(user_id),
            status TEXT DEFAULT 'Applied',
            cover_letter TEXT,
            resume_path TEXT,
            score INTEGER DEFAULT 0,
            hr_notes TEXT,
            applied_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(job_id, candidate_id)
        );
    """)

    # ACTIVITY LOG TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            log_id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(user_id),
            action TEXT,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # SAVED JOBS TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS saved_jobs (
            save_id SERIAL PRIMARY KEY,
            candidate_id INTEGER NOT NULL REFERENCES users(user_id),
            job_id INTEGER NOT NULL REFERENCES jobs(job_id),
            saved_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(candidate_id, job_id)
        );
    """)

    # Insert sample jobs if empty
    cursor.execute("SELECT COUNT(*) FROM jobs;")
    jobs_count = cursor.fetchone()[0]

    if jobs_count == 0:
        sample_jobs = [
            ("Python Developer", "TechCorp", "Bangalore", "Full-time", "2-4 years",
             "₹8-12 LPA", "Python, Flask, Django, SQL",
             "Backend Python development with Flask/Django",
             "Strong Python skills, REST API experience", "Active"),
            ("Frontend Developer", "WebWorks", "Hyderabad", "Full-time", "1-3 years",
             "₹6-10 LPA", "React, JavaScript, CSS, Bootstrap",
             "React.js & Bootstrap development",
             "Modern JavaScript, responsive design", "Active"),
        ]

        cursor.executemany("""
            INSERT INTO jobs (
                title, company, location, job_type,
                experience_required, salary_range,
                skills_required, description,
                requirements, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, sample_jobs)

    conn.commit()
    cursor.close()
    conn.close()

    print("✅ PostgreSQL tables created successfully")


if __name__ == "__main__":
    init_db()

