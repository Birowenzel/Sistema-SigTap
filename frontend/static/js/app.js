/* ==================================================================== *
 * SIGTAP Local — frontend (vanilla JS, sem build step)
 * ==================================================================== */
"use strict";

const API = "/api";
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

// ---- Estado da consulta -------------------------------------------------
const state = {
  q: "", filters: {}, page: 1, page_size: 50,
  sort_by: "no_procedimento", sort_dir: "asc",
  total: 0, pages: 0, favoritos: new Set(),
  compact: localStorage.getItem("density") === "compact",
};

// Rótulos dos filtros (key -> {label, values: {value: label}}) para os chips
const FILTER_META = {};
const LOGO = "/static/img/logo.png";

// Colunas disponíveis na grade (chave, rótulo, tipo)
const COLUMNS = [
  { key: "co_procedimento", label: "Código", type: "code" },
  { key: "no_procedimento", label: "Nome", type: "text" },
  { key: "no_grupo", label: "Grupo", type: "text" },
  { key: "no_sub_grupo", label: "Subgrupo", type: "text" },
  { key: "complexidade", label: "Complexidade", type: "text" },
  { key: "sexo", label: "Sexo", type: "text" },
  { key: "no_financiamento", label: "Financiamento", type: "text" },
  { key: "vl_sh", label: "V. Hosp. (SH)", type: "money" },
  { key: "vl_sa", label: "V. SADT (SA)", type: "money" },
  { key: "vl_sp", label: "V. Prof. (SP)", type: "money" },
  { key: "vl_total", label: "V. Total", type: "money" },
];
const DEFAULT_COLS = ["co_procedimento", "no_procedimento", "no_grupo",
  "complexidade", "vl_sh", "vl_sp", "vl_total"];

// ---- Utilidades ---------------------------------------------------------
const brl = (v) => (v === null || v === undefined || v === "")
  ? "" : Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

async function api(path, opts) {
  const r = await fetch(API + path, opts);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.statusText);
  return r.json();
}

function visibleColumns() {
  const saved = JSON.parse(localStorage.getItem("cols") || "null");
  return saved || DEFAULT_COLS;
}
function setVisibleColumns(cols) { localStorage.setItem("cols", JSON.stringify(cols)); }

// ---- Ícones SVG (estilo linha, herdam a cor via currentColor) -----------
const ICON_PATHS = {
  total:   '<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2.2"/><path d="M6 12h.01M18 12h.01"/>',
  hosp:    '<path d="M18 22V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v18"/><path d="M4 22h16"/><path d="M12 7v6M9 10h6"/>',
  sadt:    '<path d="M22 12h-4l-3 8L9 4l-3 8H2"/>',
  prof:    '<path d="M4.5 2.5V8a5.5 5.5 0 0 0 11 0V2.5"/><path d="M10 13.5v3a4 4 0 0 0 8 0v-1"/><circle cx="19" cy="14" r="2"/>',
  list:    '<path d="M8 6h13M8 12h13M8 18h13"/><path d="M3 6h.01M3 12h.01M3 18h.01"/>',
};
function icon(name, size = 20) {
  return `<svg class="ico" viewBox="0 0 24 24" width="${size}" height="${size}" fill="none"
    stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICON_PATHS[name] || ""}</svg>`;
}

// ---- Pílulas coloridas --------------------------------------------------
function pillComplexidade(txt) {
  if (!txt) return "";
  const t = txt.toLowerCase();
  let cls = "pill-gray";
  if (t.includes("alta")) cls = "pill-red";
  else if (t.includes("média") || t.includes("media")) cls = "pill-amber";
  else if (t.includes("básica") || t.includes("basica")) cls = "pill-green";
  return `<span class="pill ${cls}">${txt}</span>`;
}
function pillFinanciamento(txt) {
  if (!txt) return "";
  const t = txt.toLowerCase();
  let cls = "pill-gray";
  if (t.includes("faec")) cls = "pill-blue";
  else if (t.includes("alta") || t.includes("mac")) cls = "pill-amber";
  else if (t.includes("básica") || t.includes("basica") || t.includes("pab")) cls = "pill-green";
  return `<span class="pill ${cls}">${txt}</span>`;
}

