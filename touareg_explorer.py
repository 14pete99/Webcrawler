"""Touareg Database Explorer — web interface for browsing scraped vehicle data.

Usage:
    python touareg_explorer.py [--db path/to/touareg.db] [--port 8050]

Opens a browser to an interactive dashboard with filterable tables,
vehicle comparison, and custom SQL queries.
"""

import argparse
import json
import re
import sqlite3
import webbrowser
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

_db_path = Path("output/touareg-specs/touareg.db")

app = FastAPI(title="Touareg Explorer")

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path))
    conn.row_factory = sqlite3.Row
    return conn


def rows_to_dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@app.get("/api/vehicles")
def api_vehicles(
    year_min: int | None = None,
    year_max: int | None = None,
    badge: str | None = None,
    fuel_type: str | None = None,
    sort: str = "year",
    order: str = "desc",
    search: str | None = None,
):
    """Return vehicles with optional filters."""
    conn = get_db()
    clauses = []
    params: list = []

    if year_min is not None:
        clauses.append("v.year >= ?")
        params.append(year_min)
    if year_max is not None:
        clauses.append("v.year <= ?")
        params.append(year_max)
    if badge:
        clauses.append("v.badge = ?")
        params.append(badge)
    if fuel_type:
        clauses.append("v.fuel_type = ?")
        params.append(fuel_type)
    if search:
        clauses.append("v.vehicle_name LIKE ?")
        params.append(f"%{search}%")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    # Whitelist sort columns — prefix with table alias to avoid ambiguity
    vehicle_sorts = {"year", "variant", "vehicle_name", "badge", "price_when_new"}
    summary_sorts = {"power_kw", "torque_nm", "accel_0_100_s", "fuel_combined_lper100", "kerb_weight_kg"}
    if sort in vehicle_sorts:
        sort_col = f"v.{sort}"
    elif sort in summary_sorts:
        sort_col = f"vs.{sort}"
    else:
        sort_col = "v.year"
    direction = "ASC" if order.lower() == "asc" else "DESC"

    sql = f"""
        SELECT v.id, v.year, v.variant, v.vehicle_name, v.badge, v.series,
               v.fuel_type, v.drive_type, v.transmission, v.price_when_new,
               vs.power, vs.power_kw, vs.torque, vs.torque_nm,
               vs.engine_size, vs.cylinders, vs.accel_0_100, vs.accel_0_100_s,
               vs.fuel_combined, vs.fuel_combined_lper100,
               vs.kerb_weight, vs.kerb_weight_kg, vs.gears,
               vs.battery_capacity, vs.ev_range_wltp, vs.ancap_rating
        FROM vehicles v
        LEFT JOIN vehicle_summary vs ON vs.id = v.id
        {where}
        ORDER BY {sort_col} {direction}, v.vehicle_name ASC
    """
    rows = rows_to_dicts(conn.execute(sql, params).fetchall())
    conn.close()
    return {"vehicles": rows, "count": len(rows)}


@app.get("/api/vehicle/{vehicle_id}")
def api_vehicle_detail(vehicle_id: int):
    """Return full vehicle details with all specs."""
    conn = get_db()
    vehicle = conn.execute(
        "SELECT * FROM vehicles WHERE id = ?", (vehicle_id,)
    ).fetchone()
    if not vehicle:
        conn.close()
        return JSONResponse({"error": "not found"}, status_code=404)

    specs = rows_to_dicts(conn.execute(
        "SELECT section, key, value, numeric_value, unit FROM specs WHERE vehicle_id = ? ORDER BY section, key",
        (vehicle_id,),
    ).fetchall())
    conn.close()

    return {"vehicle": dict(vehicle), "specs": specs}


@app.get("/api/compare")
def api_compare(ids: str = Query(..., description="Comma-separated vehicle IDs")):
    """Compare specs across multiple vehicles."""
    id_list = [int(x) for x in ids.split(",") if x.strip().isdigit()]
    if not id_list or len(id_list) > 6:
        return JSONResponse({"error": "provide 2-6 vehicle IDs"}, status_code=400)

    conn = get_db()
    placeholders = ",".join("?" * len(id_list))

    vehicles = rows_to_dicts(conn.execute(
        f"SELECT * FROM vehicles WHERE id IN ({placeholders})", id_list
    ).fetchall())

    specs = rows_to_dicts(conn.execute(
        f"""SELECT vehicle_id, section, key, value, numeric_value, unit
            FROM specs WHERE vehicle_id IN ({placeholders})
            ORDER BY section, key""",
        id_list,
    ).fetchall())
    conn.close()

    return {"vehicles": vehicles, "specs": specs}


