from flask import Flask, request, jsonify, render_template, redirect, session, send_file
from flask_cors import CORS
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from datetime import datetime
import pandas as pd
import joblib
import mysql.connector
import traceback
import uuid

app = Flask(__name__)
app.secret_key = "supersecretkey"

CORS(app)

# ==================================================
# LOAD MODEL
# ==================================================
model = joblib.load("crrt_model.pkl")

# ==================================================
# MYSQL CONFIG
# ==================================================
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "admintest123",
    "database": "crrt_db"
}

def get_db_connection():
    conn = mysql.connector.connect(**DB_CONFIG)

    cursor = conn.cursor()
    cursor.execute("SET time_zone = '+08:00'")
    cursor.close()

    return conn


# ==================================================
# LOGIN PAGE
# ==================================================
@app.route("/")
def login():
    return render_template("login.html")


# ==================================================
# LOGIN PROCESS
# ==================================================
@app.route("/login", methods=["POST"])
def login_process():

    username = request.form["username"]
    password = request.form["password"]

    if username == "admin" and password == "1234":
        session["user"] = username
        return redirect("/dashboard")

    return redirect("/")


# ==================================================
# LOGOUT
# ==================================================
@app.route("/logout")
def logout():

    session.clear()
    return redirect("/")


# ==================================================
# DASHBOARD
# ==================================================
@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect("/")

    return render_template("dashboard.html")


# ==================================================
# PATIENT INPUT PAGE
# ==================================================
@app.route("/patient_input")
def patient_input():

    if "user" not in session:
        return redirect("/")

    return render_template("patient_input.html")


# ==================================================
# RESULTS PAGE
# ==================================================
@app.route("/results_page")
def results_page():

    if "user" not in session:
        return redirect("/")

    return render_template("results.html")


# ==================================================
# HISTORY PAGE
# ==================================================
@app.route("/history_page")
def history_page():

    if "user" not in session:
        return redirect("/")

    return render_template("history.html")


# ==================================================
# TRIAGE PAGE
# ==================================================
@app.route("/triage_page")
def triage_page():

    if "user" not in session:
        return redirect("/")

    return render_template("triage.html")


# ==================================================
# BATCH UPLOAD PAGE
# ==================================================
@app.route("/batch_upload_page")
def batch_upload_page():

    if "user" not in session:
        return redirect("/")

    return render_template("batch_upload.html")


# ==================================================
# REPORTS PAGE
# ==================================================
@app.route("/reports_page")
def reports_page():

    if "user" not in session:
        return redirect("/")

    return render_template("reports.html")


# ==================================================
# REPORT HTML PAGES
# ==================================================
@app.route("/daily_report")
def daily_report():

    if "user" not in session:
        return redirect("/")

    return render_template("daily_report.html")


@app.route("/weekly_report")
def weekly_report():

    if "user" not in session:
        return redirect("/")

    return render_template("weekly_report.html")


@app.route("/monthly_report")
def monthly_report():

    if "user" not in session:
        return redirect("/")

    return render_template("monthly_report.html")


@app.route("/highrisk_report")
def highrisk_report():

    if "user" not in session:
        return redirect("/")

    return render_template("highrisk_report.html")


# ==================================================
# RISK FUNCTION
# ==================================================
def get_risk(prob):

    if prob >= 0.75:
        return "HIGH", 3

    elif prob >= 0.45:
        return "MEDIUM", 2

    else:
        return "LOW", 1