// ---- Query string dos filtros ------------------------------------------
function queryParams(extra = {}) {
  const p = new URLSearchParams({
    q: state.q, page: state.page, page_size: state.page_size,
    sort_by: state.sort_by, sort_dir: state.sort_dir, ...extra,
  });
  for (const [k, v] of Object.entries(state.filters)) if (v) p.set(k, v);
  return p.toString();
}

/* ==================================================================== *
 * Consulta / grade
 * ==================================================================== */
function renderSkeleton() {
  const nCols = visibleColumns().length + 1;
  const cell = `<td><div class="skel"></div></td>`;
  $("#grid-body").innerHTML = Array.from({ length: 8 }, () =>
    `<tr class="skel-row">${cell.repeat(nCols)}</tr>`).join("");
}

async function doSearch() {
  renderActiveChips();
  renderSkeleton();
  let data;
  try { data = await api("/search?" + queryParams()); }
  catch (e) { $("#grid-body").innerHTML = `<tr><td colspan="20">Erro: ${e.message}</td></tr>`; return; }

  state.total = data.total; state.pages = data.pages;
  if (data.empty_db) {
    $("#grid-body").innerHTML = `<tr><td colspan="20"><div class="empty-hero">
      <img src="${LOGO}" alt="">
      <h2>Base ainda não importada</h2>
      <p>Para começar, importe a tabela oficial do SIGTAP. O sistema baixa a
         competência mais recente do DATASUS ou aceita o ZIP oficial.</p>
      <button class="accent big" onclick="switchView('atualizar')">⟳ Atualizar SIGTAP</button>
      </div></td></tr>`;
    $("#result-count").textContent = "";
    $("#pagination").innerHTML = ""; $("#grid-head").innerHTML = "";
    return;
  }
  renderHead(); renderRows(data.rows);
  $("#result-count").innerHTML =
    `${icon("list", 16)}<span>${data.total.toLocaleString("pt-BR")} procedimento(s)</span>`;
  renderPagination();
}

/* Chips de busca/filtros ativos */
function renderActiveChips() {
  const box = $("#active-filters");
  const chips = [];
  if (state.q) chips.push(`<span class="chip">🔍 "${state.q}"
    <button data-clear="q" title="Remover">✕</button></span>`);
  for (const [k, v] of Object.entries(state.filters)) {
    if (!v) continue;
    const meta = FILTER_META[k];
    const label = meta ? `${meta.label}: ${meta.values[v] || v}` : `${k}: ${v}`;
    chips.push(`<span class="chip">${label}
      <button data-clear="${k}" title="Remover">✕</button></span>`);
  }
  box.innerHTML = chips.length
    ? chips.join("") + `<span class="chip clear-all" data-clear="all">Limpar tudo</span>`
    : "";
  $$("#active-filters [data-clear]").forEach(b => b.onclick = () => {
    const key = b.dataset.clear;
    if (key === "q") { $("#q").value = ""; state.q = ""; }
    else if (key === "all") {
      state.q = ""; $("#q").value = ""; state.filters = {};
      $$("#filters select").forEach(s => s.value = "");
    } else {
      state.filters[key] = ""; const sel = $(`#filters select[data-key="${key}"]`);
      if (sel) sel.value = "";
    }
    state.page = 1; doSearch();
  });
}

function renderHead() {
  const cols = visibleColumns().map(k => COLUMNS.find(c => c.key === k)).filter(Boolean);
  const head = $("#grid-head");
  head.innerHTML = `<th style="width:34px"></th>` + cols.map(c => {
    const arrow = state.sort_by === c.key ? (state.sort_dir === "asc" ? "▲" : "▼") : "";
    return `<th data-key="${c.key}">${c.label} <span class="arrow">${arrow}</span></th>`;
  }).join("");
  $$("#grid-head th[data-key]").forEach(th => th.onclick = () => {
    const k = th.dataset.key;
    if (state.sort_by === k) state.sort_dir = state.sort_dir === "asc" ? "desc" : "asc";
    else { state.sort_by = k; state.sort_dir = "asc"; }
    state.page = 1; doSearch();
  });
}

