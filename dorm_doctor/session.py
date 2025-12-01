"""Session state management for DormDoctorDiagnostics
Tracks current step, user data, conversation history, and interrupt state.
"""
from dorm_doctor.config import DiagnosticStep
from dorm_doctor.utils import generate_ticket_id, get_timestamp


class Session:
    """Manages the state of a single diagnostic session."""
    
    def __init__(self):
        self.ticket_id = generate_ticket_id()
        self.current_step = DiagnosticStep.WELCOME
        self.user_data = {
            "ticket_id": self.ticket_id,
            "timestamp": get_timestamp(),
            "phone_number": None,
            "user_name": None,
            "device": {
                "type": None,
                "brandmodel": None,
                "additional_info": None
            },
            "issue_type": None,
            "description": None,
            "photos": [],
            "parts_needed": [],
            "service_fee": None,
            "parts_cost": None,
            "estimated_total": None,
            "diagnostic_opted_in": False,
            "appointment_status": "pending"
        }
        self.conversation_history = []
        self.interrupted = False
        self.skip_diagnostics = False
        
    def add_message(self, role, content):
        """Add a message to conversation history.
        
        Args:
            role: 'user' or 'bot'
            content: message text
        """
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": get_timestamp()
        })
    
    def set_step(self, step):
        """Update current diagnostic step."""
        self.current_step = step
        
    def next_step(self):
        """Move to next step in the flow."""
        self.current_step += 1
        
    def get_step(self):
        """Get current step."""
        return self.current_step
    
    def update_data(self, key, value):
        """Update user data with a key-value pair."""
        if "." in key:  # Nested key like "device.type"
            parts = key.split(".")
            if parts[0] in self.user_data and isinstance(self.user_data[parts[0]], dict):
                self.user_data[parts[0]][parts[1]] = value
        else:
            self.user_data[key] = value
    
    def get_data(self, key):
        """Get user data by key."""
        if "." in key:  # Nested key
            parts = key.split(".")
            if parts[0] in self.user_data:
                return self.user_data[parts[0]].get(parts[1])
        return self.user_data.get(key)
    
    def mark_interrupted(self):
        """Mark session as interrupted (user asked something off-topic)."""
        self.interrupted = True
        
    def clear_interrupt(self):
        """Clear interrupt flag after handling."""
        self.interrupted = False
    
    def is_interrupted(self):
        """Check if session is currently interrupted."""
        return self.interrupted
    
    def to_dict(self):
        """Convert session to dictionary for persistence."""
        return {
            "ticket_id": self.ticket_id,
            "current_step": self.current_step,
            "user_data": self.user_data,
            "conversation_history": self.conversation_history,
            "interrupted": self.interrupted,
            "skip_diagnostics": self.skip_diagnostics
        }
    
    def get_ticket_data(self):
        """Get formatted ticket data for Google Sheets."""
        device = self.user_data["device"]
        parts_needed = self.user_data.get("parts_needed", [])
        parts_str = ", ".join(parts_needed) if parts_needed else "None"
        
        # Format estimated cost
        estimated_cost = self.user_data.get("estimated_total")
        if estimated_cost:
            from dorm_doctor.config import CURRENCY
            estimated_cost = f"{CURRENCY} {estimated_cost:.2f}"
        else:
            estimated_cost = "N/A"
        
        return {
            "ticket_id": self.ticket_id,
            "timestamp": self.user_data["timestamp"],
            "phone_number": self.user_data.get("phone_number", "N/A"),
            "user_name": self.user_data.get("user_name", "N/A"),
            "device_type": device.get("type", "N/A"),
            "device_brandmodel": device.get("brandmodel", "N/A"),
            "device_additional_info": device.get("additional_info", "N/A"),
            "issue_type": self.user_data.get("issue_type", "N/A"),
            "problem_description": self.user_data.get("description", "N/A"),
            "diagnostic_completed": "Yes" if self.user_data.get("diagnostic_opted_in") else "No",
            "parts_needed": parts_str,
            "estimated_cost": estimated_cost,
            "appointment_status": self.user_data.get("appointment_status", "pending")
        }
