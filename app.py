from flask import Flask, render_template, request, redirect, session, url_for, flash, send_from_directory, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from functools import wraps
from PyPDF2 import PdfReader
import psycopg2
import psycopg2.extras
import psycopg2.errors
import os
import re

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret")

app.config["UPLOAD_FOLDER"] = "uploads/resumes"
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf"}


def get_db_connection():
    """Get PostgreSQL database connection with DictCursor"""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")

    conn = psycopg2.connect(database_url)
    return conn


def get_dict_cursor(conn):
    """Get a cursor that returns results as dictionaries"""
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def parse_resume(file_path):
    reader = PdfReader(file_path)
    text = ""

    for page in reader.pages:
        text += page.extract_text() or ""

    text = text.lower()

    skills_list = [
        "python", "java", "flask", "django",
        "react", "node", "sql",
        "machine learning", "html", "css", "javascript"
    ]

    detected_skills = [s for s in skills_list if s in text]

    exp_match = re.search(r'(\d+)\+?\s+years', text)
    experience = int(exp_match.group(1)) if exp_match else 0

    return {
        "skills": ", ".join(detected_skills),
        "experience": experience
    }


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


# ---------------- HOME ----------------
@app.route("/")
def home():
    conn = get_db_connection()
    cursor = conn.cursor()


    cursor.execute("SELECT COUNT(DISTINCT company) FROM jobs WHERE status='Active'")
    total_companies = cursor.fetchone()[0]

    cursor = get_dict_cursor(conn)
    cursor.execute("""
                   SELECT *
                   FROM jobs
                   WHERE status = 'Active'
                   ORDER BY created_at DESC
                   LIMIT 6
                   """)
    featured_jobs = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("home.html",
                           total_jobs=total_jobs,
                           total_companies=total_companies,
                           featured_jobs=featured_jobs)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form["full_name"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])
        role = request.form["role"].upper()

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """INSERT INTO users (full_name, email, password, role)
                   VALUES (%s, %s, %s, %s)
                   RETURNING user_id""",
                (full_name, email, password, role)
            )

            user_id = cursor.fetchone()[0]

            cursor.execute(
                """INSERT INTO activity_log (user_id, action, details)
                   VALUES (%s, %s, %s)""",
                (user_id, "REGISTRATION", f"{role} registered")
            )

            conn.commit()
            cursor.close()
            conn.close()

            flash("Registration successful", "success")
            return redirect(url_for("login"))

        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            cursor.close()
            conn.close()
            flash("Email already exists", "danger")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = get_dict_cursor(conn)

        cursor.execute(
            "SELECT * FROM users WHERE email = %s",
            (email,)
        )

        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["user_id"]
            session["role"] = user["role"]
            session["name"] = user["full_name"]

            return redirect(
                url_for("hr_dashboard")
                if user["role"] == "HR"
                else url_for("candidate_dashboard")
            )

        flash("Invalid credentials", "danger")

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
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM jobs")
    total_jobs = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM jobs WHERE status='Active'")
    active_jobs = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM applications")
    total_applications = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM applications WHERE status='Shortlisted'")
    shortlisted = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM applications WHERE status='Interview'")
    interviews = cursor.fetchone()[0]

    # Recent applications
    cursor = get_dict_cursor(conn)
    cursor.execute("""
                   SELECT a.application_id,
                          a.status,
                          a.applied_on,
                          a.score,
                          j.title     AS job_title,
                          u.full_name AS candidate_name,
                          u.email
                   FROM applications a
                            JOIN jobs j ON a.job_id = j.job_id
                            JOIN users u ON a.candidate_id = u.user_id
                   ORDER BY a.applied_on DESC
                   LIMIT 5
                   """)
    recent_applications = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("hr_dashboard.html",
                           total_jobs=total_jobs,
                           active_jobs=active_jobs,
                           total_applications=total_applications,
                           shortlisted=shortlisted,
                           interviews=interviews,
                           recent_applications=recent_applications)


