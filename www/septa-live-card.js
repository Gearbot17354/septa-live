(() => {
  const ONTIME = "#7dba98";
  const LATE = "#d4a054";
  const CRIT = "#d0726a";

  function esc(value) {
    return String(value ?? "")
      .replace(/&/g, "\u0026amp;")
      .replace(/</g, "\u0026lt;")
      .replace(/>/g, "\u0026gt;")
      .replace(/"/g, "\u0026quot;");
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
    if (/^-?\d+(\.\d+)?$/.test(String(state.state))) return `${state.state} min`;
    return String(state.state);
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
    .bubbles { display: flex; flex-wrap: wrap; gap: 8px; padding: 8px 12px 14px; }
    .bubble {
      flex: 1 1 138px;
      min-height: 84px;
      border-radius: 18px;
      background: #12171f;
      box-shadow: inset 0 0 0 1px #2a3340;
      padding: 12px 14px;
      text-align: left;
      color: inherit;
      cursor: pointer;
      font: inherit;
      border: 0;
    }
    .bubble.is-hero { flex: 1 1 100%; min-height: 108px; border-radius: 22px; }
    .bubble.is-map { flex: 1 1 100%; min-height: 180px; padding: 0; overflow: hidden; }
    .bubble .value { font-size: 22px; font-variant-numeric: tabular-nums; font-weight: 500; letter-spacing: -0.03em; margin-top: 4px; }
    .bubble.is-hero .value { font-size: 32px; }
    .bubble-map { width: 100%; height: 180px; border: 0; display: block; background: #0b0e13; }
    .stack { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding: 8px 12px 14px; }
    .stack .bubble { min-width: 0; }
    @media (max-width: 420px) {
      .grid { grid-template-columns: 1fr; }
      .cell.wide { grid-column: auto; }
      .stack { grid-template-columns: 1fr; }
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

  const MODULE_ORDER = ["commute", "leave", "south", "north", "bus", "status", "metro", "trolley", "map"];
  const DEFAULT_ON = ["commute", "leave", "south", "north", "bus", "status"];
  const MODULE_LABELS = {
    commute: "Commute",
    leave: "Leave in",
    south: "Southbound",
    north: "Northbound",
    bus: "Bus",
    status: "Status",
    metro: "Metro",
    trolley: "Trolley",
    map: "Live map",
  };

  function normalizeBubbleConfig(config) {
    const next = { ...(config || {}) };
    const hasFlag = MODULE_ORDER.some((id) => typeof next[`show_${id}`] === "boolean");
    if (hasFlag) {
      next.modules = MODULE_ORDER.filter((id) => {
        const flag = next[`show_${id}`];
        if (typeof flag === "boolean") return flag;
        return Array.isArray(next.modules) ? next.modules.includes(id) : DEFAULT_ON.includes(id);
      });
    } else if (Array.isArray(next.modules) && next.modules.length) {
      next.modules = next.modules.filter((id) => MODULE_ORDER.includes(id));
    } else {
      next.modules = DEFAULT_ON.slice();
    }
    for (const id of MODULE_ORDER) {
      next[`show_${id}`] = next.modules.includes(id);
    }
    if (!next.layout) next.layout = "bubbles";
    return next;
  }

  function bubbleSchema() {
    return [
      { name: "name", selector: { text: {} } },
      {
        name: "layout",
        selector: {
          select: {
            mode: "dropdown",
            options: [
              { value: "bubbles", label: "Bubbles" },
              { value: "stack", label: "Stack" },
              { value: "hero", label: "Hero" },
            ],
          },
        },
      },
      ...MODULE_ORDER.map((id) => ({
        name: `show_${id}`,
        selector: { boolean: {} },
      })),
      { name: "commute", selector: { entity: { domain: "sensor" } } },
      { name: "leave", selector: { entity: { domain: "sensor" } } },
      { name: "south", selector: { entity: { domain: "sensor" } } },
      { name: "north", selector: { entity: { domain: "sensor" } } },
      { name: "bus", selector: { entity: { domain: "sensor" } } },
      { name: "status", selector: { entity: { domain: "sensor" } } },
      { name: "metro", selector: { entity: { domain: "sensor" } } },
      { name: "trolley", selector: { entity: { domain: "sensor" } } },
      { name: "map_url", selector: { text: {} } },
    ];
  }

  function bubbleLabel(schema) {
    const name = schema && schema.name;
    if (name === "name") return "Name";
    if (name === "layout") return "Layout";
    if (name === "map_url") return "Map URL";
    if (name && name.startsWith("show_")) return MODULE_LABELS[name.slice(5)] || name;
    return MODULE_LABELS[name] || name;
  }

  class SeptaLiveBubble extends HTMLElement {
    constructor() {
      super();
      this._config = {};
      this._hass = null;
      this._last = "";
      this.attachShadow({ mode: "open" });
    }

    setConfig(config) {
      this._config = normalizeBubbleConfig(config);
      this._last = "";
      if (this._hass) this._render();
    }

    _modules() {
      const cfg = this._config || {};
      if (Array.isArray(cfg.modules) && cfg.modules.length) {
        return cfg.modules.filter((id) => MODULE_ORDER.includes(id));
      }
      return MODULE_ORDER.filter((id) => cfg[`show_${id}`] === true || (cfg[`show_${id}`] !== false && DEFAULT_ON.includes(id)));
    }

    set hass(hass) {
      this._hass = hass;
      const keys = this._modules().map((k) => this._config[k] || "");
      const sig = keys
        .concat([this._config.layout || "", this._config.map_url || "", this._modules().join(",")])
        .map((id) => {
          if (!id || id.startsWith("http") || MODULE_ORDER.includes(id)) return id;
          const s = stateOf(hass, id);
          return s ? `${s.state}|${JSON.stringify(s.attributes)}` : "";
        })
        .join("#");
      if (sig === this._last) return;
      this._last = sig;
      this._render();
    }

    getCardSize() {
      const n = this._modules().length;
      return Math.max(2, Math.ceil(n / 2) + 1);
    }

    static getLayoutOptions() {
      return { grid_columns: 4, grid_rows: 3, grid_min_columns: 2, grid_min_rows: 2 };
    }

    static getStubConfig(hass) {
      const stub = {
        name: "SEPTA Live",
        layout: "bubbles",
        modules: DEFAULT_ON.slice(),
        commute: findEntity(hass, "_commute", "sensor.septa_lansdale_commute"),
        south: findEntity(hass, "_next_southbound", "sensor.septa_lansdale_next_southbound"),
        north: findEntity(hass, "_next_northbound", "sensor.septa_lansdale_next_northbound"),
        bus: findEntity(hass, "_next_bus", "sensor.septa_lansdale_next_bus"),
        leave: findEntity(hass, "_leave_in", "sensor.septa_lansdale_leave_in"),
        status: findEntity(hass, "_status", "sensor.septa_lansdale_status"),
        metro: findEntity(hass, "_metro", "sensor.septa_lansdale_metro"),
        trolley: findEntity(hass, "_trolley", "sensor.septa_lansdale_trolley"),
      };
      for (const id of MODULE_ORDER) stub[`show_${id}`] = DEFAULT_ON.includes(id);
      return stub;
    }

    static getConfigElement() {
      return document.createElement("septa-live-bubble-editor");
    }

    static getConfigForm() {
      return {
        schema: bubbleSchema(),
        computeLabel: bubbleLabel,
      };
    }

    _face(id) {
      const cfg = this._config;
      const entity = cfg[id];
      const state = stateOf(this._hass, entity);
      const delay = Number(attr(state, "delay_min") || 0);
      const color = tone(delay, Boolean(state && state.attributes && state.attributes.cancelled));
      if (id === "commute") {
        return {
          label: "Commute",
          value: attr(state, "depart") || minutesOf(state),
          hint: state ? `${minutesOf(state)}${attr(state, "train_id") ? " · #" + attr(state, "train_id") : ""}` : "Missing",
          color,
          entity,
        };
      }
      if (id === "leave") {
        const n = state && state.state !== "unknown" ? Number(state.state) : null;
        return {
          label: "Leave in",
          value: n == null || Number.isNaN(n) ? "—" : n <= 0 ? "Now" : `${n} min`,
          hint: attr(state, "walk_minutes") ? `${attr(state, "walk_minutes")} min walk` : "Walk window",
          color: n != null && n <= 2 ? LATE : ONTIME,
          entity,
        };
      }
      if (id === "south" || id === "north") {
        return {
          label: id === "south" ? "Southbound" : "Northbound",
          value: attr(state, "clock") || minutesOf(state),
          hint: minutesOf(state),
          color,
          entity,
        };
      }
      if (id === "bus") {
        return {
          label: attr(state, "route") ? `Bus ${attr(state, "route")}` : "Next bus",
          value: attr(state, "clock") || minutesOf(state),
          hint: `${minutesOf(state)}${attr(state, "destination") ? " · " + attr(state, "destination") : ""}`,
          color,
          entity,
        };
      }
      if (id === "status") {
        const text = state ? state.state : "—";
        return {
          label: "Status",
          value: text,
          hint: "Line",
          color: /suspend|alert|delay/i.test(text) ? LATE : ONTIME,
          entity,
        };
      }
      if (id === "metro") {
        return {
          label: "Metro",
          value: state && state.state !== "unknown" ? state.state : "—",
          hint: attr(state, "summary") || "L · B · M",
          color: ONTIME,
          entity,
        };
      }
      if (id === "trolley") {
        return {
          label: "Trolley",
          value: state && state.state !== "unknown" ? state.state : "—",
          hint: attr(state, "summary") || "T · G · D",
          color: ONTIME,
          entity,
        };
      }
      return { label: id, value: "—", hint: "", color: ONTIME, entity };
    }

    _bubble(face, extraClass) {
      return `
        <button class="bubble ${extraClass || ""}" type="button" data-entity="${esc(face.entity || "")}">
          <div class="label">${esc(face.label)}</div>
          <div class="value" style="color:${face.color}">${esc(face.value)}</div>
          <div class="hint">${esc(face.hint)}</div>
        </button>
      `;
    }

    _render() {
      const modules = this._modules();
      const layout = this._config.layout === "stack" || this._config.layout === "hero" ? this._config.layout : "bubbles";
      const name = this._config.name || "SEPTA Live";
      let body = "";
      if (!modules.length) {
        body = `<div class="wrap"><div class="empty">Pick at least one module.</div></div>`;
      } else if (layout === "hero") {
        const first = modules[0];
        const rest = modules.slice(1);
        body = `<div class="bubbles">${this._moduleHtml(first, "is-hero")}${rest.map((id) => this._moduleHtml(id, "")).join("")}</div>`;
      } else if (layout === "stack") {
        body = `<div class="stack">${modules.map((id) => this._moduleHtml(id, "")).join("")}</div>`;
      } else {
        body = `<div class="bubbles">${modules.map((id) => this._moduleHtml(id, "")).join("")}</div>`;
      }
      this.shadowRoot.innerHTML = `
        <style>${BASE_CSS}</style>
        <ha-card>
          <div class="head">
            <div class="kicker">${esc(name)}</div>
            <div class="status">${esc(modules.length)} items</div>
          </div>
          ${body}
        </ha-card>
      `;
      this.shadowRoot.querySelectorAll("[data-entity]").forEach((btn) => {
        btn.addEventListener("click", () => moreInfo(this, btn.getAttribute("data-entity")));
      });
    }

    _moduleHtml(id, extraClass) {
      if (id === "map") {
        const url = this._config.map_url || "";
        if (!url) {
          return this._bubble({ label: "Live map", value: "Set map_url", hint: "Paste the embed map URL", color: LATE, entity: "" }, extraClass);
        }
        return `<div class="bubble is-map ${extraClass || ""}"><iframe class="bubble-map" src="${esc(url)}" title="SEPTA live map" loading="lazy" referrerpolicy="no-referrer"></iframe></div>`;
      }
      return this._bubble(this._face(id), extraClass);
    }
  }

  class SeptaLiveBubbleEditor extends HTMLElement {
    constructor() {
      super();
      this._config = {};
      this._hass = null;
      this._form = null;
    }

    set hass(hass) {
      this._hass = hass;
      if (this._form) this._form.hass = hass;
    }

    setConfig(config) {
      this._config = normalizeBubbleConfig(config);
      if (!this._form) {
        this._form = document.createElement("ha-form");
        this._form.computeLabel = bubbleLabel;
        this._form.addEventListener("value-changed", (ev) => {
          const next = normalizeBubbleConfig(ev.detail.value);
          if (JSON.stringify(next) === JSON.stringify(this._config)) return;
          this._config = next;
          this._form.data = next;
          this.dispatchEvent(
            new CustomEvent("config-changed", {
              bubbles: true,
              composed: true,
              detail: { config: next },
            }),
          );
        });
        this.appendChild(this._form);
      }
      this._form.schema = bubbleSchema();
      this._form.data = this._config;
      if (this._hass) this._form.hass = this._hass;
    }
  }

  if (!customElements.get("septa-live-bubble-editor")) {
    customElements.define("septa-live-bubble-editor", SeptaLiveBubbleEditor);
  }
  if (!customElements.get("septa-live-card")) {
    customElements.define("septa-live-card", SeptaLiveCard);
  }
  if (!customElements.get("septa-live-board")) {
    customElements.define("septa-live-board", SeptaLiveBoard);
  }
  if (!customElements.get("septa-live-bubble")) {
    customElements.define("septa-live-bubble", SeptaLiveBubble);
  }

  function entitiesStub(hass) {
    return {
      commute: findEntity(hass, "_commute", "sensor.septa_lansdale_commute"),
      south: findEntity(hass, "_next_southbound", "sensor.septa_lansdale_next_southbound"),
      north: findEntity(hass, "_next_northbound", "sensor.septa_lansdale_next_northbound"),
      bus: findEntity(hass, "_next_bus", "sensor.septa_lansdale_next_bus"),
      leave: findEntity(hass, "_leave_in", "sensor.septa_lansdale_leave_in"),
      status: findEntity(hass, "_status", "sensor.septa_lansdale_status"),
      metro: findEntity(hass, "_metro", "sensor.septa_lansdale_metro"),
      trolley: findEntity(hass, "_trolley", "sensor.septa_lansdale_trolley"),
    };
  }

  function registerCard(tag, Ctor, name, description, suggestion) {
    if (!customElements.get(tag)) customElements.define(tag, Ctor);
    if (!cards.some((c) => c.type === tag)) {
      cards.push({
        type: tag,
        name,
        description,
        preview: true,
        documentationURL: "https://github.com/Gearbot17354/septa-live",
        getEntitySuggestion: suggestion || suggestSepta,
      });
    }
  }

  function heroPreset(suffix, fallback, displayName) {
    return class extends SeptaLiveCard {
      setConfig(config) {
        super.setConfig({ name: displayName, ...config });
      }
      static getStubConfig(hass) {
        return { entity: findEntity(hass, suffix, fallback), name: displayName };
      }
    };
  }

  function bubblePreset(displayName, modules, layout) {
    const mods = modules.slice();
    return class extends SeptaLiveBubble {
      setConfig(config) {
        const next = { name: displayName, layout: layout || "bubbles", ...config };
        if (!next.modules || !next.modules.length) next.modules = mods.slice();
        for (const id of MODULE_ORDER) {
          if (typeof next[`show_${id}`] !== "boolean") next[`show_${id}`] = next.modules.includes(id);
        }
        super.setConfig(next);
      }
      static getStubConfig(hass) {
        return { name: displayName, layout: layout || "bubbles", modules: mods.slice(), ...entitiesStub(hass) };
      }
    };
  }

  window.customCards = window.customCards || [];
  const cards = window.customCards;
  function suggestSepta(hass, entityId) {
    if (!entityId || !String(entityId).startsWith("sensor.septa_")) return null;
    const id = String(entityId);
    const e = entitiesStub(hass);
    if (id.endsWith("_next_bus")) {
      return [
        { label: "Next bus", config: { type: "custom:septa-live-bus", entity: id, name: "Next bus" } },
        { label: "Board", config: { type: "custom:septa-live-board", name: "SEPTA Live", ...e } },
      ];
    }
    if (id.endsWith("_metro")) {
      return {
        label: "Metro",
        config: { type: "custom:septa-live-metro", name: "SEPTA Metro", layout: "bubbles", modules: ["metro", "trolley", "status"], ...e },
      };
    }
    if (id.endsWith("_trolley")) {
      return {
        label: "Trolley",
        config: { type: "custom:septa-live-trolley", name: "SEPTA Trolley", layout: "bubbles", modules: ["trolley"], ...e },
      };
    }
    if (id.endsWith("_leave_in")) {
      return { label: "Leave now", config: { type: "custom:septa-live-leave", entity: id, name: "Leave in" } };
    }
    if (id.endsWith("_next_southbound")) {
      return { label: "Southbound", config: { type: "custom:septa-live-south", entity: id, name: "Southbound" } };
    }
    if (id.endsWith("_next_northbound")) {
      return { label: "Northbound", config: { type: "custom:septa-live-north", entity: id, name: "Northbound" } };
    }
    if (id.endsWith("_status")) {
      return { label: "Status", config: { type: "custom:septa-live-status", entity: id, name: "Line status" } };
    }
    return [
      { label: "Commute", config: { type: "custom:septa-live-card", entity: id } },
      { label: "Board", config: { type: "custom:septa-live-board", name: "SEPTA Live", ...e } },
      { label: "Glance", config: { type: "custom:septa-live-glance", name: "SEPTA", layout: "bubbles", modules: ["commute", "leave", "bus", "status"], ...e } },
    ];
  }

  registerCard("septa-live-card", SeptaLiveCard, "SEPTA Live Commute", "Hero card for your next train");
  registerCard("septa-live-bus", heroPreset("_next_bus", "sensor.septa_lansdale_next_bus", "Next bus"), "SEPTA Live Next Bus", "Next bus at the stop nearest your station");
  registerCard("septa-live-leave", heroPreset("_leave_in", "sensor.septa_lansdale_leave_in", "Leave in"), "SEPTA Live Leave", "Walk-window countdown so you know when to head out");
  registerCard("septa-live-south", heroPreset("_next_southbound", "sensor.septa_lansdale_next_southbound", "Southbound"), "SEPTA Live Southbound", "Next inbound / southbound train");
  registerCard("septa-live-north", heroPreset("_next_northbound", "sensor.septa_lansdale_next_northbound", "Northbound"), "SEPTA Live Northbound", "Next outbound / northbound train");
  registerCard("septa-live-status", heroPreset("_status", "sensor.septa_lansdale_status", "Line status"), "SEPTA Live Status", "On time, delay, alert, or suspended");
  registerCard("septa-live-board", SeptaLiveBoard, "SEPTA Live Board", "Commute board: train, leave-now, both directions, and bus");
  registerCard(
    "septa-live-glance",
    bubblePreset("SEPTA", ["commute", "leave", "bus", "status"], "bubbles"),
    "SEPTA Live Glance",
    "Four sensors in one compact row",
  );
  registerCard(
    "septa-live-metro",
    bubblePreset("SEPTA Metro", ["metro", "trolley", "status"], "bubbles"),
    "SEPTA Live Metro",
    "L, B, and M in service, plus trolleys",
  );
  registerCard(
    "septa-live-trolley",
    bubblePreset("SEPTA Trolley", ["trolley"], "bubbles"),
    "SEPTA Live Trolley",
    "T, G, and D live",
  );
  registerCard("septa-live-bubble", SeptaLiveBubble, "SEPTA Live Bubble", "Pick commute, bus, Metro, trolley, and map bubbles");
})();
