"""Flask + SocketIO web server for CtrlFix Terminal
Wraps the existing flow_manager for web deployment with xterm.js frontend.
"""
from flask import Flask, render_template, session
from flask_socketio import SocketIO, emit
from dorm_doctor.flow_manager import FlowManager
from dorm_doctor.config import DiagnosticStep, ISSUE_TYPE_OPTIONS, BOOKING_OPTIONS, Colors
import uuid
import os
import sys
from io import StringIO

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Store active sessions in memory (single-user or low-traffic deployment)
sessions = {}


class DiagnosticCapture:
    """Capture print statements for diagnostic logging to web terminal"""
    def __init__(self, socket_emit_func):
        self.emit = socket_emit_func
        self.original_stdout = sys.stdout
        
    def write(self, text):
        # Send to original stdout (server logs)
        self.original_stdout.write(text)
        
        # Also send diagnostic info to web terminal
        if text.strip() and ('[' in text or '✓' in text or '✗' in text):
            # This is a diagnostic message
            self.emit('diagnostic', {'text': text.strip()})
    
    def flush(self):
        self.original_stdout.flush()


@app.route('/')
def index():
    """Serve the xterm.js terminal interface"""
    return render_template('terminal.html')


@socketio.on('connect')
def handle_connect():
    """Initialize new session when client connects"""
    session_id = str(uuid.uuid4())
    session['sid'] = session_id
    
    # Create new flow manager for this session
    sessions[session_id] = {
        'flow': FlowManager(),
        'current_step': None
    }
    
    print(f"{Colors.GREEN}[WebSocket] New session connected: {session_id[:8]}...{Colors.RESET}")
    
    # Start the diagnostic flow
    flow = sessions[session_id]['flow']
    result = flow.start()
    sessions[session_id]['current_step'] = flow.session.get_step()
    
    # Send welcome message to client
    emit('output', {
        'text': result['message'],
        'needs_input': result.get('needs_input', True)
    })


@socketio.on('disconnect')
def handle_disconnect():
    """Clean up session when client disconnects"""
    session_id = session.get('sid')
    if session_id and session_id in sessions:
        print(f"[WebSocket] Session disconnected: {session_id}")
        del sessions[session_id]


@socketio.on('input')
def handle_input(data):
    """Process user input from terminal"""
    session_id = session.get('sid')
    user_input = data.get('text', '').strip()
    
    # Validate session
    if not session_id or session_id not in sessions:
        emit('output', {
            'text': '\n⚠️  Session expired. Please refresh the page to start over.',
            'needs_input': False
        })
        return
    
    session_data = sessions[session_id]
    flow = session_data['flow']
    current_step = flow.session.get_step()
    
    # Log with color (shows in server console)
    print(f"{Colors.GRAY}[Input] {session_id[:8]}... | Step {current_step} | {user_input[:50]}{Colors.RESET}")
    
    # Send diagnostic to web terminal
    emit('diagnostic', {'text': f"[Step {current_step}] Processing input..."})
    
    # Check if this is a menu step
    if current_step == DiagnosticStep.ISSUE_TYPE:
        if user_input.isdigit():
            choice = int(user_input) - 1
            if 0 <= choice < len(ISSUE_TYPE_OPTIONS):
                user_input = str(choice)
    elif current_step == DiagnosticStep.FINAL_BOOKING:
        if user_input.isdigit():
            choice = int(user_input) - 1
            if 0 <= choice < len(BOOKING_OPTIONS):
                user_input = str(choice)
    
    # Capture stdout to intercept diagnostic prints
    import sys
    from io import StringIO
    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()
    
    try:
        # Process the input through flow manager
        result = flow.process_input(user_input)
        session_data['current_step'] = flow.session.get_step()
        
        # Get captured diagnostic output
        diagnostic_logs = captured_output.getvalue()
        
        # Restore stdout
        sys.stdout = old_stdout
        
        # Send diagnostic logs to web terminal (with colors preserved as HTML)
        if diagnostic_logs.strip():
            # Convert ANSI codes to HTML colors for web terminal
            colored_html = _ansi_to_html(diagnostic_logs.strip())
            # Also print to server console with original colors
            print(diagnostic_logs.strip())
            emit('diagnostic', {'text': colored_html})
        
        # Strip ANSI color codes from main message for web terminal
        import re
        clean_message = re.sub(r'\x1b\[[0-9;]*m', '', result['message'])
        
        # Send response back to client
        emit('output', {
            'text': clean_message,
            'needs_input': result.get('needs_input', True),
            'completed': result.get('completed', False)
        })
        
        # If flow is completed, clean up session
        if result.get('completed'):
            print(f"{Colors.GREEN}[WebSocket] Session completed: {session_id[:8]}...{Colors.RESET}")
            del sessions[session_id]
    
    except Exception as e:
        # Restore stdout on error
        sys.stdout = old_stdout
        print(f"{Colors.RED}[Error] {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        emit('output', {
            'text': f"\n❌ Error processing request: {str(e)}",
            'needs_input': False
        })