# ---------------- HR - JOB POSTING ----------------
@app.route("/hr/post-job", methods=["GET", "POST"])
@hr_required
def post_job():
    if request.method == "POST":
        title = request.form["title"]
        company = request.form["company"]
        location = request.form["location"]
        job_type = request.form["job_type"]
        experience_required = request.form["experience_required"]
        salary_range = request.form["salary_range"]
        skills_required = request.form["skills_required"]
        description = request.form["description"]
        requirements = request.form["requirements"]

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
                       INSERT INTO jobs (title, company, location, job_type,
                                         experience_required, salary_range,
                                         skills_required, description, requirements,
                                         posted_by)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       """, (title, company, location, job_type,
                             experience_required, salary_range,
                             skills_required, description, requirements,
                             session['user_id']))

        cursor.execute(
            """INSERT INTO activity_log (user_id, action, details)
               VALUES (%s, %s, %s)""",
            (session['user_id'], "JOB_POSTED", f"Posted: {title}")
        )

        conn.commit()
        cursor.close()
        conn.close()

        flash("Job posted successfully!", "success")
        return redirect(url_for("hr_jobs"))

    return render_template("post_job.html")


# ---------------- HR - VIEW JOBS ----------------
@app.route("/hr/jobs")
@hr_required
def hr_jobs():
    conn = get_db_connection()
    cursor = get_dict_cursor(conn)

    cursor.execute("""
                   SELECT j.*, COUNT(a.application_id) as application_count
                   FROM jobs j
                            LEFT JOIN applications a ON j.job_id = a.job_id
                   GROUP BY j.job_id
                   ORDER BY j.created_at DESC
                   """)
    jobs = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("hr_jobs.html", jobs=jobs)


# ---------------- HR - VIEW APPLICATIONS ----------------
@app.route("/hr/applications")
@hr_required
def hr_applications():
    conn = get_db_connection()
    cursor = get_dict_cursor(conn)

    cursor.execute("""
                   SELECT a.application_id,
                          a.status,
                          a.applied_on,
                          a.score,
                          a.cover_letter,
                          j.title AS job_title,
                          j.job_id,
                          u.full_name,
                          u.email,
                          u.phone,
                          u.skills,
                          u.experience_years,
                          u.resume_path
                   FROM applications a
                            JOIN jobs j ON a.job_id = j.job_id
                            JOIN users u ON a.candidate_id = u.user_id
                   ORDER BY a.applied_on DESC
                   """)
    applications = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("hr_applications.html", applications=applications)


# ---------------- HR - UPDATE APPLICATION STATUS ----------------
@app.route("/hr/application/<int:app_id>/update", methods=["POST"])
@hr_required
def update_application(app_id):
    new_status = request.form["status"]
    hr_notes = request.form.get("hr_notes", "")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """UPDATE applications
           SET status     = %s,
               hr_notes   = %s,
               updated_on = CURRENT_TIMESTAMP
           WHERE application_id = %s""",
        (new_status, hr_notes, app_id)
    )

    cursor.execute(
        """INSERT INTO activity_log (user_id, action, details)
           VALUES (%s, %s, %s)""",
        (session['user_id'], "STATUS_UPDATE", f"Application #{app_id} → {new_status}")
    )

    conn.commit()
    cursor.close()
    conn.close()

    flash(f"Application status updated to {new_status}", "success")
    return redirect(url_for("hr_applications"))


# ---------------- HR - DELETE JOB ----------------
@app.route("/hr/job/<int:job_id>/delete", methods=["POST"])
@hr_required
def delete_job(job_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM applications WHERE job_id = %s", (job_id,))
    cursor.execute("DELETE FROM saved_jobs WHERE job_id = %s", (job_id,))
    cursor.execute("DELETE FROM jobs WHERE job_id = %s", (job_id,))

    cursor.execute(
        """INSERT INTO activity_log (user_id, action, details)
           VALUES (%s, %s, %s)""",
        (session['user_id'], "JOB_DELETED", f"Deleted Job ID: {job_id}")
    )

    conn.commit()
    cursor.close()
    conn.close()

    flash("Job deleted successfully", "info")
    return redirect(url_for("hr_jobs"))


# ---------------- CANDIDATE DASHBOARD ----------------
@app.route("/candidate/dashboard")
@candidate_required
def candidate_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()

    user_id = session['user_id']

    cursor.execute("SELECT COUNT(*) FROM applications WHERE candidate_id = %s", (user_id,))
    total_applications = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM applications WHERE candidate_id = %s AND status = 'Applied'",
        (user_id,)
    )
    pending = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM applications WHERE candidate_id = %s AND status = 'Shortlisted'",
        (user_id,)
    )
    shortlisted = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM applications WHERE candidate_id = %s AND status = 'Interview'",
        (user_id,)
    )
    interviews = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM saved_jobs WHERE candidate_id = %s", (user_id,))
    saved_count = cursor.fetchone()[0]

    cursor = get_dict_cursor(conn)
    cursor.execute("""
                   SELECT a.application_id,
                          a.status,
                          a.applied_on,
                          a.score,
                          j.title,
                          j.company,
                          j.location
                   FROM applications a
                            JOIN jobs j ON a.job_id = j.job_id
                   WHERE a.candidate_id = %s
                   ORDER BY a.applied_on DESC
                   LIMIT 5
                   """, (user_id,))
    recent_applications = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("candidate_dashboard.html",
                           total_applications=total_applications,
                           pending=pending,
                           shortlisted=shortlisted,
                           interviews=interviews,
                           saved_count=saved_count,
                           recent_applications=recent_applications)


# ---------------- CANDIDATE - PROFILE ----------------
@app.route("/candidate/profile", methods=["GET", "POST"])
@candidate_required
def candidate_profile():
    user_id = session['user_id']

    if request.method == "POST":
        phone = request.form["phone"]
        location = request.form["location"]
        skills = request.form["skills"]
        experience_years = request.form["experience_years"]

        resume_path = None
        if 'resume' in request.files:
            file = request.files['resume']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{user_id}_{file.filename}")
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(filepath)
                resume_path = filename

                # Parse resume
                parsed_data = parse_resume(filepath)
                skills = parsed_data.get("skills", skills)
                experience_years = parsed_data.get("experience", experience_years)

        conn = get_db_connection()
        cursor = conn.cursor()

        if resume_path:
            cursor.execute("""
                           UPDATE users
                           SET phone             = %s,
                               location          = %s,
                               skills            = %s,
                               experience_years  = %s,
                               resume_path       = %s,
                               profile_completed = 1
                           WHERE user_id = %s
                           """, (phone, location, skills, experience_years, resume_path, user_id))
        else:
            cursor.execute("""
                           UPDATE users
                           SET phone             = %s,
                               location          = %s,
                               skills            = %s,
                               experience_years  = %s,
                               profile_completed = 1
                           WHERE user_id = %s
                           """, (phone, location, skills, experience_years, user_id))

        cursor.execute(
            """INSERT INTO activity_log (user_id, action, details)
               VALUES (%s, %s, %s)""",
            (user_id, "PROFILE_UPDATE", "Profile updated")
        )

        conn.commit()
        cursor.close()
        conn.close()

        flash("Profile updated successfully!", "success")
        return redirect(url_for("candidate_dashboard"))

    conn = get_db_connection()
    cursor = get_dict_cursor(conn)
    cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template("candidate_profile.html", user=user)


# ---------------- CANDIDATE - BROWSE JOBS ----------------
@app.route("/candidate/jobs")
@candidate_required
def browse_jobs():
    conn = get_db_connection()
    cursor = get_dict_cursor(conn)

    search = request.args.get("search", "")
    location = request.args.get("location", "")

    query = "SELECT * FROM jobs WHERE status = 'Active'"
    params = []

    if search:
        query += " AND (title ILIKE %s OR skills_required ILIKE %s OR company ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    if location:
        query += " AND location ILIKE %s"
        params.append(f"%{location}%")

    query += " ORDER BY created_at DESC"

    cursor.execute(query, params)
    jobs = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("browse_jobs.html", jobs=jobs, search=search, location=location)


# ---------------- CANDIDATE - VIEW JOB DETAILS ----------------
@app.route("/candidate/job/<int:job_id>")
@candidate_required
def job_details(job_id):
    conn = get_db_connection()
    cursor = get_dict_cursor(conn)

    cursor.execute("SELECT * FROM jobs WHERE job_id = %s", (job_id,))
    job = cursor.fetchone()

    user_id = session['user_id']
    cursor.execute(
        "SELECT * FROM applications WHERE job_id = %s AND candidate_id = %s",
        (job_id, user_id)
    )
    application = cursor.fetchone()

    cursor.execute(
        "SELECT * FROM saved_jobs WHERE job_id = %s AND candidate_id = %s",
        (job_id, user_id)
    )
    is_saved = cursor.fetchone() is not None

    cursor.close()
    conn.close()

    if not job:
        flash("Job not found", "danger")
        return redirect(url_for("browse_jobs"))

    return render_template("job_details.html", job=job, application=application, is_saved=is_saved)


# ---------------- CANDIDATE - APPLY FOR JOB ----------------
@app.route("/candidate/job/<int:job_id>/apply", methods=["POST"])
@candidate_required
def apply_job(job_id):
    user_id = session['user_id']
    cover_letter = request.form.get("cover_letter", "")

    conn = get_db_connection()
    cursor = get_dict_cursor(conn)

    # Get user profile
    cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    user = cursor.fetchone()

    if not user['profile_completed']:
        flash("Please complete your profile before applying", "warning")
        return redirect(url_for("candidate_profile"))

    # Get job details
    cursor.execute("SELECT * FROM jobs WHERE job_id = %s", (job_id,))
    job = cursor.fetchone()

    # Calculate matching score
    user_skills = set(user['skills'].lower().split(", ")) if user['skills'] else set()
    job_skills = set(job['skills_required'].lower().split(", ")) if job['skills_required'] else set()
    matching_skills = user_skills.intersection(job_skills)
    score = int((len(matching_skills) / len(job_skills)) * 100) if job_skills else 0

    try:
        cursor = conn.cursor()
        cursor.execute("""
                       INSERT INTO applications (job_id, candidate_id, cover_letter, resume_path, score)
                       VALUES (%s, %s, %s, %s, %s)
                       """, (job_id, user_id, cover_letter, user['resume_path'], score))

        cursor.execute(
            """INSERT INTO activity_log (user_id, action, details)
               VALUES (%s, %s, %s)""",
            (user_id, "APPLICATION", f"Applied to: {job['title']}")
        )

        conn.commit()
        flash("Application submitted successfully!", "success")

    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        flash("You have already applied to this job", "warning")

    cursor.close()
    conn.close()

    return redirect(url_for("job_details", job_id=job_id))


# ---------------- CANDIDATE - SAVE/UNSAVE JOB ----------------
@app.route("/candidate/job/<int:job_id>/save", methods=["POST"])
@candidate_required
def save_job(job_id):
    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO saved_jobs (candidate_id, job_id) VALUES (%s, %s)",
            (user_id, job_id)
        )
        conn.commit()
        flash("Job saved successfully!", "success")

    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        flash("Job already saved", "info")

    cursor.close()
    conn.close()

    return redirect(url_for("job_details", job_id=job_id))


@app.route("/candidate/job/<int:job_id>/unsave", methods=["POST"])
@candidate_required
def unsave_job(job_id):
    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM saved_jobs WHERE candidate_id = %s AND job_id = %s",
        (user_id, job_id)
    )

    conn.commit()
    cursor.close()
    conn.close()

    flash("Job removed from saved list", "info")
    return redirect(url_for("job_details", job_id=job_id))


# ---------------- CANDIDATE - MY APPLICATIONS ----------------
@app.route("/candidate/applications")
@candidate_required
def my_applications():
    user_id = session['user_id']

    conn = get_db_connection()
    cursor = get_dict_cursor(conn)

    cursor.execute("""
                   SELECT a.application_id,
                          a.status,
                          a.applied_on,
                          a.score,
                          a.hr_notes,
                          j.title,
                          j.company,
                          j.location,
                          j.job_id
                   FROM applications a
                            JOIN jobs j ON a.job_id = j.job_id
                   WHERE a.candidate_id = %s
                   ORDER BY a.applied_on DESC
                   """, (user_id,))
    applications = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("my_applications.html", applications=applications)


# ---------------- CANDIDATE - SAVED JOBS ----------------
@app.route("/candidate/saved")
@candidate_required
def saved_jobs():
    user_id = session['user_id']

    conn = get_db_connection()
    cursor = get_dict_cursor(conn)

    cursor.execute("""
                   SELECT j.*, s.saved_on
                   FROM saved_jobs s
                            JOIN jobs j ON s.job_id = j.job_id
                   WHERE s.candidate_id = %s
                   ORDER BY s.saved_on DESC
                   """, (user_id,))
    jobs = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("saved_jobs.html", jobs=jobs)


# ---------------- RESUME DOWNLOAD ----------------
@app.route("/uploads/resumes/<filename>")
@login_required
def download_resume(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


# ---------------- CHATBOT API ----------------
@app.route("/chatbot/message", methods=["POST"])
def chatbot_message():
    """Handle chatbot queries and return job recommendations"""
    data = request.get_json()
    user_message = data.get("message", "").lower().strip()

    response = {
        "message": "",
        "jobs": [],
        "suggestions": [],
        "action": None
    }

    conn = get_db_connection()
    cursor = get_dict_cursor(conn)

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
        cursor.execute("""
                       SELECT *
                       FROM jobs
                       WHERE status = 'Active'
                       ORDER BY created_at DESC
                       LIMIT 6
                       """)
        jobs = cursor.fetchall()

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
            cursor.execute("""
                           SELECT *
                           FROM jobs
                           WHERE status = 'Active'
                             AND location ILIKE %s
                           ORDER BY created_at DESC
                           """, (f"%{location}%",))
            jobs = cursor.fetchall()

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
            cursor.execute("""
                           SELECT *
                           FROM jobs
                           WHERE status = 'Active'
                             AND (title ILIKE %s OR skills_required ILIKE %s OR description ILIKE %s)
                           ORDER BY created_at DESC
                           """, (f"%{found_skill}%", f"%{found_skill}%", f"%{found_skill}%"))
            jobs = cursor.fetchall()

            response["message"] = f"💼 Found {len(jobs)} {found_skill.capitalize()} related positions"
            response["jobs"] = [dict(job) for job in jobs]
        else:
            response["message"] = "What specific skill or job title are you looking for?"

    elif any(keyword in user_message for keyword in ["salary", "pay", "package", "lpa"]):
        cursor.execute("""
                       SELECT *
                       FROM jobs
                       WHERE status = 'Active'
                         AND salary_range IS NOT NULL
                         AND salary_range != ''
                       ORDER BY created_at DESC
                       LIMIT 6
                       """)
        jobs = cursor.fetchall()

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

        cursor.execute("""
                       SELECT *
                       FROM jobs
                       WHERE status = 'Active'
                         AND experience_required ILIKE %s
                       ORDER BY created_at DESC
                       """, (f"%{exp_level.split('-')[0]}%",))
        jobs = cursor.fetchall()

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

        cursor.execute("""
                       SELECT *
                       FROM jobs
                       WHERE status = 'Active'
                         AND job_type = %s
                       ORDER BY created_at DESC
                       """, (job_type,))
        jobs = cursor.fetchall()

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
        cursor.execute("""
                       SELECT *
                       FROM jobs
                       WHERE status = 'Active'
                         AND (title ILIKE %s OR company ILIKE %s OR skills_required ILIKE %s OR description ILIKE %s)
                       ORDER BY created_at DESC
                       LIMIT 6
                       """, (f"%{user_message}%", f"%{user_message}%", f"%{user_message}%", f"%{user_message}%"))
        jobs = cursor.fetchall()

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

    cursor.close()
    conn.close()
    return jsonify(response)


@app.route("/chatbot/job-details/<int:job_id>", methods=["GET"])
def chatbot_job_details(job_id):
    """Get detailed job information for chatbot"""
    conn = get_db_connection()
    cursor = get_dict_cursor(conn)

    cursor.execute("SELECT * FROM jobs WHERE job_id=%s", (job_id,))
    job = cursor.fetchone()

    cursor.close()
    conn.close()

    if job:
        return jsonify(dict(job))
    return jsonify({"error": "Job not found"}), 404


# ---------------- RUN APP ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)