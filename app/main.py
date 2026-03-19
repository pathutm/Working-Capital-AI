from fastapi import FastAPI, HTTPException
from app.services.ai_logic_service import ai_logic_service
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Working Capital AI API")

# Add CORS middleware to allow requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from typing import List, Optional

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []

@app.get("/")
async def root():
    return {"message": "Welcome to Working Capital AI API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        # Convert Pydantic models to dicts for the service
        history_dicts = [{"role": m.role, "content": m.content} for m in (request.history or [])]
        response = await ai_logic_service.process_chat(request.message, history_dicts)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