# ==================================================
# PREDICT API
# ==================================================
@app.route("/predict", methods=["POST"])
def predict():

    conn = None
    cur = None

    try:

        data = request.json

        print("INPUT:", data)

        features = pd.DataFrame([[
            float(data["creatinine"]),
            float(data["lactate"]),
            float(data["ph"]),
            float(data["bun"]),
            float(data["map"]),
            float(data["urine_output"])
        ]], columns=[
            "creatinine",
            "lactate",
            "ph",
            "bun",
            "map",
            "urine_output"
        ])

        print("FEATURES:")
        print(features)

        print("MODEL FEATURES:", model.feature_names_in_)
        print("INPUT FEATURES:", features.columns.tolist())

        prob = float(model.predict_proba(features)[0][1])

        risk, priority = get_risk(prob)

        print("PROBABILITY =", prob)
        print("MODEL CLASSES:", model.classes_)
        print("RISK:", risk)

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        # CHECK EXISTING PATIENT
        cur.execute(
            "SELECT id FROM patients WHERE patient_code=%s",
            (data["patient_id"],)
        )

        patient = cur.fetchone()

        if patient:
            patient_db_id = patient["id"]

        else:
            cur.execute("""
                INSERT INTO patients
                (
                    patient_code,
                    full_name,
                    age,
                    gender
                )
                VALUES (%s,%s,%s,%s)
            """, (
                data["patient_id"],
                data["patient_name"],
                data["age"],
                data["gender"]
            ))

            patient_db_id = cur.lastrowid

        # SAVE PREDICTION
        cur.execute("""
            INSERT INTO predictions
            (
                patient_id,
                creatinine,
                lactate,
                ph,
                bun,
                urine,
                map,
                crrt_probability,
                risk_level,
                priority_score
            )
            VALUES
            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            patient_db_id,
            data["creatinine"],
            data["lactate"],
            data["ph"],
            data["bun"],
            data["urine_output"],
            data["map"],
            prob,
            risk,
            priority
        ))

        conn.commit()

        return jsonify({
            "success": True,
            "patient_id": data["patient_id"],
            "patient_code": data["patient_id"],
            "patient_name": data["patient_name"],
            "CRRT_probability": round(prob, 4),
            "risk_level": risk,
            "priority_score": priority
        })

    except Exception as e:

        if conn:
            conn.rollback()

        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()


# ==================================================
# HISTORY API
# ==================================================
@app.route("/history")
def history():

    conn = None
    cur = None

    try:

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT
                pr.*,
                p.patient_code,
                p.full_name,
                p.age,
                p.gender
            FROM predictions pr
            LEFT JOIN patients p
                ON p.id = pr.patient_id
            ORDER BY pr.id DESC
        """)

        results = cur.fetchall()

        return jsonify(results)

    except Exception as e:

        traceback.print_exc()

        return jsonify({
            "error": str(e)
        }), 500

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()


