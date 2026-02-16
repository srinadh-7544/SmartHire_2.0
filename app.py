from flask import Flask, render_template, request, redirect, session, url_for, flash, send_from_directory
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
app.config['UPLOAD_FOLDER'] = 'uploads/resumes'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max file size
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}
DATABASE = "database.db"

# Create upload folder if doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# ---------------- DECORATORS ----------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


def hr_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'HR':
            flash('Access denied. HR only.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


def candidate_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'CANDIDATE':
            flash('Access denied. Candidates only.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


# ---------------- HELPER FUNCTIONS ----------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Drop existing tables (CAUTION: This deletes all data!)
    # Uncomment these lines if you want a complete fresh start
    # cursor.execute("DROP TABLE IF EXISTS applications")
    # cursor.execute("DROP TABLE IF EXISTS jobs")
    # cursor.execute("DROP TABLE IF EXISTS users")
    # cursor.execute("DROP TABLE IF EXISTS activity_log")
    # cursor.execute("DROP TABLE IF EXISTS saved_jobs")

    # Enhanced Users table with profile fields
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        )
    """)

    # Enhanced Jobs table with more details
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
                                            job_id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                                            posted_by INTEGER,
                                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                            FOREIGN KEY(posted_by) REFERENCES users(user_id)
        )
    """)

    # Enhanced Applications table with more tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            application_id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            candidate_id INTEGER NOT NULL,
            status TEXT DEFAULT 'Applied',
            cover_letter TEXT,
            resume_path TEXT,
            score INTEGER DEFAULT 0,
            hr_notes TEXT,
            applied_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(job_id, candidate_id),
            FOREIGN KEY(job_id) REFERENCES jobs(job_id),
            FOREIGN KEY(candidate_id) REFERENCES users(user_id)
        )
    """)

    # Activity Log table for tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)

    # Saved Jobs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS saved_jobs (
            save_id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL,
            job_id INTEGER NOT NULL,
            saved_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(candidate_id, job_id),
            FOREIGN KEY(candidate_id) REFERENCES users(user_id),
            FOREIGN KEY (job_id) REFERENCES jobs (job_id)
        )
    """)

    # Insert enhanced sample jobs
    jobs_count = cursor.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
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
            ("Data Analyst", "DataInsights", "Chennai", "Full-time", "0-2 years",
             "₹5-8 LPA", "SQL, Python, Excel, Tableau",
             "SQL & Python analysis with data visualization",
             "Strong analytical skills, SQL proficiency", "Active"),
            ("HR Executive", "HR Solutions", "Delhi", "Full-time", "1-3 years",
             "₹4-7 LPA", "Recruitment, Communication",
             "Recruitment & HR management tasks",
             "Good communication, recruiting experience", "Active"),
            ("AI Engineer", "AI Labs", "Pune", "Full-time", "3-5 years",
             "₹15-25 LPA", "Python, TensorFlow, ML, Deep Learning",
             "Machine Learning model development",
             "Strong ML background, research experience", "Active")
        ]
        cursor.executemany(
            """INSERT INTO jobs (title, company, location, job_type, experience_required, 
               salary_range, skills_required, description, requirements, status) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            sample_jobs
        )

    conn.commit()
    conn.close()
init_db()


# ---------------- HOME ----------------
@app.route("/")
def home():
    conn = get_db_connection()
    total_jobs = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='Active'").fetchone()[0]
    total_companies = conn.execute("SELECT COUNT(DISTINCT company) FROM jobs").fetchone()[0]
    featured_jobs = conn.execute("SELECT * FROM jobs WHERE status='Active' ORDER BY created_at DESC LIMIT 6").fetchall()
    conn.close()
    return render_template("home.html",
                           total_jobs=total_jobs,
                           total_companies=total_companies,
                           featured_jobs=featured_jobs)


# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form["full_name"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"].upper()

        if len(password) < 6:
            flash("Password must be at least 6 characters", "danger")
            return render_template("register.html")

        hashed_password = generate_password_hash(password)
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (full_name, email, password, role) VALUES (?, ?, ?, ?)",
                (full_name, email, hashed_password, role)
            )
            conn.commit()

            # Log activity
            cursor.execute(
                "INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)",
                (cursor.lastrowid, "REGISTRATION", f"New {role} registered")
            )
            conn.commit()
            conn.close()

            flash("Registration successful! Please login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            conn.close()
            flash("Email already exists!", "danger")
            return render_template("register.html")
    return render_template("register.html")


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["user_id"]
            session["role"] = user["role"].upper()
            session["name"] = user["full_name"]

            # Log activity
            conn.execute(
                "INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)",
                (user["user_id"], "LOGIN", "User logged in")
            )
            conn.commit()
            conn.close()

            flash(f"Welcome back, {user['full_name']}!", "success")
            if session["role"] == "HR":
                return redirect(url_for("hr_dashboard"))
            else:
                return redirect(url_for("candidate_dashboard"))
        else:
            conn.close()
            flash("Invalid email or password!", "danger")
    return render_template("login.html")


# ---------------- LOGOUT ----------------
@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Logged out successfully!", "info")
    return redirect(url_for("login"))


# ---------------- HR DASHBOARD ----------------
@app.route("/hr/dashboard")
@hr_required
def hr_dashboard():
    conn = get_db_connection()
    total_jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    active_jobs = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='Active'").fetchone()[0]
    total_applications = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
    shortlisted = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE status='Shortlisted'"
    ).fetchone()[0]
    interviews = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE status='Interview'"
    ).fetchone()[0]

    # Recent applications
    recent_applications = conn.execute("""
                                       SELECT a.application_id, u.full_name, j.title, a.status, a.applied_on
                                       FROM applications a
                                                JOIN users u ON a.candidate_id = u.user_id
                                                JOIN jobs j ON a.job_id = j.job_id
                                       ORDER BY a.applied_on DESC LIMIT 5
                                       """).fetchall()

    conn.close()

    return render_template(
        "hr_dashboard.html",
        total_jobs=total_jobs,
        active_jobs=active_jobs,
        total_applications=total_applications,
        shortlisted=shortlisted,
        interviews=interviews,
        recent_applications=recent_applications
    )


# ---------------- HR VIEW ALL JOBS ----------------
@app.route("/hr/jobs")
@hr_required
def hr_jobs():
    conn = get_db_connection()
    jobs = conn.execute("""
                        SELECT j.*, COUNT(a.application_id) as applicant_count
                        FROM jobs j
                                 LEFT JOIN applications a ON j.job_id = a.job_id
                        GROUP BY j.job_id
                        ORDER BY j.created_at DESC
                        """).fetchall()
    conn.close()
    return render_template("hr_jobs.html", jobs=jobs)


# ---------------- HR APPLICANTS WITH FILTERS ----------------
@app.route("/hr/applicants")
@hr_required
def hr_applicants():
    status_filter = request.args.get('status', 'All')
    job_filter = request.args.get('job', 'All')

    conn = get_db_connection()

    query = """
            SELECT a.application_id, \
                   u.full_name, \
                   u.email, \
                   u.phone, \
                   u.skills,
                   j.title, \
                   j.company, \
                   a.status, \
                   a.score, \
                   a.applied_on, \
                   a.resume_path
            FROM applications a
                     JOIN users u ON a.candidate_id = u.user_id
                     JOIN jobs j ON a.job_id = j.job_id
            WHERE 1 = 1 \
            """
    params = []

    if status_filter != 'All':
        query += " AND a.status = ?"
        params.append(status_filter)

    if job_filter != 'All':
        query += " AND j.job_id = ?"
        params.append(job_filter)

    query += " ORDER BY a.applied_on DESC"

    applicants = conn.execute(query, params).fetchall()
    jobs = conn.execute("SELECT DISTINCT job_id, title FROM jobs").fetchall()
    conn.close()

    return render_template("hr_applicants.html",
                           applicants=applicants,
                           jobs=jobs,
                           status_filter=status_filter,
                           job_filter=job_filter)


# ---------------- UPDATE APPLICATION STATUS ----------------
@app.route("/hr/update-status/<int:app_id>", methods=["POST"])
@hr_required
def update_application_status(app_id):
    new_status = request.form["status"]
    hr_notes = request.form.get("hr_notes", "")

    conn = get_db_connection()
    conn.execute(
        """UPDATE applications
           SET status     = ?,
               hr_notes   = ?,
               updated_on = CURRENT_TIMESTAMP
           WHERE application_id = ?""",
        (new_status, hr_notes, app_id)
    )
    conn.commit()
    conn.close()

    flash(f"Application status updated to {new_status}", "success")
    return redirect(url_for("hr_applicants"))


# ---------------- POST JOB ----------------
@app.route("/hr/post-job", methods=["GET", "POST"])
@hr_required
def post_job():
    if request.method == "POST":
        title = request.form["title"]
        company = request.form["company"]
        location = request.form["location"]
        job_type = request.form["job_type"]
        experience_required = request.form["experience_required"]
        salary_range = request.form.get("salary_range", "")
        skills_required = request.form.get("skills_required", "")
        description = request.form["description"]
        requirements = request.form.get("requirements", "")

        conn = get_db_connection()
        conn.execute(
            """INSERT INTO jobs (title, company, location, job_type, experience_required,
                                 salary_range, skills_required, description, requirements, posted_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, company, location, job_type, experience_required,
             salary_range, skills_required, description, requirements, session["user_id"])
        )
        conn.commit()
        conn.close()

        flash("Job posted successfully!", "success")
        return redirect(url_for("hr_dashboard"))

    return render_template("post_job.html")


