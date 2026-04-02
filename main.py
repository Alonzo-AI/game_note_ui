from typing import List, Optional, Any
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import pypdfium2 as pdfium
from retriever import get_answer, get_filter_options

app = FastAPI()

# Add CORS middleware to allow requests from the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the doc directory to serve PDFs
app.mount("/pdfs", StaticFiles(directory="doc"), name="pdfs")

class ChatRequest(BaseModel):
    message: str
    team_name: str
    opponent_team: Optional[str] = None
    opponent_name: Optional[str] = None
    game_date: Optional[str] = None



class ChatResponse(BaseModel):
    reply: str
    chunks: List[Any]

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        query_text = request.message.strip()
        team_name = request.team_name.strip()
        if not query_text:
            raise HTTPException(status_code=400, detail="message is required")
        if not team_name:
            raise HTTPException(status_code=400, detail="team_name is required")

        filters = {"team": team_name}
        opponent_value = request.opponent_name or request.opponent_team
        if opponent_value:
            filters["opponent_team"] = opponent_value
        if request.game_date:
            filters["game_date"] = request.game_date
            
        result = get_answer(query_text, filters=filters)
        print("render prompt",result["prompt"])
        return ChatResponse(reply=result["answer"], chunks=result["chunks"])
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/filter-options")
async def filter_options():
    try:
        return get_filter_options()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/pdf-info")
async def get_pdf_info(college: str, season: str, game_id: str):
    pdf_dir = os.path.join("doc", college, season)
    if not os.path.exists(pdf_dir):
        raise HTTPException(status_code=404, detail="College/Season directory not found")
    
    pdf_filename = f"{game_id}.pdf"
    pdf_path = os.path.join(pdf_dir, pdf_filename)
    
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF not found for this game")
    
    try:
        pdf = pdfium.PdfDocument(pdf_path)
        total_pages = len(pdf)
        pdf.close()
        return {"totalPages": total_pages, "pdfUrl": f"/pdfs/{college}/{season}/{pdf_filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {"message": "Game Note Bot API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8506)
