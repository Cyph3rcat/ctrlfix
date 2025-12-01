"""
CTRLFIX CHATBOT REFACTOR - IMPLEMENTATION PLAN
===============================================

This document outlines the complete refactor based on user requirements.

# NEW FLOW ARCHITECTURE:

Step 0: WELCOME

- Display welcome message with ticket ID
- Transition to PHONE_NUMBER

Step 1: PHONE_NUMBER

- Use Dialogflow API to extract phone number from messy input
  Example: "yes my phone number is 93042802" → Extract 93042802
- Validate with flexible regex (handles all formats)
- Move to DEVICE_TYPE

Step 2: DEVICE_TYPE (Gemini + Entity Fulfillment Loop)

- Prompt: "What type of device needs repair? (laptop, phone, tablet, etc.)"
- Allow interrupts (Dialogflow for common questions)
- Call Gemini to extract device_type from open-ended answer
- Gemini returns JSON: {"device_type": "phone", "fulfilled": true/false, "clarification": "optional prompt if needed"}
- If fulfilled=false, prompt user again with clarification
- Loop until fulfilled=true
- Move to DEVICE_BRAND_MODEL

Step 3: DEVICE_BRAND_MODEL (Gemini + Entity Fulfillment Loop)

- Prompt: "What is the brand and model?"
- Allow interrupts
- Call Gemini to understand brand/model from user input
- Gemini returns JSON: {"brand": "Samsung", "model": "Galaxy Tab A8", "fulfilled": true/false, "clarification": ""}
- Loop until fulfilled=true
- Move to ISSUE_TYPE

Step 4: ISSUE_TYPE (Arrow Key Menu)

- Display menu with arrow key navigation:
  > Software (apps, OS, performance, viruses)
  > Hardware (screen, battery, ports, physical damage)
  > Unsure
- User navigates with ↑/↓, selects with Enter
- No Dialogflow/Gemini calls
- Move to PROBLEM_DESCRIPTION

Step 5: PROBLEM_DESCRIPTION (Literal Form Input)

- Prompt: "Please describe your problem in detail. This will be added directly to your ticket."
- NO INTERRUPTS - this is form filling
- Take input literally, store as-is
- Move to DIAGNOSTIC_OPTIN

Step 6: DIAGNOSTIC_OPTIN (Dialogflow yes/no OR Gemini)

- Prompt: "Would you like a quick diagnostic session to troubleshoot?"
- Dialogflow detects yes/no intent OR allow Gemini interrupt
- If yes → DIAGNOSTIC_MODE
- If no → Skip to COST_ESTIMATION (but still call Gemini to detect parts)

Step 7: DIAGNOSTIC_MODE (Open Gemini Dialogue)

- ONLY if user opted in at step 6
- Open back-and-forth conversation with Gemini
- Gemini analyzes device_type, brand, model, issue_type, description
- Provides debugging steps
- Gemini returns JSON: {"response": "Try restarting...", "skip": true/false, "parts_needed": ["LCD panel", "battery"]}
- If skip=true OR user says to skip → Move to COST_ESTIMATION
- Print debug: "[Gemini] Added 'Tab A8 LCD panel' to parts search"
- Continue dialogue until user is ready
- Move to COST_ESTIMATION

Step 7b: PARTS DETECTION (If user skipped diagnostic)

- Still call Gemini once to analyze and detect parts_needed
- Don't show diagnostic dialogue, just extract parts silently
- Print debug: "[Gemini] Detected parts: ['LCD panel']"

Step 8: COST_ESTIMATION (Taobao API Integration)

- Display breakdown:

  ```
  💰 COST ESTIMATION
  ━━━━━━━━━━━━━━━━━━
  Service Fee: HKD 100.00

  Parts (Live Taobao API):
  - Tab A8 LCD Panel: HKD 300.00
  ━━━━━━━━━━━━━━━━━━
  Total (Indicative): HKD 400.00

  *Note: This price is not final. The mechanic will contact you
  with the final receipt and WILL contact you before any repairs
  or purchasing parts to ensure you agree with the final price.
  ```

- Move to FINAL_BOOKING

Step 9: FINAL_BOOKING (Arrow Key Menu)

- Display menu:
  > Instant drop-off service (faster if you're sure)
  > Contact mechanic first for consultation
- User selects with arrow keys
- Store choice
- Move to GOODBYE

Step 10: GOODBYE

- Display drop-off address and mechanic contact
- Save ticket to Google Sheets
- End session

# TECHNICAL IMPLEMENTATION DETAILS:

1. MENU SYSTEM (menu_utils.py)
   ✅ COMPLETED

   - show_menu(title, options) → returns selected index
   - show_yes_no_menu(question) → returns True/False
   - Uses termios for raw input, arrow key detection

2. CONFIG.PY UPDATES
   ✅ COMPLETED

   - Updated DiagnosticStep enum (0-10)
   - Added BASE_SERVICE_FEE = 100.0
   - Added ISSUE_TYPE_OPTIONS and ISSUE_TYPE_MAPPING for menus
   - Added BOOKING_OPTIONS and BOOKING_MAPPING for menus
   - Removed old SOFTWARE_DIAGNOSTIC_TIPS, HARDWARE_CHECKLIST

3. GEMINI CLIENT UPDATES (gemini_client.py)
   TODO: Add new methods:

   a) extract_device_type(user_input, context) → JSON
   Returns: {"device_type": str, "fulfilled": bool, "clarification": str}

   b) extract_brand_model(user_input, context) → JSON
   Returns: {"brand": str, "model": str, "fulfilled": bool, "clarification": str}

   c) diagnostic_session(device_info, issue_info, description, conversation_history) → JSON
   Returns: {"response": str, "skip": bool, "parts_needed": [str]}

   d) detect_parts_only(device_info, issue_info, description) → JSON
   Returns: {"parts_needed": [str]}

4. DIALOGFLOW CLIENT UPDATES
   ✅ Already handles phone number extraction
   ✅ Already handles interrupts

   - No major changes needed

5. FLOW_MANAGER.PY REFACTOR
   TODO: Complete rewrite of:

   - \_step_device_type() - Gemini fulfillment loop
   - \_process_device_type() - Check fulfilled, loop if needed
   - \_step_device_brand_model() - Gemini fulfillment loop
   - \_process_device_brand_model() - Check fulfilled, loop if needed
   - \_step_issue_type() - Call show_menu()
   - \_process_issue_type() - Direct selection, no validation needed
   - \_step_problem_description() - Form mode, no interrupts
   - \_process_problem_description() - Literal storage
   - \_step_diagnostic_optin() - Dialogflow yes/no
   - \_process_diagnostic_optin() - Branch to diagnostic or skip
   - \_step_diagnostic_mode() - Open Gemini dialogue
   - \_process_diagnostic_mode() - Check skip flag, extract parts
   - \_step_cost_estimation() - Call Taobao API for each part
   - \_step_final_booking() - Call show_menu()
   - \_process_final_booking() - Store choice

   - Update process_input() logic:
     - Skip Dialogflow for literal input steps (4, 5, 9)
     - Allow interrupts for steps 2, 3, 6
     - Disable interrupts for step 5
     - Handle Gemini fulfillment loops

6. TAOBAO API INTEGRATION (scraper_placeholder.py)
   TODO: Implement real Taobao search
   - search_part(device_type, brand, model, part_name) → price (HKD)
   - Return average price from top 3 listings

# GEMINI JSON FORMATS:

Device Type Extraction:
{
"device_type": "tablet",
"fulfilled": true,
"clarification": ""
}

Brand/Model Extraction:
{
"brand": "Samsung",
"model": "Galaxy Tab A8",
"fulfilled": true,
"clarification": ""
}

Diagnostic Session:
{
"response": "Based on your description, this sounds like a malware issue. Try...",
"skip": false,
"parts_needed": []
}

Parts Detection (Silent):
{
"parts_needed": ["LCD panel", "battery"]
}

# NEXT STEPS:

1. Update Gemini prompts with new JSON formats
2. Refactor flow_manager.py step by step
3. Integrate menu_utils into flow
4. Test each step individually
5. Implement Taobao API integration

"""
