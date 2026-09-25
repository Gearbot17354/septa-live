/* SEPTA Transit sidebar app. Registered by the integration as /septa-live. */
(function () {
  if (customElements.get("septa-live-panel")) return;

  const CSS = `
    :host { display: block; min-height: 100%; background: var(--primary-background-color, #111318); color: var(--primary-text-color, #e8edf4); }
    .page { max-width: 1080px; margin: 0 auto; padding: 20px 16px 48px; box-sizing: border-box; }
    header { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 12px; margin-bottom: 16px; }
    h1 { margin: 0; font-size: 22px; font-weight: 600; letter-spacing: -0.02em; }
    .sub { margin: 4px 0 0; font-size: 13px; opacity: 0.7; }
    .side { display: flex; align-items: center; gap: 8px; font-size: 13px; }
    .side input { width: 16px; height: 16px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; margin-bottom: 14px; }
    .card, .list, .setup { background: var(--card-background-color, #1c1f26); border-radius: 16px; box-shadow: 0 0 0 1px var(--divider-color, rgba(255,255,255,0.08)); }
    .card { padding: 14px 14px 12px; min-width: 0; }
    .kicker { display: flex; align-items: center; justify-content: space-between; gap: 8px; font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; opacity: 0.6; }
    .badge { display: inline-flex; align-items: center; height: 18px; padding: 0 6px; border-radius: 4px; background: #1f7a3a; color: #fff; font-size: 10px; font-weight: 700; letter-spacing: 0.04em; }
    .clock { margin-top: 8px; font-size: 32px; font-weight: 560; letter-spacing: -0.03em; font-variant-numeric: tabular-nums; line-height: 1; }
    .hint { margin-top: 6px; font-size: 12px; opacity: 0.7; }
    .status { font-size: 12px; font-weight: 600; }
    .status.late { color: #e6a15c; }
    .status.bad { color: #e15b64; }
    .status.ok { color: #7dcea0; }
    .tabs { display: flex; gap: 6px; margin: 4px 0 10px; }
    .tabs button, .setup button.save {
      height: 32px; padding: 0 12px; border-radius: 999px; border: 0; cursor: pointer;
      background: var(--secondary-background-color, #11161e); color: inherit; font: inherit; font-size: 13px;
    }
    .tabs button.on { box-shadow: 0 0 0 1px var(--primary-color, #03a9f4); }
    .row { display: grid; grid-template-columns: 4.2rem minmax(0,1fr) 1.6rem auto; gap: 8px; align-items: center; padding: 10px 14px; }
    .row + .row { box-shadow: 0 -1px 0 var(--divider-color, rgba(255,255,255,0.06)); }
    .time { font-variant-numeric: tabular-nums; font-weight: 600; }
    .to { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 500; }
    .meta { font-size: 12px; opacity: 0.6; }
    .trk { display: inline-flex; width: 22px; height: 22px; align-items: center; justify-content: center; border-radius: 3px; background: var(--primary-text-color, #e8edf4); color: var(--primary-background-color, #111); font-size: 11px; font-weight: 700; }
    .wait { text-align: right; font-variant-numeric: tabular-nums; font-size: 13px; }
    .empty { padding: 18px 14px; opacity: 0.7; }
    .setup { margin-top: 16px; padding: 14px; }
    .setup h2 { margin: 0 0 4px; font-size: 15px; }
    .setup p { margin: 0 0 12px; font-size: 12px; opacity: 0.65; }
    .fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }
    label.field { display: flex; flex-direction: column; gap: 4px; font-size: 12px; opacity: 0.85; }
    input, select { height: 36px; border-radius: 8px; border: 1px solid var(--divider-color, rgba(255,255,255,0.12)); background: var(--secondary-background-color, #11161e); color: inherit; padding: 0 10px; font: inherit; }
    .checks { display: flex; flex-wrap: wrap; gap: 12px; margin: 12px 0; font-size: 13px; }
    .note { margin-top: 8px; font-size: 12px; opacity: 0.7; }
    @media (max-width: 560px) {
      .clock { font-size: 26px; }
      .row { grid-template-columns: 3.4rem minmax(0,1fr) 1.4rem auto; gap: 6px; padding: 8px 10px; }
    }
  `;

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "\u0026amp;")
      .replace(/</g, "\u0026lt;")
      .replace(/>/g, "\u0026gt;")
      .replace(/"/g, "\u0026quot;");
  }

  function slug(name) {
    return String(name || "")
      .toLowerCase()
      .replace(/&/g, " and ")
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_|_$/g, "");
  }

  function tone(delay, cancelled, status) {
    if (cancelled || /suspend/i.test(status || "")) return "bad";
    if (Number(delay) >= 1 || /late|delay/i.test(status || "")) return "late";
    return "ok";
  }

  function statusText(t) {
    if (!t) return "";
    if (t.cancelled) return "Cancelled";
    if (t.scheduled || /schedul/i.test(t.status || "")) return "Scheduled";
    const d = Number(t.delay_min || 0);
    if (d > 0) return d === 1 ? "1 min late" : `${d} min late`;
    return t.status || "On time";
  }

  class SeptaLivePanel extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._hass = null;
      this._cfg = null;
      this._dir = "south";
      this._draft = null;
      this._msg = "";
      this._busy = false;
    }

    set hass(hass) {
      const prev = this._hass && this._sig(this._hass);
      this._hass = hass;
      if (!this._cfg) this._load();
      if (prev !== this._sig(hass)) this._paint();
    }

    set panel(_panel) {
      this._paint();
    }

    _sig(hass) {
      if (!hass) return "";
      return Object.keys(hass.states)
        .filter((id) => id.startsWith("sensor.septa_"))
        .map((id) => `${id}:${hass.states[id].state}:${hass.states[id].last_updated}`)
        .join("|");
    }

    async _call(type, extra) {
      return this._hass.callWS({ type, ...extra });
    }

    async _load() {
      try {
        this._cfg = await this._call("septa_live/panel");
        const first = (this._cfg.entries || [])[0];
        if (first && !this._draft) this._draft = { ...first };
        this._paint();
      } catch (err) {
        this._msg = err && err.message ? err.message : "Could not load SEPTA Transit";
        this._paint();
      }
    }

    _entry() {
      const entries = (this._cfg && this._cfg.entries) || [];
      const id = this._draft && this._draft.entry_id;
      return entries.find((e) => e.entry_id === id) || entries[0] || null;
    }

    _state(entry, suffix) {
      if (!this._hass || !entry) return null;
      const id = `sensor.septa_${slug(entry.station)}_${suffix}`;
      return this._hass.states[id] || null;
    }

    _trains(entry, dir) {
      const suffix = dir === "north" ? "outbound_board" : "inbound_board";
      const state = this._state(entry, suffix);
      const trains = state && state.attributes && state.attributes.trains;
      return Array.isArray(trains) ? trains.slice(0, 8) : [];
    }

    _bubble(title, state, fallback) {
      if (!state) {
        return `<article class="card"><div class="kicker">${esc(title)}</div><div class="clock">—</div><div class="hint">${esc(fallback || "Not set up")}</div></article>`;
      }
      const a = state.attributes || {};
      const clock = a.clock || state.state || "—";
      const cls = tone(a.delay_min, a.cancelled, a.delay || a.status || state.state);
      const late = a.delay || a.status || (cls === "ok" ? "On time" : state.state);
      const bits = [a.destination, a.service_type, a.track ? `Track ${a.track}` : ""].filter(Boolean);
      const badge = a.line || a.route || "";
      return `<article class="card">
        <div class="kicker"><span>${esc(title)}</span>${badge ? `<span class="badge">${esc(badge)}</span>` : ""}</div>
        <div class="clock">${esc(clock)}</div>
        <div class="status ${cls}">${esc(late || "")}</div>
        <div class="hint">${esc(bits.join(" · ") || fallback || "")}</div>
      </article>`;
    }

    _rows(trains) {
      if (!trains.length) return `<div class="empty">No trains listed right now.</div>`;
      return trains
        .map((t) => {
          const cls = tone(t.delay_min, t.cancelled, t.status);
          const track = String(t.track || "").trim();
          return `<div class="row">
            <div class="time">${esc(t.clock || "—")}</div>
            <div>
              <div class="to">${esc(t.destination || "")}</div>
              <div class="meta">${esc([t.train_id ? "#" + t.train_id : "", t.service_type || ""].filter(Boolean).join(" · "))}</div>
            </div>
            <div>${track ? `<span class="trk">${esc(track)}</span>` : ""}</div>
            <div class="wait status ${cls}">${esc(statusText(t))}</div>
          </div>`;
        })
        .join("");
    }

    _paint() {
      const entry = this._entry();
      const draft = this._draft || entry || {};
      const stations = (this._cfg && this._cfg.stations) || [];
      const inbound = this._state(entry, "next_inbound");
      const outbound = this._state(entry, "next_outbound");
      const bus = this._state(entry, "next_bus");
      const leave = this._state(entry, "leave_in");
      const trains = this._trains(entry, this._dir);
      const opts = stations
        .map((name) => `<option value="${esc(name)}"${name === draft.destination ? " selected" : ""}></option>`)
        .join("");
      const checks = [
        ["show_rail", "Regional Rail"],
        ["show_bus", "Buses"],
        ["show_metro", "Metro"],
        ["show_trolley", "Trolley"],
      ]
        .map(
          ([key, label]) =>
            `<label><input type="checkbox" data-flag="${key}" ${draft[key] !== false ? "checked" : ""}/> ${label}</label>`,
        )
        .join("");

      this.shadowRoot.innerHTML = `<style>${CSS}</style>
        <div class="page">
          <header>
            <div>
              <h1>SEPTA Transit</h1>
              <p class="sub">${entry ? esc(entry.station) + " → " + esc(entry.destination || "any") : "Add the integration to get started."}</p>
            </div>
            <label class="side">
              <input type="checkbox" data-sidebar ${draft.show_sidebar !== false ? "checked" : ""}/>
              Show in sidebar
            </label>
          </header>
          <section class="grid">
            ${this._bubble("Next inbound", inbound, "Waiting for live times")}
            ${this._bubble("Next outbound", outbound, "Waiting for live times")}
            ${this._bubble("Next bus", bus, "No nearby bus")}
            ${this._bubble("Leave in", leave, "Set a walk time")}
          </section>
          <section class="list">
            <div class="tabs" style="padding:12px 12px 0">
              <button type="button" data-dir="south" class="${this._dir === "south" ? "on" : ""}">Inbound</button>
              <button type="button" data-dir="north" class="${this._dir === "north" ? "on" : ""}">Outbound</button>
            </div>
            ${this._rows(trains)}
          </section>
          <section class="setup">
            <h2>Setup</h2>
            <p>This is the same commute the sensors use. Saving reloads the integration.</p>
            <div class="fields">
              <label class="field">Destination
                <input list="septa-stations" data-dest value="${esc(draft.destination || "")}" />
                <datalist id="septa-stations">${opts}</datalist>
              </label>
              <label class="field">Walk to station (minutes)
                <input data-walk type="number" min="0" max="60" value="${esc(draft.walk_minutes ?? 8)}" />
              </label>
            </div>
            <div class="checks">${checks}</div>
            <button class="save" type="button" data-save ${this._busy ? "disabled" : ""}>Save</button>
            <div class="note">${esc(this._msg || "Sidebar changes show up after Home Assistant refreshes the menu.")}</div>
          </section>
        </div>`;
      this._bind();
    }

    _bind() {
      const root = this.shadowRoot;
      root.querySelectorAll("[data-dir]").forEach((btn) => {
        btn.addEventListener("click", () => {
          this._dir = btn.getAttribute("data-dir");
          this._paint();
        });
      });
      const draft = () => {
        this._draft = this._draft || {};
        const dest = root.querySelector("[data-dest]");
        const walk = root.querySelector("[data-walk]");
        if (dest) this._draft.destination = dest.value;
        if (walk) this._draft.walk_minutes = Number(walk.value);
        root.querySelectorAll("[data-flag]").forEach((el) => {
          this._draft[el.getAttribute("data-flag")] = el.checked;
        });
        const side = root.querySelector("[data-sidebar]");
        if (side) this._draft.show_sidebar = side.checked;
      };
      root.querySelector("[data-save]")?.addEventListener("click", async () => {
        draft();
        const entry = this._entry();
        if (!entry || !this._hass) return;
        this._busy = true;
        this._msg = "Saving…";
        this._paint();
        try {
          await this._call("septa_live/options", {
            entry_id: entry.entry_id,
            destination: this._draft.destination,
            walk_minutes: Number(this._draft.walk_minutes),
            show_sidebar: this._draft.show_sidebar !== false,
            show_rail: this._draft.show_rail !== false,
            show_bus: this._draft.show_bus !== false,
            show_metro: this._draft.show_metro === true,
            show_trolley: this._draft.show_trolley === true,
          });
          this._msg = "Saved. The sidebar updates when Home Assistant reloads this page.";
          await this._load();
        } catch (err) {
          this._msg = err && err.message ? err.message : "Save failed";
        }
        this._busy = false;
        this._paint();
      });
    }
  }

  customElements.define("septa-live-panel", SeptaLivePanel);
})();
