import os
from flask import Flask, render_template, request, redirect, session, url_for, send_file, flash
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import time
from dotenv import load_dotenv
import mysql.connector
import pytz
import requests
import io
import random

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret')

# Define India timezone
IST = pytz.timezone('Asia/Kolkata')

#----------------DATABASE CONNECTION 1 -----------------------------
def get_db_connection():
    host = os.getenv("DB_HOST")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    database = os.getenv("DB_NAME")
    port = os.getenv("DB_PORT")
    ssl_ca = os.getenv("SSL_CA")

    if not all([host, user, password, database, port, ssl_ca]):
        raise ValueError("❌ Missing one or more DB environment variables! for db 1 connection")

    return mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        port=int(port),
        ssl_ca=ssl_ca
    )

#----------------DATABASE CONNECTION 2 -----------------------------
def get_db_connection2():
    host = os.getenv("DB_HOST2")
    user = os.getenv("DB_USER2")
    password = os.getenv("DB_PASSWORD2")
    database = os.getenv("DB_NAME2")
    port = os.getenv("DB_PORT2")
    ssl_ca = os.getenv("SSL_CA2")

    if not all([host, user, password, database, port, ssl_ca]):
        raise ValueError("❌ Missing one or more DB environment variables! for db 2 connection")

    return mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        port=int(port),
        ssl_ca=ssl_ca,
        use_pure=True          # <-- REQUIRED for correct BLOB handling
    )

#-----------------current date (India timezone)----------------------

def get_current_ist_time():
    return datetime.now(IST)

def format_ist_time(dt):
    # Format datetime to string in IST
    if dt.tzinfo is None:
        dt = IST.localize(dt)
    return dt.strftime("%d-%m-%Y %H:%M")

# Update current_date to use IST
now_date = get_current_ist_time()
current_date = format_ist_time(now_date)

#----------------EMAIL-----------------------------
def send_mail(subject, body):
        # Environment variables
        try:
            api_key = os.getenv("BREVO_API_KEY")
            sender = os.getenv("EMAIL_USER")
            receiver = os.getenv("EMAIL")

            # Safety check
            if not all([api_key, sender, receiver]):
                missing = [k for k, v in {
                    "BREVO_API_KEY": api_key,
                    "EMAIL_USER": sender,
                    "RECEIVER_EMAIL": receiver
                }.items() if not v]
                return f"Missing environment variable(s): {', '.join(missing)}", 500

            # Prepare the email payload
            payload = {
                "sender": {"email": sender},
                "to": [{"email": receiver}],
                "subject": subject,
                "textContent": body
            }

            response = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={
                    "accept": "application/json",
                    "api-key": api_key,
                    "content-type": "application/json"
                },
                json=payload
            )

            # Handle response
            if response.status_code == 201:
                return "✅ Email sent successfully!"
            else:
                return f"❌ Failed to send: {response.status_code} - {response.text}", 500
        except Exception as e:
            return f"Unexpected error: {e}", 500

#--------------------------- SEND UNCOMPLETE TASK -------------------------------
def remind_tasks():
    try:
        # Connect to DB and get all incomplete tasks
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT task FROM task WHERE is_complete = %s", ("False",))
        tasks = cur.fetchall()
        cur.close()
        conn.close()
        
        if not tasks:
            body = create_email_template([])
            subject = "✓ All Tasks Complete!"
        else:
            task_list = [task['task'] for task in tasks]
            body = create_email_template(task_list)
            subject = f"📌 {len(task_list)} Task{'s' if len(task_list) > 1 else ''} Pending"
            
    except mysql.connector.Error as err:
        return f"Database error: {err}", 500
    
    print("Sending email...")
    result = send_mail(subject, body)
    return result


