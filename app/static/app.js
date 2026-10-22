const $ = id => document.getElementById(id);
const NUM = ["a_km","e","inc_deg","raan_deg","argp_deg","ref_lon_deg","duration_h","step_s","mu","obs_lat_deg","obs_lon_deg"];
const PRESET = {a_km:42164.17,e:0.0002,inc_deg:0.05,raan_deg:0,argp_deg:0,ref_lon_deg:75,duration_h:168,step_s:600,mu:398600.4418,obs_lat_deg:20,obs_lon_deg:78};
const BLUE = "#2457c5", AMBER = "#d98a00", INK = "#14202e";
let S = null, mans = [], idx = 0, timer = null;

const config = () => { const c = {name:$("name").value, epoch:$("epoch").value, model:$("model").value, maneuvers:mans};
  NUM.forEach(k => c[k] = parseFloat($(k).value)); return c; };

function renderMans() {
  $("manList").innerHTML = "";
  mans.forEach((m, i) => { const li = document.createElement("li");
    const d = m.type === "custom" ? `R${m.dr} T${m.dt} N${m.dn}` : `${m.dv_ms} m/s`;
    li.innerHTML = `<span>${m.type} · t+${m.t_hours} h · ${d}</span>`;
    const b = document.createElement("button"); b.textContent = "Remove"; b.className = "ghost";
    b.onclick = () => { mans.splice(i, 1); renderMans(); }; li.append(b); $("manList").append(li); });
}
$("addMan").onclick = () => {
  const m = {type:$("mtype").value, t_hours:parseFloat($("mt").value), dv_ms:parseFloat($("mdv").value),
    dr:parseFloat($("mdr").value), dt:parseFloat($("mdt").value), dn:parseFloat($("mdn").value)};
  if ([m.t_hours, m.dv_ms, m.dr, m.dt, m.dn].some(Number.isNaN)) { $("err").textContent = "Maneuver fields must be numbers."; return; }
  $("err").textContent = ""; mans.push(m); renderMans();
};
$("preset").onclick = () => { NUM.forEach(k => $(k).value = PRESET[k]); $("model").value = "j2"; };

async function run() {
  pause(); $("err").textContent = "";
  const c = config();
  if (NUM.some(k => Number.isNaN(c[k]))) { $("err").textContent = "Fill every numeric field."; return; }
  $("run").disabled = true; $("run").textContent = "Running…";
  try {
    const r = await fetch("/api/simulate", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(c)});
    const j = await r.json();
    if (!r.ok) throw new Error(Array.isArray(j.detail) ? j.detail.map(d => `${d.loc.slice(-1)[0]}: ${d.msg}`).join("; ") : j.detail);
    S = j; idx = 0; $("slider").max = S.t.length - 1; $("slider").value = 0; draw();
  } catch (e) { $("err").textContent = e.message; }
  $("run").disabled = false; $("run").textContent = "Run simulation";
}
$("run").onclick = run;

// Insert nulls where longitude wraps so no line is drawn across the map.
function wrap(lon, lat) { const X = [], Y = [];
  lon.forEach((x, i) => { if (i && Math.abs(x - lon[i-1]) > 180) { X.push(null); Y.push(null); } X.push(x); Y.push(lat[i]); });
  return [X, Y]; }
const hrs = () => S.t.map(t => t / 3600);
const manIdx = () => mans.map(m => Math.min(S.t.length - 1, Math.round(m.t_hours * 3600 / S.t[1])));
const lay = (title, x, y, extra = {}) => Object.assign({title:{text:title, font:{size:13}}, margin:{l:60,r:15,t:35,b:45},
  xaxis:{title:x}, yaxis:{title:y}, legend:{orientation:"h", y:-0.25}, paper_bgcolor:"#fff", font:{color:INK}}, extra);
const mlines = () => mans.map(m => ({type:"line", xref:"x", yref:"paper", x0:m.t_hours, x1:m.t_hours, y0:0, y1:1, line:{color:AMBER, dash:"dot", width:1.5}}));
const cfg = {responsive:true, displaylogo:false};

