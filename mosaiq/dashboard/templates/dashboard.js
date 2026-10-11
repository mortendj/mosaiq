/* Mosaiq dashboard — all filtering/aggregation runs client-side against the
   DEPLOYMENTS array embedded in index.html. No backend, no network calls. */

const PALETTE = ["#4fd1c5", "#a78bfa", "#f6ad55", "#f56565", "#63b3ed", "#68d391", "#f687b3", "#ecc94b"];
const TEXT_COLOR = getComputedStyle(document.documentElement).getPropertyValue("--text").trim() || "#e8edf2";
const GRID_COLOR = "rgba(143, 161, 179, 0.15)";

Chart.defaults.color = TEXT_COLOR;
Chart.defaults.borderColor = GRID_COLOR;
Chart.defaults.font.family = "Segoe UI, system-ui, sans-serif";

const state = {
  dateFrom: null,
  dateTo: null,
  search: "",
  majorVersions: new Set(),
  connectors: new Set(),
  modules: new Set(),
  databases: new Set(),
  sortKey: "deployment_name",
  sortDir: 1,
  scatterXMetric: "cpu_cores",
};

const charts = {};

// "7.19.0" -> "7.x" - the leading dotted segment, auto-detected from whatever
// versions are actually present rather than a hardcoded list, so a future 8.x
// shows up in the filter on its own.
function majorVersionOf(productVersion) {
  if (!productVersion) return null;
  const match = String(productVersion).match(/^(\d+)\./);
  return match ? `${match[1]}.x` : null;
}

function uniqueSorted(values) {
  return Array.from(new Set(values.filter((v) => v !== null && v !== undefined && v !== ""))).sort();
}

function allMajorVersions() {
  return uniqueSorted(DEPLOYMENTS.map((d) => majorVersionOf(d.product_version))).sort(compareNatural);
}
function allConnectors() {
  return uniqueSorted(DEPLOYMENTS.flatMap((d) => d.connectors || []));
}
function allModules() {
  return uniqueSorted(DEPLOYMENTS.flatMap((d) => d.modules || []));
}
function allDatabases() {
  return uniqueSorted(DEPLOYMENTS.map((d) => d.database_type));
}

function renderChecklist(containerId, values, selectedSet) {
  const container = document.getElementById(containerId);
  container.innerHTML = "";
  values.forEach((value) => {
    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = selectedSet.has(value);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) selectedSet.add(value);
      else selectedSet.delete(value);
      refresh();
    });
    label.appendChild(checkbox);
    label.appendChild(document.createTextNode(value));
    container.appendChild(label);
  });
}

function applyFilters() {
  return DEPLOYMENTS.filter((d) => {
    if (state.dateFrom && (!d.report_date || d.report_date < state.dateFrom)) return false;
    if (state.dateTo && (!d.report_date || d.report_date > state.dateTo)) return false;
    if (state.search && !d.deployment_name.toLowerCase().includes(state.search.toLowerCase())) return false;
    if (state.majorVersions.size && !state.majorVersions.has(majorVersionOf(d.product_version))) return false;
    if (state.connectors.size && !(d.connectors || []).some((c) => state.connectors.has(c))) return false;
    if (state.modules.size && !(d.modules || []).some((m) => state.modules.has(m))) return false;
    if (state.databases.size && !state.databases.has(d.database_type)) return false;
    return true;
  });
}

function sum(values) {
  return values.reduce((a, b) => a + (b || 0), 0);
}

function average(values) {
  const present = values.filter((v) => v !== null && v !== undefined);
  return present.length ? sum(present) / present.length : null;
}

function formatAverage(value) {
  return value === null ? "—" : Math.round(value).toLocaleString();
}

// Deployments are independent customer environments, not shared infrastructure - a
// "total" across them (e.g. "360 CPU cores") sums unrelated servers and represents
// nothing real. Per-deployment averages are the meaningful fleet-wide stat instead.
function renderKpis(filtered) {
  const tiles = [
    ["Deployments", filtered.length],
    ["Avg CPU cores", formatAverage(average(filtered.map((d) => d.cpu_cores)))],
    ["Avg RAM (GB)", formatAverage(average(filtered.map((d) => d.ram_gb)))],
    ["Avg documents", formatAverage(average(filtered.map((d) => d.document_count)))],
  ];

  const container = document.getElementById("kpis");
  container.innerHTML = "";
  tiles.forEach(([label, value]) => {
    const div = document.createElement("div");
    div.className = "kpi";
    div.innerHTML = `<div class="value">${value}</div><div class="label">${label}</div>`;
    container.appendChild(div);
  });
}