def create_email_template(tasks):
    """Create a clean, mobile-friendly HTML email template"""
    # Generate task items HTML
    if not tasks:
        content_html = '''
        <tr>
            <td style="padding: 40px 20px; text-align: center;">
                <div style="font-size: 80px; margin-bottom: 20px;">🎉</div>
                <h2 style="color: #10b981; font-size: 26px; margin: 0 0 10px 0; font-weight: 700;">All Done!</h2>
                <p style="color: #6b7280; font-size: 16px; margin: 0; line-height: 1.5;">You've completed all your tasks. Great job!</p>
            </td>
        </tr>
        '''
    else:
        task_items = ""
        for idx, task in enumerate(tasks, 1):
            task_items += f'''
            <tr>
                <td style="padding: 8px 0;">
                    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 12px; border: 2px solid #e5e7eb;">
                        <tr>
                            <td style="padding: 20px;">
                                <table width="100%" cellpadding="0" cellspacing="0">
                                    <tr>
                                        <td width="45" valign="top">
                                            <div style="background-color: #3b82f6; color: #ffffff; width: 36px; height: 36px; border-radius: 8px; text-align: center; line-height: 36px; font-weight: 700; font-size: 18px;">{idx}</div>
                                        </td>
                                        <td valign="top" style="padding-left: 15px;">
                                            <p style="margin: 0; color: #111827; font-size: 16px; line-height: 1.6; font-weight: 500;">{task}</p>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
            '''
        
        content_html = f'''
        <tr>
            <td style="padding: 10px 0 20px 0;">
                <h2 style="color: #111827; font-size: 22px; margin: 0; font-weight: 700; padding-bottom: 5px;">Your Tasks</h2>
                <p style="color: #6b7280; font-size: 14px; margin: 0;">{len(tasks)} task{'s' if len(tasks) > 1 else ''} waiting for you</p>
            </td>
        </tr>
        <tr>
            <td>
                <table width="100%" cellpadding="0" cellspacing="0">
                    {task_items}
                </table>
            </td>
        </tr>
        '''
    
    # Complete HTML template - Ultra clean and mobile-optimized
    html_template = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="X-UA-Compatible" content="IE=edge">
        <title>Task Update</title>
        <style type="text/css">
            body {{
                margin: 0 !important;
                padding: 0 !important;
                -webkit-text-size-adjust: 100% !important;
                -ms-text-size-adjust: 100% !important;
                -webkit-font-smoothing: antialiased !important;
            }}
            table {{
                border-collapse: collapse !important;
                mso-table-lspace: 0pt !important;
                mso-table-rspace: 0pt !important;
            }}
            img {{
                border: 0 !important;
                outline: none !important;
            }}
            p, h1, h2 {{
                padding: 0 !important;
                margin: 0 !important;
            }}
            @media only screen and (max-width: 600px) {{
                .container {{
                    width: 100% !important;
                }}
                .mobile-padding {{
                    padding: 20px !important;
                }}
            }}
        </style>
    </head>
    <body style="margin: 0; padding: 0; background-color: #f3f4f6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f3f4f6;">
            <tr>
                <td align="center" style="padding: 20px 10px;">
                    <table class="container" width="600" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px; width: 100%; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07);">
                        
                        <!-- Header Section -->
                        <tr>
                            <td align="center" style="background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); padding: 40px 20px;">
                                <table cellpadding="0" cellspacing="0" border="0">
                                    <tr>
                                        <td align="center">
                                            <div style="background-color: rgba(255, 255, 255, 0.2); width: 70px; height: 70px; border-radius: 50%; display: inline-block; text-align: center; line-height: 70px; margin-bottom: 15px;">
                                                <span style="font-size: 36px;">✓</span>
                                            </div>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td align="center">
                                            <h1 style="color: #ffffff; font-size: 28px; font-weight: 700; margin: 0;">Task Manager</h1>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td align="center" style="padding-top: 8px;">
                                            <p style="color: #dbeafe; font-size: 15px; margin: 0;">Your Daily Summary</p>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                        
                        <!-- Main Content -->
                        <tr>
                            <td class="mobile-padding" style="padding: 35px 30px;">
                                <table width="100%" cellpadding="0" cellspacing="0" border="0">
                                    <tr>
                                        <td>
                                            <p style="color: #374151; font-size: 16px; line-height: 1.6; margin: 0 0 5px 0;">Hello! 👋</p>
                                            <p style="color: #6b7280; font-size: 15px; line-height: 1.6; margin: 0 0 30px 0;">Here's your task update for today.</p>
                                        </td>
                                    </tr>
                                    
                                    {content_html}
                                    
                                    <tr>
                                        <td align="center" style="padding-top: 35px;">
                                            <table cellpadding="0" cellspacing="0" border="0">
                                                <tr>
                                                    <td align="center" style="background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); border-radius: 10px; box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);">
                                                        <a href="https://deepti.onrender.com/" style="display: block; color: #ffffff; text-decoration: none; padding: 15px 45px; font-weight: 600; font-size: 16px;">Open Dashboard</a>
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td align="center" style="background-color: #f9fafb; padding: 30px 20px; border-top: 1px solid #e5e7eb;">
                                <table cellpadding="0" cellspacing="0" border="0">
                                    <tr>
                                        <td align="center">
                                            <p style="color: #6b7280; font-size: 14px; margin: 0 0 12px 0; line-height: 1.5;">Stay productive and achieve your goals! 🚀</p>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td align="center">
                                            <p style="color: #9ca3af; font-size: 12px; margin: 0; line-height: 1.6;">
                                                © 2024 Task Manager. All rights reserved.<br>
                                                This is an automated email.
                                            </p>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td align="center" style="padding-top: 15px;">
                                            <a href="#" style="color: #9ca3af; text-decoration: none; font-size: 12px; padding: 0 8px;">Help</a>
                                            <span style="color: #d1d5db;">•</span>
                                            <a href="#" style="color: #9ca3af; text-decoration: none; font-size: 12px; padding: 0 8px;">Settings</a>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                        
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    '''
    return html_template


#---------------------------------------- SEND REMINDER FOR IPPB LOGIN ----------------------------------------

def ippb_login_reminder():
    subject = "⚠️ Urgent: Login Required - Account Deactivation Warning"
    
    # HTML Email Body
    body = '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="X-UA-Compatible" content="IE=edge">
        <title>Account Reminder</title>
        <style type="text/css">
            body {
                margin: 0 !important;
                padding: 0 !important;
                -webkit-text-size-adjust: 100% !important;
                -ms-text-size-adjust: 100% !important;
                -webkit-font-smoothing: antialiased !important;
            }
            table {
                border-collapse: collapse !important;
                mso-table-lspace: 0pt !important;
                mso-table-rspace: 0pt !important;
            }
            @media only screen and (max-width: 600px) {
                .container {
                    width: 100% !important;
                }
                .mobile-padding {
                    padding: 20px !important;
                }
            }
        </style>
    </head>
    <body style="margin: 0; padding: 0; background-color: #f3f4f6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f3f4f6;">
            <tr>
                <td align="center" style="padding: 20px 10px;">
                    <table class="container" width="600" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px; width: 100%; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07);">
                        
                        <!-- Header Section -->
                        <tr>
                            <td align="center" style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); padding: 40px 20px;">
                                <table width="100%" cellpadding="0" cellspacing="0" border="0">
                                    <tr>
                                        <td align="center" style="padding-bottom: 15px;">
                                            <table cellpadding="0" cellspacing="0" border="0" style="margin: 0 auto;">
                                                <tr>
                                                    <td align="center" style="background-color: rgba(255, 255, 255, 0.2); width: 70px; height: 70px; border-radius: 50%; text-align: center; vertical-align: middle;">
                                                        <span style="font-size: 36px; line-height: 70px; display: inline-block;">⚠️</span>
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td align="center">
                                            <h1 style="color: #ffffff; font-size: 28px; font-weight: 700; margin: 0;">Urgent Reminder</h1>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td align="center" style="padding-top: 8px;">
                                            <p style="color: #fecaca; font-size: 15px; margin: 0;">Action Required</p>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                        
                        <!-- Main Content -->
                        <tr>
                            <td class="mobile-padding" style="padding: 35px 30px;">
                                <table width="100%" cellpadding="0" cellspacing="0" border="0">
                                    <tr>
                                        <td>
                                            <p style="color: #374151; font-size: 16px; line-height: 1.6; margin: 0 0 5px 0;">Hello! 👋</p>
                                            <p style="color: #6b7280; font-size: 15px; line-height: 1.6; margin: 0 0 30px 0;">This is an important reminder about your account.</p>
                                        </td>
                                    </tr>
                                    
                                    <!-- Warning Box -->
                                    <tr>
                                        <td style="padding: 0 0 30px 0;">
                                            <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #fef2f2; border-left: 4px solid #ef4444; border-radius: 8px;">
                                                <tr>
                                                    <td style="padding: 25px;">
                                                        <table width="100%" cellpadding="0" cellspacing="0">
                                                            <tr>
                                                                <td>
                                                                    <h2 style="color: #dc2626; font-size: 20px; margin: 0 0 12px 0; font-weight: 700;">⚠️ Action Required</h2>
                                                                    <p style="color: #991b1b; font-size: 16px; line-height: 1.6; margin: 0;">
                                                                        Please log in to your <strong>IPPP Account App</strong> as soon as possible. Failure to log in may result in your account being deactivated.
                                                                    </p>
                                                                </td>
                                                            </tr>
                                                        </table>
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                    
                                    <!-- Info Box -->
                                    <tr>
                                        <td style="padding: 0 0 30px 0;">
                                            <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f0f9ff; border-radius: 8px;">
                                                <tr>
                                                    <td style="padding: 20px;">
                                                        <h3 style="color: #0369a1; font-size: 16px; margin: 0 0 10px 0; font-weight: 600;">Why is this important?</h3>
                                                        <p style="color: #075985; font-size: 14px; line-height: 1.6; margin: 0;">
                                                            Regular login helps us ensure your account remains active and secure. To prevent any interruption to your service, please log in within the next 24 hours.
                                                        </p>
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                    
                                    <!-- Additional Info -->
                                    <tr>
                                        <td style="padding-top: 30px;">
                                            <p style="color: #6b7280; font-size: 14px; line-height: 1.6; margin: 0; text-align: center;">
                                                If you have any questions or concerns, please contact our support team.
                                            </p>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td align="center" style="background-color: #f9fafb; padding: 30px 20px; border-top: 1px solid #e5e7eb;">
                                <table cellpadding="0" cellspacing="0" border="0">
                                    <tr>
                                        <td align="center">
                                            <p style="color: #6b7280; font-size: 14px; margin: 0 0 12px 0; line-height: 1.5;">
                                                This is an automated reminder from IPPP App
                                            </p>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td align="center">
                                            <p style="color: #9ca3af; font-size: 12px; margin: 0; line-height: 1.6;">
                                                © 2024 IPPP App. All rights reserved.<br>
                                                Please do not reply to this email.
                                            </p>
                                        </td>
                                    </tr>
                                    <tr>
                                        <td align="center" style="padding-top: 15px;">
                                            <a href="#" style="color: #9ca3af; text-decoration: none; font-size: 12px; padding: 0 8px;">Help Center</a>
                                            <span style="color: #d1d5db;">•</span>
                                            <a href="#" style="color: #9ca3af; text-decoration: none; font-size: 12px; padding: 0 8px;">Contact Support</a>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                        
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    '''
    
    try:
        print("Sending email...")
        result = send_mail(subject, body)
        return result
    except Exception as e:
        return f"Error sending email: {str(e)}", 500




