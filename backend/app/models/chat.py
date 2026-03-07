from pydantic import BaseModel, Field
from typing import List, Optional

class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's input message")
    context: Optional[dict] = Field(default=None, description="Optional context like current market state selected by user")

class ChatResponse(BaseModel):
    message: str = Field(..., description="The AI's response text")
    intent_detected: str = Field(..., description="The classification of the user's intent")
    is_warning: bool = Field(default=False, description="Whether the response contains a critical risk warning")
    metadata: Optional[dict] = Field(default=None, description="Extra structured data like probabilistic arrays or risk metrics")
