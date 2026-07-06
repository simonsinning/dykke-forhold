const spotSelect = document.querySelector("#spotSelect");
const refreshButton = document.querySelector("#refreshButton");
const bestGrade = document.querySelector("#bestGrade");
const bestText = document.querySelector("#bestText");
const bestScore = document.querySelector("#bestScore");
const confidenceText = document.querySelector("#confidenceText");
const spotInfoButton = document.querySelector("#spotInfoButton");
const spotInfoDialog = document.querySelector("#spotInfoDialog");
const spotInfoClose = document.querySelector("#spotInfoClose");
const spotInfoTitle = document.querySelector("#spotInfoTitle");
const spotInfoContent = document.querySelector("#spotInfoContent");
const ratingsEl = document.querySelector("#ratings");
const rankingsEl = document.querySelector("#rankings");
const rankingStatusEl = document.querySelector("#rankingStatus");
const mapStatusEl = document.querySelector("#mapStatus");
const mapDayControlsEl = document.querySelector("#mapDayControls");
const denmarkMapEl = document.querySelector("#denmarkMap");
const mapCanvasEl = document.querySelector("#mapCanvas");
const mapHeatLayerEl = document.querySelector("#mapHeatLayer");
const mapMarkerLayerEl = document.querySelector("#mapMarkerLayer");
const tabButtons = document.querySelectorAll(".tabButton");
const tabViews = document.querySelectorAll(".tabView");
const windCompassEl = document.querySelector("#windCompass");
const chartsEl = document.querySelector("#charts");
const reasonsEl = document.querySelector("#reasons");
const modelBreakdownEl = document.querySelector("#modelBreakdown");
const sourceEl = document.querySelector("#source");
const warningsEl = document.querySelector("#warnings");
const observationsEl = document.querySelector("#observations");
const observationForm = document.querySelector("#observationForm");
const formMessage = document.querySelector("#formMessage");

let currentSpot = null;
let currentSpotData = null;
let currentSeries = [];
let rankingsData = null;
let selectedMapDay = "I dag";
let mapZoom = 1;
let mapPanX = 0;
let mapPanY = 0;
let mapDragStart = null;

const MAP_BOUNDS = {
  latMin: 54.25,
  latMax: 58.05,
  lonMin: 5.2,
  lonMax: 14.3,
};

async function getJson(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Ukendt fejl");
  }
  return data;
}

async function loadSpots() {
  const data = await getJson("/api/spots");
  spotSelect.innerHTML = data.spots
    .map((spot) => `<option value="${spot.id}">${spot.name} - ${spot.area}</option>`)
    .join("");
  currentSpot = data.spots[0]?.id;
  spotSelect.value = currentSpot;
  await loadScore();
  await loadRankings();
}

async function loadScore() {
  currentSpot = spotSelect.value;
  setLoading();
  const data = await getJson(`/api/score?spot=${encodeURIComponent(currentSpot)}`);
  renderScore(data);
}

async function refreshAll() {
  await loadScore();
  await loadRankings();
}

async function loadRankings() {
  rankingStatusEl.textContent = "Henter rangliste...";
  rankingsEl.innerHTML = `<p class="muted">Scanner alle spots...</p>`;
  const data = await getJson("/api/rankings");
  renderRankings(data);
}

function switchTab(tabName) {
  tabButtons.forEach((button) => {
    button.classList.toggle("isActive", button.dataset.tab === tabName);
  });
  tabViews.forEach((view) => {
    view.classList.toggle("isActive", view.id === `${tabName}View`);
  });
  if (tabName === "map") {
    requestAnimationFrame(applyMapTransform);
  }
}

function setLoading() {
  bestGrade.textContent = "Henter data...";
  bestText.textContent = "";
  bestScore.textContent = "--";
  confidenceText.textContent = "";
  ratingsEl.innerHTML = "";
  windCompassEl.innerHTML = "";
  chartsEl.innerHTML = "";
  reasonsEl.innerHTML = "";
  modelBreakdownEl.innerHTML = "";
  observationsEl.innerHTML = "";
}

function renderScore(data) {
  const best = data.score.best;
  currentSpotData = data.spot;
  bestGrade.textContent = best.grade;
  bestScore.textContent = best.score;
  bestText.textContent = `${data.spot.name}: forventet sigt ${best.estimated_visibility_m.low}-${best.estimated_visibility_m.high} m. ${data.spot.notes}`;
  confidenceText.textContent = `Sikkerhed: ${best.confidence?.label ?? "--"}`;
  sourceEl.textContent = data.forecast.source;
  warningsEl.textContent = data.forecast.warnings.join(" ");

  ratingsEl.innerHTML = data.score.ratings.map(renderRating).join("");
  currentSeries = normalizeSeries(data.series);
  renderWindCompass(currentSeries, data.spot);
  renderCharts(currentSeries);
  reasonsEl.innerHTML = best.reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join("");
  modelBreakdownEl.innerHTML = renderBreakdown(best.breakdown);
  renderSpotInfo(data.spot, best);
  renderObservations(data.observations);
}

