/**
 * Nokia FastMile 5G Card — Lovelace card for signal monitoring.
 * Visual style mirrors HomePulse / Rehab Monitor Card (same design tokens).
 * Vanilla Web Component — no external dependencies.
 *
 * Usage in dashboard:
 *   type: custom:nokia-fastmile-card
 *   title: "Nokia FastMile 5G"   # optional
 */

// ── Signal quality thresholds ─────────────────────────────────────────────────
const Q = {
  rsrp: { good: -80, warn: -100 },   // dBm
  rsrq: { good: -10, warn: -15 },    // dB
  sinr: { good: 10,  warn: 0  },     // dB
};

function qColor(v, t) {
  if (v === null || v === undefined) return "var(--secondary-text-color)";
  if (v >= t.good) return "var(--success-color, #4caf50)";
  if (v >= t.warn) return "var(--warning-color, #ff9800)";
  return "var(--error-color, #db4437)";
}

function levelColor(lv) {
  if (lv === null) return "var(--secondary-text-color)";
  if (lv >= 4)    return "var(--success-color, #4caf50)";
  if (lv >= 2)    return "var(--warning-color, #ff9800)";
  return "var(--error-color, #db4437)";
}

function val(state) {
  if (!state || ["unavailable", "unknown"].includes(state.state)) return null;
  const n = parseFloat(state.state);
  return isNaN(n) ? state.state : n;
}

