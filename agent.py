import os, json, operator
from typing import Annotated, List, Union, TypedDict, Optional

from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from tools import update_routing_tool
from langgraph.graph import StateGraph, END

from dotenv import load_dotenv

load_dotenv()

# Add .strip() to remove any invisible spaces or newlines
api_key = os.getenv("GROQ_API_KEY")
if api_key:
    os.environ["GROQ_API_KEY"] = api_key.strip()

llm = ChatOpenAI(
    model="meta-llama/llama-4-maverick-17b-128e-instruct", 
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1", 
    temperature=0.5
)


class PaymentAgentState(TypedDict):
    latest_logs: List[dict]
    metrics: dict
    current_hypothesis: str
    is_anomaly_detected: bool
    next_action: Optional[str]
    decision_args: Optional[str]
    reasoning_log: Annotated[List[str], operator.add]
    
    # ADD THIS: Long-term memory of executed actions
    action_history: Annotated[List[str], operator.add]

# 2. The Checkpointer (The 'Pause' Button Logic)
# MemorySaver allows the graph to 'freeze' and wait for human input
# without losing its place in the loop.
checkpointer = MemorySaver()

# 3. File System Defaults
ROUTING_CONFIG_FILE = "routing_config.json"
DEFAULT_CONFIG = {
    "US": "stripe",
    "UK": "stripe",
    "IN": "stripe",
    "EU": "adyen",
    "global_default": "stripe"
}

# Ensure baseline config exists
if not os.path.exists(ROUTING_CONFIG_FILE):
    with open(ROUTING_CONFIG_FILE, "w") as f:
        json.dump(DEFAULT_CONFIG, f, indent=4)

# 4. Graph Export Helper (For the Mermaid live map in Streamlit)
def get_graph_diagram(compiled_graph):
    """Returns a Mermaid-compatible string to render the graph in UI."""
    return compiled_graph.get_graph().draw_mermaid()

def observer_node(state: PaymentAgentState):
    log_file = "transactions.log"
    recent_txs = []
    
    # Initialize the return dictionary with defaults to prevent KeyErrors
    output = {
        "latest_logs": [],
        "metrics": {"global_success_rate": 1.0, "failure_clusters": {}, "total_count": 0},
        "reasoning_log": [],
        "current_hypothesis": "Monitoring..."
    }

    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            lines = f.readlines()[-50:]
            for line in lines:
                if not line.strip(): continue # Skip empty lines
                try:
                    # Robust split: Find the first '{' and take everything from there
                    json_start = line.find('{')
                    if json_start != -1:
                        json_str = line[json_start:]
                        recent_txs.append(json.loads(json_str))
                except Exception as e:
                    continue

    if not recent_txs:
        output["reasoning_log"] = ["Observer: No valid JSON transactions found in log yet."]
        return output

    # --- Calculation Logic ---
    total = len(recent_txs)
    successes = len([t for t in recent_txs if t['status'] == 'SUCCESS'])
    
    failure_map = {}
    for t in recent_txs:
        if t['status'] == 'FAILED':
            # Use .get() to avoid KeyErrors if some logs are missing fields
            key = f"{t.get('region','UNK')}_{t.get('gateway','UNK')}_{t.get('error_code','00')}"
            failure_map[key] = failure_map.get(key, 0) + 1

    output["latest_logs"] = recent_txs
    output["metrics"] = {
        "global_success_rate": successes / total,
        "failure_clusters": failure_map,
        "total_count": total
    }
    output["reasoning_log"] = [f"Observer: Successfully parsed {total} transactions."]
    
    return output