function renderRating(rating) {
  const metrics = rating.metrics;
  return `
    <article class="rating">
      <h3>${escapeHtml(rating.label)}</h3>
      <div class="score">${rating.score}</div>
      <div class="grade">${escapeHtml(rating.grade)} · ${rating.estimated_visibility_m.low}-${rating.estimated_visibility_m.high} m</div>
      <div class="metricList">
        <span>Vind: ${metrics.avg_wind_ms} m/s · stød ${metrics.max_gust_ms} m/s</span>
        <span>Bølger: ${metrics.avg_wave_m} m · maks ${metrics.max_wave_m} m</span>
        <span>Regn: ${metrics.rain_24h_mm ?? "--"} mm/24t · ${metrics.rain_72h_mm} mm/72t</span>
        <span>Ro: ${metrics.calm_hours ?? "--"} / ${metrics.required_calm_hours ?? "--"} timer</span>
        <span>Strøm: ${metrics.avg_current_ms} m/s</span>
        <span>Vand: ${metrics.sea_temperature_c ?? "--"} °C</span>
        <span>Sikkerhed: ${escapeHtml(rating.confidence?.label ?? "--")}</span>
      </div>
    </article>
  `;
}

function renderBreakdown(breakdown = {}) {
  const items = [
    {label: "Basis", value: breakdown.base_score, positive: true},
    {label: "Sediment/bølger", value: breakdown.sediment_penalty, negative: true},
    {label: "Vindstyrke", value: breakdown.wind_penalty, negative: true},
    {label: "Regn/runoff", value: breakdown.runoff_penalty, negative: true},
    {label: "Alger", value: breakdown.algae_penalty, negative: true},
    {label: "Strøm", value: breakdown.current_penalty, negative: true},
    {label: "Recovery", value: breakdown.recovery_modifier},
    {label: "Klart vand/læ", value: breakdown.clear_water_bonus, positive: true},
    {label: "Lokal regel", value: breakdown.local_penalty, negative: true},
  ].filter((item) => typeof item.value === "number");

  return items
    .map((item) => {
      const signed = item.negative ? -Math.abs(item.value) : item.value;
      const className = signed > 0 ? "isPositive" : signed < 0 ? "isNegative" : "";
      const display = signed > 0 ? `+${signed.toFixed(1)}` : signed.toFixed(1);
      return `
        <div class="breakdownItem ${className}">
          <span>${escapeHtml(item.label)}</span>
          <strong>${display}</strong>
        </div>
      `;
    })
    .join("");
}

function renderSpotInfo(spot, rating) {
  const model = spot.visibility_model || {};
  spotInfoTitle.textContent = `${spot.name} - ${spot.area}`;
  const baseline = model.baseline_visibility_m || {};
  const factors = model.special_factors || [];
  const fetchSectors = model.fetch_sectors || [];
  const confidenceNotes = rating.confidence?.notes || [];

  spotInfoContent.innerHTML = `
    <div class="infoLead">
      <strong>${escapeHtml(model.spot_type || "Lokal spotprofil")}</strong>
      <span>${escapeHtml(model.depth_profile || "Ingen dybdeprofil angivet.")}</span>
    </div>
    <div class="infoGrid">
      ${infoFact("Bund", model.bottom_type)}
      ${infoFact("Sedimentrisiko", model.sediment_risk)}
      ${infoFact("Lavvandsfaktor", model.shallow_factor)}
      ${infoFact("Krævet ro", model.required_calm_hours ? `${model.required_calm_hours} timer` : null)}
      ${infoFact("Regnfølsomhed", model.runoff_sensitivity)}
      ${infoFact("Algefølsomhed", model.algae_sensitivity)}
      ${infoFact("Vandudskiftning", model.water_exchange)}
      ${infoFact("Basis-sigt", formatBaselineVisibility(baseline, spot.typical_visibility_m))}
    </div>
    <section class="infoSection">
      <h3>Lokale sektorer</h3>
      ${
        fetchSectors.length
          ? `<ul>${fetchSectors.map((sector) => `<li><strong>${escapeHtml(sector.label)}</strong>: faktor ${escapeHtml(sector.factor)}</li>`).join("")}</ul>`
          : `<p class="muted">Ingen lokale fetch-sektorer angivet.</p>`
      }
    </section>
    <section class="infoSection">
      <h3>Særlige lokale faktorer</h3>
      ${
        factors.length
          ? `<ul>${factors.map((factor) => `<li>${escapeHtml(factor)}</li>`).join("")}</ul>`
          : `<p class="muted">Ingen særlige faktorer angivet.</p>`
      }
    </section>
    <section class="infoSection">
      <h3>Aktuel modelvurdering</h3>
      <p>Score ${rating.score}/100, forventet sigt ${rating.estimated_visibility_m.low}-${rating.estimated_visibility_m.high} m, sikkerhed ${escapeHtml(rating.confidence?.label ?? "--")}.</p>
      ${
        confidenceNotes.length
          ? `<ul>${confidenceNotes.map((note) => `<li>${escapeHtml(note)}</li>`).join("")}</ul>`
          : ""
      }
    </section>
  `;
}