# ---------------- EDIT JOB ----------------
@app.route("/hr/edit-job/<int:job_id>", methods=["GET", "POST"])
@hr_required
def edit_job(job_id):
    conn = get_db_connection()

    if request.method == "POST":
        conn.execute("""
                     UPDATE jobs
                     SET title=?,
                         company=?,
                         location=?,
                         job_type=?,
                         experience_required=?,
                         salary_range=?,
                         skills_required=?,
                         description=?,
                         requirements=?
                     WHERE job_id = ?
                     """, (
                         request.form["title"],
                         request.form["company"],
                         request.form["location"],
                         request.form["job_type"],
                         request.form["experience_required"],
                         request.form.get("salary_range", ""),
                         request.form.get("skills_required", ""),
                         request.form["description"],
                         request.form.get("requirements", ""),
                         job_id
                     ))
        conn.commit()
        conn.close()
        flash("Job updated successfully!", "success")
        return redirect(url_for("hr_jobs"))

    job = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    conn.close()
    return render_template("edit_job.html", job=job)


# ---------------- DELETE JOB ----------------
@app.route("/hr/delete-job/<int:job_id>", methods=["POST"])
@hr_required
def delete_job(job_id):
    conn = get_db_connection()
    conn.execute("UPDATE jobs SET status='Closed' WHERE job_id=?", (job_id,))
    conn.commit()
    conn.close()
    flash("Job closed successfully!", "success")
    return redirect(url_for("hr_jobs"))


