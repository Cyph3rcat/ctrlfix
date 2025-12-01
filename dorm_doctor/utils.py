"""Utility helpers for DormDoctorDiagnostics"""
import uuid
import json
import os
import re
from datetime import datetime
from dorm_doctor.config import PHONE_PATTERN


def generate_ticket_id():
    """Generate a unique ticket ID using UUID4."""
    return str(uuid.uuid4())[:8].upper()  # Short format for easier reference


def validate_phone_number(phone):
    """Validate Hong Kong phone number format (+852 XXXX XXXX)."""
    pattern = re.compile(PHONE_PATTERN)
    return bool(pattern.match(phone.strip()))


def format_phone_number(phone):
    """Format phone number to standard HK format."""
    # Remove spaces and ensure +852 prefix
    cleaned = phone.strip().replace(" ", "")
    if not cleaned.startswith("+852"):
        if cleaned.startswith("852"):
            cleaned = "+" + cleaned
        else:
            cleaned = "+852" + cleaned
    # Add space for readability: +852 XXXX XXXX
    if len(cleaned) == 12:  # +852 + 8 digits
        return f"{cleaned[:4]} {cleaned[4:8]} {cleaned[8:]}"
    return cleaned


def get_timestamp():
    """Get current timestamp in ISO format."""
    return datetime.now().isoformat()


def save_ticket_local(ticket, path=None):
    """Append ticket to a local JSON file for simple persistence."""
    path = path or os.path.join(os.path.dirname(__file__), "..", "tickets.json")
    # normalize path
    path = os.path.abspath(path)
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = []
    except Exception:
        data = []

    data.append(ticket)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Warning: failed to save ticket locally: {e}")


def clean_input(text):
    """Clean and normalize user input."""
    return text.strip().lower() if text else ""
