// nokia-fastmile-card.js — Karta statusu routera Nokia FastMile dla Home Assistant
// Wersja 2.0.0 — Wykresy historyczne + status

const DEFAULT_ENTITY_ID = 'sensor.nokia_fastmile_5g_connection_state';
const CHART_LIBRARY_URL = 'https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js';

// ── Styles (design tokens spójne z HomePulse) ────────────────────────────────
const STYLES = `
  :host { display: block; font-family: var(--primary-font-family, 'Segoe UI', sans-serif); }

  ha-card { padding: 16px; box-sizing: border-box; }

  /* ── Nagłówek (identyczny z HomePulse) ── */
  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }
  .header-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--primary-text-color);
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .header-title ha-icon { color: var(--primary-color); }

  .header-actions { display: flex; gap: 6px; align-items: center; }

  /* ── Status routera ── */
  .status-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
    padding: 12px;
    border-radius: 12px;
    background: var(--card-background-color);
    border: 1px solid var(--divider-color);
  }
  .status-icon {
    font-size: 2rem;
    color: var(--primary-color);
  }
  .status-text {
    flex: 1;
  }
  .status-title {
    font-size: 1rem;
    font-weight: 600;
    color: var(--primary-text-color);
    margin-bottom: 4px;
  }
  .status-subtitle {
    font-size: 0.85rem;
    color: var(--secondary-text-color);
  }

  /* ── Sygnały ── */
  .signals-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 12px;
    margin-bottom: 16px;
  }
  .signal-card {
    display: flex;
    flex-direction: column;
    padding: 12px;
    border-radius: 12px;
    background: var(--card-background-color);
    border: 1px solid var(--divider-color);
    text-align: center;
  }
  .signal-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--primary-color);
    margin-bottom: 4px;
  }
  .signal-unit {
    font-size: 0.8rem;
    color: var(--secondary-text-color);
    margin-bottom: 8px;
  }
  .signal-label {
    font-size: 0.85rem;
    color: var(--primary-text-color);
    font-weight: 600;
  }
  .signal-type {
    font-size: 0.7rem;
    color: var(--secondary-text-color);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  /* ── Transfer danych ── */
  .transfer-section {
    margin-bottom: 16px;
  }
  .transfer-title {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--primary-text-color);
    margin-bottom: 8px;
  }
  .transfer-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .transfer-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    border-radius: 8px;
    background: var(--card-background-color);
    border: 1px solid var(--divider-color);
  }
  .transfer-label {
    font-size: 0.85rem;
    color: var(--primary-text-color);
  }
  .transfer-value {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--primary-color);
  }

  /* ── Informacje systemowe ── */
  .system-info {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 8px;
  }
  .info-item {
    display: flex;
    flex-direction: column;
    padding: 8px 12px;
    border-radius: 8px;
    background: var(--card-background-color);
    border: 1px solid var(--divider-color);
    text-align: center;
  }
  .info-value {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--primary-color);
    margin-bottom: 2px;
  }
  .info-label {
    font-size: 0.75rem;
    color: var(--secondary-text-color);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  /* ── Responsywność ── */
  @media (max-width: 600px) {
    .signals-grid { grid-template-columns: 1fr; }
    .transfer-grid { grid-template-columns: 1fr; }
    .system-info { grid-template-columns: 1fr 1fr; }
  }

  /* ── Wykresy ── */
  .charts-section {
    margin-top: 20px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .chart-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }
  .chart-title {
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--primary-text-color);
  }
  .time-selector {
    display: flex;
    gap: 4px;
  }
  .time-btn {
    padding: 4px 12px;
    border-radius: 6px;
    border: 1px solid var(--divider-color);
    background: var(--card-background-color);
    color: var(--primary-text-color);
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.2s;
  }
  .time-btn:hover {
    background: var(--primary-color);
    color: white;
    border-color: var(--primary-color);
  }
  .time-btn.active {
    background: var(--primary-color);
    color: white;
    border-color: var(--primary-color);
  }
  .chart-container {
    position: relative;
    height: 250px;
    background: var(--card-background-color);
    border-radius: 12px;
    border: 1px solid var(--divider-color);
    padding: 12px;
  }
`;