# ---------------- CANDIDATE DASHBOARD ----------------
@app.route("/candidate/dashboard")
@candidate_required
def candidate_dashboard():
    candidate_id = session.get("user_id")
    conn = get_db_connection()

    # Stats
    applied_jobs = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE candidate_id=?", (candidate_id,)
    ).fetchone()[0]
    in_review = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE candidate_id=? AND status='In Review'",
        (candidate_id,)
    ).fetchone()[0]
    shortlisted = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE candidate_id=? AND status='Shortlisted'",
        (candidate_id,)
    ).fetchone()[0]
    interviews = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE candidate_id=? AND status='Interview'",
        (candidate_id,)
    ).fetchone()[0]

    # Get filters
    search = request.args.get('search', '')
    location_filter = request.args.get('location', '')
    job_type_filter = request.args.get('job_type', '')

    # Build query with filters
    query = "SELECT * FROM jobs WHERE status='Active'"
    params = []

    if search:
        query += " AND (title LIKE ? OR company LIKE ? OR skills_required LIKE ?)"
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param])

    if location_filter:
        query += " AND location LIKE ?"
        params.append(f"%{location_filter}%")

    if job_type_filter:
        query += " AND job_type = ?"
        params.append(job_type_filter)

    query += " ORDER BY created_at DESC"

    jobs = conn.execute(query, params).fetchall()

    # Get applied job IDs
    applied_job_ids = [row[0] for row in conn.execute(
        "SELECT job_id FROM applications WHERE candidate_id=?", (candidate_id,)
    ).fetchall()]

    # Get saved job IDs
    saved_job_ids = [row[0] for row in conn.execute(
        "SELECT job_id FROM saved_jobs WHERE candidate_id=?", (candidate_id,)
    ).fetchall()]

    conn.close()

    return render_template(
        "candidate_dashboard.html",
        applied_jobs=applied_jobs,
        in_review=in_review,
        shortlisted=shortlisted,
        interviews=interviews,
        jobs=jobs,
        applied_job_ids=applied_job_ids,
        saved_job_ids=saved_job_ids
    )


