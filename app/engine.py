"""Numerical engine. Units: km, s, rad internally; degrees and m/s at the API boundary."""
import numpy as np
from datetime import datetime, timezone
from scipy.integrate import solve_ivp

MU = 398600.4418; RE = 6378.137; J2 = 1.08262668e-3
WE = 7.2921150e-5; FL = 1 / 298.257223563

def gmst_deg(epoch: str) -> float:
    d = datetime.fromisoformat(epoch.replace("Z", ""))
    jd = 2440587.5 + d.replace(tzinfo=timezone.utc).timestamp() / 86400
    return (280.46061837 + 360.98564736629 * (jd - 2451545.0)) % 360

def kep2cart(a, e, i, raan, w, nu, mu=MU):
    p = a * (1 - e * e); r = p / (1 + e * np.cos(nu))
    rp = np.array([r * np.cos(nu), r * np.sin(nu), 0.0])
    vp = np.sqrt(mu / p) * np.array([-np.sin(nu), e + np.cos(nu), 0.0])
    def R3(x): c, s = np.cos(x), np.sin(x); return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    def R1(x): c, s = np.cos(x), np.sin(x); return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    Q = R3(raan) @ R1(i) @ R3(w)
    return Q @ rp, Q @ vp

def elements(r, v, mu=MU):
    """Vectorised Cartesian -> a, e, i, RAAN, period and the inclination vector (P,Q).
    P,Q come from the angular-momentum vector, so they stay well defined at i ~ 0."""
    rn = np.linalg.norm(r, axis=1); vn2 = (v * v).sum(1)
    h = np.cross(r, v); hn = np.linalg.norm(h, axis=1)
    ev = np.cross(v, h) / mu - r / rn[:, None]
    a = 1 / (2 / rn - vn2 / mu)
    return dict(a=a, e=np.linalg.norm(ev, axis=1),
                i=np.degrees(np.arccos(np.clip(h[:, 2] / hn, -1, 1))),
                raan=np.degrees(np.arctan2(h[:, 0], -h[:, 1])) % 360,
                period_h=2 * np.pi * np.sqrt(a ** 3 / mu) / 3600,
                P=h[:, 0] / (hn + h[:, 2]), Q=-h[:, 1] / (hn + h[:, 2]))

def eci2ecef(r, t, gmst0):
    th = np.radians(gmst0) + WE * t; c, s = np.cos(th), np.sin(th)
    return np.stack([c * r[:, 0] + s * r[:, 1], -s * r[:, 0] + c * r[:, 1], r[:, 2]], 1)

def ecef2geodetic(r):
    x, y, z = r.T; e2 = FL * (2 - FL); lon = np.degrees(np.arctan2(y, x)); p = np.hypot(x, y)
    lat = np.arctan2(z, p * (1 - e2))
    for _ in range(6):
        N = RE / np.sqrt(1 - e2 * np.sin(lat) ** 2); lat = np.arctan2(z + e2 * N * np.sin(lat), p)
    N = RE / np.sqrt(1 - e2 * np.sin(lat) ** 2)
    return lon, np.degrees(lat), p / np.cos(lat) - N

def azel(re, lat_deg, lon_deg, h_km=0.0):
    """Topocentric azimuth/elevation (deg) of ECEF positions `re` (N,3) seen from a ground site."""
    la, lo = np.radians(lat_deg), np.radians(lon_deg); e2 = FL * (2 - FL)
    Nn = RE / np.sqrt(1 - e2 * np.sin(la) ** 2)
    obs = np.array([(Nn + h_km) * np.cos(la) * np.cos(lo), (Nn + h_km) * np.cos(la) * np.sin(lo),
                    (Nn * (1 - e2) + h_km) * np.sin(la)])
    d = re - obs
    E = d @ np.array([-np.sin(lo), np.cos(lo), 0])
    N = d @ np.array([-np.sin(la) * np.cos(lo), -np.sin(la) * np.sin(lo), np.cos(la)])
    U = d @ np.array([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])
    return np.degrees(np.arctan2(E, N)) % 360, np.degrees(np.arcsin(U / np.linalg.norm(d, axis=1)))