@app.get("/api/filters")
def api_filters():
    """Return available filter values."""
    conn = get_db()
    years = conn.execute(
        "SELECT DISTINCT year FROM vehicles ORDER BY year"
    ).fetchall()
    badges = conn.execute(
        "SELECT DISTINCT badge FROM vehicles WHERE badge IS NOT NULL ORDER BY badge"
    ).fetchall()
    fuel_types = conn.execute(
        "SELECT DISTINCT fuel_type FROM vehicles WHERE fuel_type IS NOT NULL ORDER BY fuel_type"
    ).fetchall()
    series_list = conn.execute(
        "SELECT DISTINCT series FROM vehicles WHERE series IS NOT NULL ORDER BY series"
    ).fetchall()
    conn.close()
    return {
        "years": [r["year"] for r in years],
        "badges": [r["badge"] for r in badges],
        "fuel_types": [r["fuel_type"] for r in fuel_types],
        "series": [r["series"] for r in series_list],
    }


@app.get("/api/stats")
def api_stats():
    """Return database statistics."""
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
    year_range = conn.execute("SELECT MIN(year), MAX(year) FROM vehicles").fetchone()
    price_range = conn.execute(
        "SELECT MIN(price_when_new), MAX(price_when_new) FROM vehicles WHERE price_when_new IS NOT NULL"
    ).fetchone()
    by_decade = rows_to_dicts(conn.execute(
        "SELECT (year/10)*10 AS decade, COUNT(*) AS count FROM vehicles GROUP BY decade ORDER BY decade"
    ).fetchall())
    by_fuel = rows_to_dicts(conn.execute(
        "SELECT fuel_type, COUNT(*) AS count FROM vehicles WHERE fuel_type IS NOT NULL GROUP BY fuel_type ORDER BY count DESC"
    ).fetchall())
    conn.close()
    return {
        "total_vehicles": total,
        "year_min": year_range[0],
        "year_max": year_range[1],
        "price_min": price_range[0],
        "price_max": price_range[1],
        "by_decade": by_decade,
        "by_fuel": by_fuel,
    }


@app.get("/api/query")
def api_query(sql: str = Query(..., description="SQL query")):
    """Execute a read-only SQL query."""
    # Safety: only allow SELECT statements
    cleaned = sql.strip().rstrip(";")
    if not re.match(r"(?i)^SELECT\s", cleaned):
        return JSONResponse({"error": "only SELECT queries allowed"}, status_code=400)

    # Block dangerous patterns
    dangerous = re.compile(
        r"(?i)\b(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE|ATTACH|DETACH|PRAGMA\s+(?!table_info|database_list))\b"
    )
    if dangerous.search(cleaned):
        return JSONResponse({"error": "query contains disallowed keywords"}, status_code=400)

    conn = get_db()
    try:
        cursor = conn.execute(cleaned)
        columns = [d[0] for d in cursor.description] if cursor.description else []
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return {"columns": columns, "rows": rows, "count": len(rows)}
    except Exception as e:
        conn.close()
        return JSONResponse({"error": str(e)}, status_code=400)


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index():
    return FRONTEND_HTML