function renderRows(rows) {
  const cols = visibleColumns().map(k => COLUMNS.find(c => c.key === k)).filter(Boolean);
  const body = $("#grid-body");
  $("#grid").classList.toggle("compact", state.compact);
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="20"><div class="empty-state">
      Nenhum procedimento encontrado. Tente outro termo ou limpe os filtros.</div></td></tr>`;
    return;
  }
  body.innerHTML = rows.map(r => {
    const fav = state.favoritos.has(r.co_procedimento);
    const cells = cols.map(c => {
      let v = r[c.key];
      if (c.type === "money") return `<td class="num">${brl(v)}</td>`;
      if (c.type === "code") return `<td class="code">${v ?? ""}</td>`;
      if (c.key === "complexidade") return `<td>${pillComplexidade(v)}</td>`;
      if (c.key === "no_financiamento") return `<td>${pillFinanciamento(v)}</td>`;
      return `<td>${v ?? ""}</td>`;
    }).join("");
    return `<tr data-code="${r.co_procedimento}">
      <td><span class="star ${fav ? "on" : ""}" data-code="${r.co_procedimento}">★</span></td>
      ${cells}</tr>`;
  }).join("");

  $$("#grid-body tr").forEach(tr => tr.onclick = (e) => {
    if (e.target.classList.contains("star")) return;
    openDetail(tr.dataset.code);
  });
  $$("#grid-body .star").forEach(s => s.onclick = (e) => {
    e.stopPropagation(); toggleFav(s.dataset.code, s);
  });
}

function renderPagination() {
  const box = $("#pagination"); box.innerHTML = "";
  if (state.pages <= 1) return;
  const mk = (label, page, opts = {}) => {
    const b = document.createElement("button");
    b.textContent = label;
    if (opts.active) b.classList.add("active");
    if (opts.disabled) b.disabled = true;
    b.onclick = () => { state.page = page; doSearch(); window.scrollTo(0, 0); };
    box.appendChild(b);
  };
  mk("«", 1, { disabled: state.page === 1 });
  mk("‹", Math.max(1, state.page - 1), { disabled: state.page === 1 });
  const from = Math.max(1, state.page - 2), to = Math.min(state.pages, state.page + 2);
  for (let p = from; p <= to; p++) mk(p, p, { active: p === state.page });
  mk("›", Math.min(state.pages, state.page + 1), { disabled: state.page === state.pages });
  mk("»", state.pages, { disabled: state.page === state.pages });
  const info = document.createElement("span");
  info.className = "muted"; info.textContent = `Página ${state.page} de ${state.pages}`;
  box.appendChild(info);
}

/* ==================================================================== *
 * Detalhe (modal)
 * ==================================================================== */
async function openDetail(code) {
  const modal = $("#modal"), content = $("#modal-content");
  content.innerHTML = "Carregando…"; modal.classList.remove("hidden");
  let d;
  try { d = await api("/procedimento/" + code); }
  catch (e) { content.innerHTML = "Erro: " + e.message; return; }

  const f = d.flat, L = d.labels;
  const fav = state.favoritos.has(code);
  const val = (v) => v ?? "—";

  const infoRows = [
    ["descricao", f.descricao], ["no_grupo", f.no_grupo], ["no_sub_grupo", f.no_sub_grupo],
    ["no_forma_organizacao", f.no_forma_organizacao], ["complexidade", f.complexidade],
    ["sexo", f.sexo], ["qt_maxima_execucao", f.qt_maxima_execucao],
    ["qt_dias_permanencia", f.qt_dias_permanencia], ["qt_tempo_permanencia", f.qt_tempo_permanencia],
    ["qt_pontos", f.qt_pontos], ["vl_idade_minima", f.vl_idade_minima],
    ["vl_idade_maxima", f.vl_idade_maxima], ["no_financiamento", f.no_financiamento],
    ["no_rubrica", f.no_rubrica], ["instrumentos_registro", f.instrumentos_registro],
    ["modalidades", f.modalidades], ["dt_competencia", f.dt_competencia],
  ].filter(([, v]) => v !== null && v !== undefined && v !== "")
   .map(([k, v]) => `<tr><td>${L[k] || k}</td><td>${v}</td></tr>`).join("");

  const sections = d.sections.map(sec => {
    const cols = sec.columns.filter(c => c !== "co_procedimento");
    const head = cols.map(c => `<th>${c}</th>`).join("");
    const body = sec.rows.map(row =>
      "<tr>" + cols.map(c => `<td>${row[c] ?? ""}</td>`).join("") + "</tr>").join("");
    return `<div class="section"><h3>${sec.title} (${sec.rows.length})</h3>
      <div class="table-wrap"><table><thead><tr>${head}</tr></thead>
      <tbody>${body}</tbody></table></div></div>`;
  }).join("");

  content.innerHTML = `
    <div class="code">${f.co_procedimento}</div>
    <h2>${f.no_procedimento || ""}</h2>
    <div class="badges">
      <button class="badge ${fav ? "on" : ""}" id="modal-fav">★ ${fav ? "Favoritado" : "Favoritar"}</button>
      <span class="badge">${f.no_grupo || ""}</span>
      ${pillComplexidade(f.complexidade)}
      ${pillFinanciamento(f.no_financiamento)}
    </div>
    <div class="val-grid">
      <div class="val-box total"><span class="vicon">${icon("total")}</span><small>Valor Total</small><b>${brl(f.vl_total)}</b></div>
      <div class="val-box"><span class="vicon">${icon("hosp")}</span><small>Hospitalar (SH)</small><b>${brl(f.vl_sh)}</b></div>
      <div class="val-box"><span class="vicon">${icon("sadt")}</span><small>SADT / Ambul. (SA)</small><b>${brl(f.vl_sa)}</b></div>
      <div class="val-box"><span class="vicon">${icon("prof")}</span><small>Profissional (SP)</small><b>${brl(f.vl_sp)}</b></div>
    </div>
    <table class="info-table">${infoRows}</table>
    ${sections}`;

  $("#modal-fav").onclick = () => toggleFav(code).then(() => openDetail(code));
}

/* ==================================================================== *
 * Favoritos
 * ==================================================================== */
async function loadFavoritos() {
  const list = await api("/favoritos");
  state.favoritos = new Set(list.map(f => f.co_procedimento));
  return list;
}
async function toggleFav(code, starEl) {
  if (state.favoritos.has(code)) {
    await api("/favoritos/" + code, { method: "DELETE" });
    state.favoritos.delete(code);
  } else {
    await api("/favoritos", { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ co_procedimento: code }) });
    state.favoritos.add(code);
  }
  if (starEl) starEl.classList.toggle("on");
}
async function renderFavoritos() {
  const list = await loadFavoritos();
  const box = $("#fav-list");
  if (!list.length) { box.innerHTML = `<div class="empty-state">Nenhum favorito ainda.</div>`; return; }
  box.innerHTML = list.map(f => `<div class="card" data-code="${f.co_procedimento}">
    <div class="code">${f.co_procedimento}</div>
    <h4>${f.no_procedimento || ""}</h4>
    <div class="muted">${brl(f.vl_total)}</div></div>`).join("");
  $$("#fav-list .card").forEach(c => c.onclick = () => openDetail(c.dataset.code));
}

/* ==================================================================== *
 * Histórico
 * ==================================================================== */
async function renderHistorico() {
  const list = await api("/historico");
  const box = $("#hist-list");
  if (!list.length) { box.innerHTML = `<div class="empty-state">Sem histórico.</div>`; return; }
  box.innerHTML = list.map(h => `<div class="hist-item" data-q="${encodeURIComponent(h.termo)}">
    <span>🔍 <b>${h.termo}</b> <span class="muted">${h.filtros || ""}</span></span>
    <span class="muted">${h.buscado_em}</span></div>`).join("");
  $$("#hist-list .hist-item").forEach(i => i.onclick = () => {
    $("#q").value = decodeURIComponent(i.dataset.q);
    switchView("consulta"); triggerSearch();
  });
}

/* ==================================================================== *
 * Comparar versões
 * ==================================================================== */
async function loadVersoes() {
  const vs = await api("/versoes");
  const opts = vs.map(v => `<option value="${v.id}">#${v.id} — comp. ${v.competencia || "?"} (${v.importado_em})</option>`).join("");
  $("#cmp-a").innerHTML = opts; $("#cmp-b").innerHTML = opts;
  if (vs.length >= 2) { $("#cmp-a").value = vs[1].id; $("#cmp-b").value = vs[0].id; }
}
async function doCompare() {
  const a = $("#cmp-a").value, b = $("#cmp-b").value;
  const box = $("#cmp-result"); box.innerHTML = "Comparando…";
  let d; try { d = await api(`/compare?a=${a}&b=${b}`); }
  catch (e) { box.innerHTML = "Erro: " + e.message; return; }
  const tbl = (title, rows, cols) => `<div class="section"><h3>${title} (${rows.length})</h3>
    <div class="table-wrap"><table><thead><tr>${cols.map(c => `<th>${c}</th>`).join("")}</tr></thead>
    <tbody>${rows.map(r => "<tr>" + cols.map(c => `<td>${r[c] ?? ""}</td>`).join("") + "</tr>").join("")}
    </tbody></table></div></div>`;
  const chg = d.alterados.map(c => ({
    co_procedimento: c.co_procedimento, no_procedimento: c.no_procedimento,
    mudancas: Object.entries(c.mudancas).map(([k, v]) =>
      `${k}: ${v.de} → ${v.para}`).join("; "),
  }));
  box.innerHTML = `<div class="cmp-summary">
      <div class="cmp-badge add"><b>${d.resumo.adicionados}</b>adicionados</div>
      <div class="cmp-badge del"><b>${d.resumo.removidos}</b>removidos</div>
      <div class="cmp-badge chg"><b>${d.resumo.alterados}</b>alterados</div></div>
    ${tbl("Adicionados", d.adicionados, ["co_procedimento", "no_procedimento", "vl_total"])}
    ${tbl("Removidos", d.removidos, ["co_procedimento", "no_procedimento", "vl_total"])}
    ${tbl("Alterados", chg, ["co_procedimento", "no_procedimento", "mudancas"])}`;
}