def accel(_t, y, mu, j2):
    r = y[:3]; rn = np.linalg.norm(r); a = -mu * r / rn ** 3
    if j2:
        k = 1.5 * J2 * mu * RE ** 2 / rn ** 5; z2 = (r[2] / rn) ** 2
        a = a - k * np.array([r[0] * (1 - 5 * z2), r[1] * (1 - 5 * z2), r[2] * (3 - 5 * z2)])
    return np.concatenate([y[3:], a])

def maneuver_dv(m, y):
    """Impulse in the RTN frame: R radial, N = h/|h| cross-track, T = N x R along-track (m/s -> km/s)."""
    R = y[:3] / np.linalg.norm(y[:3]); h = np.cross(y[:3], y[3:]); N = h / np.linalg.norm(h); T = np.cross(N, R)
    c = {"prograde": (0, 1, 0), "retrograde": (0, -1, 0), "radial": (1, 0, 0), "normal": (0, 0, 1)}
    d = np.array(c[m["type"]]) * m["dv_ms"] if m["type"] in c else np.array([m["dr"], m["dt"], m["dn"]])
    return (d[0] * R + d[1] * T + d[2] * N) / 1000

def propagate(y0, times, mans, mu, j2):
    out = np.zeros((len(times), 6)); y = y0.copy(); cur = 0.0
    mans = sorted(mans, key=lambda m: m["t_hours"])
    ends = [m["t_hours"] * 3600 for m in mans] + [times[-1]]
    for k, tend in enumerate(ends):
        last = k == len(mans)
        sel = np.where((times >= cur) & ((times <= tend) if last else (times < tend)))[0]
        if tend > cur:
            sol = solve_ivp(accel, (cur, tend), y, method="DOP853", rtol=1e-11, atol=1e-11,
                            t_eval=times[sel] if len(sel) else None, dense_output=True, args=(mu, j2))
            if len(sel): out[sel] = sol.y.T
            y = sol.sol(tend)
        elif len(sel): out[sel] = y
        if not last: y = y.copy(); y[3:] += maneuver_dv(mans[k], y); cur = tend
    return out

def series(states, times, gmst0, mu, obs):
    r, v = states[:, :3], states[:, 3:]; re = eci2ecef(r, times, gmst0)
    lon, lat, alt = ecef2geodetic(re)
    lon_u = np.degrees(np.unwrap(np.radians(lon)))
    el = elements(r, v, mu)
    az, el_ = azel(re, *obs)
    d = dict(x=r[:, 0], y=r[:, 1], z=r[:, 2], vx=v[:, 0], vy=v[:, 1], vz=v[:, 2],
             xe=re[:, 0], ye=re[:, 1], ze=re[:, 2], lon=lon, lat=lat, alt=alt,
             lon_rate=np.gradient(lon_u, times) * 86400, az=az, el=el_, **el)
    return {k: np.round(np.asarray(val), 9).tolist() for k, val in d.items()}

def simulate(c: dict) -> dict:
    mu = c["mu"]; g0 = gmst_deg(c["epoch"]); n = int(c["duration_h"] * 3600 / c["step_s"]) + 1
    times = np.arange(n) * c["step_s"]
    th0 = np.radians(c["ref_lon_deg"] + g0)     # inertial longitude putting the satellite over the slot at t0
    raan, w = np.radians(c["raan_deg"]), np.radians(c["argp_deg"])
    nu = (th0 - raan - w) % (2 * np.pi)
    r0, v0 = kep2cart(c["a_km"], c["e"], np.radians(c["inc_deg"]), raan, w, nu, mu)
    y0 = np.concatenate([r0, v0]); j2 = c["model"] == "j2"
    obs = (c["obs_lat_deg"], c["obs_lon_deg"])
    base = propagate(y0, times, [], mu, j2); man = propagate(y0, times, c["maneuvers"], mu, j2)
    return dict(t=times.tolist(), gmst0=g0, base=series(base, times, g0, mu, obs), man=series(man, times, g0, mu, obs),
                pos_res_km=np.linalg.norm(man[:, :3] - base[:, :3], axis=1).tolist(),
                vel_res_ms=(np.linalg.norm(man[:, 3:] - base[:, 3:], axis=1) * 1000).tolist())