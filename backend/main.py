import math
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from qdrant_client import QdrantClient, models
from fastembed import TextEmbedding
import logging
import requests
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="VibeWalk API", description="Safety-first navigation using Qdrant (NYC Edition)")

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Configuration ----------------
# NYC - Manhattan (Times Square / Penn Station area)
DEMO_CENTER_LAT = 40.7505
DEMO_CENTER_LNG = -73.9934
COLLECTION_NAME = "city_vibes_nyc"

# Initialize Qdrant Client (Auto-fallback to local mode if server is missing)
try:
    qdrant = QdrantClient(host="localhost", port=6333, timeout=1.0)
    qdrant.get_collections() # Test connection
    logger.info("Connected to Qdrant Server at localhost:6333")
except Exception as e:
    logger.warning("Qdrant Server not found. Using Local Embedded Mode (./qdrant_data).")
    qdrant = QdrantClient(path="./qdrant_data")

# Initialize Embedding Model (downloaded on first run)
logger.info("Loading FastEmbed model...")
embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
VECTOR_SIZE = 384
logger.info("FastEmbed model loaded.")

# Pre-compute concept vectors ONCE at startup (major optimization)
logger.info("Pre-computing concept vectors...")
DANGER_CONCEPT_VECTOR = list(embedding_model.embed(["Crime, assault, robbery, danger, dark, scary"]))[0].tolist()
VIBE_CONCEPT_VECTOR = list(embedding_model.embed(["Fun, delicious, beautiful, safe, happy"]))[0].tolist()
# DANGER_CONCEPT_VECTOR = [0.0] * VECTOR_SIZE
# VIBE_CONCEPT_VECTOR = [0.0] * VECTOR_SIZE
logger.info("Concept vectors cached.")

# ---------------- Models ----------------
class Point(BaseModel):
    lat: float
    lng: float

class RouteRequest(BaseModel):
    start: Point
    end: Point

class VibeReport(BaseModel):
    lat: float
    lng: float
    description: str
    type: str  # e.g., "crime", "review", "report"

class Recommendation(BaseModel):
    name: str
    description: str
    type: str

class RouteOption(BaseModel):
    id: str
    path: List[Point]
    safety_score: float
    tags: List[str]
    description: str
    recommendations: List[Recommendation]

