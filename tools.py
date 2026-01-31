import json
from langchain_core.tools import tool

@tool
def update_routing_tool(region: str, gateway: str):
    """
    Reroutes payment traffic for a specific region to a target gateway.
    Args:
        region: The geographical region (e.g., 'UK', 'US', 'EU', 'IN', 'global_default').
        gateway: The provider to use (e.g., 'stripe', 'adyen').
    """

    config_file = "routing_config.json"
    
    # 1. Read existing
    with open(config_file, "r") as f:
        config = json.load(f)
    
    # 2. Update
    if region == "global_default":
        config["global_default"] = gateway
    else:
        config[region] = gateway
        
    # 3. Save
    with open(config_file, "w") as f:
        json.dump(config, f, indent=4)
        
    return f"ACTION SUCCESS: {region} is now routed to {gateway}."