FRONTEND_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Touareg Explorer</title>
<style>
:root {
  --bg: #0f1117;
  --surface: #1a1d27;
  --surface2: #232733;
  --border: #2e3341;
  --text: #e1e4eb;
  --text2: #8b90a0;
  --accent: #4a9eff;
  --accent2: #2d7ad6;
  --green: #34d399;
  --orange: #f59e0b;
  --red: #ef4444;
  --radius: 8px;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  background: var(--bg); color: var(--text);
  line-height: 1.5;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

/* Layout */
.header {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 16px 24px;
  display: flex; align-items: center; gap: 24px;
}
.header h1 { font-size: 20px; font-weight: 600; }
.header .stats { color: var(--text2); font-size: 14px; }

.tabs {
  display: flex; gap: 0;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 0 24px;
}
.tab {
  padding: 12px 20px; cursor: pointer;
  color: var(--text2); font-size: 14px; font-weight: 500;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}
.tab:hover { color: var(--text); }
.tab.active { color: var(--accent); border-bottom-color: var(--accent); }

.content { padding: 24px; max-width: 1600px; margin: 0 auto; }
.panel { display: none; }
.panel.active { display: block; }

/* Filters */
.filters {
  display: flex; flex-wrap: wrap; gap: 12px;
  margin-bottom: 20px; align-items: flex-end;
}
.filter-group { display: flex; flex-direction: column; gap: 4px; }
.filter-group label { font-size: 12px; color: var(--text2); text-transform: uppercase; letter-spacing: 0.5px; }
.filter-group select, .filter-group input {
  background: var(--surface2); color: var(--text);
  border: 1px solid var(--border); border-radius: var(--radius);
  padding: 8px 12px; font-size: 14px; min-width: 140px;
}
.filter-group select:focus, .filter-group input:focus {
  outline: none; border-color: var(--accent);
}
.btn {
  background: var(--accent); color: #fff; border: none;
  border-radius: var(--radius); padding: 8px 16px;
  font-size: 14px; cursor: pointer; font-weight: 500;
  transition: background 0.2s;
}
.btn:hover { background: var(--accent2); }
.btn-secondary { background: var(--surface2); color: var(--text); border: 1px solid var(--border); }
.btn-secondary:hover { background: var(--border); }
.btn-sm { padding: 4px 10px; font-size: 12px; }

/* Stats cards */
.stats-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px; margin-bottom: 24px;
}
.stat-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 20px;
}
.stat-card .label { font-size: 12px; color: var(--text2); text-transform: uppercase; letter-spacing: 0.5px; }
.stat-card .value { font-size: 28px; font-weight: 700; margin-top: 4px; }
.stat-card .sub { font-size: 13px; color: var(--text2); margin-top: 2px; }

