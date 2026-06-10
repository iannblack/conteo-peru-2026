'use strict';
/* Conteo Perú 2026 — lee los JSON estáticos (mismo origen) y pinta el dashboard.
   No habla con ONPE: eso lo hace el recolector (GitHub Actions). */

const POLL_MS = 60_000;
const KEIKO = '#f5871f', SANCHEZ = '#3b8ee0';
let lastRegions = [], sortKey = 'nombre', sortDir = 1, geo = null;

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
  // Número grande = conteo ACTUAL de ONPE. Debajo, los votos en cifras.
  const v = d.nacional.votos, total = v.keiko + v.sanchez || 1;
  const actK = (v.keiko / total) * 100, actS = (v.sanchez / total) * 100;
  $('pct-keiko').textContent = pct(actK, 2);
  $('pct-sanchez').textContent = pct(actS, 2);
  $('votes-keiko').textContent = `${nf.format(v.keiko)} votos`;
  $('votes-sanchez').textContent = `${nf.format(v.sanchez)} votos`;
  $('actasLabel').textContent = pct(d.nacional.actas_pct);
  const falta = Math.max(0, 100 - d.nacional.actas_pct);
  $('faltaLabel').textContent = `falta ${pct(falta)}`;
}

function renderBar(d) {
  // Barra simple: el reparto del conteo actual. La línea blanca es el 50%.
  const v = d.nacional.votos, total = v.keiko + v.sanchez || 1;
  $('barKeiko').style.width = (v.keiko / total) * 100 + '%';
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
  $('extActas').textContent = `contado: ${pct(escPct, 0)}`;

  // desglose por continente (mayor padrón primero), en palabras simples
  const rows = [...cont].sort((a, b) => b.actas_total - a.actas_total).map((r) => {
    const n = r.votos.keiko + r.votos.sanchez;
    const nombre = r.nombre.replace('Exterior – ', '');
    if (n === 0) {
      return `<div class="ext-cont"><span class="ext-cont-name">${nombre}</span>`
        + `<div class="ext-cont-bar empty"></div>`
        + `<span class="ext-cont-meta">aún sin votos contados</span></div>`;
    }
    const ck = (r.votos.keiko / n) * 100;
    const who = ck >= 50 ? 'Keiko' : 'Sánchez';
    return `<div class="ext-cont"><span class="ext-cont-name">${nombre}</span>`
      + `<div class="ext-cont-bar"><i style="width:${ck}%"></i></div>`
      + `<span class="ext-cont-meta">gana ${who} ${pct(Math.max(ck, 100 - ck), 0)} · contado ${pct(r.pct_actas, 0)}</span></div>`;
  }).join('');
  $('extConts').innerHTML = rows;

  const pend = contabActas > 0 ? Math.round(aggN * (totActas / contabActas - 1)) : 0;
  const lider = kPct >= 50 ? 'Keiko' : 'Sánchez';
  const milesP = pend >= 10000 ? `${nf.format(Math.round(pend / 1000))} mil` : nf.format(pend);
  $('extNote').innerHTML = `Hasta ahora van <strong>${nf.format(aggN)}</strong> votos contados del extranjero y `
    + `faltan unos <strong>${milesP}</strong>. Por ahora ahí gana <strong>${lider}</strong>. `
    + `Estos votos ya están considerados en el pronóstico de arriba.`;
}

