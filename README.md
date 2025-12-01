# CtrlFix - AI-Powered Repair Diagnostic Assistant

> **An intelligent ticketing and diagnostic chatbot for device repair services**  
> Built with Dialogflow ES, Google Gemini AI, and real-time e-commerce price scraping

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Dialogflow](https://img.shields.io/badge/Dialogflow-ES-orange.svg)](https://cloud.google.com/dialogflow)
[![Gemini](https://img.shields.io/badge/Gemini-2.0_Flash-purple.svg)](https://ai.google.dev/)

---

## Overview

**CtrlFix** is a sophisticated conversational AI system designed for device repair shops. It combines nlp systems, AI-powered diagnostics, and real-time pricing lookup to create an engaging, efficient ticket filing experience.

### Key Features

- 🤖 **Hybrid NLP Architecture** - Dialogflow ES for common intents + Gemini AI for complex conversations
- 💰 **Live Price Estimation** - Real-time part pricing via SerpAPI + Amazon integration
- 📊 **Automated Ticketing** - Google Sheets API for seamless ticket recording
- 🎨 **Beautiful Terminal UI** - ANSI color-coded(super duper simple and lightweight) interface with arrow key menus
- 🔄 **Interrupt Handling** - Users can ask questions mid-flow without losing progress
- 😄 **Playful UX** - LLM(gemini) configured to joke with users who provide silly responses (e.g., "sausages")

---

## 🏗️ Architecture

### Why Hybrid NLP?

Instead of relying solely on Dialogflow ES (which is limited in flow control and state management) or the expensive Dialogflow CX, CtrlFix uses a **custom Python orchestrator** that combines:

1. **Dialogflow ES** - First line of defense for common intents (pricing questions, location queries)
2. **Gemini 2.0 Flash Lite model** - Fallback for complex/unexpected user inputs
3. **Python Flow Manager** - Full control over state, validation, and business logic..

**Benefits:**

- 💸 Cost-efficient (saves on Gemini API calls by using Dialogflow first)
- 🛠️ Highly customizable (easy integration with APIs, databases, external tools)
- 📈 Scalable (modular architecture for future enhancements)

---

## Features Deep Dive

### 1. Smart Conversational Flow

**13-Step Diagnostic Journey:**

1. **Welcome** - Introduction and ticket ID generation
2. **Phone Number** - HK number with nlp (+852 XXXX XXXX). also built in validation on code.
3. **User Name** - Literal input (no NLP overhead)
4. **Device Type** - Laptop, phone, tablet, or others. Users dont have to provide literal var name, nlp with dialogflow has been trained to handle these inputs.
5. **Brand & Model** - Gemini extraction(invalidates fictional devices. Real RAG lookup with google to make sure the device is ACTUALLY real.) with joke responses for silly inputs
6. **Additional Info** - Optional specs for repair purposes(RAM, storage, etc.)
7. **Issue Type** - Arrow key menu (Software/Hardware/Unsure). Limits user input for simplicity.
8. **Problem Description** - Literal form input (no interrupts allowed). Directly sent over to google sheets.
9. **Diagnostic Opt-in** - optional AI-powered troubleshooting session with gemini as first line of defense
10. **Diagnostic Mode** - Open Gemini dialogue if opted in
11. **Cost Estimation** - Live Amazon price scraping + calculation + add with service fee in config file.
12. **Booking** - Instant drop-off vs. consulation
13. **Goodbye** - Summary and next steps

### 2. Real-Time Price Scraping

**Algorithm:**

```python
1. User completes diagnostic → Parts needed identified (using gemini LLM to intelligently classify what parts actually need replacement)
2. For each part: Query Amazon via SerpAPI
   Search: "{brandmodel} {part_name} replacement"
3. Extract prices from top 20 results
4. Calculate: (lowest + highest) / 2
5. Convert USD → HKD (rate: 7.8). HKD pegged to USD. how conveninent.
6. Display breakdown: Service Fee + Parts = Total
```

**Example Output:**

```
💰 COST ESTIMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Service Fee: HKD 100.00

Parts (Live Serp(Amazon) API):
- LCD Screen: HKD 780.50
- Battery: HKD 234.00

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total (Indicative): HKD 1,114.50
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 3. Google Sheets Auto-Ticketing

**Ticketing Algorithm:**

```python
1. Session data collected during flow
2. On completion: get_ticket_data() formats 13 fields:
   - ticket_id, timestamp, phone_number, user_name
   - device_type, device_brandmodel, device_additional_info
   - issue_type, problem_description, diagnostic_completed
   - parts_needed (comma-separated), estimated_cost, appointment_status
3. save_ticket_local() → tickets.json (backup)
4. sheets.add_ticket() → Google Sheets row (cloud sync)
```

**Sheet Structure:**

- Row 1: Headers (ticket_id, timestamp, phone_number, ...)
- Row 2+: Ticket data (auto-appended via gspread API)

---

## 📁 Dir Structure

```
ctrlfix/
├── dorm_doctor/               # Main package
│   ├── __init__.py
│   ├── cli.py                # Terminal interface + arrow key menus
│   ├── config.py             # Constants, API keys, ANSI colors
│   ├── color_utils.py        # Color formatting utilities
│   ├── flow_manager.py       # Core orchestration logic
│   ├── session.py            # State management
│   ├── dialogflow_client.py  # Dialogflow ES integration
│   ├── gemini_client.py      # Gemini API integration
│   ├── scraper_placeholder.py # SerpAPI Amazon scraper
│   ├── sheets_placeholder.py  # Google Sheets API client
│   ├── menu_utils.py         # Arrow key menu (Unix/Linux)
│   └── utils.py              # Phone validation, ticket saving
├── run.py                    # Entry point
├── requirements.txt          # Dependencies
├── .env                      # Environment variables (API keys)
├── tickets.json              # Local ticket backup
├── ctrlfix-479512-*.json     # Google service account credentials
└── README.md                 # This file
```

### File Functions

| File                     | Purpose                                                |
| ------------------------ | ------------------------------------------------------ |
| `cli.py`                 | Terminal UI, color output, menu navigation             |
| `flow_manager.py`        | Step orchestration, interrupt handling, NLP routing    |
| `session.py`             | User data storage, conversation history                |
| `dialogflow_client.py`   | Intent detection (greetings, pricing questions, etc.)  |
| `gemini_client.py`       | Entity extraction (device info, names), free-form chat |
| `scraper_placeholder.py` | Amazon price lookup via SerpAPI                        |
| `sheets_placeholder.py`  | Google Sheets ticket logging                           |
| `config.py`              | DiagnosticStep enum, ANSI colors, constants            |

---

## 🎨 UI/UX Design

### Terminal-Based Interface

- **Why Terminal?** Lightweight, easily deployable anywhere (local, SSH, Docker)
- **ANSI Color Coding:**
  - 🔵 Light Blue - Main text
  - 🩷 Pink - Numbers, prices
  - 💛 Yellow - Bot labels `[Bot]`
  - 💚 Green - Success messages (✓)
  - 🩵 Cyan - Diagnostic info
  - ⚪ White/Bold - Highlights
  - ⬜ Gray - Decorative lines

### Interactive Elements

- **Arrow Key Menus** - Unix/Linux terminal support for issue type & booking selection
- **Literal Input Steps** - Phone, name, description (no NLP = faster)
- **Progress Indicators** - Green checkmarks show completed steps
- **Inline Validation** - Immediate feedback for phone numbers

---

## 🛠️ Setup & Installation

### Prerequisites

- Python 3.8+
- Google Cloud Project with Dialogflow ES enabled
- Google Sheets API credentials
- Gemini API key
- SerpAPI key

### Installation

1. **Clone the repository:**

```bash
git clone https://github.com/yourusername/ctrlfix.git
cd ctrlfix
```

2. **Install dependencies:**

```bash
pip install -r requirements.txt
```

3. **Configure environment variables:**
   Create a `.env` file:

```env
GEMINI_API_KEY=your_gemini_api_key
SERPAPI_API_KEY=your_serpapi_key
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
```

4. **Add service account credentials:**

- Place `ctrlfix-479512-5181093c4568.json` (Dialogflow + Sheets) in repo root
- Place `ctrlfix-479512-6f3bedef216d.json` (Vertex AI) in repo root

5. **Configure Google Sheets:**

- Create a sheet named `ctrlfixrepairs`
- Share it with your service account email
- Update `config.py` if using different sheet name

### Running the Bot

**Interactive Mode:**

```bash
python run.py
```

**Demo Mode (pre-scripted):**

```bash
python run.py --demo
```

---

## 🔧 Configuration

### API Keys (`.env`)

- `GEMINI_API_KEY` - Get from [Google AI Studio](https://ai.google.dev/)
- `SERPAPI_API_KEY` - Get from [SerpAPI](https://serpapi.com/)

### Constants (`config.py`)

- `BASE_SERVICE_FEE` - Default diagnostic fee (HKD)
- `DROPOFF_ADDRESS` - Repair shop location
- `MECHANIC_CONTACT` - Phone number for booking
- `SHEETS_COLUMNS` - Google Sheets column structure

### Dialogflow Intents

Configure these intents in Dialogflow ES:

- `greeting` - "hello", "hi"
- `location.question` - "where are you based?"
- `pricing.question` - "how much does this cost?"
- `timeline.question` - "how long will it take?"
- `phone_number` - Extract phone numbers
- `devicetype` - Extract device types

---

## 📊 How It Works

### Diagnostic Flow Example

```
[Bot] Welcome to CtrlFix! Your ticket ID: C939324C
[Bot] What's your phone number?

You: 12345678
✓ Updated phone: +852 1234 5678

[Bot] What's your name?

You: John Doe
✓ User name: John Doe

[Bot] What type of device?

You: laptop
✓ Device type: laptop

[Bot] What's the brand and model?

You: my device is a sausage
[Bot] Haha, a sausage device? That's creative! 🌭
      But I need actual device info. What's your laptop brand/model?

You: ASUS ROG G614J
✓ Device: ASUS ROG G614J

[Bot] Additional info? (RAM, storage, etc.)

You: 16GB RAM, 512GB SSD
✓ Additional info: 16GB RAM, 512GB SSD

[Arrow Key Menu - Issue Type]
> Hardware (screen, battery, ports)
  Software (apps, OS, performance)
  Unsure

✓ Issue type: hardware

[Bot] Describe the problem:

You: Screen is flickering with pink lines. Started after I dropped it.
✓ Description saved (65 chars)

[Bot] Want a diagnostic session?

You: yes

[Gemini Diagnostic Mode - Interactive troubleshooting]
...

[Cost Estimation]
[PriceLookup] Searching Amazon: 'ASUS ROG G614J LCD Screen replacement'
[PriceLookup] Found 15 prices: $89.99 - $134.50 (avg: $108.23)
[PriceLookup] Estimated cost: $112.25 USD = $875.55 HKD

💰 COST ESTIMATION
Service Fee: HKD 100.00
Parts:
- LCD Screen: HKD 875.55
Total: HKD 975.55

[Arrow Key Menu - Booking]
> Instant drop-off service
  Contact mechanic first

✓ Booking: instant_dropoff

[Google Sheets Updated]
[Local Backup Saved]

[Bot] Thank you! Your ticket #C939324C is ready.
      Drop off at: Room 939a, Homantin Halls, Polyu
```

---

## 🌐 Future Enhancements

- [ ] Web interface (Flask/FastAPI + React)
- [ ] WhatsApp Business API integration
- [ ] Image upload for damage assessment
- [ ] Multi-language support (Cantonese, Mandarin)
- [ ] Payment gateway integration
- [ ] Warranty tracking system

---


## 📄 License

MIT License - See LICENSE file for details


---