// Compares values like "7.19.0" or "16" by their numeric segments, not as plain
// strings - a plain string compare puts "7.19.0" before "7.3.0" (since '1' < '3'),
// which is wrong for version numbers.
function compareNatural(a, b) {
  const partsA = String(a).split(/[^0-9]+/).filter(Boolean).map(Number);
  const partsB = String(b).split(/[^0-9]+/).filter(Boolean).map(Number);
  const length = Math.max(partsA.length, partsB.length);
  for (let i = 0; i < length; i++) {
    const diff = (partsA[i] ?? 0) - (partsB[i] ?? 0);
    if (diff !== 0) return diff;
  }
  return 0;
}

function countBy(filtered, extractor) {
  const counts = new Map();
  filtered.forEach((d) => {
    const raw = extractor(d);
    const values = Array.isArray(raw) ? raw : [raw];
    values.forEach((v) => {
      if (v === null || v === undefined || v === "") return;
      counts.set(v, (counts.get(v) || 0) + 1);
    });
  });
  return counts;
}

function upsertBarChart(canvasId, counts, { horizontal = false, sortBy = "count" } = {}) {
  // "count" ranks by popularity (right for adoption charts: connectors, modules).
  // "value" orders ascending by the category's own numeric value (right for pure
  // magnitude distributions - CPU/RAM - so they read as an actual histogram shape).
  // "value-desc" orders descending - right for version numbers specifically, since a
  // version carries a recency story (newest first), unlike a plain magnitude.
  const sortedEntries = Array.from(counts.entries()).sort((a, b) => {
    if (sortBy === "value") return compareNatural(a[0], b[0]);
    if (sortBy === "value-desc") return compareNatural(b[0], a[0]);
    return b[1] - a[1];
  });
  const labels = sortedEntries.map((e) => String(e[0]));
  const data = sortedEntries.map((e) => e[1]);

  // Bars always count deployments, so the value axis is always a whole number -
  // force whole-number ticks (no 0.5/1.5 steps) and hide the redundant "0" label.
  const countAxis = {
    grid: { color: GRID_COLOR },
    beginAtZero: true,
    ticks: { stepSize: 1, precision: 0, callback: (value) => (value === 0 ? "" : value) },
  };
  const categoryAxis = { grid: { color: GRID_COLOR } };

  const config = {
    type: "bar",
    data: {
      labels,
      datasets: [{ data, backgroundColor: labels.map((_, i) => PALETTE[i % PALETTE.length]) }],
    },
    options: {
      indexAxis: horizontal ? "y" : "x",
      plugins: { legend: { display: false } },
      scales: horizontal
        ? { x: countAxis, y: categoryAxis }
        : { x: categoryAxis, y: countAxis },
    },
  };

  if (charts[canvasId]) {
    charts[canvasId].data = config.data;
    charts[canvasId].update();
  } else {
    charts[canvasId] = new Chart(document.getElementById(canvasId), config);
  }
}

function upsertDoughnutChart(canvasId, counts) {
  const entries = Array.from(counts.entries());
  const config = {
    type: "doughnut",
    data: {
      // Count baked right into the label text - a doughnut has no axis to read
      // values off of like a bar chart does, so the number has to live in the label.
      labels: entries.map((e) => `${e[0]} (${e[1]})`),
      datasets: [{ data: entries.map((e) => e[1]), backgroundColor: entries.map((_, i) => PALETTE[i % PALETTE.length]) }],
    },
    options: { plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } } } },
  };
  if (charts[canvasId]) {
    charts[canvasId].data = config.data;
    charts[canvasId].update();
  } else {
    charts[canvasId] = new Chart(document.getElementById(canvasId), config);
  }
}

function averageDocumentsByX(points) {
  const buckets = new Map();
  points.forEach(({ x, y }) => {
    const bucket = buckets.get(x) || { sum: 0, count: 0 };
    bucket.sum += y;
    bucket.count += 1;
    buckets.set(x, bucket);
  });
  return Array.from(buckets.entries())
    .map(([x, { sum, count }]) => ({ x, y: sum / count }))
    .sort((a, b) => a.x - b.x);
}

function upsertScatterChart(filtered) {
  const metric = state.scatterXMetric;
  const metricLabel = metric === "cpu_cores" ? "CPU cores" : "RAM (GB)";
  const points = filtered
    .filter((d) => d[metric] && d.document_count)
    .map((d) => ({ x: d[metric], y: d.document_count, label: d.deployment_name }));
  const trend = averageDocumentsByX(points);

  const config = {
    type: "scatter",
    data: {
      datasets: [
        {
          type: "scatter",
          label: "Deployments",
          data: points,
          backgroundColor: PALETTE[0],
        },
        {
          type: "line",
          label: "Average at this hardware level",
          data: trend,
          borderColor: PALETTE[3],
          backgroundColor: PALETTE[3],
          borderWidth: 2,
          pointRadius: 3,
          tension: 0,
          fill: false,
        },
      ],
    },
    options: {
      plugins: {
        legend: { display: true, position: "top", labels: { boxWidth: 12 } },
        tooltip: {
          callbacks: {
            label: (ctx) =>
              ctx.dataset.type === "line"
                ? `Average at ${ctx.raw.x} ${metricLabel}: ${Math.round(ctx.raw.y).toLocaleString()} docs`
                : `${ctx.raw.label}: ${ctx.raw.x} ${metricLabel}, ${ctx.raw.y.toLocaleString()} docs`,
          },
        },
      },
      scales: {
        x: { title: { display: true, text: metricLabel }, grid: { color: GRID_COLOR } },
        y: { type: "logarithmic", title: { display: true, text: "Documents (log scale)" }, grid: { color: GRID_COLOR } },
      },
    },
  };

  if (charts["chart-scatter"]) {
    charts["chart-scatter"].data = config.data;
    charts["chart-scatter"].options = config.options;
    charts["chart-scatter"].update();
  } else {
    charts["chart-scatter"] = new Chart(document.getElementById("chart-scatter"), config);
  }
}

