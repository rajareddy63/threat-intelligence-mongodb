#!/usr/bin/env python3
"""Usage: python3 make_pdf.py "Your Name" "USN" https://hub.docker.com/r/<user>/lab12-mongo"""
import sys
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

name, usn, url = sys.argv[1:4]
c = canvas.Canvas("Lab12_Submission.pdf", pagesize=A4)
y = 800
def line(t, size=12, gap=22):
    global y
    c.setFont("Helvetica", size); c.drawString(60, y, t); y -= gap
line("Chapter 12 - MongoDB Security Labs (12.1 RBAC, 12.2 TLS)", 16, 34)
line(f"Name: {name}"); line(f"USN: {usn}", gap=34)
line("Docker Hub URL:", 13); line(url, 12, 34)
line("Run:  docker run -it --rm " + url.split("/r/")[-1] + "  then  /lab/run_labs.sh", 11, 34)
line("Lab 12.1: --auth, admin + app_user_read/app_user_write/hr_user, salary-redaction view", 11)
line("Lab 12.2: OpenSSL CA/server/client certs, requireTLS, PyMongo TLS find_one, cryptography script", 11)
c.save()