/* ==================================================================== *
 * Relatórios
 * ==================================================================== */
async function runReport(name) {
  const box = $("#rep-result"); box.innerHTML = "Gerando…";
  let d; try { d = await api("/relatorio/" + name); }
  catch (e) { box.innerHTML = "Erro: " + e.message; return; }
  const money = new Set(["vl_total", "vl_sh", "vl_sa", "vl_sp", "soma_total"]);
  box.innerHTML = `<div class="toolbar"><h3>${d.title}</h3><div class="spacer"></div>
      <div class="export"><span class="muted">Exportar:</span>
      <button data-f="xlsx">Excel</button><button data-f="csv">CSV</button><button data-f="pdf">PDF</button></div></div>
    <div class="table-wrap"><table><thead><tr>${d.columns.map(c => `<th>${c}</th>`).join("")}</tr></thead>
    <tbody>${d.rows.map(r => "<tr>" + d.columns.map(c =>
      `<td class="${money.has(c) ? "num" : ""}">${money.has(c) ? brl(r[c]) : (r[c] ?? "")}</td>`).join("") + "</tr>").join("")}
    </tbody></table></div>`;
  $$("#rep-result .export button").forEach(b => b.onclick = () =>
    window.location = `${API}/export?source=relatorio&name=${name}&fmt=${b.dataset.f}`);
}