# ---------------- CANDIDATE PROFILE ----------------
@app.route("/candidate/profile", methods=["GET", "POST"])
@candidate_required
def candidate_profile():
    candidate_id = session.get("user_id")
    conn = get_db_connection()

    if request.method == "POST":
        phone = request.form.get("phone")
        location = request.form.get("location")
        skills = request.form.get("skills")
        experience_years = request.form.get("experience_years", 0)

        # Handle resume upload
        resume_path = None
        if 'resume' in request.files:
            file = request.files['resume']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(f"{candidate_id}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                resume_path = filename

        if resume_path:
            conn.execute("""
                         UPDATE users
                         SET phone=?,
                             location=?,
                             skills=?,
                             experience_years=?,
                             resume_path=?,
                             profile_completed=1
                         WHERE user_id = ?
                         """, (phone, location, skills, experience_years, resume_path, candidate_id))
        else:
            conn.execute("""
                         UPDATE users
                         SET phone=?,
                             location=?,
                             skills=?,
                             experience_years=?,
                             profile_completed=1
                         WHERE user_id = ?
                         """, (phone, location, skills, experience_years, candidate_id))

        conn.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for("candidate_profile"))

    user = conn.execute("SELECT * FROM users WHERE user_id=?", (candidate_id,)).fetchone()
    conn.close()
    return render_template("candidate_profile.html", user=user)


# ---------------- MY APPLICATIONS ----------------
@app.route("/candidate/my-applications")
@candidate_required
def my_applications():
    candidate_id = session.get("user_id")
    conn = get_db_connection()

    applications = conn.execute("""
                                SELECT a.*, j.title, j.company, j.location, j.job_type
                                FROM applications a
                                         JOIN jobs j ON a.job_id = j.job_id
                                WHERE a.candidate_id = ?
                                ORDER BY a.applied_on DESC
                                """, (candidate_id,)).fetchall()

    conn.close()
    return render_template("my_applications.html", applications=applications)


