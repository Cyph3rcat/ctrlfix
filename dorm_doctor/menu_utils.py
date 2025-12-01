"""Menu utilities for Linux-style arrow key navigation
Provides interactive menu selection with arrow keys and Enter to confirm.
"""
import sys
import tty
import termios


def show_menu(title, options):
    """Display an interactive menu with arrow key navigation.
    
    Args:
        title: Menu title/prompt to display
        options: List of option strings
        
    Returns:
        int: Index of selected option (0-based)
        
    Usage:
        options = ["Software", "Hardware", "Unsure"]
        choice = show_menu("Select issue type:", options)
        # Returns 0, 1, or 2
    """
    selected = 0
    
    def print_menu():
        """Print menu with current selection highlighted."""
        print("\n" + title)
        print("━" * 50)
        for i, option in enumerate(options):
            if i == selected:
                print(f"  → {option}  ← ")
            else:
                print(f"    {option}")
        print("━" * 50)
        print("Use ↑/↓ arrow keys to navigate, Enter to select\n")
    
    def get_key():
        """Read a single keypress."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
            # Handle arrow keys (escape sequences)
            if ch == '\x1b':  # ESC
                ch = sys.stdin.read(2)
                if ch == '[A':  # Up arrow
                    return 'up'
                elif ch == '[B':  # Down arrow
                    return 'down'
            elif ch == '\r' or ch == '\n':  # Enter
                return 'enter'
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    
    # Clear screen and show initial menu
    print("\033[2J\033[H", end="")  # Clear screen, move cursor to top
    print_menu()
    
    while True:
        key = get_key()
        
        if key == 'up':
            selected = (selected - 1) % len(options)
            print("\033[2J\033[H", end="")  # Clear and redraw
            print_menu()
        elif key == 'down':
            selected = (selected + 1) % len(options)
            print("\033[2J\033[H", end="")  # Clear and redraw
            print_menu()
        elif key == 'enter':
            # Clear the menu display
            print("\033[2J\033[H", end="")
            print(f"\n✓ Selected: {options[selected]}\n")
            return selected


def show_yes_no_menu(question):
    """Show a yes/no menu.
    
    Args:
        question: Question to ask
        
    Returns:
        bool: True if yes, False if no
    """
    choice = show_menu(question, ["Yes", "No"])
    return choice == 0
