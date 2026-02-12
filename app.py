import os
from flask import Flask, render_template, request, redirect, session, url_for, send_file, flash, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import time
from dotenv import load_dotenv
import mysql.connector
import pytz
import requests
import io
import random
from datetime import time
from pushbullet import Pushbullet

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
        use_pure=True
    )

#-----------------current date (India timezone)----------------------

def get_current_ist_time():
    return datetime.now(IST)

def format_ist_time(dt):
    if dt.tzinfo is None:
        dt = IST.localize(dt)
    return dt.strftime("%d-%m-%Y %H:%M")

# Update current_date to use IST
now_date = get_current_ist_time()
current_date = format_ist_time(now_date)

#----------------ROUTS START----------------------------

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        password = request.form.get('password')
        db = get_db_connection()
        cur = db.cursor(dictionary=True)

        cur.execute("SELECT * FROM users WHERE user_id=%s",(user_id,))
        res = cur.fetchone()

        if password == res["password"]:
            session['user_id'] = user_id
            session["id"] = res["id"]

            if user_id == os.getenv("USER_ID"):
                return redirect(url_for('home'))
            else:
                return redirect(url_for('list_files'))
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
    if session["user_id"] != os.getenv("USER_ID"):
        return redirect("/")
    return render_template("home_page.html")

#-------------------- ERROR  AND SUCESS PAGES -----------
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

@app.route('/Done', methods=['GET', 'POST'])
def done():
    return render_template("done.html")

#------------tasks rout-------------------------------

@app.route('/tasks/sort-tasks', methods=['GET', 'POST'])
def sort_tasks():
    if "user_id" not in session:
        return redirect("/unautorized")
    
    if session["user_id"] != os.getenv("USER_ID"):
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
    
    if session["user_id"] != os.getenv("USER_ID"):
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
    
    if session["user_id"] != os.getenv("USER_ID"):
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
    
    if session["user_id"] != os.getenv("USER_ID"):
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
    
    if session["user_id"] != os.getenv("USER_ID"):
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
    
    if session["user_id"] != os.getenv("USER_ID"):
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




@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

#----------------ROUTS END----------------------------

#----------------------- NOTIFICATION ----------------------------------
@app.route("/pending_tasks", methods=["GET"])
def send_pending_tasks():
    api_key = request.args.get("api_key")
    expected_key = os.getenv("ROUT_ACTIVATE_API_KEY")

    
    print("RECEIVED api_key:", api_key)
    print("EXPECTED api_key:", expected_key)

    if not api_key or not expected_key or api_key.strip() != expected_key:
        return jsonify({"error": "Unauthorized"}), 401
    
    now = get_current_ist_time().time()
    start = time(00, 10)
    end   = time(6, 30)
    if start <= now <= end:
        return jsonify({"message": "this is not the right time"}), 200

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT task FROM task WHERE is_complete=%s", ("False",))
    results = cur.fetchall()
    conn.close()

    tasks = [row["task"] for row in results]
    final_result = "\n\n".join(tasks) if tasks else "No pending tasks"

    if final_result == "No pending tasks":
        return "no pending task"

    pb_key = os.getenv("PUSHBULLET_AUTH_KEY")
    if pb_key:
        try:
            pb = Pushbullet(pb_key)
            pb.push_note("🤖Pending Tasks:", final_result)
        except Exception as e:
            print("Pushbullet error:", e)

    return jsonify({"status": "Notification sent", "tasks_sent": len(tasks)}), 200

    