function infoFact(label, value) {
  return `
    <div class="infoFact">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value ?? "--")}</strong>
    </div>
  `;
}

function formatBaselineVisibility(baseline, fallback) {
  const parts = [
    ["vinter", baseline.winter],
    ["forår", baseline.spring],
    ["sommer", baseline.summer],
    ["efterår", baseline.autumn],
  ].filter(([, value]) => value !== undefined);
  if (!parts.length) return `${fallback ?? 4} m`;
  return parts.map(([label, value]) => `${label}: ${value} m`).join(" · ");
}

function renderRankings(data) {
  rankingsData = data;
  rankingStatusEl.textContent = `Opdateret ${formatLongDate(new Date(data.generated_at).getTime())}`;
  rankingsEl.innerHTML = data.days.map(renderRankingDay).join("");
  renderMap(data);
}

function renderRankingDay(day) {
  return `
    <article class="rankingDay">
      <h3>${escapeHtml(day.label)}</h3>
      <div class="rankingList">
        ${day.rankings.map(renderRankingItem).join("")}
      </div>
    </article>
  `;
}

function renderRankingItem(item) {
  const visibility = item.estimated_visibility_m;
  const metrics = item.metrics;
  return `
    <button class="rankingRow" type="button" data-spot="${escapeHtml(item.spot_id)}">
      <span class="rankNumber">${item.rank}</span>
      <span class="rankMain">
        <strong>${escapeHtml(item.name)}</strong>
        <small>${escapeHtml(item.area)} · ${escapeHtml(item.window)}</small>
      </span>
      <span class="rankScore">
        <strong>${item.score}</strong>
        <small>${escapeHtml(item.grade)}</small>
      </span>
      <span class="rankMetrics">
        Sigt ${visibility.low}-${visibility.high} m · vind ${metrics.avg_wind_ms} m/s · bølger ${metrics.avg_wave_m} m
      </span>
    </button>
  `;
}

function renderMap(data) {
  if (!data?.days?.length) {
    mapStatusEl.textContent = "Ingen kortdata";
    mapDayControlsEl.innerHTML = "";
    mapHeatLayerEl.innerHTML = "";
    mapMarkerLayerEl.innerHTML = "";
    return;
  }

  if (!data.days.some((day) => day.label === selectedMapDay)) {
    selectedMapDay = data.days[0].label;
  }

  mapStatusEl.textContent = `Opdateret ${formatLongDate(new Date(data.generated_at).getTime())}`;
  mapDayControlsEl.innerHTML = data.days
    .map(
      (day) =>
        `<button class="mapDayButton ${day.label === selectedMapDay ? "isActive" : ""}" type="button" data-day="${escapeHtml(day.label)}">${escapeHtml(day.label)}</button>`
    )
    .join("");

  const day = data.days.find((item) => item.label === selectedMapDay);
  const spots = day?.rankings ?? [];
  mapHeatLayerEl.innerHTML = spots.map(renderMapHeat).join("");
  mapMarkerLayerEl.innerHTML = spots.map(renderMapMarker).join("");
  applyMapTransform();
}

function renderMapHeat(item) {
  const position = mapPosition(item);
  const color = scoreColor(item.score);
  const size = 28 + Math.max(0, item.score) * 0.18;
  return `
    <div
      class="mapHeat"
      style="left:${position.x}%; top:${position.y}%; width:${size}px; height:${size}px; background:${color};"
    ></div>
  `;
}

function renderMapMarker(item) {
  const position = mapPosition(item);
  const score = Math.round(item.score);
  return `
    <button
      class="mapMarker"
      type="button"
      data-spot="${escapeHtml(item.spot_id)}"
      style="left:${position.x}%; top:${position.y}%; --score-color:${scoreColor(item.score)};"
      title="${escapeHtml(item.name)}: ${item.score}/100"
      aria-label="${escapeHtml(item.name)}: ${item.score} ud af 100"
    >
      <span>
        <svg viewBox="0 0 44 44" aria-hidden="true" focusable="false">
          <circle cx="22" cy="22" r="18" class="mapMarkerDot"></circle>
          <text x="22" y="22">${score}</text>
        </svg>
      </span>
    </button>
  `;
}

function mapPosition(item) {
  const longitude = Number(item.longitude);
  const latitude = Number(item.latitude);
  const x =
    ((longitudeToX(longitude) - longitudeToX(MAP_BOUNDS.lonMin)) /
      (longitudeToX(MAP_BOUNDS.lonMax) - longitudeToX(MAP_BOUNDS.lonMin))) *
    100;
  const y =
    ((latitudeToY(latitude) - latitudeToY(MAP_BOUNDS.latMax)) /
      (latitudeToY(MAP_BOUNDS.latMin) - latitudeToY(MAP_BOUNDS.latMax))) *
    100;
  return {
    x: Math.max(2, Math.min(98, x)),
    y: Math.max(2, Math.min(98, y)),
  };
}

