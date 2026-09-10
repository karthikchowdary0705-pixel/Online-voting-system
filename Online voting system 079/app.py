from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "cloud_voting_secret_key"

DATABASE = "voting.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            has_voted INTEGER DEFAULT 0
        )
    """)

    # Candidates table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            party TEXT NOT NULL,
            votes INTEGER DEFAULT 0
        )
    """)

    # Create demo candidates if table is empty
    cursor.execute("SELECT COUNT(*) FROM candidates")
    count = cursor.fetchone()[0]

    if count == 0:
        candidates = [
            ("Candidate A", "Progress Party"),
            ("Candidate B", "Development Party"),
            ("Candidate C", "People's Party")
        ]

        cursor.executemany(
            "INSERT INTO candidates (name, party) VALUES (?, ?)",
            candidates
        )

    conn.commit()
    conn.close()


@app.route("/")
def index():
    return render_template("index.html")


# ---------------- REGISTER ----------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"].strip()
        password = request.form["password"]

        if not username or not password:
            flash("Please enter username and password.")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        conn = get_db()

        try:
            conn.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, hashed_password)
            )

            conn.commit()
            flash("Registration successful. Please login.")

            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            flash("Username already exists.")

        finally:
            conn.close()

    return render_template("register.html")


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()

        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(user["password"], password):

            session["user_id"] = user["id"]
            session["username"] = user["username"]

            return redirect(url_for("vote"))

        flash("Invalid username or password.")

    return render_template("login.html")


# ---------------- VOTING PAGE ----------------

@app.route("/vote")
def vote():

    if "user_id" not in session:
        flash("Please login first.")
        return redirect(url_for("login"))

    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    candidates = conn.execute(
        "SELECT * FROM candidates"
    ).fetchall()

    conn.close()

    if user["has_voted"]:
        return redirect(url_for("result"))

    return render_template(
        "vote.html",
        candidates=candidates,
        username=session["username"]
    )


# ---------------- CAST VOTE ----------------

@app.route("/cast_vote", methods=["POST"])
def cast_vote():

    if "user_id" not in session:
        return redirect(url_for("login"))

    candidate_id = request.form.get("candidate")

    if not candidate_id:
        flash("Please select a candidate.")
        return redirect(url_for("vote"))

    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    # Prevent multiple votes
    if user["has_voted"]:
        conn.close()
        flash("You have already voted.")
        return redirect(url_for("result"))

    # Check candidate
    candidate = conn.execute(
        "SELECT * FROM candidates WHERE id = ?",
        (candidate_id,)
    ).fetchone()

    if not candidate:
        conn.close()
        flash("Invalid candidate.")
        return redirect(url_for("vote"))

    # Increase candidate vote count
    conn.execute(
        "UPDATE candidates SET votes = votes + 1 WHERE id = ?",
        (candidate_id,)
    )

    # Mark user as voted
    conn.execute(
        "UPDATE users SET has_voted = 1 WHERE id = ?",
        (session["user_id"],)
    )

    conn.commit()
    conn.close()

    flash("Your vote has been recorded successfully.")

    return redirect(url_for("result"))


# ---------------- RESULTS ----------------

@app.route("/result")
def result():

    conn = get_db()

    candidates = conn.execute("""
        SELECT * FROM candidates
        ORDER BY votes DESC
    """).fetchall()

    total_votes = conn.execute(
        "SELECT SUM(votes) FROM candidates"
    ).fetchone()[0]

    conn.close()

    if total_votes is None:
        total_votes = 0

    return render_template(
        "result.html",
        candidates=candidates,
        total_votes=total_votes
    )


# ---------------- ADMIN ----------------

@app.route("/admin")
def admin():

    conn = get_db()

    candidates = conn.execute(
        "SELECT * FROM candidates ORDER BY votes DESC"
    ).fetchall()

    users = conn.execute(
        "SELECT id, username, has_voted FROM users"
    ).fetchall()

    conn.close()

    return render_template(
        "admin.html",
        candidates=candidates,
        users=users
    )


# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():

    session.clear()

    flash("You have been logged out.")

    return redirect(url_for("index"))


if __name__ == "__main__":
    init_db()

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )