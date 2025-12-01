"""Gemini API client for conversational fallback
Prioritizes Vertex AI with service account, falls back to API key mode
"""
from dorm_doctor.config import DIALOGFLOW_PROJECT_ID, VERTEX_CREDENTIALS_PATH
import os


class GeminiClient:
    """Gemini API client for handling free-form user input via Google Gen AI SDK."""
    
    def __init__(self):
        self.use_real_api = False
        self.use_vertex = False
        self.project_id = DIALOGFLOW_PROJECT_ID
        self.location = "us-central1"  # Vertex AI region
        
        # Cost optimization: Cache common responses
        self.response_cache = {
            "cost_questions": "Our diagnostic fee is HKD 100. Repair costs vary based on the issue (software: HKD 100-300, hardware: varies by parts needed).",
            "timeline_questions": "Most repairs take 2-5 business days. Simple software fixes can be same-day.",
            "location_questions": "Drop-off details will be provided with your ticket confirmation.",
            "warranty_questions": "Check manufacturer warranty first. We handle out-of-warranty repairs with 30-day guarantee.",
            "data_safety": "We recommend backing up data. Hardware repairs usually preserve data, software repairs have small risk."
        }
        
        # Priority 1: Try Gemini API Key mode (direct API access)
        self._load_env()
        if self.api_key:
            try:
                from google import genai
                from google.genai import types

                # Initialize client with API key mode
                self.client = genai.Client(api_key=self.api_key)

                # Store generation config
                self.config = types.GenerateContentConfig(
                    temperature=0.7,
                    top_p=0.9,
                    top_k=40,
                    max_output_tokens=256,
                )
                self.use_real_api = True
                self.use_vertex = False
                print("[Gemini] ✅ Connected to Gemini API using API key")
                return
            except ImportError:
                print("[Gemini] ⚠️  google-genai not installed. Run: pip install google-genai")
            except Exception as e:
                print(f"[Gemini] ⚠️  Gemini API key connection failed: {type(e).__name__}: {e}")
        
        # Priority 2: Try Vertex AI mode as fallback
        credentials_path = VERTEX_CREDENTIALS_PATH
        if credentials_path and os.path.exists(credentials_path):
            try:
                # Set environment variable for service account
                os.environ.setdefault('GOOGLE_APPLICATION_CREDENTIALS', credentials_path)

                from google import genai
                from google.genai import types

                # Initialize client with Vertex AI mode
                self.client = genai.Client(vertexai=True, project=self.project_id, location=self.location)

                # Store generation config
                self.config = types.GenerateContentConfig(
                    temperature=0.7,
                    top_p=0.9,
                    top_k=40,
                    max_output_tokens=256,
                )
                self.use_real_api = True
                self.use_vertex = True
                print("[Gemini] ✅ Connected to Google Gen AI SDK (Vertex AI mode) using Vertex credentials")
                return
            except ImportError:
                print("[Gemini] ⚠️  google-genai not installed. Run: pip install google-genai")
            except Exception as e:
                print(f"[Gemini] ⚠️  Vertex AI connection failed: {type(e).__name__}: {e}")

        # Fallback: Mock mode
        print("[Gemini] ⚠️  Using mock mode (neither API key nor Vertex AI available)")
    
    def _load_env(self):
        """Load environment variables from .env file."""
        self.api_key = None
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        if key.strip() == 'GEMINI_API_KEY':
                            self.api_key = value.strip()
                            break
        
    def generate_response(self, user_input, conversation_history, current_step_context):
        """Generate response with cost optimization.
        
        Uses cached responses for common questions to avoid API calls.
        """
        
        # Check for common questions first (avoid API call)
        user_lower = user_input.lower()
        
        if any(word in user_lower for word in ["cost", "price", "expensive", "much", "fee"]):
            entities = self._extract_entities_from_input(user_input)
            return {
                "message": self.response_cache["cost_questions"],
                "entities_detected": entities
            }
        elif any(word in user_lower for word in ["how long", "when", "time", "wait"]):
            return {
                "message": self.response_cache["timeline_questions"],
                "entities_detected": {}
            }
        elif any(word in user_lower for word in ["where", "location", "address", "drop off"]):
            return {
                "message": self.response_cache["location_questions"],
                "entities_detected": {}
            }
        elif any(word in user_lower for word in ["warranty", "guarantee", "covered"]):
            return {
                "message": self.response_cache["warranty_questions"],
                "entities_detected": {}
            }
        elif any(word in user_lower for word in ["data", "files", "backup", "lose", "safe"]):
            return {
                "message": self.response_cache["data_safety"],
                "entities_detected": {}
            }
        
        # Only use API for complex queries or entity extraction
        if self.use_real_api:
            return self._real_generate_response(user_input, conversation_history, current_step_context)
        else:
            return self._mock_generate_response(user_input, current_step_context)
    
    def _real_generate_response(self, user_input, conversation_history, current_step_context):
        """Call actual Gemini API using Google Gen AI SDK."""
        try:
            prompt = self._build_prompt(user_input, conversation_history, current_step_context)
            
            # Use appropriate model based on connection type
            if self.use_vertex:
                # Vertex AI model name
                model_name = 'gemini-2.0-flash-lite'
            else:
                # Direct API model name
                model_name = 'gemini-2.0-flash-lite'
            
            response = self.client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=self.config
            )
            
            mode = "Vertex AI" if self.use_vertex else "API Key"
            print(f"[Gemini] Generated response (real API - {mode})")
            
            # Parse JSON response from Gemini
            try:
                parsed_response = self._parse_gemini_json_response(response.text)
                return parsed_response
            except Exception as parse_error:
                print(f"[Gemini] JSON parsing failed: {parse_error}")
                print(f"[Gemini] Raw response: {response.text[:200]}...")
                # Fallback to simple entity extraction
                entities = self._extract_entities_from_input(user_input)
                return {
                    "message": response.text,
                    "entities_detected": entities
                }
                
        except Exception as e:
            print(f"[Gemini] API error: {e}. Falling back to mock.")
            return self._mock_generate_response(user_input, current_step_context)
    
    def _mock_generate_response(self, user_input, current_step_context):
        """Mock response generation using enhanced entity detection."""
        
        # Use the enhanced entity detection
        entity_result = self._mock_generate_response_with_structured_entities(user_input, current_step_context)
        return entity_result
    
    def _build_prompt(self, user_input, conversation_history, current_step_context):
        """Build optimized prompt using current session data."""
        
        # Get current session data to minimize redundant extraction
        session_data = self._get_session_summary(conversation_history)
        
        prompt = f"""You are DormDoctorDiagnostics, a repair assistant.

CURRENT CONTEXT: {current_step_context}
KNOWN INFO: {session_data}
USER INPUT: "{user_input}"

TASK: Respond helpfully and extract ANY entities mentioned.

IMPORTANT: You MUST respond with ONLY valid JSON. No markdown, no extra text, no code blocks.

Example of user saying phone number correction:
User: "woops i forgot my phone number is actually +852 4839 8392"
Response: {{"user_response": "Got it, I'll update your phone number.", "new_entities": {{"phone_number": "+852 4839 8392"}}, "confidence": {{"phone": 1.0, "device": 0.0}}}}

OUTPUT FORMAT (JSON only, no markdown):
{{"user_response": "helpful response (50 words max)", "new_entities": {{"phone_number": "if phone mentioned/corrected", "device_info": "if device details provided", "issue_info": "if issue described"}}, "confidence": {{"phone": 0.0, "device": 0.0}}}}

CRITICAL FORMATTING RULES:
1. Use underscore in keys: "phone_number" NOT "phonenumber"
2. Use underscore in keys: "device_info" NOT "deviceinfo"
3. Use underscore in keys: "issue_info" NOT "issueinfo"
4. Extract entities if user provides/corrects them
5. For HK phones: use +852 XXXX XXXX format
6. Keep response under 50 words
7. Output ONLY the JSON object, no other text
8. Do NOT wrap JSON in markdown code blocks"""
        
        return prompt
    
    def _get_session_summary(self, conversation_history):
        """Extract current session state to avoid re-extracting known entities."""
        summary_parts = []
        
        # Look for existing data in conversation
        for msg in conversation_history[-10:]:  # Last 10 messages only
            content = msg.get("content", "").lower()
            role = msg.get("role", "")
            
            if role == "bot":
                # Extract key info from bot messages
                if "phone:" in content or "+852" in content:
                    summary_parts.append("phone_provided")
                if any(device in content for device in ["laptop", "iphone", "macbook", "asus", "dell"]):
                    summary_parts.append("device_mentioned")
                if any(issue in content for issue in ["software", "hardware", "issue"]):
                    summary_parts.append("issue_discussed")
        
        return f"Known: {', '.join(set(summary_parts)) if summary_parts else 'none'}"
    
    def _extract_entities_from_input(self, user_input):
        """Extract entities from user input using pattern matching."""
        entities = {}
        
        # Phone number detection (Hong Kong)
        import re
        phone_pattern = r'(\+?852\s?\d{4}\s?\d{4})'
        phone_match = re.search(phone_pattern, user_input)
        if phone_match:
            entities["phone"] = phone_match.group(1)
        
        # Device info detection
        device_keywords = ["laptop", "phone", "macbook", "iphone", "asus", "dell", "hp", "samsung", 
                          "ram", "gb", "inch", "pro", "air", "tablet", "ipad"]
        user_lower = user_input.lower()
        if any(keyword in user_lower for keyword in device_keywords) and len(user_input.split()) > 2:
            entities["device_info"] = user_input
        
        return entities
    
    def _parse_gemini_json_response(self, response_text):
        """Parse JSON response from Gemini, handling various formats."""
        import json
        import re
        
        # Clean the response text first
        cleaned_text = response_text.strip()
        
        # Remove markdown code blocks if present (try multiple patterns)
        # Pattern 1: ```json ... ```
        if "```json" in cleaned_text:
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', cleaned_text, re.DOTALL)
            if json_match:
                cleaned_text = json_match.group(1).strip()
        # Pattern 2: ``` ... ```
        elif "```" in cleaned_text:
            json_match = re.search(r'```\s*([\s\S]*?)\s*```', cleaned_text, re.DOTALL)
            if json_match:
                cleaned_text = json_match.group(1).strip()
        
        # Also try to extract just the JSON object if it's there
        if not cleaned_text.startswith('{'):
            json_obj_match = re.search(r'\{[\s\S]*\}', cleaned_text, re.DOTALL)
            if json_obj_match:
                cleaned_text = json_obj_match.group(0)
        
        # Try to extract JSON object
        json_pattern = r'\{[\s\S]*?\}'
        json_match = re.search(json_pattern, cleaned_text, re.DOTALL)
        
        if json_match:
            json_str = json_match.group(0)
        else:
            # Try the entire cleaned text as JSON
            json_str = cleaned_text
            if not json_str.startswith('{'):
                raise ValueError("No JSON object found in response")
        
        try:
            # Try parsing the JSON - if it's truncated, try to complete it
            try:
                parsed = json.loads(json_str)
            except json.JSONDecodeError as e:
                # If JSON is incomplete (common with truncated responses), try to fix it
                print(f"[Gemini] JSON incomplete, attempting to fix: {str(e)}")
                # Add closing braces if missing
                if json_str.count('{') > json_str.count('}'):
                    json_str += '}' * (json_str.count('{') - json_str.count('}'))
                parsed = json.loads(json_str)
            
            # Convert to our expected format
            entities = {}
            if "new_entities" in parsed:
                new_entities = parsed["new_entities"]
                # Only process non-null, non-empty entities
                for key, value in new_entities.items():
                    if value and str(value).lower() not in ["null", "none", ""]:
                        if key == "phone_number":
                            entities["phone"] = value
                        elif key == "device_info":
                            entities["device_info"] = value
                        elif key == "issue_info":
                            entities["issue_description"] = value
            
            return {
                "message": parsed.get("user_response", "I understand."),
                "entities_detected": entities,
                "confidence_scores": parsed.get("confidence", {})
            }
            
        except json.JSONDecodeError as e:
            print(f"[Gemini] JSON decode error: {e}")
            print(f"[Gemini] Attempted to parse: {json_str[:100]}...")
            raise ValueError(f"Invalid JSON: {e}")
    
    def _mock_generate_response_with_structured_entities(self, user_input, current_step_context):
        """Enhanced mock response with better entity extraction matching user examples."""
        user_input_lower = user_input.lower()
        
        # Extract entities using improved patterns
        entities = {}
        confidence = {}
        
        # Enhanced phone detection with better formatting
        import re
        phone_patterns = [
            r'(\+852\s?\d{4}\s?\d{4})',  # +852 1234 5678
            r'(852\s?\d{4}\s?\d{4})',   # 852 1234 5678  
            r'(\+852\s?\d{8})',         # +8521234568
            r'(\d{4}\s?\d{4})',         # 1234 5678 (assume HK if 8 digits)
        ]
        
        for pattern in phone_patterns:
            match = re.search(pattern, user_input)
            if match:
                phone = match.group(1)
                # Normalize to +852 XXXX XXXX format
                digits_only = re.sub(r'[^\d]', '', phone)
                if digits_only.startswith('852'):
                    digits_only = digits_only[3:]  # Remove 852 prefix
                elif len(digits_only) == 8:
                    pass  # Already 8 digits
                else:
                    continue  # Invalid format
                
                if len(digits_only) == 8:
                    formatted_phone = f"+852 {digits_only[:4]} {digits_only[4:]}"
                    entities["phone"] = formatted_phone
                    confidence["phone"] = 1.0
                break
        
        # Enhanced device detection
        device_keywords = {
            "laptop": ["laptop", "notebook", "macbook"],
            "phone": ["phone", "iphone", "smartphone"], 
            "tablet": ["tablet", "ipad"],
        }
        
        brands = ["apple", "asus", "dell", "hp", "samsung", "lenovo", "acer", "msi", "razer"]
        
        # Check if user is providing device information
        has_device_info = False
        for dtype, keywords in device_keywords.items():
            if any(keyword in user_input_lower for keyword in keywords):
                has_device_info = True
                break
        
        # Check for brand mentions
        for brand in brands:
            if brand in user_input_lower:
                has_device_info = True
                break
        
        # If device info detected and it's substantial, extract it
        if has_device_info and len(user_input.split()) >= 2:
            entities["device_info"] = user_input
            confidence["device"] = 0.9
        
        # Check for correction/update keywords
        is_correction = any(word in user_input_lower for word in [
            "woops", "oops", "sorry", "actually", "forgot", "correction", 
            "mistake", "wrong", "meant", "should be", "change", "update"
        ])
        
        # Generate response based on context and entities found
        if "phone" in entities:
            if is_correction:
                message = "Got it, I'll update your phone number."
            else:
                message = f"Thank you! I've noted your phone number as {entities['phone']}."
        elif "device_info" in entities:
            if is_correction:
                message = "Understood, I'll update your device information."
            else:
                message = f"Thanks for the device details: {entities['device_info']}."
        elif any(word in user_input_lower for word in ["cost", "price", "expensive", "much", "fee"]):
            message = "Our diagnostic fee is HKD 100. Repair costs vary based on the issue - software fixes typically range from HKD 100-300, while hardware repairs depend on parts needed."
        elif any(word in user_input_lower for word in ["how long", "when", "time", "wait", "duration"]):
            message = "Most repairs take 2-5 business days depending on parts availability. Simple software fixes can often be done same-day."
        elif any(word in user_input_lower for word in ["where", "location", "address", "drop off", "drop-off"]):
            message = "You can drop off your device at our dorm repair station. I'll provide the exact address and instructions at the end of our chat."
        elif any(word in user_input_lower for word in ["warranty", "guarantee", "covered"]):
            message = "If your device is under manufacturer warranty, we recommend checking with them first. We handle out-of-warranty repairs with a 30-day guarantee."
        elif any(word in user_input_lower for word in ["data", "files", "backup", "lose", "safe"]):
            message = "We always recommend backing up your data before any repair. Hardware repairs usually preserve data, but software repairs have some risk."
        elif any(word in user_input_lower for word in ["help", "confused", "don't understand", "what", "?"]):
            message = "No worries! I'm here to help you report your device issue and get an estimate. Just answer my questions as best as you can."
        else:
            message = "I understand. Is there anything else I can help you with today? Please provide details about your device or the issue you're experiencing."
        
        return {
            "message": message,
            "entities_detected": entities,
            "confidence_scores": confidence
        }
    
    def _format_history(self, history):
        """Format conversation history for prompt (Phase 2)."""
        formatted = []
        for msg in history[-5:]:  # Last 5 messages
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            formatted.append(f"{role}: {content}")
        return "\n".join(formatted)
    
    # ========== NEW METHODS FOR REFACTORED FLOW ==========
    
    def extract_user_name(self, user_input, conversation_history):
        """Extract user's first and last name with validation.
        
        Args:
            user_input: User's name input
            conversation_history: Previous conversation messages
            
        Returns:
            dict with:
                - user_name: Extracted full name
                - fulfilled: Boolean indicating if valid name provided
                - clarification: Prompt if fulfilled=False
        """
        if self.use_real_api:
            return self._extract_user_name_real(user_input, conversation_history)
        else:
            return self._extract_user_name_mock(user_input)
    
    def _extract_user_name_real(self, user_input, conversation_history):
        """Real API call for user name extraction."""
        prompt = f"""You are extracting a person's first and last name.

USER INPUT: "{user_input}"
CONVERSATION HISTORY: {self._format_history(conversation_history)}

TASK: Extract the user's full name (first and last). Distinguish between real names vs irrelevant input.

CASES:

1. VALID NAME (looks like actual first + last name):
   - Extract and mark fulfilled=true
   
2. INCOMPLETE (only first name or unclear):
   - Mark fulfilled=false, ask for full name
   
3. IRRELEVANT (gibberish, food, random words):
   - Mark fulfilled=false
   - Make a FRIENDLY JOKE
   - Ask for their actual name

Examples:
Input: "John Smith" → {{"user_name": "John Smith", "fulfilled": true, "clarification": ""}}
Input: "Jane Doe" → {{"user_name": "Jane Doe", "fulfilled": true, "clarification": ""}}
Input: "John" → {{"user_name": "", "fulfilled": false, "clarification": "Thanks John! Could you also provide your last name?"}}
Input: "sausages" → {{"user_name": "", "fulfilled": false, "clarification": "Haha, 'Sausages' is a fun name, but I need your real name! 😄 What's your first and last name?"}}
Input: "abc123" → {{"user_name": "", "fulfilled": false, "clarification": "That doesn't look like a name. Could you provide your actual first and last name? (e.g., John Smith)"}}

OUTPUT FORMAT (JSON only, no markdown):
{{"user_name": "full name or empty", "fulfilled": true|false, "clarification": "prompt if needed"}}
"""
        
        try:
            model_name = 'gemini-2.0-flash-lite'
            response = self.client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=self.config
            )
            
            import json
            import re
            
            json_match = re.search(r'\{[^{}]*\}', response.text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
                return {
                    "user_name": result.get("user_name", ""),
                    "fulfilled": result.get("fulfilled", False),
                    "clarification": result.get("clarification", "")
                }
        except Exception as e:
            print(f"[Gemini] User name extraction error: {e}")
        
        return self._extract_user_name_mock(user_input)
    
    def _extract_user_name_mock(self, user_input):
        """Mock user name extraction."""
        user_input = user_input.strip()
        words = user_input.split()
        
        # Check for irrelevant keywords
        irrelevant = ["sausage", "banana", "cat", "dog", "pizza", "123", "test"]
        if any(word.lower() in user_input.lower() for word in irrelevant):
            return {
                "user_name": "",
                "fulfilled": False,
                "clarification": "That doesn't look like a real name! 😄 What's your actual first and last name?"
            }
        
        # Check if it looks like a name (at least 2 words)
        if len(words) >= 2:
            return {
                "user_name": user_input,
                "fulfilled": True,
                "clarification": ""
            }
        elif len(words) == 1 and len(user_input) > 1:
            # Only first name
            return {
                "user_name": "",
                "fulfilled": False,
                "clarification": f"Thanks {user_input}! Could you also provide your last name?"
            }
        else:
            return {
                "user_name": "",
                "fulfilled": False,
                "clarification": "Could you provide your first and last name? (e.g., John Smith)"
            }
    
    def extract_device_type(self, user_input, conversation_history):
        """Extract device type with entity fulfillment check.
        
        Args:
            user_input: User's description of device type
            conversation_history: Previous conversation messages
            
        Returns:
            dict with:
                - device_type: Extracted device type (laptop/phone/tablet/etc)
                - fulfilled: Boolean indicating if entity is clear enough
                - clarification: Prompt to ask user if fulfilled=False
        """
        if self.use_real_api:
            return self._extract_device_type_real(user_input, conversation_history)
        else:
            return self._extract_device_type_mock(user_input)
    
    def _extract_device_type_real(self, user_input, conversation_history):
        """Real API call for device type extraction."""
        prompt = f"""You are extracting device type information.

USER INPUT: "{user_input}"
CONVERSATION HISTORY: {self._format_history(conversation_history)}

TASK: Determine the device type. Common types: laptop, phone, tablet, desktop, smartwatch, gaming console, etc.

If the input is clear (e.g. "laptop", "my phone", "tablet"), extract it.
If ambiguous (e.g. "it's kinda both" or "surface"), ask for clarification.

OUTPUT FORMAT (JSON only, no markdown):
{{"device_type": "laptop|phone|tablet|etc", "fulfilled": true|false, "clarification": "ask if not clear"}}

Examples:
Input: "laptop" → {{"device_type": "laptop", "fulfilled": true, "clarification": ""}}
Input: "phone" → {{"device_type": "phone", "fulfilled": true, "clarification": ""}}
Input: "it's like a tablet and laptop" → {{"device_type": "tablet-laptop hybrid", "fulfilled": false, "clarification": "Is it a 2-in-1 device like a Surface Pro, or an iPad with keyboard?"}}
Input: "surface pro" → {{"device_type": "laptop", "fulfilled": true, "clarification": ""}}
"""
        
        try:
            model_name = 'gemini-2.0-flash-lite'
            response = self.client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=self.config
            )
            
            import json
            import re
            
            # Extract JSON from response
            json_match = re.search(r'\{[^{}]*\}', response.text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
                return {
                    "device_type": result.get("device_type", "unknown"),
                    "fulfilled": result.get("fulfilled", False),
                    "clarification": result.get("clarification", "")
                }
        except Exception as e:
            print(f"[Gemini] Device type extraction error: {e}")
        
        # Fallback
        return self._extract_device_type_mock(user_input)
    
    def _extract_device_type_mock(self, user_input):
        """Mock device type extraction."""
        user_lower = user_input.lower()
        
        if any(word in user_lower for word in ["laptop", "notebook", "macbook"]):
            return {"device_type": "laptop", "fulfilled": True, "clarification": ""}
        elif any(word in user_lower for word in ["phone", "iphone", "smartphone", "mobile"]):
            return {"device_type": "phone", "fulfilled": True, "clarification": ""}
        elif any(word in user_lower for word in ["tablet", "ipad"]):
            return {"device_type": "tablet", "fulfilled": True, "clarification": ""}
        elif any(word in user_lower for word in ["surface", "hybrid", "2-in-1", "2 in 1"]):
            return {"device_type": "laptop", "fulfilled": True, "clarification": ""}
        else:
            return {
                "device_type": "unknown",
                "fulfilled": False,
                "clarification": "Could you be more specific? Is it a laptop, phone, or tablet?"
            }
    
    def extract_brandmodel(self, user_input, conversation_history, device_type):
        """Extract combined brand and model with entity fulfillment check.
        
        Args:
            user_input: User's description of brand/model
            conversation_history: Previous conversation messages
            device_type: Device type from previous step
            
        Returns:
            dict with:
                - brandmodel: Extracted combined brand and model
                - fulfilled: Boolean indicating if entity is clear
                - clarification: Prompt if fulfilled=False
        """
        if self.use_real_api:
            return self._extract_brandmodel_real(user_input, conversation_history, device_type)
        else:
            return self._extract_brandmodel_mock(user_input)
    
    def _extract_brandmodel_real(self, user_input, conversation_history, device_type):
        """Real API call for brandmodel extraction."""
        prompt = f"""You are extracting device brand and model information.

DEVICE TYPE: {device_type}
USER INPUT: "{user_input}"
CONVERSATION HISTORY: {self._format_history(conversation_history)}

TASK: Extract the brand and model as a SINGLE combined string. Distinguish between unclear device info vs completely irrelevant input.

THREE CASES:

1. CLEAR device info (recognizable brands/models):
   - Extract and mark fulfilled=true
   
2. UNCLEAR device info (looks like attempt at brand/model but unclear):
   - Extract literally, mark fulfilled=false, ask for clarification
   
3. COMPLETELY IRRELEVANT (random words, food, animals, gibberish):
   - Mark fulfilled=false
   - Make a PLAYFUL JOKE about what they said
   - Then ask them to provide actual device info

Examples:
Input: "Samsung Tab A7" → {{"brandmodel": "Samsung Tab A7", "fulfilled": true, "clarification": ""}}
Input: "iPhone 13" → {{"brandmodel": "Apple iPhone 13", "fulfilled": true, "clarification": ""}}
Input: "giraffe 78" → {{"brandmodel": "giraffe 78", "fulfilled": false, "clarification": "I'm not familiar with that brand. Could you double-check the brand name? For example: Samsung Tab A8, iPhone 13, ASUS ROG"}}
Input: "sausages" → {{"brandmodel": "", "fulfilled": false, "clarification": "Haha, sausages are great, but they're not gonna help fix your device! 😄 Could you tell me your actual device brand and model? For example: Samsung Galaxy Tab, iPhone 13, ASUS Laptop"}}
Input: "banana" → {{"brandmodel": "", "fulfilled": false, "clarification": "Ring ring ring, banana phone! 🍌 But seriously, what's your device brand and model? (e.g., Samsung Tab A8, MacBook Air)"}}
Input: "my cat" → {{"brandmodel": "", "fulfilled": false, "clarification": "Cats are adorable! 🐱 But I need to know your device brand and model to help you. What device are you trying to fix?"}}

OUTPUT FORMAT (JSON only, no markdown):
{{"brandmodel": "extracted or empty", "fulfilled": true|false, "clarification": "joke + ask if irrelevant, or clarify if unclear"}}
"""
        
        try:
            model_name = 'gemini-2.0-flash-lite'
            response = self.client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=self.config
            )
            
            import json
            import re
            
            json_match = re.search(r'\{[^{}]*\}', response.text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
                return {
                    "brandmodel": result.get("brandmodel", ""),
                    "fulfilled": result.get("fulfilled", False),
                    "clarification": result.get("clarification", "")
                }
        except Exception as e:
            print(f"[Gemini] Brand/model extraction error: {e}")
        
        return self._extract_brandmodel_mock(user_input)
    
    def _extract_brandmodel_mock(self, user_input):
        """Mock brandmodel extraction."""
        brandmodel = user_input.strip()
        user_lower = brandmodel.lower()
        
        # Check for common irrelevant inputs
        irrelevant_keywords = {
            "sausage": "Haha, sausages are great, but they're not gonna help fix your device! 😄",
            "banana": "Ring ring ring, banana phone! 🍌 But seriously,",
            "cat": "Cats are adorable! 🐱 But I need to know your device",
            "dog": "Dogs are awesome! 🐶 But let's focus on your device",
            "pizza": "Pizza is life! 🍕 But it won't fix your device",
            "food": "I'm hungry too, but",
            "random": "That's quite random!",
        }
        
        # Check if input is completely irrelevant
        for keyword, joke_start in irrelevant_keywords.items():
            if keyword in user_lower:
                return {
                    "brandmodel": "",
                    "fulfilled": False,
                    "clarification": f"{joke_start} what's your actual device brand and model? (e.g., Samsung Tab A8, iPhone 13, ASUS Laptop)"
                }
        
        # Check for known brands
        known_brands = ["samsung", "apple", "iphone", "ipad", "macbook", "asus", "dell", 
                       "hp", "lenovo", "acer", "microsoft", "surface", "huawei", "xiaomi",
                       "oppo", "vivo", "oneplus", "google", "pixel"]
        
        has_known_brand = any(brand in user_lower for brand in known_brands)
        
        # If single word and no known brand, likely irrelevant
        if len(brandmodel.split()) == 1 and not has_known_brand:
            return {
                "brandmodel": "",
                "fulfilled": False,
                "clarification": f"Hmm, '{brandmodel}' doesn't look like a device brand I recognize. Could you provide the actual brand and model? For example: Samsung Tab A8, iPhone 13, ASUS ROG"
            }
        
        # If looks like it could be a device (2+ words or has known brand)
        if len(brandmodel.split()) >= 2 or has_known_brand:
            return {
                "brandmodel": brandmodel,
                "fulfilled": True,
                "clarification": ""
            }
        else:
            return {
                "brandmodel": brandmodel,
                "fulfilled": False,
                "clarification": "Could you provide both the brand and model? For example: Samsung Tab A8, iPhone 13, ASUS Laptop"
            }
    
    def extract_additional_info(self, user_input, conversation_history, device_type, brandmodel):
        """Extract additional device information and check relevance.
        
        Args:
            user_input: User's additional info or response
            conversation_history: Previous conversation messages
            device_type: Device type
            brandmodel: Brand and model
            
        Returns:
            dict with:
                - additional_info: Extracted info (if relevant)
                - relevant: Boolean - true if on-topic device info, false otherwise
                - joke_response: Friendly joke if irrelevant (only if relevant=false)
        """
        if self.use_real_api:
            return self._extract_additional_info_real(user_input, conversation_history, device_type, brandmodel)
        else:
            return self._extract_additional_info_mock(user_input)
    
    def _extract_additional_info_real(self, user_input, conversation_history, device_type, brandmodel):
        """Real API call for additional info extraction."""
        prompt = f"""You are collecting optional additional device information.

DEVICE: {brandmodel} ({device_type})
USER INPUT: "{user_input}"

TASK: Determine if the user provided RELEVANT device information (RAM, storage, purchase year, condition, etc.)

If RELEVANT (device specs/info):
- Extract the information
- Set relevant=true

If IRRELEVANT (random stuff like "sausages", "my cat", etc.):
- Make a playful, friendly joke about what they said
- Set relevant=false
- Encourage them to get back on track

OUTPUT FORMAT (JSON only, no markdown):
{{"additional_info": "extracted info or empty", "relevant": true|false, "joke_response": "friendly joke if irrelevant"}}

Examples:
Input: "18 gigs of ram, purchased in 2020" → {{"additional_info": "18 gigs of ram, purchased in 2020", "relevant": true, "joke_response": ""}}
Input: "sausages" → {{"additional_info": "", "relevant": false, "joke_response": "Haha, sausages are great, but I don't think they'll help fix your device! 😄 Let's get back to business - do you have any actual device specs to share, or shall we move on?"}}
Input: "512GB SSD, 16GB RAM" → {{"additional_info": "512GB SSD, 16GB RAM", "relevant": true, "joke_response": ""}}
Input: "banana phone" → {{"additional_info": "", "relevant": false, "joke_response": "Ring ring ring ring ring, banana phone! 🍌📞 Classic tune, but let's focus on your actual device. Any real specs to share, or ready to continue?"}}
"""
        
        try:
            model_name = 'gemini-2.0-flash-lite'
            response = self.client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=self.config
            )
            
            import json
            import re
            
            json_match = re.search(r'\{[^{}]*\}', response.text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
                return {
                    "additional_info": result.get("additional_info", ""),
                    "relevant": result.get("relevant", True),
                    "joke_response": result.get("joke_response", "")
                }
        except Exception as e:
            print(f"[Gemini] Additional info extraction error: {e}")
        
        return self._extract_additional_info_mock(user_input)
    
    def _extract_additional_info_mock(self, user_input):
        """Mock additional info extraction."""
        user_lower = user_input.lower()
        
        # Check for device-relevant keywords
        relevant_keywords = ["gb", "ram", "storage", "ssd", "hdd", "purchased", "bought", "year", 
                            "warranty", "condition", "new", "used", "gb", "tb", "ghz", "processor"]
        
        is_relevant = any(keyword in user_lower for keyword in relevant_keywords)
        
        if is_relevant:
            return {
                "additional_info": user_input.strip(),
                "relevant": True,
                "joke_response": ""
            }
        else:
            # Generate a playful response for common irrelevant inputs
            jokes = {
                "sausage": "Haha, sausages are great, but I don't think they'll help fix your device! 😄",
                "banana": "Ring ring ring, banana phone! 🍌 Classic, but let's focus on your actual device.",
                "cat": "Cats are adorable, but they're not exactly tech specs! 🐱",
                "dog": "Dogs are awesome, but unfortunately not a device spec! 🐶",
                "pizza": "Pizza is life, but it won't fix your device! 🍕",
            }
            
            joke = "That's... interesting! But let's get back to your device."
            for keyword, response in jokes.items():
                if keyword in user_lower:
                    joke = response
                    break
            
            return {
                "additional_info": "",
                "relevant": False,
                "joke_response": f"{joke} Do you have any actual device specs to share, or shall we move on?"
            }
    
    def diagnostic_session(self, device_type, brandmodel, issue_type, description, user_input, conversation_history):
        """Interactive diagnostic session with Gemini.
        
        Args:
            device_type: Device type
            brandmodel: Combined brand and model
            issue_type: software/hardware/unsure
            description: User's problem description
            user_input: Current user message
            conversation_history: Full conversation
            
        Returns:
            dict with:
                - response: Gemini's diagnostic response
                - skip: Boolean if user wants to skip
                - parts_needed: List of parts that may need replacement
        """
        if self.use_real_api:
            return self._diagnostic_session_real(device_type, brandmodel, issue_type, description, user_input, conversation_history)
        else:
            return self._diagnostic_session_mock(user_input, issue_type)
    
    def _diagnostic_session_real(self, device_type, brandmodel, issue_type, description, user_input, conversation_history):
        """Real API diagnostic session."""
        prompt = f"""You are a repair technician providing diagnostic help.

DEVICE INFO:
- Type: {device_type}
- Brand/Model: {brandmodel}
- Issue Type: {issue_type}
- Description: {description}

USER MESSAGE: "{user_input}"
CONVERSATION: {self._format_history(conversation_history)}

TASK: Provide helpful diagnostic steps. Detect if user wants to skip. Identify parts that may need replacement.

OUTPUT FORMAT (JSON only):
{{"response": "your diagnostic advice", "skip": false, "parts_needed": ["part1", "part2"]}}

Examples:
Input: "how do I fix it?" → {{"response": "Try restarting in safe mode first...", "skip": false, "parts_needed": []}}
Input: "let's skip this" → {{"response": "Understood, moving to cost estimation.", "skip": true, "parts_needed": ["LCD panel"]}}
Input: "screen is cracked" → {{"response": "A cracked screen needs replacement...", "skip": false, "parts_needed": ["LCD panel", "digitizer"]}}
"""
        
        try:
            model_name = 'gemini-2.0-flash-lite'
            response = self.client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=self.config
            )
            
            import json
            import re
            
            json_match = re.search(r'\{[^{}]*\}', response.text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
                return {
                    "response": result.get("response", ""),
                    "skip": result.get("skip", False),
                    "parts_needed": result.get("parts_needed", [])
                }
        except Exception as e:
            print(f"[Gemini] Diagnostic session error: {e}")
        
        return self._diagnostic_session_mock(user_input, issue_type)
    
    def _diagnostic_session_mock(self, user_input, issue_type):
        """Mock diagnostic session."""
        user_lower = user_input.lower()
        
        # Check for skip intent
        skip_keywords = ["skip", "no thanks", "move on", "next", "let's continue", "estimate"]
        wants_skip = any(word in user_lower for word in skip_keywords)
        
        # Detect parts from keywords
        parts = []
        if any(word in user_lower for word in ["screen", "display", "lcd"]):
            parts.append("LCD panel")
        if any(word in user_lower for word in ["battery", "charge", "power"]):
            parts.append("battery")
        
        if wants_skip:
            response = "Understood! Let's move to cost estimation."
        elif issue_type == "software":
            response = "For software issues, try: 1) Restart device 2) Check for updates 3) Clear app cache. Does this help?"
        else:
            response = "Based on your description, this may require part replacement. Can you describe the physical condition?"
        
        return {
            "response": response,
            "skip": wants_skip,
            "parts_needed": parts
        }
    
    def detect_parts_only(self, device_type, brandmodel, issue_type, description):
        """Silently detect parts needed without user interaction.
        
        Used when user skips diagnostic session.
        
        Returns:
            dict with:
                - parts_needed: List of parts
        """
        if self.use_real_api:
            return self._detect_parts_real(device_type, brandmodel, issue_type, description)
        else:
            return self._detect_parts_mock(description, issue_type)
    
    def _detect_parts_real(self, device_type, brandmodel, issue_type, description):
        """Real API parts detection."""
        prompt = f"""Analyze this repair case and identify parts that may need replacement.

DEVICE: {brandmodel} ({device_type})
ISSUE TYPE: {issue_type}
DESCRIPTION: {description}

TASK: List parts that likely need replacement based on the description.

OUTPUT FORMAT (JSON only):
{{"parts_needed": ["part1", "part2"]}}

Examples:
- "screen cracked" → {{"parts_needed": ["LCD panel"]}}
- "won't charge" → {{"parts_needed": ["battery", "charging port"]}}
- "software slow" → {{"parts_needed": []}}
"""
        
        try:
            model_name = 'gemini-2.0-flash-lite'
            response = self.client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=self.config
            )
            
            import json
            import re
            
            json_match = re.search(r'\{[^{}]*\}', response.text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
                return {"parts_needed": result.get("parts_needed", [])}
        except Exception as e:
            print(f"[Gemini] Parts detection error: {e}")
        
        return self._detect_parts_mock(description, issue_type)
    
    def _detect_parts_mock(self, description, issue_type):
        """Mock parts detection."""
        desc_lower = description.lower()
        parts = []
        
        if issue_type == "software":
            return {"parts_needed": []}
        
        if any(word in desc_lower for word in ["screen", "display", "lcd", "cracked"]):
            parts.append("LCD panel")
        if any(word in desc_lower for word in ["battery", "charge", "power", "dead"]):
            parts.append("battery")
        if any(word in desc_lower for word in ["port", "charging port", "usb"]):
            parts.append("charging port")
        
        return {"parts_needed": parts}