@app.route("/ippb_login_reminder", methods=["GET"])
def remind_for_ippb_login():
    api_key = request.args.get("api_key")
    expected_key = os.getenv("ROUT_ACTIVATE_API_KEY")

    
    print("RECEIVED api_key:", api_key)
    print("EXPECTED api_key:", expected_key)


    if not api_key or not expected_key or api_key.strip() != expected_key:
        return jsonify({"error": "Unauthorized"}), 401
    
    title = "🤖Pending Tasks Alert🤖"
    url = f"https://deepti.onrender.com/ippb_pass?api_key={os.getenv("ROUT_ACTIVATE_API_KEY")}"
    msg = f"This is a reminder for login to your IPPB app for avoid password deactivation.\n\
            \n-----------------------------------------------------------\n\
            \n If forgotten the password then click the below link⬇️\n"

    pb_key = os.getenv("PUSHBULLET_AUTH_KEY")
    if not pb_key:
        print("❌ PUSHBULLET_AUTH_KEY not set")
    else:
        try:
            pb = Pushbullet(pb_key)
            pb.push_link(title, url, body=msg)
        except Exception as e:
            print("Pushbullet error:", e)

    return jsonify({"status": "Notification sent"}), 200



@app.route("/koyeb_login_reminder", methods=["GET"])
def remind_for_ippb_login():
    api_key = request.args.get("api_key")
    expected_key = os.getenv("ROUT_ACTIVATE_API_KEY")

    
    print("RECEIVED api_key:", api_key)
    print("EXPECTED api_key:", expected_key)


    if not api_key or not expected_key or api_key.strip() != expected_key:
        return jsonify({"error": "Unauthorized"}), 401
    
    title = "🤖Pending Tasks Alert🤖"
    url = f"https://app.koyeb.com/"
    msg = f"This is a reminder for login to your koyeb dashboard for avoid Account deactivation.\n\
            \n-----------------------------------------------------------\n"

    pb_key = os.getenv("PUSHBULLET_AUTH_KEY")
    if not pb_key:
        print("❌ PUSHBULLET_AUTH_KEY not set")
    else:
        try:
            pb = Pushbullet(pb_key)
            pb.push_link(title, url, body=msg)
        except Exception as e:
            print("Pushbullet error:", e)

    return jsonify({"status": "Notification sent"}), 200



@app.route("/ippb_pass", methods=["GET"])
def ippb_pass():
    api_key = request.args.get("api_key")
    expected_key = os.getenv("ROUT_ACTIVATE_API_KEY")

    
    print("RECEIVED api_key:", api_key)
    print("EXPECTED api_key:", expected_key)

    if not api_key or not expected_key or api_key.strip() != expected_key:
        return jsonify({"error": "Unauthorized"}), 401
    
    msg = f"This is a the password for IPPB mobile login.\
                \n--------------------------------------------------\
                \n {os.getenv("IPPB_PASSWORD")}\
                \n--------------------------------------------------\n\
                💀keep it Secret💀"

    pb_key = os.getenv("PUSHBULLET_AUTH_KEY")
    if not pb_key:
        print("❌ PUSHBULLET_AUTH_KEY not set")
    else:
        try:
            pb = Pushbullet(pb_key)
            pb.push_note("🤖Password for IPPB login:", msg)
        except Exception as e:
            print("Pushbullet error:", e)
    return redirect("/Done")


@app.route("/clear_push", methods=["GET"])
def clear_notification():
    api_key = request.args.get("api_key")
    expected_key = os.getenv("ROUT_ACTIVATE_API_KEY")

    if not api_key or not expected_key or api_key.strip() != expected_key:
        return jsonify({"error": "Unauthorized"}), 401

    pb_key = os.getenv("PUSHBULLET_AUTH_KEY")
    if not pb_key:
        return jsonify({"error": "Pushbullet key missing"}), 500

    try:
        pb = Pushbullet(pb_key)
        pushes = pb.get_pushes()

        for push in pushes:
            push_id = push.get("iden")
            if not push_id:
                continue
            try:
                pb.delete_push(push_id)
            except Exception as e:
                print("Delete failed:", e)

    except Exception as e:
        print("Pushbullet fatal error:", e)

    return jsonify({"status": "all pushes cleared"}), 200




# ---------------- SCHEDULER CONFIG --------
if __name__ == '__main__':
    app.run()
    # app.run(host="0.0.0.0", port=5005, debug=True)
