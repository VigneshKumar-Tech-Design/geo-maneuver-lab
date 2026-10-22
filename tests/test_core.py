import numpy as np
from fastapi.testclient import TestClient
from app.engine import *
from app.main import app

def cfg(**k):
    d = dict(epoch="2026-01-01T00:00:00", a_km=42164.17, e=0.0, inc_deg=0.0, raan_deg=0, argp_deg=0, ref_lon_deg=75, obs_lat_deg=20, obs_lon_deg=75,
             duration_h=48, step_s=600, mu=MU, model="two_body", maneuvers=[]); d.update(k); return d

def test_kep_roundtrip():
    r, v = kep2cart(30000, 0.1, 0.3, 1.0, 0.5, 0.7); el = elements(r[None], v[None])
    assert abs(el["a"][0] - 30000) < 1e-6 and abs(el["e"][0] - 0.1) < 1e-9 and abs(np.radians(el["i"][0]) - 0.3) < 1e-9

def test_geo_stays_on_slot():
    s = simulate(cfg())["man"]
    assert np.ptp(s["lon"]) < 0.05 and abs(s["lon"][0] - 75) < 1e-6

def test_energy_conserved_two_body():
    assert np.ptp(simulate(cfg())["man"]["a"]) < 1e-4

def test_prograde_raises_a_and_drifts_west():
    r = simulate(cfg(maneuvers=[dict(type="prograde", t_hours=1, dv_ms=2, dr=0, dt=0, dn=0)], duration_h=96))
    assert r["man"]["a"][-1] > r["base"]["a"][-1] + 10 and r["man"]["lon"][-1] < r["base"]["lon"][-1]

def test_normal_burn_tilts_plane():
    r = simulate(cfg(maneuvers=[dict(type="normal", t_hours=1, dv_ms=10, dr=0, dt=0, dn=0)]))
    assert r["man"]["i"][-1] > 0.1

def test_api_validation():
    c = TestClient(app); assert c.get("/api/health").json()["status"] == "ok"
    assert c.post("/api/simulate", json={"a_km": 100}).status_code == 422