/* ==================================================================== *
 * Competências (exportar qualquer mês em planilha)
 * ==================================================================== */
async function downloadFile(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).error || msg; } catch (_) {}
    throw new Error(msg);
  }
  const blob = await r.blob();
  const cd = r.headers.get("Content-Disposition") || "";
  const m = cd.match(/filename="?([^"]+)"?/);
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = m ? m[1] : "sigtap.xlsx";
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}

async function renderCompetencias() {
  const box = $("#comp-list");
  box.innerHTML = `<div class="muted">Carregando…</div>`;
  let data;
  try { data = await api("/competencias"); }
  catch (e) { box.innerHTML = "Erro: " + e.message; return; }
  $("#comp-folder").textContent = data.pasta;
  if (!data.itens.length) {
    box.innerHTML = `<div class="empty-state">Nenhum ZIP de competência encontrado.
      Coloque os arquivos na pasta indicada acima, ou use o botão
      "Exportar um ZIP do computador".</div>`;
    return;
  }
  box.innerHTML = data.itens.map(c => `<div class="comp-card">
      <div class="comp-month">${c.label}</div>
      <div class="comp-file muted" title="${c.filename}">${c.filename}</div>
      <div class="muted comp-meta">${c.tamanho_mb} MB · competência ${c.competencia}</div>
      <div class="comp-actions">
        <button class="accent" data-file="${c.filename}" data-fmt="xlsx">${icon("total", 15)} Excel</button>
        <button data-file="${c.filename}" data-fmt="csv">CSV</button>
      </div></div>`).join("");
  $$("#comp-list button").forEach(b => b.onclick = () =>
    exportCompetencia(b.dataset.file, b.dataset.fmt, b));
}

