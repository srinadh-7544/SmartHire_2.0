import sqlite3

DATABASE = "database.db"


def migrate_database():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    print("Starting database migration...")

    try:
        # Check and add missing columns to jobs table
        cursor.execute("PRAGMA table_info(jobs)")
        jobs_columns = [column[1] for column in cursor.fetchall()]

        if 'job_type' not in jobs_columns:
            cursor.execute("ALTER TABLE jobs ADD COLUMN job_type TEXT DEFAULT 'Full-time'")
            print("✓ Added job_type column to jobs table")

        if 'experience_required' not in jobs_columns:
            cursor.execute("ALTER TABLE jobs ADD COLUMN experience_required TEXT")
            print("✓ Added experience_required column to jobs table")

        if 'salary_range' not in jobs_columns:
            cursor.execute("ALTER TABLE jobs ADD COLUMN salary_range TEXT")
            print("✓ Added salary_range column to jobs table")

        if 'skills_required' not in jobs_columns:
            cursor.execute("ALTER TABLE jobs ADD COLUMN skills_required TEXT")
            print("✓ Added skills_required column to jobs table")

        if 'requirements' not in jobs_columns:
            cursor.execute("ALTER TABLE jobs ADD COLUMN requirements TEXT")
            print("✓ Added requirements column to jobs table")

        if 'status' not in jobs_columns:
            cursor.execute("ALTER TABLE jobs ADD COLUMN status TEXT DEFAULT 'Active'")
            print("✓ Added status column to jobs table")

        if 'created_at' not in jobs_columns:
            cursor.execute("ALTER TABLE jobs ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            print("✓ Added created_at column to jobs table")

        # Check and add missing columns to users table
        cursor.execute("PRAGMA table_info(users)")
        users_columns = [column[1] for column in cursor.fetchall()]

        if 'phone' not in users_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN phone TEXT")
            print("✓ Added phone column to users table")

        if 'location' not in users_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN location TEXT")
            print("✓ Added location column to users table")

        if 'skills' not in users_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN skills TEXT")
            print("✓ Added skills column to users table")

        if 'experience_years' not in users_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN experience_years INTEGER")
            print("✓ Added experience_years column to users table")

        if 'resume_path' not in users_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN resume_path TEXT")
            print("✓ Added resume_path column to users table")

        if 'profile_completed' not in users_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN profile_completed INTEGER DEFAULT 0")
            print("✓ Added profile_completed column to users table")

        if 'created_at' not in users_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            print("✓ Added created_at column to users table")

        # Check and add missing columns to applications table
        cursor.execute("PRAGMA table_info(applications)")
        applications_columns = [column[1] for column in cursor.fetchall()]

        if 'cover_letter' not in applications_columns:
            cursor.execute("ALTER TABLE applications ADD COLUMN cover_letter TEXT")
            print("✓ Added cover_letter column to applications table")

        if 'resume_path' not in applications_columns:
            cursor.execute("ALTER TABLE applications ADD COLUMN resume_path TEXT")
            print("✓ Added resume_path column to applications table")

        if 'score' not in applications_columns:
            cursor.execute("ALTER TABLE applications ADD COLUMN score INTEGER DEFAULT 0")
            print("✓ Added score column to applications table")

        if 'hr_notes' not in applications_columns:
            cursor.execute("ALTER TABLE applications ADD COLUMN hr_notes TEXT")
            print("✓ Added hr_notes column to applications table")

        if 'updated_on' not in applications_columns:
            cursor.execute("ALTER TABLE applications ADD COLUMN updated_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            print("✓ Added updated_on column to applications table")

        # Create activity_log table if doesn't exist
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS activity_log
                       (
                           log_id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           user_id
                           INTEGER,
                           action
                           TEXT,
                           details
                           TEXT,
                           timestamp
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           FOREIGN
                           KEY
                       (
                           user_id
                       ) REFERENCES users
                       (
                           user_id
                       )
                           )
                       """)
        print("✓ Created activity_log table")

        # Create saved_jobs table if doesn't exist
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS saved_jobs
                       (
                           save_id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           candidate_id
                           INTEGER
                           NOT
                           NULL,
                           job_id
                           INTEGER
                           NOT
                           NULL,
                           saved_on
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           UNIQUE
                       (
                           candidate_id,
                           job_id
                       ),
                           FOREIGN KEY
                       (
                           candidate_id
                       ) REFERENCES users
                       (
                           user_id
                       ),
                           FOREIGN KEY
                       (
                           job_id
                       ) REFERENCES jobs
                       (
                           job_id
                       )
                           )
                       """)
        print("✓ Created saved_jobs table")

        # Update existing jobs with default values
        cursor.execute("""
                       UPDATE jobs
                       SET job_type = 'Full-time',
                           status   = 'Active'
                       WHERE job_type IS NULL
                          OR status IS NULL
                       """)
        print("✓ Updated existing jobs with default values")

        conn.commit()
        print("\n✅ Database migration completed successfully!")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_database()