/* Table */
.table-wrap { overflow-x: auto; border-radius: var(--radius); border: 1px solid var(--border); }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th {
  background: var(--surface2); color: var(--text2);
  padding: 10px 14px; text-align: left; font-weight: 600;
  font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;
  position: sticky; top: 0; cursor: pointer; white-space: nowrap;
  user-select: none; border-bottom: 1px solid var(--border);
}
th:hover { color: var(--text); }
th .sort-arrow { margin-left: 4px; font-size: 10px; }
td {
  padding: 10px 14px; border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
tr:hover td { background: var(--surface2); }
tr.selected td { background: #1e3a5f; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.price { color: var(--green); }
.badge-tag {
  display: inline-block; background: var(--surface2);
  border: 1px solid var(--border); border-radius: 4px;
  padding: 1px 8px; font-size: 12px;
}

/* Detail modal */
.modal-overlay {
  display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.7); z-index: 100; justify-content: center; align-items: start;
  padding: 40px 20px; overflow-y: auto;
}
.modal-overlay.show { display: flex; }
.modal {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 12px; width: 100%; max-width: 900px;
  padding: 32px; position: relative;
}
.modal-close {
  position: absolute; top: 16px; right: 16px;
  background: none; border: none; color: var(--text2);
  font-size: 24px; cursor: pointer;
}
.modal-close:hover { color: var(--text); }
.modal h2 { font-size: 18px; margin-bottom: 4px; }
.modal .subtitle { color: var(--text2); font-size: 14px; margin-bottom: 20px; }
.spec-section { margin-bottom: 20px; }
.spec-section h3 {
  font-size: 13px; color: var(--accent); text-transform: uppercase;
  letter-spacing: 0.5px; margin-bottom: 8px;
  padding-bottom: 4px; border-bottom: 1px solid var(--border);
}
.spec-row { display: flex; padding: 4px 0; font-size: 13px; }
.spec-key { color: var(--text2); width: 240px; flex-shrink: 0; }
.spec-val { color: var(--text); }

/* Compare panel */
.compare-bar {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 12px 16px;
  margin-bottom: 16px; display: flex; align-items: center; gap: 12px;
}
.compare-bar .chips { display: flex; gap: 8px; flex-wrap: wrap; flex: 1; }
.chip {
  background: var(--surface2); border: 1px solid var(--border);
  border-radius: 20px; padding: 4px 12px; font-size: 12px;
  display: flex; align-items: center; gap: 6px;
}
.chip .remove { cursor: pointer; color: var(--text2); font-size: 14px; }
.chip .remove:hover { color: var(--red); }

.compare-table { width: 100%; }
.compare-table th:first-child { min-width: 200px; }
.compare-table .section-header td {
  background: var(--surface2); font-weight: 600; font-size: 12px;
  text-transform: uppercase; letter-spacing: 0.5px; color: var(--accent);
  padding: 8px 14px;
}
.highlight-best { color: var(--green); font-weight: 600; }
.highlight-worst { color: var(--text2); }

/* Query panel */
.query-box {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 16px; margin-bottom: 16px;
}
.query-box textarea {
  width: 100%; min-height: 80px; background: var(--surface2);
  color: var(--text); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 12px; font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px; resize: vertical;
}
.query-box textarea:focus { outline: none; border-color: var(--accent); }
.query-presets { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
.result-info { color: var(--text2); font-size: 13px; margin: 12px 0; }

/* Chart bars */
.bar-chart { margin: 16px 0; }
.bar-row { display: flex; align-items: center; gap: 12px; margin: 6px 0; }
.bar-label { width: 100px; font-size: 13px; text-align: right; color: var(--text2); }
.bar-track { flex: 1; height: 24px; background: var(--surface2); border-radius: 4px; overflow: hidden; position: relative; }
.bar-fill { height: 100%; background: var(--accent); border-radius: 4px; transition: width 0.5s; display: flex; align-items: center; padding: 0 8px; }
.bar-fill span { font-size: 11px; font-weight: 600; white-space: nowrap; }

/* Responsive */
@media (max-width: 768px) {
  .filters { flex-direction: column; }
  .stats-grid { grid-template-columns: 1fr 1fr; }
  .header { flex-direction: column; align-items: start; gap: 8px; }
}
</style>
</head>
<body>

<div class="header">
  <h1>Touareg Explorer</h1>
  <div class="stats" id="header-stats">Loading...</div>
</div>

<div class="tabs">
  <div class="tab active" data-tab="dashboard">Dashboard</div>
  <div class="tab" data-tab="vehicles">Vehicles</div>
  <div class="tab" data-tab="compare">Compare</div>
  <div class="tab" data-tab="query">SQL Query</div>
</div>

<div class="content">

  <!-- Dashboard -->
  <div class="panel active" id="panel-dashboard">
    <div class="stats-grid" id="stats-grid"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px">
      <div>
        <h3 style="font-size:14px;margin-bottom:12px;color:var(--text2)">Vehicles by Decade</h3>
        <div class="bar-chart" id="decade-chart"></div>
      </div>
      <div>
        <h3 style="font-size:14px;margin-bottom:12px;color:var(--text2)">Price Trend (Cheapest per Year)</h3>
        <div class="bar-chart" id="price-chart"></div>
      </div>
    </div>
  </div>

  <!-- Vehicles -->
  <div class="panel" id="panel-vehicles">
    <div class="filters" id="filters-bar"></div>
    <div class="compare-bar" id="compare-bar" style="display:none">
      <span style="font-size:13px;color:var(--text2)">Compare:</span>
      <div class="chips" id="compare-chips"></div>
      <button class="btn btn-sm" onclick="openCompare()">Compare Selected</button>
      <button class="btn btn-sm btn-secondary" onclick="clearCompare()">Clear</button>
    </div>
    <div class="table-wrap" style="max-height:calc(100vh - 280px);overflow-y:auto">
      <table id="vehicles-table">
        <thead><tr id="vehicles-thead"></tr></thead>
        <tbody id="vehicles-tbody"></tbody>
      </table>
    </div>
  </div>

  <!-- Compare -->
  <div class="panel" id="panel-compare">
    <p id="compare-empty" style="color:var(--text2)">Select 2-6 vehicles from the Vehicles tab to compare.</p>
    <div id="compare-content" style="display:none">
      <div class="table-wrap" style="max-height:calc(100vh - 200px);overflow-y:auto">
        <table class="compare-table" id="compare-table"></table>
      </div>
    </div>
  </div>

  <!-- Query -->
  <div class="panel" id="panel-query">
    <div class="query-box">
      <textarea id="sql-input" placeholder="SELECT * FROM vehicle_summary ORDER BY power_kw DESC LIMIT 20">SELECT * FROM vehicle_summary ORDER BY power_kw DESC LIMIT 20</textarea>
      <div style="display:flex;gap:12px;margin-top:12px;align-items:center">
        <button class="btn" onclick="runQuery()">Run Query</button>
        <span class="result-info" id="query-info"></span>
      </div>
      <div class="query-presets">
        <button class="btn btn-sm btn-secondary" onclick="setQuery(`SELECT vehicle_name, power, torque, accel_0_100, fuel_combined, kerb_weight\nFROM vehicle_summary\nORDER BY power_kw DESC\nLIMIT 20`)">Top Power</button>
        <button class="btn btn-sm btn-secondary" onclick="setQuery(`SELECT vehicle_name, accel_0_100, power, kerb_weight\nFROM vehicle_summary\nWHERE accel_0_100_s IS NOT NULL\nORDER BY accel_0_100_s ASC\nLIMIT 15`)">Fastest 0-100</button>
        <button class="btn btn-sm btn-secondary" onclick="setQuery(`SELECT year, MIN(price_when_new) AS min_price, MAX(price_when_new) AS max_price, COUNT(*) AS models\nFROM vehicles\nWHERE price_when_new IS NOT NULL\nGROUP BY year\nORDER BY year`)">Price by Year</button>
        <button class="btn btn-sm btn-secondary" onclick="setQuery(`SELECT vehicle_name, fuel_combined, fuel_combined_lper100, co2_combined\nFROM vehicle_summary\nWHERE fuel_combined_lper100 IS NOT NULL\nORDER BY fuel_combined_lper100 ASC\nLIMIT 15`)">Most Efficient</button>
        <button class="btn btn-sm btn-secondary" onclick="setQuery(`SELECT vehicle_name, kerb_weight, towing_braked_kg, length_mm\nFROM vehicle_summary\nWHERE kerb_weight_kg IS NOT NULL\nORDER BY kerb_weight_kg DESC\nLIMIT 15`)">Heaviest</button>
        <button class="btn btn-sm btn-secondary" onclick="setQuery(`SELECT badge, COUNT(*) AS count, MIN(year) AS first_year, MAX(year) AS last_year,\n  MIN(price_when_new) AS min_price, MAX(price_when_new) AS max_price\nFROM vehicles\nWHERE badge IS NOT NULL\nGROUP BY badge\nORDER BY count DESC`)">Badges Summary</button>
        <button class="btn btn-sm btn-secondary" onclick="setQuery(`SELECT section, key, value, COUNT(*) AS vehicles\nFROM specs\nGROUP BY section, key, value\nORDER BY section, key, vehicles DESC`)">All Spec Values</button>
      </div>
    </div>
    <div class="table-wrap" style="max-height:calc(100vh - 380px);overflow-y:auto">
      <table id="query-table">
        <thead><tr id="query-thead"></tr></thead>
        <tbody id="query-tbody"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- Detail Modal -->
<div class="modal-overlay" id="detail-modal">
  <div class="modal">
    <button class="modal-close" onclick="closeModal()">&times;</button>
    <div id="modal-content"></div>
  </div>
</div>

<script>
// State
let allVehicles = [];
let compareSet = new Set();
let currentSort = { col: 'year', order: 'desc' };
let filters = {};

// --- Tab navigation ---
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('panel-' + tab.dataset.tab).classList.add('active');
  });
});

