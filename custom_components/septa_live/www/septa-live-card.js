(() => {
  const ONTIME = "#7dba98";
  const LATE = "#d4a054";
  const CRIT = "#d0726a";

  function esc(value) {
    return String(value ?? "")
      .replace(/&/g, "&")
      .replace(/</g, "<")
      .replace(/>/g, ">")
      .replace(/"/g, """);
  }

  function tone(delayMin, cancelled) {
    if (cancelled || delayMin >= 10) return CRIT;
    if (delayMin > 0) return LATE;
    return ONTIME;
  }

  function delayLabel(delayMin, cancelled, status) {
    if (cancelled) return "Cancelled";
    if (status && /cancel/i.test(status)) return status;
    if (delayMin <= 0) return "On time";
    return `${delayMin} min late`;
  }

  function findEntity(hass, suffix, fallback) {
    const states = hass && hass.states ? hass.states : {};
    const keys = Object.keys(states);
    const match = keys.find((id) => id.startsWith("sensor.septa_") && id.endsWith(suffix));
    if (match) return match;
    if (suffix === "_commute") {
      const rest = keys.find((id) => /^sensor\.septa_.+_to_/.test(id));
      if (rest) return rest;
    }
    return fallback;
  }

  function stateOf(hass, entityId) {
    if (!hass || !entityId) return null;
    return hass.states[entityId] || null;
  }

  function minutesOf(state) {
    if (!state) return "—";
    if (state.state === "unknown" || state.state === "unavailable" || state.state === "") return "—";
    return `${state.state} min`;
  }

  function attr(state, key) {
    return (state && state.attributes && state.attributes[key]) || "";
  }

  const BASE_CSS = `
    :host { display: block; }
    ha-card {
      background: var(--ha-card-background, var(--card-background-color, #171d27));
      color: var(--primary-text-color, #e8edf4);
      overflow: hidden;
    }
    .wrap { padding: 16px 18px 18px; font-family: var(--ha-font-family-body, IBM Plex Sans, system-ui, sans-serif); }
    .kicker { font-size: 11px; letter-spacing: 0.16em; text-transform: uppercase; opacity: 0.55; font-weight: 500; }
    .row { display: flex; justify-content: space-between; align-items: flex-end; gap: 12px; margin-top: 8px; }
    .clock { font-size: 32px; font-variant-numeric: tabular-nums; font-weight: 500; letter-spacing: -0.03em; line-height: 1; }
    .mins { font-size: 20px; font-variant-numeric: tabular-nums; font-weight: 500; }
    .meta { margin-top: 8px; font-size: 13px; opacity: 0.75; }
    .empty { padding: 8px 0 2px; font-size: 14px; opacity: 0.7; }
    button.hit {
      display: block; width: 100%; text-align: left; background: none; border: 0; color: inherit;
      font: inherit; padding: 0; cursor: pointer;
    }
    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1px;
      background: var(--divider-color, rgba(127,127,127,0.25));
    }
    .cell { background: var(--ha-card-background, var(--card-background-color, #171d27)); padding: 14px 16px; }
    .cell.wide { grid-column: 1 / -1; }
    .head { display: flex; justify-content: space-between; align-items: center; padding: 14px 16px 10px; }
    .status { font-size: 12px; font-weight: 500; }
    .hint { margin-top: 4px; font-size: 12px; opacity: 0.6; }
    .label { font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; opacity: 0.5; }
    @media (max-width: 420px) {
      .grid { grid-template-columns: 1fr; }
      .cell.wide { grid-column: auto; }
    }
  `;

  function moreInfo(host, entityId) {
    if (!entityId) return;
    const ev = new CustomEvent("hass-more-info", {
      bubbles: true,
      composed: true,
      detail: { entityId },
    });
    host.dispatchEvent(ev);
  }

  class SeptaLiveCard extends HTMLElement {
    constructor() {
      super();
      this._config = {};
      this._hass = null;
      this._last = "";
      this.attachShadow({ mode: "open" });
    }

    setConfig(config) {
      if (!config || !config.entity) {
        throw new Error("Set entity to a SEPTA Live commute, train, or next-bus sensor");
      }
      this._config = config;
      this._last = "";
    }

    set hass(hass) {
      this._hass = hass;
      const state = stateOf(hass, this._config.entity);
      const sig = state ? `${state.state}|${JSON.stringify(state.attributes)}|${this._config.name || ""}` : "missing";
      if (sig === this._last) return;
      this._last = sig;
      this._render();
    }

    getCardSize() {
      return 2;
    }

    static getLayoutOptions() {
      return { grid_columns: 2, grid_rows: 2, grid_min_columns: 2, grid_min_rows: 2 };
    }

    static getStubConfig(hass) {
      return {
        entity:
          findEntity(hass, "_commute", "") ||
          findEntity(hass, "_next_bus", "") ||
          "sensor.septa_lansdale_commute",
      };
    }

    static getConfigForm() {
      return {
        schema: [
          { name: "name", selector: { text: {} } },
          {
            name: "entity",
            required: true,
            selector: { entity: { domain: "sensor" } },
          },
        ],
      };
    }

    _render() {
      const entity = this._config.entity;
      const state = stateOf(this._hass, entity);
      const name = this._config.name;
      if (!state) {
        this.shadowRoot.innerHTML = `<style>${BASE_CSS}</style><ha-card><div class="wrap"><div class="kicker">SEPTA Live</div><div class="empty">Missing ${esc(entity)}</div></div></ha-card>`;
        return;
      }
      const delay = Number(attr(state, "delay_min") || 0);
      const cancelled = Boolean(state.attributes && state.attributes.cancelled);
      const isBus = Boolean(attr(state, "route"));
      const clock = attr(state, "depart") || attr(state, "clock") || "";
      const dest = attr(state, "destination") || attr(state, "arrive") || "";
      const idLabel = isBus ? `Route ${attr(state, "route")}` : `#${attr(state, "train_id") || "—"}`;
      const status = attr(state, "delay") || attr(state, "status") || delayLabel(delay, cancelled, "");
      const live = attr(state, "live") ? " · live" : "";
      const kicker = name || (isBus ? "SEPTA Bus" : "SEPTA Live");
      const color = tone(delay, cancelled);
      this.shadowRoot.innerHTML = `
        <style>${BASE_CSS}</style>
        <ha-card>
          <button class="hit" type="button">
            <div class="wrap">
              <div class="kicker">${esc(kicker)}</div>
              <div class="row">
                <div class="clock">${esc(clock || minutesOf(state))}</div>
                <div class="mins" style="color:${color}">${esc(minutesOf(state))}</div>
              </div>
              <div class="meta">${esc(idLabel)}${dest ? " · " + esc(dest) : ""} · ${esc(status)}${esc(live)}</div>
            </div>
          </button>
        </ha-card>
      `;
      this.shadowRoot.querySelector("button").addEventListener("click", () => moreInfo(this, entity));
    }
  }

  class SeptaLiveBoard extends HTMLElement {
    constructor() {
      super();
      this._config = {};
      this._hass = null;
      this._last = "";
      this.attachShadow({ mode: "open" });
    }

    setConfig(config) {
      this._config = config || {};
      this._last = "";
    }

    set hass(hass) {
      this._hass = hass;
      const ids = ["commute", "south", "north", "bus", "leave", "status"].map((k) => this._config[k] || "");
      const sig = ids
        .map((id) => {
          const s = stateOf(hass, id);
          return s ? `${s.state}|${JSON.stringify(s.attributes)}` : "";
        })
        .join("#");
      if (sig === this._last) return;
      this._last = sig;
      this._render();
    }

    getCardSize() {
      return 5;
    }

    static getLayoutOptions() {
      return { grid_columns: 4, grid_rows: 4, grid_min_columns: 2, grid_min_rows: 3 };
    }

    static getStubConfig(hass) {
      return {
        name: "SEPTA Live",
        commute: findEntity(hass, "_commute", "sensor.septa_lansdale_commute"),
        south: findEntity(hass, "_next_southbound", "sensor.septa_lansdale_next_southbound"),
        north: findEntity(hass, "_next_northbound", "sensor.septa_lansdale_next_northbound"),
        bus: findEntity(hass, "_next_bus", "sensor.septa_lansdale_next_bus"),
        leave: findEntity(hass, "_leave_in", "sensor.septa_lansdale_leave_in"),
        status: findEntity(hass, "_status", "sensor.septa_lansdale_status"),
      };
    }

    static getConfigForm() {
      return {
        schema: [
          { name: "name", selector: { text: {} } },
          { name: "commute", selector: { entity: { domain: "sensor" } } },
          { name: "south", selector: { entity: { domain: "sensor" } } },
          { name: "north", selector: { entity: { domain: "sensor" } } },
          { name: "bus", selector: { entity: { domain: "sensor" } } },
          { name: "leave", selector: { entity: { domain: "sensor" } } },
          { name: "status", selector: { entity: { domain: "sensor" } } },
        ],
      };
    }

    _cell(label, entity, value, hint, color) {
      return `
        <button class="hit cell" type="button" data-entity="${esc(entity)}">
          <div class="label">${esc(label)}</div>
          <div class="clock" style="font-size:24px;margin-top:6px;color:${color || "inherit"}">${esc(value)}</div>
          ${hint ? `<div class="hint">${esc(hint)}</div>` : ""}
        </button>
      `;
    }

    _render() {
      const cfg = this._config;
      const commute = stateOf(this._hass, cfg.commute);
      const south = stateOf(this._hass, cfg.south);
      const north = stateOf(this._hass, cfg.north);
      const bus = stateOf(this._hass, cfg.bus);
      const leave = stateOf(this._hass, cfg.leave);
      const status = stateOf(this._hass, cfg.status);
      const commuteDelay = Number(attr(commute, "delay_min") || 0);
      const busDelay = Number(attr(bus, "delay_min") || 0);
      const statusText = status ? status.state : "—";
      const statusColor = /suspend|alert|delay/i.test(statusText) ? LATE : ONTIME;
      const leaveNum = leave && leave.state !== "unknown" ? Number(leave.state) : null;
      const leaveColor = leaveNum != null && leaveNum <= 2 ? LATE : ONTIME;
      const commuteClock = attr(commute, "depart") || minutesOf(commute);
      const southClock = attr(south, "clock") || minutesOf(south);
      const northClock = attr(north, "clock") || minutesOf(north);
      const busClock = attr(bus, "clock") || minutesOf(bus);
      const busRoute = attr(bus, "route") ? `Route ${attr(bus, "route")}` : "Next bus";

      this.shadowRoot.innerHTML = `
        <style>${BASE_CSS}</style>
        <ha-card>
          <div class="head">
            <div class="kicker">${esc(cfg.name || "SEPTA Live")}</div>
            <div class="status" style="color:${statusColor}">${esc(statusText)}</div>
          </div>
          <div class="grid">
            ${this._cell("Commute", cfg.commute, commuteClock, `${minutesOf(commute)} · ${delayLabel(commuteDelay, false, attr(commute, "delay"))}`, tone(commuteDelay, false))}
            ${this._cell("Leave in", cfg.leave, leave ? minutesOf(leave) : "—", attr(leave, "walk_minutes") ? `${attr(leave, "walk_minutes")} min walk` : "Walk window", leaveColor)}
            ${this._cell("Southbound", cfg.south, southClock, minutesOf(south), tone(Number(attr(south, "delay_min") || 0), false))}
            ${this._cell("Northbound", cfg.north, northClock, minutesOf(north), tone(Number(attr(north, "delay_min") || 0), false))}
            ${this._cell(busRoute, cfg.bus, busClock, `${minutesOf(bus)}${attr(bus, "destination") ? " · " + attr(bus, "destination") : ""}`, tone(busDelay, false)).replace('class="hit cell"', 'class="hit cell wide"')}
          </div>
        </ha-card>
      `;
      this.shadowRoot.querySelectorAll("[data-entity]").forEach((btn) => {
        btn.addEventListener("click", () => moreInfo(this, btn.getAttribute("data-entity")));
      });
    }
  }

  if (!customElements.get("septa-live-card")) {
    customElements.define("septa-live-card", SeptaLiveCard);
  }
  if (!customElements.get("septa-live-board")) {
    customElements.define("septa-live-board", SeptaLiveBoard);
  }

  window.customCards = window.customCards || [];
  const cards = window.customCards;
  if (!cards.some((c) => c.type === "septa-live-card")) {
    cards.push({
      type: "septa-live-card",
      name: "SEPTA Live",
      description: "Next SEPTA train or bus from a SEPTA Live sensor",
      preview: true,
    });
  }
  if (!cards.some((c) => c.type === "septa-live-board")) {
    cards.push({
      type: "septa-live-board",
      name: "SEPTA Live Board",
      description: "Pre-made commute dashboard: train, leave-now, both directions, and bus",
      preview: true,
    });
  }
})();