function draw() {
  const B = S.base, M = S.man, t = hrs(), f = $("frame").value, k = f === "eci" ? ["x","y","z"] : ["xe","ye","ze"], mi = manIdx();
  // Earth sphere + equator ring (frame-independent because Earth is a sphere here)
  const u = [], v = [], X = [], Y = [], Z = [], RE = 6378.137;
  for (let i = 0; i <= 20; i++) { X.push([]); Y.push([]); Z.push([]); for (let j = 0; j <= 40; j++) {
    const th = Math.PI * i / 20, ph = 2 * Math.PI * j / 40; X[i].push(RE*Math.sin(th)*Math.cos(ph)); Y[i].push(RE*Math.sin(th)*Math.sin(ph)); Z[i].push(RE*Math.cos(th)); } }
  const line3 = (s, name, color) => ({type:"scatter3d", mode:"lines", x:s[k[0]], y:s[k[1]], z:s[k[2]], name, line:{color, width:4}});
  Plotly.react("p3d", [
    {type:"surface", x:X, y:Y, z:Z, showscale:false, opacity:.9, colorscale:[[0,"#9db8cf"],[1,"#9db8cf"]], name:"Earth", hoverinfo:"skip"},
    line3(B, "Baseline (no maneuver)", BLUE), line3(M, "Maneuvered", AMBER),
    {type:"scatter3d", mode:"markers", x:[M[k[0]][idx]], y:[M[k[1]][idx]], z:[M[k[2]][idx]], name:"Current position", marker:{size:6, color:INK}},
    {type:"scatter3d", mode:"markers", x:mi.map(i => M[k[0]][i]), y:mi.map(i => M[k[1]][i]), z:mi.map(i => M[k[2]][i]), name:"Maneuver", marker:{size:6, color:"#b3392f", symbol:"diamond"}}
  ], {title:{text:`Orbit in ${f === "eci" ? "ECI (J2000-like, inertial)" : "ECEF (rotating with Earth)"} · km`, font:{size:13}},
      margin:{l:0,r:0,t:35,b:0}, scene:{aspectmode:"data", xaxis:{title:"X"}, yaxis:{title:"Y"}, zaxis:{title:"Z"}}, legend:{orientation:"h"}}, cfg);

  const [bx, by] = wrap(B.lon, B.lat), [mx, my] = wrap(M.lon, M.lat);
  Plotly.react("pgt", [{x:bx, y:by, mode:"lines", name:"Baseline", line:{color:BLUE}}, {x:mx, y:my, mode:"lines", name:"Maneuvered", line:{color:AMBER}},
    {x:[M.lon[idx]], y:[M.lat[idx]], mode:"markers", name:"Subsatellite point", marker:{size:10, color:INK}},
    {x:[parseFloat($("ref_lon_deg").value)], y:[0], mode:"markers", name:"Slot", marker:{symbol:"x", size:10, color:"#b3392f"}},
    {x:mi.map(i => M.lon[i]), y:mi.map(i => M.lat[i]), mode:"markers", name:"Maneuver", marker:{symbol:"diamond", size:9, color:"#b3392f"}}],
    lay("Ground track", "Longitude (°E)", "Latitude (°)", {xaxis:{title:"Longitude (°E)"}}), cfg);

  const ts = (id, title, y, key) => Plotly.react(id, [{x:t, y:B[key], name:"Baseline", line:{color:BLUE}}, {x:t, y:M[key], name:"Maneuvered", line:{color:AMBER}}],
    lay(title, "Time since epoch (h)", y, {shapes:mlines()}), cfg);
  ts("plon", "Earth-fixed longitude", "Longitude (°E)", "lon"); ts("pdrift", "Longitude drift rate", "°/day", "lon_rate");
  drawElem();
  Plotly.react("ppq", [{x:B.Q, y:B.P, mode:"lines", name:"Baseline", line:{color:BLUE}}, {x:M.Q, y:M.P, mode:"lines+markers", name:"Maneuvered", marker:{size:3}, line:{color:AMBER}}],
    lay("Inclination vector (P–Q)", "Q = tan(i/2)·cos Ω", "P = tan(i/2)·sin Ω"), cfg);
  Plotly.react("pres", [{x:t, y:S.pos_res_km, name:"Position (km)", line:{color:INK}}, {x:t, y:S.vel_res_ms, name:"Velocity (m/s)", yaxis:"y2", line:{color:"#b3392f"}}],
    lay("Residuals vs baseline", "Time since epoch (h)", "km", {yaxis2:{title:"m/s", overlaying:"y", side:"right"}, shapes:mlines()}), cfg);
  drawSky();
  marker();
}

