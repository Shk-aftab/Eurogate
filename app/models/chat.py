# app/models/chat.py
from pydantic import BaseModel
from typing import List, Dict, Any, Optional # Keep these for potential future use

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    response: str
    # Optional: Add source information later if needed
    # sources: Optional[List[Dict[str, Any]]] = None

# Ensure there are no other imports or code below this that might cause issues