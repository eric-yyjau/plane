from fastapi import FastAPI, Request
from pydantic import BaseModel
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Event Planning Plane Agent")

class WebhookPayload(BaseModel):
    action: str
    event_type: str
    data: dict

@app.post("/plane-webhook")
async def plane_webhook(payload: dict):
    """
    Endpoint to receive webhooks from Plane.
    Specifically listens for new Projects or Issues created.
    """
    logger.info(f"Received webhook payload: {payload}")
    
    # TODO: Filter for new project creations
    # TODO: Call LLM (Gemini) to generate tasks based on the event description
    # TODO: Push generated tasks back to Plane via its REST API
    
    return {"status": "success", "message": "Webhook received"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