function renderProb(d) {
  const pr = d.proyeccion.prob_victoria;
  // probabilidades como "X de cada 100" — mucho más intuitivo que un % suelto
  const pk = Math.round(pr.keiko * 100), ps = 100 - pk;
  $('prob-keiko').style.width = pk + '%';
  $('prob-sanchez').style.width = ps + '%';
  $('probval-keiko').textContent = `${pk} de 100`;
  $('probval-sanchez').textContent = `${ps} de 100`;

  const g = d.proyeccion.ganador_proyectado;
  const name = g === 'keiko' ? 'Keiko Fujimori' : 'Roberto Sánchez';
  const gcol = g === 'keiko' ? KEIKO : SANCHEZ;
  const p = Math.max(pk, ps);
  // SIEMPRE en condicional ("ganaría"): es un pronóstico del final, no el conteo.
  let frase;
  if (p >= 95) frase = 'ganaría la elección, con casi total seguridad';
  else if (p >= 75) frase = 'ganaría la elección cuando se termine de contar — es quien tiene más opciones';
  else if (p >= 60) frase = 'terminaría ganando cuando se cuente todo, aunque aún no es seguro';
  else frase = 'tiene una ligerísima ventaja para el final — sigue siendo un empate';
  $('winner').innerHTML = `<b style="color:${gcol}">${name}</b> ${frase}.`;

  // Cuando el pronóstico contradice el conteo visible en ONPE, hay que explicarlo
  // o parece mentira ("en ONPE va ganando el otro").
  const v = d.nacional.votos;
  const curLider = v.keiko >= v.sanchez ? 'keiko' : 'sanchez';
  const ctr = $('contraste');
  if (curLider !== g) {
    const curName = curLider === 'keiko' ? 'Keiko' : 'Sánchez';
    const curCol = curLider === 'keiko' ? KEIKO : SANCHEZ;
    const gShort = g === 'keiko' ? 'Keiko' : 'Sánchez';
    ctr.innerHTML = `¿Por qué, si en ONPE va adelante <b style="color:${curCol}">${curName}</b>? `
      + `Porque los votos que <b>faltan por contar</b> — sobre todo los del extranjero — `
      + `vienen favoreciendo a <b style="color:${gcol}">${gShort}</b>, y eso voltearía el resultado al final.`;
    ctr.hidden = false;
  } else {
    ctr.hidden = true;
  }

  $('probHint').textContent = `¿Cómo leer esto? Simulamos la elección ${nf.format(d.proyeccion.n_samples)} veces `
    + `con los datos de hoy: ${g === 'keiko' ? 'Keiko' : 'Sánchez'} gana en ${p} de cada 100 escenarios.`;

  // margen en votos, en lenguaje de calle ("42 mil votos")
  const mv = d.proyeccion.margen_votos;
  if (mv) {
    const lname = mv.lider === 'keiko' ? 'Keiko' : 'Sánchez';
    const lcol = mv.lider === 'keiko' ? KEIKO : SANCHEZ;
    const miles = (x) => (Math.abs(x) >= 10000 ? `${nf.format(Math.round(Math.abs(x) / 1000))} mil` : nf.format(Math.abs(x)));
    const cruzaCero = mv.lo < 0 && mv.hi > 0;
    let extra = '';
    if (cruzaCero) {
      extra = ` <span class="muted">Pero ojo: por lo apretado del conteo, todavía podría ganar cualquiera de los dos.</span>`;
    }
    $('margenVotos').innerHTML = `Ventaja más probable: <b style="color:${lcol}">unos ${miles(mv.abs_mediana)} votos</b> a favor de ${lname}.${extra}`;
  }

  // resultado final estimado, con su rango en palabras simples
  const proj = d.proyeccion.proyeccion_2via_pct;
  $('finalEst').innerHTML = `Resultado final estimado: `
    + `<b style="color:${KEIKO}">Keiko ${pct(proj.keiko.media)}</b> — `
    + `<b style="color:${SANCHEZ}">Sánchez ${pct(proj.sanchez.media)}</b> `
    + `<span class="muted">(Keiko podría terminar entre ${pct(proj.keiko.lo)} y ${pct(proj.keiko.hi)}).</span>`;
}

// ---- sección 4: qué falta para conocer al ganador -------------------------
// La pregunta del momento: cuántos votos faltan, DÓNDE están, y si alcanzan
// para voltear el resultado. Todo en cifras simples y palabras.

