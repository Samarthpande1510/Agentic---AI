import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

# Import your LangGraph app
# Make sure agent_graph.py is in the same directory
from agent import app 

# --- SETUP ---
api = FastAPI(title="Payment Agent Backend")

# Allow React (localhost:3000) to talk to Python (localhost:8000)
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For hackathon, allow all. In prod, specify ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DATA MODELS ---
# These define what the Frontend sends to us
class AgentRequest(BaseModel):
    thread_id: str = "demo_session_1"

class ApprovalRequest(BaseModel):
    thread_id: str
    approved: bool

# --- HELPER FUNCTIONS ---
def get_config(thread_id: str):
    return {"configurable": {"thread_id": thread_id}}

def parse_logs(event_stream) -> List[str]:
    """Helper to extract clean strings from LangGraph events"""
    logs = []
    for event in event_stream:
        for node, update in event.items():
            if "reasoning_log" in update:
                # Format: "[NODE_NAME] The log message"
                entry = f"[{node.upper()}] {update['reasoning_log'][-1]}"
                logs.append(entry)
    return logs

# --- ENDPOINTS ---

@api.get("/")
def health_check():
    return {"status": "Agent is online"}

@api.post("/run_cycle")
async def run_cycle(req: AgentRequest):
    """
    Triggers the agent to look at logs and think.
    Returns the 'Thought Trace' logs.
    """
    config = get_config(req.thread_id)
    
    # Run the graph (it will stop automatically if it hits 'interrupt')
    # We pass an empty reasoning_log to kickstart the state if it's new
    try:
        iterator = app.stream({"reasoning_log": []}, config=config)
        logs = parse_logs(iterator)
        return {"logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api.get("/agent_state")
async def get_agent_state(thread_id: str = "demo_session_1"):
    config = get_config(thread_id)
    snapshot = app.get_state(config)
    
    # NEW: Check for 'sentry' instead of 'executor'
    if snapshot.next and "sentry" in snapshot.next:
        proposal_json = snapshot.values.get("decision_args")
        # Let the frontend know which tool is being used
        tool_name = snapshot.values.get("next_action") 
        
        return {
            "status": "WAITING_FOR_APPROVAL",
            "proposal": proposal_json,
            "tool": tool_name
        }
    
    return {"status": "IDLE", "proposal": None}


@api.post("/approve_action")
async def approve_action(req: ApprovalRequest):
    """
    User clicks 'Approve' or 'Reject' in UI.
    """
    config = get_config(req.thread_id)
    
    if req.approved:
        # RESUME: Pass None to continue from the pause point
        iterator = app.stream(None, config=config)
        logs = parse_logs(iterator)
        return {"status": "EXECUTED", "logs": logs}
    else:
        # REJECT: Modify state to cancel the action so the graph doesn't get stuck
        app.update_state(config, {"next_action": "MONITOR"}) 
        return {"status": "REJECTED", "logs": ["User rejected the proposal. Action cancelled."]}

# --- RUNNER ---
if __name__ == "__main__":
    uvicorn.run(api, host="127.0.0.1", port=8000)
