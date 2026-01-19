import csv
import random
import json
import os
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from groq import Groq  # <--- Google yerine Groq geldi

# --- AYARLAR ---
# Render'da Environment Variable olarak "GROQ_API_KEY" eklemeyi unutma!
API_KEY = os.getenv("GROQ_API_KEY", "BURAYA_GROQ_KEY_YAZABILIRSIN_AMA_RENDERDA_ENV_KULLAN")
CSV_FILE = "soru_bankasi.csv"

# Groq İstemcisi
client = Groq(api_key=API_KEY)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

class EvaluationRequest(BaseModel):
    question: str
    official_answer: str
    user_answer: str

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
        return {"Question": f"Error: {e}", "Answer": "", "chapter": "Error"}

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/question")
async def api_get_question():
    return get_random_question()

@app.post("/api/evaluate")
async def api_evaluate(data: EvaluationRequest):
    print(f"\n[HAM SES GİRİŞİ]: {data.user_answer}")
    
    if not data.user_answer or len(data.user_answer.strip()) < 2:
        return JSONResponse(content={
            "corrected_text": "No speech detected.",
            "score_knowledge": 0, "score_english": 0, "score_sufficiency": 0,
            "summary": "No speech detected.", 
            "feedback": "Please check your microphone."
        })

    # Groq (Llama 3) için Prompt
    system_prompt = "You are a Senior Flight Examiner. Return output ONLY in JSON format."
    
    user_prompt = f"""
    The pilot candidate's answer comes from a basic Speech-to-Text engine and contains errors (e.g., "Tyga" instead of "TO/GA").
    
    Question: {data.question}
    Correct Answer Ref: {data.official_answer}
    Raw Transcript: {data.user_answer}

    TASK:
    1. Fix aviation terminologies (Context Repair).
    2. Evaluate the answer (0-10).

    JSON SCHEMA:
    {{
        "corrected_text": "string",
        "score_knowledge": integer,
        "score_english": integer,
        "score_sufficiency": integer,
        "summary": "string",
        "feedback": "string"
    }}
    """
    
    try:
        completion = client.chat.completions.create(
            model="llama3-70b-8192", # Bu model çok zekidir
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0,
            response_format={"type": "json_object"} # JSON Modunu zorluyoruz
        )
        
        result_json = json.loads(completion.choices[0].message.content)
        print(f"[AI DÜZELTMESİ]: {result_json.get('corrected_text')}")
        return JSONResponse(content=result_json)

    except Exception as e:
        print(f"Groq API Hatası: {e}")
        return JSONResponse(content={
            "corrected_text": data.user_answer,
            "score_knowledge": 0, "score_english": 0, "score_sufficiency": 0,
            "summary": "System Error", 
            "feedback": "API Error. Please try again."
        })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
