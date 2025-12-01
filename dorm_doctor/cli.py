"""Command-line entry for DormDoctorDiagnostics"""
import argparse
from dorm_doctor.flow_manager import FlowManager
from dorm_doctor.menu_utils import show_menu
from dorm_doctor.config import DiagnosticStep, ISSUE_TYPE_OPTIONS, BOOKING_OPTIONS, Colors


def run_interactive():
    """Run interactive CLI chatbot."""
    print(Colors.highlight("=" * 60))
    print(Colors.highlight("  DormDoctorDiagnostics - Interactive Mode"))
    print(Colors.highlight("=" * 60))
    print(Colors.LIGHT_BLUE + "Type your responses and press Enter." + Colors.RESET)
    print(Colors.LIGHT_BLUE + "You can ask questions at any time - I'll handle interrupts!" + Colors.RESET)
    print(Colors.highlight("=" * 60))
    print()
    
    flow = FlowManager()
    
    # start of flow
    result = flow.start()
    print(Colors.bot(result["message"]))
    
    # Main conversation loop
    while not result.get("completed", False):
        if result.get("needs_input", True):
            current_step = flow.session.get_step()
            
            # Special handling for menu-based steps
            if current_step == DiagnosticStep.ISSUE_TYPE:
                # Show arrow key menu for issue type
                choice_idx = show_menu("What type of issue are you experiencing?", ISSUE_TYPE_OPTIONS)
                user_input = str(choice_idx)
            elif current_step == DiagnosticStep.FINAL_BOOKING:
                # Show arrow key menu for booking type
                choice_idx = show_menu("How would you like to proceed?", BOOKING_OPTIONS)
                user_input = str(choice_idx)
            else:
                # Regular text input
                user_input = input(f"\n{Colors.user('')}").strip()
                if not user_input:
                    # Empty input, just continue (some steps use Enter to proceed)
                    user_input = "continue"
            
            result = flow.process_input(user_input)
            print(f"\n{Colors.bot(result['message'])}")
        else:
            # No input needed, but flow not complete - shouldn't happen
            break
    
    print("\n" + Colors.highlight("=" * 60))
    print(Colors.highlight("  Session complete!"))
    print(Colors.highlight("=" * 60))


def run_demo():
    """Run non-interactive demo with pre-scripted responses."""
    print("=" * 60)
    print("  DormDoctorDiagnostics - Demo Mode")
    print("=" * 60)
    print("Simulating a complete diagnostic session...")
    print("=" * 60)
    print()
    
    flow = FlowManager()
    
    # Pre-scripted demo inputs
    demo_inputs = [
        "",  # Welcome - just press enter
        "+852 1234 5678",  # Phone number
        "ASUS ROG Laptop G614J with 16GB RAM and RTX 3060",  # Device info
        "2",  # Issue type - hardware
        "Screen is flickering and showing pink lines. Started after I dropped it yesterday.",  # Description
        "yes",  # Has photos
        "",  # Continue to cost estimation
        "yes",  # Feedback - yes it helped
        "1",  # Book appointment
    ]
    
    result = flow.start()
    print(f"Bot: {result['message']}\n")
    
    for demo_input in demo_inputs:
        if result.get("completed", False):
            break
        
        if result.get("needs_input", True):
            print(f"[Demo Input]: {demo_input if demo_input else '[Enter]'}")
            result = flow.process_input(demo_input if demo_input else "continue")
            print(f"\nBot: {result['message']}\n")
            print("-" * 60)
    
    print("\n" + "=" * 60)
    print("  Demo complete!")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="DormDoctorDiagnostics - AI-powered repair assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py              Run interactive mode
  python run.py --demo       Run demo with pre-scripted inputs
  python run.py --help       Show this help message
        """
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run demo conversation (non-interactive with pre-scripted inputs)"
    )
    args = parser.parse_args()

    if args.demo:
        run_demo()
    else:
        run_interactive()


if __name__ == "__main__":
    main()
