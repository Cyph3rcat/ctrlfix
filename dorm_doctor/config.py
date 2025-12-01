"""Configuration for DormDoctorDiagnostics
Contains API keys, constants, and configuration values.
"""
import os
import json
import tempfile
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# API Keys and Credentials
DIALOGFLOW_PROJECT_ID = "ctrlfix-479512"

# Helper function to get credentials path (supports env var JSON or file path)
def _get_credentials_path(env_var_name, fallback_file_path):
    """
    Get credentials either from environment variable (JSON string) or file path.
    This allows Railway deployment without committing JSON files to git.
    """
    json_content = os.getenv(env_var_name)
    
    if json_content:
        # Create temporary file with JSON content from env var
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        temp_file.write(json_content)
        temp_file.close()
        return temp_file.name
    else:
        # Fall back to local file path
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", fallback_file_path))

# Vertex service account JSON (the file ending with ...216d)
VERTEX_CREDENTIALS_PATH = _get_credentials_path(
    "VERTEX_CREDENTIALS_JSON",
    "ctrlfix-479512-6f3bedef216d.json"
)

# Primary service account used for Dialogflow and Google Sheets
SERVICE_ACCOUNT_JSON = _get_credentials_path(
    "SERVICE_ACCOUNT_JSON", 
    "ctrlfix-479512-5181093c4568.json"
)

# Backwards-compatible aliases
DIALOGFLOW_CREDENTIALS_PATH = SERVICE_ACCOUNT_JSON

# SerpAPI - for Amazon price scraping (loaded from .env)
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")

# Google Sheets - uses the primary service account by default
GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON = SERVICE_ACCOUNT_JSON
GOOGLE_SHEETS_SPREADSHEET_NAME = "ctrlfixrepairs"  # Name of your Google Sheet
GOOGLE_SHEETS_SPREADSHEET_TAB = "Sheet1"  # Name of the tab/sheet within the spreadsheet

# Currency
CURRENCY = "HKD"
BASE_DIAGNOSTIC_FEE = 100.0  # HKD - Standard service fee
BASE_SERVICE_FEE = 100.0  # HKD - Same as diagnostic fee

# Phone number validation (Hong Kong format)
PHONE_PATTERN = r"^\+852\s?\d{4}\s?\d{4}$"

# Diagnostic steps enumeration - UPDATED FLOW
class DiagnosticStep:
    WELCOME = 0
    PHONE_NUMBER = 1
    USER_NAME = 2  # Collect first and last name
    DEVICE_TYPE = 3  # Gemini + entity fulfillment loop
    DEVICE_BRAND_MODEL = 4  # Gemini + entity fulfillment loop
    ADDITIONAL_INFO = 5  # Optional additional device info collection
    ISSUE_TYPE = 6  # Arrow key selection
    PROBLEM_DESCRIPTION = 7  # Literal form input
    DIAGNOSTIC_OPTIN = 8  # Ask if user wants diagnostic
    DIAGNOSTIC_MODE = 9  # Open Gemini dialogue (if opted in)
    COST_ESTIMATION = 10  # Service fee + Taobao API parts
    FINAL_BOOKING = 11  # Arrow key: Instant drop-off vs Contact mechanic
    GOODBYE = 12

# Issue types - for arrow key menu
ISSUE_TYPE_OPTIONS = [
    "Software (apps, OS, performance, viruses)",
    "Hardware (screen, battery, ports, physical damage)",
    "Unsure"
]

ISSUE_TYPE_MAPPING = {
    0: "software",
    1: "hardware",
    2: "unsure"
}

# Booking options - for arrow key menu
BOOKING_OPTIONS = [
    "Instant drop-off service (faster if you're sure about the issue)",
    "Contact mechanic first for further consultation"
]

BOOKING_MAPPING = {
    0: "instant_dropoff",
    1: "contact_first"
}

# Dialogflow interrupt intents (user asking questions mid-flow)
# Dialogflow is now ONLY for handling interrupts
INTERRUPT_INTENTS = [
    "greeting",             # "hello", "hi", etc.
    "location.question",    # "where are you based?"
    "pricing.question",     # "how much does this cost?"
    "timeline.question",    # "how long will it take?"
    "warranty.question",    # "is this covered by warranty?"
    "help.request",         # "I don't understand"
    "data.safety"           # "will I lose my data?"
]

# Drop-off address (placeholder)
DROPOFF_ADDRESS = "Room 939a, Homantin Halls, Polyu"
MECHANIC_CONTACT = "+852 5489 9626"

# Google Sheets columns
SHEETS_COLUMNS = [
    "ticket_id",
    "timestamp",
    "phone_number",
    "user_name",
    "device_type",
    "device_brandmodel",
    "device_additional_info",
    "issue_type",
    "problem_description",
    "diagnostic_completed",
    "parts_needed",
    "estimated_cost",
    "appointment_status"
]

# ANSI Color Codes for pretty terminal output
class Colors:
    """ANSI color codes for terminal styling"""
    # Text colors
    LIGHT_BLUE = "\033[94m"      # Main text (light blue)
    PINK = "\033[95m"            # Numbers (pink/magenta)
    YELLOW = "\033[93m"          # Bot labels (yellow)
    GREEN = "\033[92m"           # Success messages (green)
    CYAN = "\033[96m"            # Diagnostic info (cyan)
    RED = "\033[91m"             # Errors/warnings (red)
    WHITE = "\033[97m"           # Important info (white)
    GRAY = "\033[90m"            # Subtle info (gray)
    
    # Styles
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"            # Reset to default
    
    @staticmethod
    def bot(text):
        """Format bot messages in yellow"""
        return f"{Colors.YELLOW}[Bot]{Colors.RESET} {Colors.LIGHT_BLUE}{text}{Colors.RESET}"
    
    @staticmethod
    def user(text):
        """Format user input in white"""
        return f"{Colors.WHITE}You:{Colors.RESET} {text}"
    
    @staticmethod
    def number(value):
        """Format numbers in pink"""
        return f"{Colors.PINK}{value}{Colors.RESET}"
    
    @staticmethod
    def success(text):
        """Format success messages in green"""
        return f"{Colors.GREEN}✓ {text}{Colors.RESET}"
    
    @staticmethod
    def error(text):
        """Format error messages in red"""
        return f"{Colors.RED}✗ {text}{Colors.RESET}"
    
    @staticmethod
    def diagnostic(text):
        """Format diagnostic info in cyan"""
        return f"{Colors.CYAN}{text}{Colors.RESET}"
    
    @staticmethod
    def highlight(text):
        """Format highlighted text in bold white"""
        return f"{Colors.BOLD}{Colors.WHITE}{text}{Colors.RESET}"
