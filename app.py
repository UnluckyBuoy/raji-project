from twilio.rest import Client
from flask import jsonify
from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import datetime
import bcrypt
import os

# Twilio
ACCOUNT_SID = os.getenv("TWILIO_SID")
AUTH_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_NUMBER = "+12315081973"

client = Client(ACCOUNT_SID, AUTH_TOKEN)

# Admin credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

app = Flask(__name__)
app.secret_key = "raji_secret_key"


# ================= DATABASE =================

def init_db():
    conn = sqlite3.connect("alerts.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT,
            location TEXT,
            map_link TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()


# ================= HOME =================

@app.route("/")
def home():
    conn = sqlite3.connect("alerts.db")
    cursor = conn.cursor()
    cursor.execute("SELECT time FROM alerts ORDER BY id DESC LIMIT 1")
    last_alert = cursor.fetchone()
    conn.close()

    return render_template("index.html", last_alert=last_alert)


# ================= ALERT =================

@app.route("/alert", methods=["POST"])
def alert():

    location = request.form.get("location")
    if not location:
        return redirect(url_for("home"))

    time_now = datetime.datetime.now()
    map_link = f"https://www.google.com/maps?q={location}"

    conn = sqlite3.connect("alerts.db")
    cursor = conn.cursor()

    # Anti-spam
    cursor.execute("SELECT time FROM alerts ORDER BY id DESC LIMIT 1")
    last_alert = cursor.fetchone()

    if last_alert:
        last_time = datetime.datetime.fromisoformat(last_alert[0])
        seconds_passed = (time_now - last_time).total_seconds()

        if seconds_passed < 30:
            remaining = int(30 - seconds_passed)
            flash(f"Please wait {remaining} seconds before sending another alert.")
            conn.close()
            return redirect(url_for("home"))

    # Insert new alert
    cursor.execute(
        "INSERT INTO alerts (time, location, map_link) VALUES (?, ?, ?)",
        (str(time_now), location, map_link)
    )
    conn.commit()

    # Get contacts
    cursor.execute("SELECT phone FROM contacts")
    contacts = cursor.fetchall()
    conn.close()

    # Send SMS
    message = f"🚨 Emergency Alert!\nLocation: {map_link}"

    for contact in contacts:
        try:
            client.messages.create(
                body=message,
                from_=TWILIO_NUMBER,
                to=contact[0]
            )
        except Exception as e:
            print("SMS Error:", e)

    flash("Emergency Alert Sent to All Contacts!")
    return redirect(url_for("home"))


# ================= ADMIN =================

@app.route("/admin")
def admin():
    if not session.get("admin"):
        return redirect(url_for("login"))

    conn = sqlite3.connect("alerts.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM alerts ORDER BY id DESC")
    alerts = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM alerts")
    total_alerts = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM alerts WHERE date(time)=date('now')")
    today_alerts = cursor.fetchone()[0]

    cursor.execute("SELECT time FROM alerts ORDER BY id DESC LIMIT 1")
    last_alert = cursor.fetchone()
    last_alert_time = last_alert[0] if last_alert else "No alerts yet"

    cursor.execute("""
        SELECT date(time), COUNT(*)
        FROM alerts
        GROUP BY date(time)
        ORDER BY date(time) ASC
    """)
    chart_data = cursor.fetchall()

    conn.close()

    return render_template(
        "admin.html",
        alerts=alerts,
        total_alerts=total_alerts,
        today_alerts=today_alerts,
        last_alert_time=last_alert_time,
        chart_data=chart_data
    )


# ================= LOGIN =================

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Use SAME credentials everywhere
        if username == ADMIN_USERNAME and password == "admin123":
            session["admin"] = True   # 🔥 THIS WAS MISSING
            return jsonify({
                "status": "success",
                "redirect": "/admin"
            })
        else:
            return jsonify({
                "status": "error"
            })

    return render_template("login.html")

# ================= LOGOUT =================

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("login"))


# ================= DELETE =================

@app.route("/delete/<int:alert_id>")
def delete_alert(alert_id):
    if not session.get("admin"):
        return redirect(url_for("login"))

    conn = sqlite3.connect("alerts.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM alerts WHERE id=?", (alert_id,))
    conn.commit()
    conn.close()

    flash("Alert deleted successfully!")
    return redirect(url_for("admin"))


# ================= CONTACTS =================

@app.route("/contacts", methods=["GET", "POST"])
def contacts():
    conn = sqlite3.connect("alerts.db")
    cursor = conn.cursor()

    if request.method == "POST":
        name = request.form["name"]
        phone = request.form["phone"]
        cursor.execute(
            "INSERT INTO contacts (name, phone) VALUES (?, ?)",
            (name, phone)
        )
        conn.commit()

    cursor.execute("SELECT * FROM contacts")
    contacts = cursor.fetchall()
    conn.close()

    return render_template("contacts.html", contacts=contacts)


# ================= CONTACTS DELETE =================

@app.route("/delete_contact/<int:contact_id>")
def delete_contact(contact_id):
    conn = sqlite3.connect("alerts.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM contacts WHERE id=?", (contact_id,))
    conn.commit()
    conn.close()
    flash("Contact deleted successfully!")
    return redirect(url_for("contacts"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)