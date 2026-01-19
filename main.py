import csv
import random
import json
import os
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from groq import Groq
# Mevcut importların en tepede kalsın (import os zaten var)

# --- AYARLAR ---
# Bu satır şunu der: "Sunucudaysan sistemden anahtarı al, bilgisayardaysan buradaki yedeği kullan."
API_KEY = os.getenv("GOOGLE_API_KEY", "AIzaSyBUNM1UlYeuJvSpw6-OhdFAbGK3pPltMdU")
CSV_FILE = "soru_bankasi.csv"

client = genai.Client(api_key=API_KEY)

# ... Kodun geri kalanı aynen kalsın ...

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Frontend'den gelen veri modeli
class EvaluationRequest(BaseModel):
    question: str
    official_answer: str
    user_answer: str

# --- YARDIMCI FONKSİYONLAR ---
def get_random_question():
    questions = []
    if not os.path.exists(CSV_FILE):
        return {"Question": "Error: CSV not found", "Answer": "", "chapter": "System"}
    
    try:
        with open(CSV_FILE, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                questions.append(row)
        return random.choice(questions) if questions else None
    except Exception as e:
        return {"Question": f"Error reading CSV: {e}", "Answer": "", "chapter": "Error"}

# --- ENDPOINTS ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/question")
async def api_get_question():
    return get_random_question()

@app.post("/api/evaluate")
async def api_evaluate(data: EvaluationRequest):
    print(f"\n[HAM SES GİRİŞİ]: {data.user_answer}")
    
    # Boş ses kontrolü
    if not data.user_answer or len(data.user_answer.strip()) < 2:
        return JSONResponse(content={
            "corrected_text": "No speech detected.",
            "score_knowledge": 0, "score_english": 0, "score_sufficiency": 0,
            "summary": "No speech detected.", 
            "feedback": "Please check your microphone."
        })

    # Gemini'ye "Transcription Repair" görevi veriyoruz
    prompt = f"""
    You are a Senior Flight Examiner and Aviation Context Expert.
    The pilot candidate's answer comes from a basic Speech-to-Text engine and contains phonetic errors (e.g., "Tyga" instead of "TO/GA", "OEI" heard as "away", "V1" heard as "we one").
    
    Current Question: {data.question}
    Correct Answer Reference: {data.official_answer}
    Raw Transcript (With Errors): {data.user_answer}

    TASK:
    1. First, RECONSTRUCT the candidate's sentence by fixing aviation terminologies based on the context.
    2. Then, EVALUATE the reconstructed answer.

    Return ONLY a raw JSON object (no markdown) with this structure:
    {{
        "corrected_text": "The fully corrected version of the candidate's answer (Fix Tyga -> TO/GA etc.)",
        "score_knowledge": (integer 0-10),
        "score_english": (integer 0-10),
        "score_sufficiency": (integer 0-10),
        "summary": "One sentence summary of the correct answer",
        "feedback": "One sentence professional advice"
    }}
    """
    
    try:
        response = client.models.generate_content(model="gemini-flash-latest", contents=prompt)
        raw_text = response.text
        
        # Markdown temizliği
        cleaned_text = raw_text.replace("```json", "").replace("```", "").strip()
        
        result_json = json.loads(cleaned_text)
        print(f"[DÜZELTİLMİŞ METİN]: {result_json.get('corrected_text')}")
        return JSONResponse(content=result_json)

    except Exception as e:
        print(f"AI/JSON Hatası: {e}")
        return JSONResponse(content={
            "corrected_text": data.user_answer, # Düzeltilemediyse eskisini ver
            "score_knowledge": 0, "score_english": 0, "score_sufficiency": 0,
            "summary": "System Error", 
            "feedback": "Could not parse AI response. Please try again."
        })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