function nombreDe(l) { return l === 'keiko' ? 'Keiko' : 'Sánchez'; }
function colorDe(l) { return l === 'keiko' ? KEIKO : SANCHEZ; }
const miles = (x) => (Math.abs(x) >= 10000 ? `${nf.format(Math.round(Math.abs(x) / 1000))} mil` : nf.format(Math.abs(x)));

function renderFalta(d) {
  const nac = d.nacional;
  const vpa = d.proyeccion.votos_por_acta_nacional || 200;
  const actasPend = Math.max(0, nac.actas_total - nac.actas_contabilizadas);
  const votosPend = Math.round(actasPend * vpa);
  const v = nac.votos;
  const diff = Math.abs(v.keiko - v.sanchez);
  const liderC = v.keiko >= v.sanchez ? 'keiko' : 'sanchez';

  $('faltaBig').innerHTML = `Faltan por contar <b>${nf.format(actasPend)}</b> actas — `
    + `unos <b>${miles(votosPend)} votos</b>.`;

  let verdict;
  if (votosPend > diff * 2) {
    verdict = `La ventaja de ${nombreDe(liderC)} en los votos contados es de apenas `
      + `<strong>${miles(diff)} votos</strong>, y falta mucho más que eso por contar: `
      + `<strong>la elección todavía puede ir para cualquiera de los dos.</strong>`;
  } else if (votosPend > diff) {
    verdict = `La ventaja de ${nombreDe(liderC)} es de ${miles(diff)} votos y queda poco más que eso `
      + `por contar: <strong>todavía podría voltearse, pero cada vez es más difícil.</strong>`;
  } else {
    verdict = `La ventaja de ${nombreDe(liderC)} (${miles(diff)} votos) ya es mayor que todo lo que `
      + `falta por contar (${miles(votosPend)}): <strong>el resultado está prácticamente definido.</strong>`;
  }
  $('faltaVerdict').innerHTML = verdict;

  // dónde está lo pendiente: extranjero como un bloque + departamentos
  const ext = d.regiones.filter((r) => r.exterior);
  const extPend = ext.reduce((a, r) => a + (r.actas_total - r.actas_contabilizadas), 0);
  const extTot = ext.reduce((a, r) => a + r.actas_total, 0);
  const extK = ext.reduce((a, r) => a + r.votos.keiko, 0);
  const extS = ext.reduce((a, r) => a + r.votos.sanchez, 0);
  const items = d.regiones.filter((r) => !r.exterior).map((r) => ({
    nombre: r.nombre,
    pend: r.actas_total - r.actas_contabilizadas,
    pctPend: Math.max(0, 100 - r.pct_actas),
    k: r.votos.keiko, s: r.votos.sanchez,
  }));
  if (extPend > 0) {
    items.push({ nombre: 'El extranjero', pend: extPend,
      pctPend: extTot ? (100 * extPend) / extTot : 0, k: extK, s: extS });
  }
  const top = items.filter((i) => i.pend > 0).sort((a, b) => b.pend - a.pend).slice(0, 5);
  const maxPend = top[0]?.pend || 1;

  $('faltaList').innerHTML = top.map((i) => {
    const n = i.k + i.s;
    const l = i.k >= i.s ? 'keiko' : 'sanchez';
    const quien = n
      ? `ahí viene ganando <b style="color:${colorDe(l)}">${nombreDe(l)}</b> (${pct((100 * Math.max(i.k, i.s)) / n, 0)})`
      : `<span class="muted">aún no se sabe hacia dónde se inclina</span>`;
    return `<div class="fl-row">
      <div class="fl-top"><b>${i.nombre}</b>
        <span class="muted">faltan ${nf.format(i.pend)} actas (${i.pctPend.toFixed(0)}% sin contar)</span></div>
      <div class="fl-bar"><i style="width:${((100 * i.pend) / maxPend).toFixed(1)}%; background:${n ? colorDe(l) : '#525c6a'}"></i></div>
      <div class="fl-quien">${quien}</div>
    </div>`;
  }).join('');
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
    const sinVotos = (r.votos.keiko + r.votos.sanchez) === 0;
    const lider = r.lider === 'keiko' ? 'Keiko' : 'Sánchez';
    const tagcls = r.lider === 'keiko' ? 'tag-keiko' : 'tag-sanchez';
    const kshare = r.share_keiko_actual;
    // Resultado = los dos porcentajes en números + la barra debajo como refuerzo
    const resultado = sinVotos
      ? `<span class="muted">aún sin votos contados</span>`
      : `<div class="rep">
           <div class="rep-nums"><span class="rk">${pct(kshare, 1)}</span><span class="rs">${pct(100 - kshare, 1)}</span></div>
           <div class="minibar ${r.exterior ? 'exterior' : ''}"><i style="width:${kshare}%"></i></div>
         </div>`;
    return `<tr>
      <td>${r.exterior ? r.nombre.replace('Exterior – ', '') + ' <span class="tag tag-ext">extranjero</span>' : r.nombre}</td>
      <td class="num">${pct(r.pct_actas)}</td>
      <td>${sinVotos ? '<span class="muted">—</span>' : `<span class="tag ${tagcls}">${lider}</span>`}</td>
      <td>${resultado}</td>
    </tr>`;
  }).join('');
}