# ---------------- SECHDULER  ----------------
scheduler = BackgroundScheduler()
scheduler.add_job(remind_tasks, 'interval', hours=2)
scheduler.add_job(ippb_login_reminder, 'cron', day='*/3', hour=22, minute=0)



#----------------ROUTS START----------------------------

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        password = request.form.get('password')
        if user_id == os.getenv("USER_ID") and password == os.getenv("USER_PASSWORD"):
            session['user_id'] = user_id
            return redirect(url_for('home'))
        else:
            msgs=["Invalid Credential", "invalid values", "Credential not match", "wrong input",
                    "wrong Credential", "not allow", "not a valid input"]
            msg = msgs[random.randint(0, 6)]
            flash(msg, "error")
    return render_template('login.html')

#------------home page-------------------------------

@app.route('/home', methods=['GET', 'POST'])
def home():
    if "user_id" not in session:
        return redirect("/")
    return render_template("home_page.html")

#-------------------- ERROR PAGES -----------
@app.route('/unautorized', methods=['GET', 'POST'])
def unautorized():
    return render_template("error_page/acces_denied.html")

@app.route('/server-error', methods=['GET', 'POST'])
def server_error():
    if "user_id" not in session:
        return redirect('/unautorized')
    return render_template("error_page/ep500.html")