// Sky view: zenith at the centre, horizon at the rim, N at top, E on the right. Below-horizon samples are hidden.
const skyR = e => e > 0 ? 90 - e : null;
function drawSky() {
  const B = S.base, M = S.man;
  const [bx, by] = wrap(B.az, B.el), [mx, my] = wrap(M.az, M.el);
  Plotly.react("psky", [
    {x:bx, y:by, mode:"lines", name:"Baseline", line:{color:BLUE}},
    {x:mx, y:my, mode:"lines", name:"Maneuvered", line:{color:AMBER}},
    {x:[M.az[idx]], y:[M.el[idx]], mode:"markers", name:"Current", marker:{size:10, color:INK}}
  ], lay("Sky view (as seen from the observer)", "Azimuth (° from N, E = 90)", "Elevation (°)"), cfg);
}

function drawElem() { if (!S) return; const key = $("elem").value, t = hrs();
  Plotly.react("pel", [{x:t, y:S.base[key], name:"Baseline", line:{color:BLUE}}, {x:t, y:S.man[key], name:"Maneuvered", line:{color:AMBER}}],
    lay("Orbital element history", "Time since epoch (h)", $("elem").selectedOptions[0].text, {shapes:mlines()}), cfg); }

// Slider → move the position markers in every plot (no re-propagation).
function marker() {
  const M = S.man, k = $("frame").value === "eci" ? ["x","y","z"] : ["xe","ye","ze"], t = S.t[idx] / 3600;
  Plotly.restyle("p3d", {x:[[M[k[0]][idx]]], y:[[M[k[1]][idx]]], z:[[M[k[2]][idx]]]}, [3]);
  Plotly.restyle("pgt", {x:[[M.lon[idx]]], y:[[M.lat[idx]]]}, [2]);
  Plotly.restyle("psky", {x:[[M.az[idx]]], y:[[M.el[idx]]]}, [2]);
  $("clock").textContent = `t = ${t.toFixed(2)} h · lon ${M.lon[idx].toFixed(3)}°E · lat ${M.lat[idx].toFixed(3)}° · drift ${M.lon_rate[idx].toFixed(3)} °/day`;
  $("slider").value = idx;
}
const go = i => { if (!S) return; idx = Math.max(0, Math.min(S.t.length - 1, i)); marker(); };
function pause() { clearInterval(timer); timer = null; $("play").textContent = "Play"; }
$("play").onclick = () => { if (!S) return; if (timer) return pause(); $("play").textContent = "Pause";
  timer = setInterval(() => { if (idx >= S.t.length - 1) return pause(); go(idx + Math.max(1, Math.round(S.t.length / 400))); }, 40); };
$("slider").oninput = e => { pause(); go(+e.target.value); };
$("fwd").onclick = () => { pause(); go(idx + 1); }; $("back").onclick = () => { pause(); go(idx - 1); };
$("reset").onclick = () => { pause(); go(0); };
$("frame").onchange = () => S && draw(); $("elem").onchange = drawElem;

function download(name, text, type) { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], {type})); a.download = name; a.click(); }
$("json").onclick = () => download(`${$("name").value}_config.json`, JSON.stringify(config(), null, 2), "application/json");
$("csv").onclick = () => { if (!S) { $("err").textContent = "Run a simulation before exporting."; return; }
  const cols = ["x","y","z","vx","vy","vz","xe","ye","ze","a","e","i","raan","lon","lat","alt","lon_rate","P","Q"];
  const head = "# epoch_utc," + $("epoch").value + "; t in s since epoch; x..vz ECI km, km/s; xe..ze ECEF km; a km; i,raan,lon,lat deg; alt km; lon_rate deg/day; P,Q dimensionless; maneuvered scenario\n";
  const rows = S.t.map((t, n) => [t, ...cols.map(c => S.man[c][n])].join(","));
  download(`${$("name").value}_maneuvered.csv`, head + "t_s," + cols.join(",") + "\n" + rows.join("\n"), "text/csv"); };