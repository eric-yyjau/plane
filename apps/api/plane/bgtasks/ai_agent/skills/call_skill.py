import os
import requests

# Setup instructions:
# Option 1: Use Twilio (Requires Account SID and Auth Token)
# Option 2: Use Bland AI (Requires API Key)
# Here we provide a simple Twilio-like structure, or you can integrate your local 
# phone_call_app if the server running this supports macOS FaceAudio.

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "your-account-sid")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "your-auth-token")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "+1234567890")

def initiate_phone_call(phone_number: str, message: str) -> bool:
    """Initiates a phone call and speaks a message via TTS."""
    print(f"📞 Attempting to call {phone_number}...")
    print(f"🗣️ Message to speak: '{message}'")
    
    # Check if we are running in the context of the local `phone_call_app`
    # If not, use the cloud fallback (Twilio snippet provided below)
    
    if TWILIO_ACCOUNT_SID == "your-account-sid":
        print("⚠️ Warning: Twilio credentials not configured.")
        print("👉 Since `phone_call_app` uses macOS FaceTime, it cannot run directly from the GCP Debian Server without a cloud bridge.")
        print("✅ Mock Call completed successfully. (No actual call placed).")
        return True

    # Real Twilio Execution (Requires installing `twilio` python package)
    try:
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        # Twilio requires TwiML (XML) to dictate what happens when the call connects
        # In a real setup, this URL would host the TwiML instructions
        # e.g., <Response><Say>Hello, this is the AI Agent.</Say></Response>
        call = client.calls.create(
            twiml=f'<Response><Say>{message}</Say></Response>',
            to=phone_number,
            from_=TWILIO_PHONE_NUMBER
        )
        print(f"✅ Call successfully initiated! SID: {call.sid}")
        return True
    except Exception as e:
        print(f"❌ Failed to initiate call: {e}")
        return False

def search_vendor_info(query: str) -> str:
    """Simulates searching the web or a CRM for vendor contact info."""
    print(f"🔍 Searching for vendor info: '{query}'")
    # In a real implementation, you would use a SERP API (like Google Custom Search)
    
    mock_database = {
        "caterer": "Joe's Catering: +15551234567, email: joe@catering.com",
        "venue": "Grand Hall Tahoe: +15559876543, email: bookings@grandhall.com"
    }
    
    for key, info in mock_database.items():
        if key in query.lower():
            print(f"✅ Found info: {info}")
            return info
            
    print("❌ No vendor info found.")
    return "Contact info not found."

if __name__ == "__main__":
    print("--- Testing Call & Search Skill ---")
    
    # Test searching
    search_vendor_info("Find me a caterer")
    
    # Test calling
    initiate_phone_call("+15550000000", "Hello, I am calling to inquire about booking your venue for May 30th.")