@app.route('/card-not-allow', methods=['GET', 'POST'])
def card_not_allow():
    if "user_id" not in session:
        return redirect('/unautorized')
    return render_template("error_page/credit_t_card.html")

@app.route('/error', methods=['GET', 'POST'])
def other_error():
    return render_template("error_page/o_error.html")


#------------tasks rout-------------------------------

@app.route('/tasks/sort-tasks', methods=['GET', 'POST'])
def sort_tasks():
    if "user_id" not in session:
        return redirect("/unautorized")
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        if request.method == 'POST':
            ids_to_delete = [int(i) for i in request.form.getlist('delete_checkbox')]
            if ids_to_delete:
                format_strings = ','.join(['%s'] * len(ids_to_delete))
                print(format_strings)
                cur.execute(f"UPDATE task SET is_complete = 'True' WHERE t_id IN ({format_strings})", tuple(ids_to_delete))
                conn.commit()
                cur.close()
                conn.close()
                return redirect("/tasks/sort-tasks")
    except Exception:
        return redirect(url_for('server_error'))
    try:
        cur.execute("SELECT t_id,task FROM task WHERE is_complete=%s",("False",))
        statements = cur.fetchall()
        cur.close()
        conn.close()
    except Exception:
        return redirect(url_for('server_error'))
    return render_template('task/uncomplete_sort_work.html', statements=statements)