// --- Fetch helpers ---
async function api(url) {
  const r = await fetch(url);
  return r.json();
}

// --- Dashboard ---
async function loadDashboard() {
  const stats = await api('/api/stats');
  document.getElementById('header-stats').textContent =
    `${stats.total_vehicles} vehicles | ${stats.year_min}–${stats.year_max} | $${(stats.price_min||0).toLocaleString()}–$${(stats.price_max||0).toLocaleString()}`;

  document.getElementById('stats-grid').innerHTML = `
    <div class="stat-card"><div class="label">Total Vehicles</div><div class="value">${stats.total_vehicles}</div></div>
    <div class="stat-card"><div class="label">Year Range</div><div class="value">${stats.year_min}–${stats.year_max}</div><div class="sub">${stats.year_max - stats.year_min + 1} years</div></div>
    <div class="stat-card"><div class="label">Price Range</div><div class="value">$${(stats.price_min||0).toLocaleString()}</div><div class="sub">to $${(stats.price_max||0).toLocaleString()}</div></div>
    <div class="stat-card"><div class="label">Fuel Types</div><div class="value">${stats.by_fuel.length}</div><div class="sub">${stats.by_fuel.map(f=>`${f.fuel_type} (${f.count})`).join(', ')}</div></div>
  `;

  // Decade chart
  const maxDecade = Math.max(...stats.by_decade.map(d => d.count));
  document.getElementById('decade-chart').innerHTML = stats.by_decade.map(d => `
    <div class="bar-row">
      <div class="bar-label">${d.decade}s</div>
      <div class="bar-track"><div class="bar-fill" style="width:${d.count/maxDecade*100}%"><span>${d.count}</span></div></div>
    </div>
  `).join('');

  // Price chart
  const priceData = await api('/api/query?sql=' + encodeURIComponent(
    'SELECT year, MIN(price_when_new) AS price FROM vehicles WHERE price_when_new IS NOT NULL GROUP BY year ORDER BY year'
  ));
  if (priceData.rows) {
    const maxPrice = Math.max(...priceData.rows.map(r => r.price));
    document.getElementById('price-chart').innerHTML = priceData.rows.map(r => `
      <div class="bar-row">
        <div class="bar-label">${r.year}</div>
        <div class="bar-track"><div class="bar-fill" style="width:${r.price/maxPrice*100}%;background:var(--green)"><span>$${r.price.toLocaleString()}</span></div></div>
      </div>
    `).join('');
  }
}