function longitudeToX(longitude) {
  return (longitude + 180) / 360;
}

function latitudeToY(latitude) {
  const sinLatitude = Math.sin((latitude * Math.PI) / 180);
  return 0.5 - Math.log((1 + sinLatitude) / (1 - sinLatitude)) / (4 * Math.PI);
}

function scoreColor(score) {
  if (score >= 80) return "#2f9e44";
  if (score >= 62) return "#82c91e";
  if (score >= 42) return "#f08c00";
  if (score >= 25) return "#e8590c";
  return "#c92a2a";
}

function setMapZoom(nextZoom, originX, originY) {
  const rect = denmarkMapEl.getBoundingClientRect();
  const oldZoom = mapZoom;
  const newZoom = Math.max(1, Math.min(18, nextZoom));
  const centerX = Number.isFinite(originX) ? originX : rect.width / 2;
  const centerY = Number.isFinite(originY) ? originY : rect.height / 2;
  const mapX = (centerX - mapPanX) / oldZoom;
  const mapY = (centerY - mapPanY) / oldZoom;

  mapZoom = newZoom;
  mapPanX = centerX - mapX * newZoom;
  mapPanY = centerY - mapY * newZoom;
  clampMapPan();
  applyMapTransform();
}

function resetMapZoom() {
  mapZoom = 1;
  mapPanX = 0;
  mapPanY = 0;
  applyMapTransform();
}

function clampMapPan() {
  const rect = denmarkMapEl.getBoundingClientRect();
  if (mapZoom <= 1) {
    mapPanX = 0;
    mapPanY = 0;
    return;
  }

  const minX = rect.width * (1 - mapZoom);
  const minY = rect.height * (1 - mapZoom);
  mapPanX = Math.min(0, Math.max(minX, mapPanX));
  mapPanY = Math.min(0, Math.max(minY, mapPanY));
}

function applyMapTransform() {
  const transform = `translate(${mapPanX}px, ${mapPanY}px) scale(${mapZoom})`;
  mapCanvasEl.style.transform = transform;
  const markerScale = 1 / mapZoom;
  const heatScale = 1 / mapZoom;
  const heatOpacity = mapZoom <= 1 ? 0.18 : Math.max(0.05, 0.18 / Math.sqrt(mapZoom));
  mapCanvasEl.style.setProperty("--marker-scale", markerScale.toFixed(3));
  mapCanvasEl.style.setProperty("--heat-scale", heatScale.toFixed(3));
  mapCanvasEl.style.setProperty("--heat-opacity", heatOpacity.toFixed(3));
  denmarkMapEl.classList.toggle("isZoomed", mapZoom > 1);
}

function normalizeSeries(series = []) {
  return series
    .map((row) => ({...row, ts: new Date(row.time).getTime()}))
    .filter((row) => Number.isFinite(row.ts));
}

function renderWindCompass(series, spot) {
  if (!series.length) {
    windCompassEl.innerHTML = `<p class="muted">Ingen vinddata til kompasvisning.</p>`;
    return;
  }

  const nowIndex = closestIndex(series, Date.now());
  const coastOverlay = renderCoastOverlay(spot);
  windCompassEl.innerHTML = `
    <div class="windCompassInfo">
      <div>
        <h3>Vindkompas</h3>
        <p id="windCompassTime"></p>
      </div>
      <div class="windStats">
        <strong id="windCompassSpeed">--</strong>
        <span id="windCompassDirection">--</span>
        <span id="windCompassRain">--</span>
      </div>
    </div>
    <div class="windCompassBody">
      <div class="compassScene" id="compassScene">
        ${coastOverlay}
        <div class="rainLayer" id="rainLayer"></div>
        <span class="compassLabel north">N</span>
        <span class="compassLabel east">Ø</span>
        <span class="compassLabel south">S</span>
        <span class="compassLabel west">V</span>
        <div class="windArrow" id="windArrow" aria-hidden="true"></div>
      </div>
      <div class="windScale" aria-label="Vindstyrke farver">
        <h4>Vind</h4>
        <div><i style="background:#2f9e44"></i><span>0-4 m/s</span></div>
        <div><i style="background:#f08c00"></i><span>4-7 m/s</span></div>
        <div><i style="background:#e8590c"></i><span>7-10 m/s</span></div>
        <div><i style="background:#c92a2a"></i><span>10+ m/s</span></div>
        <h4>Kyst</h4>
        <div><i class="coastKey land"></i><span>Strand/land</span></div>
        <div><i class="coastKey water"></i><span>Vand</span></div>
      </div>
      <div class="windSliderBlock">
        <input id="windTimeSlider" type="range" min="0" max="${series.length - 1}" step="1" value="${nowIndex}">
        <div class="windSliderLabels">
          <span>${formatShortDate(series[0].ts)}</span>
          <span>Nu</span>
          <span>${formatShortDate(series[series.length - 1].ts)}</span>
        </div>
      </div>
    </div>
  `;

  const slider = document.querySelector("#windTimeSlider");
  slider.addEventListener("input", () => updateWindCompass(Number(slider.value)));
  updateWindCompass(nowIndex);
}

