"""Dialogflow ES client for intent detection

Install: pip install google-cloud-dialogflow
"""
from dorm_doctor.config import DIALOGFLOW_PROJECT_ID, DIALOGFLOW_CREDENTIALS_PATH
import os
from google.cloud import dialogflow


class DialogflowClient:
    """Dialogflow ES client for intent detection."""
    
    def __init__(self, project_id=None, credentials_path=None):
        self.project_id = project_id or DIALOGFLOW_PROJECT_ID
        self.credentials_path = credentials_path or DIALOGFLOW_CREDENTIALS_PATH
        
        if not os.path.exists(self.credentials_path):
            raise FileNotFoundError(f"Dialogflow credentials not found at {self.credentials_path}")
        
        # Set credentials environment variable for Google Cloud
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = self.credentials_path
        
        try:
            self.session_client = dialogflow.SessionsClient()
            print(f"[DialogflowClient] ✓ Connected to Dialogflow ES (Project: {self.project_id})")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Dialogflow: {e}")
    
    def detect_intent(self, session_id, text, language_code="en"):
        """Detect intent from user input.
        
        Args:
            session_id: Unique session identifier
            text: User input text
            language_code: Language code (default: en)
            
        Returns:
            dict with keys:
                - intent: detected intent name
                - confidence: confidence score (0-1)
                - parameters: extracted parameters
                - fulfillment_text: response text
        """
        return self._detect_intent(session_id, text, language_code)
    
    def _validate_hk_phone_number(self, phone_number):
        """Validate and normalize Hong Kong phone numbers.
        
        Accepts formats like:
        - +852 7832 7832
        - +85283929032
        - 8903 9302
        - 93438930
        - Any whitespace combination
        
        Returns normalized format: +852 XXXX XXXX
        """
        import re
        
        # Extract only digits from the input
        digits_only = re.sub(r'\D', '', phone_number)
        
        # Remove 852 prefix if present
        if digits_only.startswith('852'):
            digits_only = digits_only[3:]
        
        # Check if we have exactly 8 digits
        if len(digits_only) != 8:
            return False, f"Phone number must have 8 digits. You provided {len(digits_only)} digits."
        
        # Format to +852 XXXX XXXX
        formatted_phone = f"+852 {digits_only[:4]} {digits_only[4:]}"
        return True, formatted_phone

    def _detect_intent(self, session_id, text, language_code):
        """Call Dialogflow ES API."""
        try:
            session_path = self.session_client.session_path(self.project_id, session_id)
            text_input = dialogflow.TextInput(text=text, language_code=language_code)
            query_input = dialogflow.QueryInput(text=text_input)

            response = self.session_client.detect_intent(
                request={"session": session_path, "query_input": query_input}
            )

            # Check if the intent is phone_number and validate
            parsed_response = self._parse_response(response)
            print(f"[DialogflowClient] Detected intent: {parsed_response['intent']}, dialogflow successfully called.")
            
            if parsed_response["intent"] == "phone_number":
                # Get phone parameter - handle different possible parameter names
                phone_value = (parsed_response["parameters"].get("phone") or 
                              parsed_response["parameters"].get("phone-number") or 
                              parsed_response["parameters"].get("phone_number") or
                              text)  # Fallback to raw user input
                
                print(f"[DialogflowClient] Phone parameter extracted: '{phone_value}'")
                print(f"[DialogflowClient] All parameters: {parsed_response['parameters']}")
                
                # Only validate if we have a non-empty value
                if phone_value and str(phone_value).strip():
                    is_valid, result = self._validate_hk_phone_number(str(phone_value))
                    if not is_valid:
                        parsed_response["fulfillment_text"] = result
                        parsed_response["confidence"] = 0.0
                    else:
                        # Store the formatted phone number back
                        parsed_response["parameters"]["phone"] = result
                else:
                    # No phone number provided
                    parsed_response["fulfillment_text"] = "I didn't catch your phone number. Please provide your Hong Kong phone number."
                    parsed_response["confidence"] = 0.0

            return parsed_response
        except Exception as e:
            print(f"[DialogflowClient] API Error: {e}")
            raise
    
    def _parse_response(self, response):
        """Parse Dialogflow API response."""
        intent_name = response.query_result.intent.display_name if response.query_result.intent.display_name else "unknown"
        confidence = response.query_result.intent_detection_confidence
        
        # Extract parameters
        parameters = {}
        for key, value in response.query_result.parameters.items():
            parameters[key] = value
        
        fulfillment_text = response.query_result.fulfillment_text
        
        return {
            "intent": intent_name,
            "confidence": confidence,
            "parameters": parameters,
            "fulfillment_text": fulfillment_text
        }
