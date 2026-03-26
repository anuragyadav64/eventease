from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import date
import re, os
from werkzeug.security import generate_password_hash, check_password_hash
import qrcode, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from dotenv import load_dotenv

app = Flask(__name__)
load_dotenv()
app.secret_key = os.getenv('SECRET_KEY', 'eventease_secret')
DB_NAME = "database.db"

def get_db():
    return sqlite3.connect(DB_NAME)

# ===================== INIT DB =====================
def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        college_id TEXT NOT NULL
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        event_date DATE NOT NULL,
        event_time TEXT NOT NULL,
        venue TEXT NOT NULL,
        category TEXT NOT NULL,
        audience TEXT NOT NULL,
        description TEXT,
        status TEXT DEFAULT 'Upcoming',
        sub_events TEXT,
        college_id TEXT NOT NULL
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        rollno TEXT NOT NULL,
        department TEXT NOT NULL,
        year TEXT NOT NULL,
        role TEXT,
        sub_event TEXT,
        college_id TEXT NOT NULL,
        FOREIGN KEY (event_id) REFERENCES events (id),
        UNIQUE(event_id, email)
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        message TEXT NOT NULL,
        college_id TEXT NOT NULL
    )''')
    conn.commit()
    conn.close()

init_db()

# ===================== UTILS =====================
def validate_input(name, email, phone, rollno, department, year):
    if not re.match(r"^[a-zA-Z\s]+$", name):
        return "Invalid name (only letters and spaces allowed)."
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        return "Invalid email format."
    if not re.match(r"^\d{10}$", phone):
        return "Invalid phone number (10 digits only)."
    if not re.match(r"^\d+$", rollno):
        return "Invalid roll number (digits only)."
    if not re.match(r"^[a-zA-Z\s]+$", department):
        return "Invalid department (letters and spaces only)."
    if year not in ["1st Year", "2nd Year", "3rd Year", "4th Year"]:
        return "Invalid year."
    return None

def generate_qr(event_title, email):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(f"Event: {event_title}\nEmail: {email}")
    qr.make(fit=True)
    qr_dir = os.path.join("static", "qr")
    os.makedirs(qr_dir, exist_ok=True)
    safe_email = re.sub(r'[^\w\-_\.]', '_', email)
    safe_title = re.sub(r'[^\w\-_\.]', '_', event_title)
    filename = os.path.join(qr_dir, f"{safe_email}_{safe_title}.png")
    qr.save(filename)
    return filename

def send_email(to_email, event_title, qr_path):
    sender = os.getenv('EMAIL_USER')
    password = os.getenv('EMAIL_PASS')

    msg = MIMEMultipart()
    msg['Subject'] = f"Registration Confirmation - {event_title}"
    msg['From'] = sender
    msg['To'] = to_email

    body = MIMEText(f"""
    <html>
      <body>
        <h2 style="color:green;">Registration Successful!</h2>
        <p>Hello {to_email},</p>
        <p>You have successfully registered for <b>{event_title}</b>.</p>
        <p>Please find your QR code attached below.</p>
        <br>
        <p>Best regards,<br>EventEase Team</p>
      </body>
    </html>
    """, 'html')
    msg.attach(body)

    with open(qr_path, 'rb') as f:
        img = MIMEImage(f.read())
        img.add_header('Content-Disposition', 'attachment', filename=os.path.basename(qr_path))
        msg.attach(img)

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

# ===================== ROUTES =====================
@app.route("/")
def home():
    return redirect("/start")

@app.route("/start", methods=["GET", "POST"])
def start():
    if request.method == "POST":
        role = request.form.get("role")
        college = request.form.get("college")
        if role and college:
            session["role"] = role
            session["college_id"] = college
            if role == "admin":
                return redirect("/login")
            else:
                return redirect("/dashboard")  # user direct dashboard
    return render_template("start.html")


from datetime import date

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    college_id = session.get("college_id")
    if not college_id:
        return redirect("/start")
    
    conn = get_db()
    cur = conn.cursor()
    today = date.today()
    
    if request.method == "POST":
        search = request.form.get("search", "").strip()
        if search:
            cur.execute(
                "SELECT * FROM events WHERE college_id=? AND title LIKE ? ORDER BY event_date",
                (college_id, f"%{search}%")
            )
        else:
            cur.execute(
                "SELECT * FROM events WHERE college_id=? ORDER BY event_date",
                (college_id,)
            )
    else:
        cur.execute(
            "SELECT * FROM events WHERE college_id=? ORDER BY event_date",
            (college_id,)
        )
    
    events = cur.fetchall()
    updated_events = []
    for event in events:
        # Convert string to date object
        event_date = date.fromisoformat(event[2])
        
        # Status calculation
        if event_date < today:
            status = "Completed"
        else:
            status = "Upcoming"
        
        # Update DB if status changed
        if status != event[8]:
            cur.execute("UPDATE events SET status=? WHERE id=?", (status, event[0]))
        
        # Replace event[2] (string) with event_date (date object)
        fixed_event = (
            event[0],  # id
            event[1],  # title
            event_date,  # date object
            event[3],  # time
            event[4],  # venue
            event[5],  # category
            event[6],  # audience
            event[7],  # participants
            status,    # updated status
            *event[9:] # rest of fields if any
        )
        
        updated_events.append(fixed_event)
    
    conn.commit()
    conn.close()
    
    return render_template("index.html", events=updated_events, today=today)


@app.route("/register/<int:event_id>", methods=["GET", "POST"])
def register(event_id):
    college_id = session.get("college_id")
    if not college_id:
        return redirect("/start")
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM events WHERE id=? AND college_id=?", (event_id, college_id))
    event = cur.fetchone()
    conn.close()
    
    if not event:
        return "Event not found", 404
    
    if request.method == "POST":
        name = request.form.get("name").strip()
        email = request.form.get("email").strip()
        phone = request.form.get("phone").strip()
        rollno = request.form.get("rollno").strip()
        department = request.form.get("department").strip()
        year = request.form.get("year").strip()
        role = request.form.get("role", "").strip()
        sub_event = request.form.get("sub_event", "").strip()
        
        error = validate_input(name, email, phone, rollno, department, year)
        if error:
            return render_template("register.html", event=event, error=error)
        
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO participants (event_id, name, email, phone, rollno, department, year, role, sub_event, college_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (event_id, name, email, phone, rollno, department, year, role, sub_event, college_id))
            conn.commit()
            
            qr_path = generate_qr(event[1], email)
            send_email(email, event[1], qr_path)
            
            return redirect("/my_registrations?success=1")
        except sqlite3.IntegrityError:
            error = "You are already registered for this event."
        finally:
            conn.close()
        
        return render_template("register.html", event=event, error=error)
    
    return render_template("register.html", event=event)

@app.route("/event", methods=["GET", "POST"])
@app.route("/event/<int:event_id>", methods=["GET", "POST"])
def event_form(event_id=None):
    if session.get("role") != "admin":
        return redirect("/start")
    
    college_id = session.get("college_id")
    conn = get_db()
    cur = conn.cursor()
    
    if request.method == "POST":
        title = request.form.get("title").strip()
        event_date = request.form.get("event_date")
        event_time = request.form.get("event_time").strip()
        venue = request.form.get("venue").strip()
        category = request.form.get("category").strip()
        audience = request.form.get("audience").strip()
        description = request.form.get("description").strip()
        sub_events = request.form.get("sub_events").strip()
        
        if event_id:
            cur.execute("UPDATE events SET title=?, event_date=?, event_time=?, venue=?, category=?, audience=?, description=?, sub_events=? WHERE id=? AND college_id=?",
                        (title, event_date, event_time, venue, category, audience, description, sub_events, event_id, college_id))
        else:
            cur.execute("INSERT INTO events (title, event_date, event_time, venue, category, audience, description, sub_events, college_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (title, event_date, event_time, venue, category, audience, description, sub_events, college_id))
        
        conn.commit()
        conn.close()
        return redirect("/dashboard")
    
    if event_id:
        cur.execute("SELECT * FROM events WHERE id=? AND college_id=?", (event_id, college_id))
        event = cur.fetchone()
        conn.close()
        return render_template("event_form.html", event=event)
    
    conn.close()
    return render_template("event_form.html")

@app.route("/details/<int:event_id>")
def event_details(event_id):
    college_id = session.get("college_id")
    if not college_id:
        return redirect("/start")
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM events WHERE id=? AND college_id=?", (event_id, college_id))
    event = cur.fetchone()
    conn.close()
    
    if not event:
        return "Event not found", 404
    
    return render_template("event_detail.html", event=event)

@app.route("/participants/<int:event_id>")
def participants(event_id):
    if session.get("role") != "admin":
        return redirect("/start")
    
    college_id = session.get("college_id")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM participants WHERE event_id=? AND college_id=?", (event_id, college_id))
    participants_list = cur.fetchall()
    cur.execute("SELECT title FROM events WHERE id=? AND college_id=?", (event_id, college_id))
    event_title = cur.fetchone()[0]
    conn.close()
    
    return render_template("participants.html", participants=participants_list, event_title=event_title)

@app.route("/my_registrations", methods=["GET", "POST"])
def my_registrations():
    college_id = session.get("college_id")
    if not college_id:
        return redirect("/start")
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.*, e.title, e.event_date, e.event_time, e.venue
        FROM participants p
        JOIN events e ON p.event_id = e.id
        WHERE p.college_id=? ORDER BY e.event_date
    """, (college_id,))
    registrations = cur.fetchall()
    conn.close()
    
    return render_template("my_registrations.html", registrations=registrations)

@app.route("/cancel_registration/<event_title>/<email>")
def cancel_registration(event_title, email):
    college_id = session.get("college_id")
    if not college_id:
        return redirect("/start")
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM participants WHERE email=? AND college_id=? AND event_id IN (SELECT id FROM events WHERE title=? AND college_id=?)",
                (email, college_id, event_title, college_id))
    conn.commit()
    conn.close()
    
    return redirect("/my_registrations?cancelled=1")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password").strip()
        college_id = request.form.get("college_id").strip()  # 👈 form se lo

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT password_hash FROM admins WHERE username=? AND college_id=?", (username, college_id))
        result = cur.fetchone()
        conn.close()

        if result and check_password_hash(result[0], password):
            session["admin"] = username
            session["college_id"] = college_id  # 👈 set karo session me
            return redirect("/dashboard")
        else:
            error = "Invalid credentials. Don't have an account? Create one below."
            return render_template("login.html", error=error, show_register=True, college_id=college_id)

    return render_template("login.html", college_id=session.get("college_id"))




@app.route("/add_admin", methods=["GET", "POST"])
def add_admin():
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password").strip()
        confirm_password = request.form.get("confirm_password").strip()
        college_id = request.form.get("college_id").strip()  # 👈 form se lo

        if not college_id:
            return render_template("add_admin.html", error="College ID missing. Please go back to Start page.")

        if password != confirm_password:
            return render_template("add_admin.html", error="Passwords do not match")

        hashed = generate_password_hash(password)
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO admins (username, password_hash, college_id) VALUES (?, ?, ?)",
                        (username, hashed, college_id))
            conn.commit()
            session["college_id"] = college_id  # 👈 set karo session me
            return redirect("/login?added=1")
        except sqlite3.IntegrityError:
            conn.rollback()
            return render_template("add_admin.html", error="Username already exists for this college.")
        finally:
            conn.close()

    return render_template("add_admin.html")





@app.route("/logout")
def logout():
    session.clear()
    return redirect("/start")

@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    college_id = session.get("college_id")
    if not college_id:
        return redirect("/start")
    
    if request.method == "POST":
        name = request.form.get("name").strip()
        message = request.form.get("message").strip()
        
        if not name or not message:
            return render_template("feedback.html", error="All fields are required")
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO feedback (name, message, college_id) VALUES (?, ?, ?)", (name, message, college_id))
        conn.commit()
        conn.close()
        return redirect("/dashboard?feedback=1")
    return render_template("feedback.html")

@app.route("/feedbacks")
def feedback_list():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT name, message FROM feedback WHERE college_id=? ORDER BY id DESC", (session.get("college_id"),))
    feedbacks = cur.fetchall()
    conn.close()
    return render_template("feedback_list.html", feedbacks=feedbacks)

@app.route("/delete_event/<int:event_id>")
def delete_event(event_id):
    if session.get("role") != "admin":
        return redirect("/start")
    
    college_id = session.get("college_id")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM participants WHERE event_id=? AND college_id=?", (event_id, college_id))
    cur.execute("DELETE FROM events WHERE id=? AND college_id=?", (event_id, college_id))
    conn.commit()
    conn.close()
    
    return redirect("/dashboard?deleted=1")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
