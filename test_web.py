import requests
import time
import json

BASE_URL = "http://127.0.0.1:8000"
THREAD_ID = f"test_session_{int(time.time())}" # Unique ID every run

def print_step(step, msg):
    print(f"\n🔹 [STEP {step}] {msg}")

def run_test():
    print(f"🚀 Starting Backend Test (Thread ID: {THREAD_ID})")
    
    # --- STEP 1: KICK THE AGENT ---
    print_step(1, "Triggering Agent Cycle (/run_cycle)...")
    payload = {"thread_id": THREAD_ID}
    
    try:
        response = requests.post(f"{BASE_URL}/run_cycle", json=payload)
        response.raise_for_status()
        data = response.json()
        
        # Print logs to see what the agent thought
        print("   📝 Agent Logs:")
        for log in data.get("logs", []):
            print(f"      {log}")
            
    except Exception as e:
        print(f"   ❌ Error running cycle: {e}")
        return

    # --- STEP 2: CHECK IF PAUSED ---
    print_step(2, "Checking Agent State (/agent_state)...")
    
    # We poll because sometimes the server finishes fast, sometimes slow
    # But for this simple test, one check is usually enough
    response = requests.get(f"{BASE_URL}/agent_state", params={"thread_id": THREAD_ID})
    state_data = response.json()
    
    status = state_data.get("status")
    print(f"   🕵️ Current Status: {status}")
    
    if status != "WAITING_FOR_APPROVAL":
        print("   ⚠️ Agent did NOT pause. It likely thinks the system is healthy.")
        print("      -> Check your Simulator weights! Needs more failures.")
        return

    proposal = state_data.get("proposal")
    print(f"   ✋ Action Required! Agent wants to: {proposal}")

    # --- STEP 3: APPROVE THE ACTION ---
    print_step(3, "Approving Action (/approve_action)...")
    
    approval_payload = {
        "thread_id": THREAD_ID,
        "approved": True
    }
    
    response = requests.post(f"{BASE_URL}/approve_action", json=approval_payload)
    result = response.json()
    
    print(f"   ✅ Approval Response: {result['status']}")
    print("   📝 Final Execution Logs:")
    for log in result.get("logs", []):
        print(f"      {log}")

    print("\n🎉 TEST COMPLETE: System successfully detected failure, paused, and executed fix.")

if __name__ == "__main__":
    run_test()