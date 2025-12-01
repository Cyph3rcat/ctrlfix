"""Flow manager for ctrlfixDiagnostics
Orchestrates the diagnostic flow, handles interrupts, and manages state transitions.
"""
from dorm_doctor.session import Session
from dorm_doctor.config import (
    DiagnosticStep,
    ISSUE_TYPE_OPTIONS,
    ISSUE_TYPE_MAPPING,
    BOOKING_OPTIONS,
    BOOKING_MAPPING,
    BASE_SERVICE_FEE,
    DROPOFF_ADDRESS,
    MECHANIC_CONTACT,
    CURRENCY,
    INTERRUPT_INTENTS,
    Colors
)
from dorm_doctor.dialogflow_client import DialogflowClient
from dorm_doctor.gemini_client import GeminiClient
from dorm_doctor.scraper_placeholder import PriceLookupClient
from dorm_doctor.sheets_placeholder import GoogleSheetsClient
from dorm_doctor.utils import validate_phone_number, format_phone_number, save_ticket_local
from dorm_doctor.menu_utils import show_menu, show_yes_no_menu
from dorm_doctor.color_utils import print_success, print_diagnostic, format_currency


class FlowManager:
    """Manages the diagnostic flow and handles user interactions."""
    
    def __init__(self):
        self.session = Session()
        self.dialogflow = DialogflowClient()
        self.gemini = GeminiClient()
        self.price_lookup = PriceLookupClient()
        self.sheets = GoogleSheetsClient()
        
    def start(self):
        """Start the diagnostic flow."""
        self.session.set_step(DiagnosticStep.WELCOME)
        return self._step_welcome()
    
    def process_input(self, user_input):
        """Process user input and determine next action.
        
        This is the main entry point for handling user messages.
        It decides whether to:
        1. Use Dialogflow for expected inputs
        2. Use Gemini for free-form/interrupt handling
        3. Proceed to next step in the flow
        
        Args:
            user_input: Raw user input text
            
        Returns:
            dict: Response with keys:
                - message: Text to display to user
                - completed: Whether the flow is complete
                - needs_input: Whether bot is waiting for user input
        """
        self.session.add_message("user", user_input)
        
        current_step = self.session.get_step()
        
        # SKIP NLP ENTIRELY for these literal input steps - process directly
        # USER_NAME, ISSUE_TYPE and FINAL_BOOKING use literal/menu input (handled in CLI)
        # PROBLEM_DESCRIPTION is literal form input (no interrupts allowed)
        if current_step in [DiagnosticStep.USER_NAME, DiagnosticStep.ISSUE_TYPE, DiagnosticStep.PROBLEM_DESCRIPTION, DiagnosticStep.FINAL_BOOKING]:
            return self._process_step_input(current_step, user_input, {"intent": "literal_input", "confidence": 1.0})
        
        # Handle empty input or "continue" as just moving forward (not an interrupt)
        if not user_input.strip() or user_input.strip().lower() == "continue":
            # If we were at cost estimation, just move to next step
            if current_step == DiagnosticStep.COST_ESTIMATION:
                return self._process_step_input(current_step, user_input, {"intent": "continue", "confidence": 1.0})
            # Otherwise treat as potential issue
        
        # Try Dialogflow ONLY for phone number extraction and interrupts
        # For DEVICE_TYPE and DEVICE_BRAND_MODEL, we'll use Gemini directly
        intent_result = self.dialogflow.detect_intent(
            session_id=self.session.ticket_id,
            text=user_input
        )
        
        # Log Dialogflow detection with color
        print_diagnostic(f"[Dialogflow] Intent: {Colors.YELLOW}{intent_result.get('intent')}{Colors.RESET} | Confidence: {Colors.number(intent_result.get('confidence', 0))}")
        
        # Check if it's a known interrupt intent (user asking questions mid-flow)
        # These intents should be configured in Dialogflow with fulfillment text
        if intent_result["intent"] in INTERRUPT_INTENTS and intent_result["confidence"] > 0.6:
            # Handle interrupt with Dialogflow's fulfillment text, then auto-resume
            response = intent_result["fulfillment_text"]
            self.session.add_message("bot", response)
            
            # Get the current step prompt to resume
            resume_result = self._execute_step(current_step)
            
            return {
                "message": f"{response}\n\n{resume_result['message']}",
                "completed": False,
                "needs_input": True
            }
        
        # Check if Dialogflow detected a valid intent that should be processed normally
        # (don't treat step-appropriate intents as interrupts)
        # If intent is detected (not unknown), trust it and process
        if intent_result["intent"] != "unknown":
            # Check if this is expected for current step OR a valid entity update
            is_expected_intent = self._is_expected_intent_for_step(intent_result["intent"], current_step)
            
            if is_expected_intent:
                # For phone_number intent specifically, handle it directly without going to Gemini
                # This handles both WELCOME step (which asks for phone) and PHONE_NUMBER step
                if intent_result["intent"] == "phone_number" and current_step in [DiagnosticStep.WELCOME, DiagnosticStep.PHONE_NUMBER]:
                    phone_from_intent = intent_result["parameters"].get("phone", "")
                    # Check if phone was provided and validation passed (confidence > 0)
                    if phone_from_intent and intent_result["confidence"] > 0.0:
                        self.session.update_data("phone_number", phone_from_intent)
                        print_success(f"Updated phone: {Colors.number(phone_from_intent)}")
                        print_diagnostic("[FlowManager] Moving to next step: USER_NAME")
                        # Move from WELCOME to PHONE_NUMBER, then to USER_NAME
                        if current_step == DiagnosticStep.WELCOME:
                            self.session.set_step(DiagnosticStep.PHONE_NUMBER)
                        self.session.next_step()
                        result = self._step_user_name()
                        self.session.add_message("bot", result["message"])
                        return result
                    else:
                        # Validation failed (confidence = 0) or no phone provided
                        message = intent_result.get("fulfillment_text") or "That doesn't look like a valid Hong Kong phone number. Please use the format: +852 XXXX XXXX"
                        self.session.add_message("bot", message)
                        return {"message": message, "completed": False, "needs_input": True}
                else:
                    # Process normally for current step
                    return self._process_step_input(current_step, user_input, intent_result)
            
            # Check if this is a valid entity update (only if NOT expected for current step)
            is_entity_update = self._handle_entity_update(intent_result, current_step)
            if is_entity_update:
                # Entity was updated, continue with current step
                resume_result = self._execute_step(current_step)
                return {
                    "message": f"Got it, I've updated that information.\n\n{resume_result['message']}",
                    "completed": False,
                    "needs_input": True
                }
            
            # If we got here with good confidence but it wasn't expected and not an entity update,
            # it might be an edge case - just process normally
            return self._process_step_input(current_step, user_input, intent_result)
        
        # If Dialogflow returned unknown intent, use Gemini for conversational fallback
        # BUT: don't interrupt on empty inputs OR if we already processed the input successfully above
        if intent_result["intent"] == "unknown" and user_input.strip():
            print(f"[FlowManager] Unknown intent - calling Gemini for fallback")
            
            # SPECIAL CASE: If we're in DEVICE_BRAND_MODEL step, try to extract device info first
            if current_step == DiagnosticStep.DEVICE_BRAND_MODEL:
                print(f"[FlowManager] Attempting extract_brandmodel for device info extraction")
                device_type = self.session.get_data("device.type") or "unknown"
                result = self.gemini.extract_brandmodel(user_input, self.session.conversation_history, device_type)
                
                print_diagnostic(f"[Gemini] Brand/model extraction: {Colors.CYAN}{result}{Colors.RESET}")
                
                if result["fulfilled"]:
                    # Entity fulfilled - store and move on
                    brandmodel = result["brandmodel"]
                    self.session.update_data("device.brandmodel", brandmodel)
                    print_success(f"Device: {Colors.CYAN}{brandmodel}{Colors.RESET}")
                    
                    # Provide confirmation message ONLY (no follow-up question)
                    confirmation = f"Okay, your device seems to be a {brandmodel}."
                    print(f"[Bot Response] {confirmation}")
                    self.session.add_message("bot", confirmation)
                    
                    print(f"[FlowManager] Device updated, auto-progressing to next step")
                    self.session.next_step()
                    next_result = self._step_additional_info()
                    self.session.add_message("bot", next_result["message"])
                    
                    return {
                        "message": f"{confirmation}\n\n{next_result['message']}",
                        "completed": False,
                        "needs_input": True
                    }
                else:
                    # Not fulfilled - could be unclear device info OR completely irrelevant input
                    # Both cases: show the clarification (which includes joke if irrelevant)
                    # and stay in the same step for user to try again
                    clarification = result["clarification"]
                    self.session.add_message("bot", clarification)
                    return {"message": clarification, "completed": False, "needs_input": True}
            
            # SPECIAL CASE: If we're in ADDITIONAL_INFO step, extract additional device info
            if current_step == DiagnosticStep.ADDITIONAL_INFO:
                print(f"[FlowManager] Attempting extract_additional_info for additional device specs")
                result = self.gemini.extract_additional_info(
                    user_input=user_input,
                    conversation_history=self.session.conversation_history,
                    device_type=self.session.get_data("device.type"),
                    brandmodel=self.session.get_data("device.brandmodel")
                )
                
                print_diagnostic(f"[Gemini] Additional info extraction: {Colors.CYAN}{result}{Colors.RESET}")
                
                if result.get("relevant"):
                    # User provided relevant device info
                    additional_info = result["additional_info"]
                    self.session.update_data("device.additional_info", additional_info)
                    print_success(f"Additional info: {Colors.LIGHT_BLUE}{additional_info}{Colors.RESET}")
                    
                    confirmation = f"Got it! I've noted: {additional_info}"
                    self.session.add_message("bot", confirmation)
                    
                    # Move to next step
                    self.session.next_step()
                    next_result = self._step_issue_type()
                    self.session.add_message("bot", next_result["message"])
                    
                    return {
                        "message": f"{confirmation}\n\n{next_result['message']}",
                        "completed": False,
                        "needs_input": True
                    }
                else:
                    # User said something irrelevant - friendly joke response
                    joke_response = result.get("joke_response", "Please provide device information or type 'no' to skip.")
                    self.session.add_message("bot", joke_response)
                    
                    # Re-prompt for the step
                    reprompt = self._step_additional_info()
                    
                    return {
                        "message": f"{joke_response}\n\n{reprompt['message']}",
                        "completed": False,
                        "needs_input": True
                    }
            
            # For other steps OR if device extraction suggested it's an interrupt, use generic interrupt handler
            self.session.mark_interrupted()
            gemini_response = self.gemini.generate_response(
                user_input=user_input,
                conversation_history=self.session.conversation_history,
                current_step_context=self._get_step_name(current_step)
            )
            
            # Handle Gemini's response (could be string or dict)
            if isinstance(gemini_response, dict):
                response_text = gemini_response["message"]
                entities = gemini_response.get("entities_detected", {})
                
                # Debug: Print full Gemini response for diagnostics
                print(f"[Gemini] Full response: {gemini_response}")
                
                # Process any entities Gemini detected
                entity_updates = []
                for entity_type, entity_value in entities.items():
                    if entity_type == "phone":
                        # Validate Hong Kong phone number
                        from dorm_doctor.utils import validate_phone_number, format_phone_number
                        if validate_phone_number(entity_value):
                            formatted = format_phone_number(entity_value)
                            self.session.update_data("phone_number", formatted)
                            entity_updates.append(f"Updated phone: {formatted}")
                    elif entity_type == "issue_description":
                        self.session.update_data("description", entity_value)
                        entity_updates.append(f"Updated issue description")
                
                # Check confidence scores for feedback
                confidence_scores = gemini_response.get("confidence_scores", {})
                low_confidence = [k for k, v in confidence_scores.items() if 0.3 < v < 0.7]
                if low_confidence:
                    response_text += f"\n\n(I'm not completely sure about: {', '.join(low_confidence)})"
                
                # Add entity update notifications only if we made updates
                if entity_updates:
                    response_text += f"\n\n✓ {' | '.join(entity_updates)}"
            else:
                # Backward compatibility - Gemini returned just a string
                response_text = gemini_response
            
            self.session.add_message("bot", response_text)
            
            # After handling interrupt, resume the current step automatically
            resume_result = self._execute_step(current_step)
            return {
                "message": f"{response_text}\n\n{resume_result['message']}",
                "completed": False,
                "needs_input": True
            }
        
        # If we were interrupted and user confirms to continue
        if self.session.is_interrupted():
            if intent_result["intent"] == "affirmative":
                self.session.clear_interrupt()
                # Resume from current step - show the prompt again
                result = self._execute_step(current_step)
                self.session.add_message("bot", result["message"])
                return result
            elif intent_result["intent"] == "negative":
                self.session.clear_interrupt()
                response = "No problem! Feel free to ask more questions, or let me know when you're ready."
                self.session.add_message("bot", response)
                return {
                    "message": response,
                    "completed": False,
                    "needs_input": True
                }
            # If interrupted but didn't get affirmative/negative, treat as another question
            # Fall through to process as interrupt again
        
        # Process input based on current step
        return self._process_step_input(current_step, user_input, intent_result)
    
    def _process_step_input(self, step, user_input, intent_result):
        """Process user input for a specific diagnostic step."""
        
        if step == DiagnosticStep.WELCOME:
            # Welcome already asks for phone number, process it directly
            return self._process_phone_number(user_input)
        
        elif step == DiagnosticStep.PHONE_NUMBER:
            return self._process_phone_number(user_input)
        
        elif step == DiagnosticStep.USER_NAME:
            return self._process_user_name(user_input, intent_result)
        
        elif step == DiagnosticStep.DEVICE_TYPE:
            return self._process_device_type(user_input, intent_result)
        
        elif step == DiagnosticStep.DEVICE_BRAND_MODEL:
            return self._process_device_brand_model(user_input, intent_result)
        
        elif step == DiagnosticStep.ADDITIONAL_INFO:
            return self._process_additional_info(user_input, intent_result)
        
        elif step == DiagnosticStep.ISSUE_TYPE:
            # This should never be called - issue type uses menu in CLI
            return self._process_issue_type(user_input, intent_result)
        
        elif step == DiagnosticStep.PROBLEM_DESCRIPTION:
            return self._process_problem_description(user_input, intent_result)
        
        elif step == DiagnosticStep.DIAGNOSTIC_OPTIN:
            return self._process_diagnostic_optin(user_input, intent_result)
        
        elif step == DiagnosticStep.DIAGNOSTIC_MODE:
            return self._process_diagnostic_mode(user_input, intent_result)
        
        elif step == DiagnosticStep.COST_ESTIMATION:
            # Cost is automatically shown, just need confirmation to continue
            self.session.next_step()
            return self._step_final_booking()
        
        elif step == DiagnosticStep.FINAL_BOOKING:
            # This should never be called - final booking uses menu in CLI
            return self._process_final_booking(user_input, intent_result)
        
        elif step == DiagnosticStep.GOODBYE:
            return self._step_goodbye()
        
        # Fallback
        return {
            "message": "Sorry, I'm not sure what to do here. Let's continue.",
            "completed": False,
            "needs_input": True
        }
    
    def _execute_step(self, step):
        """Execute a specific step without user input (for resuming after interrupt)."""
        step_methods = {
            DiagnosticStep.WELCOME: self._step_welcome,
            DiagnosticStep.PHONE_NUMBER: self._step_phone_number,
            DiagnosticStep.USER_NAME: self._step_user_name,
            DiagnosticStep.DEVICE_TYPE: self._step_device_type,
            DiagnosticStep.DEVICE_BRAND_MODEL: self._step_device_brand_model,
            DiagnosticStep.ADDITIONAL_INFO: self._step_additional_info,
            DiagnosticStep.ISSUE_TYPE: self._step_issue_type,
            DiagnosticStep.PROBLEM_DESCRIPTION: self._step_problem_description,
            DiagnosticStep.DIAGNOSTIC_OPTIN: self._step_diagnostic_optin,
            DiagnosticStep.DIAGNOSTIC_MODE: self._step_diagnostic_mode,
            DiagnosticStep.COST_ESTIMATION: self._step_cost_estimation,
            DiagnosticStep.FINAL_BOOKING: self._step_final_booking,
            DiagnosticStep.GOODBYE: self._step_goodbye,
        }
        method = step_methods.get(step)
        if method:
            return method()
        return {"message": "Continuing...", "completed": False, "needs_input": True}
    
    # Step 0: Welcome
    def _step_welcome(self):
        message = (
            "Hello! I'm CtrlFixDiagnostics 🔧\n\n"
            "I'm a chatbot designed by CtrlFix to help with:\n"
            "- Quick diagnostics and problem identification\n"
            "- Cost estimation for repairs\n"
            "- Booking appointments and arranging drop-offs\n\n"
            f"Your ticket ID is: {self.session.ticket_id}\n\n"
            "I will understand your intentions, and guide you through booking. Feel free to interrupt me at any moment with any related questions.\n\n"
            "To get started, let's get your phone number.\n"
            "Please enter your Hong Kong phone number in the format: +852 XXXX XXXX"
        )
        self.session.add_message("bot", message)
        return {"message": message, "completed": False, "needs_input": True}
    
    # Step 1: Phone number
    def _step_phone_number(self):
        message = (
            "First, I need your phone number for contact purposes.\n"
            "Please enter your Hong Kong phone number in the format: +852 XXXX XXXX"
        )
        self.session.add_message("bot", message)
        return {"message": message, "completed": False, "needs_input": True}
    
    def _process_phone_number(self, user_input):
        # Note: Dialogflow intent detection is already done in process_input()
        # This method is only called if Dialogflow detected phone_number intent
        # OR if we need manual validation
        
        # At this point, if we reached here via normal flow, Dialogflow already validated
        # the phone number in process_input(). Let's extract it from the session or validate manually.
        
        # Try manual validation first
        if validate_phone_number(user_input):
            formatted = format_phone_number(user_input)
            self.session.update_data("phone_number", formatted)
            
            print(f"✓ Updated phone: {formatted}")
            
            self.session.next_step()
            return self._step_user_name()
        else:
            message = (
                "That doesn't look like a valid Hong Kong phone number.\n"
                "Please use the format: +852 XXXX XXXX (e.g., +852 1234 5678)"
            )
            self.session.add_message("bot", message)
            return {"message": message, "completed": False, "needs_input": True}
    
    # Step 2: User name (Literal input - no NLP)
    def _step_user_name(self):
        message = (
            "Thanks! Now, what's your name?\n"
            "Please provide your first and last name:"
        )
        self.session.add_message("bot", message)
        return {"message": message, "completed": False, "needs_input": True}
    
    def _process_user_name(self, user_input, intent_result=None):
        # Store literally - no NLP, no processing
        # User can provide any name, even ridiculous ones (they might be legit)
        user_name = user_input.strip()
        
        if len(user_name) < 2:
            message = "Please provide your name (at least 2 characters)."
            self.session.add_message("bot", message)
            return {"message": message, "completed": False, "needs_input": True}
        
        self.session.update_data("user_name", user_name)
        print_success(f"User name: {Colors.LIGHT_BLUE}{user_name}{Colors.RESET}")
        
        self.session.next_step()
        return self._step_device_type()
    
    # Step 3: Device type (Dialogflow entity extraction)
    def _step_device_type(self):
        message = (
            "Great! What type of device needs repair?\n\n"
            "Options: laptop, phone, tablet, others\n\n"
            "Please choose the category closest to your device type."
        )
        self.session.add_message("bot", message)
        return {"message": message, "completed": False, "needs_input": True}
    
    def _process_device_type(self, user_input, intent_result=None):
        # Use Dialogflow to extract device type via @device-type entity
        if intent_result and intent_result.get("intent") == "devicetype":
            # Extract device-type entity from Dialogflow
            device_type = intent_result.get("parameters", {}).get("device-type", "").lower()
            
            if device_type:
                # Normalize device type
                if device_type in ["laptop", "phone", "tablet", "others"]:
                    self.session.update_data("device.type", device_type)
                    print(f"✓ Device type: {device_type}")
                    
                    self.session.next_step()
                    return self._step_device_brand_model()
                else:
                    # Device type not in expected categories, treat as "others"
                    self.session.update_data("device.type", "others")
                    print(f"✓ Device type: others (from '{device_type}')")
                    
                    self.session.next_step()
                    return self._step_device_brand_model()
        
        # Fallback: Dialogflow didn't detect devicetype intent
        message = (
            "I didn't quite catch that. Please tell me your device type:\n\n"
            "Options: laptop, phone, tablet, others"
        )
        self.session.add_message("bot", message)
        return {"message": message, "completed": False, "needs_input": True}
    
    # Step 4: Device brand/model (Gemini + entity fulfillment loop)
    def _step_device_brand_model(self):
        message = (
            "Perfect! Now please tell me the brand and model.\n\n"
            "Examples:\n"
            "- Samsung Galaxy Tab A8\n"
            "- ASUS ROG Laptop G614J\n"
            "- iPhone 13 Pro\n\n"
            "Just type it as you know it:"
        )
        self.session.add_message("bot", message)
        return {"message": message, "completed": False, "needs_input": True}
    
    def _process_device_brand_model(self, user_input, intent_result=None):
        # Use Gemini to understand brand/model with fulfillment check
        device_type = self.session.get_data("device.type") or "unknown"
        result = self.gemini.extract_brandmodel(user_input, self.session.conversation_history, device_type)
        
        print(f"[Gemini] Brand/model extraction: {result}")
        
        if result["fulfilled"]:
            # Entity fulfilled - store and move on
            brandmodel = result["brandmodel"]
            self.session.update_data("device.brandmodel", brandmodel)
            print(f"✓ Device: {brandmodel}")
            
            # Provide confirmation message
            confirmation = f"Okay, your device seems to be a {brandmodel}."
            self.session.add_message("bot", confirmation)
            
            self.session.next_step()
            next_result = self._step_additional_info()
            
            return {
                "message": f"{confirmation}\n\n{next_result['message']}",
                "completed": False,
                "needs_input": True
            }
        else:
            # Not fulfilled - ask for clarification
            message = result["clarification"]
            self.session.add_message("bot", message)
            # Stay in same step (loop until fulfilled)
            return {"message": message, "completed": False, "needs_input": True}
    
    # Step 4: Additional info (Optional device specs)
    def _step_additional_info(self):
        message = (
            "Do you have any additional information about your device?\n\n"
            "For example:\n"
            "- RAM (e.g., 16GB)\n"
            "- Storage (e.g., 512GB SSD)\n"
            "- Purchase year (e.g., bought in 2020)\n"
            "- Any other relevant details\n\n"
            "Type your info, or type 'no' to skip:"
        )
        self.session.add_message("bot", message)
        return {"message": message, "completed": False, "needs_input": True}
    
    def _process_additional_info(self, user_input, intent_result=None):
        # Check if user wants to skip (Dialogflow negative intent OR explicit skip words)
        if intent_result and intent_result.get("intent") == "negative":
            print("[FlowManager] User declined additional info (Dialogflow negative)")
            self.session.next_step()
            return self._step_issue_type()
        
        user_lower = user_input.strip().lower()
        
        if user_lower in ["no", "skip", "none", "nope", "n", "nah", "na", "naw"]:
            # User skipped - move to next step
            print("[FlowManager] User skipped additional info")
            self.session.next_step()
            return self._step_issue_type()
        
        # Use Gemini to extract additional info and check relevance
        result = self.gemini.extract_additional_info(
            user_input=user_input,
            conversation_history=self.session.conversation_history,
            device_type=self.session.get_data("device.type"),
            brandmodel=self.session.get_data("device.brandmodel")
        )
        
        print(f"[Gemini] Additional info extraction: {result}")
        
        if result.get("relevant"):
            # User provided relevant device info
            additional_info = result["additional_info"]
            self.session.update_data("device.additional_info", additional_info)
            print_success(f"Additional info: {Colors.LIGHT_BLUE}{additional_info}{Colors.RESET}")
            
            confirmation = f"Got it! I've noted: {additional_info}"
            self.session.add_message("bot", confirmation)
            
            # Move to next step
            self.session.next_step()
            next_result = self._step_issue_type()
            
            return {
                "message": f"{confirmation}\n\n{next_result['message']}",
                "completed": False,
                "needs_input": True
            }
        else:
            # User said something irrelevant - friendly joke response
            joke_response = result.get("joke_response", "Please provide device information or type 'no' to skip.")
            self.session.add_message("bot", joke_response)
            
            # Re-prompt for the step
            reprompt = self._step_additional_info()
            
            return {
                "message": f"{joke_response}\n\n{reprompt['message']}",
                "completed": False,
                "needs_input": True
            }
    
    # Step 5: Issue type (Menu selection)
    def _step_issue_type(self):
        message = (
            "What type of issue are you experiencing?\n\n"
            "1. Software (apps, OS, performance, viruses)\n"
            "2. Hardware (screen, battery, ports, physical damage)\n"
            "3. Unsure\n\n"
            "Type 1, 2, or 3 (or 's', 'h', 'u'):"
        )
        self.session.add_message("bot", message)
        return {"message": message, "completed": False, "needs_input": True}
    
    def _process_issue_type(self, user_input, intent_result):
        # Accept multiple input formats: numbers (1-3), letters (s/h/u), or full text
        user_input = user_input.strip().lower()
        issue_type = None
        
        try:
            # Try to parse as number (1-3)
            choice_idx = int(user_input)
            issue_type = ISSUE_TYPE_MAPPING.get(choice_idx)
        except ValueError:
            # Try letter shortcuts or text matching
            if user_input in ['s', '1']:
                issue_type = "software"
            elif user_input in ['h', '2']:
                issue_type = "hardware"
            elif user_input in ['u', '3']:
                issue_type = "unsure"
            elif "software" in user_input:
                issue_type = "software"
            elif "hardware" in user_input:
                issue_type = "hardware"
            else:
                issue_type = "unsure"
        
        if issue_type:
            self.session.update_data("issue_type", issue_type)
            print_success(f"Issue type: {Colors.CYAN}{issue_type}{Colors.RESET}")
            self.session.next_step()
            return self._step_problem_description()
        else:
            message = "Please select an option from the menu."
            self.session.add_message("bot", message)
            return {"message": message, "completed": False, "needs_input": True}
    
    # Step 5: Problem description (Literal form input - NO INTERRUPTS)
    def _step_problem_description(self):
        message = (
            "Please describe your problem in as much detail as possible.\n\n"
            "⚠️  NOTE: What you type here will be added DIRECTLY to your ticket for the mechanic to read.\n"
            "No interrupts are allowed at this step - this is form filling.\n\n"
            "Include:\n"
            "- When did it start?\n"
            "- What were you doing when it happened?\n"
            "- Any error messages?\n"
            "- Recent changes (updates, drops, water exposure)?\n\n"
            "Type your description:"
        )
        self.session.add_message("bot", message)
        return {"message": message, "completed": False, "needs_input": True}
    
    def _process_problem_description(self, user_input, intent_result=None):
        # Store literally - no NLP, no processing
        description = user_input.strip()
        self.session.update_data("description", description)
        
        print_success(f"Description saved ({Colors.number(len(description))} chars)")
        
        self.session.next_step()
        return self._step_diagnostic_optin()
    
    # Step 6: Diagnostic opt-in (Dialogflow yes/no OR Gemini interrupt)
    def _step_diagnostic_optin(self):
        message = (
            "Would you like a quick diagnostic session to troubleshoot the issue?\n\n"
            "This can help identify the problem and potential solutions.\n\n"
            "Type 'yes' or 'no':"
        )
        self.session.add_message("bot", message)
        return {"message": message, "completed": False, "needs_input": True}
    
    def _process_diagnostic_optin(self, user_input, intent_result):
        # Check Dialogflow for yes/no intent
        wants_diagnostic = False
        
        if intent_result["intent"] == "affirmative":
            wants_diagnostic = True
        elif intent_result["intent"] == "negative":
            wants_diagnostic = False
        else:
            # Fallback to keyword detection
            user_lower = user_input.lower()
            wants_diagnostic = any(word in user_lower for word in ["yes", "sure", "ok", "okay", "yeah"])
        
        if wants_diagnostic:
            self.session.update_data("diagnostic_opted_in", True)
            self.session.next_step()
            return self._step_diagnostic_mode()
        else:
            self.session.update_data("diagnostic_opted_in", False)
            # Skip diagnostic mode, but still detect parts
            print("[Gemini] User skipped diagnostic, detecting parts silently...")
            parts_result = self.gemini.detect_parts_only(
                device_type=self.session.get_data("device.type"),
                brandmodel=self.session.get_data("device.brandmodel"),
                issue_type=self.session.get_data("issue_type"),
                description=self.session.get_data("description")
            )
            parts = parts_result.get("parts_needed", [])
            self.session.update_data("parts_needed", parts)
            for part in parts:
                print(f"[Gemini] Detected part: {part}")
            
            # Skip to cost estimation
            self.session.set_step(DiagnosticStep.COST_ESTIMATION)
            return self._step_cost_estimation()
    
    # Step 8: Diagnostic mode (Open Gemini dialogue)
    def _step_diagnostic_mode(self):
        # Initialize diagnostic session
        device_type = self.session.get_data("device.type")
        brandmodel = self.session.get_data("device.brandmodel")
        issue_type = self.session.get_data("issue_type")
        description = self.session.get_data("description")
        
        message = (
            f"🔧 DIAGNOSTIC SESSION STARTED\n\n"
            f"Device: {brandmodel} ({device_type})\n"
            f"Issue: {issue_type}\n\n"
            "I'll help you troubleshoot. Let's start:\n"
            "Based on your description, let me analyze the issue..."
        )
        
        # Make initial diagnostic call
        result = self.gemini.diagnostic_session(
            device_type=device_type,
            brandmodel=brandmodel,
            issue_type=issue_type,
            description=description,
            user_input="Start diagnostic",
            conversation_history=self.session.conversation_history
        )
        
        response = result["response"]
        parts = result.get("parts_needed", [])
        
        # Store parts
        if parts:
            existing_parts = self.session.get_data("parts_needed") or []
            for part in parts:
                if part not in existing_parts:
                    existing_parts.append(part)
                    print(f"[Gemini] Added '{part}' to parts search")
            self.session.update_data("parts_needed", existing_parts)
        
        full_message = f"{message}\n\n{response}\n\n(Type your response, or say 'skip' to move to cost estimation)"
        self.session.add_message("bot", full_message)
        return {"message": full_message, "completed": False, "needs_input": True}
    
    def _process_diagnostic_mode(self, user_input, intent_result):
        # Continue diagnostic dialogue with Gemini
        result = self.gemini.diagnostic_session(
            device_type=self.session.get_data("device.type"),
            brandmodel=self.session.get_data("device.brandmodel"),
            issue_type=self.session.get_data("issue_type"),
            description=self.session.get_data("description"),
            user_input=user_input,
            conversation_history=self.session.conversation_history
        )
        
        response = result["response"]
        skip = result.get("skip", False)
        parts = result.get("parts_needed", [])
        
        # Update parts list
        if parts:
            existing_parts = self.session.get_data("parts_needed") or []
            for part in parts:
                if part not in existing_parts:
                    existing_parts.append(part)
                    print(f"[Gemini] Added '{part}' to parts search")
            self.session.update_data("parts_needed", existing_parts)
        
        if skip:
            # User wants to skip, move to cost estimation
            message = f"{response}\n\nMoving to cost estimation..."
            self.session.add_message("bot", message)
            self.session.next_step()
            return self._step_cost_estimation()
        else:
            # Continue dialogue
            message = f"{response}\n\n(Continue troubleshooting, or say 'skip' to move to cost estimation)"
            self.session.add_message("bot", message)
            # Stay in same step
            return {"message": message, "completed": False, "needs_input": True}
    
    # Step 9: Cost estimation (Service fee + amazon API)
    def _step_cost_estimation(self):
        # Get parts list
        parts_needed = self.session.get_data("parts_needed") or []
        device_type = self.session.get_data("device.type") or "device"
        brandmodel = self.session.get_data("device.brandmodel") or ""
        
        # Calculate costs
        service_fee = BASE_SERVICE_FEE
        parts_total = 0.0
        parts_details = []
        
        print_diagnostic(f"[Cost Estimation] Searching Amazon for {Colors.number(len(parts_needed))} parts...")
        
        for part_name in parts_needed:
            # Call Amazon API
            price = self.price_lookup.get_price(
                device_type=device_type,
                brandmodel=brandmodel,
                part_name=part_name
            )
            parts_total += price
            parts_details.append(f"- {part_name}: {format_currency(price, CURRENCY)}")
            print_diagnostic(f"[Serp(Amazon) API] {part_name}: {format_currency(price, CURRENCY)}")
        
        total = service_fee + parts_total
        
        # Build message with colors
        message = f"\n{Colors.PINK}💰 COST ESTIMATION{Colors.RESET}\n"
        message += Colors.GRAY + "━" * 50 + Colors.RESET + "\n"
        message += f"{Colors.LIGHT_BLUE}Service Fee: {format_currency(service_fee, CURRENCY)}{Colors.RESET}\n\n"
        
        if parts_details:
            message += f"{Colors.CYAN}Parts (Live Serp(Amazon) API):{Colors.RESET}\n"
            for detail in parts_details:
                message += f"{Colors.LIGHT_BLUE}{detail}{Colors.RESET}\n"
            message += "\n"
        
        message += Colors.GRAY + "━" * 50 + Colors.RESET + "\n"
        message += f"{Colors.BOLD}{Colors.WHITE}Total (Indicative): {format_currency(total, CURRENCY)}{Colors.RESET}\n"
        message += Colors.GRAY + "━" * 50 + Colors.RESET + "\n\n"
        message += f"{Colors.YELLOW}⚠️  NOTE:{Colors.RESET} {Colors.LIGHT_BLUE}This price is not final. Our mechanic will contact you\n"
        message += "with the final receipt and WILL contact you before any repairs or\n"
        message += "purchasing parts to ensure you agree with the final price.\n"
        message += f"Do not worry!{Colors.RESET}\n\n"
        message += f"{Colors.GRAY}Press Enter to continue...{Colors.RESET}"
        
        # Store cost
        self.session.update_data("service_fee", service_fee)
        self.session.update_data("parts_cost", parts_total)
        self.session.update_data("estimated_total", total)
        
        self.session.add_message("bot", message)
        return {"message": message, "completed": False, "needs_input": True}
    
    # Step 9: Final booking (Menu selection)
    def _step_final_booking(self):
        message = (
            "Final step! How would you like to proceed?\n\n"
            "1. Instant drop-off service (faster if you're sure about the issue)\n"
            "2. Contact mechanic first for further consultation\n\n"
            "Type 1 or 2:"
        )
        self.session.add_message("bot", message)
        return {"message": message, "completed": False, "needs_input": True}
    
    def _process_final_booking(self, user_input, intent_result):
        # Accept number input (1-2) or keywords
        user_input = user_input.strip().lower()
        booking_type = None
        
        try:
            choice_idx = int(user_input)
            booking_type = BOOKING_MAPPING.get(choice_idx)
        except ValueError:
            # Fallback: try to match text
            if "instant" in user_input or "drop" in user_input:
                booking_type = "instant_dropoff"
            elif "contact" in user_input or "mechanic" in user_input or "consult" in user_input:
                booking_type = "contact_first"
            else:
                # Default to contact first if unclear
                booking_type = None
        
        if booking_type:
            self.session.update_data("booking_type", booking_type)
            print(f"✓ Booking type: {booking_type}")
            
            # Generate and log ticket
            self._finalize_ticket()
            
            # Move to goodbye
            self.session.next_step()
            return self._step_goodbye()
        else:
            message = "Please select an option from the menu."
            self.session.add_message("bot", message)
            return {"message": message, "completed": False, "needs_input": True}
    
    # Step 11: Goodbye
    def _step_goodbye(self):
        device_info = self.session.get_data('device.brandmodel') or 'Unknown'
        device_type = self.session.get_data('device.type') or ''
        additional_info = self.session.get_data('device.additional_info')
        
        device_display = f"{device_info} ({device_type})"
        if additional_info:
            device_display += f" - {additional_info}"
        
        message = (
            f"\n{'='*50}\n"
            f"Thank you for using CtrlFixDiagnostics! 🔧\n"
            f"{'='*50}\n\n"
            f"📋 Your Ticket Summary:\n"
            f"   Ticket ID: {self.session.ticket_id}\n"
            "Please keep your ticket ID in case you need to edit your response and for reference\n"
            f"   Name: {self.session.get_data('user_name')}\n"
            f"   Phone: {self.session.get_data('phone_number')}\n"
            f"   Device: {device_display}\n"
            f"   Issue: {self.session.get_data('issue_type')}\n"
            f"   Estimate: {self.session.get_data('estimated_cost')}\n\n"
            f"📍 Drop-off Location:\n"
            f"   {DROPOFF_ADDRESS}\n\n"
            f"📞 Questions? Contact the mechanic:\n"
            f"   {MECHANIC_CONTACT}\n\n"
            f"Drop-off Instructions:\n"
            f"1. Include charger and relevant accessories\n"
            f"2. Back up your data if possible\n"
            f"3. Label device with your name and ticket ID: {self.session.ticket_id}\n\n"
            f"We'll contact you with updates. Have a great day! 👋\n"
        )
        self.session.add_message("bot", message)
        return {"message": message, "completed": True, "needs_input": False}
    
    def _finalize_ticket(self):
        """Generate final ticket and log to Google Sheets."""
        ticket_data = self.session.get_ticket_data()
        
        # Save locally
        save_ticket_local(ticket_data)
        
        # TODO Phase 2: Upload to Google Sheets
        # sheets.add_ticket() should make actual API call here
        self.sheets.add_ticket(ticket_data)
    
    def _get_step_name(self, step):
        """Get human-readable name for a step (for Gemini context)."""
        step_names = {
            DiagnosticStep.WELCOME: "Welcome/Introduction",
            DiagnosticStep.PHONE_NUMBER: "Collecting phone number",
            DiagnosticStep.USER_NAME: "Collecting user's name",
            DiagnosticStep.DEVICE_TYPE: "Collecting device type",
            DiagnosticStep.DEVICE_BRAND_MODEL: "Collecting device brand and model",
            DiagnosticStep.ADDITIONAL_INFO: "Collecting additional device information",
            DiagnosticStep.ISSUE_TYPE: "Identifying issue type",
            DiagnosticStep.PROBLEM_DESCRIPTION: "Collecting problem description",
            DiagnosticStep.DIAGNOSTIC_OPTIN: "Asking if user wants diagnostic session",
            DiagnosticStep.DIAGNOSTIC_MODE: "Interactive diagnostic dialogue",
            DiagnosticStep.COST_ESTIMATION: "Showing cost estimation",
            DiagnosticStep.FINAL_BOOKING: "Final booking selection",
            DiagnosticStep.GOODBYE: "Farewell",
        }
        return step_names.get(step, "Unknown step")
    
    def _is_expected_intent_for_step(self, intent, current_step):
        """Check if an intent is expected for the current step."""
        expected_intents = {
            DiagnosticStep.WELCOME: ["phone_number"],  # Welcome asks for phone directly
            DiagnosticStep.PHONE_NUMBER: ["phone_number"],
            DiagnosticStep.USER_NAME: ["literal_input"],  # Literal input, no NLP
            DiagnosticStep.DEVICE_TYPE: ["devicetype"],  # Dialogflow @device-type entity
            DiagnosticStep.DEVICE_BRAND_MODEL: ["detailed_text"],  # Gemini handles
            DiagnosticStep.ADDITIONAL_INFO: ["detailed_text"],  # Gemini handles
            DiagnosticStep.ISSUE_TYPE: ["literal_input"],  # Arrow key menu, no NLP
            DiagnosticStep.PROBLEM_DESCRIPTION: ["detailed_text"],  # Literal input, no NLP
            DiagnosticStep.DIAGNOSTIC_OPTIN: ["affirmative", "negative"],  # Yes/no for diagnostic
            DiagnosticStep.DIAGNOSTIC_MODE: ["detailed_text"],  # Open Gemini dialogue
            DiagnosticStep.COST_ESTIMATION: [],  # No user input expected
            DiagnosticStep.FINAL_BOOKING: ["literal_input"],  # Arrow key menu, no NLP
            DiagnosticStep.GOODBYE: [],  # No user input expected
        }
        
        return intent in expected_intents.get(current_step, [])
    
    def _handle_entity_update(self, intent_result, current_step):
        """Handle entity updates that can happen at any time during conversation.
        
        Returns True if an entity was updated, False otherwise.
        This should NOT trigger if the intent is expected for the current step.
        """
        intent = intent_result["intent"]
        
        # Don't treat as entity update if this intent is expected for current step
        if self._is_expected_intent_for_step(intent, current_step):
            return False
        
        # Phone number update (when NOT in phone number step)
        if intent == "phone_number":
            phone = intent_result["parameters"].get("phone", "")
            # Use the same validation as in _process_phone_number
            if intent_result["confidence"] > 0.0:  # Validation passed in Dialogflow
                self.session.update_data("phone_number", phone)
                self.session.add_message("bot", f"Updated phone number to: {phone}")
                return True
        
        # Device type update (when NOT in device type/brand steps)
        elif intent == "device_type":
            device_type_input = intent_result["parameters"].get("device_type", "")
            
            # Extract device type
            device_type_lower = device_type_input.lower()
            device_type = "unknown"
            if any(word in device_type_lower for word in ["laptop", "notebook", "macbook"]):
                device_type = "laptop"
            elif any(word in device_type_lower for word in ["phone", "iphone", "smartphone"]):
                device_type = "phone"
            elif any(word in device_type_lower for word in ["tablet", "ipad"]):
                device_type = "tablet"
            
            self.session.update_data("device.type", device_type)
            self.session.add_message("bot", f"Updated device type to: {device_type}")
            return True
        
        # Issue type update (when NOT in issue type step)
        elif intent == "issue_type":
            issue_type = intent_result["parameters"].get("issue_type")
            if issue_type:
                self.session.update_data("issue_type", issue_type)
                self.session.add_message("bot", f"Updated issue type to: {issue_type}")
                return True
        
        return False
