import time
import random
import json
import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone

# --- CONFIGURATION ---
LOG_FILE = "transactions.log"
CONFIG_FILE = "routing_config.json"
MAX_BYTES = 5 * 1024 * 1024  # 5MB limit
BACKUP_COUNT = 1

# Setup the Rotating Logger
logger = logging.getLogger("PaymentSimulator")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT)
logger.addHandler(handler)

# Initial/Default Routing Configuration
DEFAULT_CONFIG = {
    "US": "stripe",
    "UK": "stripe",
    "IN": "stripe",
    "EU": "adyen",
    "global_default": "stripe"
}

# --- UNTOUCHED GATEWAY PROFILES ---
GATEWAY_PROFILES = {
    "stripe": {"avg_latency": 150},
    "adyen": {"avg_latency": 310}
}

def get_routing_config():
    """Reads the current routing setup. If file doesn't exist, creates it."""
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f)
        return DEFAULT_CONFIG
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def generate_transaction(scenario="normal"):
    # Load current configuration to see where traffic is being routed
    config = get_routing_config()
    region = random.choice(["US", "UK", "IN", "EU"])
    
    # DYNAMIC GATEWAY PICKER: Uses agent's preferred gateway for this region
    gateway = config.get(region, config.get("global_default", "stripe"))
    
    profile = GATEWAY_PROFILES[gateway]
    
    status = "SUCCESS"
    error_code = "00"
    latency = profile["avg_latency"] + random.randint(-20, 50)

    # --- YOUR SCENARIO LOGIC (UNTOUCHED) ---
    if scenario == "uk_bank_outage" and region == "UK" and gateway == "stripe":
        if random.random() > 0.3:
            status = "FAILED"
            error_code = "91"

    elif scenario == "adyen_latency_spike" and gateway == "adyen":
        status = "SUCCESS"
        latency = random.randint(5000, 9000)

    elif scenario == "india_auth_bug" and region == "IN" and gateway == "stripe":
        status = "FAILED"
        error_code = "401"

    elif random.random() < 0.02:
        status = "FAILED"
        error_code = random.choice(["51", "05"])
    # --- END OF YOUR LOGIC ---

    return {
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "transaction_id": f"tx_{random.getrandbits(24)}",
        "gateway": gateway,
        "region": region,
        "status": status,
        "error_code": error_code,
        "latency_ms": latency,
        "amount": round(random.uniform(5.0, 500.0), 2)
    }

def main():
    print(f"📡 Simulator started. Listening to {CONFIG_FILE}")
    scenarios = ["normal", "uk_bank_outage", "adyen_latency_spike", "india_auth_bug"]

    try:
        while True:
            current_mode = random.choices(
                scenarios, 
                weights=[0.1, 0.9, 0, 0],
                k=1
            )[0]

            tx = generate_transaction(scenario=current_mode)
            
            # Log the JSON for the LangGraph Agent
            logger.info(json.dumps(tx))

            # Visual Feedback
            status_color = "\033[92m" if tx["status"] == "SUCCESS" else "\033[91m"
            if tx["latency_ms"] > 1000: status_color = "\033[93m"
            
            print(f"{status_color}[{current_mode.upper()}] {tx['region']} | {tx['gateway']} | {tx['status']} | {tx['latency_ms']}ms\033[0m")
            
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nSimulation stopped.")

if __name__ == "__main__":
    main()