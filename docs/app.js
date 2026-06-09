'use strict';
/* Conteo Perú 2026 — lee los JSON estáticos (mismo origen) y pinta el dashboard.
   No habla con ONPE: eso lo hace el recolector (GitHub Actions). */

const POLL_MS = 60_000;
const KEIKO = '#f5871f', SANCHEZ = '#3b8ee0';
let chart = null, lastRegions = [], sortKey = 'nombre', sortDir = 1, geo = null;

const $ = (id) => document.getElementById(id);
const pct = (x, d = 1) => (x == null ? '—' : Number(x).toFixed(d) + '%');
const nf = new Intl.NumberFormat('es-PE');

async function getJSON(path) {
  const r = await fetch(`${path}?v=${Date.now()}`, { cache: 'no-store' });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

function timeAgo(iso) {
  const t = new Date(iso.endsWith('Z') ? iso : iso + 'Z');
  const s = Math.max(0, (Date.now() - t.getTime()) / 1000);
  if (s < 90) return 'hace segundos';
  if (s < 3600) return `hace ${Math.round(s / 60)} min`;
  if (s < 86400) return `hace ${Math.round(s / 3600)} h`;
  return `hace ${Math.round(s / 86400)} d`;
}

function renderHeadline(d) {
  // Número grande = conteo ACTUAL escrutado (lo que muestra ONPE). La proyección
  // va como línea secundaria. El share actual viene directo de los votos válidos.
  const v = d.nacional.votos, total = v.keiko + v.sanchez || 1;
  const actK = (v.keiko / total) * 100, actS = (v.sanchez / total) * 100;
  const proj = d.proyeccion.proyeccion_2via_pct;
  $('pct-keiko').textContent = pct(actK, 2);
  $('pct-sanchez').textContent = pct(actS, 2);
  $('band-keiko').textContent = `${pct(proj.keiko.media)} (${pct(proj.keiko.lo)}–${pct(proj.keiko.hi)})`;
  $('band-sanchez').textContent = `${pct(proj.sanchez.media)} (${pct(proj.sanchez.lo)}–${pct(proj.sanchez.hi)})`;
  $('actasLabel').textContent = `${pct(d.nacional.actas_pct)} actas`;
}

function renderBar(d) {
  // Relleno sólido = conteo actual; banda punteada = rango proyectado (95%).
  const v = d.nacional.votos, total = v.keiko + v.sanchez || 1;
  const actK = (v.keiko / total) * 100;
  const k = d.proyeccion.proyeccion_2via_pct.keiko;
  $('barKeiko').style.width = actK + '%';
  $('barBand').style.left = k.lo + '%';
  $('barBand').style.width = Math.max(0, k.hi - k.lo) + '%';
}

function renderExterior(d) {
  const cont = (d.regiones || []).filter((x) => x.exterior);
  if (!cont.length) { $('extCard').style.display = 'none'; return; }

  // agregado (suma de continentes)
  const aggK = cont.reduce((a, r) => a + r.votos.keiko, 0);
  const aggS = cont.reduce((a, r) => a + r.votos.sanchez, 0);
  const aggN = aggK + aggS;
  const totActas = cont.reduce((a, r) => a + r.actas_total, 0);
  const contabActas = cont.reduce((a, r) => a + r.actas_contabilizadas, 0);
  if (aggN === 0) { $('extCard').style.display = 'none'; return; }
  const kPct = (aggK / aggN) * 100;
  $('extKeiko').textContent = pct(kPct, 1);
  $('extSanchez').textContent = pct(100 - kPct, 1);
  $('extBar').style.width = kPct + '%';
  const escPct = totActas ? (100 * contabActas / totActas) : 0;
  $('extActas').textContent = `${pct(escPct)} escrutado · ${nf.format(contabActas)}/${nf.format(totActas)} actas`;

  // desglose por continente (mayor padrón primero)
  const rows = [...cont].sort((a, b) => b.actas_total - a.actas_total).map((r) => {
    const n = r.votos.keiko + r.votos.sanchez;
    const nombre = r.nombre.replace('Exterior – ', '');
    if (n === 0) {
      return `<div class="ext-cont"><span class="ext-cont-name">${nombre}</span>`
        + `<div class="ext-cont-bar empty"></div>`
        + `<span class="ext-cont-meta">${pct(r.pct_actas)} esc. · pendiente</span></div>`;
    }
    const ck = (r.votos.keiko / n) * 100;
    return `<div class="ext-cont"><span class="ext-cont-name">${nombre}</span>`
      + `<div class="ext-cont-bar"><i style="width:${ck}%"></i></div>`
      + `<span class="ext-cont-meta">${pct(ck)} K · ${pct(r.pct_actas)} esc.</span></div>`;
  }).join('');
  $('extConts').innerHTML = rows;

  const pend = contabActas > 0 ? Math.round(aggN * (totActas / contabActas - 1)) : 0;
  const lider = kPct >= 50 ? 'Keiko' : 'Sánchez';
  $('extNote').innerHTML = `${nf.format(aggN)} votos contados · faltan ~<strong>${nf.format(pend)}</strong> por contar. `
    + `El extranjero lidera <strong>${lider}</strong> y ya está incorporado en la proyección nacional.`;
}

function renderProb(d) {
  const pr = d.proyeccion.prob_victoria;
  const fmtP = (x) => (x >= 0.999 ? '>99.9%' : x <= 0.001 ? '<0.1%' : (x * 100).toFixed(1) + '%');
  $('prob-keiko').style.width = (pr.keiko * 100).toFixed(1) + '%';
  $('prob-sanchez').style.width = (pr.sanchez * 100).toFixed(1) + '%';
  $('probval-keiko').textContent = fmtP(pr.keiko);
  $('probval-sanchez').textContent = fmtP(pr.sanchez);
  $('nsamples').textContent = nf.format(d.proyeccion.n_samples);
  $('fracFalta').textContent = pct(d.proyeccion.frac_faltante * 100);

  const g = d.proyeccion.ganador_proyectado;
  const name = g === 'keiko' ? 'Keiko Fujimori' : 'Roberto Sánchez';
  const p = Math.max(pr.keiko, pr.sanchez);
  let verb = p >= 0.95 ? 'favorito claro' : p >= 0.75 ? 'favorito' : p >= 0.6 ? 'ligera ventaja' : 'empate técnico';
  $('winner').innerHTML = `Proyección actual: <b style="color:${g === 'keiko' ? KEIKO : SANCHEZ}">${name}</b> — ${verb} (${fmtP(p)}).`;
}

function renderChart(history) {
  if (!history || !history.length) return;
  const pts = history.slice(-200);
  const labels = pts.map((p) => {
    const t = new Date(p.t.endsWith('Z') ? p.t : p.t + 'Z');
    return t.toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit' });
  });
  const hi = pts.map((p) => p.keiko.hi), lo = pts.map((p) => p.keiko.lo), med = pts.map((p) => p.keiko.media);
  const ds = [
    { label: 'hi', data: hi, borderColor: 'transparent', backgroundColor: 'rgba(245,135,31,.16)', fill: '+1', pointRadius: 0, tension: .3 },
    { label: 'lo', data: lo, borderColor: 'transparent', backgroundColor: 'transparent', fill: false, pointRadius: 0, tension: .3 },
    { label: 'Keiko proyectada', data: med, borderColor: KEIKO, borderWidth: 2, fill: false, pointRadius: 0, tension: .3 },
  ];
  const opts = {
    responsive: true, maintainAspectRatio: false, animation: false,
    interaction: { mode: 'index', intersect: false },
    scales: {
      y: { grid: { color: '#262c36' }, ticks: { color: '#8b95a4', callback: (v) => v + '%' },
           suggestedMin: 48, suggestedMax: 52 },
      x: { grid: { display: false }, ticks: { color: '#8b95a4', maxTicksLimit: 7 } },
    },
    plugins: {
      legend: { display: false },
      annotation: false,
      tooltip: { filter: (i) => i.dataset.label === 'Keiko proyectada',
        callbacks: { label: (i) => `Keiko: ${i.parsed.y.toFixed(2)}%` } },
    },
  };
  if (chart) { chart.data.labels = labels; chart.data.datasets = ds; chart.update(); }
  else chart = new Chart($('chart'), { type: 'line', data: { labels, datasets: ds }, options: opts });
}

function renderTable(d) {
  lastRegions = d.proyeccion.por_region;
  drawTable();
}

function drawTable() {
  const q = ($('filtro').value || '').toLowerCase().trim();
  const rows = lastRegions
    .filter((r) => r.nombre.toLowerCase().includes(q))
    .sort((a, b) => {
      let x = a[sortKey], y = b[sortKey];
      if (typeof x === 'string') return sortDir * x.localeCompare(y);
      return sortDir * ((x ?? 0) - (y ?? 0));
    });
  const tb = $('tbody');
  tb.innerHTML = rows.map((r) => {
    const lider = r.lider === 'keiko' ? 'Keiko' : 'Sánchez';
    const tagcls = r.lider === 'keiko' ? 'tag-keiko' : 'tag-sanchez';
    const kshare = r.share_keiko_actual;
    return `<tr>
      <td>${r.nombre}${r.exterior ? ' <span class="muted">·ext</span>' : ''}</td>
      <td class="num">${pct(r.pct_actas)}</td>
      <td><span class="tag ${tagcls}">${lider}</span></td>
      <td class="num">${pct(r.margen)}</td>
      <td><div class="minibar ${r.exterior ? 'exterior' : ''}"><i style="width:${kshare}%"></i></div></td>
    </tr>`;
  }).join('');
}

function renderUpdated(d, stale) {
  $('updated').textContent = `Actualizado ${timeAgo(d.timestamp_utc)}`;
  $('liveDot').classList.toggle('stale', !!stale);
  $('metodo').textContent = `Método: ${d.proyeccion.metodo} · error sistemático ±${d.proyeccion.sigma_sistematico_pts} pts · ${nf.format(d.nacional.votos_validos)} votos válidos contados.`;
}

async function tick() {
  try {
    const [latest, history] = await Promise.all([
      getJSON('data/latest.json'),
      getJSON('data/history.json').catch(() => []),
    ]);
    const ageMin = (Date.now() - new Date(latest.timestamp_utc.replace(/Z?$/, 'Z')).getTime()) / 60000;
    window._latest = latest;
    renderHeadline(latest); renderBar(latest); renderProb(latest);
    renderExterior(latest);
    renderTable(latest); renderChart(history); renderUpdated(latest, ageMin > 20);
    if (geo) renderMap(latest);
  } catch (e) {
    console.error(e);
    $('updated').textContent = 'sin conexión con los datos';
    $('liveDot').classList.add('stale');
  }
}

// interacciones
$('filtro').addEventListener('input', drawTable);
document.querySelectorAll('th[data-k]').forEach((th) => th.addEventListener('click', () => {
  const k = th.dataset.k;
  if (sortKey === k) sortDir *= -1; else { sortKey = k; sortDir = k === 'nombre' ? 1 : -1; }
  drawTable();
}));

// ---- mapa coroplético (SVG propio, sin dependencias) --------------------
const norm = (s) => (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase().trim();
let mapPaths = {};

function buildMap() {
  const feats = geo.features;
  let lonMin = 1e9, lonMax = -1e9, latMin = 1e9, latMax = -1e9;
  const eachCoord = (g, fn) => {
    const polys = g.type === 'Polygon' ? [g.coordinates] : g.coordinates;
    polys.forEach((poly) => poly.forEach((ring) => ring.forEach(fn)));
  };
  feats.forEach((f) => eachCoord(f.geometry, ([lo, la]) => {
    if (lo < lonMin) lonMin = lo; if (lo > lonMax) lonMax = lo;
    if (la < latMin) latMin = la; if (la > latMax) latMax = la;
  }));
  const pad = 8, W = 480, S = (W - 2 * pad) / (lonMax - lonMin);
  const H = Math.round((latMax - latMin) * S + 2 * pad);
  const proj = ([lo, la]) => [((lo - lonMin) * S + pad).toFixed(1), ((latMax - la) * S + pad).toFixed(1)];
  const ringPath = (ring) => ring.map((c, i) => (i ? 'L' : 'M') + proj(c).join(' ')).join('') + 'Z';
  const featPath = (g) => {
    const polys = g.type === 'Polygon' ? [g.coordinates] : g.coordinates;
    return polys.map((poly) => poly.map(ringPath).join('')).join('');
  };
  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Mapa del Perú por departamento">`;
  feats.forEach((f, i) => {
    const key = norm(f.properties.NOMBDEP);
    const id = 'dep_' + i;
    mapPaths[key] = id;
    svg += `<path id="${id}" class="map-dep" d="${featPath(f.geometry)}" data-name="${f.properties.NOMBDEP}" fill="#2a313c"></path>`;
  });
  svg += '</svg>';
  $('map').innerHTML = svg;
  $('map').insertAdjacentHTML('beforeend', `<div class="map-tip" id="mapTip"></div>`);
  $('mapCard').insertAdjacentHTML('beforeend',
    `<div class="map-legend"><span><i class="swatch" style="background:${KEIKO}"></i>Keiko</span>
     <span><i class="swatch" style="background:${SANCHEZ}"></i>Sánchez</span>
     <span class="muted">intensidad = margen</span></div>`);

  const tip = $('mapTip');
  $('map').addEventListener('mousemove', (e) => {
    const p = e.target.closest('.map-dep'); if (!p) { tip.style.display = 'none'; return; }
    tip.innerHTML = p._tip || p.dataset.name; tip.style.display = 'block';
    tip.style.left = (e.clientX + 14) + 'px'; tip.style.top = (e.clientY + 14) + 'px';
  });
  $('map').addEventListener('mouseleave', () => { tip.style.display = 'none'; });
  if (window._latest) renderMap(window._latest);
}

function renderMap(d) {
  d.proyeccion.por_region.forEach((r) => {
    if (r.exterior) return;
    const id = mapPaths[norm(r.nombre)];
    if (!id) return;
    const el = document.getElementById(id); if (!el) return;
    const n = r.votos.keiko + r.votos.sanchez;
    if (n === 0) { el.setAttribute('fill', '#2a313c'); return; }
    const color = r.lider === 'keiko' ? KEIKO : SANCHEZ;
    const alpha = (0.32 + Math.min(r.margen, 35) / 35 * 0.63).toFixed(2);
    el.setAttribute('fill', color);
    el.setAttribute('fill-opacity', alpha);
    const lider = r.lider === 'keiko' ? 'Keiko' : 'Sánchez';
    el._tip = `<strong>${r.nombre}</strong><br>${lider} +${pct(r.margen)} · ${pct(r.pct_actas)} actas`;
  });
}

async function initMap() {
  try { geo = await getJSON('data/peru-departamentos.geojson'); buildMap(); }
  catch (e) { console.warn('mapa off:', e); $('mapCard').style.display = 'none'; }
}

tick();
setInterval(tick, POLL_MS);
initMap();