function renderUpdated(d, stale) {
  $('updated').textContent = `Actualizado ${timeAgo(d.timestamp_utc)}`;
  $('liveDot').classList.toggle('stale', !!stale);
  $('metodo').textContent = `Pronóstico calculado con ${nf.format(d.nacional.votos_validos)} votos ya contados · `
    + `se actualiza solo cada 5 minutos · última data de ONPE: ${timeAgo(d.timestamp_utc)}.`;
}

async function tick() {
  try {
    const latest = await getJSON('data/latest.json');
    const ageMin = (Date.now() - new Date(latest.timestamp_utc.replace(/Z?$/, 'Z')).getTime()) / 60000;
    window._latest = latest;
    renderHeadline(latest); renderBar(latest); renderProb(latest);
    renderExterior(latest); renderFalta(latest);
    renderTable(latest); renderUpdated(latest, ageMin > 20);
    if (geo) renderMap(latest);
    if (worldGeo) renderWorldMap(latest);
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
    `<div class="map-legend"><span><i class="swatch" style="background:${KEIKO}"></i>gana Keiko</span>
     <span><i class="swatch" style="background:${SANCHEZ}"></i>gana Sánchez</span>
     <span class="muted">color más intenso = más ventaja</span></div>`);

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
    el._tip = `<strong>${r.nombre}</strong><br>va ganando ${lider} por ${pct(r.margen)}<br>votos contados: ${pct(r.pct_actas)}`;
  });
}

async function initMap() {
  try { geo = await getJSON('data/peru-departamentos.geojson'); buildMap(); }
  catch (e) { console.warn('mapa off:', e); $('mapCard').style.display = 'none'; }
}

// ---- mapa mundial del voto exterior (por país, ISO3) --------------------
let worldGeo = null, worldPaths = {};

async function initWorldMap() {
  try { worldGeo = await getJSON('data/world-countries.geojson'); buildWorldMap(); }
  catch (e) { console.warn('world map off:', e); $('worldCard').style.display = 'none'; }
}

