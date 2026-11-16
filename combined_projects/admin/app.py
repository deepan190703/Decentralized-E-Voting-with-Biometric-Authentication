import os
import sqlite3
import base64
from flask import Flask, request, render_template, redirect, url_for, session
# from flask import session, redirect, url_for
from werkzeug.utils import secure_filename
from ecdsa import SigningKey, SECP256k1
import requests
from datetime import datetime, timedelta
import time

app = Flask(__name__)
app.secret_key = "supersecret"

UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Configuration for Admin Auth ---
ADMIN_PASSWORDS = [base64.b64decode("c291cmFqaXRzYW1hbnRh".encode('utf-8')).decode('utf-8'), base64.b64decode("YWthaXNhbWFudGE=".encode('utf-8')).decode('utf-8'), base64.b64decode("YWRtaW4=".encode('utf-8')).decode('utf-8')]

# --- Candidate Key Generator ---
def generate_key_pair():
    private_key = SigningKey.generate(curve=SECP256k1)
    public_key = private_key.get_verifying_key()
    return public_key.to_string().hex(), private_key.to_string().hex()

# --- Route: Admin Login ---
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if all([request.form.get(f"p{i+1}") == ADMIN_PASSWORDS[i] for i in range(3)]):
            session['admin'] = True
            return redirect(url_for("dashboard"))
        else:
            return "Wrong Passwords"
    return render_template("index.html")

# --- Route: Admin Dashboard ---
@app.route("/dashboard")
def dashboard():
    if not session.get('admin'):
        return redirect(url_for("login"))
    return render_template("dashboard.html")

# --- Route: Distribute Coins ---
@app.route("/distribute", methods=["POST"])
def distribute():
    if not session.get('admin'):
        return redirect(url_for("login"))

    PUBLIC_KEY = "17918b20b63a1b75862d2c76ba8890619012e5a77639a2fdfde85f282ef96a2ae738237ecd0b0e7a081a6e1bdf4692f877ba759e4a131b6d5aa977a088680714"  # truncated
    PRIVATE_KEY = base64.b64decode("OTc2YjdhZjI2ODFjMDY5YTIyMzA1NzMzMTkzY2MxZTkxNTM2NTA3ZDA2NzJkYzk3MDVlYWNlNjM0NzQ4YjQ0MQ==".encode('utf-8')).decode('utf-8')  # truncated

    def sign_transaction(sender, receiver, amount, nonce):
        sk = SigningKey.from_string(bytes.fromhex(PRIVATE_KEY), curve=SECP256k1)
        message = f"{sender}{receiver}{amount}{nonce}".encode()
        signature = sk.sign(message).hex()
        return signature

    conn = sqlite3.connect("../voters.db")
    c = conn.cursor()
    c.execute("SELECT public_key FROM voters")
    accounts = c.fetchall()
    conn.close()

    skipped, sent = 0, 0

    for (public_key,) in accounts:
        balance_response = requests.get("http://127.0.0.1:8000/balance", params={"address": public_key})
        balance = balance_response.json().get("balance", 0)

        if balance >= 1:
            skipped += 1
            continue

        nonce_response = requests.get(f"http://127.0.0.1:8000/nonce/{PUBLIC_KEY}")
        nonce = nonce_response.json().get("nonce", 0)
        signature = sign_transaction(PUBLIC_KEY, public_key, 1, nonce)

        tx = {
            "sender": PUBLIC_KEY,
            "receiver": public_key,
            "amount": 1,
            "nonce": nonce,
            "signature": signature
        }
        requests.post("http://127.0.0.1:8000/transaction", json=tx)
        sent += 1
        time.sleep(10)
        continue
    result = f"✅ Sent: {sent}, Skipped: {skipped}"
    return render_template('distribute.html', result=result)

# --- Route: Add Candidate ---
@app.route("/add_candidate", methods=["GET", "POST"])
def add_candidate():
    if not session.get('admin'):
        return redirect(url_for("login"))

    message = None

    if request.method == "POST":
        name = request.form['name']
        party = request.form['party']
        image_file = request.files['image']
        logo_file = request.files['logo']

        image_b64 = base64.b64encode(image_file.read()).decode('utf-8')
        logo_b64 = base64.b64encode(logo_file.read()).decode('utf-8')

        conn = sqlite3.connect("../candidates.db")
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                party TEXT,
                image_base64 TEXT,
                logo_base64 TEXT,
                public_key TEXT UNIQUE,
                private_key TEXT UNIQUE
            )
        """)

        # 🔁 Keep generating until a unique key pair is found
        while True:
            pub, priv = generate_key_pair()

            # Check if public or private key exists
            c.execute("SELECT * FROM candidates WHERE public_key=? OR private_key=?", (pub, priv))
            if not c.fetchone():
                break  # ✅ Unique keys found

        # Save candidate
        c.execute("INSERT INTO candidates (name, party, image_base64, logo_base64, public_key, private_key) VALUES (?, ?, ?, ?, ?, ?)",
                  (name, party, image_b64, logo_b64, pub, priv))
        conn.commit()
        conn.close()

        message = "✅ Candidate added successfully!"

    return render_template("add_candidate.html", message=message)

@app.route("/view_candidates")
def view_candidates():
    if not session.get("admin"):
        return redirect(url_for("login"))
    try:
        conn = sqlite3.connect("../candidates.db")
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM candidates")
    except:
        return "NO DATA" 
    conn = sqlite3.connect("../candidates.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM candidates")
    rows = c.fetchall()
    conn.close()

    candidates = []
    for row in rows:
        candidates.append({
            "name": row["name"],
            "party": row["party"],
            "image": row["image_base64"],
            "logo": row["logo_base64"],
            "public_key": row["public_key"]
        })

    return render_template("view_candidates.html", candidates=candidates)



@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True,port=5002)