function renderCoastOverlay(spot) {
  const badDirections = spot?.bad_wind_directions || [];
  const goodDirections = spot?.good_wind_directions || [];
  if (!badDirections.length && !goodDirections.length) {
    return "";
  }

  const badCenter = circularMeanDegrees(badDirections) ?? normalizeDegrees((circularMeanDegrees(goodDirections) ?? 180) + 180);
  const goodCenter = normalizeDegrees(badCenter + 180);
  const coastStart = polarToCartesian(50, 50, 46, badCenter - 90);
  const coastEnd = polarToCartesian(50, 50, 46, badCenter + 90);

  return `
    <svg class="coastOverlay" viewBox="0 0 100 100" aria-hidden="true">
      <defs>
        <pattern id="landPattern" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(35)">
          <rect width="7" height="7" fill="#f08c00"></rect>
          <rect width="2.2" height="7" fill="#7c2d12" opacity="0.7"></rect>
        </pattern>
      </defs>
      <circle cx="50" cy="50" r="42" class="coastRing"></circle>
      <path class="coastSector land" d="${pieSectorPath(50, 50, 46, goodCenter - 90, goodCenter + 90)}"></path>
      <path class="coastSector water" d="${pieSectorPath(50, 50, 46, badCenter - 90, badCenter + 90)}"></path>
      <line class="coastLine" x1="${coastStart.x.toFixed(1)}" y1="${coastStart.y.toFixed(1)}" x2="${coastEnd.x.toFixed(1)}" y2="${coastEnd.y.toFixed(1)}"></line>
    </svg>
  `;
}

function pieSectorPath(cx, cy, radius, startAngle, endAngle) {
  const startOuter = polarToCartesian(cx, cy, radius, endAngle);
  const endOuter = polarToCartesian(cx, cy, radius, startAngle);
  const largeArcFlag = Math.abs(endAngle - startAngle) <= 180 ? "0" : "1";

  return [
    "M", cx, cy,
    "L", startOuter.x.toFixed(2), startOuter.y.toFixed(2),
    "A", radius, radius, 0, largeArcFlag, 0, endOuter.x.toFixed(2), endOuter.y.toFixed(2),
    "Z",
  ].join(" ");
}

function circularMeanDegrees(values) {
  const clean = values.map(Number).filter(Number.isFinite);
  if (!clean.length) return null;
  const vector = clean.reduce(
    (acc, value) => {
      const radians = (value * Math.PI) / 180;
      return {
        x: acc.x + Math.cos(radians),
        y: acc.y + Math.sin(radians),
      };
    },
    {x: 0, y: 0}
  );
  if (Math.abs(vector.x) < 0.0001 && Math.abs(vector.y) < 0.0001) return clean[0];
  return normalizeDegrees((Math.atan2(vector.y, vector.x) * 180) / Math.PI);
}

function normalizeDegrees(value) {
  return ((value % 360) + 360) % 360;
}

function polarToCartesian(cx, cy, radius, angleDegrees) {
  const angleRadians = ((angleDegrees - 90) * Math.PI) / 180;
  return {
    x: cx + radius * Math.cos(angleRadians),
    y: cy + radius * Math.sin(angleRadians),
  };
}

function updateWindCompass(index) {
  const row = currentSeries[index];
  if (!row) return;

  const windSpeed = Number(row.wind_speed ?? 0);
  const windGusts = Number(row.wind_gusts ?? 0);
  const windFrom = Number(row.wind_direction ?? 0);
  const windTo = (windFrom + 180) % 360;
  const rain = Number(row.precipitation ?? 0);
  const color = windColor(windSpeed);
  const rainOpacity = Math.min(0.75, rain / 4);
  const arrowScale = 0.48 + Math.min(1.0, windSpeed / 11) * 0.62;
  const arrowLength = windSpeed < 4 ? "kort pil" : windSpeed < 7 ? "middel pil" : windSpeed < 10 ? "stor pil" : "meget stor pil";

  document.querySelector("#windCompassTime").textContent = formatLongDate(row.ts);
  document.querySelector("#windCompassSpeed").textContent = `${windSpeed.toFixed(1)} m/s`;
  document.querySelector("#windCompassDirection").textContent = `Fra ${compassName(windFrom)} (${Math.round(windFrom)}°), blæser mod ${compassName(windTo)} · ${windRelation(windFrom)}`;
  document.querySelector("#windCompassRain").textContent = rain > 0 ? `Regn ${rain.toFixed(1)} mm/t` : "Ingen regn";

  const scene = document.querySelector("#compassScene");
  const arrow = document.querySelector("#windArrow");
  const rainLayer = document.querySelector("#rainLayer");
  scene.style.setProperty("--wind-color", color);
  scene.style.setProperty("--rain-opacity", rainOpacity);
  scene.style.setProperty("--gust-ring", Math.min(1, windGusts / 18));
  scene.style.setProperty("--arrow-scale", arrowScale.toFixed(2));
  arrow.setAttribute("title", `${arrowLength} ved ${windSpeed.toFixed(1)} m/s`);
  arrow.style.transform = `rotate(${windTo}deg) scale(${arrowScale.toFixed(2)})`;
  rainLayer.classList.toggle("isRaining", rain > 0.05);
}

