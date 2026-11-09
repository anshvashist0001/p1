"use strict";
const $ = (id) => document.getElementById(id);
let report = {requests: 0, endpoints: []};
let refreshing = false;
const ms = (value) => `${Number(value).toFixed(1)} ms`;
function text(tag, content, className) {
  const element = document.createElement(tag);
  element.textContent = content;
  if (className) element.className = className;
  return element;
}
async function get(path) {
  const response = await fetch(path, {signal: AbortSignal.timeout(10000), cache: "no-store"});
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json();
}
function renderTable() {
  const filter = $("filter").value.toLowerCase();
  const rows = report.endpoints.filter(row => `${row.route} ${row.variant}`.toLowerCase().includes(filter));
  $("endpoints").replaceChildren();
  for (const row of rows) {
    const tr = document.createElement("tr");
    const route = document.createElement("td");
    route.append(text("span", row.method, "tag"), document.createTextNode(row.route));
    if (row.variant !== "default") route.append(text("span", row.variant.replaceAll("_", " "), "variant"));
    tr.append(route);
    [row.requests, ms(row.avg_ms), ms(row.p95_ms), `${row.error_rate_pct}%`, row.avg_query_count, ms(row.avg_query_ms)].forEach((value, index) => {
      tr.append(text("td", value, index === 3 && row.error_rate_pct ? "bad" : ""));
    });
    $("endpoints").append(tr);
  }
  $("empty").hidden = rows.length > 0;
  $("empty").textContent = report.requests ? "No endpoints match your filter." : "No requests yet. Generate traffic to start investigating.";
}
function renderSummary() {
  const count = report.requests;
  const weighted = key => count ? report.endpoints.reduce((sum, row) => sum + row[key] * row.requests, 0) / count : 0;
  $("total").textContent = count.toLocaleString();
  $("average").textContent = count ? ms(weighted("avg_ms")) : "—";
  const errors = report.endpoints.reduce((sum, row) => sum + row.client_errors + row.server_errors, 0);
  $("errors").textContent = count ? `${(100 * errors / count).toFixed(1)}%` : "—";
  $("sql").textContent = count ? ms(weighted("avg_query_ms")) : "—";
  renderTable();
  const notes = [];
  const repeated = report.endpoints.find(row => row.avg_query_count > 10);
  if (repeated) notes.push(`${repeated.route} (${repeated.variant}) averages ${repeated.avg_query_count} queries per request. Check for repeated fetching; compare the batch strategy.`);
  const slow = report.endpoints[0];
  if (slow) notes.push(`Highest p95: ${slow.route}, ${ms(slow.p95_ms)} across ${slow.requests} requests. ${slow.route.endsWith("/slow") ? "This endpoint has an artificial delay." : "Repeat the workload before drawing conclusions."}`);
  if (errors) notes.push(`${errors} responses have a 4xx or 5xx status. The demo error endpoint intentionally returns 503.`);
  if (!notes.length) notes.push("Generate requests to reveal patterns. No sample metrics are preloaded.");
  $("insights").replaceChildren(...notes.map(note => text("li", note)));
}
function renderChart(samples) {
  const rows = samples.slice(0, 60).reverse();
  const max = Math.max(1, ...rows.map(row => row.duration_ms));
  $("chart").replaceChildren();
  for (const row of rows) {
    const bar = document.createElement("div");
    bar.className = `bar${row.status >= 400 ? " error" : ""}`;
    bar.style.height = `${Math.max(1, 100 * row.duration_ms / max)}%`;
    bar.title = `${row.route} · ${row.status} · ${ms(row.duration_ms)} · ${new Date(row.timestamp * 1000).toLocaleTimeString()}`;
    $("chart").append(bar);
  }
  $("chart").setAttribute("aria-label", `${rows.length} recent requests; maximum latency ${ms(max)}. Detailed timings are in the endpoint table.`);
  $("chart-scale").textContent = rows.length ? `0 – ${ms(max)} · ${rows.length} requests` : "No samples";
}
async function refresh() {
  if (refreshing) return;
  refreshing = true;
  $("refresh").disabled = true;
  try {
    const [summary, requests, health] = await Promise.all([get("/monitoring/summary"), get("/monitoring/requests?limit=60"), get("/health")]);
    report = summary;
    renderSummary(); renderChart(requests.items);
    $("database").textContent = health.database;
    $("retention").textContent = `Local development · ${summary.window}`;
    $("status").textContent = "● Live · 3s";
    $("updated").textContent = `Updated ${new Date().toLocaleTimeString()}`;
    $("notice").hidden = summary.persistence !== "degraded";
    if (summary.persistence === "degraded") $("notice").textContent = "Some metrics could not be saved to disk. Live metrics are available, but history may be incomplete after restart.";
  } catch (error) {
    $("status").textContent = "Disconnected";
    $("notice").textContent = "Cannot refresh metrics. Check that the API is running; displayed values may be stale.";
    $("notice").hidden = false;
  } finally {
    refreshing = false; $("refresh").disabled = false;
  }
}
async function experiment(kind) {
  $("traffic").disabled = $("compare").disabled = true;
  $("experiment").textContent = "Running local requests…";
  try {
    if (kind === "traffic") {
      const paths = [...Array(8).fill("/api/products"), "/api/demo/slow?delay_ms=250", "/api/demo/error"];
      const responses = await Promise.all(paths.map(path => fetch(path, {signal: AbortSignal.timeout(10000)}).then(async r => { await r.arrayBuffer(); return r.status; })));
      const failures = responses.filter(status => status >= 400).length;
      $("experiment").textContent = `Completed ${responses.length} requests: ${failures} error response(s). One 503 is intentional; the slow route has a simulated 250 ms wait.`;
    } else {
      const totals = {n_plus_one: 0, batch: 0};
      // Warm both paths, then alternate order to reduce warm-cache/order bias.
      await get("/api/demo/catalog?strategy=n_plus_one");
      await get("/api/demo/catalog?strategy=batch");
      for (let i = 0; i < 10; i++) {
        const order = i % 2 ? ["batch", "n_plus_one"] : ["n_plus_one", "batch"];
        for (const strategy of order) {
          const start = performance.now();
          await get(`/api/demo/catalog?strategy=${strategy}`);
          totals[strategy] += performance.now() - start;
        }
      }
      $("experiment").textContent = `10 measured requests each · browser average: repeated queries ${ms(totals.n_plus_one / 10)}, batch ${ms(totals.batch / 10)}. Includes network and JSON parsing. The table shows server measurements, including warm-ups and earlier traffic.`;
    }
  } catch (error) {
    $("experiment").textContent = `Experiment stopped: ${error.message}. Check the API connection and retry.`;
  } finally {
    $("traffic").disabled = $("compare").disabled = false;
    await refresh();
  }
}
$("refresh").addEventListener("click", refresh);
$("filter").addEventListener("input", renderTable);
$("traffic").addEventListener("click", () => experiment("traffic"));
$("compare").addEventListener("click", () => experiment("compare"));
refresh();
setInterval(() => { if (!document.hidden) refresh(); }, 3000);