// --- Filters ---
async function loadFilters() {
  filters = await api('/api/filters');
  const bar = document.getElementById('filters-bar');
  bar.innerHTML = `
    <div class="filter-group">
      <label>Search</label>
      <input type="text" id="f-search" placeholder="Search vehicles..." oninput="loadVehicles()">
    </div>
    <div class="filter-group">
      <label>Year From</label>
      <select id="f-year-min" onchange="loadVehicles()">
        <option value="">All</option>
        ${filters.years.map(y => `<option value="${y}">${y}</option>`).join('')}
      </select>
    </div>
    <div class="filter-group">
      <label>Year To</label>
      <select id="f-year-max" onchange="loadVehicles()">
        <option value="">All</option>
        ${filters.years.map(y => `<option value="${y}">${y}</option>`).join('')}
      </select>
    </div>
    <div class="filter-group">
      <label>Badge</label>
      <select id="f-badge" onchange="loadVehicles()">
        <option value="">All</option>
        ${filters.badges.map(b => `<option value="${b}">${b}</option>`).join('')}
      </select>
    </div>
    <div class="filter-group">
      <label>Fuel Type</label>
      <select id="f-fuel" onchange="loadVehicles()">
        <option value="">All</option>
        ${filters.fuel_types.map(f => `<option value="${f}">${f}</option>`).join('')}
      </select>
    </div>
    <div class="filter-group">
      <label>&nbsp;</label>
      <button class="btn btn-secondary" onclick="resetFilters()">Reset</button>
    </div>
  `;
}

function resetFilters() {
  document.getElementById('f-search').value = '';
  document.getElementById('f-year-min').value = '';
  document.getElementById('f-year-max').value = '';
  document.getElementById('f-badge').value = '';
  document.getElementById('f-fuel').value = '';
  loadVehicles();
}

// --- Vehicles table ---
const COLUMNS = [
  { key: '_select', label: '', sortable: false },
  { key: 'year', label: 'Year', sortable: true },
  { key: 'badge', label: 'Badge', sortable: true },
  { key: 'variant', label: 'Variant', sortable: true },
  { key: 'fuel_type', label: 'Fuel', sortable: false },
  { key: 'price_when_new', label: 'Price', sortable: true, fmt: 'price' },
  { key: 'power_kw', label: 'Power (kW)', sortable: true, fmt: 'num1' },
  { key: 'torque_nm', label: 'Torque (Nm)', sortable: true, fmt: 'num0' },
  { key: 'accel_0_100_s', label: '0-100', sortable: true, fmt: 'num1' },
  { key: 'fuel_combined_lper100', label: 'L/100km', sortable: true, fmt: 'num1' },
  { key: 'kerb_weight_kg', label: 'Weight (kg)', sortable: true, fmt: 'num0' },
];

function renderThead() {
  document.getElementById('vehicles-thead').innerHTML = COLUMNS.map(c => {
    if (!c.sortable) return `<th>${c.label}</th>`;
    const arrow = currentSort.col === c.key
      ? (currentSort.order === 'asc' ? ' &#9650;' : ' &#9660;')
      : '';
    return `<th onclick="sortBy('${c.key}')">${c.label}<span class="sort-arrow">${arrow}</span></th>`;
  }).join('');
}

function fmtVal(val, fmt) {
  if (val == null) return '<span style="color:var(--text2)">—</span>';
  if (fmt === 'price') return `<span class="price">$${Number(val).toLocaleString()}</span>`;
  if (fmt === 'num0') return Number(val).toLocaleString(undefined, {maximumFractionDigits:0});
  if (fmt === 'num1') return Number(val).toFixed(1);
  return val;
}

function renderVehicles() {
  renderThead();
  const tbody = document.getElementById('vehicles-tbody');
  tbody.innerHTML = allVehicles.map(v => {
    const selected = compareSet.has(v.id);
    return `<tr class="${selected?'selected':''}" ondblclick="showDetail(${v.id})">
      ${COLUMNS.map(c => {
        if (c.key === '_select') return `<td><input type="checkbox" ${selected?'checked':''} onchange="toggleCompare(${v.id}, this.checked)"></td>`;
        const cls = c.fmt ? 'num' : '';
        return `<td class="${cls}">${fmtVal(v[c.key], c.fmt)}</td>`;
      }).join('')}
    </tr>`;
  }).join('');
}

