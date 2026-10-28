from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
import os, json, sqlite3, uuid, datetime, httpx
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from fastapi.responses import Response

load_dotenv()
DB_PATH = os.getenv("DATABASE_PATH", "travel_planner.db")
app = FastAPI(title="Personalized Travel Itinerary Planner", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

class TripRequest(BaseModel):
    destination: str = Field(min_length=2, max_length=100)
    start_date: str
    days: int = Field(ge=1, le=14)
    budget: float = Field(gt=0, le=1000000)
    currency: str = "USD"
    travel_style: str = "Balanced"
    party: str = "Solo"
    interests: list[str] = []
    pace: str = "Balanced"
    notes: str = ""

class SwapRequest(BaseModel):
    trip: TripRequest
    day: int = 1
    activity_index: int = 0
    preference: str = "something different"

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.execute("""create table if not exists trips (
          id text primary key, created_at text not null, destination text not null,
          start_date text, days integer, budget real, preferences text, itinerary text
        )""")
init_db()

def demo_itinerary(req: TripRequest):
    interest = req.interests or ["local highlights", "food"]
    places = [
        ("Old Town & local market", "09:00", "Walk through historic lanes and browse local crafts.", 18),
        ("Signature local lunch", "12:30", "Try a well-reviewed regional dish at a casual local spot.", 22),
        ("Scenic viewpoint", "15:00", "Take a relaxed route to a scenic overlook and enjoy the views.", 12),
        ("Dinner near the centre", "19:00", "Finish with a memorable meal close to your evening stop.", 30),
        ("Museum or cultural landmark", "10:00", "Explore the destination's history and cultural highlights.", 16),
        ("Park and neighbourhood café", "13:00", "Slow down with a green-space stroll and a coffee break.", 15),
        ("Local experience", "16:00", "Choose a hands-on or guided experience related to your interests.", 28),
    ]
    itinerary = []
    for day in range(1, req.days + 1):
        items = []
        for j in range(3):
            p = places[(day * 2 + j) % len(places)]
            items.append({"time": p[1], "title": p[0], "description": p[2],
                          "category": ["Sightseeing", "Food", "Experience"][j],
                          "cost": round(p[3] * (1.25 if req.travel_style == "Luxury" else 1), 2),
                          "duration": ["1.5 hours", "1 hour", "2 hours"][j]})
        itinerary.append({"day": day, "title": ["Explore and get oriented", "Culture, flavours and views", "Local favourites and hidden gems"][((day-1) % 3)],
                          "summary": f"A {req.pace.lower()} day shaped around {', '.join(interest[:2])}. Keep travel between stops short where possible.",
                          "activities": items})
    return itinerary

async def ai_itinerary(req: TripRequest):
    provider = os.getenv("AI_PROVIDER", "demo").lower()
    prompt = f"""Create a practical {req.days}-day itinerary for {req.destination}. Start date: {req.start_date}.
Budget total: {req.currency} {req.budget}; party: {req.party}; style: {req.travel_style}; pace: {req.pace};
interests: {', '.join(req.interests)}; notes: {req.notes}.
Return ONLY valid JSON array with one object per day: day (number), title, summary, activities (3-4 objects with time, title, description, category, cost (number), duration). Be realistic, group nearby places, keep costs within budget, do not claim live opening hours or availability."""
    if provider == "gemini" and os.getenv("GEMINI_API_KEY"):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{os.getenv('GEMINI_MODEL','gemini-2.5-flash')}:generateContent?key={os.getenv('GEMINI_API_KEY')}"
        async with httpx.AsyncClient(timeout=45) as client:
            r = await client.post(url, json={"contents":[{"parts":[{"text":prompt}]}],
                "generationConfig":{"responseMimeType":"application/json","temperature":0.5}})
            r.raise_for_status()
            raw = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(raw)
    if provider == "groq" and os.getenv("GROQ_API_KEY"):
        async with httpx.AsyncClient(timeout=45) as client:
            r = await client.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}"},
                json={"model":os.getenv("GROQ_MODEL","llama-3.3-70b-versatile"),
                      "messages":[{"role":"system","content":"Return only valid JSON."},{"role":"user","content":prompt}],
                      "temperature":0.5, "response_format":{"type":"json_object"}})
            r.raise_for_status()
            raw = r.json()["choices"][0]["message"]["content"]
            data = json.loads(raw)
            return data.get("itinerary", data) if isinstance(data, dict) else data
    return demo_itinerary(req)

