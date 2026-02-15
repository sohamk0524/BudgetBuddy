Role: Full-Stack Engineer (Python/Flask & SwiftUI).
Context: I am building "BudgetBuddy." I have an existing Flask app.py that currently uses email/password. I want to switch to a phone-number-only SMS Authentication flow for my App Store launch.
Task 1: Backend (Flask) Please refactor my app.py to remove email/password logic and implement:
POST /v1/send_sms_code: Generates a 6-digit code, saves it to the database (with a 5-minute expiry), and uses a placeholder function send_via_twilio(phone, code) to simulate sending the SMS.
POST /v1/verify_code: Checks the code. If valid and not expired, it returns a token (the user_id) and a hasProfile boolean. If the phone number is new, it should create a new User record automatically.
Task 2: Frontend (SwiftUI) Refactor the provided LoginView.swift into a state-machine architecture:
ViewModel: An AuthenticationViewModel that tracks AuthState (.enterPhone, .verifyOTP, .authenticated).
Networking: Ensure URLSession uses an ephemeral configuration to force HTTP/1.1 for the iOS Simulator.
Views:
EnterPhoneView: Styled like BudgetBuddy (wallet icon, accent colors). Uses PhoneNumberKit for E.164 formatting.
OTPView: A 6-digit entry screen that auto-submits.
HomeView: Must include a "Delete Account" button (for App Store compliance).
Constraints:
Keep using my existing SQLAlchemy db instance.
Use the phone number as the unique identifier for the User model.
Maintain the current onboarding and chat logic to work with the new user_id (token).

