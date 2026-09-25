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
    .mode-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 10px; margin-bottom: 18px; }
    .mode-card {
      display: flex; flex-direction: column; text-align: left; border: 0; border-radius: 16px;
      background: #171d27; color: #e8edf4; box-shadow: 0 0 0 1px #2a3340; padding: 0; overflow: hidden; min-height: 108px;
    }
    .mode-card.on { box-shadow: 0 0 0 1px #7aa2ce; }
    .mode-main { flex: 1; border: 0; background: transparent; color: inherit; font: inherit; text-align: left; cursor: pointer; padding: 14px 14px 6px; }
    .mode-card .nm { font-weight: 560; }
    .mode-card .st { color: #8b96a8; font-size: 13px; margin-top: 2px; }
    .steppers { display: flex; justify-content: flex-end; gap: 6px; padding: 0 10px 10px; }
    .steppers button {
      width: 32px; height: 32px; border-radius: 6px; border: 0; cursor: pointer;
      background: #0b0e13; color: #c5ced8; box-shadow: 0 0 0 1px #2a3340; font: inherit; font-size: 18px; line-height: 1;
    }
    .steppers button:disabled { opacity: 0.35; cursor: default; }
    .commute-row {
      display: grid; grid-template-columns: 8.5rem minmax(0,1fr) minmax(0,1fr) auto minmax(0,1.15fr);
      gap: 10px; align-items: end; padding: 12px; margin-bottom: 10px;
      border-radius: 16px; background: #171d27; box-shadow: 0 0 0 1px #2a3340;
    }
    .who { display: flex; align-items: center; gap: 8px; font-weight: 560; padding-bottom: 8px; }
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
      .commute-row, .mode-grid { grid-template-columns: 1fr; }
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
      const lines = (this._cfg && this._cfg.lines) || [];
      const busRoutes = (this._cfg && this._cfg.bus_routes) || [];
      const metroLines = (this._cfg && this._cfg.metro_lines) || [];
      const trolleyLines = (this._cfg && this._cfg.trolley_lines) || [];
      const metroStops = (this._cfg && this._cfg.metro_stations) || [];
      const trolleyStops = (this._cfg && this._cfg.trolley_stations) || [];
      const watches = Array.isArray(draft.watches) ? draft.watches : [];
      const showRail = draft.show_rail !== false;
      const showBus = draft.show_bus === true;
      const showMetro = draft.show_metro === true;
      const showTrolley = draft.show_trolley === true;
      const south = this._trains(entry, "south");
      const north = this._trains(entry, "north");
      const bus = this._state(entry, "next_bus");
      const leave = this._state(entry, "leave_in");
      const status = this._state(entry, "status");
      const trains = this._dir === "north" ? north : south;
      const leaveText = leave && !blank(leave) ? leave.state + " min" : "—";
      const statusText = status && !blank(status) ? status.state : "Live";
      const homeOpts = stations.map((name) => '<option value="' + esc(name) + '"' + (name === draft.station ? " selected" : "") + ">" + esc(name) + "</option>").join("");
      const destOpts = stations.map((name) => '<option value="' + esc(name) + '"' + (name === draft.destination ? " selected" : "") + ">" + esc(name) + "</option>").join("");
      const lineOpts = '<option value="">Any line</option>' + lines.map((line) => '<option value="' + esc(line.id) + '"' + (line.id === draft.rail_line ? " selected" : "") + ">" + esc(line.name) + "</option>").join("");
      const busOpts = '<option value="">Any route</option>' + busRoutes.map((route) => '<option value="' + esc(route.id) + '"' + (String(route.id) === String(draft.bus_line || "") ? " selected" : "") + ">" + esc(route.id + " · " + route.name) + "</option>").join("");
      const selectOpts = (list, value, empty, labelOf) =>
        '<option value="">' + esc(empty) + "</option>" +
        list.map((item) => {
          const id = typeof item === "string" ? item : item.id;
          const label = labelOf ? labelOf(item) : (typeof item === "string" ? item : item.name);
          return '<option value="' + esc(id) + '"' + (String(id) === String(value || "") ? " selected" : "") + ">" + esc(label) + "</option>";
        }).join("");
      const modeCard = (flag, mode, title, on) => {
        const extra = watches.filter((w) => w.mode === mode).length;
        const n = on ? 1 + extra : 0;
        const caption = on && extra ? n + " lines" : (on ? "On" : "Off");
        return '<div class="mode-card' + (on ? " on" : "") + '"><button type="button" class="mode-main" data-mode="' + flag + '"><div class="nm">' + esc(title) + '</div><div class="st">' + esc(caption) + '</div></button><div class="steppers"><button type="button" data-minus="' + mode + '"' + (on ? "" : " disabled") + '>−</button><button type="button" data-plus="' + mode + '"' + (on && n >= 4 ? " disabled" : "") + ">+</button></div></div>";
      };
      const watchRows = watches.filter((w) => (w.mode === "rail" && showRail) || (w.mode === "bus" && showBus) || (w.mode === "metro" && showMetro) || (w.mode === "trolley" && showTrolley)).map((w) => {
        const lineList = w.mode === "rail" ? lines : w.mode === "bus" ? busRoutes : w.mode === "metro" ? metroLines : trolleyLines;
        const placeList = w.mode === "metro" ? metroStops : w.mode === "trolley" ? trolleyStops : stations;
        const title = { rail: "Regional Rail", bus: "Buses", metro: "Metro", trolley: "Trolley" }[w.mode];
        const lineLabel = (item) => (w.mode === "bus" ? item.id + " · " + item.name : item.name);
        return '<div class="commute-row"><div class="who">' + esc(title) + '</div><label class="field">Line<select data-watch-line="' + esc(w.id) + '">' + selectOpts(lineList, w.line, "Any line", lineLabel) + '</select></label><label class="field">Home<select data-watch-home="' + esc(w.id) + '">' + selectOpts(placeList, w.home, "Same as above", null) + '</select></label><span class="swap">↔</span><label class="field">Commute to<select data-watch-dest="' + esc(w.id) + '">' + selectOpts(placeList, w.dest, "Any destination", null) + "</select></label></div>";
      }).join("");
      const serviceCard = (title, state) => {
        const summary = state && state.attributes && state.attributes.summary ? String(state.attributes.summary) : "";
        const count = state && !blank(state) ? state.state : "—";
        return '<article class="bubble"><div class="kicker"><span>' + esc(title) + '</span></div><div class="clockrow"><div class="clock">' + esc(count) + '</div></div><div class="hint">' + esc(summary || (state ? "None reporting" : "Turn it on, then Save")) + "</div></article>";
      };
      const metro = this._state(entry, "metro");
      const trolley = this._state(entry, "trolley");
      const busCard = showBus
        ? '<article class="bubble"><div class="kicker"><span>Next bus</span>' + (bus && bus.attributes && bus.attributes.route ? lineBadge(String(bus.attributes.route)) : "") + '</div><div class="clockrow"><div class="clock">' + esc(bus && !blank(bus) ? ((bus.attributes && bus.attributes.clock) || bus.state) : "—") + "</div></div><div class=\"hint\">" + esc(bus && bus.attributes && bus.attributes.destination ? bus.attributes.destination : "No nearby bus") + "</div></article>"
        : "";
      const bubbles = (this._tab === "all" || this._tab === "rail") && showRail
        ? this._bubble("Next inbound", south) + this._bubble("Next outbound", north)
        : "";
      const busBubble = (this._tab === "all" || this._tab === "bus") ? busCard : "";
      const metroBubble = showMetro && (this._tab === "all" || this._tab === "metro") ? serviceCard("Metro", metro) : "";
      const trolleyBubble = showTrolley && (this._tab === "all" || this._tab === "trolley") ? serviceCard("Trolley", trolley) : "";
      const lineBubbles = watches.filter((w) => this._tab === "all" || this._tab === w.mode).map((w) => {
        const state = this._state(entry, "line_" + w.mode + "_" + w.id);
        const name = (w.line || w.home || w.mode).toString();
        return serviceCard(name, state);
      }).join("");

      this.shadowRoot.innerHTML = "<style>" + CSS + "</style><div class=\"page\">" +
        '<header class="top"><div class="brand">' + RAIL + '<div><div class="eyebrow"><span class="live"></span> Regional Rail</div><h1>SEPTA Transit</h1></div></div>' +
        '<label class="side"><input type="checkbox" data-sidebar ' + (draft.show_sidebar !== false ? "checked" : "") + "/> Show in sidebar</label></header>" +
        '<div class="meta"><span>' + esc(statusText) + "</span><span>" + esc(entry ? entry.station : "") + '</span><label>Walk <select data-walk>' +
        [0, 2, 4, 5, 6, 8, 10, 12, 15, 20].map((n) => '<option value="' + n + '"' + (Number(draft.walk_minutes) === n ? " selected" : "") + ">" + n + " min</option>").join("") +
        "</select></label>" + (showRail ? "<span>Leave in <b>" + esc(leaveText) + "</b></span>" : "") + "</div>" +
        '<p class="label">Show on board</p><div class="mode-grid">' +
        modeCard("show_rail", "rail", "Regional Rail", showRail) +
        modeCard("show_bus", "bus", "Buses", showBus) +
        modeCard("show_metro", "metro", "Metro", showMetro) +
        modeCard("show_trolley", "trolley", "Trolley", showTrolley) +
        "</div>" +
        '<p class="label">Commute</p>' +
        (showRail ? '<div class="commute-row"><div class="who">Regional Rail</div><label class="field">Line<select data-rail-line>' + lineOpts + '</select></label><label class="field">Home<select data-home>' + homeOpts + '</select></label><span class="swap">↔</span><label class="field">Commute to<select data-dest>' + destOpts + "</select></label></div>" : "") +
        (showBus ? '<div class="commute-row"><div class="who">Buses</div><label class="field">Line<select data-bus-line>' + busOpts + '</select></label><label class="field">Home stop<input value="Nearby stops" disabled /></label><span class="swap"></span><label class="field">Commute to<input value="Any destination" disabled /></label></div>' : "") +
        (showMetro ? '<div class="commute-row"><div class="who">Metro</div><label class="field">Line<select data-metro-line>' + selectOpts(metroLines, draft.metro_line, "Any line", (item) => item.name) + '</select></label><label class="field">Home<select data-metro-home>' + selectOpts(metroStops, draft.metro_home, "All Metro", null) + '</select></label><span class="swap">↔</span><label class="field">Commute to<select data-metro-dest>' + selectOpts(metroStops, draft.metro_dest, "Any destination", null) + "</select></label></div>" : "") +
        (showTrolley ? '<div class="commute-row"><div class="who">Trolley</div><label class="field">Line<select data-trolley-line>' + selectOpts(trolleyLines, draft.trolley_line, "Any line", (item) => item.name) + '</select></label><label class="field">Home<select data-trolley-home>' + selectOpts(trolleyStops, draft.trolley_home, "All trolleys", null) + '</select></label><span class="swap">↔</span><label class="field">Commute to<select data-trolley-dest>' + selectOpts(trolleyStops, draft.trolley_dest, "Any destination", null) + "</select></label></div>" : "") +
        watchRows +
        '<button class="save" type="button" data-save ' + (this._busy ? "disabled" : "") + ">Save</button>" +
        '<p class="note">Plus adds another line and its sensor. Save turns Metro and trolley on, then they show up on the board.</p>' +
        (this._msg ? '<div class="note">' + esc(this._msg) + "</div>" : "") +
        '<section class="board"><div class="board-head"><p class="label" style="margin:0">Board</p><span class="sub">' + esc(entry ? entry.station : "") + '</span></div><div class="modes" style="padding:0 12px"><button type="button" data-tab="all" class="' + (this._tab === "all" ? "on" : "") + '">All</button>' + (showRail ? '<button type="button" data-tab="rail" class="' + (this._tab === "rail" ? "on" : "") + '">Regional Rail</button>' : "") + (showBus ? '<button type="button" data-tab="bus" class="' + (this._tab === "bus" ? "on" : "") + '">Buses</button>' : "") + (showMetro ? '<button type="button" data-tab="metro" class="' + (this._tab === "metro" ? "on" : "") + '">Metro</button>' : "") + (showTrolley ? '<button type="button" data-tab="trolley" class="' + (this._tab === "trolley" ? "on" : "") + '">Trolley</button>' : "") + '</div><div class="bubbles">' + bubbles + busBubble + metroBubble + trolleyBubble + lineBubbles + "</div></section>" +
        (showRail ? '<section class="deps"><div class="dep-head"><div><div class="eyebrow">Departures</div><div class="sub">' + esc(this._dir === "north" ? "Outbound" : "Inbound") + '</div></div><div class="modes" style="margin:0"><button type="button" data-dir="south" class="' + (this._dir === "south" ? "on" : "") + '">Inbound</button><button type="button" data-dir="north" class="' + (this._dir === "north" ? "on" : "") + '">Outbound</button></div></div><div class="cols"><span>Time</span><span>Destination</span><span style="text-align:center">Platform</span><span style="text-align:right">Expected</span></div>' + this._rows(trains) + "</section>" : "") +
        "</div>";
      this._bind();
    }

    _bind() {
      const root = this.shadowRoot;
      const grab = () => {
        this._draft = this._draft || {};
        const dest = root.querySelector("[data-dest]");
        const home = root.querySelector("[data-home]");
        const walk = root.querySelector("[data-walk]");
        const side = root.querySelector("[data-sidebar]");
        const railLine = root.querySelector("[data-rail-line]");
        const busLine = root.querySelector("[data-bus-line]");
        if (dest) this._draft.destination = dest.value;
        if (home) this._draft.station = home.value;
        if (walk) this._draft.walk_minutes = Number(walk.value);
        if (side) this._draft.show_sidebar = side.checked;
        if (railLine) this._draft.rail_line = railLine.value;
        if (busLine) this._draft.bus_line = busLine.value;
        ["metro", "trolley"].forEach((mode) => {
          const line = root.querySelector("[data-" + mode + "-line]");
          const home = root.querySelector("[data-" + mode + "-home]");
          const destSel = root.querySelector("[data-" + mode + "-dest]");
          if (line) this._draft[mode + "_line"] = line.value;
          if (home) this._draft[mode + "_home"] = home.value;
          if (destSel) this._draft[mode + "_dest"] = destSel.value;
        });
        this._draft.watches = (this._draft.watches || []).map((w) => {
          const line = root.querySelector('[data-watch-line="' + w.id + '"]');
          const wh = root.querySelector('[data-watch-home="' + w.id + '"]');
          const wd = root.querySelector('[data-watch-dest="' + w.id + '"]');
          return Object.assign({}, w, {
            line: line ? line.value : w.line,
            home: wh ? wh.value : w.home,
            dest: wd ? wd.value : w.dest,
          });
        });
      };
      const setMode = (mode, on) => {
        const flag = "show_" + mode;
        this._draft[flag] = mode === "rail" ? on : on;
        if (mode === "rail" && !on) this._draft.show_rail = false;
      };
      root.querySelectorAll("[data-dir]").forEach((btn) => btn.addEventListener("click", () => { this._dir = btn.getAttribute("data-dir"); this._paint(); }));
      root.querySelectorAll("[data-tab]").forEach((btn) => btn.addEventListener("click", () => { this._tab = btn.getAttribute("data-tab"); this._paint(); }));
      root.querySelectorAll("[data-mode]").forEach((btn) => btn.addEventListener("click", () => {
        grab();
        const key = btn.getAttribute("data-mode");
        const mode = key.replace("show_", "");
        const on = mode === "rail" ? this._draft.show_rail !== false : this._draft[key] === true;
        setMode(mode, !on);
        this._paint();
      }));
      root.querySelectorAll("[data-plus]").forEach((btn) => btn.addEventListener("click", () => {
        grab();
        const mode = btn.getAttribute("data-plus");
        const on = mode === "rail" ? this._draft.show_rail !== false : this._draft["show_" + mode] === true;
        if (!on) {
          setMode(mode, true);
        } else {
          const extra = (this._draft.watches || []).filter((w) => w.mode === mode);
          if (extra.length >= 3) return;
          this._draft.watches = (this._draft.watches || []).concat([{ id: Math.random().toString(36).slice(2, 10), mode: mode, line: "", home: "", dest: "" }]);
        }
        this._paint();
      }));
      root.querySelectorAll("[data-minus]").forEach((btn) => btn.addEventListener("click", () => {
        grab();
        const mode = btn.getAttribute("data-minus");
        const list = this._draft.watches || [];
        const extra = list.filter((w) => w.mode === mode);
        if (extra.length) {
          const last = extra[extra.length - 1].id;
          this._draft.watches = list.filter((w) => w.id !== last);
        } else {
          setMode(mode, false);
        }
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
            station: this._draft.station,
            destination: this._draft.destination,
            walk_minutes: Number(this._draft.walk_minutes),
            show_sidebar: this._draft.show_sidebar !== false,
            show_rail: this._draft.show_rail !== false,
            show_bus: this._draft.show_bus === true,
            show_metro: this._draft.show_metro === true,
            show_trolley: this._draft.show_trolley === true,
            rail_line: this._draft.rail_line || "",
            bus_line: this._draft.bus_line || "",
            metro_line: this._draft.metro_line || "",
            trolley_line: this._draft.trolley_line || "",
            metro_home: this._draft.metro_home || "",
            metro_dest: this._draft.metro_dest || "",
            trolley_home: this._draft.trolley_home || "",
            trolley_dest: this._draft.trolley_dest || "",
            watches: this._draft.watches || [],
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