@socketio.on('ping')
def handle_ping():
    """Keep-alive ping from client"""
    emit('pong')


def _ansi_to_html(text):
    """Convert ANSI color codes to HTML span tags for web terminal display"""
    import re
    
    # ANSI to HTML color mapping
    color_map = {
        '30': 'color: #000000',  # Black
        '31': 'color: #ff6b6b',  # Red
        '32': 'color: #51cf66',  # Green
        '33': 'color: #ffd43b',  # Yellow
        '34': 'color: #74c0fc',  # Blue
        '35': 'color: #f783ac',  # Pink/Magenta
        '36': 'color: #4dabf7',  # Cyan
        '37': 'color: #e9ecef',  # White
        '90': 'color: #868e96',  # Gray
        '91': 'color: #ff6b6b',  # Bright Red
        '92': 'color: #51cf66',  # Bright Green
        '93': 'color: #ffd43b',  # Bright Yellow
        '94': 'color: #74c0fc',  # Bright Blue
        '95': 'color: #f783ac',  # Bright Magenta
        '96': 'color: #4dabf7',  # Bright Cyan
        '97': 'color: #f8f9fa',  # Bright White
        '1': 'font-weight: bold',  # Bold
    }
    
    # Replace ANSI codes with HTML spans
    def replace_ansi(match):
        codes = match.group(1).split(';')
        if '0' in codes or not codes[0]:  # Reset
            return '</span>'
        
        styles = []
        for code in codes:
            if code in color_map:
                styles.append(color_map[code])
        
        if styles:
            return f'<span style="{"; ".join(styles)}">'
        return ''
    
    # Convert ANSI escape sequences
    html = re.sub(r'\x1b\[([0-9;]*)m', replace_ansi, text)
    
    # Additional coloring for specific patterns if no ANSI codes present
    if '\x1b[' not in text:
        # Color [Gemini], [PriceLookup], etc. in cyan
        html = re.sub(r'\[([A-Za-z]+(?:\([^)]+\))?)\]', r'<span style="color: #4dabf7">[\1]</span>', html)
        # Color "Press Enter" type instructions in yellow
        html = re.sub(r'(Press Enter|Type|press Enter|Enter to continue)', r'<span style="color: #ffd43b">\1</span>', html, flags=re.IGNORECASE)
    
    # Close any remaining open spans
    open_spans = html.count('<span') - html.count('</span>')
    html += '</span>' * open_spans
    
    return html


if __name__ == '__main__':
    print("=" * 60)
    print("  CtrlFix Web Terminal Server")
    print("=" * 60)
    print("  Starting Flask + SocketIO server...")
    print(f"  Local: http://localhost:5000")
    print("=" * 60)
    
    # Run with eventlet for WebSocket support
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
