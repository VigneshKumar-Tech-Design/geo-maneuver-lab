# GEO Maneuver Lab (Phase 1 + 2 core)

    pip install -r requirements.txt
    uvicorn app.main:app --reload      # open http://127.0.0.1:8000
    pytest

Plotly.js loads from a CDN (needs internet in the browser). All astrodynamics runs in Python (`app/engine.py`).

**Implemented:** GEO initialisation at a slot longitude; two-body and J2 propagation (DOP853, rtol 1e-11); impulsive prograde/retrograde/radial/normal/custom RTN burns, multiple per run; ECI/ECEF; geodetic ground track with wrap handling; longitude, drift rate, orbital elements, period, P–Q, residuals vs a no-maneuver baseline; time slider/play/step; CSV and JSON export; Pydantic validation; `/api/simulate`, `/api/maneuver-types`, `/api/health`.

**Not yet implemented:** Cartesian input, TLE/SGP4, third-body/SRP/drag, finite-duration thrust, EW/NS station-keeping and relocation wizards, `/api/compare`, `/api/analyze-stationkeeping`, maneuver detection, textured Earth.

**Assumptions:** GMST-only ECI→ECEF (no precession/nutation/polar motion, error of order km at GEO — adequate for visualisation, not for operations); spherical Earth surface in 3D; J2 is the only perturbation, so real N–S/E–W drift from the Sun, Moon and Earth's tesseral terms is not reproduced.
