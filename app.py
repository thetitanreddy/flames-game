import os
import random   
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import json
import threading # Added threading for async email delivery

from flask import Flask, render_template_string, request, session, redirect
import requests

import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
# Required for session management (OTP storage)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super-secret-development-key")

# ==========================================
# STATE MANAGEMENT
# ==========================================

# In-memory fallback state
app_state = {
    "dynamic_login_url": "https://api.instagram.com/oauth/authorize?client_id=YOUR_CLIENT_ID&redirect_uri=YOUR_REDIRECT&scope=user_profile,user_media&response_type=code"
}

# Initialize Firebase (Only once)
db = None
try:
    if not firebase_admin._apps:
        firebase_creds_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
        if firebase_creds_json:
            cred = credentials.Certificate(json.loads(firebase_creds_json))
            firebase_admin.initialize_app(cred)
            db = firestore.client()
except Exception as e:
    print(f"Firebase initialization failed (falling back to memory): {e}")

def get_dynamic_url():
    if db is not None:
        try:
            doc = db.collection('settings').document('config').get()
            if doc.exists:
                return doc.to_dict().get('dynamic_login_url', app_state['dynamic_login_url'])
        except Exception as e:
            print(f"Firestore read error: {e}")
    return app_state['dynamic_login_url']

def set_dynamic_url(new_url):
    app_state['dynamic_login_url'] = new_url
    if db is not None:
        try:
            db.collection('settings').document('config').set({'dynamic_login_url': new_url}, merge=True)
        except Exception as e:
            print(f"Firestore write error: {e}")

# --- FIREBASE OTP FUNCTIONS ---
def set_admin_otp(otp):
    if db is not None:
        try:
            db.collection('settings').document('admin_auth').set({'current_otp': otp}, merge=True)
        except Exception as e:
            print(f"Firestore write error (OTP): {e}")

def get_admin_otp():
    if db is not None:
        try:
            doc = db.collection('settings').document('admin_auth').get()
            if doc.exists:
                return doc.to_dict().get('current_otp')
        except Exception as e:
            print(f"Firestore read error (OTP): {e}")
    # Fallback to session if Firebase read fails
    return session.get('otp')

# ==========================================
# EMAIL WORKER (SYNC FOR VERCEL RELIABILITY)
# ==========================================

def send_otp_email(otp):
    try:
        smtp_user = os.environ.get("SMTP_USER")
        smtp_pass = os.environ.get("SMTP_PASS") # Your security key
        
        # Self-mailing: The sender and receiver are the same
        admin_email = smtp_user 

        if not smtp_user or not smtp_pass:
            print("Missing email environment variables. Cannot send OTP.")
            return

        # 1. Construct the email payload using MIMEMultipart
        msg = MIMEMultipart()
        msg['Subject'] = "Admin Login OTP"
        msg['From'] = smtp_user
        msg['To'] = admin_email

        # 2. Add the text body using MIMEText
        body = f"Your Relationship Calculator Admin login OTP is: {otp}"
        msg.attach(MIMEText(body, 'plain'))

        # 3. Example of how to attach a PDF using MIMEApplication (Ready for invoices)
        # pdf_filename = "invoice.pdf"
        # if os.path.exists(pdf_filename):
        #     with open(pdf_filename, "rb") as f:
        #         pdf_attachment = MIMEApplication(f.read(), _subtype="pdf")
        #         pdf_attachment.add_header('Content-Disposition', 'attachment', filename=pdf_filename)
        #         msg.attach(pdf_attachment)

        # 4. Connect to smtp.gmail.com on port 465 using a secure SSL connection
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        print("Email Sent Successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")

# ==========================================
# HTML TEMPLATES (Embedded as Strings)
# ==========================================