# ==================================================
# TRIAGE API
# ==================================================
@app.route("/triage")
def triage():

    conn = None
    cur = None

    try:

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT
                p.patient_code,
                p.full_name,
                p.age,
                p.gender,
                pr.*
            FROM predictions pr
            LEFT JOIN patients p
                ON p.id = pr.patient_id
            ORDER BY pr.crrt_probability DESC
        """)

        results = cur.fetchall()

        return jsonify(results)

    except Exception as e:

        traceback.print_exc()

        return jsonify({
            "error": str(e)
        }), 500

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()

    # ==================================================
# REPORT API HELPER
# ==================================================
def fetch_report_rows(query, params=None):

    conn = None
    cur = None

    try:

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute(query, params or ())

        results = cur.fetchall()

        return results

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()


# ==================================================
# API DAILY REPORT
# ==================================================
@app.route("/api/daily_report")
def api_daily_report():

    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    results = fetch_report_rows("""
        SELECT
            p.patient_code,
            p.full_name,
            pr.crrt_probability,
            pr.risk_level,
            pr.created_at
        FROM predictions pr
        LEFT JOIN patients p
            ON p.id = pr.patient_id
        WHERE DATE(pr.created_at)=CURDATE()
        ORDER BY pr.created_at DESC
    """)

    return jsonify(results)


# ==================================================
# API WEEKLY REPORT
# ==================================================
@app.route("/api/weekly_report")
def api_weekly_report():

    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    results = fetch_report_rows("""
        SELECT
            p.patient_code,
            p.full_name,
            pr.crrt_probability,
            pr.risk_level,
            pr.created_at
        FROM predictions pr
        LEFT JOIN patients p
            ON p.id = pr.patient_id
        WHERE pr.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        ORDER BY pr.created_at DESC
    """)

    return jsonify(results)


# ==================================================
# API MONTHLY REPORT
# ==================================================
@app.route("/api/monthly_report")
def api_monthly_report():

    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    month = request.args.get("month")
    year = request.args.get("year")

    if not month or not year:
        return jsonify([])

    results = fetch_report_rows("""
        SELECT
            p.patient_code,
            p.full_name,
            pr.crrt_probability,
            pr.risk_level,
            pr.created_at
        FROM predictions pr
        LEFT JOIN patients p
            ON p.id = pr.patient_id
        WHERE MONTH(pr.created_at) = %s
        AND YEAR(pr.created_at) = %s
        ORDER BY pr.created_at DESC
    """, (month, year))

    return jsonify(results)


# ==================================================
# API HIGH RISK REPORT
# ==================================================
@app.route("/api/highrisk_report")
def api_highrisk_report():

    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    results = fetch_report_rows("""
        SELECT
            p.patient_code,
            p.full_name,
            p.age,
            p.gender,
            pr.crrt_probability,
            pr.risk_level,
            pr.priority_score,
            pr.created_at
        FROM predictions pr
        LEFT JOIN patients p
            ON p.id = pr.patient_id
        WHERE pr.risk_level='HIGH'
        ORDER BY pr.crrt_probability DESC
    """)

    return jsonify(results)


# ==================================================
# PDF HELPER
# ==================================================
def generate_report_pdf(title, table_data, filename, header_color):

    buffer = BytesIO()

    doc = SimpleDocTemplate(buffer)

    styles = getSampleStyleSheet()

    elements = []

    elements.append(
        Paragraph(title, styles["Title"])
    )

    elements.append(
        Paragraph(
            f"Generated On: {datetime.now().strftime('%d %B %Y %H:%M')}",
            styles["Normal"]
        )
    )

    elements.append(Spacer(1, 20))

    table = Table(table_data, repeatRows=1)

    table.setStyle(TableStyle([

        ("BACKGROUND", (0,0), (-1,0), header_color),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), 1, colors.black),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("ALIGN", (0,0), (-1,-1), "CENTER")

    ]))

    elements.append(table)

    doc.build(elements)

    buffer.seek(0)

    response = send_file(
        buffer,
        mimetype="application/pdf"
    )

    response.headers["Content-Disposition"] = \
        f"inline; filename={filename}"

    return response


def build_pdf_table(records, highrisk=False):

    if highrisk:

        table_data = [[
            "Patient Code",
            "Patient Name",
            "Probability",
            "Priority",
            "Date"
        ]]

        for row in records:

            table_data.append([
                row.get("patient_code") or "-",
                row.get("full_name") or "-",
                f"{float(row.get('crrt_probability') or 0) * 100:.2f}%",
                row.get("priority_score") or "-",
                str(row.get("created_at") or "-")
            ])

    else:

        table_data = [[
            "Patient Code",
            "Patient Name",
            "Probability",
            "Risk",
            "Date"
        ]]

        for row in records:

            table_data.append([
                row.get("patient_code") or "-",
                row.get("full_name") or "-",
                f"{float(row.get('crrt_probability') or 0) * 100:.2f}%",
                row.get("risk_level") or "-",
                str(row.get("created_at") or "-")
            ])

    return table_data


# ==================================================
# GENERATE DAILY PDF
# ==================================================
@app.route("/generate_daily_pdf")
def generate_daily_pdf():

    if "user" not in session:
        return redirect("/")

    records = fetch_report_rows("""
        SELECT
            p.patient_code,
            p.full_name,
            pr.crrt_probability,
            pr.risk_level,
            pr.created_at
        FROM predictions pr
        LEFT JOIN patients p
            ON p.id = pr.patient_id
        WHERE DATE(pr.created_at)=CURDATE()
        ORDER BY pr.created_at DESC
    """)

    return generate_report_pdf(
        "Daily CRRT Report",
        build_pdf_table(records),
        "daily_report.pdf",
        colors.darkblue
    )


# ==================================================
# GENERATE WEEKLY PDF
# ==================================================
@app.route("/generate_weekly_pdf")
def generate_weekly_pdf():

    if "user" not in session:
        return redirect("/")

    records = fetch_report_rows("""
        SELECT
            p.patient_code,
            p.full_name,
            pr.crrt_probability,
            pr.risk_level,
            pr.created_at
        FROM predictions pr
        LEFT JOIN patients p
            ON p.id = pr.patient_id
        WHERE pr.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        ORDER BY pr.created_at DESC
    """)

    return generate_report_pdf(
        "Weekly CRRT Report",
        build_pdf_table(records),
        "weekly_report.pdf",
        colors.green
    )


# ==================================================
# GENERATE MONTHLY PDF
# ==================================================
@app.route("/generate_monthly_pdf")
def generate_monthly_pdf():

    if "user" not in session:
        return redirect("/")

    month = request.args.get("month")
    year = request.args.get("year")

    if not month or not year:
        return "Please select month and year."

    records = fetch_report_rows("""
        SELECT
            p.patient_code,
            p.full_name,
            pr.crrt_probability,
            pr.risk_level,
            pr.created_at
        FROM predictions pr
        LEFT JOIN patients p
            ON p.id = pr.patient_id
        WHERE MONTH(pr.created_at) = %s
        AND YEAR(pr.created_at) = %s
        ORDER BY pr.created_at DESC
    """, (month, year))

    return generate_report_pdf(
        f"Monthly CRRT Report - {month}/{year}",
        build_pdf_table(records),
        f"monthly_report_{month}_{year}.pdf",
        colors.orange
    )


# ==================================================
# GENERATE HIGH RISK PDF
# ==================================================
@app.route("/generate_highrisk_pdf")
def generate_highrisk_pdf():

    if "user" not in session:
        return redirect("/")

    records = fetch_report_rows("""
        SELECT
            p.patient_code,
            p.full_name,
            pr.crrt_probability,
            pr.priority_score,
            pr.created_at
        FROM predictions pr
        LEFT JOIN patients p
            ON p.id = pr.patient_id
        WHERE pr.risk_level='HIGH'
        ORDER BY pr.crrt_probability DESC
    """)

    return generate_report_pdf(
        "High Risk Patient Report",
        build_pdf_table(records, highrisk=True),
        "highrisk_report.pdf",
        colors.red
    )


# ==================================================
# CSV EXPORT HELPER
# ==================================================
def export_records_csv(records, filename):

    df = pd.DataFrame(records)

    csv_buffer = BytesIO()

    df.to_csv(csv_buffer, index=False)

    csv_buffer.seek(0)

    return send_file(
        csv_buffer,
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename
    )


# ==================================================
# EXPORT ALL CSV
# ==================================================
@app.route("/export_csv")
def export_csv():

    if "user" not in session:
        return redirect("/")

    records = fetch_report_rows("""
        SELECT
            p.patient_code,
            p.full_name,
            p.age,
            p.gender,
            pr.creatinine,
            pr.lactate,
            pr.ph,
            pr.bun,
            pr.urine,
            pr.map,
            pr.crrt_probability,
            pr.risk_level,
            pr.created_at
        FROM predictions pr
        LEFT JOIN patients p
            ON p.id = pr.patient_id
        ORDER BY pr.created_at DESC
    """)

    return export_records_csv(
        records,
        "crrt_report.csv"
    )


# ==================================================
# EXPORT DAILY CSV
# ==================================================
@app.route("/export_daily_csv")
def export_daily_csv():

    if "user" not in session:
        return redirect("/")

    records = fetch_report_rows("""
        SELECT
            p.patient_code,
            p.full_name,
            pr.crrt_probability,
            pr.risk_level,
            pr.created_at
        FROM predictions pr
        LEFT JOIN patients p
            ON p.id = pr.patient_id
        WHERE DATE(pr.created_at)=CURDATE()
        ORDER BY pr.created_at DESC
    """)

    return export_records_csv(
        records,
        "daily_report.csv"
    )


# ==================================================
# EXPORT WEEKLY CSV
# ==================================================
@app.route("/export_weekly_csv")
def export_weekly_csv():

    if "user" not in session:
        return redirect("/")

    records = fetch_report_rows("""
        SELECT
            p.patient_code,
            p.full_name,
            pr.crrt_probability,
            pr.risk_level,
            pr.created_at
        FROM predictions pr
        LEFT JOIN patients p
            ON p.id = pr.patient_id
        WHERE pr.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        ORDER BY pr.created_at DESC
    """)

    return export_records_csv(
        records,
        "weekly_report.csv"
    )


# ==================================================
# EXPORT MONTHLY CSV
# ==================================================
@app.route("/export_monthly_csv")
def export_monthly_csv():

    if "user" not in session:
        return redirect("/")

    month = request.args.get("month")
    year = request.args.get("year")

    if not month or not year:
        return "Please select month and year."

    records = fetch_report_rows("""
        SELECT
            p.patient_code,
            p.full_name,
            pr.crrt_probability,
            pr.risk_level,
            pr.created_at
        FROM predictions pr
        LEFT JOIN patients p
            ON p.id = pr.patient_id
        WHERE MONTH(pr.created_at) = %s
        AND YEAR(pr.created_at) = %s
        ORDER BY pr.created_at DESC
    """, (month, year))

    return export_records_csv(
        records,
        f"monthly_report_{month}_{year}.csv"
    )


# ==================================================
# EXPORT HIGH RISK CSV
# ==================================================
@app.route("/export_highrisk_csv")
def export_highrisk_csv():

    if "user" not in session:
        return redirect("/")

    records = fetch_report_rows("""
        SELECT
            p.patient_code,
            p.full_name,
            p.age,
            p.gender,
            pr.crrt_probability,
            pr.risk_level,
            pr.priority_score,
            pr.created_at
        FROM predictions pr
        LEFT JOIN patients p
            ON p.id = pr.patient_id
        WHERE pr.risk_level='HIGH'
        ORDER BY pr.crrt_probability DESC
    """)

    return export_records_csv(
        records,
        "highrisk_report.csv"
    )

# ==================================================
# BATCH PDF EXPORT
# ==================================================
@app.route("/export_pdf")
def export_pdf():

    if "user" not in session:
        return redirect("/")

    batch_ids = session.get("last_batch_ids", [])

    if not batch_ids:
        return "No recent batch upload found."

    placeholders = ",".join(["%s"] * len(batch_ids))

    records = fetch_report_rows(f"""
        SELECT
            p.patient_code,
            p.full_name,
            pr.creatinine,
            pr.lactate,
            pr.ph,
            pr.bun,
            pr.urine,
            pr.map,
            pr.crrt_probability,
            pr.risk_level
        FROM predictions pr
        LEFT JOIN patients p
            ON p.id = pr.patient_id
        WHERE pr.id IN ({placeholders})
        ORDER BY pr.id DESC
    """, tuple(batch_ids))

    total = len(records)
    high = sum(1 for r in records if str(r.get("risk_level")).upper() == "HIGH")
    medium = sum(1 for r in records if str(r.get("risk_level")).upper() == "MEDIUM")
    low = sum(1 for r in records if str(r.get("risk_level")).upper() == "LOW")

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("CRRT Clinical Decision Support System Report", styles["Title"]))
    elements.append(Paragraph(
        f"Generated On: {datetime.now().strftime('%d %B %Y %H:%M')}",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 20))

    summary_data = [
        ["Metric", "Count"],
        ["Total Assessments", total],
        ["High Risk", high],
        ["Medium Risk", medium],
        ["Low Risk", low]
    ]

    summary_table = Table(summary_data, colWidths=[250, 120])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.darkblue),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), 1, colors.black),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN", (0,0), (-1,-1), "CENTER")
    ]))

    elements.append(Paragraph("Executive Summary", styles["Heading2"]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    table_data = [[
        "Patient ID",
        "Creatinine",
        "Lactate",
        "pH",
        "BUN",
        "Urine",
        "MAP",
        "Probability",
        "Risk"
    ]]

    for row in records:
        table_data.append([
            row.get("patient_code") or "-",
            row.get("creatinine") or "-",
            row.get("lactate") or "-",
            row.get("ph") or "-",
            row.get("bun") or "-",
            row.get("urine") or "-",
            row.get("map") or "-",
            f"{float(row.get('crrt_probability') or 0) * 100:.2f}%",
            row.get("risk_level") or "-"
        ])

    patient_table = Table(table_data, repeatRows=1)
    patient_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.darkblue),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), 1, colors.black),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("ALIGN", (0,0), (-1,-1), "CENTER")
    ]))

    elements.append(Paragraph("Patient Prediction Results", styles["Heading2"]))
    elements.append(patient_table)
    elements.append(Spacer(1,20))
    elements.append(Paragraph(
        "This report was automatically generated by the CRRT Clinical Decision Support System (CDSS).",
        styles["Italic"]
    ))

    doc.build(elements)
    buffer.seek(0)

    response = send_file(buffer, mimetype="application/pdf")
    response.headers["Content-Disposition"] = "inline; filename=CRRT_Clinical_Report.pdf"

    return response


# ==================================================
# BATCH PREVIEW
# Upload CSV and preview only, do not save to database
# ==================================================
@app.route("/batch-preview", methods=["POST"])
def batch_preview():

    try:

        if "file" not in request.files:
            return jsonify({
                "success": False,
                "error": "No file uploaded"
            }), 400

        file = request.files["file"]

        filename = file.filename.lower()

        if filename.endswith(".csv"):
            df = pd.read_csv(file)

        elif filename.endswith(".xlsx"):
            df = pd.read_excel(file)

        else:
            return jsonify({
                "success": False,
                "error": "Only CSV and Excel (.xlsx) files are supported."
            }), 400

        print("CSV Columns:")
        print(df.columns.tolist())

        required_columns = [
            "patient_id",
            "patient_name",
            "age",
            "gender",
            "creatinine",
            "lactate",
            "ph",
            "bun",
            "map",
            "urine_output"
        ]

        missing = [
            col for col in required_columns
            if col not in df.columns
        ]

        if missing:
            return jsonify({
                "success": False,
                "error": f"Missing columns: {', '.join(missing)}"
            }), 400

        df = df[required_columns]

        preview_data = []

        for _, row in df.iterrows():

            preview_data.append({
                "patient_id": str(row["patient_id"]),
                "patient_name": str(row["patient_name"]),
                "age": int(row["age"]),
                "gender": str(row["gender"]),

                "creatinine": float(row["creatinine"]),
                "lactate": float(row["lactate"]),
                "ph": float(row["ph"]),
                "bun": float(row["bun"]),
                "map": float(row["map"]),
                "urine_output": float(row["urine_output"])
            })

        session["batch_preview_data"] = preview_data

        return jsonify({
            "success": True,
            "message": f"{len(preview_data)} records ready for preview",
            "data": preview_data
        })

    except Exception as e:

        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ==================================================
# BATCH CONFIRM
# Confirm preview, predict and save to database
# ==================================================
@app.route("/batch-confirm", methods=["POST"])
def batch_confirm():

    conn = None
    cur = None

    try:

        preview_data = session.get("batch_preview_data", [])

        if not preview_data:
            return jsonify({
                "success": False,
                "error": "No preview data found. Please upload CSV first."
            }), 400

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        results = []
        batch_prediction_ids = []

        for row in preview_data:

            features = pd.DataFrame([[
                float(row["creatinine"]),
                float(row["lactate"]),
                float(row["ph"]),
                float(row["bun"]),
                float(row["map"]),
                float(row["urine_output"])
            ]], columns=[
                "creatinine",
                "lactate",
                "ph",
                "bun",
                "map",
                "urine_output"
            ])

            prob = float(model.predict_proba(features)[0][1])
            risk, priority = get_risk(prob)

            # Check if patient already exists
            cur.execute(
                "SELECT id FROM patients WHERE patient_code=%s",
                (row["patient_id"],)
            )

            patient = cur.fetchone()

            if patient:
                patient_db_id = patient["id"]

            else:
                cur.execute("""
                    INSERT INTO patients
                    (
                        patient_code,
                        full_name,
                        age,
                        gender
                    )
                    VALUES
                    (%s,%s,%s,%s)
                """, (
                    row["patient_id"],
                    row["patient_name"],
                    row["age"],
                    row["gender"]
                ))

                patient_db_id = cur.lastrowid

            # Save prediction
            cur.execute("""
                INSERT INTO predictions
                (
                    patient_id,
                    creatinine,
                    lactate,
                    ph,
                    bun,
                    urine,
                    map,
                    crrt_probability,
                    risk_level,
                    priority_score
                )
                VALUES
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                patient_db_id,
                float(row["creatinine"]),
                float(row["lactate"]),
                float(row["ph"]),
                float(row["bun"]),
                float(row["urine_output"]),
                float(row["map"]),
                prob,
                risk,
                priority
            ))

            prediction_id = cur.lastrowid
            batch_prediction_ids.append(prediction_id)

            results.append({
                "patient_id": row["patient_id"],
                "patient_name": row["patient_name"],
                "age": row["age"],
                "gender": row["gender"],

                "creatinine": float(row["creatinine"]),
                "lactate": float(row["lactate"]),
                "ph": float(row["ph"]),
                "bun": float(row["bun"]),
                "map": float(row["map"]),
                "urine_output": float(row["urine_output"]),

                "crrt_probability": round(prob, 4),
                "risk_level": risk,
                "priority_score": priority
            })

        conn.commit()

        session["last_batch_ids"] = batch_prediction_ids
        session["last_batch_results"] = results

        session.pop("batch_preview_data", None)

        return jsonify({
            "success": True,
            "message": f"Successfully predicted and saved {len(results)} patients",
            "results": results
        })

    except Exception as e:

        if conn:
            conn.rollback()

        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()
            
# ==================================================
# RUN APP
# ==================================================
if __name__ == "__main__":

    app.run(debug=True)