# ---------------- APPLY JOB WITH COVER LETTER ----------------
@app.route("/apply/<int:job_id>", methods=["GET", "POST"])
@candidate_required
def apply_job(job_id):
    candidate_id = session.get("user_id")

    if request.method == "POST":
        cover_letter = request.form.get("cover_letter", "")

        # Handle resume upload
        resume_path = None
        if 'resume' in request.files:
            file = request.files['resume']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(f"{candidate_id}_{int(datetime.now().timestamp())}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                resume_path = filename

        conn = get_db_connection()
        try:
            conn.execute(
                """INSERT INTO applications (job_id, candidate_id, cover_letter, resume_path)
                   VALUES (?, ?, ?, ?)""",
                (job_id, candidate_id, cover_letter, resume_path)
            )
            conn.commit()
            conn.close()
            flash("Application submitted successfully!", "success")
            return redirect(url_for("candidate_dashboard"))
        except sqlite3.IntegrityError:
            conn.close()
            flash("You have already applied to this job!", "warning")
            return redirect(url_for("candidate_dashboard"))

    # GET request - show application form
    conn = get_db_connection()
    job = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    conn.close()
    return render_template("apply_job.html", job=job)


# ---------------- SAVE/UNSAVE JOB ----------------
@app.route("/save-job/<int:job_id>", methods=["POST"])
@candidate_required
def save_job(job_id):
    candidate_id = session.get("user_id")
    conn = get_db_connection()

    try:
        conn.execute(
            "INSERT INTO saved_jobs (candidate_id, job_id) VALUES (?, ?)",
            (candidate_id, job_id)
        )
        conn.commit()
        flash("Job saved!", "success")
    except sqlite3.IntegrityError:
        flash("Job already saved!", "info")

    conn.close()
    return redirect(url_for("candidate_dashboard"))


@app.route("/unsave-job/<int:job_id>", methods=["POST"])
@candidate_required
def unsave_job(job_id):
    candidate_id = session.get("user_id")
    conn = get_db_connection()
    conn.execute(
        "DELETE FROM saved_jobs WHERE candidate_id=? AND job_id=?",
        (candidate_id, job_id)
    )
    conn.commit()
    conn.close()
    flash("Job removed from saved!", "info")
    return redirect(url_for("candidate_dashboard"))


# ---------------- DOWNLOAD RESUME ----------------
@app.route('/download-resume/<filename>')
@login_required
def download_resume(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ---------------- CHATBOT ROUTES ----------------
@app.route("/chatbot/query", methods=["POST"])
def chatbot_query():
    """Handle chatbot queries and provide intelligent responses"""
    data = request.get_json()
    user_message = data.get("message", "").lower().strip()

    conn = get_db_connection()
    response = {
        "message": "",
        "jobs": [],
        "suggestions": [],
        "action": None
    }

    # Intent Detection
    if any(keyword in user_message for keyword in ["hello", "hi", "hey", "start"]):
        response["message"] = """👋 Hello! I'm your Job Assistant. I can help you with:

- Find jobs by title, location, or skills
- Get salary information
- Connect with HR teams
- Apply to positions

What are you looking for today?"""
        response["suggestions"] = [
            "Show me Python jobs",
            "Jobs in Bangalore",
            "Full-time positions",
            "Entry level jobs"
        ]

    elif any(keyword in user_message for keyword in ["available jobs", "show jobs", "list jobs", "all jobs"]):
        jobs = conn.execute("""
                            SELECT *
                            FROM jobs
                            WHERE status = 'Active'
                            ORDER BY created_at DESC LIMIT 6
                            """).fetchall()

        response["message"] = f"📋 Found {len(jobs)} active positions for you!"
        response["jobs"] = [dict(job) for job in jobs]
        response["suggestions"] = ["Tell me more about these", "Jobs in specific location", "Filter by experience"]

    elif "location" in user_message or any(
            city in user_message for city in ["bangalore", "delhi", "mumbai", "hyderabad", "chennai", "pune"]):
        # Extract location
        location = None
        cities = {
            "bangalore": "Bangalore",
            "delhi": "Delhi",
            "mumbai": "Mumbai",
            "hyderabad": "Hyderabad",
            "chennai": "Chennai",
            "pune": "Pune"
        }
        for key, value in cities.items():
            if key in user_message:
                location = value
                break

        if location:
            jobs = conn.execute("""
                                SELECT *
                                FROM jobs
                                WHERE status = 'Active'
                                  AND location LIKE ?
                                ORDER BY created_at DESC
                                """, (f"%{location}%",)).fetchall()

            response["message"] = f"📍 Found {len(jobs)} jobs in {location}"
            response["jobs"] = [dict(job) for job in jobs]
        else:
            response[
                "message"] = "Which city are you interested in? (Bangalore, Delhi, Mumbai, Hyderabad, Chennai, Pune)"
            response["suggestions"] = ["Bangalore", "Delhi", "Mumbai", "Hyderabad"]

    elif any(keyword in user_message for keyword in
             ["python", "java", "react", "developer", "engineer", "analyst", "hr", "ai", "ml"]):
        # Extract skill/title
        skills = ["python", "java", "react", "javascript", "sql", "ai", "ml", "data", "frontend", "backend"]
        found_skill = None
        for skill in skills:
            if skill in user_message:
                found_skill = skill
                break

        if found_skill:
            jobs = conn.execute("""
                                SELECT *
                                FROM jobs
                                WHERE status = 'Active'
                                  AND (title LIKE ? OR skills_required LIKE ? OR description LIKE ?)
                                ORDER BY created_at DESC
                                """, (f"%{found_skill}%", f"%{found_skill}%", f"%{found_skill}%")).fetchall()

            response["message"] = f"💼 Found {len(jobs)} {found_skill.capitalize()} related positions"
            response["jobs"] = [dict(job) for job in jobs]
        else:
            response["message"] = "What specific skill or job title are you looking for?"

    elif any(keyword in user_message for keyword in ["salary", "pay", "package", "lpa"]):
        jobs = conn.execute("""
                            SELECT *
                            FROM jobs
                            WHERE status = 'Active'
                              AND salary_range IS NOT NULL
                              AND salary_range != ''
                            ORDER BY created_at DESC
                                LIMIT 6
                            """).fetchall()

        response["message"] = "💰 Here are positions with salary information:"
        response["jobs"] = [dict(job) for job in jobs]
        response["suggestions"] = ["Show high paying jobs", "Entry level salaries"]

    elif any(keyword in user_message for keyword in ["experience", "fresher", "entry level", "senior"]):
        if "fresher" in user_message or "entry" in user_message:
            exp_level = "0-2 years"
        elif "senior" in user_message:
            exp_level = "5+"
        else:
            exp_level = "2-4 years"

        jobs = conn.execute("""
                            SELECT *
                            FROM jobs
                            WHERE status = 'Active'
                              AND experience_required LIKE ?
                            ORDER BY created_at DESC
                            """, (f"%{exp_level.split('-')[0]}%",)).fetchall()

        response["message"] = f"🎯 Found {len(jobs)} positions for {exp_level} experience"
        response["jobs"] = [dict(job) for job in jobs]

    elif any(keyword in user_message for keyword in ["full-time", "part-time", "contract", "internship", "job type"]):
        job_type = "Full-time"
        if "part-time" in user_message or "part time" in user_message:
            job_type = "Part-time"
        elif "contract" in user_message:
            job_type = "Contract"
        elif "internship" in user_message:
            job_type = "Internship"

        jobs = conn.execute("""
                            SELECT *
                            FROM jobs
                            WHERE status = 'Active'
                              AND job_type = ?
                            ORDER BY created_at DESC
                            """, (job_type,)).fetchall()

        response["message"] = f"⏰ Found {len(jobs)} {job_type} positions"
        response["jobs"] = [dict(job) for job in jobs]

    elif any(keyword in user_message for keyword in ["hr", "contact", "connect", "recruiter"]):
        response["message"] = """📞 To connect with our HR team:

- Apply to any job posting
- Our HR will review your application
- You'll receive interview invitations via email
- Direct contact info is available in job postings

Would you like to see available positions?"""
        response["suggestions"] = ["Show all jobs", "Jobs with immediate hiring"]

    elif any(keyword in user_message for keyword in ["apply", "application", "how to apply"]):
        response["message"] = """📝 How to Apply:

1. Browse jobs that match your skills
2. Click "Apply Now" on any job card
3. Fill in your details and upload resume
4. Submit your application
5. Track status in your dashboard

Ready to start? Let me show you some jobs!"""
        response["suggestions"] = ["Show me jobs", "What documents needed?"]
        response["action"] = "show_jobs"

    elif any(keyword in user_message for keyword in ["help", "what can you do", "features"]):
        response["message"] = """🤖 I can help you with:

✅ Find jobs by title, skills, or location
✅ Filter by experience level
✅ Check salary information
✅ Get job type details (Full-time, Part-time, etc.)
✅ Guide you through application process
✅ Connect you with HR teams

Try asking:
- "Show Python jobs in Bangalore"
- "Entry level positions"
- "Jobs with 10+ LPA salary"
- "How to apply?"
"""
        response["suggestions"] = ["Show all jobs", "Jobs in my city", "Entry level jobs"]

    else:
        # Default fallback - search in all fields
        jobs = conn.execute("""
                            SELECT *
                            FROM jobs
                            WHERE status = 'Active'
                              AND (title LIKE ? OR company LIKE ? OR skills_required LIKE ? OR description LIKE ?)
                            ORDER BY created_at DESC LIMIT 6
                            """, (f"%{user_message}%", f"%{user_message}%", f"%{user_message}%",
                                  f"%{user_message}%")).fetchall()

        if jobs:
            response["message"] = f"🔍 Found {len(jobs)} jobs matching '{user_message}'"
            response["jobs"] = [dict(job) for job in jobs]
        else:
            response["message"] = """I didn't quite understand that. Try asking:

- "Show me jobs in [city]"
- "Find [skill] developer jobs"
- "Entry level positions"
- "Help" for more options"""
            response["suggestions"] = ["Show all jobs", "Help", "Available locations"]

    conn.close()
    return jsonify(response)


@app.route("/chatbot/job-details/<int:job_id>", methods=["GET"])
def chatbot_job_details(job_id):
    """Get detailed job information for chatbot"""
    conn = get_db_connection()
    job = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    conn.close()

    if job:
        return jsonify(dict(job))
    return jsonify({"error": "Job not found"}), 404

# ---------------- RUN APP ----------------
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)

