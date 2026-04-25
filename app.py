from flask import Flask, request, render_template, redirect, session, Response
import json
from datetime import datetime
import io
import matplotlib.pyplot as plt
import os

print(os.getcwd())

app = Flask(__name__, template_folder="templates")
import os
app.secret_key = os.getenv("SECRET_KEY", "dev_key")

DATA_FILE = "data.json"

# ----------------------------
# LOAD / SAVE
# ----------------------------
def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except:
        return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

user_db = load_data()


# ----------------------------
# AUTH
# ----------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if len(username) < 3:
            return render_template("signup.html", error="Username too short")

        if len(password) < 4:
            return render_template("signup.html", error="Password too weak")

        if username in user_db:
            return render_template("signup.html", error="User already exists")

        user_db[username] = {
            "password": password,
            "expenses": []
        }

        save_data(user_db)
        return redirect("/login")

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username not in user_db:
            return render_template("login.html", error="User not found")

        if user_db[username]["password"] != password:
            return render_template("login.html", error="Wrong password")

        session["user"] = username
        return redirect("/")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/login")


# ----------------------------
# HOME
# ----------------------------
@app.route("/")
def home():
    if "user" not in session:
        return redirect("/login")   # 👈 MUST

    user = session["user"]
    expenses = user_db[user]["expenses"]

    total = sum(e["amount"] for e in expenses)

    category_totals = {}
    for e in expenses:
        cat = e["category"]
        category_totals[cat] = category_totals.get(cat, 0) + e["amount"]

    max_cat = max(category_totals, key=category_totals.get) if category_totals else "None"

    return render_template(
        "index.html",
        expenses=expenses,
        total=total,
        max_cat=max_cat,
        user=user,
        chart_labels=list(category_totals.keys()),
        chart_values=list(category_totals.values())
    )

# ----------------------------
# ADD EXPENSE
# ----------------------------
@app.route("/add", methods=["POST"])
def add():
    if "user" not in session:
        return redirect("/login")

    user = session["user"]

    if user not in user_db:
        user_db[user] = {"password": "", "expenses": []}

    amount = request.form.get("amount", "").strip()
    category = request.form.get("category")
    custom = request.form.get("custom_category", "").strip()

    if not amount.isdigit():
        return "Invalid amount"

    if category == "Other":
        if len(custom) < 3:
            return "Invalid custom category"
        category = custom.capitalize()

    user_db[user]["expenses"].append({
        "amount": int(amount),
        "category": category,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    save_data(user_db)

    return redirect("/")


# ----------------------------
# CHART
# ----------------------------
@app.route("/chart")
def chart():
    if "user" not in session:
        return redirect("/login")

    user = session["user"]
    expenses = user_db[user]["expenses"]

    if not expenses:
        return "<h2>No data to show</h2><a href='/'>Back</a>"

    category_totals = {}

    for e in expenses:
        cat = e["category"]
        category_totals[cat] = category_totals.get(cat, 0) + e["amount"]

    labels = list(category_totals.keys())
    values = list(category_totals.values())

    # COLORS (premium look)
    colors = [
        "#4F8CFF", "#22C55E", "#F97316",
        "#EF4444", "#A855F7", "#14B8A6"
    ]

    plt.figure(figsize=(6,6), facecolor="#0B1220")

    wedges, texts, autotexts = plt.pie(
        values,
        labels=labels,
        autopct="%1.1f%%",
        colors=colors[:len(labels)],
        textprops={"color": "white"}
    )

    plt.title("Expense Breakdown", color="white", fontsize=14)

    img = io.BytesIO()
    plt.savefig(img, format="png", bbox_inches="tight", facecolor="#0B1220")
    plt.close()
    img.seek(0)

    return Response(img.getvalue(), mimetype="image/png")
# ----------------------------
# SUMMARY
# ----------------------------
@app.route("/summary")
def summary():
    if "user" not in session:
        return redirect("/login")

    user = session["user"]
    expenses = user_db[user]["expenses"]

    if not expenses:
        return """
        <h2>No Data Available</h2>
        <a href="/">Back</a>
        """

    total = sum(e["amount"] for e in expenses)
    txn_count = len(expenses)
    avg_spend = round(total / txn_count, 2)

    # ------------------------
    # CATEGORY ANALYSIS
    # ------------------------
    category_totals = {}
    for e in expenses:
        cat = e["category"]
        category_totals[cat] = category_totals.get(cat, 0) + e["amount"]

    top_category = max(category_totals, key=category_totals.get)
    top_amount = category_totals[top_category]
    top_percent = round((top_amount / total) * 100, 2)

    # ------------------------
    # WEEKLY TREND
    # ------------------------
    from datetime import datetime, timedelta

    now = datetime.now()
    last7 = 0
    prev7 = 0

    for e in expenses:
        t = datetime.strptime(e["time"], "%Y-%m-%d %H:%M:%S")

        if t >= now - timedelta(days=7):
            last7 += e["amount"]
        elif t >= now - timedelta(days=14):
            prev7 += e["amount"]

    trend = "increased 📈" if last7 > prev7 else "decreased 📉"

    # ------------------------
    # SMART INSIGHTS
    # ------------------------
    insights = []

    insights.append(f"You spent most on {top_category} ({top_percent}%)")

    if top_percent > 60:
        insights.append("⚠️ One category dominates your spending")

    if avg_spend > 1000:
        insights.append("💸 High average spend detected")
    else:
        insights.append("👍 Spending is under control")

    if last7 > prev7:
        insights.append("📈 Spending increased in last 7 days")
    else:
        insights.append("📉 Spending decreased recently")

    # ------------------------
    # OUTPUT UI
    # ------------------------
    return f"""
    <html>
    <head>
        <title>Insights</title>
        <style>
            body {{
                font-family: Arial;
                background: #0B1220;
                color: white;
                padding: 20px;
            }}
            .card {{
                background: #111A2E;
                padding: 15px;
                margin: 10px 0;
                border-radius: 12px;
            }}
            h2 {{
                color: #4F8CFF;
            }}
        </style>
    </head>

    <body>

        <h2>📊 Smart Insights</h2>

        <div class="card">
            <b>Total:</b> ₹{total}<br>
            <b>Transactions:</b> {txn_count}<br>
            <b>Average:</b> ₹{avg_spend}
        </div>

        <div class="card">
            <b>Top Category:</b> {top_category} ({top_percent}%)
        </div>

        <div class="card">
            <b>Weekly Trend:</b> {trend}
        </div>

        <div class="card">
            <b>Insights:</b><br>
            {"<br>".join(insights)}
        </div>

        <br>
        <a href="/" style="color:#4F8CFF;">⬅ Back</a>

    </body>
    </html>
    """

# ----------------------------
# DELETE / CLEAR
# ----------------------------
@app.route("/delete")
def delete():
    if "user" not in session:
        return redirect("/login")

    user = session["user"]

    if user_db[user]["expenses"]:
        user_db[user]["expenses"].pop()
        save_data(user_db)

    return redirect("/")


@app.route("/clear")
def clear():
    if "user" not in session:
        return redirect("/login")

    user = session["user"]
    user_db[user]["expenses"] = []
    save_data(user_db)

    return redirect("/")

# ----------------------------
# RUN
# ----------------------------
app.run(debug=True, host="0.0.0.0", port=5000)