@app.route('/tasks/add-sort-tasks', methods=['GET', 'POST'])
def add_sort_tasks():
    if "user_id" not in session:
        return redirect("/unautorized")
    if request.method == 'POST':
        task_name = request.form["task_name"]
        current_ist_date = format_ist_time(get_current_ist_time())
        try:
            conn = get_db_connection()
            cur = conn.cursor(dictionary=True)
            cur.execute("INSERT INTO task(task, date) VALUES (%s, %s)",(task_name, current_ist_date))
            conn.commit()
            cur.close()
            conn.close()
        except Exception:
            return redirect('/server-error')
        return redirect(url_for('add_sort_tasks'))
    return render_template('task/add_sort_work.html')

@app.route("/tasks/completed-sort-work", methods=['GET', 'POST'])
def complete_sort_tasks():
    if "user_id" not in session:
        return redirect("/unautorized")
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True,  buffered=True)
        cur.execute("SELECT * FROM task WHERE is_complete = %s",("True",))
        statements = cur.fetchall()
        cur.close()
        conn.close()
    except Exception:
        return redirect('/server-error')
    return render_template("task/completed_sort_work.html", statements = statements)


@app.route("/tasks/clear-all-sort-tasks")
def clear_complete_sort_tasks():
    if "user_id" not in session:
        return redirect("/unautorized")
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("DELETE FROM task WHERE is_complete=%s",("True",))
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        return redirect('/server-error')
    return redirect(url_for('complete_sort_tasks'))