async function loadVehicles() {
  const params = new URLSearchParams();
  const search = document.getElementById('f-search')?.value;
  const yearMin = document.getElementById('f-year-min')?.value;
  const yearMax = document.getElementById('f-year-max')?.value;
  const badge = document.getElementById('f-badge')?.value;
  const fuel = document.getElementById('f-fuel')?.value;

  if (search) params.set('search', search);
  if (yearMin) params.set('year_min', yearMin);
  if (yearMax) params.set('year_max', yearMax);
  if (badge) params.set('badge', badge);
  if (fuel) params.set('fuel_type', fuel);
  params.set('sort', currentSort.col);
  params.set('order', currentSort.order);

  const data = await api('/api/vehicles?' + params.toString());
  allVehicles = data.vehicles;
  renderVehicles();
}

function sortBy(col) {
  if (currentSort.col === col) {
    currentSort.order = currentSort.order === 'asc' ? 'desc' : 'asc';
  } else {
    currentSort.col = col;
    currentSort.order = col === 'year' || col === 'price_when_new' || col === 'power_kw' || col === 'torque_nm' || col === 'kerb_weight_kg'
      ? 'desc' : 'asc';
  }
  loadVehicles();
}

// --- Compare ---
function toggleCompare(id, checked) {
  if (checked) compareSet.add(id); else compareSet.delete(id);
  updateCompareBar();
  renderVehicles();
}

function updateCompareBar() {
  const bar = document.getElementById('compare-bar');
  const chips = document.getElementById('compare-chips');
  if (compareSet.size === 0) { bar.style.display = 'none'; return; }
  bar.style.display = 'flex';
  chips.innerHTML = Array.from(compareSet).map(id => {
    const v = allVehicles.find(x => x.id === id);
    const name = v ? `${v.year} ${v.badge || v.variant}` : `#${id}`;
    return `<div class="chip">${name}<span class="remove" onclick="toggleCompare(${id},false)">&times;</span></div>`;
  }).join('');
}

function clearCompare() {
  compareSet.clear();
  updateCompareBar();
  renderVehicles();
}

async function openCompare() {
  if (compareSet.size < 2) return alert('Select at least 2 vehicles');
  const ids = Array.from(compareSet).join(',');
  const data = await api('/api/compare?ids=' + ids);

  // Switch to compare tab
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelector('[data-tab="compare"]').classList.add('active');
  document.getElementById('panel-compare').classList.add('active');

  document.getElementById('compare-empty').style.display = 'none';
  document.getElementById('compare-content').style.display = 'block';

  const vehicles = data.vehicles;
  const specs = data.specs;

  // Group specs by section > key
  const sections = {};
  for (const s of specs) {
    if (!sections[s.section]) sections[s.section] = {};
    if (!sections[s.section][s.key]) sections[s.section][s.key] = {};
    sections[s.section][s.key][s.vehicle_id] = s;
  }

  // Overview rows
  const overviewKeys = [
    {key: 'year', label: 'Year'},
    {key: 'badge', label: 'Badge'},
    {key: 'series', label: 'Series'},
    {key: 'fuel_type', label: 'Fuel Type'},
    {key: 'transmission', label: 'Transmission'},
    {key: 'price_when_new', label: 'Price When New', fmt: 'price'},
  ];

  let html = `<thead><tr><th></th>${vehicles.map(v =>
    `<th style="max-width:180px;white-space:normal">${v.vehicle_name}</th>`
  ).join('')}</tr></thead><tbody>`;

  // Overview section
  html += `<tr class="section-header"><td colspan="${vehicles.length+1}">Overview</td></tr>`;
  for (const {key, label, fmt} of overviewKeys) {
    html += `<tr><td style="color:var(--text2)">${label}</td>`;
    for (const v of vehicles) {
      const val = v[key];
      html += `<td>${fmt === 'price' && val ? '$' + Number(val).toLocaleString() : (val || '—')}</td>`;
    }
    html += '</tr>';
  }

  // Spec sections
  for (const [section, keys] of Object.entries(sections)) {
    html += `<tr class="section-header"><td colspan="${vehicles.length+1}">${section}</td></tr>`;
    for (const [key, byVehicle] of Object.entries(keys)) {
      // Find best value for numeric comparisons
      const numVals = vehicles.map(v => byVehicle[v.id]?.numeric_value).filter(x => x != null);
      const isLowerBetter = key.includes('Consumption') || key.includes('CO2') || key.includes('Acceleration') || key.includes('Emission');
      const bestVal = numVals.length > 0 ? (isLowerBetter ? Math.min(...numVals) : Math.max(...numVals)) : null;

      html += `<tr><td style="color:var(--text2)">${key}</td>`;
      for (const v of vehicles) {
        const s = byVehicle[v.id];
        const val = s ? s.value : '—';
        const isBest = s && s.numeric_value != null && s.numeric_value === bestVal && numVals.length > 1;
        html += `<td class="${isBest ? 'highlight-best' : ''}">${val}</td>`;
      }
      html += '</tr>';
    }
  }

  html += '</tbody>';
  document.getElementById('compare-table').innerHTML = html;
}