def reasoner_node(state: PaymentAgentState):
    """
    Node 2: The LLM analyzes clusters to form a hypothesis.
    """
    metrics = state.get("metrics", {})
    clusters = metrics.get('failure_clusters', {})
    
    # Construct a clear snapshot for the LLM
    cluster_summary = json.dumps(clusters, indent=2)

    prompt = f"""
    You are a Senior Payment Operations Manager. 
    Analyze the following failure clusters observed in the last 50 transactions:
    
    DATA:
    {cluster_summary}
    
    GLOBAL SUCCESS RATE: {metrics.get('global_success_rate', 0):.2%}
    
    TASK:
    1. Determine if a specific "Targeted Incident" is occurring.
    2. A cluster is an incident if it has a high count (e.g., > 5) for a specific Region/Gateway/Error.
    3. Identify the Root Cause.
    4. If no clear pattern exists, label it as "Normal Noise".
    
    OUTPUT FORMAT:
    Hypothesis: <Your finding>
    Confidence: <0-100%>
    Anomaly Detected: <Yes/No>
    """

    # Call the LLM
    response = llm.invoke([
        SystemMessage(content="You analyze fintech logs for patterns."),
        HumanMessage(content=prompt)
    ])
    
    # Parse the LLM response (we can use simple string parsing for now)
    content = response.content
    is_anomaly = "Anomaly Detected: Yes" in content
    
    # Extract the hypothesis line for the UI
    hypothesis = "Monitoring..."
    for line in content.split("\n"):
        if line.startswith("Hypothesis:"):
            hypothesis = line.replace("Hypothesis:", "").strip()

    return {
        "current_hypothesis": hypothesis,
        "is_anomaly_detected": is_anomaly,
        "reasoning_log": [f"Reasoner: Analyzed clusters. Hypothesis: {hypothesis}"]
    }


def decider_node(state: PaymentAgentState):
    """Decides to call a tool OR alert the human."""
    hypothesis = state['current_hypothesis']
    history = state.get('action_history', [])

    if not state['is_anomaly_detected']:
        return {"next_action": "MONITOR", "reasoning_log": ["Decider: No action needed."]}

    prompt = f"""
    Hypothesis: {hypothesis}
    Past Actions Taken: {json.dumps(history[-5:])} (Last 5 actions)
    
    - If a specific region is failing, call 'update_routing'.
    - CHECK PAST ACTIONS: If you already rerouted this region recently, do not do it again unless necessary.
    """

    llm_with_tools = llm.bind_tools([update_routing_tool])
    response = llm_with_tools.invoke(prompt)
    
    if response.tool_calls:
        tool_call = response.tool_calls[0]
        return {
            "next_action": "update_routing",
            "decision_args": json.dumps(tool_call['args']),
            "reasoning_log": [f"Decider: Proposed {tool_call['name']} with {tool_call['args']}"]
        }
    
    return {"next_action": "ALERT_HUMAN", "reasoning_log": ["Decider: Alerting Human (No auto-fix)."]}


def executor_node(state: PaymentAgentState):
    """Executes the tool and saves the action to history."""
    args = json.loads(state['decision_args'])
    result = update_routing_tool.invoke(args)
    
    # Create a timestamped record
    action_record = f"ACTION TAKEN: update_routing with {args} | RESULT: {result}"
    
    return {
        "reasoning_log": [f"Executor: {result}"],
        "action_history": [action_record] 
    }

workflow = StateGraph(PaymentAgentState)
workflow.add_node("observer", observer_node)
workflow.add_node("reasoner", reasoner_node)
workflow.add_node("decider", decider_node)
workflow.add_node("executor", executor_node)

workflow.set_entry_point("observer")
workflow.add_edge("observer", "reasoner")
workflow.add_edge("reasoner", "decider")

def route_decision(state):
    if state.get("next_action") == "update_routing":
        return "executor"
    return END

workflow.add_conditional_edges(
    "decider",          # Start Node
    route_decision,     # Logic Function
    {                   # The Map: { "Return Value": "Target Node" }
        "executor": "executor",
        END: END
    }
)
workflow.add_edge("executor", END)

checkpointer = MemorySaver()
app = workflow.compile(checkpointer=checkpointer, interrupt_before=["executor"])