async function exportCompetencia(file, fmt, btn) {
  const status = $("#comp-status");
  const label = btn ? btn.innerHTML : "";
  if (btn) { btn.disabled = true; btn.textContent = "Gerando…"; }
  status.className = "comp-status working";
  status.textContent = `Gerando planilha de ${file}… isso leva alguns segundos.`;
  try {
    await downloadFile(`${API}/competencias/export?file=${encodeURIComponent(file)}&fmt=${fmt}`);
    status.className = "comp-status ok";
    status.textContent = `✓ Planilha de ${file} gerada e baixada.`;
  } catch (e) {
    status.className = "comp-status err";
    status.textContent = "Erro: " + e.message;
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = label; }
  }
}

async function exportCompetenciaUpload(file, fmt) {
  const status = $("#comp-status");
  status.className = "comp-status working";
  status.textContent = `Gerando planilha de ${file.name}… isso leva alguns segundos.`;
  const fd = new FormData(); fd.append("file", file); fd.append("fmt", fmt);
  try {
    await downloadFile(`${API}/competencias/export-upload`, { method: "POST", body: fd });
    status.className = "comp-status ok";
    status.textContent = `✓ Planilha de ${file.name} gerada e baixada.`;
  } catch (e) {
    status.className = "comp-status err";
    status.textContent = "Erro: " + e.message;
  }
}

/* ==================================================================== *
 * Atualização
 * ==================================================================== */
let statusTimer = null;
function pollStatus() {
  clearInterval(statusTimer);
  statusTimer = setInterval(async () => {
    const s = await api("/status");
    $("#update-log").textContent = s.log.join("\n");
    $("#update-log").scrollTop = $("#update-log").scrollHeight;
    if (!s.running) {
      clearInterval(statusTimer);
      if (s.result) { loadMeta(); loadFilters(); }
    }
  }, 800);
}
async function doUpdate() {
  $("#update-log").textContent = "Iniciando…";
  try { await api("/atualizar", { method: "POST" }); pollStatus(); }
  catch (e) { $("#update-log").textContent = "Erro: " + e.message; }
}
async function doImport(file) {
  const fd = new FormData(); fd.append("file", file);
  $("#update-log").textContent = "Enviando ZIP…";
  try { await api("/importar", { method: "POST", body: fd }); pollStatus(); }
  catch (e) { $("#update-log").textContent = "Erro: " + e.message; }
}

/* ==================================================================== *
 * Filtros laterais / colunas
 * ==================================================================== */
async function loadFilters() {
  const groups = await api("/filters");
  const box = $("#filters");
  box.innerHTML = groups.map(g => `<div class="filter-group">
    <label>${g.label}</label>
    <select data-key="${g.key}"><option value="">Todos</option>
    ${g.options.map(o => `<option value="${o.value}">${o.label}</option>`).join("")}</select>
  </div>`).join("");
  // guarda rótulos para os chips de filtros ativos
  groups.forEach(g => {
    FILTER_META[g.key] = { label: g.label, values: {} };
    g.options.forEach(o => { FILTER_META[g.key].values[o.value] = o.label; });
  });
  $$("#filters select").forEach(sel => sel.onchange = () => {
    state.filters[sel.dataset.key] = sel.value; state.page = 1; doSearch();
  });
}
function renderColConfig() {
  const vis = new Set(visibleColumns());
  $("#col-config").innerHTML = COLUMNS.map(c =>
    `<label><input type="checkbox" data-key="${c.key}" ${vis.has(c.key) ? "checked" : ""}> ${c.label}</label>`
  ).join("");
  $$("#col-config input").forEach(cb => cb.onchange = () => {
    const cols = $$("#col-config input:checked").map(i => i.dataset.key);
    setVisibleColumns(cols); renderHead(); doSearch();
  });
}

