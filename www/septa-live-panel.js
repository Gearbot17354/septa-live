/* SEPTA Transit sidebar app — same board layout as the SEPTA Transit page. */
(function () {
  if (customElements.get("septa-live-panel")) return;

  const LINE = {
    AIR: "#00539f", CHE: "#9b5a2c", CHW: "#3d9cc7", CYN: "#6b3fa0", FOX: "#e87722",
    LAN: "#2e7d32", MED: "#e35205", NOR: "#6e7a86", PAO: "#6ea244", TRE: "#9b1b30",
    WAR: "#e6a317", WTR: "#ef6c00", WIL: "#c62828",
  };

  const CSS = `
    :host { display: block; min-height: 100%; background: #0b0e13; color: #e8edf4; font-family: "IBM Plex Sans", ui-sans-serif, system-ui, sans-serif; }
    .page { max-width: 1080px; margin: 0 auto; padding: 28px 16px 64px; box-sizing: border-box; }
    .top { display: flex; flex-wrap: wrap; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 22px; }
    .brand { display: flex; align-items: center; gap: 12px; }
    .mark { width: 40px; height: 40px; flex: none; }
    .eyebrow { display: flex; align-items: center; gap: 8px; font-size: 11px; font-weight: 600; letter-spacing: 0.18em; text-transform: uppercase; color: #5c6778; }
    .live { width: 7px; height: 7px; border-radius: 99px; background: #7dba98; box-shadow: 0 0 0 4px rgba(125,186,152,0.18); }
    h1 { margin: 4px 0 0; font-size: 34px; font-weight: 500; letter-spacing: -0.03em; }
    .side { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #8b96a8; }
    .meta { display: flex; flex-wrap: wrap; align-items: center; gap: 14px; margin-bottom: 18px; font-size: 12px; color: #8b96a8; }
    .meta b { color: #e8edf4; font-weight: 560; font-variant-numeric: tabular-nums; }
    .meta select, .field input, .field select {
      height: 32px; border-radius: 8px; border: 0; background: #1e2632; color: #e8edf4;
      box-shadow: 0 0 0 1px #2a3340; padding: 0 8px; font: inherit;
    }
    .label { margin: 0 0 8px; font-size: 11px; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; color: #5c6778; }
    .modes { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 18px; }
    .modes button {
      height: 34px; padding: 0 12px; border-radius: 999px; border: 0; cursor: pointer;
      background: #171d27; color: #8b96a8; box-shadow: 0 0 0 1px #2a3340; font: inherit; font-size: 13px;
    }
    .modes button.on { color: #e8edf4; background: #1e2632; box-shadow: 0 0 0 1px #7aa2ce; }
    .commute { display: grid; gap: 10px; grid-template-columns: 8.5rem 1fr auto 1fr auto; align-items: end; margin-bottom: 18px; padding: 12px; border-radius: 12px; background: #171d27; box-shadow: 0 0 0 1px #2a3340; }
    .who { display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 560; padding-bottom: 6px; }
    .field { display: flex; flex-direction: column; gap: 6px; min-width: 0; font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: #5c6778; }
    .field input, .field select { width: 100%; letter-spacing: 0; text-transform: none; font-size: 14px; height: 40px; }
    .swap { width: 36px; height: 36px; border-radius: 8px; border: 0; background: transparent; color: #8b96a8; font-size: 16px; }
    .board { border-radius: 16px; background: #171d27; box-shadow: 0 0 0 1px #2a3340; overflow: hidden; }
    .board-head { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px 4px; }
    .bubbles { display: flex; flex-wrap: wrap; gap: 8px; padding: 8px 12px 12px; }
    .bubble { flex: 1 1 240px; min-width: 220px; border-radius: 16px; background: #0b0e13; box-shadow: 0 0 0 1px #2a3340; padding: 12px; }
    .kicker { display: flex; align-items: center; justify-content: space-between; gap: 8px; font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; color: #5c6778; }
    .kicker span { display: flex; align-items: center; gap: 8px; }
    .clockrow { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; margin-top: 6px; }
    .clock { font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 30px; font-weight: 500; letter-spacing: -0.03em; font-variant-numeric: tabular-nums; }
    .clock.sm { font-size: 20px; }
    .hint { margin-top: 4px; font-size: 12px; color: #8b96a8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .ok { color: #7dba98; } .late { color: #d4a054; } .bad { color: #d0726a; } .muted { color: #8b96a8; }
    .follow { margin-top: 8px; padding-top: 8px; box-shadow: 0 -1px 0 #2a3340; }
    .line { display: inline-flex; align-items: center; justify-content: center; min-width: 34px; height: 18px; padding: 0 5px; border-radius: 3px; color: #fff; font-size: 10px; font-weight: 700; letter-spacing: 0.04em; }
    .deps { margin-top: 18px; border-radius: 16px; background: #171d27; box-shadow: 0 0 0 1px #2a3340; overflow: hidden; }
    .dep-head { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 12px; padding: 14px 16px; box-shadow: 0 1px 0 #2a3340; }
    .cols, .row { display: grid; grid-template-columns: 4.5rem minmax(0,1fr) 4.2rem 5.6rem; gap: 12px; align-items: center; padding: 8px 16px; }
    .cols { font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase; color: #5c6778; font-weight: 600; }
    .row { padding-top: 12px; padding-bottom: 12px; box-shadow: 0 -1px 0 #2a3340; }
    .time { font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 18px; font-weight: 500; line-height: 1; }
    .ampm { margin-top: 3px; font-size: 10px; letter-spacing: 0.12em; color: #5c6778; }
    .to { display: flex; align-items: center; gap: 8px; font-weight: 560; min-width: 0; }
    .to em { font-style: normal; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .sub { font-size: 12px; color: #8b96a8; }
    .trk { display: inline-flex; width: 28px; height: 28px; align-items: center; justify-content: center; border-radius: 2px; background: #e8edf4; color: #12171f; font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 12px; font-weight: 700; justify-self: center; }
    .expect { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; text-align: right; font-variant-numeric: tabular-nums; }
    .pill { display: inline-flex; align-items: center; height: 22px; padding: 0 8px; border-radius: 999px; background: #1e2632; font-size: 11px; font-weight: 600; }
    .pill.ok { color: #7dba98; } .pill.late { color: #d4a054; } .pill.bad { color: #d0726a; }
    .empty { padding: 22px 16px; color: #8b96a8; font-size: 14px; }
    .save {
      height: 36px; padding: 0 14px; border-radius: 8px; border: 0; cursor: pointer;
      background: #e8edf4; color: #0b0e13; font: inherit; font-size: 13px; font-weight: 600;
    }
    .note { margin-top: 8px; font-size: 12px; color: #8b96a8; }
    @media (max-width: 800px) {
      h1 { font-size: 28px; }
      .commute { grid-template-columns: 1fr; }
      .cols, .row { grid-template-columns: 3.4rem minmax(0,1fr) 1.6rem 4.6rem; gap: 8px; padding-left: 12px; padding-right: 12px; }
      .time { font-size: 14px; }
    }
  `;

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "\u0026amp;")
      .replace(/</g, "\u0026lt;")
      .replace(/>/g, "\u0026gt;")
      .replace(/"/g, "\u0026quot;");
  }

  function blank(state) {
    if (!state) return true;
    const v = String(state.state || "").toLowerCase();
    return v === "unknown" || v === "unavailable" || v === "none" || v === "";
  }

  function toneOf(t) {
    if (!t) return "muted";
    if (t.cancelled) return "bad";
    if (t.scheduled || /schedul/i.test(t.status || "")) return "muted";
    if (Number(t.delay_min || 0) > 0 || /late|delay/i.test(t.status || t.delay || "")) return "late";
    return "ok";
  }

  function lateLabel(t) {
    if (!t) return "";
    if (t.cancelled) return "Cancelled";
    if (t.scheduled || /schedul/i.test(t.status || "")) return "Scheduled";
    const d = Number(t.delay_min || 0);
    if (d > 0) return d === 1 ? "1 min late" : d + " min late";
    if (t.status && !/on time/i.test(t.status)) return t.status;
    return "On time";
  }

  function hintOf(t) {
    if (!t) return "";
    const mins = t.minutes != null && t.minutes !== "" ? (Number(t.minutes) <= 0 ? "Due" : (Number(t.minutes) >= 60 ? Math.floor(t.minutes / 60) + "h " + (Number(t.minutes) % 60 ? (Number(t.minutes) % 60) + "m" : "") : Number(t.minutes) + " min")) : "";
    return [mins, t.service_type, t.destination, t.track ? "Track " + t.track : ""].filter(Boolean).join(" · ");
  }

  function lineBadge(code) {
    const key = String(code || "").toUpperCase();
    if (!key) return "";
    const bg = LINE[key] || "#7aa2ce";
    return '<span class="line" style="background:' + bg + '">' + esc(key) + "</span>";
  }

  function splitClock(clock) {
    const text = String(clock || "").trim();
    const m = text.match(/^(\d{1,2}:\d{2})\s*([AP]M)?$/i);
    if (!m) return { time: text || "—", period: "" };
    return { time: m[1], period: (m[2] || "").toUpperCase() };
  }

  const RAIL = '<svg class="mark" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="11" fill="#231f20" stroke="#fff" stroke-width="1.15"/><path fill="#fff" d="M7 16.5h10v1.2H7zM8.2 6.2h7.6c.7 0 1.2.6 1.2 1.3v6.2c0 .7-.5 1.3-1.2 1.3H8.2c-.7 0-1.2-.6-1.2-1.3V7.5c0-.7.5-1.3 1.2-1.3zm.5 1.6v2.2h6.6V7.8H8.7zm0 3.4v1.5h2.2v-1.5H8.7zm4.4 0v1.5h2.2v-1.5h-2.2z"/></svg>';

  class SeptaLivePanel extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._hass = null;
      this._cfg = null;
      this._dir = "south";
      this._tab = "all";
      this._draft = null;
      this._msg = "";
      this._busy = false;
    }

    set hass(hass) {
      const prev = this._hass && this._sig(this._hass);
      this._hass = hass;
      if (!this._cfg) this._load();
      else if (prev !== this._sig(hass)) this._paint();
    }

    set panel(_) {}

    _sig(hass) {
      if (!hass) return "";
      return Object.keys(hass.states)
        .filter((id) => id.indexOf("septa") !== -1)
        .map((id) => id + ":" + hass.states[id].state + ":" + hass.states[id].last_updated)
        .join("|");
    }

    async _call(type, extra) {
      return this._hass.callWS(Object.assign({ type: type }, extra || {}));
    }

    async _load() {
      try {
        this._cfg = await this._call("septa_live/panel");
        const first = (this._cfg.entries || [])[0];
        if (first) this._draft = Object.assign({}, first);
        this._paint();
      } catch (err) {
        this._msg = (err && err.message) || "Could not load SEPTA Transit";
        this._paint();
      }
    }

    _entry() {
      const entries = (this._cfg && this._cfg.entries) || [];
      const id = this._draft && this._draft.entry_id;
      return entries.find((e) => e.entry_id === id) || entries[0] || null;
    }

    _state(entry, key) {
      if (!this._hass || !entry) return null;
      const id = entry.entities && entry.entities[key];
      if (id && this._hass.states[id]) return this._hass.states[id];
      const slug = String(entry.station || "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
      const guesses = {
        south: ["next_inbound", "next_southbound", "south"],
        north: ["next_outbound", "next_northbound", "north"],
        south_board: ["inbound_board", "southbound_board"],
        north_board: ["outbound_board", "northbound_board"],
        leave_in: ["leave_in"],
        next_bus: ["next_bus"],
        status: ["status"],
      };
      const names = guesses[key] || [key];
      for (let i = 0; i < names.length; i++) {
        const hit = this._hass.states["sensor.septa_" + slug + "_" + names[i]];
        if (hit) return hit;
      }
      const list = Object.keys(this._hass.states);
      for (let i = 0; i < list.length; i++) {
        const eid = list[i];
        if (eid.indexOf(slug) === -1) continue;
        if (names.some((n) => eid.endsWith("_" + n))) return this._hass.states[eid];
      }
      return null;
    }

    _trains(entry, dir) {
      const state = this._state(entry, dir === "north" ? "north_board" : "south_board");
      const trains = state && state.attributes && state.attributes.trains;
      if (Array.isArray(trains) && trains.length) return trains.slice(0, 8);
      const one = this._state(entry, dir === "north" ? "north" : "south");
      if (!one || blank(one)) return [];
      const a = one.attributes || {};
      return [{
        clock: a.clock || one.state,
        destination: a.destination,
        train_id: a.train_id,
        line: a.line,
        track: a.track || a.platform,
        delay_min: a.delay_min,
        status: a.status || a.delay,
        service_type: a.service_type,
        cancelled: a.cancelled,
        minutes: one.state,
      }];
    }

    _bubble(title, trains) {
      const first = trains[0];
      const second = trains[1];
      const cls = toneOf(first);
      const clock = first ? (first.clock || "—") : "—";
      const status = first ? lateLabel(first) : "";
      const follow = second
        ? '<div class="follow"><div class="clockrow"><div class="clock sm ' + toneOf(second) + '">' + esc(second.clock || "—") + '</div><div class="status ' + toneOf(second) + '">' + esc(lateLabel(second)) + '</div></div><div class="hint">' + esc(hintOf(second)) + "</div></div>"
        : "";
      return '<article class="bubble"><div class="kicker"><span>' + RAIL.replace('class="mark"', 'class="mark" style="width:22px;height:22px"') + esc(title) + "</span>" + (first && first.line ? lineBadge(first.line) : "") + '</div><div class="clockrow"><div class="clock ' + cls + '">' + esc(clock) + '</div>' + (status ? '<div class="' + cls + '">' + esc(status) + "</div>" : "") + '</div><div class="hint">' + esc(first ? hintOf(first) : "None listed") + "</div>" + follow + "</article>";
    }

    _rows(trains) {
      if (!trains.length) return '<div class="empty">No trains listed right now.</div>';
      return trains.slice(0, 5).map((t) => {
        const parts = splitClock(t.clock);
        const cls = toneOf(t);
        const mins = t.minutes != null && t.minutes !== "" && !isNaN(Number(t.minutes))
          ? (Number(t.minutes) <= 0 ? "Due" : (Number(t.minutes) >= 60 ? Math.floor(Number(t.minutes) / 60) + "h" + (Number(t.minutes) % 60 ? " " + (Number(t.minutes) % 60) + "m" : "") : Number(t.minutes) + " min"))
          : "";
        return '<div class="row"><div><div class="time">' + esc(parts.time) + '</div>' + (parts.period ? '<div class="ampm">' + esc(parts.period) + "</div>" : "") + '</div><div><div class="to">' + lineBadge(t.line) + "<em>" + esc(t.destination || "") + '</em></div><div class="sub">' + esc([t.train_id ? "#" + t.train_id : "", t.service_type || ""].filter(Boolean).join(" · ")) + '</div></div><div>' + (t.track ? '<span class="trk">' + esc(t.track) + "</span>" : "") + '</div><div class="expect"><span>' + esc(mins || "—") + '</span><span class="pill ' + cls + '">' + esc(lateLabel(t)) + "</span></div></div>";
      }).join("");
    }

    _paint() {
      const entry = this._entry();
      const draft = this._draft || entry || {};
      const stations = (this._cfg && this._cfg.stations) || [];
      const showRail = draft.show_rail !== false;
      const showBus = draft.show_bus === true;
      const south = this._trains(entry, "south");
      const north = this._trains(entry, "north");
      const bus = this._state(entry, "next_bus");
      const leave = this._state(entry, "leave_in");
      const status = this._state(entry, "status");
      const trains = this._dir === "north" ? north : south;
      const leaveText = leave && !blank(leave) ? leave.state + " min" : "—";
      const statusText = status && !blank(status) ? status.state : "Live";
      const opts = stations.map((name) => '<option value="' + esc(name) + '"' + (name === draft.destination ? " selected" : "") + ">" + esc(name) + "</option>").join("");
      const busCard = showBus
        ? '<article class="bubble"><div class="kicker"><span>Next bus</span>' + (bus && bus.attributes && bus.attributes.route ? lineBadge(String(bus.attributes.route)) : "") + '</div><div class="clockrow"><div class="clock">' + esc(bus && !blank(bus) ? ((bus.attributes && bus.attributes.clock) || bus.state) : "—") + "</div></div><div class=\"hint\">" + esc(bus && bus.attributes && bus.attributes.destination ? bus.attributes.destination : "No nearby bus") + "</div></article>"
        : "";
      const bubbles = (this._tab === "all" || this._tab === "rail") && showRail
        ? this._bubble("Next inbound", south) + this._bubble("Next outbound", north)
        : "";
      const busBubble = (this._tab === "all" || this._tab === "bus") ? busCard : "";

      this.shadowRoot.innerHTML = "<style>" + CSS + "</style><div class=\"page\">" +
        '<header class="top"><div class="brand">' + RAIL + '<div><div class="eyebrow"><span class="live"></span> Regional Rail</div><h1>SEPTA Transit</h1></div></div>' +
        '<label class="side"><input type="checkbox" data-sidebar ' + (draft.show_sidebar !== false ? "checked" : "") + "/> Show in sidebar</label></header>" +
        '<div class="meta"><span>' + esc(statusText) + "</span><span>" + esc(entry ? entry.station : "") + '</span><label>Walk <select data-walk>' +
        [0, 2, 4, 5, 6, 8, 10, 12, 15, 20].map((n) => '<option value="' + n + '"' + (Number(draft.walk_minutes) === n ? " selected" : "") + ">" + n + " min</option>").join("") +
        "</select></label>" + (showRail ? "<span>Leave in <b>" + esc(leaveText) + "</b></span>" : "") + "</div>" +
        '<p class="label">Show on board</p><div class="modes">' +
        '<button type="button" data-mode="show_rail" class="' + (showRail ? "on" : "") + '">Regional Rail</button>' +
        '<button type="button" data-mode="show_bus" class="' + (showBus ? "on" : "") + '">Buses</button>' +
        '<button type="button" data-mode="show_metro" class="' + (draft.show_metro ? "on" : "") + '">Metro</button>' +
        '<button type="button" data-mode="show_trolley" class="' + (draft.show_trolley ? "on" : "") + '">Trolley</button>' +
        "</div>" +
        '<div class="commute"><div class="who">Regional Rail</div><label class="field">Home<input value="' + esc(entry ? entry.station : "") + '" disabled /></label><span class="swap">↔</span><label class="field">Commute to<select data-dest>' + opts + "</select></label><button class=\"save\" type=\"button\" data-save " + (this._busy ? "disabled" : "") + ">Save</button></div>" +
        (this._msg ? '<div class="note">' + esc(this._msg) + "</div>" : "") +
        '<section class="board"><div class="board-head"><p class="label" style="margin:0">Board</p><span class="sub">' + esc(entry ? entry.station : "") + '</span></div><div class="modes" style="padding:0 12px"><button type="button" data-tab="all" class="' + (this._tab === "all" ? "on" : "") + '">All</button><button type="button" data-tab="rail" class="' + (this._tab === "rail" ? "on" : "") + '">Regional Rail</button>' + (showBus ? '<button type="button" data-tab="bus" class="' + (this._tab === "bus" ? "on" : "") + '">Buses</button>' : "") + '</div><div class="bubbles">' + bubbles + busBubble + "</div></section>" +
        (showRail ? '<section class="deps"><div class="dep-head"><div><div class="eyebrow">Departures</div><div class="sub">' + esc(this._dir === "north" ? "Outbound" : "Inbound") + '</div></div><div class="modes" style="margin:0"><button type="button" data-dir="south" class="' + (this._dir === "south" ? "on" : "") + '">Inbound</button><button type="button" data-dir="north" class="' + (this._dir === "north" ? "on" : "") + '">Outbound</button></div></div><div class="cols"><span>Time</span><span>Destination</span><span style="text-align:center">Platform</span><span style="text-align:right">Expected</span></div>' + this._rows(trains) + "</section>" : "") +
        "</div>";
      this._bind();
    }

    _bind() {
      const root = this.shadowRoot;
      const grab = () => {
        this._draft = this._draft || {};
        const dest = root.querySelector("[data-dest]");
        const walk = root.querySelector("[data-walk]");
        const side = root.querySelector("[data-sidebar]");
        if (dest) this._draft.destination = dest.value;
        if (walk) this._draft.walk_minutes = Number(walk.value);
        if (side) this._draft.show_sidebar = side.checked;
      };
      root.querySelectorAll("[data-dir]").forEach((btn) => btn.addEventListener("click", () => { this._dir = btn.getAttribute("data-dir"); this._paint(); }));
      root.querySelectorAll("[data-tab]").forEach((btn) => btn.addEventListener("click", () => { this._tab = btn.getAttribute("data-tab"); this._paint(); }));
      root.querySelectorAll("[data-mode]").forEach((btn) => btn.addEventListener("click", () => {
        grab();
        const key = btn.getAttribute("data-mode");
        this._draft[key] = !this._draft[key];
        if (key === "show_rail" && this._draft.show_rail === undefined) this._draft.show_rail = false;
        this._paint();
      }));
      root.querySelector("[data-save]") && root.querySelector("[data-save]").addEventListener("click", async () => {
        grab();
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
            show_bus: this._draft.show_bus === true,
            show_metro: this._draft.show_metro === true,
            show_trolley: this._draft.show_trolley === true,
          });
          this._msg = "Saved.";
          await this._load();
        } catch (err) {
          this._msg = (err && err.message) || "Save failed";
        }
        this._busy = false;
        this._paint();
      });
    }
  }

  customElements.define("septa-live-panel", SeptaLivePanel);
})();