function formatNumber(value, decimals) {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function renderTable(filtered) {
  const sorted = [...filtered].sort((a, b) => {
    const key = state.sortKey;
    const av = Array.isArray(a[key]) ? a[key].join(", ") : a[key];
    const bv = Array.isArray(b[key]) ? b[key].join(", ") : b[key];
    if (av === bv) return 0;
    if (av === null || av === undefined) return 1;
    if (bv === null || bv === undefined) return -1;
    if (key === "product_version") return compareNatural(av, bv) * state.sortDir;
    return (av > bv ? 1 : -1) * state.sortDir;
  });

  const body = document.getElementById("data-table-body");
  body.innerHTML = sorted
    .map(
      (d) => `<tr>
        <td>${d.deployment_name}</td>
        <td>${d.report_date || "—"}</td>
        <td>${d.product_version || "—"}</td>
        <td>${(d.connectors || []).join(", ") || "—"}</td>
        <td>${(d.modules || []).join(", ") || "—"}</td>
        <td>${d.database_type || "—"}</td>
        <td class="num">${formatNumber(d.cpu_cores, 0)}</td>
        <td class="num">${formatNumber(d.ram_gb, 0)}</td>
        <td class="num">${formatNumber(d.index_size_gb, 3)}</td>
        <td class="num">${formatNumber(d.document_count, 0)}</td>
      </tr>`
    )
    .join("");
}

function refresh() {
  const filtered = applyFilters();
  renderKpis(filtered);
  upsertBarChart("chart-connectors", countBy(filtered, (d) => d.connectors), { horizontal: true });
  upsertBarChart("chart-versions", countBy(filtered, (d) => d.product_version), { sortBy: "value-desc" });
  upsertBarChart("chart-modules", countBy(filtered, (d) => d.modules), { horizontal: true });
  upsertDoughnutChart("chart-database", countBy(filtered, (d) => d.database_type));
  upsertBarChart("chart-cpu", countBy(filtered, (d) => d.cpu_cores), { sortBy: "value" });
  upsertBarChart("chart-ram", countBy(filtered, (d) => d.ram_gb), { sortBy: "value" });
  upsertScatterChart(filtered);
  renderTable(filtered);
}

function renderChecklists() {
  renderChecklist("filter-major-version", allMajorVersions(), state.majorVersions);
  renderChecklist("filter-connectors", allConnectors(), state.connectors);
  renderChecklist("filter-modules", allModules(), state.modules);
  renderChecklist("filter-database", allDatabases(), state.databases);
}

function wireFilterControls() {
  renderChecklists();

  const dateFrom = document.getElementById("filter-date-from");
  const dateTo = document.getElementById("filter-date-to");
  const reportDates = DEPLOYMENTS.map((d) => d.report_date).filter(Boolean).sort();
  if (reportDates.length) {
    dateFrom.min = dateTo.min = reportDates[0];
    dateFrom.max = dateTo.max = reportDates[reportDates.length - 1];
  }
  dateFrom.addEventListener("change", () => { state.dateFrom = dateFrom.value || null; refresh(); });
  dateTo.addEventListener("change", () => { state.dateTo = dateTo.value || null; refresh(); });

  document.getElementById("filter-search").addEventListener("input", (e) => {
    state.search = e.target.value;
    refresh();
  });

  document.getElementById("scatter-x-metric").addEventListener("change", (e) => {
    state.scatterXMetric = e.target.value;
    refresh();
  });

  document.querySelectorAll("#data-table th").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.key;
      state.sortDir = state.sortKey === key ? -state.sortDir : 1;
      state.sortKey = key;
      refresh();
    });
  });

  document.getElementById("reset-filters").addEventListener("click", () => {
    state.dateFrom = null;
    state.dateTo = null;
    state.search = "";
    state.majorVersions.clear();
    state.connectors.clear();
    state.modules.clear();
    state.databases.clear();
    dateFrom.value = "";
    dateTo.value = "";
    document.getElementById("filter-search").value = "";
    renderChecklists();
    refresh();
  });
}

wireFilterControls();
refresh();