#--------------------- EXPENSEC ROUTS -----------------------


@app.route('/home/expenses', methods=['GET', 'POST'])
def expenses():
    if "user_id" not in session:
        return redirect("/unautorized")
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute("SELECT t_id, type, s_date, time, mode, amount,bank_name, purpose FROM expenses WHERE is_display=%s ORDER BY t_id DESC",("True",))
        transactions = cur.fetchall()

        cur.execute("SELECT SUM(amount) AS total_in_amount FROM expenses WHERE is_display = %s AND type = %s",("True", "Credit"))
        result_in = cur.fetchone()
        total_in = result_in['total_in_amount']

        cur.execute("SELECT SUM(amount) AS total_out_amount FROM expenses WHERE is_display = %s AND type = %s",("True", "Debit"))
        result_out = cur.fetchone()
        total_out = result_out['total_out_amount']

        cur.execute("SELECT cash, ippb, jio, sbi FROM expenses WHERE t_id = (SELECT MAX(t_id) FROM expenses)")
        result_balance = cur.fetchone()

        cur.close()
        conn.close()
    except Exception:
        return redirect('/server-error')


    if not result_balance:
        result_balance = {"cash": 3200, "ippb": 110, "jio": 0.75, "sbi": 11950}
    balances = {
        "cash": result_balance["cash"],
        "ippb": result_balance["ippb"],
        "jio": result_balance["jio"],
        "sbi": result_balance["sbi"]
    }

    total={
        "total_in":total_in,
        "total_out":total_out
    }
    return render_template("expense/expense_view.html", transactions=transactions, balances=balances, total=total)


@app.route("/home/add_transaction", methods=["GET", "POST"])
def add_transaction():
    if "user_id" not in session:
        return redirect("/unautorized")
    if request.method == "POST":
        payment_type = request.form.get("payment_type")     #type
        amount = float(request.form.get("amount"))                 #amount
        mode = request.form.get("mode")                      #mode
        account = request.form.get("account")               #bank_name
        if mode == "Cash":
            account="None"
        date = request.form.get("date")                      #date
        time = request.form.get("time")                      #time
        purpose = request.form.get("purpose")                #purpose
        s_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d-%m-%Y")#s_date

        try:
            conn = get_db_connection()
            cur = conn.cursor(dictionary=True)

            cur.execute("SELECT cash, ippb, jio, sbi FROM expenses WHERE t_id = (SELECT MAX(t_id) FROM expenses)")
            previous_value = cur.fetchone()
        except Exception:
            return redirect('/server-error')
        # if not previous_value:
        #     previous_value={"cash": 3200, "ippb": 110, "jio": 0.75, "sbi": 11950}

        new_balance={
            "cash":previous_value["cash"],
            "ippb":previous_value["ippb"],
            "jio":previous_value["jio"],
            "sbi":previous_value["sbi"]
        }
        try:
        #credt not allow
            if payment_type == "Credit":
                if mode == "Card":
                    return redirect(url_for('card_not_allow'))
                if mode == "Cash":
                    new_balance["cash"] = new_balance["cash"] + amount
                if mode == "UPI" or mode == "Bank Transfer":
                    new_balance[account] += amount
            # Debit mechanisim
            elif payment_type == "Debit":
                if mode == "Card":
                    new_balance["sbi"] = new_balance["sbi"] - amount
                if mode == "Cash":
                    new_balance["cash"] = new_balance["cash"] - amount
                if mode == "UPI" or mode == "Bank Transfer":
                    new_balance[account] -= amount
            else:
                return redirect('/error')
        except TypeError:
            return redirect(url_for('other_error'))
        
        try:
            cur.execute("INSERT INTO expenses(is_display,type,date,s_date,time,mode,bank_name,amount,purpose,cash,ippb,jio,sbi)" \
            " VALUES(%s, %s, %s, %s, %s ,%s, %s, %s, %s,%s, %s, %s, %s)",
            ("True",payment_type,date,s_date,time,mode,account,amount,purpose,new_balance["cash"],new_balance["ippb"],new_balance["jio"],new_balance["sbi"]))
            conn.commit()
            cur.close()
            conn.close()
        except Exception:
            return redirect('/server-error')
        
        return redirect(url_for('add_transaction'))

    return render_template("expense/add_expenses.html")

