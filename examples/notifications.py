"""Example: Alert notifications via email and Slack."""

import os
from typing import Optional

import requests
from flask_mail import Mail, Message

# Configure Flask-Mail
# pip install flask-mail

mail = None


def init_mail(app):
    """Initialize mail configuration."""
    global mail
    app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", 587))
    app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
    app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER", "trainwatch@example.com")
    mail = Mail(app)


def send_critical_alert_email(alert: dict):
    """Send email for critical alert."""
    if not mail:
        return

    recipient = os.getenv("ALERT_EMAIL", "ops@example.com")
    msg = Message(
        subject=f"🚆 CRITICAL: {alert['trainId']} - {alert['sensor']}",
        recipients=[recipient],
        html=f"""
        <h2>Critical Alert: {alert['trainId']}</h2>
        <p><strong>Sensor:</strong> {alert['sensor']}</p>
        <p><strong>Detector:</strong> {alert['detector']}</p>
        <p><strong>Peak value:</strong> {alert['peak']}</p>
        <p><strong>Active since:</strong> {alert['startedTs']}</p>
        <hr>
        <p><strong>Recommendation:</strong></p>
        <p>{alert['recommendation']}</p>
        <hr>
        <p><a href="https://trainwatch.example.com/train/{alert['trainId']}">
            View in dashboard →
        </a></p>
        """,
    )
    mail.send(msg)


def send_slack_notification(alert: dict):
    """Post alert to Slack channel."""
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        return

    color = "danger" if alert["severity"] == "crit" else "warning"
    payload = {
        "attachments": [
            {
                "color": color,
                "title": f"{alert['trainId']} - {alert['sensor']}",
                "fields": [
                    {"title": "Severity", "value": alert["severity"].upper(), "short": True},
                    {"title": "Detector", "value": alert["detector"], "short": True},
                    {"title": "Peak value", "value": str(alert["peak"]), "short": True},
                    {"title": "Active", "value": "Yes" if alert["active"] else "Resolved", "short": True},
                    {
                        "title": "Recommendation",
                        "value": alert["recommendation"],
                        "short": False,
                    },
                ],
                "actions": [
                    {
                        "type": "button",
                        "text": "View in dashboard",
                        "url": f"https://trainwatch.example.com/train/{alert['trainId']}",
                    }
                ],
            }
        ]
    }
    requests.post(webhook_url, json=payload)


def send_pagerduty_incident(alert: dict):
    """Create PagerDuty incident for critical alerts."""
    pagerduty_key = os.getenv("PAGERDUTY_INTEGRATION_KEY")
    if not pagerduty_key or alert["severity"] != "crit":
        return

    payload = {
        "routing_key": pagerduty_key,
        "event_action": "trigger",
        "dedup_key": f"{alert['trainId']}:{alert['sensor']}",
        "payload": {
            "summary": f"Critical: {alert['trainId']} - {alert['sensor']}",
            "severity": "critical",
            "source": "TrainWatch",
            "component": alert["trainId"],
            "custom_details": {
                "sensor": alert["sensor"],
                "peak": alert["peak"],
                "detector": alert["detector"],
                "recommendation": alert["recommendation"],
            },
        },
        "links": [
            {
                "href": f"https://trainwatch.example.com/train/{alert['trainId']}",
                "text": "View in dashboard",
            }
        ],
    }
    requests.post("https://events.pagerduty.com/v2/enqueue", json=payload)


# Usage in Flask app:
#
# from flask import Flask
# from examples.notifications import init_mail, send_critical_alert_email
#
# app = Flask(__name__)
# init_mail(app)
#
# @app.route("/api/alerts", methods=["POST"])
# def handle_alert():
#     alert = request.json
#     if alert["severity"] == "crit":
#         send_critical_alert_email(alert)
#     return jsonify({"status": "alert processed"}), 200
#
# Environment variables (.env):
# MAIL_SERVER=smtp.gmail.com
# MAIL_PORT=587
# MAIL_USE_TLS=true
# MAIL_USERNAME=your-email@gmail.com
# MAIL_PASSWORD=your-app-password
# MAIL_DEFAULT_SENDER=trainwatch@example.com
# ALERT_EMAIL=ops@example.com
# SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
# PAGERDUTY_INTEGRATION_KEY=...
