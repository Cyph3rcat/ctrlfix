"""Google Sheets client for ticket logging
Automatically tries to use real Google Sheets API, falls back to mock if not available.
"""
from dorm_doctor.config import GOOGLE_SHEETS_SPREADSHEET_TAB, SHEETS_COLUMNS
import os


class GoogleSheetsClient:
    """Google Sheets client for ticket logging."""
    
    def __init__(self, credentials_path=None, spreadsheet_name=None):
        # Get credentials path and spreadsheet name from config
        from dorm_doctor.config import GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON, GOOGLE_SHEETS_SPREADSHEET_NAME
        
        self.credentials_path = credentials_path or GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON
        self.spreadsheet_name = spreadsheet_name or GOOGLE_SHEETS_SPREADSHEET_NAME
        self.client = None
        self.sheet = None
        
        # Try to initialize real Google Sheets client
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            creds = Credentials.from_service_account_file(self.credentials_path, scopes=scopes)
            self.client = gspread.authorize(creds)
            
            # Open spreadsheet by name
            spreadsheet = self.client.open(self.spreadsheet_name)
            
            # Try to get worksheet by common names, fallback to first sheet
            try:
                self.sheet = spreadsheet.worksheet(GOOGLE_SHEETS_SPREADSHEET_TAB)
            except gspread.WorksheetNotFound:
                try:
                    self.sheet = spreadsheet.worksheet("Sheet1")
                except gspread.WorksheetNotFound:
                    # Fallback to first sheet
                    self.sheet = spreadsheet.sheet1
            
            # Ensure headers are in row 1 (only if row 1 is completely empty)
            try:
                existing_headers = self.sheet.row_values(1)
                if not existing_headers or all(not cell for cell in existing_headers):
                    # Row 1 is empty - add headers
                    self.sheet.update('A1', [SHEETS_COLUMNS])
                    print(f"[GoogleSheetsClient] ✅ Initialized headers in row 1")
            except Exception as e:
                print(f"[GoogleSheetsClient] ⚠️  Could not check/set headers: {e}")
            
            print(f"[GoogleSheetsClient] ✅ Connected to '{self.spreadsheet_name}' (worksheet: {self.sheet.title})")
        except ImportError as e:
            print(f"[GoogleSheetsClient] ⚠️  gspread not installed - using mock mode")
            print(f"[GoogleSheetsClient]    Install with: pip install gspread google-auth")
        except gspread.SpreadsheetNotFound:
            print(f"[GoogleSheetsClient] ⚠️  Spreadsheet '{self.spreadsheet_name}' not found")
            print(f"[GoogleSheetsClient]    Create it in Google Sheets or check the name in config.py")
            print(f"[GoogleSheetsClient]    Using mock mode")
        except FileNotFoundError:
            print(f"[GoogleSheetsClient] ⚠️  Service account file not found: {self.credentials_path}")
            print(f"[GoogleSheetsClient]    Using mock mode")
        except Exception as e:
            print(f"[GoogleSheetsClient] ⚠️  Failed to connect: {type(e).__name__}: {e}")
            print(f"[GoogleSheetsClient]    Using mock mode")
        
    def add_ticket(self, ticket_data):
        """Add a ticket to Google Sheets.
        
        Args:
            ticket_data: dict with ticket information matching SHEETS_COLUMNS
            
        Returns:
            bool: Success status
        """
        if self.sheet:
            # Real Google Sheets API call
            try:
                # Build row data matching SHEETS_COLUMNS order
                row = [ticket_data.get(col, "N/A") for col in SHEETS_COLUMNS]
                
                # Append as a new row (will go to next empty row after row 1 headers)
                self.sheet.append_row(row, value_input_option='USER_ENTERED')
                
                print("\n" + "="*60)
                print("📊 GOOGLE SHEETS UPDATED")
                print("="*60)
                print(f"Spreadsheet: {self.spreadsheet_name}")
                print(f"Ticket ID: {ticket_data.get('ticket_id')}")
                print(f"User: {ticket_data.get('user_name')}")
                print(f"Phone: {ticket_data.get('phone_number')}")
                print(f"Device: {ticket_data.get('device_brandmodel')} ({ticket_data.get('device_type')})")
                print(f"Issue: {ticket_data.get('issue_type')}")
                print(f"Parts: {ticket_data.get('parts_needed')}")
                print(f"Cost: {ticket_data.get('estimated_cost')}")
                print(f"Status: {ticket_data.get('appointment_status')}")
                print("="*60 + "\n")
                return True
            except Exception as e:
                print(f"\n❌ [Google Sheets] Failed to add ticket: {e}")
                return False
        else:
            # Mock implementation
            print("\n" + "="*60)
            print("📊 GOOGLE SHEETS UPDATED (Mock)")
            print("="*60)
            print(f"Ticket ID: {ticket_data.get('ticket_id')}")
            print(f"User: {ticket_data.get('user_name')}")
            print(f"Phone: {ticket_data.get('phone_number')}")
            print(f"Device: {ticket_data.get('device_brandmodel')} ({ticket_data.get('device_type')})")
            print(f"Issue: {ticket_data.get('issue_type')}")
            print(f"Parts: {ticket_data.get('parts_needed')}")
            print(f"Cost: {ticket_data.get('estimated_cost')}")
            print(f"Status: {ticket_data.get('appointment_status')}")
            print("="*60 + "\n")
            return True
    
    def get_ticket_by_id(self, ticket_id):
        """Retrieve a ticket by ticket ID (Phase 2)."""
        # TODO Phase 2: Search sheet for ticket_id and return row
        pass
    
    def update_ticket_status(self, ticket_id, status):
        """Update appointment status for a ticket (Phase 2)."""
        # TODO Phase 2: Find ticket row and update appointment_status column
        pass

