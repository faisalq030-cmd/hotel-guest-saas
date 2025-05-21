from flask import Flask, render_template_string, send_file, url_for
from notion_client import Client
import qrcode
import os
import subprocess
from datetime import datetime

# Notion setup (best practice: use env variable for auth token)
NOTION_SECRET = os.environ.get("NOTION_TOKEN", "your_default_notion_token_here")
notion = Client(auth=NOTION_SECRET)
database_id = "1f095662fbd7805da4d3cefe15d8ba9d"

# Flask setup
app = Flask(__name__)

# Base URL for public links (use env in production)
BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:5000")

# Folder paths
QR_FOLDER = os.path.join(app.root_path, "static", "qrcodes")
PDF_FOLDER = os.path.join(app.root_path, "static", "pdfs")
os.makedirs(QR_FOLDER, exist_ok=True)
os.makedirs(PDF_FOLDER, exist_ok=True)

@app.route("/guest/<guest_name>/<created>")
def welcome_guest(guest_name, created):
    created_prefix = created[:10]

    response = notion.databases.query(
        database_id=database_id,
        filter={
            "property": "Guest Name",
            "title": {
                "equals": guest_name
            }
        }
    )

    guest = None
    for result in response["results"]:
        if result["created_time"].startswith(created_prefix):
            guest = result
            break

    if not guest:
        return f"No guest found with name: {guest_name} and created: {created}"

    props = guest["properties"]

    def safe_get(field, default="N/A"):
        return props.get(field, {}).get("rich_text", [{}])[0].get("plain_text", default)

    def safe_title(field, default="Guest"):
        return props.get(field, {}).get("title", [{}])[0].get("plain_text", default)

    def safe_select(field, default="Unknown"):
        return props.get(field, {}).get("select", {}).get("name", default)

    def safe_number(field, default="N/A"):
        return props.get(field, {}).get("number", default)

    def safe_date(field):
        return props.get(field, {}).get("date", {}).get("start", "N/A")

    guest_name_val = safe_title("Guest Name")
    room_number = safe_number("Room Number")
    room_type = safe_select("Room Type")
    phone = safe_get("Guest Phone Number")
    checkin = safe_date("Check-in Date")
    checkout = safe_date("Check-out Date")
    created_time = guest.get("created_time", "N/A")

    slug = f"{guest_name.lower().replace(' ', '-')}-{created.replace(':', '').replace('-', '')}"
    guest_url = f"{BASE_URL}/guest/{guest_name}/{created}"
    qr_filename = f"{slug}.png"
    qr_path = os.path.join(QR_FOLDER, qr_filename)
    qr_url = f"/static/qrcodes/{qr_filename}"

    if not os.path.exists(qr_path):
        img = qrcode.make(guest_url)
        img.save(qr_path)

    notion.pages.update(
        page_id=guest["id"],
        properties={
            "Welcome Page URL": {"url": guest_url},
            "QR Code URL": {"url": f"{BASE_URL}{qr_url}"}
        }
    )

    html = """ <!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Welcome {{ name }}</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f2f2f2; margin: 0; padding: 0; }
        .header { background-color: #003366; color: white; padding: 25px 0; text-align: center; font-size: 30px; font-weight: bold; letter-spacing: 1px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2); }
        .card { background-color: white; max-width: 700px; margin: 40px auto; padding: 40px; border-radius: 16px; box-shadow: 0 6px 20px rgba(0, 0, 0, 0.1); }
        .card h1 { color: #003366; font-size: 28px; margin-bottom: 20px; }
        .card p { font-size: 17px; line-height: 1.7; margin: 12px 0; }
        .card img { display: block; margin: 30px auto 20px; }
        .download-btn { display: block; width: 220px; margin: 20px auto; padding: 12px; background-color: #003366; color: white; text-align: center; text-decoration: none; border-radius: 8px; font-weight: bold; }
        .footer { text-align: center; font-size: 14px; color: #666; margin-top: 25px; }
    </style>
</head>
<body>
    <div class="header">Welcome to Royal Horizon Hotel</div>
    <div class="card">
        <h1>Hello, {{ name }}!</h1>
        <p><strong>Room Number:</strong> {{ room }}</p>
        <p><strong>Room Type:</strong> {{ type }}</p>
        <p><strong>Phone Number:</strong> {{ phone }}</p>
        <p><strong>Check-in:</strong> {{ checkin }}</p>
        <p><strong>Check-out:</strong> {{ checkout }}</p>
        <p><strong>Registered On:</strong> {{ created }}</p>
        <img src="{{ qr }}" width="180" alt="QR Code"/>
        <a class="download-btn" href="{{ pdf_url }}">Download as PDF</a>
        <div class="footer">Scan this QR code to revisit this welcome page.</div>
    </div>
</body>
</html>"""

    pdf_url = url_for("download_pdf", guest_name=guest_name, created=created)
    return render_template_string(html,
        name=guest_name_val,
        room=room_number,
        type=room_type,
        phone=phone,
        checkin=checkin,
        checkout=checkout,
        created=created_time,
        qr=qr_url,
        pdf_url=pdf_url
    )

@app.route("/guest/<guest_name>/<created>/pdf")
def download_pdf(guest_name, created):
    slug = f"{guest_name.lower().replace(' ', '-')}-{created.replace(':', '').replace('-', '')}"
    url = f"{BASE_URL}/guest/{guest_name}/{created}"
    pdf_filename = f"{slug}.pdf"
    pdf_path = os.path.join(PDF_FOLDER, pdf_filename)

    # Generate PDF using wkhtmltopdf if it doesn't exist
    if not os.path.exists(pdf_path):
        subprocess.run(["wkhtmltopdf", url, pdf_path])

    return send_file(pdf_path, as_attachment=True, download_name=f"{guest_name}_welcome.pdf")
