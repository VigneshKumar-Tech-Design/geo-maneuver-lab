from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .engine import simulate

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="GEO Maneuver Lab", version="0.1.0")

class Maneuver(BaseModel):
    type: Literal["prograde", "retrograde", "radial", "normal", "custom"] = "prograde"
    t_hours: float = Field(ge=0, description="Hours after the initial epoch")
    dv_ms: float = Field(1.0, ge=0, le=5000)
    dr: float = Field(0, ge=-5000, le=5000); dt: float = Field(0, ge=-5000, le=5000); dn: float = Field(0, ge=-5000, le=5000)

class SimRequest(BaseModel):
    name: str = "GEO-1"
    epoch: str = "2026-01-01T00:00:00"
    a_km: float = Field(42164.17, gt=6600, lt=500000)
    e: float = Field(0.0002, ge=0, lt=0.9)
    inc_deg: float = Field(0.05, ge=0, le=180)
    raan_deg: float = Field(0, ge=0, lt=360)
    argp_deg: float = Field(0, ge=0, lt=360)
    ref_lon_deg: float = Field(75, ge=-180, le=180)
    duration_h: float = Field(168, gt=0, le=24 * 60)
    step_s: float = Field(600, ge=10, le=86400)
    obs_lat_deg: float = Field(20, ge=-90, le=90)
    obs_lon_deg: float = Field(78, ge=-180, le=180)
    mu: float = Field(398600.4418, gt=0)
    model: Literal["two_body", "j2"] = "j2"
    maneuvers: list[Maneuver] = []

@app.get("/api/health")
def health(): return {"status": "ok", "version": app.version}

@app.get("/api/maneuver-types")
def types():
    return {"unit": "m/s, RTN frame (R radial, T along-track, N cross-track)", "types": {
        "prograde": "+T", "retrograde": "-T", "radial": "+R", "normal": "+N", "custom": "dr, dt, dn components"}}

@app.post("/api/simulate")
def run(req: SimRequest):
    c = req.model_dump()
    if c["duration_h"] * 3600 / c["step_s"] > 20000:
        raise HTTPException(422, "Too many samples: increase the step or shorten the duration (max 20000).")
    try: return simulate(c)
    except ValueError as ex: raise HTTPException(422, f"Invalid epoch or state: {ex}")

@app.get("/")
def index(): return FileResponse(STATIC / "index.html")
app.mount("/static", StaticFiles(directory=STATIC), name="static")