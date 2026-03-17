from fastapi import FastAPI, HTTPException
from app.services.gemini_service import gemini_service
from pydantic import BaseModel

app = FastAPI(title="Working Capital AI API")

class ChatRequest(BaseModel):
    message: str

@app.get("/")
async def root():
    return {"message": "Welcome to Working Capital AI API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        response = await gemini_service.generate_response(request.message)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
