import time
from agent import PaymentAgentState, observer_node # Import your logic

def run_test():
    # 1. Setup a fresh dummy state
    state: PaymentAgentState = {
        "latest_logs": [],
        "metrics": {},
        "current_hypothesis": "Initial state",
        "reasoning_log": [],
        "next_action": None,
        "is_anomaly_detected": False,
        "history": []
    }

    print("🚀 Starting Observer Test...")
    print("Watching 'transactions.log' for 5 iterations...\n")

    for i in range(5):
        # 2. Call the node function manually
        update = observer_node(state)
        
        # 3. Apply the update to our local state
        state.update(update)
        # Note: reasoning_log is a list, so in a real graph it appends. 
        # Here we just check the latest entry.
        
        metrics = state.get("metrics", {})
        log_entry = state["reasoning_log"][-1]

        print(f"--- Iteration {i+1} ---")
        print(f"📊 Metrics: {metrics}")
        print(f"🧠 Thought: {log_entry}")
        
        if metrics.get("total_count", 0) > 0:
            print("✅ Success: Data ingested and clusters calculated.")
        else:
            print("⚠️ Warning: No logs found yet. Is the simulator running?")
        
        print("-" * 30)
        time.sleep(2) # Wait for more data to be generated

if __name__ == "__main__":
    run_test()