function windRelation(windFrom) {
  const spot = currentSpotData || {};
  const tolerance = Number(spot.direction_tolerance ?? 55);
  const bad = directionMatchClient(windFrom, spot.bad_wind_directions || [], tolerance);
  const good = directionMatchClient(windFrom, spot.good_wind_directions || [], tolerance);
  if (bad > 0.55 && bad >= good) return "påland/uro";
  if (good > 0.55 && good > bad) return "fraland/læ";
  if (bad > 0.15 && bad >= good) return "delvis påland";
  if (good > 0.15 && good > bad) return "delvis fraland";
  return "sidevind/neutral";
}

function directionMatchClient(direction, centers, tolerance) {
  if (!Number.isFinite(direction) || !centers.length) return 0;
  const distance = Math.min(...centers.map((center) => angleDistanceClient(direction, Number(center))));
  if (distance >= tolerance) return 0;
  return 1 - distance / tolerance;
}

function angleDistanceClient(a, b) {
  return Math.abs((((a - b + 180) % 360) + 360) % 360 - 180);
}

function closestIndex(rows, targetTs) {
  let bestIndex = 0;
  let bestDistance = Infinity;
  rows.forEach((row, index) => {
    const distance = Math.abs(row.ts - targetTs);
    if (distance < bestDistance) {
      bestDistance = distance;
      bestIndex = index;
    }
  });
  return bestIndex;
}

function windColor(speed) {
  if (speed < 4) return "#2f9e44";
  if (speed < 7) return "#f08c00";
  if (speed < 10) return "#e8590c";
  return "#c92a2a";
}

function formatShortDate(ts) {
  return new Date(ts).toLocaleDateString("da-DK", {weekday: "short", day: "numeric"});
}

