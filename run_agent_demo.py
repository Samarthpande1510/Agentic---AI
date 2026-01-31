import time
from agent import app

# Thread ID keeps the session state in memory
config = {"configurable": {"thread_id": "hackathon_demo"}}

print("🤖 Payment Ops Agent Started. Monitoring 'transactions.log'...")

while True:
    print("\n--- NEW CYCLE ---")
    
    # 1. Run the Graph (Input: Empty log list just to trigger the start)
    # This runs Observer -> Reasoner -> Decider -> (Pause?)
    for event in app.stream({"reasoning_log": []}, config=config):
        for node, update in event.items():
            if "reasoning_log" in update:
                # Print the last log entry from the node
                print(f"[{node.upper()}] {update['reasoning_log'][-1]}")

    # 2. Check if we are paused (The "Human Check")
    snapshot = app.get_state(config)
    
    # If the next step is 'executor', we are paused!
    if snapshot.next and "executor" in snapshot.next:
        proposal = snapshot.values.get('decision_args')
        
        print(f"\n✋ APPROVAL REQUIRED: Agent wants to run 'update_routing'")
        print(f"   ARGS: {proposal}")
        
        choice = input("   👉 Approve? (y/n): ")
        
        if choice.lower() == "y":
            print("   ✅ User Approved. Executing change...")
            # Resume graph with None (proceeds to Executor)
            for event in app.stream(None, config=config):
                for node, update in event.items():
                    print(f"[{node.upper()}] {update['reasoning_log'][-1]}")
        else:
            print("   ❌ User Rejected. Cancelling action...")
            # HACK: We inject a state update to clear the 'next_action' 
            # so the graph doesn't get stuck trying to execute in the next loop.
            app.update_state(config, {"next_action": "MONITOR"}) 
            
    else:
        print("   ✅ Cycle complete. No manual approval needed.")

    # Wait 5 seconds before checking logs again
    time.sleep(5)