"""
DRAMeXchange Daily Alert
Screenshots the DRAM Spot Price, Module Spot Price, and Flash Spot Price tables,
emails as a PDF every day at 5 AM EST.
"""

import io
import os
import smtplib
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import img2pdf
from PIL import Image
from playwright.sync_api import sync_playwright


def capture_screenshot():
    """Capture the three spot price tables from DRAMeXchange."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 1800})

        print("Loading DRAMeXchange page...")
        page.goto("https://www.dramexchange.com/", wait_until="networkidle", timeout=60000)

        # Wait for AJAX-loaded price tables to populate
        page.wait_for_timeout(6000)

        screenshot_bytes = None
        try:
            # Find the top of the DRAM Spot Price section
            dram_heading = page.locator("text=DRAM Spot Price").first
            dram_heading.wait_for(timeout=10000)
            top_box = dram_heading.bounding_box()

            # Find the bottom of the Flash Spot Price section by locating its heading
            # then adding enough height to include all its rows
            flash_heading = page.locator("text=Flash Spot Price").first
            flash_heading.wait_for(timeout=10000)
            flash_box = flash_heading.bounding_box()

            # Flash table has ~5 rows; add 300px below the heading to capture them all
            bottom = flash_box["y"] + 300

            clip = {
                "x": max(0, top_box["x"] - 10),
                "y": max(0, top_box["y"] - 10),
                "width": 600,
                "height": bottom - top_box["y"] + 20,
            }
            screenshot_bytes = page.screenshot(clip=clip)
            print(f"Screenshot captured (height: {int(clip['height'])}px).")
        except Exception as e:
            print(f"Element-based capture failed, falling back to viewport: {e}")
            screenshot_bytes = page.screenshot()

        browser.close()

    return screenshot_bytes


def convert_to_pdf(screenshot_bytes):
    """Convert screenshot to PDF."""
    img = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    return img2pdf.convert(img_bytes.read())


def send_email(pdf_bytes, recipient_email):
    """Send the PDF as an email attachment via Gmail SMTP."""
    sender_email = os.environ.get("GMAIL_ADDRESS")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not sender_email or not app_password:
        raise ValueError("GMAIL_ADDRESS and GMAIL_APP_PASSWORD environment variables must be set.")

    date_str = datetime.now().strftime("%Y-%m-%d")

    msg = MIMEMultipart()
    msg["Subject"] = f"DRAMeXchange Spot Prices — {date_str}"
    msg["From"] = sender_email
    msg["To"] = recipient_email

    body = MIMEText(
        f"Attached: DRAM, Module, and Flash spot prices from DRAMeXchange for {date_str}.",
        "plain",
    )
    msg.attach(body)

    attachment = MIMEBase("application", "pdf")
    attachment.set_payload(pdf_bytes)
    encoders.encode_base64(attachment)
    attachment.add_header(
        "Content-Disposition",
        f"attachment; filename=dramexchange-{date_str}.pdf",
    )
    msg.attach(attachment)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, app_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())

    print(f"Email sent to {recipient_email}")


def main():
    recipient_email = "jt@lokoyacap.com"

    print(f"DRAMeXchange scraper — {datetime.now().strftime('%Y-%m-%d')}")
    screenshot_bytes = capture_screenshot()

    print("Generating PDF...")
    pdf_bytes = convert_to_pdf(screenshot_bytes)

    print("Sending email...")
    send_email(pdf_bytes, recipient_email)


if __name__ == "__main__":
    main()