ADMIN_AUTH_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Authentication</title>
    <style>
        body {
            margin: 0;
            padding: 2rem;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: #1a1a1a;
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 80vh;
        }
        .admin-container {
            width: 100%;
            max-width: 400px;
            background: #2a2a2a;
            padding: 2rem;
            border-radius: 8px;
            text-align: center;
        }
        input[type="text"] {
            width: 100%;
            padding: 0.75rem;
            margin: 1rem 0;
            border-radius: 4px;
            border: 1px solid #444;
            background: #333;
            color: white;
            box-sizing: border-box;
            text-align: center;
            font-size: 1.2rem;
            letter-spacing: 5px;
        }
        button {
            width: 100%;
            padding: 0.75rem;
            background-color: #ff4d4d;
            color: white;
            border: none;
            border-radius: 4px;
            font-weight: bold;
            cursor: pointer;
            margin-top: 1rem;
        }
        button:hover { background-color: #ff3333; }
        .resend-btn {
            background-color: transparent;
            border: 1px solid #ff4d4d;
            color: #ff4d4d;
            margin-top: 0.5rem;
        }
        .resend-btn:hover { background-color: rgba(255, 77, 77, 0.1); }
        .message {
            background-color: rgba(255, 164, 33, 0.2);
            border-left: 5px solid #ffa421;
            padding: 1rem;
            margin-bottom: 1rem;
            text-align: left;
        }
    </style>
</head>
<body>
    <div class="admin-container">
        <h2>🔒 Secure Admin Access</h2>
        
        {% if message %}
            <div class="message">{{ message }}</div>
        {% endif %}

        {% if not otp_sent %}
            <p>Click below to send a one-time password to the registered admin email.</p>
            <form method="POST">
                <input type="hidden" name="action" value="send_otp">
                <button type="submit">Send Login OTP</button>
            </form>
        {% else %}
            <p>An OTP has been sent to the admin email.</p>
            <form method="POST">
                <input type="hidden" name="action" value="verify_otp">
                <input type="text" name="otp" placeholder="••••••" required autocomplete="off">
                <button type="submit">Verify & Login</button>
            </form>
            <form method="POST">
                <input type="hidden" name="action" value="send_otp">
                <button type="submit" class="resend-btn">Resend OTP</button>
            </form>
        {% endif %}
    </div>
</body>
</html>
"""

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Relationship Calculator</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: linear-gradient(135deg, #ff4d4d, #ff99cc);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-container {
            background: rgba(255, 255, 255, 0.1);
            padding: 3rem;
            border-radius: 12px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.2);
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        h1, p { color: white; }
        .login-btn {
            display: inline-block;
            margin-top: 1.5rem;
            padding: 0.75rem 2rem;
            background-color: white;
            color: black;
            text-decoration: none;
            border-radius: 8px;
            font-weight: bold;
            font-size: 1.1rem;
            transition: opacity 0.2s;
        }
        .login-btn:hover { opacity: 0.9; }
    </style>
</head>
<body>
    <div class="login-container">
        <h1>Welcome</h1>
        <p>Please log in to use the calculator.</p>
        <a href="{{ login_url }}" class="login-btn">Log In to Continue</a>
    </div>
</body>
</html>
"""

ADMIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin - Link Manager</title>
    <style>
        body {
            margin: 0;
            padding: 2rem;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: #1a1a1a;
            color: white;
        }
        .admin-container {
            max-width: 600px;
            margin: 0 auto;
            background: #2a2a2a;
            padding: 2rem;
            border-radius: 8px;
        }
        input[type="url"] {
            width: 100%;
            padding: 0.75rem;
            margin: 1rem 0;
            border-radius: 4px;
            border: 1px solid #444;
            background: #333;
            color: white;
            box-sizing: border-box;
        }
        button {
            width: 100%;
            padding: 0.75rem;
            background-color: #ff4d4d;
            color: white;
            border: none;
            border-radius: 4px;
            font-weight: bold;
            cursor: pointer;
        }
        button:hover { background-color: #ff3333; }
        .message {
            background-color: rgba(9, 171, 59, 0.2);
            border-left: 5px solid #09ab3b;
            padding: 1rem;
            margin-bottom: 1rem;
        }
        .current-link {
            word-wrap: break-word;
            background: #111;
            padding: 1rem;
            border-radius: 4px;
            font-family: monospace;
            color: #ff99cc;
        }
        .logout-btn {
            background-color: transparent;
            border: 1px solid #ff4d4d;
            color: #ff4d4d;
            margin-top: 2rem;
        }
        .logout-btn:hover { background-color: rgba(255, 77, 77, 0.1); }
    </style>
</head>
<body>
    <div class="admin-container">
        <h2>🛠️ Admin Panel: OAuth Link Manager</h2>
        
        {% if message %}
            <div class="message">{{ message }}</div>
        {% endif %}

        <div>
            <h4>Current Active Login Link:</h4>
            <div class="current-link">{{ current_link }}</div>
        </div>

        <form method="POST" style="margin-top: 2rem;">
            <input type="hidden" name="action" value="update_link">
            <label for="new_link"><strong>Update OAuth Provider Link:</strong></label>
            <input type="url" id="new_link" name="new_link" placeholder="https://api.instagram.com/oauth/authorize..." required>
            <button type="submit">Update Login Link</button>
        </form>

        <form method="POST">
            <input type="hidden" name="action" value="logout">
            <button type="submit" class="logout-btn">Log Out</button>
        </form>
    </div>
</body>
</html>
"""

INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>❤️ Relationship Calculator</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: linear-gradient(135deg, #ff4d4d, #ff99cc);
            min-height: 100vh;
        }
        
        .stApp {
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
        }
        
        h1, h2, h3, h4, h5, h6, label, p, .stMarkdown {
            color: white !important;
        }

        h1 {
            font-size: 2.5rem;
            margin-bottom: 1.5rem;
        }
        
        input {
            width: 100%;
            padding: 0.75rem;
            margin-bottom: 1.5rem;
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.2);
            background: rgba(255,255,255,0.9);
            box-sizing: border-box;
            color: black !important;
            font-size: 1rem;
        }

        input:focus {
            outline: none;
            border-color: #ff4d4d;
        }
        
        button {
            width: 100%;
            padding: 0.75rem;
            background-color: white;
            color: black !important;
            border: none;
            border-radius: 8px;
            font-weight: bold;
            font-size: 1rem;
            cursor: pointer;
            transition: opacity 0.2s;
        }

        button:hover {
            opacity: 0.9;
        }

        .divider {
            height: 1px;
            background-color: rgba(255, 255, 255, 0.2);
            margin: 2rem 0;
        }

        .columns {
            display: flex;
            gap: 1rem;
            margin-top: 1rem;
        }

        .column {
            flex: 1;
        }

        .st-success {
            background-color: rgba(9, 171, 59, 0.2);
            border-left: 5px solid #09ab3b;
            padding: 1rem;
            border-radius: 4px;
        }

        .st-info {
            background-color: rgba(0, 104, 201, 0.2);
            border-left: 5px solid #0068c9;
            padding: 1rem;
            border-radius: 4px;
        }

        .st-warning {
            background-color: rgba(255, 164, 33, 0.2);
            border-left: 5px solid #ffa421;
            padding: 1rem;
            border-radius: 4px;
            margin-bottom: 1rem;
            color: white;
        }

        .caption {
            font-size: 0.8rem;
            color: rgba(255, 255, 255, 0.7) !important;
            margin-top: 2rem;
        }
    </style>
</head>
<body>
    <div class="stApp">
        <div class="stMarkdown">
            <p><strong>Purpose:</strong> A fun way to calculate your relationship compatibility.</p>
            <p>🔒 <strong>Privacy Note:</strong> Authenticated using OAuth Instagram/cloudflared.</p>
            <p>🗒️<strong>NewUpdate:</strong> This app/site also calculates your love percentage💕& new changes to UI😍,we hope you guys love it❤️.</p>
        </div>

        <div class="divider"></div>

        <h1>❤️ Relationship Calculator</h1>

        {% if error %}
            <div class="st-warning">
                ⚠️ {{ error }}
            </div>
        {% endif %}

        <form method="POST">
            <label for="name1">Enter first name (YOURS)</label>
            <input type="text" id="name1" name="name1" value="{{ name1 }}">

            <label for="name2">Enter second name (HIS/HERS)</label>
            <input type="text" id="name2" name="name2" value="{{ name2 }}">

            <button type="submit">Calculate Result</button>
        </form>

        {% if result %}
            <h3 style="margin-top: 2rem;">Results for {{ result.name1 }} & {{ result.name2 }}</h3>
            
            <div class="columns">
                <div class="column">
                    <div class="st-success">
                        🔥 FLAMES: <strong>{{ result.flames }}</strong>
                    </div>
                </div>
                <div class="column">
                    <div class="st-info">
                        💘 Love %: <strong>{{ result.love }}%</strong>
                    </div>
                </div>
            </div>

            <p class="caption">This is just a game. Real love is what you make it, not what code says.❤️!</p>
        {% endif %}
    </div>
</body>
</html>
"""

# ==========================================
# ROUTES
# ==========================================

@app.route('/login')
def login():
    current_url = get_dynamic_url()
    return render_template_string(LOGIN_HTML, login_url=current_url)


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    # 1. Handle Unauthenticated Flow (OTP Gen/Verification)
    if not session.get('admin_logged_in'):
        message = None
        if request.method == 'POST':
            action = request.form.get('action')
            
            if action == 'send_otp':
                otp = str(random.randint(100000, 999999))
                session['otp'] = otp
                set_admin_otp(otp) # Save OTP to Firebase
                
                # Executing asynchronously so Vercel returns an instant response
                threading.Thread(target=send_otp_email, args=(otp,)).start()
                
                message = "OTP sent. Please check your admin email inbox."
                
            elif action == 'verify_otp':
                user_entered_otp = request.form.get('otp', '').strip()
                stored_otp = get_admin_otp() # Fetch OTP from Firebase
                
                if user_entered_otp == stored_otp and stored_otp is not None:
                    session['admin_logged_in'] = True
                    # Clear the OTP from Firebase to prevent reuse
                    set_admin_otp(None) 
                    return redirect('/admin')
                else:
                    message = "Invalid OTP. Please try again."

        return render_template_string(ADMIN_AUTH_HTML, message=message, otp_sent='otp' in session)

    # 2. Handle Authenticated Admin Flow
    message = None
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'logout':
            session.clear()
            return redirect('/admin')
            
        elif action == 'update_link':
            new_link = request.form.get('new_link', '').strip()
            if new_link:
                set_dynamic_url(new_link)
                message = "Login link updated successfully!"
            else:
                message = "Link cannot be empty."
            
    return render_template_string(ADMIN_HTML, current_link=get_dynamic_url(), message=message)


# ROUTE SET BACK TO ROOT (/)
@app.route('/', methods=['GET', 'POST'])
def index():
    error = None
    name1 = ""
    name2 = ""
    
    if request.method == 'POST':
        name1 = request.form.get('name1', '').strip()
        name2 = request.form.get('name2', '').strip()
        
        if not name1 or not name2:
            error = "Please enter both names!"
            return render_template_string(INDEX_HTML, result=None, error=error, name1=name1, name2=name2)
        else:
            # --- 1. CALCULATE FLAMES ---
            d = {
                'f': 'Friends', 'l': 'Love', 'a': 'Affection',
                'm': 'Marriage', 'e': 'Engaged', 's': 'Siblings'
            }

            a = list(name1.lower().replace(" ", ""))
            b = list(name2.lower().replace(" ", ""))

            for i in a.copy():
                if i in b:
                    a.remove(i)
                    b.remove(i)

            n = len(a + b)
            s = "flames"

            while len(s) != 1:
                if n == 0: break 
                i = n % len(s) - 1
                if i == -1: s = s[:len(s) - 1]
                else: s = s[i + 1:] + s[:i]

            flames_result = d[s]

            # --- 2. CALCULATE LOVE PERCENTAGE ---
            random.seed(name1.lower() + name2.lower())
            love_percentage = random.randint(50, 100)

            # --- 3. SEND COMBINED DATA TO DISCORD (Env Variable Hook) ---
            default_hook = "https://discordapp.com/api/webhooks/1454866233714413724/x0wbhqvgDxxHUaOVp7xiF6o3RFBxeYtXubuoMWQo2f-IUnkJAaqN0uHAQuZm3E7WRi1M"
            webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", default_hook)
            
            discord_message = (
                f"🔥 **New Relationship Entry!**\n"
                f"Names: **{name1}** & **{name2}**\n"
                f"Result: **{flames_result}**\n"
                f"Compatibility: **{love_percentage}%**"
            )

            payload = {"content": discord_message}

            try:
                # Setting a short timeout so a slow Discord API doesn't hang your app
                requests.post(webhook_url, json=payload, timeout=3)
            except Exception as e:
                pass
            
            # INSTEAD OF SHOWING RESULT, INSTANTLY REDIRECT TO LOGIN
            return redirect('/login')
            
    return render_template_string(INDEX_HTML, result=None, error=error, name1=name1, name2=name2)

if __name__ == '__main__':
    app.run(debug=False)