function formatLongDate(ts) {
  return new Date(ts).toLocaleString("da-DK", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function renderCharts(series) {
  const chartConfigs = [
    {
      title: "Vind",
      unit: "m/s",
      fields: [
        {key: "wind_speed", label: "Vind", color: "#0b7285"},
        {key: "wind_gusts", label: "Vindstød", color: "#c92a2a"},
      ],
      min: 0,
    },
    {
      title: "Vindretning",
      unit: "grader",
      fields: [{key: "wind_direction", label: "Retning", color: "#5f3dc4"}],
      min: 0,
      max: 360,
      compass: true,
    },
    {
      title: "Bølger",
      unit: "m",
      fields: [{key: "wave_height", label: "Bølgehøjde", color: "#1971c2"}],
      min: 0,
    },
    {
      title: "Regn",
      unit: "mm/t",
      fields: [{key: "precipitation", label: "Nedbør", color: "#2f9e44", bars: true}],
      min: 0,
    },
    {
      title: "Strøm",
      unit: "m/s",
      fields: [{key: "current_velocity", label: "Strøm", color: "#e67700"}],
      min: 0,
    },
    {
      title: "Vandtemperatur",
      unit: "°C",
      fields: [{key: "sea_temperature", label: "Temperatur", color: "#087f5b"}],
    },
  ];

  chartsEl.innerHTML = chartConfigs.map((config) => renderChart(series, config)).join("");
}

function renderChart(series, config) {
  const rows = series
    .map((row) => ({...row, ts: new Date(row.time).getTime()}))
    .filter((row) => Number.isFinite(row.ts));

  if (!rows.length) {
    return `<article class="chartCard"><h3>${escapeHtml(config.title)}</h3><p class="muted">Ingen data.</p></article>`;
  }

  const width = 720;
  const height = 250;
  const pad = {top: 20, right: 22, bottom: 38, left: 46};
  const innerWidth = width - pad.left - pad.right;
  const innerHeight = height - pad.top - pad.bottom;
  const minTime = rows[0].ts;
  const maxTime = rows[rows.length - 1].ts;
  const values = config.fields.flatMap((field) =>
    rows.map((row) => row[field.key]).filter((value) => typeof value === "number")
  );
  const rawMin = config.min ?? Math.min(...values);
  const rawMax = config.max ?? Math.max(...values);
  const yMin = Number.isFinite(rawMin) ? rawMin : 0;
  const yMax = Number.isFinite(rawMax) && rawMax > yMin ? rawMax : yMin + 1;
  const x = (ts) => pad.left + ((ts - minTime) / (maxTime - minTime || 1)) * innerWidth;
  const y = (value) => pad.top + (1 - (value - yMin) / (yMax - yMin)) * innerHeight;
  const nowX = x(Date.now());
  const yTicks = makeTicks(yMin, yMax, 4);
  const xTicks = makeTimeTicks(minTime, maxTime);
  const legend = config.fields
    .map((field) => `<span><i style="background:${field.color}"></i>${escapeHtml(field.label)}</span>`)
    .join("");
  const latest = [...rows].reverse().find((row) => typeof row[config.fields[0].key] === "number");
  const latestValue = latest ? formatValue(latest[config.fields[0].key], config) : "--";

  const seriesMarkup = config.fields
    .map((field) => {
      if (field.bars) {
        return renderBars(rows, field, x, y, yMin, pad.top + innerHeight);
      }
      return renderLine(rows, field, x, y);
    })
    .join("");

  const directionMarkers = config.compass ? renderDirectionMarkers(rows, x, y) : "";

  return `
    <article class="chartCard">
      <div class="chartHeader">
        <div>
          <h3>${escapeHtml(config.title)}</h3>
          <p>${escapeHtml(config.unit)}</p>
        </div>
        <strong>${latestValue}</strong>
      </div>
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(config.title)} graf">
        <rect x="${pad.left}" y="${pad.top}" width="${innerWidth}" height="${innerHeight}" class="plotBg"></rect>
        ${yTicks
          .map(
            (tick) => `
              <line x1="${pad.left}" x2="${width - pad.right}" y1="${y(tick)}" y2="${y(tick)}" class="gridLine"></line>
              <text x="${pad.left - 8}" y="${y(tick) + 4}" text-anchor="end" class="axisText">${formatAxis(tick, config)}</text>
            `
          )
          .join("")}
        ${xTicks
          .map(
            (tick) => `
              <line x1="${x(tick.ts)}" x2="${x(tick.ts)}" y1="${pad.top}" y2="${pad.top + innerHeight}" class="timeLine"></line>
              <text x="${x(tick.ts)}" y="${height - 12}" text-anchor="middle" class="axisText">${tick.label}</text>
            `
          )
          .join("")}
        ${
          nowX >= pad.left && nowX <= width - pad.right
            ? `<line x1="${nowX}" x2="${nowX}" y1="${pad.top}" y2="${pad.top + innerHeight}" class="nowLine"></line><text x="${nowX + 5}" y="${pad.top + 14}" class="nowText">Nu</text>`
            : ""
        }
        ${seriesMarkup}
        ${directionMarkers}
      </svg>
      <div class="legend">${legend}</div>
    </article>
  `;
}

function renderLine(rows, field, x, y) {
  const points = rows
    .filter((row) => typeof row[field.key] === "number")
    .map((row) => `${x(row.ts).toFixed(1)},${y(row[field.key]).toFixed(1)}`)
    .join(" ");
  if (!points) return "";
  return `<polyline points="${points}" fill="none" stroke="${field.color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></polyline>`;
}

function renderBars(rows, field, x, y, yMin, baseline) {
  const barWidth = 3;
  return rows
    .filter((row) => typeof row[field.key] === "number")
    .map((row) => {
      const valueY = y(Math.max(row[field.key], yMin));
      const height = Math.max(1, baseline - valueY);
      return `<rect x="${(x(row.ts) - barWidth / 2).toFixed(1)}" y="${valueY.toFixed(1)}" width="${barWidth}" height="${height.toFixed(1)}" fill="${field.color}" opacity="0.75"></rect>`;
    })
    .join("");
}

function renderDirectionMarkers(rows, x, y) {
  return rows
    .filter((row, index) => index % 12 === 0 && typeof row.wind_direction === "number")
    .map((row) => {
      const markerX = x(row.ts);
      const markerY = y(row.wind_direction);
      return `<text x="${markerX}" y="${markerY - 8}" text-anchor="middle" class="directionArrow" style="transform-origin:${markerX}px ${markerY}px; transform: rotate(${row.wind_direction}deg);">↑</text>`;
    })
    .join("");
}

function makeTicks(min, max, count) {
  const ticks = [];
  const step = (max - min) / count;
  for (let index = 0; index <= count; index += 1) {
    ticks.push(min + step * index);
  }
  return ticks;
}

function makeTimeTicks(minTime, maxTime) {
  const ticks = [];
  const dayMs = 24 * 60 * 60 * 1000;
  const start = new Date(minTime);
  start.setHours(0, 0, 0, 0);
  for (let ts = start.getTime(); ts <= maxTime + dayMs; ts += dayMs) {
    if (ts >= minTime && ts <= maxTime) {
      const date = new Date(ts);
      ticks.push({
        ts,
        label: date.toLocaleDateString("da-DK", {weekday: "short", day: "numeric"}),
      });
    }
  }
  return ticks;
}

function formatValue(value, config) {
  if (config.compass) {
    return `${Math.round(value)}° ${compassName(value)}`;
  }
  return `${Number(value).toFixed(value >= 10 ? 0 : 1)} ${config.unit}`;
}

function formatAxis(value, config) {
  if (config.compass) {
    return `${Math.round(value)}°`;
  }
  return Number(value).toFixed(value >= 10 ? 0 : 1);
}

function compassName(degrees) {
  const names = ["N", "NØ", "Ø", "SØ", "S", "SV", "V", "NV"];
  const index = Math.round((((degrees % 360) + 360) % 360) / 45) % names.length;
  return names[index];
}

function renderObservations(observations) {
  if (!observations.length) {
    observationsEl.innerHTML = `<p class="muted">Ingen observationer endnu for dette spot.</p>`;
    return;
  }
  observationsEl.innerHTML = observations
    .map(
      (obs) => `
        <div class="observation">
          <div>
            <strong>${escapeHtml(obs.created_at)}</strong>
            <div class="muted">${escapeHtml(obs.surface || "")}</div>
          </div>
          <div><strong>${escapeHtml(String(obs.visibility_m))} m</strong><div class="muted">${escapeHtml(obs.diveable)}</div></div>
          <div>${escapeHtml(obs.notes || "")}</div>
        </div>
      `
    )
    .join("");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

observationForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  formMessage.textContent = "Gemmer...";
  const payload = {
    spot_id: currentSpot,
    visibility_m: document.querySelector("#visibilityInput").value,
    surface: document.querySelector("#surfaceInput").value,
    diveable: document.querySelector("#diveableInput").checked,
    notes: document.querySelector("#notesInput").value,
  };
  try {
    await getJson("/api/observations", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    observationForm.reset();
    document.querySelector("#diveableInput").checked = true;
    formMessage.textContent = "Observation gemt.";
    await loadScore();
  } catch (error) {
    formMessage.textContent = error.message;
  }
});

rankingsEl.addEventListener("click", async (event) => {
  const row = event.target.closest(".rankingRow");
  if (!row) return;
  await openSpot(row.dataset.spot);
});

mapDayControlsEl.addEventListener("click", (event) => {
  const button = event.target.closest(".mapDayButton");
  if (!button) return;
  selectedMapDay = button.dataset.day;
  renderMap(rankingsData);
});

mapMarkerLayerEl.addEventListener("click", async (event) => {
  const marker = event.target.closest(".mapMarker");
  if (!marker) return;
  await openSpot(marker.dataset.spot);
});

denmarkMapEl.addEventListener("click", (event) => {
  const zoomButton = event.target.closest("[data-map-zoom]");
  if (!zoomButton) return;
  const action = zoomButton.dataset.mapZoom;
  if (action === "in") setMapZoom(mapZoom * 2.2);
  if (action === "out") setMapZoom(mapZoom / 2.2);
  if (action === "reset") resetMapZoom();
});

denmarkMapEl.addEventListener(
  "wheel",
  (event) => {
    event.preventDefault();
    const rect = denmarkMapEl.getBoundingClientRect();
    const factor = event.deltaY < 0 ? 1.18 : 1 / 1.18;
    setMapZoom(mapZoom * factor, event.clientX - rect.left, event.clientY - rect.top);
  },
  {passive: false}
);

denmarkMapEl.addEventListener("pointerdown", (event) => {
  if (mapZoom <= 1) return;
  if (event.target.closest(".mapMarker, .mapZoomControls, .mapAttribution")) return;
  mapDragStart = {
    pointerId: event.pointerId,
    x: event.clientX,
    y: event.clientY,
    panX: mapPanX,
    panY: mapPanY,
  };
  denmarkMapEl.setPointerCapture(event.pointerId);
});

denmarkMapEl.addEventListener("pointermove", (event) => {
  if (!mapDragStart || event.pointerId !== mapDragStart.pointerId) return;
  mapPanX = mapDragStart.panX + event.clientX - mapDragStart.x;
  mapPanY = mapDragStart.panY + event.clientY - mapDragStart.y;
  clampMapPan();
  applyMapTransform();
});

denmarkMapEl.addEventListener("pointerup", () => {
  mapDragStart = null;
});

denmarkMapEl.addEventListener("pointercancel", () => {
  mapDragStart = null;
});

spotInfoButton.addEventListener("click", () => {
  if (typeof spotInfoDialog.showModal === "function") {
    spotInfoDialog.showModal();
  } else {
    spotInfoDialog.setAttribute("open", "");
  }
});

spotInfoClose.addEventListener("click", () => {
  spotInfoDialog.close();
});

spotInfoDialog.addEventListener("click", (event) => {
  if (event.target === spotInfoDialog) {
    spotInfoDialog.close();
  }
});

async function openSpot(spotId) {
  spotSelect.value = spotId;
  switchTab("spot");
  await loadScore();
  window.scrollTo({top: 0, behavior: "smooth"});
}

tabButtons.forEach((button) => {
  button.addEventListener("click", () => switchTab(button.dataset.tab));
});

spotSelect.addEventListener("change", loadScore);
refreshButton.addEventListener("click", refreshAll);
window.addEventListener("resize", applyMapTransform);

loadSpots().catch((error) => {
  bestGrade.textContent = "Fejl";
  bestText.textContent = error.message;
});
