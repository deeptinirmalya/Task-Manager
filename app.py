import os
from flask import Flask, render_template, request, redirect, session, url_for
from datetime import datetime
from dotenv import load_dotenv
import mysql.connector
import pytz
import requests

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret')

# Define India timezone
IST = pytz.timezone('Asia/Kolkata')

#----------------DATABASE CONNECTION-----------------------------
#hii
def get_db_connection():
    host = os.getenv("DB_HOST")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    database = os.getenv("DB_NAME")
    port = os.getenv("DB_PORT")
    ssl_ca = os.getenv("SSL_CA")

    if not all([host, user, password, database, port, ssl_ca]):
        raise ValueError("❌ Missing one or more DB environment variables!")

    return mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        port=int(port),
        ssl_ca=ssl_ca
    )

#-----------------current date (India timezone)----------------------

def get_current_ist_time():
    """Returns current time in IST timezone"""
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



# ---------------- REMINDER JOB ----------------


#----------------ROUTS START----------------------------

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        password = request.form.get('password')
        if user_id == os.getenv("USER_ID") and password == os.getenv("USER_PASSWORD"):
            session['user_id'] = user_id
            return redirect(url_for('home'))
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
    return render_template("error_page/ep500.html")

@app.route('/card-not-allow', methods=['GET', 'POST'])
def card_not_allow():
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
    except mysql.connector.Error:
        return redirect(url_for('server_error'))
    try:
        cur.execute("SELECT t_id,task FROM task WHERE is_complete=%s",("False",))
        statements = cur.fetchall()
        cur.close()
        conn.close()
    except mysql.connector.Error:
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
        except mysql.connector.Error:
            return redirect(url_for('server_error'))
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
    except mysql.connector.Error:
        return redirect(url_for('server_error'))
    return render_template("task/completed_sort_work.html", statements = statements)


@app.route("/tasks/completed-sort-tasks/clear-all-sort-tasks")
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
    except mysql.connector.Error:
        return redirect(url_for('server_error'))
    return redirect("/tasks/completed-sort-tasks/clear-all-sort-tasks")


#--------------------- EXPENSEC ROUTS -----------------------


@app.route('/home/expenses', methods=['GET', 'POST'])
def expenses():
    if "user_id" not in session:
        return redirect("/unautorized")
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute("SELECT t_id, type, s_date, time, mode, amount,bank_name, purpose FROM expenses WHERE is_display=%s",("True",))
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
    except mysql.connector.Error:
        return redirect(url_for('server_error'))


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
        except mysql.connector.Error:
            return redirect(url_for('server_error'))
        
        try:
            cur.execute("SELECT cash, ippb, jio, sbi FROM expenses WHERE t_id = (SELECT MAX(t_id) FROM expenses)")
            previous_value = cur.fetchone()
        except mysql.connector.Error:
            return redirect(url_for('server_error'))

        if not previous_value:
            previous_value={"cash": 3200, "ippb": 110, "jio": 0.75, "sbi": 11950}

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
                return redirect(url_for('other_error'))
        except TypeError:
            return redirect(url_for('other_error'))
        
        try:
            cur.execute("INSERT INTO expenses(is_display,type,date,s_date,time,mode,bank_name,amount,purpose,cash,ippb,jio,sbi)" \
            " VALUES(%s, %s, %s, %s, %s ,%s, %s, %s, %s,%s, %s, %s, %s)",
            ("False",payment_type,date,s_date,time,mode,account,amount,purpose,new_balance["cash"],new_balance["ippb"],new_balance["jio"],new_balance["sbi"]))
            conn.commit()
            cur.close()
            conn.close()
        except mysql.connector.Error:
            return redirect(url_for('server_error'))
        
        return redirect(url_for('add_transaction'))
    return render_template("expense/add_expenses.html")







#------------------------- LOG OUT -----------------------

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


#----------------ROUTS END----------------------------


# ---------------- SCHEDULER CONFIG --------
if __name__ == '__main__':
    app.run(debug=True)
    # app.run(host="0.0.0.0", port=5005, debug=True)