function fmtUptime(sec) {
  if (sec === null || sec === undefined) return "—";
  const d = Math.floor(sec / 86400);
  const h = Math.floor((sec % 86400) / 3600);
  const m = Math.floor((sec % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function fmtBytes(bytes) {
  if (bytes === null || bytes === undefined) return "—";
  const n = Number(bytes);
  if (!Number.isFinite(n)) return "—";
  if (n === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(Math.floor(Math.log(n) / Math.log(1024)), units.length - 1);
  return `${(n / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 2)} ${units[i]}`;
}

function fmtTraffic(state) {
  const value = val(state);
  if (value === null || value === undefined) return "—";
  const unit = state?.attributes?.unit_of_measurement;
  if (unit && unit.toLowerCase() !== "b") {
    const n = Number(value);
    const display = Number.isFinite(n) ? n.toFixed(2) : value;
    return `${display} ${unit}`;
  }
  return fmtBytes(value);
}

// ── Styles (same design tokens as home-pulse-card) ────────────────────────────
const STYLES = `
  :host { display: block; }

  ha-card { padding: 16px; box-sizing: border-box; }

  /* Header */
  .header {
    display: flex; align-items: flex-start;
    justify-content: space-between; margin-bottom: 14px;
  }
  .header-title {
    font-size: 1.1rem; font-weight: 600;
    color: var(--primary-text-color);
    display: flex; align-items: center; gap: 8px;
  }
  .header-title ha-icon { color: var(--primary-color); }
  .header-meta {
    font-size: 0.72rem; color: var(--secondary-text-color); margin-top: 2px;
  }
  .badge {
    font-size: 0.72rem; font-weight: 700; padding: 3px 10px;
    border-radius: 20px; white-space: nowrap; margin-top: 2px;
  }
  .badge.ok   { background: color-mix(in srgb, var(--success-color,#4caf50) 15%, transparent);
                color: var(--success-color, #4caf50); }
  .badge.err  { background: color-mix(in srgb, var(--error-color,#db4437) 15%, transparent);
                color: var(--error-color, #db4437); }
  .badge.unk  { background: color-mix(in srgb, var(--secondary-text-color) 12%, transparent);
                color: var(--secondary-text-color); }

  /* Signal panels grid */
  .panels { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px; }

  .panel {
    padding: 10px 12px; border-radius: 12px;
    background: var(--card-background-color);
    border: 1px solid var(--divider-color);
  }
  .panel-title {
    font-size: 0.72rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
    color: var(--secondary-text-color); margin-bottom: 8px;
  }

  /* Signal bars */
  .bars { display: flex; align-items: flex-end; gap: 3px; margin-bottom: 8px; height: 18px; }
  .bar {
    width: 7px; border-radius: 2px 2px 0 0;
    background: var(--divider-color);
  }
  .bar.b1 { height: 30%; } .bar.b2 { height: 48%; }
  .bar.b3 { height: 64%; } .bar.b4 { height: 82%; } .bar.b5 { height: 100%; }
  .bar.filled { background: var(--bar-color, var(--primary-color)); }
  .level-label { font-size: 0.75rem; font-weight: 600; color: var(--bar-color, var(--primary-color)); margin-left: 4px; align-self: center; }

  /* Metric rows */
  .metric { display: flex; justify-content: space-between; align-items: center;
            padding: 2px 0; font-size: 0.82rem; }
  .metric-label { color: var(--secondary-text-color); }
  .metric-value { font-weight: 600; font-variant-numeric: tabular-nums; }

  /* Charts */
  .charts { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
  .chart-wrap {
    border-radius: 12px; background: var(--card-background-color);
    border: 1px solid var(--divider-color); overflow: hidden;
  }
  .chart-header {
    display: flex; justify-content: space-between; align-items: center;
    padding: 6px 10px 2px;
  }
  .chart-label { font-size: 0.72rem; font-weight: 600; color: var(--secondary-text-color); }
  .chart-current { font-size: 0.72rem; font-weight: 700; }
  svg.sparkline { display: block; width: 100%; height: 56px; }

  /* Transfer */
  .transfer {
    display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 8px; margin-bottom: 12px;
  }
  .traffic {
    border: 1px solid var(--divider-color); border-radius: 10px;
    padding: 8px 10px; background: var(--card-background-color);
  }
  .traffic-label {
    font-size: 0.7rem; color: var(--secondary-text-color);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .traffic-value {
    margin-top: 3px; font-size: 0.9rem; font-weight: 700;
    color: var(--primary-text-color); font-variant-numeric: tabular-nums;
  }

  /* Footer */
  .footer {
    display: flex; gap: 6px; flex-wrap: wrap;
    padding-top: 10px; border-top: 1px solid var(--divider-color);
  }
  .stat {
    display: flex; align-items: center; gap: 5px;
    font-size: 0.8rem; color: var(--secondary-text-color);
    padding: 4px 8px; border-radius: 8px;
    background: color-mix(in srgb, var(--divider-color) 40%, transparent);
  }
  .stat ha-icon { --mdc-icon-size: 16px; color: var(--primary-color); }
  .stat b { color: var(--primary-text-color); }

  /* Unavailable */
  .unavail {
    text-align: center; padding: 28px 0;
    color: var(--secondary-text-color); font-size: 0.9rem;
  }
  .unavail ha-icon { --mdc-icon-size: 38px; display: block; margin: 0 auto 8px;
                     color: var(--primary-color); opacity: .4; }

  @media (max-width: 520px) {
    .panels { grid-template-columns: 1fr; }
    .transfer { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  }
`;

// ── Card ──────────────────────────────────────────────────────────────────────
class NokiaFastMileCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._history = {};          // entity_id → [{t, v}]
    this._historyFetchedAt = 0;
    this._historyFetching = false;
  }

  // ── HA interface ──────────────────────────────────────────────────────────

  setConfig(config) {
    this._config = config;
    this._render();
  }

  set hass(hass) {
    const prev = this._hass;
    this._hass = hass;

    // Re-render only when relevant entities change
    const ids = this._relevantIds();
    const changed = !prev || ids.some(id => prev.states[id] !== hass.states[id]);
    if (!changed) return;

    this._render();

    // Fetch history at most every 5 minutes
    if (Date.now() - this._historyFetchedAt > 5 * 60 * 1000 && !this._historyFetching) {
      this._fetchHistory();
    }
  }

  static getStubConfig() {
    return { title: "Nokia FastMile 5G" };
  }

  // ── Entity discovery ──────────────────────────────────────────────────────
  // Finds sensor entities by friendly_name keyword (case-insensitive).
  // With `has_entity_name = True` in HA, friendly_name = "{device} {sensor}",
  // e.g. "Nokia FastMile 5G (192.168.192.1) 5G RSRP".

  _find(keyword) {
    const states = this._hass?.states;
    if (!states) return null;
    const kw = keyword.toLowerCase();
    for (const [id, s] of Object.entries(states)) {
      if (!id.startsWith("sensor.")) continue;
      if ((s.attributes.friendly_name ?? "").toLowerCase().includes(kw)) return s;
    }
    return null;
  }

  _relevantIds() {
    if (!this._hass) return [];
    return Object.keys(this._hass.states).filter(id =>
      id.startsWith("sensor.") &&
      (this._hass.states[id].attributes.friendly_name ?? "").toLowerCase().includes("nokia fastmile")
    );
  }

  // ── History (sparklines) ──────────────────────────────────────────────────

  async _fetchHistory() {
    if (!this._hass || this._historyFetching) return;
    const s5g  = this._find("5g rsrp");
    const sLte = this._find("lte rsrp");
    const ids  = [s5g?.entity_id, sLte?.entity_id].filter(Boolean);
    if (!ids.length) return;

    this._historyFetching = true;
    const now   = new Date();
    const start = new Date(now - 2 * 3600 * 1000).toISOString();
    const end   = now.toISOString();

    try {
      const data = await this._hass.callApi(
        "GET",
        `history/period/${start}?filter_entity_id=${ids.join(",")}&end_time=${end}&minimal_response&no_attributes`
      );
      if (Array.isArray(data)) {
        for (const series of data) {
          if (!series.length) continue;
          const eid = series[0].entity_id;
          this._history[eid] = series
            .filter(s => !isNaN(parseFloat(s.state)))
            .map(s => ({ t: new Date(s.last_changed).getTime(), v: parseFloat(s.state) }));
        }
      }
    } catch (_) { /* history API unavailable */ }

    this._historyFetchedAt = Date.now();
    this._historyFetching  = false;
    this._render();
  }

  // ── SVG sparkline ─────────────────────────────────────────────────────────

  _sparklineSvg(points, color, gradId) {
    const W = 300, H = 52, PAD = 6;

    if (!points || points.length < 2) {
      return `<svg class="sparkline" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
        <text x="${W/2}" y="${H/2+4}" text-anchor="middle" fill="var(--secondary-text-color)" font-size="11" font-family="sans-serif">Brak historii</text>
      </svg>`;
    }

    const vals  = points.map(p => p.v);
    const times = points.map(p => p.t);
    const minV  = Math.min(...vals),  maxV = Math.max(...vals);
    const minT  = Math.min(...times), maxT = Math.max(...times);
    const vR    = maxV - minV || 1;
    const tR    = maxT - minT || 1;

    const x = t => ((t - minT) / tR * (W - 1)).toFixed(1);
    const y = v => (H - PAD - (v - minV) / vR * (H - PAD * 2)).toFixed(1);

    const pts    = points.map(p => `${x(p.t)},${y(p.v)}`).join(" ");
    const area   = `0,${H} ${pts} ${W - 1},${H}`;
    const lastV  = vals[vals.length - 1];
    const lastY  = parseFloat(y(lastV));
    const dotX   = parseFloat(x(times[times.length - 1]));

    return `
      <svg class="sparkline" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
        <defs>
          <linearGradient id="${gradId}" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"   stop-color="${color}" stop-opacity="0.28"/>
            <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
          </linearGradient>
        </defs>
        <polygon points="${area}" fill="url(#${gradId})"/>
        <polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.6"
                  stroke-linejoin="round" stroke-linecap="round"/>
        <circle cx="${dotX}" cy="${lastY}" r="2.5" fill="${color}"/>
      </svg>`;
  }

  // ── HTML helpers ──────────────────────────────────────────────────────────

  _barsHtml(level, color) {
    const filled = level ?? 0;
    const bars = [1,2,3,4,5].map(i =>
      `<div class="bar b${i}${i <= filled ? " filled" : ""}" style="--bar-color:${color}"></div>`
    ).join("");
    return `<div class="bars">${bars}<span class="level-label" style="--bar-color:${color}">${level ?? "—"}/5</span></div>`;
  }

  _metricHtml(label, value, unit, color) {
    const display = value === null ? "—" : `${value}`;
    const suffix  = (value !== null && unit) ? ` <span style="font-size:.7em;font-weight:400">${unit}</span>` : "";
    return `
      <div class="metric">
        <span class="metric-label">${label}</span>
        <span class="metric-value" style="color:${color}">${esc(display)}${suffix}</span>
      </div>`;
  }

  _trafficHtml(label, state) {
    return `
      <div class="traffic">
        <div class="traffic-label">${esc(label)}</div>
        <div class="traffic-value">${esc(fmtTraffic(state))}</div>
      </div>`;
  }

  _chartHtml(state, label, color, gradId) {
    const eid    = state?.entity_id;
    const points = this._history[eid] ?? [];
    const cur    = val(state);
    const curTxt = cur !== null ? `${cur} dBm` : "—";
    const curClr = cur !== null ? qColor(cur, Q.rsrp) : "var(--secondary-text-color)";

    return `
      <div class="chart-wrap">
        <div class="chart-header">
          <span class="chart-label">${label} — ostatnie 2h</span>
          <span class="chart-current" style="color:${curClr}">${esc(curTxt)}</span>
        </div>
        ${this._sparklineSvg(points, color, gradId)}
      </div>`;
  }

  // ── Render ────────────────────────────────────────────────────────────────

  _render() {
    const root = this.shadowRoot;
    root.innerHTML = "";
    const style = document.createElement("style");
    style.textContent = STYLES;
    root.appendChild(style);
    const card = document.createElement("ha-card");
    card.innerHTML = this._html();
    root.appendChild(card);
  }

  _html() {
    if (!this._hass) return `<div class="unavail"><ha-icon icon="mdi:antenna"></ha-icon>Ładowanie…</div>`;

    const title = this._config.title ?? "Nokia FastMile 5G";

    // Entities
    const eConn    = this._find("stan połączenia");
    const eWanMode = this._find("tryb wan");
    const eWanAct  = this._find("aktywny wan");

    const e5gRsrp  = this._find("5g rsrp");
    const e5gRsrq  = this._find("5g rsrq");
    const e5gSinr  = this._find("5g sinr");
    const e5gLvl   = this._find("5g poziom");
    const e5gBand  = this._find("5g band");
    const e5gArfcn = this._find("5g downlink arfcn");

    const eLteRsrp = this._find("lte rsrp");
    const eLteRsrq = this._find("lte rsrq");
    const eLteRssi = this._find("lte rssi");
    const eLteSinr = this._find("lte sinr");
    const eLteLvl  = this._find("lte poziom");
    const eLteBand = this._find("lte band");
    const eLteArfcn = this._find("lte downlink earfcn");

    const eCellRx = this._find("cellular bytes received");
    const eCellTx = this._find("cellular bytes sent");
    const eEthRx = this._find("ethernet bytes received");
    const eEthTx = this._find("ethernet bytes sent");

    const eUptime  = this._find("uptime");
    const eDevices = this._find("podłączone urządzenia");
    const eSms     = this._find("nieprzeczytane sms");

    // Check if integration is present at all
    if (!e5gRsrp && !eLteRsrp) {
      return `
        <div class="unavail">
          <ha-icon icon="mdi:antenna"></ha-icon>
          Nie znaleziono encji Nokia FastMile.<br>
          <small>Sprawdź czy integracja jest zainstalowana.</small>
        </div>`;
    }

    // Values
    const connState = val(eConn);
    const connected = typeof connState === "string"
      ? connState.toLowerCase().includes("connect")
      : null;

    const badgeClass = connected === true ? "ok" : connected === false ? "err" : "unk";
    const badgeText  = connected === true ? "Połączono"
                     : connected === false ? "Rozłączono" : "Nieznany";

    const wanMode = val(eWanMode) ?? "—";
    const wanAct  = val(eWanAct)  ?? "";

    // 5G values
    const rsrp5g = val(e5gRsrp);
    const rsrq5g = val(e5gRsrq);
    const sinr5g = val(e5gSinr);
    const lvl5g  = val(e5gLvl);
    const band5g = val(e5gBand);
    const arfcn5g = val(e5gArfcn);
    const clr5g  = levelColor(lvl5g);

    // LTE values
    const rsrpLte = val(eLteRsrp);
    const rsrqLte = val(eLteRsrq);
    const rssiLte = val(eLteRssi);
    const sinrLte = val(eLteSinr);
    const lvlLte  = val(eLteLvl);
    const bandLte = val(eLteBand);
    const arfcnLte = val(eLteArfcn);
    const clrLte  = levelColor(lvlLte);

    // Footer
    const uptime  = val(eUptime);
    const devices = val(eDevices);
    const sms     = val(eSms);

    // Last update from any entity
    const lastChanged = e5gRsrp?.last_changed ?? eLteRsrp?.last_changed;
    const updatedStr  = lastChanged
      ? new Date(lastChanged).toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" })
      : "";

    return `
      <!-- Header -->
      <div class="header">
        <div>
          <div class="header-title">
            <ha-icon icon="mdi:antenna"></ha-icon>
            ${esc(title)}
          </div>
          <div class="header-meta">
            ${esc(wanMode)}${wanAct ? ` · ${esc(wanAct)}` : ""}
            ${updatedStr ? ` · aktualizacja ${esc(updatedStr)}` : ""}
          </div>
        </div>
        <span class="badge ${badgeClass}">${badgeText}</span>
      </div>

      <!-- Signal panels -->
      <div class="panels">
        <!-- 5G NR -->
        <div class="panel">
          <div class="panel-title">5G NR</div>
          ${this._barsHtml(lvl5g, clr5g)}
          ${this._metricHtml("RSRP", rsrp5g, "dBm", qColor(rsrp5g, Q.rsrp))}
          ${this._metricHtml("RSRQ", rsrq5g, "dB",  qColor(rsrq5g, Q.rsrq))}
          ${this._metricHtml("SINR", sinr5g, "dB",  qColor(sinr5g, Q.sinr))}
          ${this._metricHtml("Band", band5g, "", "var(--primary-text-color)")}
          ${this._metricHtml("ARFCN", arfcn5g, "", "var(--primary-text-color)")}
        </div>
        <!-- LTE -->
        <div class="panel">
          <div class="panel-title">LTE</div>
          ${this._barsHtml(lvlLte, clrLte)}
          ${this._metricHtml("RSRP", rsrpLte, "dBm", qColor(rsrpLte, Q.rsrp))}
          ${this._metricHtml("RSRQ", rsrqLte, "dB",  qColor(rsrqLte, Q.rsrq))}
          ${this._metricHtml("RSSI", rssiLte, "dBm", qColor(rssiLte, Q.rsrp))}
          ${this._metricHtml("SINR", sinrLte, "dB",  qColor(sinrLte, Q.sinr))}
          ${this._metricHtml("Band", bandLte, "", "var(--primary-text-color)")}
          ${this._metricHtml("EARFCN", arfcnLte, "", "var(--primary-text-color)")}
        </div>
      </div>

      <!-- Transfer -->
      <div class="transfer">
        ${this._trafficHtml("Cellular RX", eCellRx)}
        ${this._trafficHtml("Cellular TX", eCellTx)}
        ${this._trafficHtml("Ethernet RX", eEthRx)}
        ${this._trafficHtml("Ethernet TX", eEthTx)}
      </div>

      <!-- Sparkline charts -->
      <div class="charts">
        ${this._chartHtml(e5gRsrp,  "5G RSRP",  "var(--primary-color)",              "g5")}
        ${this._chartHtml(eLteRsrp, "LTE RSRP", "var(--accent-color, var(--info-color, #2196f3))", "lt")}
      </div>

      <!-- Footer -->
      <div class="footer">
        <div class="stat">
          <ha-icon icon="mdi:timer-outline"></ha-icon>
          Uptime <b>${esc(fmtUptime(uptime))}</b>
        </div>
        <div class="stat">
          <ha-icon icon="mdi:devices"></ha-icon>
          <b>${devices ?? "—"}</b> urządz.
        </div>
        <div class="stat">
          <ha-icon icon="mdi:message-badge-outline"></ha-icon>
          SMS <b>${sms ?? "—"}</b>
        </div>
      </div>
    `;
  }
}

customElements.define("nokia-fastmile-card", NokiaFastMileCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "nokia-fastmile-card",
  name: "Nokia FastMile 5G Card",
  description: "Monitoring sygnału 5G/LTE z wykresami historii.",
  preview: false,
});