// --- Detail modal ---
async function showDetail(id) {
  const data = await api('/api/vehicle/' + id);
  const v = data.vehicle;
  const specs = data.specs;

  // Group specs by section
  const sections = {};
  for (const s of specs) {
    if (!sections[s.section]) sections[s.section] = [];
    sections[s.section].push(s);
  }

  let html = `<h2>${v.vehicle_name}</h2>
    <div class="subtitle">${v.badge || ''} ${v.series || ''} | ${v.fuel_type || ''} | ${v.drive_type || ''} | ${v.transmission || ''}
    ${v.price_when_new ? ' | $' + v.price_when_new.toLocaleString() : ''}</div>`;

  for (const [section, rows] of Object.entries(sections)) {
    html += `<div class="spec-section"><h3>${section}</h3>`;
    for (const s of rows) {
      html += `<div class="spec-row"><div class="spec-key">${s.key}</div><div class="spec-val">${s.value}</div></div>`;
    }
    html += '</div>';
  }

  document.getElementById('modal-content').innerHTML = html;
  document.getElementById('detail-modal').classList.add('show');
}

function closeModal() {
  document.getElementById('detail-modal').classList.remove('show');
}
document.getElementById('detail-modal').addEventListener('click', e => {
  if (e.target === e.currentTarget) closeModal();
});
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

// --- SQL Query ---
function setQuery(sql) {
  document.getElementById('sql-input').value = sql;
  runQuery();
}

async function runQuery() {
  const sql = document.getElementById('sql-input').value.trim();
  if (!sql) return;
  const data = await api('/api/query?sql=' + encodeURIComponent(sql));

  if (data.error) {
    document.getElementById('query-info').textContent = 'Error: ' + data.error;
    document.getElementById('query-thead').innerHTML = '';
    document.getElementById('query-tbody').innerHTML = '';
    return;
  }

  document.getElementById('query-info').textContent = `${data.count} row(s) returned`;
  document.getElementById('query-thead').innerHTML = data.columns.map(c => `<th>${c}</th>`).join('');
  document.getElementById('query-tbody').innerHTML = data.rows.map(r =>
    '<tr>' + data.columns.map(c => {
      const v = r[c];
      if (v == null) return '<td style="color:var(--text2)">NULL</td>';
      if (typeof v === 'number' && c.toLowerCase().includes('price'))
        return `<td class="num price">$${v.toLocaleString()}</td>`;
      if (typeof v === 'number')
        return `<td class="num">${v.toLocaleString(undefined, {maximumFractionDigits:2})}</td>`;
      return `<td>${v}</td>`;
    }).join('') + '</tr>'
  ).join('');
}

// --- Init ---
async function init() {
  await loadDashboard();
  await loadFilters();
  await loadVehicles();
  // Auto-run default query
  runQuery();
}
init();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Touareg Database Explorer")
    parser.add_argument("--db", default="output/touareg-specs/touareg.db", help="Path to SQLite database")
    parser.add_argument("--port", type=int, default=8050, help="Port to serve on (default: 8050)")
    parser.add_argument("--no-open", action="store_true", help="Don't auto-open browser")
    args = parser.parse_args()

    global _db_path  # noqa: PLW0603
    _db_path = Path(args.db)

    if not _db_path.exists():
        print(f"Error: database not found at {_db_path}")
        print("Run 'python build_touareg_db.py' first to create it.")
        return

    url = f"http://localhost:{args.port}"
    print(f"Touareg Explorer: {url}")
    print(f"Database: {_db_path}")

    if not args.no_open:
        import threading
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