/* ==================================================================== *
 * Meta / navegação / init
 * ==================================================================== */
async function loadMeta() {
  const m = await api("/meta");
  const comp = m.competencia ? `${m.competencia.slice(4)}/${m.competencia.slice(0, 4)}` : "sem dados";
  $("#meta-info").textContent =
    `${m.total.toLocaleString("pt-BR")} procedimentos · competência ${comp}`;
  const fc = $("#footer-comp");
  if (fc) fc.textContent = m.competencia ? `competência ${comp}` : "base não importada";
}

function switchView(view) {
  $$(".view").forEach(v => v.classList.add("hidden"));
  $("#view-" + view).classList.remove("hidden");
  $$(".tab-btn").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  if (view === "favoritos") renderFavoritos();
  if (view === "historico") renderHistorico();
  if (view === "comparar") loadVersoes();
  if (view === "competencias") renderCompetencias();
}

let searchDebounce = null;
function triggerSearch() {
  state.q = $("#q").value.trim(); state.page = 1; doSearch();
}
function debouncedSearch() {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(triggerSearch, 300);
}

function initEvents() {
  $("#q").addEventListener("input", debouncedSearch);
  $("#q").addEventListener("keydown", e => { if (e.key === "Enter") triggerSearch(); });
  $("#btn-search").onclick = triggerSearch;
  $("#page-size").onchange = e => { state.page_size = +e.target.value; state.page = 1; doSearch(); };
  $("#btn-clear").onclick = () => {
    state.filters = {}; $$("#filters select").forEach(s => s.value = "");
    state.page = 1; doSearch();
  };
  $$(".tab-btn").forEach(b => b.onclick = () => switchView(b.dataset.view));
  $$(".export button").forEach(b => b.onclick = () =>
    window.location = `${API}/export?source=search&fmt=${b.dataset.fmt}&${queryParams()}`);
  $$(".report-buttons button").forEach(b => b.onclick = () => runReport(b.dataset.rep));
  $("#btn-compare").onclick = doCompare;
  $("#btn-do-update").onclick = doUpdate;
  $("#file-zip").onchange = e => { if (e.target.files[0]) doImport(e.target.files[0]); };
  $("#comp-upload").onchange = e => {
    if (e.target.files[0]) exportCompetenciaUpload(e.target.files[0], $("#comp-upload-fmt").value);
    e.target.value = "";
  };
  $("#modal-close").onclick = () => $("#modal").classList.add("hidden");
  $("#modal").onclick = e => { if (e.target.id === "modal") $("#modal").classList.add("hidden"); };
  document.addEventListener("keydown", e => {   // ESC fecha o modal
    if (e.key === "Escape") $("#modal").classList.add("hidden");
  });
  $("#btn-theme").onclick = () => {
    const t = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = t; localStorage.setItem("theme", t);
  };
  $("#btn-density").onclick = () => {
    state.compact = !state.compact;
    localStorage.setItem("density", state.compact ? "compact" : "normal");
    $("#btn-density").classList.toggle("on", state.compact);
    $("#grid").classList.toggle("compact", state.compact);
  };
}

async function init() {
  // Tema: usa o escolhido; se não houver, segue o tema do sistema (Windows)
  const savedTheme = localStorage.getItem("theme");
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.dataset.theme = savedTheme || (prefersDark ? "dark" : "light");

  state.page_size = +$("#page-size").value;
  $("#btn-density").classList.toggle("on", state.compact);
  initEvents(); renderColConfig();
  await loadMeta();
  await Promise.all([loadFilters(), loadFavoritos().catch(() => {})]);
  switchView("consulta");
  doSearch();
}
window.switchView = switchView;   // usado pelo botão da tela vazia
document.addEventListener("DOMContentLoaded", init);
