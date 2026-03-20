from flask import render_template, request, redirect, session
from flask import Flask
from pymongo import MongoClient
from datetime import datetime
import os
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-123")

# Connect to MongoDB
client = MongoClient(os.environ.get("MONGO_URI"))
db = client["cable_db"]

customers = db["customers"]
payments = db["payments"]
transactions = db["transactions"]

customers.create_index("card_number", unique=True)
customers.create_index("stb_number", unique=True)

payments.create_index(
    [("card_number", 1), ("year", 1), ("month", 1)],
    unique=True
)


@app.route('/')
def home():
    return redirect('/login')

# LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form['password']

        if password == "admin123":
            session['admin'] = True
            return redirect('/dashboard')
        else:
            return render_template('login.html', error="Wrong Password")

    return render_template('login.html')


# ADMIN
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('admin'):
        return redirect('/login')

    if request.method == 'POST':
        card_number = request.form['card_number']
        stb_number = request.form['stb_number']
        monthly_amount = request.form['monthly_amount']

        try:
            customers.insert_one({
                "card_number": card_number,
                "stb_number": stb_number,
                "monthly_amount": int(monthly_amount)
            })
        except:
            return render_template("admin.html",
                                   error="Card Number or STB Number Already Exists",
                                   customers=customers.find())

    search_query = request.args.get("search")

    if search_query:
        all_customers = customers.find({"card_number": search_query})
    else:
        all_customers = customers.find()
    
    return render_template(
        "admin.html",
        customers=all_customers
    )


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# EDIT MONTHLY AMOUNT
@app.route('/edit/<card_number>', methods=['GET', 'POST'])
def edit(card_number):
    if not session.get('admin'):
        return redirect('/login')

    customer = customers.find_one({"card_number": card_number})

    if request.method == 'POST':
        new_amount = request.form['monthly_amount']

        customers.update_one(
            {"card_number": card_number},
            {"$set": {"monthly_amount": int(new_amount)}}
        )

        return redirect('/admin')

    return render_template("edit.html", customer=customer)


# PAYMENTS PAGE (MONTH LIST)
@app.route('/payments/<card_number>')
def payments_page(card_number):
    if not session.get('admin'):
        return redirect('/login')

    customer = customers.find_one({"card_number": card_number})

    months = [
        "January","February","March","April","May","June",
        "July","August","September","October","November","December"
    ]

    year = 2026

    payment_records = []

    for month in months:
        record = payments.find_one({
            "card_number": card_number,
            "year": year,
            "month": month
        })

        if record:
            if record["status"] == "Paid":
                status_text = "Paid"
            elif record["status"] == "Balance":
                status_text = f"Balance ₹{record['balance']}"
            else:
                status_text = "Not Paid"

            payment_records.append({
                "month": month,
                "status": status_text
            })
        else:
            payment_records.append({
                "month": month,
                "status": "Not Paid"
            })
    return render_template(
        "payments.html",
        customer=customer,
        payments=payment_records,
        year=year
    )


# 🔥 PAY MONTH ROUTE (NEWLY ADDED)
@app.route('/pay/<card_number>/<month>', methods=['GET', 'POST'])
def pay_month(card_number, month):
    if not session.get('admin'):
        return redirect('/login')

    customer = customers.find_one({"card_number": card_number})
    year = 2026

    if request.method == 'POST':
        paid_amount_input = int(request.form['paid_amount'])
        monthly_amount = customer['monthly_amount']

        existing = payments.find_one({
            "card_number": card_number,
            "year": year,
            "month": month
        })

        if existing:
            previous_paid = existing.get("paid_amount", 0)
            paid_amount = previous_paid + paid_amount_input
        else:
            paid_amount = paid_amount_input

        balance = monthly_amount - paid_amount

        if balance <= 0:
            status = "Paid"
            balance = 0
        else:
            status = "Balance"

        payments.update_one(
            {
                "card_number": card_number,
                "year": year,
                "month": month
            },
            {
                "$set": {
                    "paid_amount": paid_amount,
                    "monthly_amount": monthly_amount,
                    "balance": balance,
                    "status": status
                }
            },
            upsert=True
        )

        return redirect(f"/payments/{card_number}")

    return render_template(
        "pay.html",
        customer=customer,
        month=month,
        year=year
    )


@app.route('/monthly-summary')
def monthly_summary():
    if not session.get('admin'):
        return redirect('/login')

    from datetime import datetime

    now = datetime.now()
    year = now.year
    current_month = now.strftime("%B")

    summary_list = []

    for customer in customers.find():
        record = payments.find_one({
            "card_number": customer["card_number"],
            "year": year,
            "month": current_month
        })

        if record:
            if record["status"] == "Paid":
                status_text = "Paid"
            else:
                status_text = f"Balance ₹{record['balance']}"
        else:
            status_text = "Not Paid"

        summary_list.append({
            "card_number": customer["card_number"],
            "stb_number": customer["stb_number"],
            "status": status_text
        })

    # ✅ COUNT LOGIC (IMPORTANT)
    paid_count = 0
    unpaid_count = 0
    balance_count = 0

    for s in summary_list:
        if s["status"] == "Paid":
            paid_count += 1
        elif "Balance" in s["status"]:
            balance_count += 1
        else:
            unpaid_count += 1

    return render_template(
        "summary.html",
        summary_list=summary_list,
        month=current_month,
        year=year,
        paid_count=paid_count,
        unpaid_count=unpaid_count,
        balance_count=balance_count
    )


@app.route("/dashboard")
def dashboard():
    if not session.get("admin"):
        return redirect("/login")

    total_customers = customers.count_documents({})

    paid_customers = payments.count_documents({"status": "Paid"})
    not_paid_customers = payments.count_documents({"status": "Not Paid"})
    balance_customers = payments.count_documents({"status": "Balance"})

    total_collected = 0
    paid_records = payments.find({"status": "Paid"})
    for record in paid_records:
        total_collected += record.get("paid_amount", 0)

    return render_template(
        "dashboard.html",
        total_customers=total_customers,
        paid_customers=paid_customers,
        not_paid_customers=not_paid_customers,
        balance_customers=balance_customers,
        total_collected=total_collected
    )




if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))