# ---------------- Helpers ----------------
def get_vector(text: str) -> List[float]:
    """Generate vector for text using FastEmbed."""
    vectors = list(embedding_model.embed([text]))
    return vectors[0].tolist() # type: ignore
    # MOCKED FOR DEBUGGING
    # return [0.0] * VECTOR_SIZE

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in meters between two coordinates."""
    R = 6371000  # radius of Earth in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# ---------------- Startup & Seeding ----------------
@app.on_event("startup")
async def startup_event():
    # Check if collection exists
    try:
        collections = qdrant.get_collections()
        exists = any(c.name == COLLECTION_NAME for c in collections.collections)
    except Exception:
        exists = False # Robustness

    if not exists:
        logger.info(f"Creating collection '{COLLECTION_NAME}'...")
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(size=VECTOR_SIZE, distance=models.Distance.COSINE),
        )
        # Hybrid Seeding
        await seed_nyc_data()
    else:
        logger.info(f"Collection '{COLLECTION_NAME}' already exists.")

async def seed_nyc_data():
    points = []
    
    # 1. REAL NYC Crime Data (Socrata API)
    try:
        data_url = "https://data.cityofnewyork.us/resource/5uac-w243.json?$limit=300&$where=latitude IS NOT NULL"
        logger.info(f"Fetching real crime data from {data_url}...")
        response = requests.get(data_url)
        crime_data = response.json()
        
        for record in crime_data:
            desc = record.get("pd_desc", "Unspecified Crime")
            lat = float(record["latitude"])
            lng = float(record["longitude"])
            
            # Simple spatial filter for Manhattan Demo Area (approx) to keep vector search readable
            if 40.70 < lat < 40.80 and -74.02 < lng < -73.95:
                points.append({
                    "text": f"Crime Report: {desc}",
                    "type": "crime",
                    "lat": lat,
                    "lng": lng
                })
        logger.info(f"Processed {len(points)} real crime records for demo area.")
        
    except Exception as e:
        logger.error(f"Failed to fetch real crime data: {e}")
    
    # 2. Mock Reviews (For Recommendations)
    # Times Sq / Penn Station Area
    reviews = [
        # Positive
        {"text": "Joe's Pizza - Best slice in NY! Felt super safe and busy.", "type": "review", "lat": 40.7305, "lng": -74.0021, "name": "Joe's Pizza"},
        {"text": "Bryant Park - Lovely place to sit and have coffee. Security is visible.", "type": "review", "lat": 40.7536, "lng": -73.9832, "name": "Bryant Park"},
        {"text": "MOMA - Amazing art, very secure entrance and clean area.", "type": "review", "lat": 40.7614, "lng": -73.9776, "name": "MOMA"},
        {"text": "High Line - Beautiful walk, filled with tourists and families.", "type": "review", "lat": 40.7480, "lng": -74.0048, "name": "The High Line"},

        # Negative / Safety Warnings
        {"text": "Subway Station Entrance - A bit sketchy at night, saw some fights.", "type": "review", "lat": 40.7505, "lng": -73.9934, "name": "Subway Entrance"},
        {"text": "Dark alley behavior near 8th Ave, avoid alone.", "type": "review", "lat": 40.7550, "lng": -73.9920, "name": "8th Ave Corner"},
    ]
    
    points.extend(reviews)
    
    # Batch Upsert
    upsert_points = []
    for i, p in enumerate(points):
        vector = get_vector(p["text"])
        payload = {
            "text": p["text"], 
            "type": p["type"], 
            "location": {"lat": p["lat"], "lon": p["lng"]}
        }
        if "name" in p:
            payload["name"] = p["name"]
            
        upsert_points.append(
            models.PointStruct(
                id=i,
                vector=vector,
                payload=payload
            )
        )
        
        if len(upsert_points) >= 100:
            qdrant.upsert(collection_name=COLLECTION_NAME, points=upsert_points)
            upsert_points = []
            
    if upsert_points:
        qdrant.upsert(collection_name=COLLECTION_NAME, points=upsert_points)
        
    logger.info(f"Seeding Complete. Total Vibe Nodes: {len(points)}")

def fetch_osrm_route(start: Point, end: Point, profile: str = "foot") -> List[Point]:
    """Fetches a real route from OSRM (OpenStreetMap Routing Machine)."""
    # OSRM uses (lng, lat) order
    url = f"https://router.project-osrm.org/route/v1/{profile}/{start.lng},{start.lat};{end.lng},{end.lat}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "false"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        if data.get("code") == "Ok" and data.get("routes"):
            coords = data["routes"][0]["geometry"]["coordinates"]
            # OSRM returns [lng, lat], convert to Point(lat, lng)
            return [Point(lat=c[1], lng=c[0]) for c in coords]
    except Exception as e:
        logger.error(f"OSRM routing failed: {e}")
    return []

def generate_real_paths(start: Point, end: Point) -> List[List[Point]]:
    """Generates 3 real walking routes using OSRM with waypoints."""
    paths = []
    
    # 1. Direct walking route
    direct = fetch_osrm_route(start, end, "foot")
    if direct:
        paths.append(direct)
    
    # 2. Alternate route (via a waypoint slightly north)
    offset = 0.003  # ~300m
    waypoint_north = Point(lat=(start.lat + end.lat) / 2 + offset, lng=(start.lng + end.lng) / 2)
    alt1_a = fetch_osrm_route(start, waypoint_north, "foot")
    alt1_b = fetch_osrm_route(waypoint_north, end, "foot")
    if alt1_a and alt1_b:
        paths.append(alt1_a + alt1_b[1:])  # Avoid duplicate point
    
    # 3. Alternate route (via a waypoint slightly south)
    waypoint_south = Point(lat=(start.lat + end.lat) / 2 - offset, lng=(start.lng + end.lng) / 2)
    alt2_a = fetch_osrm_route(start, waypoint_south, "foot")
    alt2_b = fetch_osrm_route(waypoint_south, end, "foot")
    if alt2_a and alt2_b:
        paths.append(alt2_a + alt2_b[1:])
    
    # Fallback to at least one path if API fails
    if not paths:
        logger.warning("OSRM failed, using fallback straight line")
        paths.append([start, end])
    
    return paths



def score_route(path: List[Point]) -> dict:
    """Scores route and finds recommendations. OPTIMIZED: samples 10 points max."""
    
    total_danger_score = 0
    hit_count = 0
    detected_tags = []
    recommendations = []
    
    # Use cached concept vectors (no per-request embedding!)
    danger_query = DANGER_CONCEPT_VECTOR
    vibe_query = VIBE_CONCEPT_VECTOR

    # OPTIMIZATION: Sample only 10 evenly-spaced points (instead of 50-200+)
    sample_count = min(10, len(path))
    step = max(1, len(path) // sample_count)
    sampled_points = [path[i] for i in range(0, len(path), step)][:sample_count]
    
    logger.debug(f"Scoring route: {len(path)} points, sampling {len(sampled_points)}")

    # Sample points along path
    for p in sampled_points:
        # 1. Check Danger
        danger_hits = qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=danger_query,
            limit=2,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="location",
                        geo_radius=models.GeoRadius(center=models.GeoPoint(lat=p.lat, lon=p.lng), radius=150.0)
                    )
                ]
            )
        ).points
        
        for hit in danger_hits:
            # Lower threshold even more (0.60) to ensure reports hit hard
            if hit.score > 0.60:
                total_danger_score += hit.score
                hit_count += 1
                logger.info(f"Danger hit: score={hit.score:.2f}, text={hit.payload.get('text', '')[:50]}")
                tag = hit.payload.get("text", "").split(":")[0] # e.g. "Crime Report"
                if len(tag) < 30 and tag not in detected_tags:
                    detected_tags.append(tag)

        # 2. Check Recommendations (Positive Vibes)
        # Only if we haven't found too many already
        if len(recommendations) < 2:
            rec_hits = qdrant.query_points(
                collection_name=COLLECTION_NAME,
                query=vibe_query,
                limit=1,
                query_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="location",
                            geo_radius=models.GeoRadius(center=models.GeoPoint(lat=p.lat, lon=p.lng), radius=100.0)
                        ),
                        models.FieldCondition(key="type", match=models.MatchValue(value="review"))
                    ]
                )
            ).points
            for hit in rec_hits:
                if hit.score > 0.75: # It's a positive vibe
                    name = hit.payload.get("name", "Unknown Spot")
                    desc = hit.payload.get("text", "")
                    # Deduplicate 
                    if not any(r["name"] == name for r in recommendations):
                        recommendations.append({"name": name, "description": desc, "type": "place"})

    # Scoring Logic
    # 0 hits = 10/10. 
    # High danger hits lower the score.
    
    # Increased penalty multiplier to make reports significantly impact score
    penalty = total_danger_score * 4.0 
    final_score = max(1.0, min(10.0, 10.0 - penalty))
    
    return {
        "score": final_score, 
        "tags": detected_tags[:4],
        "recommendations": recommendations
    }

# ---------------- Endpoints ----------------
@app.get("/routes", response_model=List[RouteOption])
async def get_routes(start_lat: float, start_lng: float, end_lat: float, end_lng: float):
    start = Point(lat=start_lat, lng=start_lng)
    end = Point(lat=end_lat, lng=end_lng)
    
    paths = generate_real_paths(start, end)
    
    response = []
    descriptions = ["Direct Walking Route", "North Alternate", "South Alternate"]
    
    for i, path in enumerate(paths):
        analysis = score_route(path)
        
        response.append(RouteOption(
            id=f"route-{i}",
            path=path,
            safety_score=round(analysis["score"], 1),
            tags=analysis["tags"],
            description=descriptions[i],
            recommendations=analysis["recommendations"]
        ))
        
    return response

@app.post("/report")
async def report_vibe(report: VibeReport):
    """Evolving Memory: User reports a new vibe node."""
    vector = get_vector(report.description)
    import uuid
    import datetime
    point_id = str(uuid.uuid4())
    timestamp = datetime.datetime.now().isoformat()
    
    qdrant.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            models.PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "text": report.description,
                    "type": report.type,
                    "location": {"lat": report.lat, "lon": report.lng},
                    "source": "user_report",
                    "timestamp": timestamp,
                    "severity": "high" # Assume user reports are significant
                }
            )
        ]
    )
    logger.info(f"Report added: '{report.description}' at ({report.lat}, {report.lng})")
    return {"status": "success", "message": "Vibe memory updated. Search again to see impact.", "location": {"lat": report.lat, "lng": report.lng}}

@app.get("/nearby-vibes")
async def get_nearby_vibes(lat: float, lng: float, radius: float = 200.0):
    """Returns all vibe nodes (crimes, reviews, reports) near a location."""
    try:
        # Use scroll to get all points matching the filter
        results, _ = qdrant.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="location",
                        geo_radius=models.GeoRadius(
                            center=models.GeoPoint(lat=lat, lon=lng),
                            radius=radius
                        )
                    )
                ]
            ),
            limit=20
        )
        
        vibes = []
        for point in results:
            vibes.append({
                "id": str(point.id),
                "text": point.payload.get("text", ""),
                "type": point.payload.get("type", "unknown"),
                "source": point.payload.get("source", "seeded"),
                "name": point.payload.get("name", None),
                "timestamp": point.payload.get("timestamp", None),
                "location": point.payload.get("location", {})
            })
        
        logger.info(f"Found {len(vibes)} vibes near ({lat}, {lng})")
        return {"vibes": vibes, "count": len(vibes)}
    except Exception as e:
        logger.error(f"Error fetching nearby vibes: {e}")
        return {"vibes": [], "count": 0, "error": str(e)}

@app.get("/")
def read_root():
    return {"status": "VibeWalk NYC Backend Online", "source": "NYC Open Data + Qdrant"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