@app.get("/api/health")
def health():
    return {"status":"ok", "ai_provider":os.getenv("AI_PROVIDER","demo"), "mode":"live AI" if os.getenv("AI_PROVIDER","demo") in ("gemini","groq") else "demo"}

@app.post("/api/itinerary")
async def generate(req: TripRequest):
    try:
        itinerary = await ai_itinerary(req)
        if isinstance(itinerary, dict):
            itinerary = itinerary.get("itinerary", [])
        if not isinstance(itinerary, list) or not itinerary:
            raise ValueError("AI returned an empty itinerary")
        total = sum(float(a.get("cost", 0) or 0) for d in itinerary for a in d.get("activities", []))
        return {"id":str(uuid.uuid4()), "destination":req.destination, "start_date":req.start_date,
                "days":req.days, "budget":req.budget, "currency":req.currency,
                "estimated_cost":round(total,2), "itinerary":itinerary, "mode":os.getenv("AI_PROVIDER","demo")}
    except Exception as exc:
        # Avoid exposing secrets/provider response details to clients.
        raise HTTPException(status_code=502, detail="Could not generate itinerary. Check your AI provider settings and try again.") from exc

@app.post("/api/trips")
def save_trip(payload: dict):
    required = ["id", "destination", "itinerary"]
    if any(k not in payload for k in required):
        raise HTTPException(status_code=400, detail="Trip id, destination, and itinerary are required")
    prefs = {k:payload.get(k) for k in ["start_date","days","budget","currency"]}
    with db() as con:
        con.execute("insert or replace into trips values (?,?,?,?,?,?,?,?)", (
            payload["id"], datetime.datetime.now(datetime.timezone.utc).isoformat(),
            payload["destination"], payload.get("start_date"), payload.get("days",1),
            payload.get("budget",0), json.dumps(prefs), json.dumps(payload["itinerary"])))
    return {"saved":True, "id":payload["id"]}

@app.get("/api/trips")
def list_trips():
    with db() as con:
        rows = con.execute("select * from trips order by created_at desc limit 50").fetchall()
    return [{"id":r["id"],"created_at":r["created_at"],"destination":r["destination"],
             "start_date":r["start_date"],"days":r["days"],"budget":r["budget"],
             "preferences":json.loads(r["preferences"] or "{}"),"itinerary":json.loads(r["itinerary"] or "[]")}
            for r in rows]

@app.post("/api/swap")
async def swap_activity(body: SwapRequest):
    try:
        itinerary = await ai_itinerary(body.trip)
        idx = max(0, min(body.day - 1, len(itinerary)-1))
        acts = itinerary[idx].get("activities", [])
        if acts:
            old = acts[max(0,min(body.activity_index,len(acts)-1))]
            old["title"] = f"Alternative: {body.preference}"
            old["description"] = f"Try a different {body.preference} experience in {body.trip.destination}. Verify local details before visiting."
        return {"itinerary":itinerary}
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not swap activity.") from exc

@app.get("/api/trips/{trip_id}/pdf")
def export_pdf(trip_id: str):
    with db() as con:
        row = con.execute("select * from trips where id=?", (trip_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Save this trip before exporting its PDF.")
    trip = {"destination":row["destination"],"start_date":row["start_date"],
            "days":row["days"],"budget":row["budget"],"itinerary":json.loads(row["itinerary"])}
    from io import BytesIO
    buff = BytesIO()
    doc = SimpleDocTemplate(buff, pagesize=A4, rightMargin=42,leftMargin=42,topMargin=42,bottomMargin=42)
    styles = getSampleStyleSheet()
    story = [Paragraph("Personalized Travel Itinerary", styles["Title"]),
             Paragraph(f"{trip['destination']} · {trip['start_date'] or ''} · {trip['days']} days", styles["Heading2"]),
             Paragraph(f"Budget: {trip['budget']}", styles["Normal"]), Spacer(1,16)]
    for day in trip["itinerary"]:
        story.append(Paragraph(f"Day {day.get('day','')} — {day.get('title','')}", styles["Heading2"]))
        story.append(Paragraph(day.get("summary",""), styles["Normal"]))
        for a in day.get("activities",[]):
            story.append(Paragraph(f"{a.get('time','')} | {a.get('title','')} — {a.get('description','')} (est. {a.get('cost',0)})", styles["BodyText"]))
            story.append(Spacer(1,5))
        story.append(Spacer(1,10))
    doc.build(story)
    return Response(buff.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition":f'attachment; filename="itinerary-{trip_id[:8]}.pdf"'})
