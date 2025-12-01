# Dialogflow ES Configuration Guide

This guide shows exactly how to configure Dialogflow ES intents to match with the codebase.

---

## Required Intent Names (Must Match Exactly)

### 1. Core Flow Intents

#### **Intent: `affirmative`**

- **Purpose:** Detect yes/positive responses
- **Training Phrases:**
  ```
  yes
  yeah
  yep
  sure
  ok
  okay
  alright
  absolutely
  definitely
  ```
- **Code Usage:** `intent_result["intent"] == "affirmative"`
- **Where Used:** Resuming after interrupts, feedback confirmation

---

#### **Intent: `negative`**

- **Purpose:** Detect no/negative responses
- **Training Phrases:**
  ```
  no
  nope
  nah
  not really
  no thanks
  I don't think so
  ```
- **Code Usage:** `intent_result["intent"] == "negative"`
- **Where Used:** Declining to continue, rejecting suggestions

---

#### **Intent: `issue_type`**

- **Purpose:** Detect hardware/software classification
- **Training Phrases:**
  ```
  hardware
  software
  physical problem
  digital issue
  app problem
  screen issue
  battery problem
  it's broken physically
  ```
- **Parameters:**
  - `@issue-type` (custom entity)
    - Values: `software`, `hardware`, `unsure`
- **Code Usage:** `intent_result["intent"] == "issue_type"`
- **Entity Access:** `intent_result["parameters"]["issue_type"]`

---

#### **Intent: `skip_diagnostics`**

- **Purpose:** User wants to skip troubleshooting tips
- **Training Phrases:**
  ```
  skip
  skip this
  no thanks
  I don't need tips
  just book it
  let's skip to booking
  ```
- **Code Usage:** `intent_result["intent"] == "skip_diagnostics"`

---

### 2. Interrupt Intents (Conversational)

These handle user questions mid-flow. **Names must match `config.INTERRUPT_INTENTS`**.

#### **Intent: `location.question`**

- **Training Phrases:**
  ```
  where are you based
  what's your location
  where do I drop it off
  where is the shop
  what's your address
  how do I find you
  ```
- **Fulfillment Text:**
  ```
  You can drop off your device at our dorm repair station.
  I'll provide the exact address and instructions at the end of our chat.
  ```

---

#### **Intent: `pricing.question`**

- **Training Phrases:**
  ```
  how much does this cost
  what are your prices
  is it expensive
  how much will I pay
  what's the fee
  pricing information
  ```
- **Fulfillment Text:**
  ```
  Our diagnostic fee is HKD 100. The actual repair cost depends on the issue.
  I'll provide a specific estimate once I know more about your device.
  ```

---

#### **Intent: `timeline.question`**

- **Training Phrases:**
  ```
  how long will this take
  when will it be ready
  how many days
  what's the turnaround time
  how long do repairs take
  ```
- **Fulfillment Text:**
  ```
  Most repairs take 2-5 business days depending on parts availability.
  Simple software fixes can often be done same-day.
  ```

---

#### **Intent: `warranty.question`**

- **Training Phrases:**
  ```
  is this covered by warranty
  do you honor warranty
  what about my warranty
  will this void warranty
  ```
- **Fulfillment Text:**
  ```
  If your device is under manufacturer warranty, we recommend checking with the
  manufacturer first. We provide repairs for out-of-warranty devices.
  ```

---

#### **Intent: `help.request`**

- **Training Phrases:**
  ```
  I don't understand
  what do you mean
  help me
  I'm confused
  can you explain
  what should I do
  ```
- **Fulfillment Text:**
  ```
  No worries! I'm here to help you report your device issue and get an estimate.
  Just answer my questions as best as you can.
  ```

---

#### **Intent: `data.safety`**

- **Training Phrases:**
  ```
  will I lose my data
  is my data safe
  what about my files
  should I backup
  can you recover data
  ```
- **Fulfillment Text:**
  ```
  We always recommend backing up your data before any repair. Your data is usually
  safe for hardware repairs, but we can't guarantee it for software issues.
  ```

---

## Custom Entities

### **@device-type**

- **Values:**
  ```
  laptop (synonyms: notebook, computer, pc, macbook)
  phone (synonyms: smartphone, mobile, iphone, android)
  tablet (synonyms: ipad, surface)
  ```

### **@device-brand**

- **Values:**
  ```
  Asus
  Dell
  HP
  Lenovo
  Apple
  Samsung
  Microsoft
  Acer
  MSI
  Razer
  ```

### **@issue-type**

- **Values:**
  ```
  software (synonyms: app, program, os, system, virus)
  hardware (synonyms: physical, broken, damaged, screen, battery)
  unsure (synonyms: don't know, not sure, both)
  ```

---

## How Code Accesses These

### Intent Name

```python
intent_result = dialogflow.detect_intent(session_id, "where are you based?")
# Returns: {"intent": "location.question", "confidence": 0.92, ...}

if intent_result["intent"] == "location.question":
    # Handle location question
```

### Entity Parameters

```python
intent_result = dialogflow.detect_intent(session_id, "asus laptop")
# Returns: {"intent": "device_info", "parameters": {"@device-brand": "asus", "@device-type": "laptop"}}

brand = intent_result["parameters"].get("@device-brand")  # "asus"
device = intent_result["parameters"].get("@device-type")  # "laptop"
```

### Fulfillment Text

```python
intent_result = dialogflow.detect_intent(session_id, "how much is it")
# Returns: {"intent": "pricing.question", "fulfillment_text": "Our diagnostic fee..."}

response = intent_result["fulfillment_text"]
print(response)  # Prints the configured fulfillment text
```

---

## Configuration Checklist

- [ ] Create all 4 core flow intents (`affirmative`, `negative`, `issue_type`, `skip_diagnostics`)
- [ ] Create all 6 interrupt intents (location, pricing, timeline, warranty, help, data safety)
- [ ] Add training phrases to each intent (at least 5-10 per intent)
- [ ] Create custom entities (`@device-type`, `@device-brand`, `@issue-type`)
- [ ] Set fulfillment text for all interrupt intents
- [ ] Test in Dialogflow console "Try it now" panel
- [ ] Update `dorm_doctor/config.py` if you add/rename any interrupt intents

---

## Testing

In Dialogflow console, try these inputs:

| User Input      | Expected Intent     | Expected Entity/Response                          |
| --------------- | ------------------- | ------------------------------------------------- |
| "yes"           | `affirmative`       | confidence > 0.9                                  |
| "hardware"      | `issue_type`        | `@issue-type`: "hardware"                         |
| "asus laptop"   | (custom)            | `@device-brand`: "asus", `@device-type`: "laptop" |
| "where are you" | `location.question` | Fulfillment text shown                            |
| "how much"      | `pricing.question`  | Fulfillment text shown                            |

---

## Adding New Intents

1. Create intent in Dialogflow with your chosen name (e.g., `refund.question`)
2. Add training phrases and fulfillment text
3. Add intent name to `dorm_doctor/config.py`:
   ```python
   INTERRUPT_INTENTS = [
       "location.question",
       "pricing.question",
       # ... existing intents
       "refund.question",  # ← Add here
   ]
   ```
4. Code will automatically handle it!

No other code changes needed ✅
