"""Color utility functions for pretty terminal output"""
from dorm_doctor.config import Colors


def print_success(message):
    """Print success message in green with checkmark"""
    print(Colors.success(message))


def print_error(message):
    """Print error message in red with X"""
    print(Colors.error(message))


def print_info(message):
    """Print info message in light blue"""
    print(f"{Colors.LIGHT_BLUE}{message}{Colors.RESET}")


def print_diagnostic(message):
    """Print diagnostic info in cyan"""
    print(Colors.diagnostic(message))


def print_bot_label(message):
    """Print bot label in yellow"""
    print(f"{Colors.YELLOW}{message}{Colors.RESET}")


def format_number(value):
    """Format number in pink"""
    return Colors.number(value)


def format_currency(amount, currency="HKD"):
    """Format currency amount with pink number"""
    return f"{currency} {Colors.number(f'{amount:.2f}')}"
