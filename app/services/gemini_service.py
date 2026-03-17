import google.generativeai as genai
from app.core.config import settings

class GeminiService:
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.MODEL_NAME)

    async def generate_response(self, prompt: str) -> str:
        response = self.model.generate_content(prompt)
        return response.text

gemini_service = GeminiService()