function buildWorldMap() {
  const feats = worldGeo.features.filter((f) => f.id !== 'ATA');  // sin Antártida
  const each = (g, fn) => {
    const ps = g.type === 'Polygon' ? [g.coordinates] : g.coordinates;
    ps.forEach((p) => p.forEach((r) => r.forEach(fn)));
  };
  const lonMin = -180, lonMax = 180;
  let latMin = 1e9, latMax = -1e9;
  feats.forEach((f) => each(f.geometry, ([, la]) => {
    if (la < -58) return; if (la < latMin) latMin = la; if (la > latMax) latMax = la;
  }));
  const pad = 4, W = 720, S = (W - 2 * pad) / (lonMax - lonMin);
  const H = Math.round((latMax - latMin) * S + 2 * pad);
  const proj = ([lo, la]) => [
    ((lo - lonMin) * S + pad).toFixed(1),
    ((latMax - Math.max(la, latMin)) * S + pad).toFixed(1),
  ];
  const ring = (r) => r.map((c, i) => (i ? 'L' : 'M') + proj(c).join(' ')).join('') + 'Z';
  const path = (g) => {
    const ps = g.type === 'Polygon' ? [g.coordinates] : g.coordinates;
    return ps.map((p) => p.map(ring).join('')).join('');
  };
  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Mapa mundial del voto exterior">`;
  feats.forEach((f) => {
    const id = 'w_' + f.id; worldPaths[f.id] = id;
    svg += `<path id="${id}" class="map-dep" d="${path(f.geometry)}" fill="#242a33"></path>`;
  });
  svg += '</svg>';
  $('worldMap').innerHTML = svg;
  $('worldMap').insertAdjacentHTML('beforeend', `<div class="map-tip" id="worldTip"></div>`);
  const tip = $('worldTip');
  $('worldMap').addEventListener('mousemove', (e) => {
    const p = e.target.closest('.map-dep');
    if (!p || !p._tip) { tip.style.display = 'none'; return; }
    tip.innerHTML = p._tip; tip.style.display = 'block';
    tip.style.left = (e.clientX + 14) + 'px'; tip.style.top = (e.clientY + 14) + 'px';
  });
  $('worldMap').addEventListener('mouseleave', () => { tip.style.display = 'none'; });
  if (window._latest) renderWorldMap(window._latest);
}

function renderWorldMap(d) {
  Object.values(worldPaths).forEach((id) => {
    const el = document.getElementById(id);
    if (el) { el.setAttribute('fill', '#242a33'); el.removeAttribute('fill-opacity'); el._tip = null; }
  });
  (d.exterior_paises || []).forEach((p) => {
    const id = worldPaths[p.iso3]; if (!id) return;
    const el = document.getElementById(id); if (!el) return;
    const n = p.votos.keiko + p.votos.sanchez; if (!n) return;
    const ck = (p.votos.keiko / n) * 100;
    const lider = ck >= 50 ? 'keiko' : 'sanchez';
    const margen = Math.abs(2 * ck - 100);
    el.setAttribute('fill', lider === 'keiko' ? KEIKO : SANCHEZ);
    el.setAttribute('fill-opacity', (0.4 + Math.min(margen, 40) / 40 * 0.55).toFixed(2));
    el._tip = `<strong>${p.nombre}</strong><br>va ganando ${lider === 'keiko' ? 'Keiko' : 'Sánchez'} con ${pct(Math.max(ck, 100 - ck))}<br>${nf.format(n)} votos contados`;
  });
  // chips resumen por continente
  const cont = (d.regiones || []).filter((x) => x.exterior);
  $('worldConts').innerHTML = [...cont].sort((a, b) => b.actas_total - a.actas_total).map((r) => {
    const n = r.votos.keiko + r.votos.sanchez;
    const nombre = r.nombre.replace('Exterior – ', '');
    if (!n) return `<span class="wchip"><b>${nombre}</b> <span class="muted">sin votos aún</span></span>`;
    const ck = (r.votos.keiko / n) * 100;
    const who = ck >= 50 ? 'Keiko' : 'Sánchez';
    const col = ck >= 50 ? KEIKO : SANCHEZ;
    return `<span class="wchip"><b>${nombre}</b> <span style="color:${col}">gana ${who} ${pct(Math.max(ck, 100 - ck), 0)}</span></span>`;
  }).join('');
}

tick();
setInterval(tick, POLL_MS);
initMap();
initWorldMap();