#----------------------------------- FILE MECANISIM -------------------------------
@app.route('/upload_files', methods=['GET', 'POST'])
def upload_file():
    if "user_id" not in session:
        return redirect("/unautorized")
    
    if request.method == 'POST':
        file = request.files.get('file')

        if not file or file.filename.strip() == '':
            return "No file selected"

        file_name = file.filename
        file_ext = file_name.split('.')[-1]
        file_data = file.read()
        file_size = len(file_data)
        uploaded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            db = get_db_connection2()
            cursor = db.cursor(buffered=True)

            cursor.execute("""
                INSERT INTO stored_files (file_name, file_ext, file_size, uploaded_at, file_data)
                VALUES (%s, %s, %s, %s, %s)
            """, (file_name, file_ext, file_size, uploaded_at, file_data))
            db.commit()
            cursor.close()
            db.close()
            return redirect(url_for('upload_file'))

        except Exception as e:
            print("UPLOAD ERROR:", e)
            return redirect('/server-error')

    return render_template("file/upload_file.html")



# LIST ALL FILES

@app.route('/view_files')
def list_files():
    if "user_id" not in session:
        return redirect("/unautorized")
    try:
        db = get_db_connection2()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT id, file_name, file_size, uploaded_at FROM stored_files ORDER BY id DESC")
        files = cursor.fetchall()
        db.close()
        cursor.close()
    except Exception:
        return redirect('/server-error')
    return render_template("file/view_files.html", files=files)


#DOWNLOAD FILE

@app.route('/download/<int:file_id>')
def download_file(file_id):
    if "user_id" not in session:
        return redirect("/unautorized")

    try:
        db = get_db_connection2()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT file_name, file_data FROM stored_files WHERE id = %s",(file_id,))
        result = cursor.fetchone()
        db.close()
        cursor.close()
    except Exception as e:
        print("Download error:", str(e))
        return redirect('/server-error')

    if not result:
        return "File not found"

    file_name = result["file_name"]
    file_data = result["file_data"]

    return send_file(
        io.BytesIO(file_data),
        download_name=file_name,
        as_attachment=True
    )

@app.route('/truncket', methods=['POST'])
def truncket():
    if "user_id" not in session:
        return redirect('/unautorized')
    
    password = request.form.get('password')
    
    if password == os.getenv('USER_PASSWORD'):
        try:
            db = get_db_connection2()
            cursor = db.cursor(dictionary=True)
            cursor.execute("TRUNCATE TABLE stored_files")
            db.commit()
            db.close()
            cursor.close()
            flash("All files deleted successfully!", "success")
            return redirect(url_for('list_files'))
        except Exception as e:
            print("Error:", e)  # useful for debugging
            return redirect('/server-error')
    else:
        flash("Wrong password", "error")
        return redirect(url_for('list_files'))




@app.route("/send-mail", methods=['GET', 'POST'])







#------------------------- LOG OUT -----------------------

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


#----------------ROUTS END----------------------------


# ---------------- SCHEDULER CONFIG --------
if __name__ == '__main__':
    scheduler.start()
    app.run()
    # app.run(host="0.0.0.0", port=5005, debug=True)