// ── Główna klasa karty ──────────────────────────────────────────────────────
class NokiaFastMileCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._hass = null;
    this._config = {};
    this._entities = {};
    this._charts = {};
    this._chartLib = null;
    this._timeRange = '24h'; // '24h', '7d', '30d'
    this._historyData = {};
    this._updateSchedule = null;
  }

  set hass(hass) {
    this._hass = hass;
    this._updateEntities();
    
    if (!this._chartLib) {
      this._loadChartLibrary().then(() => {
        this._render();
        this._loadHistoryData();
        this._scheduleUpdates();
      });
    } else {
      this._render();
      this._loadHistoryData();
    }
  }

  setConfig(config) {
    this._config = config;
  }

  getCardSize() {
    return 6;
  }

  _updateEntities() {
    if (!this._hass) return;

    const baseEntity = this._config.entity || DEFAULT_ENTITY_ID;
    const entityId = baseEntity.replace('_connection_state', '');

    this._entities = {
      connection_state: this._hass.states[`${entityId}_connection_state`],
      wan_mode: this._hass.states[`${entityId}_wan_mode`],
      wan_active: this._hass.states[`${entityId}_wan_active`],
      uptime: this._hass.states[`${entityId}_uptime`],
      sw_version: this._hass.states[`${entityId}_sw_version`],
      serial_number: this._hass.states[`${entityId}_serial_number`],
      connected_devices: this._hass.states[`${entityId}_connected_devices`],
      unread_sms: this._hass.states[`${entityId}_unread_sms`],

      // 5G signals
      '5g_rsrp': this._hass.states[`${entityId}_5g_rsrp`],
      '5g_rsrq': this._hass.states[`${entityId}_5g_rsrq`],
      '5g_sinr': this._hass.states[`${entityId}_5g_sinr`],
      '5g_signal_level': this._hass.states[`${entityId}_5g_signal_level`],
      '5g_rsrp_strength_index': this._hass.states[`${entityId}_5g_rsrp_strength_index`],

      // LTE signals
      'lte_rsrp': this._hass.states[`${entityId}_lte_rsrp`],
      'lte_rsrq': this._hass.states[`${entityId}_lte_rsrq`],
      'lte_rssi': this._hass.states[`${entityId}_lte_rssi`],
      'lte_sinr': this._hass.states[`${entityId}_lte_sinr`],
      'lte_signal_level': this._hass.states[`${entityId}_lte_signal_level`],
      'lte_rsrp_strength_index': this._hass.states[`${entityId}_lte_rsrp_strength_index`],

      // Transfer data
      cellular_bytes_received: this._hass.states[`${entityId}_cellular_bytes_received`],
      cellular_bytes_sent: this._hass.states[`${entityId}_cellular_bytes_sent`],
      ethernet_bytes_received: this._hass.states[`${entityId}_ethernet_bytes_received`],
      ethernet_bytes_sent: this._hass.states[`${entityId}_ethernet_bytes_sent`],
      ethernet_packets_received: this._hass.states[`${entityId}_ethernet_packets_received`],
      ethernet_packets_sent: this._hass.states[`${entityId}_ethernet_packets_sent`],
    };
  }

  _render() {
    if (!this._hass) return;

    const root = this.shadowRoot;
    root.innerHTML = `
      <style>${STYLES}</style>
      <ha-card>
        <div class="header">
          <div class="header-title">
            <ha-icon icon="mdi:router-network"></ha-icon>
            Nokia FastMile 5G
          </div>
        </div>

        ${this._renderStatus()}

        <div class="signals-grid">
          ${this._renderSignalCard('5g_rsrp', '5G RSRP', 'dBm')}
          ${this._renderSignalCard('5g_rsrq', '5G RSRQ', 'dB')}
          ${this._renderSignalCard('5g_sinr', '5G SINR', 'dB')}
          ${this._renderSignalCard('lte_rsrp', 'LTE RSRP', 'dBm')}
          ${this._renderSignalCard('lte_rsrq', 'LTE RSRQ', 'dB')}
          ${this._renderSignalCard('lte_rssi', 'LTE RSSI', 'dBm')}
        </div>

        <div class="transfer-section">
          <div class="transfer-title">Transfer danych</div>
          <div class="transfer-grid">
            ${this._renderTransferItem('cellular_bytes_received', 'Cellular ↓')}
            ${this._renderTransferItem('cellular_bytes_sent', 'Cellular ↑')}
            ${this._renderTransferItem('ethernet_bytes_received', 'Ethernet ↓')}
            ${this._renderTransferItem('ethernet_bytes_sent', 'Ethernet ↑')}
          </div>
        </div>

        <div class="system-info">
          ${this._renderInfoItem('uptime', 'Uptime', 's')}
          ${this._renderInfoItem('connected_devices', 'Urządzenia')}
          ${this._renderInfoItem('unread_sms', 'SMS')}
          ${this._renderInfoItem('sw_version', 'Wersja')}
        </div>

        <div class="charts-section">
          <div class="chart-header">
            <div class="chart-title">Sygnały (RSRP)</div>
            <div class="time-selector">
              <button class="time-btn active" data-range="24h" onclick="this.getRootNode().host._setTimeRange('24h')">24h</button>
              <button class="time-btn" data-range="7d" onclick="this.getRootNode().host._setTimeRange('7d')">7d</button>
              <button class="time-btn" data-range="30d" onclick="this.getRootNode().host._setTimeRange('30d')">30d</button>
            </div>
          </div>
          <div class="chart-container">
            <canvas id="signal-chart-canvas"></canvas>
          </div>

          <div class="chart-header">
            <div class="chart-title">Transfer danych (Download)</div>
          </div>
          <div class="chart-container">
            <canvas id="transfer-chart-canvas"></canvas>
          </div>
        </div>
      </ha-card>
    `;

    // Podepnij event listenery do przycisków
    root.querySelectorAll('.time-btn').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        const range = e.target.dataset.range;
        this._setTimeRange(range);
      });
    });
  }

  _renderStatus() {
    const state = this._entities.connection_state;
    if (!state) return '';

    const isConnected = state.state === 'Connected';
    const icon = isConnected ? 'mdi:wifi-check' : 'mdi:wifi-off';
    const color = isConnected ? 'var(--success-color, #10b981)' : 'var(--error-color, #ef4444)';

    return `
      <div class="status-row" style="border-left: 4px solid ${color};">
        <ha-icon class="status-icon" icon="${icon}" style="color: ${color};"></ha-icon>
        <div class="status-text">
          <div class="status-title">${state.state}</div>
          <div class="status-subtitle">
            ${this._entities.wan_mode?.state || 'Unknown'} • ${this._entities.wan_active?.state || 'Unknown'}
          </div>
        </div>
      </div>
    `;
  }

  _renderSignalCard(key, label, unit) {
    const entity = this._entities[key];
    if (!entity) return '';

    const value = entity.state;
    const type = key.startsWith('5g') ? '5G' : 'LTE';

    return `
      <div class="signal-card">
        <div class="signal-value">${value !== 'unknown' ? value : '—'}</div>
        <div class="signal-unit">${unit}</div>
        <div class="signal-label">${label.replace(/5G |LTE /, '')}</div>
        <div class="signal-type">${type}</div>
      </div>
    `;
  }

  _renderTransferItem(key, label) {
    const entity = this._entities[key];
    if (!entity) return '';

    const value = parseInt(entity.state) || 0;
    const formatted = this._formatBytes(value);

    return `
      <div class="transfer-item">
        <span class="transfer-label">${label}</span>
        <span class="transfer-value">${formatted}</span>
      </div>
    `;
  }

  _renderInfoItem(key, label, unit = '') {
    const entity = this._entities[key];
    if (!entity) return '';

    let value = entity.state;
    if (key === 'uptime' && value !== 'unknown') {
      value = this._formatDuration(parseInt(value));
    }

    return `
      <div class="info-item">
        <div class="info-value">${value !== 'unknown' ? value : '—'}</div>
        <div class="info-label">${label}</div>
      </div>
    `;
  }

  _formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  _formatDuration(seconds) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const mins = Math.floor((seconds % 3600) / 60);

    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${mins}m`;
    return `${mins}m`;
  }

  // ── Ładowanie biblioteki Chart.js ──
  async _loadChartLibrary() {
    return new Promise((resolve) => {
      if (window.Chart) {
        this._chartLib = window.Chart;
        resolve();
        return;
      }

      const script = document.createElement('script');
      script.src = CHART_LIBRARY_URL;
      script.onload = () => {
        this._chartLib = window.Chart;
        resolve();
      };
      script.onerror = () => {
        console.warn('Failed to load Chart.js');
        resolve();
      };
      document.head.appendChild(script);
    });
  }

  // ── Harmonogram aktualizacji ──
  _scheduleUpdates() {
    if (this._updateSchedule) clearInterval(this._updateSchedule);
    this._updateSchedule = setInterval(() => this._loadHistoryData(), 300000); // 5 minut
  }

  // ── Pobieranie danych historycznych z API HA ──
  async _loadHistoryData() {
    if (!this._hass) return;

    const baseEntity = this._config.entity || DEFAULT_ENTITY_ID;
    const entityId = baseEntity.replace('_connection_state', '');

    // Mapowanie encji do pobierania historii
    const historyEntities = [
      `${entityId}_5g_rsrp`,
      `${entityId}_lte_rsrp`,
      `${entityId}_cellular_bytes_received`,
      `${entityId}_ethernet_bytes_received`,
    ];

    try {
      const endTime = new Date();
      const startTime = new Date(endTime.getTime() - this._getTimeRangeMs());

      const response = await this._hass.callWS({
        type: 'history/history_stats',
        start_time: startTime.toISOString(),
        end_time: endTime.toISOString(),
        entity_ids: historyEntities,
        period: '1h',
        statistic_types: ['mean'],
      }).catch(() => null);

      if (response) {
        this._historyData = response;
        this._updateCharts();
      } else {
        // Fallback: pobierz data bezpośrednio z historii
        await this._loadHistoryFallback(historyEntities, startTime, endTime);
      }
    } catch (error) {
      console.warn('Error loading history:', error);
    }
  }

  async _loadHistoryFallback(entityIds, startTime, endTime) {
    if (!this._hass?.auth?.callApi) return;

    try {
      const startStr = startTime.toISOString();
      const endStr = endTime.toISOString();
      const entitiesParam = entityIds.join(',');

      const history = await this._hass.auth.callApi(
        'get',
        `/api/history/period/${startStr}?end_time=${endStr}&entity_ids=${entitiesParam}`
      );

      if (Array.isArray(history)) {
        this._processHistoryData(history);
        this._updateCharts();
      }
    } catch (error) {
      console.warn('Error with history fallback:', error);
    }
  }

  _processHistoryData(history) {
    this._historyData = {};
    history.forEach((entityHistory) => {
      if (entityHistory[0]) {
        const entityId = entityHistory[0].entity_id;
        this._historyData[entityId] = entityHistory;
      }
    });
  }

  _getTimeRangeMs() {
    switch (this._timeRange) {
      case '7d': return 7 * 24 * 60 * 60 * 1000;
      case '30d': return 30 * 24 * 60 * 60 * 1000;
      default: return 24 * 60 * 60 * 1000; // 24h
    }
  }

  // ── Aktualizacja wykresów ──
  _updateCharts() {
    if (!this._chartLib) return;

    this._updateSignalChart();
    this._updateTransferChart();
  }

  _updateSignalChart() {
    const ctx = this.shadowRoot.querySelector('#signal-chart-canvas');
    if (!ctx) return;

    const baseEntity = this._config.entity || DEFAULT_ENTITY_ID;
    const entityId = baseEntity.replace('_connection_state', '');

    const rsrpData = this._extractChartData(`${entityId}_5g_rsrp`);
    const lteRsrpData = this._extractChartData(`${entityId}_lte_rsrp`);

    const labels = rsrpData.times.map((t) => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));

    if (this._charts.signal) {
      this._charts.signal.destroy();
    }

    this._charts.signal = new this._chartLib(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: '5G RSRP (dBm)',
            data: rsrpData.values,
            borderColor: 'rgb(59, 130, 246)',
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            tension: 0.3,
            fill: true,
          },
          {
            label: 'LTE RSRP (dBm)',
            data: lteRsrpData.values,
            borderColor: 'rgb(34, 197, 94)',
            backgroundColor: 'rgba(34, 197, 94, 0.1)',
            tension: 0.3,
            fill: true,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: true, position: 'top' },
        },
        scales: {
          y: {
            beginAtZero: false,
            title: { display: true, text: 'dBm' },
          },
        },
      },
    });
  }

  _updateTransferChart() {
    const ctx = this.shadowRoot.querySelector('#transfer-chart-canvas');
    if (!ctx) return;

    const baseEntity = this._config.entity || DEFAULT_ENTITY_ID;
    const entityId = baseEntity.replace('_connection_state', '');

    const cellularData = this._extractChartData(`${entityId}_cellular_bytes_received`);
    const ethernetData = this._extractChartData(`${entityId}_ethernet_bytes_received`);

    const labels = cellularData.times.map((t) => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));

    if (this._charts.transfer) {
      this._charts.transfer.destroy();
    }

    this._charts.transfer = new this._chartLib(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Cellular Download (MB)',
            data: cellularData.values.map((v) => v / 1048576),
            borderColor: 'rgb(139, 92, 246)',
            backgroundColor: 'rgba(139, 92, 246, 0.1)',
            tension: 0.3,
            fill: true,
          },
          {
            label: 'Ethernet Download (MB)',
            data: ethernetData.values.map((v) => v / 1048576),
            borderColor: 'rgb(236, 72, 153)',
            backgroundColor: 'rgba(236, 72, 153, 0.1)',
            tension: 0.3,
            fill: true,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: true, position: 'top' },
        },
        scales: {
          y: {
            beginAtZero: true,
            title: { display: true, text: 'MB' },
          },
        },
      },
    });
  }

  _extractChartData(entityId) {
    const history = this._historyData[entityId] || [];
    const times = [];
    const values = [];

    history.forEach((state) => {
      if (state.state && state.state !== 'unknown' && !isNaN(parseFloat(state.state))) {
        times.push(state.last_changed || state.last_updated);
        values.push(parseFloat(state.state));
      }
    });

    return { times, values };
  }

  // ── Obsługa zmiany zakresu czasowego ──
  _setTimeRange(range) {
    this._timeRange = range;
    this.shadowRoot.querySelectorAll('.time-btn').forEach((btn) => {
      btn.classList.remove('active');
    });
    this.shadowRoot.querySelector(`[data-range="${range}"]`)?.classList.add('active');
    this._loadHistoryData();
  }

customElements.define('nokia-fastmile-card', NokiaFastMileCard);

// ── Konfiguracja dla Lovelace ───────────────────────────────────────────────
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'nokia-fastmile-card',
  name: 'Nokia FastMile Card',
  description: 'Karta statusu routera Nokia FastMile 5G',
  preview: true,
});