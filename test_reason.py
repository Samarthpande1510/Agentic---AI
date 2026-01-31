import time
from agent import observer_node, reasoner_node

def run_live_test():
    # 1. Start with an empty base state
    state = {
        "latest_logs": [],
        "metrics": {},
        "current_hypothesis": "Starting live test...",
        "reasoning_log": [],
        "is_anomaly_detected": False,
        "history": []
    }

    print("🛰️ Connecting to live stream...")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            # STEP A: OBSERVE
            # Grabs the last 50 transactions from transactions.log
            obs_update = observer_node(state)
            state.update(obs_update)
            
            # STEP B: REASON (Only if we have data)
            if state["metrics"].get("total_count", 0) > 0:
                print(f"📊 [OBSERVER] Success Rate: {state['metrics']['global_success_rate']:.2%}")
                print(f"🔍 [OBSERVER] Clusters: {state['metrics']['failure_clusters']}")
                
                res_update = reasoner_node(state)
                state.update(res_update)
                
                # STEP C: PRINT RESULTS
                print(f"🧠 [REASONER] Hypothesis: {state['current_hypothesis']}")
                print(f"🚨 [REASONER] Anomaly Detected: {state['is_anomaly_detected']}")
                print(f"📜 [TRACE] {state['reasoning_log'][-1]}")
            else:
                print("⏳ Waiting for simulator data...")

            print("-" * 50)
            time.sleep(5) # Run the brain every 5 seconds

    except KeyboardInterrupt:
        print("\nStopping live test.")

if __name__ == "__main__":
    run_live_test()