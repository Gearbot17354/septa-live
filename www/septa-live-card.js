(() => {
  const CARD_VERSION = "1.9.6";

const RAIL_STATIONS = [
    {name:'9th St',api:'9th St'},
    {name:'30th Street Station',api:'30th Street Station'},
    {name:'49th Street',api:'49th Street'},
    {name:'Airport Terminal A',api:'Airport Terminal A'},
    {name:'Airport Terminal B',api:'Airport Terminal B'},
    {name:'Airport Terminals C & D',api:'Airport Terminals C & D'},
    {name:'Airport Terminals E & F',api:'Airport Terminals E & F'},
    {name:'Allegheny',api:'Allegheny'},
    {name:'Allen Lane',api:'Allen Lane'},
    {name:'Ambler',api:'Ambler'},
    {name:'Angora',api:'Angora'},
    {name:'Ardmore',api:'Ardmore'},
    {name:'Ardsley',api:'Ardsley'},
    {name:'Bala',api:'Bala'},
    {name:'Berwyn',api:'Berwyn'},
    {name:'Bethayres',api:'Bethayres'},
    {name:'Bridesburg',api:'Bridesburg'},
    {name:'Bristol',api:'Bristol'},
    {name:'Bryn Mawr',api:'Bryn Mawr'},
    {name:'Carpenter',api:'Carpenter'},
    {name:'Chalfont',api:'Chalfont'},
    {name:'Chelten Avenue',api:'Chelten Avenue'},
    {name:'Cheltenham',api:'Cheltenham'},
    {name:'Chester Transportation Center',api:'Chester Transportation Center'},
    {name:'Chestnut Hill East',api:'Chestnut Hill East'},
    {name:'Chestnut Hill West',api:'Chestnut Hill West'},
    {name:'Churchmans Crossing',api:'Churchmans Crossing'},
    {name:'Claymont',api:'Claymont'},
    {name:'Clifton-Aldan',api:'Clifton-Aldan'},
    {name:'Colmar',api:'Colmar'},
    {name:'Conshohocken',api:'Conshohocken'},
    {name:'Cornwells Heights',api:'Cornwells Heights'},
    {name:'Crestmont',api:'Crestmont'},
    {name:'Croydon',api:'Croydon'},
    {name:'Crum Lynne',api:'Crum Lynne'},
    {name:'Curtis Park',api:'Curtis Park'},
    {name:'Cynwyd',api:'Cynwyd'},
    {name:'Darby',api:'Darby'},
    {name:'Daylesford',api:'Daylesford'},
    {name:'Delaware Valley College',api:'Delaware Valley College'},
    {name:'Devon',api:'Devon'},
    {name:'Downingtown',api:'Downingtown'},
    {name:'Doylestown',api:'Doylestown'},
    {name:'East Falls',api:'East Falls'},
    {name:'Eastwick',api:'Eastwick Station'},
    {name:'Eddington',api:'Eddington'},
    {name:'Eddystone',api:'Eddystone'},
    {name:'Elkins Park',api:'Elkins Park'},
    {name:'Elm Street, Norristown',api:'Elm Street, Norristown'},
    {name:'Elwyn',api:'Elwyn'},
    {name:'Exton',api:'Exton'},
    {name:'Fern Rock TC',api:'Fern Rock Transportation Center'},
    {name:'Fernwood-Yeadon',api:'Fernwood-Yeadon'},
    {name:'Folcroft',api:'Folcroft'},
    {name:'Forest Hills',api:'Forest Hills'},
    {name:'Fort Washington',api:'Fort Washington'},
    {name:'Fortuna',api:'Fortuna'},
    {name:'Fox Chase',api:'Fox Chase'},
    {name:'Germantown',api:'Germantown'},
    {name:'Gladstone',api:'Gladstone'},
    {name:'Glenolden',api:'Glenolden'},
    {name:'Glenside',api:'Glenside'},
    {name:'Gravers',api:'Gravers'},
    {name:'Gwynedd Valley',api:'Gwynedd Valley'},
    {name:'Hatboro',api:'Hatboro'},
    {name:'Haverford',api:'Haverford'},
    {name:'Highland',api:'Highland'},
    {name:'Highland Avenue',api:'Highland Avenue'},
    {name:'Holmesburg Junction',api:'Holmesburg Junction'},
    {name:'Ivy Ridge',api:'Ivy Ridge'},
    {name:'Jefferson Station',api:'Jefferson Station'},
    {name:'Jenkintown-Wyncote',api:'Jenkintown-Wyncote'},
    {name:'Langhorne',api:'Langhorne'},
    {name:'Lansdale',api:'Lansdale'},
    {name:'Lansdowne',api:'Lansdowne'},
    {name:'Lawndale',api:'Lawndale'},
    {name:'Levittown',api:'Levittown'},
    {name:'Link Belt',api:'Link Belt'},
    {name:'Main Street, Norristown',api:'Main Street, Norristown'},
    {name:'Malvern',api:'Malvern'},
    {name:'Manayunk',api:'Manayunk'},
    {name:'Marcus Hook',api:'Marcus Hook'},
    {name:'Meadowbrook',api:'Meadowbrook'},
    {name:'Media',api:'Media'},
    {name:'Melrose Park',api:'Melrose Park'},
    {name:'Merion',api:'Merion'},
    {name:'Miquon',api:'Miquon'},
    {name:'Morton',api:'Morton'},
    {name:'Mount Airy',api:'Mount Airy'},
    {name:'Moylan-Rose Valley',api:'Moylan-Rose Valley'},
    {name:'Narberth',api:'Narberth'},
    {name:'Neshaminy Falls',api:'Neshaminy Falls'},
    {name:'New Britain',api:'New Britain'},
    {name:'Newark',api:'Newark'},
    {name:'Noble',api:'Noble'},
    {name:'Norristown TC',api:'Norristown Transportation Center'},
    {name:'North Broad',api:'North Broad'},
    {name:'North Hills',api:'North Hills'},
    {name:'North Philadelphia',api:'North Philadelphia'},
    {name:'North Wales',api:'North Wales'},
    {name:'Norwood',api:'Norwood'},
    {name:'Olney',api:'Olney'},
    {name:'Oreland',api:'Oreland'},
    {name:'Overbrook',api:'Overbrook'},
    {name:'Paoli',api:'Paoli'},
    {name:'Penllyn',api:'Penllyn'},
    {name:'Pennbrook',api:'Pennbrook'},
    {name:'Philmont',api:'Philmont'},
    {name:'Primos',api:'Primos'},
    {name:'Prospect Park',api:'Prospect Park'},
    {name:'Queen Lane',api:'Queen Lane'},
    {name:'Radnor',api:'Radnor'},
    {name:'Ridley Park',api:'Ridley Park'},
    {name:'Rosemont',api:'Rosemont'},
    {name:'Roslyn',api:'Roslyn'},
    {name:'Rydal',api:'Rydal'},
    {name:'Ryers',api:'Ryers'},
    {name:'Secane',api:'Secane'},
    {name:'Sedgwick',api:'Sedgwick'},
    {name:'Sharon Hill',api:'Sharon Hill'},
    {name:'Somerton',api:'Somerton'},
    {name:'Spring Mill',api:'Spring Mill'},
    {name:'St. Davids',api:'St. Davids'},
    {name:'St. Martins',api:'St. Martins'},
    {name:'Stenton',api:'Stenton'},
    {name:'Strafford',api:'Strafford'},
    {name:'Suburban Station',api:'Suburban Station'},
    {name:'Swarthmore',api:'Swarthmore'},
    {name:'Tacony',api:'Tacony'},
    {name:'Temple University',api:'Temple University'},
    {name:'Thorndale',api:'Thorndale'},
    {name:'Torresdale',api:'Torresdale'},
    {name:'Trenton Transit Center',api:'Trenton Transit Center'},
    {name:'Trevose',api:'Trevose'},
    {name:'Tulpehocken',api:'Tulpehocken'},
    {name:'University City',api:'University City'},
    {name:'Upsal',api:'Upsal'},
    {name:'Villanova',api:'Villanova'},
    {name:'Wallingford',api:'Wallingford'},
    {name:'Warminster',api:'Warminster'},
    {name:'Washington Lane',api:'Washington Lane'},
    {name:'Wayne',api:'Wayne'},
    {name:'Wayne Junction',api:'Wayne Junction'},
    {name:'West Trenton',api:'West Trenton'},
    {name:'Whitford',api:'Whitford'},
    {name:'Willow Grove',api:'Willow Grove'},
    {name:'Wilmington',api:'Wilmington'},
    {name:'Wissahickon',api:'Wissahickon'},
    {name:'Wister',api:'Wister'},
    {name:'Woodbourne',api:'Woodbourne'},
    {name:'Wyndmoor',api:'Wyndmoor'},
    {name:'Wynnefield Avenue',api:'Wynnefield Avenue'},
    {name:'Wynnewood',api:'Wynnewood'},
    {name:'Yardley',api:'Yardley'},
  ];

  const SIZE_ROWS = { compact: 3, regular: 5, large: 8 };
  function normalizeSize(value) {
    const v = String(value || "").toLowerCase();
    if (v === "compact" || v === "small") return "compact";
    if (v === "large" || v === "big") return "large";
    return "regular";
  }
  function slugifyName(name) {
    return String(name || "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
  }
  function boardForStation(boards, station) {
    const want = String(station || "").trim().toLowerCase();
    const slug = slugifyName(want);
    return boards.find((b) => b.slug === slug || String(b.name).toLowerCase() === want) || null;
  }
  function stationApiName(station) {
    const want = String(station || "").trim();
    const slug = slugifyName(want);
    const hit = RAIL_STATIONS.find(
      (s) => s.api === want || s.name === want || slugifyName(s.api) === slug || slugifyName(s.name) === slug,
    );
    return hit ? hit.api : want;
  }
  const ONTIME = "#7dba98";
  const LATE = "#d4a054";
  const CRIT = "#d0726a";
  const RAIL = {
    AIR: "#00539f",
    CHE: "#9b5a2c",
    CHW: "#3d9cc7",
    CYN: "#6b3fa0",
    FOX: "#e87722",
    LAN: "#2e7d32",
    MED: "#e35205",
    NOR: "#6e7a86",
    PAO: "#6ea244",
    TRE: "#9b1b30",
    WAR: "#e6a317",
    WTR: "#ef6c00",
    WIL: "#c62828",
  };
  const LINE = {
    L: { bg: "#1c9ad6", fg: "#fff" },
    B: { bg: "#f26100", fg: "#fff" },
    M: { bg: "#613393", fg: "#fff" },
    T: { bg: "#5a960a", fg: "#fff" },
    G: { bg: "#fcd602", fg: "#14110c" },
    D: { bg: "#e5427b", fg: "#fff" },
  };
  const RAIL_NAME = [
    [/airport/i, "AIR"],
    [/chestnut hill east|chestnut h east/i, "CHE"],
    [/chestnut hill west|chestnut h west/i, "CHW"],
    [/cynwyd/i, "CYN"],
    [/fox chase/i, "FOX"],
    [/lansdale|doylestown/i, "LAN"],
    [/media|wawa/i, "MED"],
    [/manayunk|norristown/i, "NOR"],
    [/paoli|thorndale/i, "PAO"],
    [/trenton/i, "TRE"],
    [/warminster/i, "WAR"],
    [/west trenton/i, "WTR"],
    [/wilmington|newark/i, "WIL"],
  ];

  function railCode(line) {
    const raw = String(line || "").trim().toUpperCase();
    if (RAIL[raw]) return raw;
    for (const [re, code] of RAIL_NAME) {
      if (re.test(line || "")) return code;
    }
    return "";
  }

  function railBadge(line) {
    const code = railCode(line);
    if (!code) return "";
    return `<span class="rail-badge" style="background:${RAIL[code]}">${esc(code)}</span>`;
  }
  const MODE_FOR = {
    south: "rail",
    north: "rail",
    bus: "bus",
    metro: "metro",
    trolley: "trolley",
    leave: "walk",
    status: "status",
    map: "map",
  };
  const LETTERS_FOR = {
    metro: ["L", "B", "M"],
    trolley: ["T", "G", "D"],
  };

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
    if (status && /schedul/i.test(status)) return "Scheduled";
    if (status && /cancel/i.test(status)) return status;
    if (delayMin <= 0) return "On time";
    return `${durationLabel(delayMin)} late`;
  }

  function serviceLabel(raw) {
    const key = String(raw || "").trim().toUpperCase().replace(/[_-]+/g, " ");
    if (!key) return "";
    if (key === "LOCAL") return "Local";
    if (key === "EXP" || key === "EXPRESS") return "Express";
    if (key === "LIMITED" || key === "EXPRESS LIMITED" || key === "LIMITED EXPRESS") return "Limited";
    return key.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
  }

  const BOARD_RE = /^sensor\.(?:.+_)?septa_(.+?)_(southbound|northbound|inbound|outbound)_board$/;

  function isSeptaSensor(id) {
    return id.startsWith("sensor.") && id.includes("septa_");
  }

  function findEntity(hass, suffix, fallback) {
    const states = hass && hass.states ? hass.states : {};
    const keys = Object.keys(states);
    const aliases = {
      "_next_southbound": ["_next_inbound", "_next_southbound"],
      "_next_northbound": ["_next_outbound", "_next_northbound"],
      "_southbound_board": ["_inbound_board", "_southbound_board", "_south_board"],
      "_northbound_board": ["_outbound_board", "_northbound_board", "_north_board"],
      "_map": ["_map", "_live_map"],
    };
    const options = aliases[suffix] || [suffix];
    for (const end of options) {
      const hits = keys.filter((id) => isSeptaSensor(id) && id.endsWith(end));
      hits.sort((a, b) => Number(!a.startsWith("sensor.septa_")) - Number(!b.startsWith("sensor.septa_")));
      if (hits.length) return hits[0];
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
    if (/^-?\d+(\.\d+)?$/.test(String(state.state))) return durationLabel(Number(state.state));
    return String(state.state);
  }

  function durationLabel(n) {
    if (n == null || Number.isNaN(Number(n))) return "—";
    const m = Math.round(Number(n));
    if (m <= 0) return "Due";
    if (m < 60) return `${m} min`;
    const h = Math.floor(m / 60);
    const rest = m % 60;
    return rest ? `${h}h ${rest}m` : `${h}h`;
  }

  function overnightEmpty(heading) {
    const hour = new Date().getHours();
    const overnight = hour >= 21 || hour < 5;
    const dir = String(heading || "scheduled").toLowerCase();
    if (overnight) {
      return `No more ${dir} trains tonight. SEPTA posts the next board with the first morning trips.`;
    }
    return `No ${dir} trains listed`;
  }

  function trainsOf(state, limit) {
    if (!state || !state.attributes) return [];
    const a = state.attributes;
    const list = a.trains || a.southbound || a.northbound || [];
    return Array.isArray(list) ? list.slice(0, limit || 8) : [];
  }

  function dirFromEntity(entityId) {
    return /north|outbound/.test(String(entityId || "")) ? "north" : "south";
  }

  function synthTrain(state) {
    if (!state) return null;
    return {
      train_id: attr(state, "train_id"),
      destination: attr(state, "destination"),
      line: attr(state, "line"),
      clock: attr(state, "clock") || attr(state, "depart"),
      minutes: Number(state.state),
      track: attr(state, "track") || attr(state, "platform"),
      status: attr(state, "status") || attr(state, "delay"),
      delay_min: Number(attr(state, "delay_min") || 0),
      cancelled: Boolean(state.attributes && state.attributes.cancelled),
      scheduled: Boolean(state.attributes && state.attributes.scheduled) || /schedul/i.test(attr(state, "status")),
      service_type: attr(state, "service_type") || attr(state, "service"),
    };
  }

  function trainsForDirection(hass, entity, direction) {
    const state = stateOf(hass, entity);
    const self = trainsOf(state);
    if (self.length) return { state, trains: self, entity };
    const suffix = direction === "north" ? "_northbound_board" : "_southbound_board";
    const boardId = findEntity(hass, suffix, "");
    const board = stateOf(hass, boardId);
    const list = trainsOf(board);
    if (list.length) return { state: board, trains: list, entity: boardId || entity };
    const one = synthTrain(state);
    return { state, trains: one ? [one] : [], entity };
  }

  function trainHint(t) {
    const wait = durationLabel(t && t.minutes);
    const service = serviceLabel(t && (t.service_type || t.service));
    const dest = t && t.destination ? t.destination : "";
    const track = t && String(t.track || t.platform || "").trim();
    return [wait, service, dest, track ? `Track ${track}` : ""].filter(Boolean).join(" · ");
  }

  function trainColor(t) {
    if (!t) return "inherit";
    if (t.scheduled || /schedul/i.test(t.status || "")) return "inherit";
    return tone(Number(t.delay_min || 0), Boolean(t.cancelled));
  }

  function bubbleTrain(t, size) {
    const clock = splitClock(t.clock);
    const label = `${clock.time || "—"}${clock.period ? " " + clock.period : ""}`;
    const late = delayLabel(Number(t.delay_min || 0), Boolean(t.cancelled), t.status || (t.scheduled ? "Scheduled" : ""));
    const color = trainColor(t);
    return `
      <div class="bubble-train is-${size}">
        <div class="bubble-clock-row">
          <div class="bubble-clock is-${size}" style="color:${color}">${esc(label)}</div>
          <div class="bubble-late" style="color:${color}">${esc(late)}</div>
        </div>
        <div class="bubble-hint">${esc(trainHint(t))}</div>
      </div>`;
  }

  function heroInner(title, trains, entity, limit) {
    const list = Array.isArray(trains) ? trains.slice(0, Number(limit) > 0 ? Number(limit) : 2) : [];
    const first = list[0];
    const body = first
      ? list.map((t, i) => bubbleTrain(t, i === 0 ? "lg" : "sm")).join("")
      : `<div class="empty">${esc(overnightEmpty(title))}</div>`;
    return `
      <button class="hit bubble" type="button" data-entity="${esc(entity || "")}">
        <div class="bubble-head">
          <div class="kicker-row">${modeIcon("rail")}<div class="kicker">${esc(title)}</div></div>
          ${first ? railBadge(first.line) : ""}
        </div>
        ${body}
      </button>`;
  }

  function serviceBubble(opts) {
    const extra = opts.extra || "";
    const late = opts.late ? `<div class="bubble-late" style="color:${opts.color || "inherit"}">${esc(opts.late)}</div>` : "";
    const hint = opts.hint ? `<div class="bubble-hint">${esc(opts.hint)}</div>` : "";
    return `
      <button class="hit bubble" type="button" data-entity="${esc(opts.entity || "")}">
        <div class="bubble-head">
          <div class="kicker-row">${modeIcon(opts.kind || "rail")}<div class="kicker">${esc(opts.title || "")}</div></div>
          ${extra}
        </div>
        <div class="bubble-clock-row">
          <div class="bubble-clock is-lg" style="color:${opts.color || "inherit"}">${esc(opts.clock || "—")}</div>
          ${late}
        </div>
        ${hint}
      </button>`;
  }

  function busInner(state, entity, title) {
    if (!state) {
      return serviceBubble({ entity, kind: "bus", title: title || "Next bus", clock: "—", hint: "No nearby buses" });
    }
    const clock = splitClock(attr(state, "clock") || attr(state, "depart") || "");
    const label = `${clock.time || minutesOf(state)}${clock.period ? " " + clock.period : ""}`;
    const delay = Number(attr(state, "delay_min") || 0);
    const live = Boolean(attr(state, "live"));
    const dest = attr(state, "destination");
    const route = attr(state, "route");
    const color = live ? tone(delay, false) : "inherit";
    return serviceBubble({
      entity,
      kind: "bus",
      title: title || (route ? `Bus ${route}` : "Next bus"),
      extra: route ? pill(route) : "",
      clock: label,
      late: live ? delayLabel(delay, false, "") : "Scheduled",
      color,
      hint: [minutesOf(state), dest].filter(Boolean).join(" · ") || "live",
    });
  }

  function leaveInner(state, entity, title) {
    const n = state && state.state !== "unknown" && state.state !== "unavailable" ? Number(state.state) : null;
    const value = n == null || Number.isNaN(n) ? "—" : n <= 0 ? "Now" : durationLabel(n);
    const walk = attr(state, "walk_minutes");
    const train = attr(state, "train_id");
    const hint = [walk ? `${walk} min walk` : "Walk window", train ? `#${train}` : ""].filter(Boolean).join(" · ");
    return serviceBubble({
      entity,
      kind: "walk",
      title: title || "Leave in",
      clock: value,
      color: n != null && n <= 2 ? LATE : ONTIME,
      hint,
    });
  }

  function statusInner(state, entity, title) {
    const text = state ? state.state : "—";
    const color = /suspend|alert|delay/i.test(text) ? LATE : ONTIME;
    return serviceBubble({
      entity,
      kind: "status",
      title: title || "Line status",
      clock: text,
      color,
      hint: "Line",
    });
  }

  function splitClock(label) {
    const text = String(label || "").trim();
    const match = text.match(/^(.+?)\s*(AM|PM)$/i);
    if (!match) return { time: text, period: "" };
    return { time: match[1], period: match[2].toUpperCase() };
  }

  function titleStation(slug) {
    return String(slug || "")
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
  }

  function slugFromEntity(entityId) {
    const match = String(entityId || "").match(BOARD_RE);
    return match ? match[1] : "";
  }

  function discoverBoards(hass) {
    const states = hass && hass.states ? hass.states : {};
    const map = {};
    for (const id of Object.keys(states)) {
      const match = id.match(BOARD_RE);
      if (!match) continue;
      const slug = match[1];
      const dir = match[2];
      if (!map[slug]) {
        map[slug] = { slug, name: titleStation(slug), south: "", north: "" };
      }
      if (dir === "southbound" || dir === "inbound") map[slug].south = id;
      else map[slug].north = id;
      const station = states[id] && states[id].attributes && states[id].attributes.station;
      if (station) map[slug].name = String(station);
    }
    return Object.values(map).sort((a, b) => a.name.localeCompare(b.name));
  }

  function attr(state, key) {
    return (state && state.attributes && state.attributes[key]) || "";
  }

  function circleIcon(inner) {
    return `<svg class="mode" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="11" fill="#231f20" stroke="#fff" stroke-width="1.15"/>${inner}</svg>`;
  }

  const MODE_SVG = {
    metro: `<svg class="mode" viewBox="0 0 500 500" aria-hidden="true"><circle cx="250" cy="250" r="240" fill="#231f20" stroke="#fff" stroke-width="16"/><path fill="#fff" d="M197.7 412.9l125.2-107.4H166.6L56 194.5 162.7 86.8h139.4L176.8 194.2h156.3l110.7 111.1-106.6 107.5H197.7Zm115.8-117.9-86.5-86.5c-2.3-2.3-5.5-3.6-8.7-3.7h-32l86.1 86.1c2.6 2.6 6.1 4 9.7 4h31.4z"/></svg>`,
    bus: `<svg class="mode" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" role="img" aria-label="SEPTA Bus"><path fill="#231F20" d="M99.988 200.409c55.226 0 99.988-44.763 99.988-99.988 0-55.219-44.763-99.982-99.988-99.982C44.769.439 0 45.202 0 100.421c0 55.225 44.769 99.988 99.988 99.988"/><path fill="#fff" d="M56.956 151.397c0-2.028 1.647-3.676 3.676-3.676h8.021c2.029 0 3.669 1.647 3.669 3.676v12.256c0 2.036-1.641 3.677-3.669 3.677h-8.021c-2.029 0-3.676-1.641-3.676-3.677z"/><path fill="#fff" d="M131.897 151.048c0-2.029 1.641-3.676 3.676-3.676h8.014c2.035 0 3.68 1.646 3.68 3.676v12.256c0 2.029-1.645 3.677-3.68 3.677h-8.014c-2.035 0-3.676-1.647-3.676-3.677z"/><path fill="#fff" d="M156.575 142.646l2.34-20.658-3.046-73.562c0-4.134-2.077-18.406-8.39-19.138H56.466c-7.691.242-9.541 14.266-9.083 19.138l-4.562 75.565 2.535 18.14c0 4.128 111.219 4.649 111.219.511"/><path fill="#fff" d="M42.359 143.015c0-2.144 1.647-3.873 3.676-3.873h110.266c2.026 0 3.677 1.729 3.677 3.873v7.073c0 2.137-1.65 3.873-3.677 3.873H46.035c-2.029 0-3.676-1.736-3.676-3.873z"/><path fill="#231F20" d="M51.842 130.759c0-1.075.82-1.939 1.836-1.939h5.63c1.016 0 1.836.864 1.836 1.939v4.052c0 1.068-.82 1.939-1.836 1.939h-5.63c-1.016 0-1.836-.871-1.836-1.939z"/><path fill="#231F20" d="M63.309 130.771c0-1.068.82-1.939 1.836-1.939h5.63c1.016 0 1.836.871 1.836 1.939v4.058c0 1.068-.82 1.934-1.836 1.934h-5.63c-1.016 0-1.836-.865-1.836-1.934z"/><path fill="#231F20" d="M130.606 130.53c0-1.068.826-1.94 1.835-1.94h5.638c1.015 0 1.835.872 1.835 1.94v4.051c0 1.075-.82 1.94-1.835 1.94h-5.638c-1.009 0-1.835-.865-1.835-1.94z"/><path fill="#231F20" d="M142.073 130.543c0-1.068.827-1.934 1.835-1.934h5.639c1.008 0 1.828.865 1.828 1.934v4.058c0 1.068-.82 1.939-1.828 1.939h-5.639c-1.008 0-1.835-.871-1.835-1.939z"/><path fill="#231F20" d="M57.178 54.367h89.917c3.091 0 5.594 2.729 5.594 6.093l1.46 45.087c0 3.365-3.963 5.477-7.054 5.477H57.178c-3.083 0-8.147-2.493-8.147-5.857l1.634-44.579c0-3.365 3.43-6.214 6.513-6.214"/><path fill="#231F20" d="M58.507 47.778l1.348-10.793c0-1.113 1.948-2.531 3.042-2.531h77.773c1.068 0 1.962.954 1.962 2.061l1.202 11.105c0 1.145-2.096 2.22-3.164 2.22H60.474c-1.094 0-1.967-.916-1.967-2.062"/><path fill="#231F20" d="M50.118 41.945c0-.999.82-1.813 1.836-1.813h2.862c1.013 0 1.833.814 1.833 1.813s-.82 1.813-1.833 1.813h-2.862c-1.016 0-1.836-.814-1.836-1.813"/><path fill="#231F20" d="M145.19 41.545c0-.999.82-1.813 1.835-1.813h2.855c1.021 0 1.841.814 1.841 1.813s-.82 1.806-1.841 1.806h-2.855c-.999 0-1.82-.808-1.82-1.806"/></svg>`,
    rail: `<svg class="mode" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 250 250" role="img" aria-label="SEPTA Regional Rail"><circle cx="125" cy="125" r="125" fill="#231F20"/><g fill="#fff" fill-rule="evenodd"><path d="M119.31 15.81L127.19 15.69L133.16 15.66L137.22 15.72L139.38 15.88L139.62 16.12L140.12 16.31L140.88 16.44L141.88 16.50L143.12 16.50L144.12 16.56L144.88 16.69L145.38 16.88L145.62 17.12L146.00 17.31L146.50 17.44L147.12 17.50L147.88 17.50L148.56 17.62L149.19 17.88L149.75 18.25L150.25 18.75L150.69 19.12L151.06 19.38L151.38 19.50L151.62 19.50L152.03 19.78L152.59 20.34L153.31 21.19L154.19 22.31L154.62 23.38L154.62 24.38L154.19 25.31L153.31 26.19L152.53 26.84L151.84 27.28L151.25 27.50L150.75 27.50L150.19 27.38L149.56 27.12L148.88 26.75L148.12 26.25L147.19 25.81L146.06 25.44L144.75 25.12L143.25 24.88L142.06 24.62L141.19 24.38L140.62 24.12L140.38 23.88L139.31 23.62L137.44 23.38L134.75 23.12L131.25 22.88L128.59 22.97L126.78 23.41L125.81 24.19L125.69 25.31L125.72 26.28L125.91 27.09L126.25 27.75L126.75 28.25L127.12 29.00L127.38 30.00L127.50 31.25L127.50 32.75L127.38 33.94L127.12 34.81L126.75 35.38L126.25 35.62L125.88 36.44L125.62 37.81L125.50 39.75L125.50 42.25L125.91 44.16L126.72 45.47L127.94 46.19L129.56 46.31L130.84 46.47L131.78 46.66L132.38 46.88L132.62 47.12L134.06 47.38L136.69 47.62L140.50 47.88L145.50 48.12L149.31 48.38L151.94 48.62L153.38 48.88L153.62 49.12L154.12 49.31L154.88 49.44L155.88 49.50L157.12 49.50L158.12 49.56L158.88 49.69L159.38 49.88L159.62 50.12L160.06 50.31L160.69 50.44L161.50 50.50L162.50 50.50L163.31 50.56L163.94 50.69L164.38 50.88L164.62 51.12L165.19 51.38L166.06 51.62L167.25 51.88L168.75 52.12L170.25 52.50L171.75 53.00L173.25 53.62L174.75 54.38L176.09 55.16L177.28 55.97L178.31 56.81L179.19 57.69L179.97 58.91L180.66 60.47L181.25 62.38L181.75 64.62L174.78 66.34L160.34 67.53L138.44 68.19L109.06 68.31L87.00 68.19L72.25 67.81L64.81 67.19L64.69 66.31L64.66 65.59L64.72 65.03L64.88 64.62L65.12 64.38L65.31 64.00L65.44 63.50L65.50 62.88L65.50 62.12L65.62 61.31L65.88 60.44L66.25 59.50L66.75 58.50L67.53 57.47L68.59 56.41L69.94 55.31L71.56 54.19L72.91 53.34L73.97 52.78L74.75 52.50L75.25 52.50L75.88 52.38L76.62 52.12L77.50 51.75L78.50 51.25L79.44 50.88L80.31 50.62L81.12 50.50L81.88 50.50L82.50 50.44L83.00 50.31L83.38 50.12L83.62 49.88L84.12 49.69L84.88 49.56L85.88 49.50L87.12 49.50L88.12 49.44L88.88 49.31L89.38 49.12L89.62 48.88L91.38 48.62L94.62 48.38L99.38 48.12L105.62 47.88L110.38 47.62L113.62 47.38L115.38 47.12L115.62 46.88L116.06 46.69L116.69 46.56L117.50 46.50L118.50 46.50L119.34 46.41L120.03 46.22L120.56 45.94L120.94 45.56L121.22 44.78L121.41 43.59L121.50 42.00L121.50 40.00L121.31 38.38L120.94 37.12L120.38 36.25L119.62 35.75L119.06 35.00L118.69 34.00L118.50 32.75L118.50 31.25L118.69 30.00L119.06 29.00L119.62 28.25L120.38 27.75L120.94 27.19L121.31 26.56L121.50 25.88L121.50 25.12L121.41 24.47L121.22 23.91L120.94 23.44L120.56 23.06L120.09 22.78L119.53 22.59L118.88 22.50L118.12 22.50L117.50 22.56L117.00 22.69L116.62 22.88L116.38 23.12L115.62 23.31L114.38 23.44L112.62 23.50L110.38 23.50L108.62 23.56L107.38 23.69L106.62 23.88L106.38 24.12L105.88 24.38L105.12 24.62L104.12 24.88L102.88 25.12L101.75 25.44L100.75 25.81L99.88 26.25L99.12 26.75L98.44 27.12L97.81 27.38L97.25 27.50L96.75 27.50L96.22 27.34L95.66 27.03L95.06 26.56L94.44 25.94L93.97 25.34L93.66 24.78L93.50 24.25L93.50 23.75L93.84 23.03L94.53 22.09L95.56 20.94L96.94 19.56L98.09 18.53L99.03 17.84L99.75 17.50L100.25 17.50L100.69 17.44L101.06 17.31L101.38 17.12L101.62 16.88L102.12 16.69L102.88 16.56L103.88 16.50L105.12 16.50L106.09 16.47L106.78 16.41L107.19 16.31L107.31 16.19L109.38 16.06L113.38 15.94Z"/><path d="M82.69 177.81L84.81 177.69L86.47 177.78L87.66 178.09L88.38 178.62L88.62 179.38L93.06 179.94L101.69 180.31L114.50 180.50L131.50 180.50L144.25 180.31L152.75 179.94L157.00 179.38L157.00 178.62L157.56 178.06L158.69 177.69L160.38 177.50L162.62 177.50L164.44 177.69L165.81 178.06L166.75 178.62L167.25 179.38L168.00 179.94L169.00 180.31L170.25 180.50L171.75 180.50L172.97 180.59L173.91 180.78L174.56 181.06L174.94 181.44L175.28 181.91L175.59 182.47L175.88 183.12L176.12 183.88L176.50 184.69L177.00 185.56L177.62 186.50L178.38 187.50L178.56 188.31L178.19 188.94L177.25 189.38L175.75 189.62L174.75 190.12L174.25 190.88L174.25 191.88L174.75 193.12L175.22 194.16L175.66 194.97L176.06 195.56L176.44 195.94L177.16 196.22L178.22 196.41L179.62 196.50L181.38 196.50L182.91 196.91L184.22 197.72L185.31 198.94L186.19 200.56L186.97 201.91L187.66 202.97L188.25 203.75L188.75 204.25L189.19 204.75L189.56 205.25L189.88 205.75L190.12 206.25L190.28 206.72L190.34 207.16L190.31 207.56L190.19 207.94L189.69 208.25L188.81 208.50L187.56 208.69L185.94 208.81L185.09 209.53L185.03 210.84L185.75 212.75L187.25 215.25L187.28 217.16L185.84 218.47L182.94 219.19L178.56 219.31L175.00 218.88L172.25 217.88L170.31 216.31L169.19 214.19L168.31 212.44L167.69 211.06L167.31 210.06L167.19 209.44L161.59 208.97L150.53 208.66L134.00 208.50L112.00 208.50L95.22 209.09L83.66 210.28L77.31 212.06L76.19 214.44L75.25 216.31L74.50 217.69L73.94 218.56L73.56 218.94L72.28 219.22L70.09 219.41L67.00 219.50L63.00 219.50L59.97 219.41L57.91 219.22L56.81 218.94L56.69 218.56L56.72 218.03L56.91 217.34L57.25 216.50L57.75 215.50L58.25 214.62L58.75 213.88L59.25 213.25L59.75 212.75L60.19 212.19L60.56 211.56L60.88 210.88L61.12 210.12L60.91 209.53L60.22 209.09L59.06 208.81L57.44 208.69L56.19 208.56L55.31 208.44L54.81 208.31L54.69 208.19L54.72 207.84L54.91 207.28L55.25 206.50L55.75 205.50L56.47 204.28L57.41 202.84L58.56 201.19L59.94 199.31L61.44 197.88L63.06 196.88L64.81 196.31L66.69 196.19L68.22 195.84L69.41 195.28L70.25 194.50L70.75 193.50L71.12 192.62L71.38 191.88L71.50 191.25L71.50 190.75L71.22 190.34L70.66 190.03L69.81 189.81L68.69 189.69L67.81 189.50L67.19 189.25L66.81 188.94L66.69 188.56L66.78 188.03L67.09 187.34L67.62 186.50L68.38 185.50L69.00 184.56L69.50 183.69L69.88 182.88L70.12 182.12L70.78 181.53L71.84 181.09L73.31 180.81L75.19 180.69L76.66 180.47L77.72 180.16L78.38 179.75L78.62 179.25L78.84 178.84L79.03 178.53L79.19 178.31L79.31 178.19L79.94 178.06L81.06 177.94Z"/><path d="M108.56 72.81L137.94 72.69L160.00 77.06L174.75 85.94L182.19 99.31L182.31 117.19L182.03 131.28L181.34 141.59L180.25 148.12L178.75 150.88L177.62 153.06L176.88 154.69L176.50 155.75L176.50 156.25L176.19 157.25L175.56 158.75L174.62 160.75L173.38 163.25L172.16 165.16L170.97 166.47L169.81 167.19L168.69 167.31L167.78 167.72L167.09 168.41L166.62 169.38L166.38 170.62L165.75 171.56L164.75 172.19L163.38 172.50L161.62 172.50L160.28 171.97L159.34 170.91L158.81 169.31L158.69 167.19L158.31 165.56L157.69 164.44L156.81 163.81L155.69 163.69L154.50 163.12L153.25 162.12L151.94 160.69L150.56 158.81L149.53 156.84L148.84 154.78L148.50 152.62L148.50 150.38L148.06 148.62L147.19 147.38L145.88 146.62L144.12 146.38L142.81 142.19L141.94 134.06L141.50 122.00L141.50 106.00L141.34 93.84L141.03 85.53L140.56 81.06L139.94 80.44L137.53 79.97L133.34 79.66L127.38 79.50L119.62 79.50L113.66 79.59L109.47 79.78L107.06 80.06L106.44 80.44L105.97 84.78L105.66 93.09L105.50 105.38L105.50 121.62L105.06 133.88L104.19 142.12L102.88 146.38L101.12 146.62L99.81 147.31L98.94 148.44L98.50 150.00L98.50 152.00L98.16 154.03L97.47 156.09L96.44 158.19L95.06 160.31L93.75 161.94L92.50 163.06L91.31 163.69L90.19 163.81L89.34 164.41L88.78 165.47L88.50 167.00L88.50 169.00L88.03 170.53L87.09 171.59L85.69 172.19L83.81 172.31L82.38 172.12L81.38 171.62L80.81 170.81L80.69 169.69L80.31 168.81L79.69 168.19L78.81 167.81L77.69 167.69L76.75 167.50L76.00 167.25L75.44 166.94L75.06 166.56L74.72 166.03L74.41 165.34L74.12 164.50L73.88 163.50L73.12 161.62L71.88 158.88L70.12 155.25L67.88 150.75L66.19 143.00L65.06 132.00L64.50 117.75L64.50 100.25L64.50 87.06L64.50 78.19L64.50 73.62L64.50 73.38L71.84 73.16L86.53 72.97Z"/><path d="M149.44 55.06L149.06 55.44L148.81 56.31L148.69 57.69L148.69 59.56L148.81 61.94L150.09 63.72L152.53 64.91L156.12 65.50L160.88 65.50L164.53 65.41L167.09 65.22L168.56 64.94L168.94 64.56L169.22 64.03L169.41 63.34L169.50 62.50L169.50 61.50L169.41 60.59L169.22 59.78L168.94 59.06L168.56 58.44L168.16 57.97L167.72 57.66L167.25 57.50L166.75 57.50L166.12 57.38L165.38 57.12L164.50 56.75L163.50 56.25L162.56 55.88L161.69 55.62L160.88 55.50L160.12 55.50L159.50 55.44L159.00 55.31L158.62 55.12L158.38 54.88L157.75 54.69L156.75 54.56L155.38 54.50L153.62 54.50L152.25 54.50L151.25 54.50L150.62 54.50L150.38 54.50L150.09 54.59L149.78 54.78Z"/><path d="M149.69 122.44L148.81 123.06L148.09 123.66L147.53 124.22L147.12 124.75L146.88 125.25L146.69 125.81L146.56 126.44L146.50 127.12L146.50 127.88L146.66 128.66L146.97 129.47L147.44 130.31L148.06 131.19L148.66 131.91L149.22 132.47L149.75 132.88L150.25 133.12L150.81 133.31L151.44 133.44L152.12 133.50L152.88 133.50L153.66 133.34L154.47 133.03L155.31 132.56L156.19 131.94L156.91 131.34L157.47 130.78L157.88 130.25L158.12 129.75L158.31 129.19L158.44 128.56L158.50 127.88L158.50 127.12L158.34 126.34L158.03 125.53L157.56 124.69L156.94 123.81L156.22 123.09L155.41 122.53L154.50 122.12L153.50 121.88L152.69 121.69L152.06 121.56L151.62 121.50L151.38 121.50L150.97 121.66L150.41 121.97Z"/><path d="M89.62 54.88L89.38 55.12L88.94 55.31L88.31 55.44L87.50 55.50L86.50 55.50L85.69 55.56L85.06 55.69L84.62 55.88L84.38 56.12L83.88 56.38L83.12 56.62L82.12 56.88L80.88 57.12L79.84 57.41L79.03 57.72L78.44 58.06L78.06 58.44L77.78 59.09L77.59 60.03L77.50 61.25L77.50 62.75L78.78 63.91L81.34 64.72L85.19 65.19L90.31 65.31L94.19 64.81L96.81 63.69L98.19 61.94L98.31 59.56L98.31 57.69L98.19 56.31L97.94 55.44L97.56 55.06L96.91 54.78L95.97 54.59L94.75 54.50L93.25 54.50L92.06 54.50L91.19 54.50L90.62 54.50L90.38 54.50L90.12 54.56L89.88 54.69Z"/><path d="M107.06 54.44L106.44 55.06L105.97 55.91L105.66 56.97L105.50 58.25L105.50 59.75L105.56 61.00L105.69 62.00L105.88 62.75L106.12 63.25L106.47 63.72L106.91 64.16L107.44 64.56L108.06 64.94L110.41 65.22L114.47 65.41L120.25 65.50L127.75 65.50L133.53 65.34L137.59 65.03L139.94 64.56L140.56 63.94L141.03 63.03L141.34 61.84L141.50 60.38L141.50 58.62L141.34 57.16L141.03 55.97L140.56 55.06L139.94 54.44L137.59 53.97L133.53 53.66L127.75 53.50L120.25 53.50L114.56 53.50L110.69 53.50L108.62 53.50L108.38 53.50L108.03 53.66L107.59 53.97Z"/><path d="M148.44 80.06L148.06 80.44L147.78 82.09L147.59 85.03L147.50 89.25L147.50 94.75L147.66 99.03L147.97 102.09L148.44 103.94L149.06 104.56L150.53 105.03L152.84 105.34L156.00 105.50L160.00 105.50L163.12 105.44L165.38 105.31L166.75 105.12L167.25 104.88L167.72 104.59L168.16 104.28L168.56 103.94L168.94 103.56L169.22 101.91L169.41 98.97L169.50 94.75L169.50 89.25L169.41 85.03L169.22 82.09L168.94 80.44L168.56 80.06L167.16 79.78L164.72 79.59L161.25 79.50L156.75 79.50L153.31 79.50L150.94 79.50L149.62 79.50L149.38 79.50L149.09 79.59L148.78 79.78Z"/><path d="M90.31 122.81L89.19 123.69L88.34 124.66L87.78 125.72L87.50 126.88L87.50 128.12L87.72 129.28L88.16 130.34L88.81 131.31L89.69 132.19L90.59 132.84L91.53 133.28L92.50 133.50L93.50 133.50L94.38 133.44L95.12 133.31L95.75 133.12L96.25 132.88L96.72 132.53L97.16 132.09L97.56 131.56L97.94 130.94L98.22 130.16L98.41 129.22L98.50 128.12L98.50 126.88L98.34 125.78L98.03 124.84L97.56 124.06L96.94 123.44L96.28 122.91L95.59 122.47L94.88 122.12L94.12 121.88L93.50 121.69L93.00 121.56L92.62 121.50L92.38 121.50L91.91 121.72L91.22 122.16Z"/><path d="M112.06 55.81L112.44 55.69L112.84 55.66L113.28 55.72L113.75 55.88L114.25 56.12L114.72 56.47L115.16 56.91L115.56 57.44L115.94 58.06L116.06 58.75L115.94 59.50L115.56 60.31L114.94 61.19L114.28 61.84L113.59 62.28L112.88 62.50L112.12 62.50L111.47 62.41L110.91 62.22L110.44 61.94L110.06 61.56L109.78 61.03L109.59 60.34L109.50 59.50L109.50 58.50L109.59 57.72L109.78 57.16L110.06 56.81L110.44 56.69L110.75 56.56L111.00 56.44L111.19 56.31L111.31 56.19L111.50 56.06L111.75 55.94Z"/><path d="M134.69 55.81L134.81 55.69L135.12 55.75L135.62 56.00L136.31 56.44L137.19 57.06L137.84 57.66L138.28 58.22L138.50 58.75L138.50 59.25L138.41 59.78L138.22 60.34L137.94 60.94L137.56 61.56L137.03 62.03L136.34 62.34L135.50 62.50L134.50 62.50L133.66 62.41L132.97 62.22L132.44 61.94L132.06 61.56L131.78 61.09L131.59 60.53L131.50 59.88L131.50 59.12L131.66 58.47L131.97 57.91L132.44 57.44L133.06 57.06L133.56 56.75L133.94 56.50L134.19 56.31L134.31 56.19L134.44 56.06L134.56 55.94Z"/><path d="M120.06 83.81L124.44 83.69L127.88 83.75L130.38 84.00L131.94 84.44L132.56 85.06L133.03 86.66L133.34 89.22L133.50 92.75L133.50 97.25L133.34 100.78L133.03 103.34L132.56 104.94L131.94 105.56L130.41 106.03L127.97 106.34L124.62 106.50L120.38 106.50L117.03 106.34L114.59 106.03L113.06 105.56L112.44 104.94L111.97 103.34L111.66 100.78L111.50 97.25L111.50 92.75L111.59 89.28L111.78 86.84L112.06 85.44L112.44 85.06L112.75 84.75L113.00 84.50L113.19 84.31L113.31 84.19L114.50 84.06L116.75 83.94Z"/><path d="M76.44 80.06L76.06 80.44L75.78 82.09L75.59 85.03L75.50 89.25L75.50 94.75L75.59 98.97L75.78 101.91L76.06 103.56L76.44 103.94L77.91 104.22L80.47 104.41L84.12 104.50L88.88 104.50L92.47 102.97L94.91 99.91L96.19 95.31L96.31 89.19L95.25 84.56L93.00 81.44L89.56 79.81L84.94 79.69L81.41 79.59L78.97 79.53L77.62 79.50L77.38 79.50L77.09 79.59L76.78 79.78Z"/><path d="M87.69 191.56L86.81 192.94L86.19 194.06L85.81 194.94L85.69 195.56L85.81 195.94L90.81 196.19L100.69 196.31L115.44 196.31L135.06 196.19L149.66 195.84L159.22 195.28L163.75 194.50L163.25 193.50L162.72 192.59L162.16 191.78L161.56 191.06L160.94 190.44L156.09 189.97L147.03 189.66L133.75 189.50L116.25 189.50L103.06 189.50L94.19 189.50L89.62 189.50L89.38 189.50L88.97 189.84L88.41 190.53Z"/><path d="M117.19 148.81L128.31 148.69L136.69 149.12L142.31 150.12L145.19 151.69L145.31 153.81L142.62 155.44L137.12 156.56L128.81 157.19L117.69 157.31L109.31 156.94L103.69 156.06L100.81 154.69L100.69 152.81L100.59 151.34L100.53 150.28L100.50 149.62L100.50 149.38L103.28 149.16L108.84 148.97Z"/></g></svg>`,
    trolley: `<svg class="mode" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 250 250" role="img" aria-label="SEPTA Trolley"><circle cx="125" cy="125" r="125" fill="#231F20"/><g fill="#fff" fill-rule="evenodd"><path d="M119.31 15.81L127.19 15.69L133.16 15.66L137.22 15.72L139.38 15.88L139.62 16.12L140.12 16.31L140.88 16.44L141.88 16.50L143.12 16.50L144.12 16.56L144.88 16.69L145.38 16.88L145.62 17.12L146.00 17.31L146.50 17.44L147.12 17.50L147.88 17.50L148.56 17.62L149.19 17.88L149.75 18.25L150.25 18.75L150.69 19.12L151.06 19.38L151.38 19.50L151.62 19.50L152.03 19.78L152.59 20.34L153.31 21.19L154.19 22.31L154.62 23.38L154.62 24.38L154.19 25.31L153.31 26.19L152.53 26.84L151.84 27.28L151.25 27.50L150.75 27.50L150.19 27.38L149.56 27.12L148.88 26.75L148.12 26.25L147.19 25.81L146.06 25.44L144.75 25.12L143.25 24.88L142.06 24.62L141.19 24.38L140.62 24.12L140.38 23.88L139.31 23.62L137.44 23.38L134.75 23.12L131.25 22.88L128.59 22.97L126.78 23.41L125.81 24.19L125.69 25.31L125.72 26.28L125.91 27.09L126.25 27.75L126.75 28.25L127.12 29.00L127.38 30.00L127.50 31.25L127.50 32.75L127.38 33.94L127.12 34.81L126.75 35.38L126.25 35.62L125.88 36.44L125.62 37.81L125.50 39.75L125.50 42.25L125.91 44.16L126.72 45.47L127.94 46.19L129.56 46.31L130.84 46.47L131.78 46.66L132.38 46.88L132.62 47.12L134.06 47.38L136.69 47.62L140.50 47.88L145.50 48.12L149.31 48.38L151.94 48.62L153.38 48.88L153.62 49.12L154.12 49.31L154.88 49.44L155.88 49.50L157.12 49.50L158.12 49.56L158.88 49.69L159.38 49.88L159.62 50.12L160.06 50.31L160.69 50.44L161.50 50.50L162.50 50.50L163.31 50.56L163.94 50.69L164.38 50.88L164.62 51.12L165.19 51.38L166.06 51.62L167.25 51.88L168.75 52.12L170.25 52.50L171.75 53.00L173.25 53.62L174.75 54.38L176.09 55.16L177.28 55.97L178.31 56.81L179.19 57.69L179.97 58.91L180.66 60.47L181.25 62.38L181.75 64.62L174.78 66.34L160.34 67.53L138.44 68.19L109.06 68.31L87.00 68.19L72.25 67.81L64.81 67.19L64.69 66.31L64.66 65.59L64.72 65.03L64.88 64.62L65.12 64.38L65.31 64.00L65.44 63.50L65.50 62.88L65.50 62.12L65.62 61.31L65.88 60.44L66.25 59.50L66.75 58.50L67.53 57.47L68.59 56.41L69.94 55.31L71.56 54.19L72.91 53.34L73.97 52.78L74.75 52.50L75.25 52.50L75.88 52.38L76.62 52.12L77.50 51.75L78.50 51.25L79.44 50.88L80.31 50.62L81.12 50.50L81.88 50.50L82.50 50.44L83.00 50.31L83.38 50.12L83.62 49.88L84.12 49.69L84.88 49.56L85.88 49.50L87.12 49.50L88.12 49.44L88.88 49.31L89.38 49.12L89.62 48.88L91.38 48.62L94.62 48.38L99.38 48.12L105.62 47.88L110.38 47.62L113.62 47.38L115.38 47.12L115.62 46.88L116.06 46.69L116.69 46.56L117.50 46.50L118.50 46.50L119.34 46.41L120.03 46.22L120.56 45.94L120.94 45.56L121.22 44.78L121.41 43.59L121.50 42.00L121.50 40.00L121.31 38.38L120.94 37.12L120.38 36.25L119.62 35.75L119.06 35.00L118.69 34.00L118.50 32.75L118.50 31.25L118.69 30.00L119.06 29.00L119.62 28.25L120.38 27.75L120.94 27.19L121.31 26.56L121.50 25.88L121.50 25.12L121.41 24.47L121.22 23.91L120.94 23.44L120.56 23.06L120.09 22.78L119.53 22.59L118.88 22.50L118.12 22.50L117.50 22.56L117.00 22.69L116.62 22.88L116.38 23.12L115.62 23.31L114.38 23.44L112.62 23.50L110.38 23.50L108.62 23.56L107.38 23.69L106.62 23.88L106.38 24.12L105.88 24.38L105.12 24.62L104.12 24.88L102.88 25.12L101.75 25.44L100.75 25.81L99.88 26.25L99.12 26.75L98.44 27.12L97.81 27.38L97.25 27.50L96.75 27.50L96.22 27.34L95.66 27.03L95.06 26.56L94.44 25.94L93.97 25.34L93.66 24.78L93.50 24.25L93.50 23.75L93.84 23.03L94.53 22.09L95.56 20.94L96.94 19.56L98.09 18.53L99.03 17.84L99.75 17.50L100.25 17.50L100.69 17.44L101.06 17.31L101.38 17.12L101.62 16.88L102.12 16.69L102.88 16.56L103.88 16.50L105.12 16.50L106.09 16.47L106.78 16.41L107.19 16.31L107.31 16.19L109.38 16.06L113.38 15.94Z"/><path d="M82.69 177.81L84.81 177.69L86.47 177.78L87.66 178.09L88.38 178.62L88.62 179.38L93.06 179.94L101.69 180.31L114.50 180.50L131.50 180.50L144.25 180.31L152.75 179.94L157.00 179.38L157.00 178.62L157.56 178.06L158.69 177.69L160.38 177.50L162.62 177.50L164.44 177.69L165.81 178.06L166.75 178.62L167.25 179.38L168.00 179.94L169.00 180.31L170.25 180.50L171.75 180.50L172.97 180.59L173.91 180.78L174.56 181.06L174.94 181.44L175.28 181.91L175.59 182.47L175.88 183.12L176.12 183.88L176.50 184.69L177.00 185.56L177.62 186.50L178.38 187.50L178.56 188.31L178.19 188.94L177.25 189.38L175.75 189.62L174.75 190.12L174.25 190.88L174.25 191.88L174.75 193.12L175.22 194.16L175.66 194.97L176.06 195.56L176.44 195.94L177.16 196.22L178.22 196.41L179.62 196.50L181.38 196.50L182.91 196.91L184.22 197.72L185.31 198.94L186.19 200.56L186.97 201.91L187.66 202.97L188.25 203.75L188.75 204.25L189.19 204.75L189.56 205.25L189.88 205.75L190.12 206.25L190.28 206.72L190.34 207.16L190.31 207.56L190.19 207.94L189.69 208.25L188.81 208.50L187.56 208.69L185.94 208.81L185.09 209.53L185.03 210.84L185.75 212.75L187.25 215.25L187.28 217.16L185.84 218.47L182.94 219.19L178.56 219.31L175.00 218.88L172.25 217.88L170.31 216.31L169.19 214.19L168.31 212.44L167.69 211.06L167.31 210.06L167.19 209.44L161.59 208.97L150.53 208.66L134.00 208.50L112.00 208.50L95.22 209.09L83.66 210.28L77.31 212.06L76.19 214.44L75.25 216.31L74.50 217.69L73.94 218.56L73.56 218.94L72.28 219.22L70.09 219.41L67.00 219.50L63.00 219.50L59.97 219.41L57.91 219.22L56.81 218.94L56.69 218.56L56.72 218.03L56.91 217.34L57.25 216.50L57.75 215.50L58.25 214.62L58.75 213.88L59.25 213.25L59.75 212.75L60.19 212.19L60.56 211.56L60.88 210.88L61.12 210.12L60.91 209.53L60.22 209.09L59.06 208.81L57.44 208.69L56.19 208.56L55.31 208.44L54.81 208.31L54.69 208.19L54.72 207.84L54.91 207.28L55.25 206.50L55.75 205.50L56.47 204.28L57.41 202.84L58.56 201.19L59.94 199.31L61.44 197.88L63.06 196.88L64.81 196.31L66.69 196.19L68.22 195.84L69.41 195.28L70.25 194.50L70.75 193.50L71.12 192.62L71.38 191.88L71.50 191.25L71.50 190.75L71.22 190.34L70.66 190.03L69.81 189.81L68.69 189.69L67.81 189.50L67.19 189.25L66.81 188.94L66.69 188.56L66.78 188.03L67.09 187.34L67.62 186.50L68.38 185.50L69.00 184.56L69.50 183.69L69.88 182.88L70.12 182.12L70.78 181.53L71.84 181.09L73.31 180.81L75.19 180.69L76.66 180.47L77.72 180.16L78.38 179.75L78.62 179.25L78.84 178.84L79.03 178.53L79.19 178.31L79.31 178.19L79.94 178.06L81.06 177.94Z"/><path d="M108.56 72.81L137.94 72.69L160.00 77.06L174.75 85.94L182.19 99.31L182.31 117.19L182.03 131.28L181.34 141.59L180.25 148.12L178.75 150.88L177.62 153.06L176.88 154.69L176.50 155.75L176.50 156.25L176.19 157.25L175.56 158.75L174.62 160.75L173.38 163.25L172.16 165.16L170.97 166.47L169.81 167.19L168.69 167.31L167.78 167.72L167.09 168.41L166.62 169.38L166.38 170.62L165.75 171.56L164.75 172.19L163.38 172.50L161.62 172.50L160.28 171.97L159.34 170.91L158.81 169.31L158.69 167.19L158.31 165.56L157.69 164.44L156.81 163.81L155.69 163.69L154.50 163.12L153.25 162.12L151.94 160.69L150.56 158.81L149.53 156.84L148.84 154.78L148.50 152.62L148.50 150.38L148.06 148.62L147.19 147.38L145.88 146.62L144.12 146.38L142.81 142.19L141.94 134.06L141.50 122.00L141.50 106.00L141.34 93.84L141.03 85.53L140.56 81.06L139.94 80.44L137.53 79.97L133.34 79.66L127.38 79.50L119.62 79.50L113.66 79.59L109.47 79.78L107.06 80.06L106.44 80.44L105.97 84.78L105.66 93.09L105.50 105.38L105.50 121.62L105.06 133.88L104.19 142.12L102.88 146.38L101.12 146.62L99.81 147.31L98.94 148.44L98.50 150.00L98.50 152.00L98.16 154.03L97.47 156.09L96.44 158.19L95.06 160.31L93.75 161.94L92.50 163.06L91.31 163.69L90.19 163.81L89.34 164.41L88.78 165.47L88.50 167.00L88.50 169.00L88.03 170.53L87.09 171.59L85.69 172.19L83.81 172.31L82.38 172.12L81.38 171.62L80.81 170.81L80.69 169.69L80.31 168.81L79.69 168.19L78.81 167.81L77.69 167.69L76.75 167.50L76.00 167.25L75.44 166.94L75.06 166.56L74.72 166.03L74.41 165.34L74.12 164.50L73.88 163.50L73.12 161.62L71.88 158.88L70.12 155.25L67.88 150.75L66.19 143.00L65.06 132.00L64.50 117.75L64.50 100.25L64.50 87.06L64.50 78.19L64.50 73.62L64.50 73.38L71.84 73.16L86.53 72.97Z"/><path d="M149.44 55.06L149.06 55.44L148.81 56.31L148.69 57.69L148.69 59.56L148.81 61.94L150.09 63.72L152.53 64.91L156.12 65.50L160.88 65.50L164.53 65.41L167.09 65.22L168.56 64.94L168.94 64.56L169.22 64.03L169.41 63.34L169.50 62.50L169.50 61.50L169.41 60.59L169.22 59.78L168.94 59.06L168.56 58.44L168.16 57.97L167.72 57.66L167.25 57.50L166.75 57.50L166.12 57.38L165.38 57.12L164.50 56.75L163.50 56.25L162.56 55.88L161.69 55.62L160.88 55.50L160.12 55.50L159.50 55.44L159.00 55.31L158.62 55.12L158.38 54.88L157.75 54.69L156.75 54.56L155.38 54.50L153.62 54.50L152.25 54.50L151.25 54.50L150.62 54.50L150.38 54.50L150.09 54.59L149.78 54.78Z"/><path d="M149.69 122.44L148.81 123.06L148.09 123.66L147.53 124.22L147.12 124.75L146.88 125.25L146.69 125.81L146.56 126.44L146.50 127.12L146.50 127.88L146.66 128.66L146.97 129.47L147.44 130.31L148.06 131.19L148.66 131.91L149.22 132.47L149.75 132.88L150.25 133.12L150.81 133.31L151.44 133.44L152.12 133.50L152.88 133.50L153.66 133.34L154.47 133.03L155.31 132.56L156.19 131.94L156.91 131.34L157.47 130.78L157.88 130.25L158.12 129.75L158.31 129.19L158.44 128.56L158.50 127.88L158.50 127.12L158.34 126.34L158.03 125.53L157.56 124.69L156.94 123.81L156.22 123.09L155.41 122.53L154.50 122.12L153.50 121.88L152.69 121.69L152.06 121.56L151.62 121.50L151.38 121.50L150.97 121.66L150.41 121.97Z"/><path d="M89.62 54.88L89.38 55.12L88.94 55.31L88.31 55.44L87.50 55.50L86.50 55.50L85.69 55.56L85.06 55.69L84.62 55.88L84.38 56.12L83.88 56.38L83.12 56.62L82.12 56.88L80.88 57.12L79.84 57.41L79.03 57.72L78.44 58.06L78.06 58.44L77.78 59.09L77.59 60.03L77.50 61.25L77.50 62.75L78.78 63.91L81.34 64.72L85.19 65.19L90.31 65.31L94.19 64.81L96.81 63.69L98.19 61.94L98.31 59.56L98.31 57.69L98.19 56.31L97.94 55.44L97.56 55.06L96.91 54.78L95.97 54.59L94.75 54.50L93.25 54.50L92.06 54.50L91.19 54.50L90.62 54.50L90.38 54.50L90.12 54.56L89.88 54.69Z"/><path d="M107.06 54.44L106.44 55.06L105.97 55.91L105.66 56.97L105.50 58.25L105.50 59.75L105.56 61.00L105.69 62.00L105.88 62.75L106.12 63.25L106.47 63.72L106.91 64.16L107.44 64.56L108.06 64.94L110.41 65.22L114.47 65.41L120.25 65.50L127.75 65.50L133.53 65.34L137.59 65.03L139.94 64.56L140.56 63.94L141.03 63.03L141.34 61.84L141.50 60.38L141.50 58.62L141.34 57.16L141.03 55.97L140.56 55.06L139.94 54.44L137.59 53.97L133.53 53.66L127.75 53.50L120.25 53.50L114.56 53.50L110.69 53.50L108.62 53.50L108.38 53.50L108.03 53.66L107.59 53.97Z"/><path d="M148.44 80.06L148.06 80.44L147.78 82.09L147.59 85.03L147.50 89.25L147.50 94.75L147.66 99.03L147.97 102.09L148.44 103.94L149.06 104.56L150.53 105.03L152.84 105.34L156.00 105.50L160.00 105.50L163.12 105.44L165.38 105.31L166.75 105.12L167.25 104.88L167.72 104.59L168.16 104.28L168.56 103.94L168.94 103.56L169.22 101.91L169.41 98.97L169.50 94.75L169.50 89.25L169.41 85.03L169.22 82.09L168.94 80.44L168.56 80.06L167.16 79.78L164.72 79.59L161.25 79.50L156.75 79.50L153.31 79.50L150.94 79.50L149.62 79.50L149.38 79.50L149.09 79.59L148.78 79.78Z"/><path d="M90.31 122.81L89.19 123.69L88.34 124.66L87.78 125.72L87.50 126.88L87.50 128.12L87.72 129.28L88.16 130.34L88.81 131.31L89.69 132.19L90.59 132.84L91.53 133.28L92.50 133.50L93.50 133.50L94.38 133.44L95.12 133.31L95.75 133.12L96.25 132.88L96.72 132.53L97.16 132.09L97.56 131.56L97.94 130.94L98.22 130.16L98.41 129.22L98.50 128.12L98.50 126.88L98.34 125.78L98.03 124.84L97.56 124.06L96.94 123.44L96.28 122.91L95.59 122.47L94.88 122.12L94.12 121.88L93.50 121.69L93.00 121.56L92.62 121.50L92.38 121.50L91.91 121.72L91.22 122.16Z"/><path d="M112.06 55.81L112.44 55.69L112.84 55.66L113.28 55.72L113.75 55.88L114.25 56.12L114.72 56.47L115.16 56.91L115.56 57.44L115.94 58.06L116.06 58.75L115.94 59.50L115.56 60.31L114.94 61.19L114.28 61.84L113.59 62.28L112.88 62.50L112.12 62.50L111.47 62.41L110.91 62.22L110.44 61.94L110.06 61.56L109.78 61.03L109.59 60.34L109.50 59.50L109.50 58.50L109.59 57.72L109.78 57.16L110.06 56.81L110.44 56.69L110.75 56.56L111.00 56.44L111.19 56.31L111.31 56.19L111.50 56.06L111.75 55.94Z"/><path d="M134.69 55.81L134.81 55.69L135.12 55.75L135.62 56.00L136.31 56.44L137.19 57.06L137.84 57.66L138.28 58.22L138.50 58.75L138.50 59.25L138.41 59.78L138.22 60.34L137.94 60.94L137.56 61.56L137.03 62.03L136.34 62.34L135.50 62.50L134.50 62.50L133.66 62.41L132.97 62.22L132.44 61.94L132.06 61.56L131.78 61.09L131.59 60.53L131.50 59.88L131.50 59.12L131.66 58.47L131.97 57.91L132.44 57.44L133.06 57.06L133.56 56.75L133.94 56.50L134.19 56.31L134.31 56.19L134.44 56.06L134.56 55.94Z"/><path d="M120.06 83.81L124.44 83.69L127.88 83.75L130.38 84.00L131.94 84.44L132.56 85.06L133.03 86.66L133.34 89.22L133.50 92.75L133.50 97.25L133.34 100.78L133.03 103.34L132.56 104.94L131.94 105.56L130.41 106.03L127.97 106.34L124.62 106.50L120.38 106.50L117.03 106.34L114.59 106.03L113.06 105.56L112.44 104.94L111.97 103.34L111.66 100.78L111.50 97.25L111.50 92.75L111.59 89.28L111.78 86.84L112.06 85.44L112.44 85.06L112.75 84.75L113.00 84.50L113.19 84.31L113.31 84.19L114.50 84.06L116.75 83.94Z"/><path d="M76.44 80.06L76.06 80.44L75.78 82.09L75.59 85.03L75.50 89.25L75.50 94.75L75.59 98.97L75.78 101.91L76.06 103.56L76.44 103.94L77.91 104.22L80.47 104.41L84.12 104.50L88.88 104.50L92.47 102.97L94.91 99.91L96.19 95.31L96.31 89.19L95.25 84.56L93.00 81.44L89.56 79.81L84.94 79.69L81.41 79.59L78.97 79.53L77.62 79.50L77.38 79.50L77.09 79.59L76.78 79.78Z"/><path d="M87.69 191.56L86.81 192.94L86.19 194.06L85.81 194.94L85.69 195.56L85.81 195.94L90.81 196.19L100.69 196.31L115.44 196.31L135.06 196.19L149.66 195.84L159.22 195.28L163.75 194.50L163.25 193.50L162.72 192.59L162.16 191.78L161.56 191.06L160.94 190.44L156.09 189.97L147.03 189.66L133.75 189.50L116.25 189.50L103.06 189.50L94.19 189.50L89.62 189.50L89.38 189.50L88.97 189.84L88.41 190.53Z"/><path d="M117.19 148.81L128.31 148.69L136.69 149.12L142.31 150.12L145.19 151.69L145.31 153.81L142.62 155.44L137.12 156.56L128.81 157.19L117.69 157.31L109.31 156.94L103.69 156.06L100.81 154.69L100.69 152.81L100.59 151.34L100.53 150.28L100.50 149.62L100.50 149.38L103.28 149.16L108.84 148.97Z"/></g></svg>`,
    walk: circleIcon(`<circle cx="13.1" cy="7.05" r="1.35" fill="#fff"/><path fill="#fff" d="M12.2 9.1 9.4 11.2l.85 1.05 1.7-1.25v2.55l-2.35 4.05 1.2.7 1.85-3.2 1.55 3.2 1.2-.7-2.05-4.3.25-2.35 1.7 1.4.85-1.1-2.95-2.25z"/>`),
    status: circleIcon(`<path fill="#fff" d="M12 6.2 17.6 16.4H6.4L12 6.2z"/><rect x="11.35" y="9.5" width="1.3" height="3.4" rx="0.4" fill="#231f20"/><circle cx="12" cy="14.35" r="0.7" fill="#231f20"/>`),
    map: circleIcon(`<path fill="#fff" d="M8.2 6.6 12 8.1l3.8-1.5 2.4 1.1v9.7l-2.4-1.1-3.8 1.5-3.8-1.5-2.4 1.1V7.7l2.4-1.1z"/>`),
  };

  function modeIcon(kind) {
    return MODE_SVG[kind] || MODE_SVG.rail;
  }

  function bullet(letter) {
    const c = LINE[letter] || { bg: "#333", fg: "#fff" };
    return `<span class="bullet" style="background:${c.bg};color:${c.fg}">${esc(letter)}</span>`;
  }

  function bulletRow(letters) {
    if (!letters || !letters.length) return "";
    return `<span class="bullets">${letters.map(bullet).join("")}</span>`;
  }

  function pill(text) {
    if (!text) return "";
    return `<span class="pill">${esc(text)}</span>`;
  }

  const BASE_CSS = `
    :host { display: block; }
    ha-card {
      background: var(--ha-card-background, var(--card-background-color, #171d27));
      color: var(--primary-text-color, #e8edf4);
      overflow: hidden;
    }
    .wrap { padding: 18px 20px 20px; font-family: var(--ha-font-family-body, IBM Plex Sans, system-ui, sans-serif); }
    .kicker { font-size: 11px; letter-spacing: 0.16em; text-transform: uppercase; opacity: 0.55; font-weight: 500; }
    .row { display: flex; justify-content: space-between; align-items: flex-end; gap: 12px; margin-top: 8px; }
    .clock { font-size: 32px; font-variant-numeric: tabular-nums; font-weight: 500; letter-spacing: -0.03em; line-height: 1; }
    .mins { font-size: 20px; font-variant-numeric: tabular-nums; font-weight: 500; }
    .meta { margin-top: 8px; font-size: 13px; opacity: 0.75; }
    .empty { padding: 8px 0 2px; font-size: 14px; opacity: 0.7; }
    button.hit {
      display: block; width: 100%; text-align: left; background: none; border: 0; color: inherit;
      font: inherit; cursor: pointer;
    }
    button.hit.cell { padding: 16px 18px; }
    button.hit.bubble { padding: 16px 18px 14px; }
    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1px;
      background: var(--divider-color, rgba(127,127,127,0.25));
    }
    .cell { background: var(--ha-card-background, var(--card-background-color, #171d27)); padding: 16px 18px; }
    .cell.wide { grid-column: 1 / -1; }
    .head { display: flex; justify-content: space-between; align-items: center; padding: 16px 18px 8px; }
    .status { font-size: 12px; font-weight: 500; }
    .hint { margin-top: 4px; font-size: 12px; opacity: 0.6; }
    .label { font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; opacity: 0.5; }
    .bubbles { display: flex; flex-wrap: wrap; gap: 10px; padding: 8px 16px 18px; }
    .bubble {
      flex: 1 1 138px;
      min-height: 84px;
      border-radius: 18px;
      background: #12171f;
      box-shadow: inset 0 0 0 1px #2a3340;
      padding: 16px 18px 14px;
      text-align: left;
      color: inherit;
      cursor: pointer;
      font: inherit;
      border: 0;
    }
    .bubble.is-hero { flex: 1 1 100%; min-height: 108px; border-radius: 22px; }
    .bubble.is-map { flex: 1 1 100%; min-height: 200px; padding: 0; overflow: hidden; cursor: default; }
    .bubble .value { font-size: 22px; font-variant-numeric: tabular-nums; font-weight: 500; letter-spacing: -0.03em; margin-top: 4px; }
    .bubble.is-hero .value { font-size: 32px; }
    .bubble-map { width: 100%; height: 200px; border: 0; display: block; background: #0b0e13; }
    .map-host { position: relative; width: 100%; height: 280px; background: #0b0e13; overflow: hidden; touch-action: none; }
    .bubble.is-map .map-host, .map-host.is-bubble { height: 200px; }
    .osm-wrap { position: absolute; inset: 0; cursor: grab; }
    .osm-wrap.is-drag { cursor: grabbing; }
    .osm-tiles, .osm-marks { position: absolute; inset: 0; overflow: hidden; }
    .osm-tiles img { position: absolute; width: 256px; height: 256px; max-width: none; user-select: none; pointer-events: none; display: block; }
    .osm-wrap.is-dark .osm-tiles img { filter: invert(1) hue-rotate(180deg) brightness(0.95) contrast(0.92); }
    .osm-mark {
      position: absolute; transform: translate(-50%, -50%);
      min-width: 22px; height: 18px; padding: 0 5px; z-index: 1;
      border-radius: 3px; font-size: 10px; font-weight: 700; line-height: 1;
      color: #fff; display: flex; align-items: center; justify-content: center;
      box-shadow: 0 1px 4px rgba(0,0,0,0.45); cursor: pointer; white-space: nowrap;
      border: 0; font-family: inherit;
    }
    .osm-mark.is-home {
      width: 12px; height: 12px; min-width: 12px; padding: 0; border-radius: 50%;
      background: #7aa2ce; box-shadow: 0 0 0 3px rgba(122,162,206,0.35);
    }
    .osm-mark.is-metro { width: 18px; height: 18px; min-width: 18px; padding: 0; border-radius: 2px; transform: translate(-50%, -50%) rotate(45deg); }
    .osm-mark.is-metro span { transform: rotate(-45deg); font-size: 9px; }
    .osm-pop {
      position: absolute; left: 8px; right: 8px; bottom: 8px; z-index: 3;
      background: #171d27; color: #e8edf4; border-radius: 10px;
      padding: 8px 10px; font-size: 12px; line-height: 1.35;
      box-shadow: 0 0 0 1px #2a3340;
    }
    .osm-pop .k { font-size: 10px; letter-spacing: 0.12em; text-transform: uppercase; opacity: 0.55; }
    .osm-pop .t { font-weight: 600; margin-top: 2px; }
    .osm-pop .m { opacity: 0.7; margin-top: 2px; }
    .osm-zoom {
      position: absolute; top: 8px; right: 8px; display: flex; flex-direction: column; gap: 4px; z-index: 2;
    }
    .osm-zoom button {
      width: 32px; height: 32px; border: 0; border-radius: 6px;
      background: #171d27; color: #e8edf4; box-shadow: 0 0 0 1px #2a3340;
      cursor: pointer; font-size: 16px; line-height: 1;
    }
    .osm-count {
      position: absolute; left: 8px; top: 8px; z-index: 2;
      background: rgba(23,29,39,0.88); color: #8b96a8; font-size: 11px;
      padding: 4px 8px; border-radius: 6px;
    }
    .osm-attr {
      position: absolute; right: 8px; bottom: 8px; z-index: 2;
      font-size: 9px; color: #8b96a8; background: rgba(11,14,19,0.72); padding: 2px 6px; border-radius: 4px;
    }
    .stack { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; padding: 12px 16px 18px; }
    .stack .bubble { min-width: 0; }
    .mode {
      width: 28px; height: 28px; display: block; flex-shrink: 0;
      object-fit: contain; border-radius: 50%;
    }
    .bubble .mode { width: 26px; height: 26px; }
    .title-row {
      display: flex; align-items: center; justify-content: space-between; gap: 8px;
    }
    .title-row .left { display: flex; align-items: center; gap: 8px; min-width: 0; }
    .bullets { display: inline-flex; gap: 3px; flex-shrink: 0; }
    .bullet {
      display: inline-flex; align-items: center; justify-content: center;
      width: 20px; height: 20px; border-radius: 2px;
      font-family: Roboto, IBM Plex Sans, system-ui, sans-serif;
      font-weight: 700; font-size: 12px; line-height: 1;
    }
    .pill {
      display: inline-flex; align-items: center; justify-content: center;
      height: 18px; padding: 0 8px; border-radius: 999px;
      background: #111; color: #fff; font-size: 11px; font-weight: 700; letter-spacing: 0.02em;
    }
    .kicker-row { display: flex; align-items: center; gap: 8px; }
    .dep { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: var(--divider-color, rgba(127,127,127,0.25)); }
    .dep-col { background: var(--ha-card-background, var(--card-background-color, #171d27)); padding: 4px 0 8px; }
    .dep-head { display: flex; align-items: center; justify-content: space-between; padding: 16px 18px 8px; }
    .dep-row {
      display: grid; grid-template-columns: 4.6rem minmax(0,1fr) 1.7rem auto;
      gap: 10px; align-items: center; padding: 12px 18px;
    }
    .dep-row + .dep-row { box-shadow: 0 -1px 0 var(--divider-color, rgba(127,127,127,0.2)); }
    .dep-time { font-variant-numeric: tabular-nums; font-weight: 500; font-size: 14px; }
    .dep-dest { min-width: 0; }
    .dep-dest .to { display: flex; align-items: center; gap: 6px; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .dep-dest .id { display: block; font-size: 11px; opacity: 0.55; }
    .dep-trk {
      display: inline-flex; align-items: center; justify-content: center;
      width: 22px; height: 22px; border-radius: 2px; background: #e8edf4; color: #12171f;
      font-size: 11px; font-weight: 700; font-variant-numeric: tabular-nums;
    }
    .dep-trk.is-empty { background: transparent; color: var(--secondary-text-color, #8b93a1); }
    .dep-mins { font-size: 12px; font-variant-numeric: tabular-nums; font-weight: 500; text-align: right; white-space: nowrap; }
    .dep-toolbar { display: flex; flex-wrap: wrap; gap: 10px; padding: 0 18px 12px; }
    .dep-toolbar label { display: flex; flex-direction: column; gap: 4px; min-width: 140px; flex: 1; }
    .dep-toolbar span { font-size: 10px; letter-spacing: 0.12em; text-transform: uppercase; opacity: 0.55; }
    .dep-toolbar select {
      height: 36px; border-radius: 6px; border: 1px solid var(--divider-color, rgba(127,127,127,0.35));
      background: var(--secondary-background-color, #11161e); color: inherit; padding: 0 10px; font-size: 13px;
    }
    .dep-cols,
    button.hit.dep-cols {
      display: grid;
      grid-template-columns: 4.5rem minmax(0, 1fr) 5.75rem 5.6rem;
      gap: 12px;
      align-items: center;
      padding: 10px 18px;
    }
    .dep-cols > *,
    button.hit.dep-cols > * { min-width: 0; }
    .dep-cols.is-head {
      font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase; opacity: 0.5; font-weight: 600;
    }
    .dep-cols.is-head > :nth-child(3) { text-align: center; }
    .dep-cols.is-head > :nth-child(4) { text-align: right; }
    .dep-cols.is-row { padding-top: 8px; padding-bottom: 8px; }
    .dep-cols.is-row + .dep-cols.is-row { box-shadow: 0 -1px 0 var(--divider-color, rgba(127,127,127,0.2)); }
    .dep-plat { display: flex; width: 100%; justify-content: center; }
    .dep-expect { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; text-align: right; }
    .dep-expect .late { font-size: 11px; }
    .size-pills { display: flex; gap: 6px; padding: 0 18px 12px; }
    .size-pills button {
      height: 28px; padding: 0 10px; border-radius: 999px; border: 1px solid var(--divider-color, rgba(127,127,127,0.35));
      background: transparent; color: inherit; font-size: 11px; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase;
    }
    .size-pills button.on { background: var(--secondary-background-color, #11161e); border-color: transparent; }
    .dep-card.is-compact .dep-cols,
    .dep-card.is-compact button.hit.dep-cols { padding: 10px 16px; grid-template-columns: 3.6rem minmax(0,1fr) 4.75rem 4.6rem; gap: 10px; }
    .dep-card.is-compact .dep-cols.is-head { letter-spacing: 0.08em; }
    .dep-card.is-compact .dep-time { font-size: 12px; }
    .dep-card.is-compact .dep-dest .to { font-size: 12px; }
    .dep-card.is-compact .dep-trk { width: 18px; height: 18px; font-size: 10px; }
    .dep-card.is-compact .dep-toolbar select { height: 32px; }
    .dep-card.is-compact .head { padding-bottom: 2px; }
    .dep-card.is-large .dep-cols,
    .dep-card.is-large button.hit.dep-cols { padding: 14px 20px; grid-template-columns: 5.4rem minmax(0,1fr) 5.75rem 6.2rem; }
    .dep-card.is-large .dep-time { font-size: 20px; }
    .dep-card.is-large .dep-dest .to { font-size: 15px; }
    .dep-card.is-large .dep-trk { width: 28px; height: 28px; font-size: 12px; }
    .dep-card { container-type: inline-size; }
    @container (max-width: 460px) {
      .dep-cols,
      button.hit.dep-cols,
      .dep-card.is-compact .dep-cols,
      .dep-card.is-compact button.hit.dep-cols,
      .dep-card.is-large .dep-cols,
      .dep-card.is-large button.hit.dep-cols {
        grid-template-columns: 3.3rem minmax(0,1fr) 4.75rem 4.4rem;
        gap: 8px;
        padding-left: 16px;
        padding-right: 16px;
      }
      .dep-time { font-size: 13px; }
      .dep-expect, .dep-expect .late { font-size: 11px; line-height: 1.2; }
      .dep-toolbar label { min-width: 0; }
    }
    .bubble { min-width: 0; }
    .hero-grid { min-width: 0; }

    .rail-badge {
      display: inline-flex; align-items: center; justify-content: center;
      min-width: 34px; height: 18px; padding: 0 5px; border-radius: 3px;
      color: #fff; font-size: 10px; font-weight: 700; letter-spacing: 0.04em;
    }
    .bubble {
      display: block; width: 100%; text-align: left;
      min-height: 92px; padding: 16px 18px 14px;
      background: var(--secondary-background-color, rgba(18,23,31,0.55));
      border-radius: 16px;
      box-shadow: inset 0 0 0 1px var(--divider-color, rgba(127,127,127,0.22));
    }
    .bubble-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
    .bubble-clock-row { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; margin-top: 4px; }
    .bubble-clock {
      margin-top: 0;
      font-variant-numeric: tabular-nums;
      font-weight: 500;
      letter-spacing: -0.03em;
      white-space: nowrap;
    }
    .bubble-clock.is-lg { font-size: 30px; }
    .bubble-clock.is-sm { font-size: 20px; }
    .bubble { container-type: inline-size; }
    @container (max-width: 210px) {
      .bubble-clock.is-lg { font-size: 22px; }
      .bubble-clock.is-sm { font-size: 16px; }
    }
    .bubble-late { font-size: 12px; font-weight: 500; white-space: nowrap; }
    .bubble-hint { margin-top: 2px; font-size: 12px; opacity: 0.65; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .bubble-train.is-sm {
      margin-top: 8px; padding-top: 8px;
      box-shadow: 0 -1px 0 var(--divider-color, rgba(127,127,127,0.2));
    }
    .hero-grid {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      padding: 6px 16px 18px;
    }
    .hero-grid > .bubble {
      flex: 1 1 138px;
      min-width: 8.5rem;
      width: auto;
    }
    .board-wrap {
      background: var(--ha-card-background, var(--card-background-color, #171d27));
    }
    .board-bar {
      display: flex; flex-wrap: wrap; gap: 8px 14px;
      padding: 16px 18px 6px;
      font-size: 12px; opacity: 0.72;
    }
    @media (max-width: 640px) {
      .hero-grid { display: flex; }
    }
    @media (max-width: 420px) {
      .grid { grid-template-columns: 1fr; }
      .cell.wide { grid-column: auto; }
      .stack { grid-template-columns: 1fr; }
      .dep { grid-template-columns: 1fr; }
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

  const PHILLY = { lat: 40.037, lon: -75.171 };
  const OSM_TILE = "https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png";
  const ESRI_TILE = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}";

  function latLonToWorld(lat, lon, z) {
    const n = 256 * Math.pow(2, z);
    const x = ((Number(lon) + 180) / 360) * n;
    const rad = (Number(lat) * Math.PI) / 180;
    const sin = Math.min(0.9999, Math.max(-0.9999, Math.sin(rad)));
    const y = (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * n;
    return { x, y };
  }

  function worldToLatLon(x, y, z) {
    const n = 256 * Math.pow(2, z);
    const lon = (x / n) * 360 - 180;
    const n2 = Math.PI - (2 * Math.PI * y) / n;
    const lat = (180 / Math.PI) * Math.atan(Math.sinh(n2));
    return { lat, lon };
  }

  function mapPayload(state) {
    if (!state || !state.attributes) return { home: null, vehicles: [], count: 0, station: "" };
    const a = state.attributes;
    const vehicles = (Array.isArray(a.vehicles) ? a.vehicles : []).filter((v) => {
      if (!v) return false;
      const lat = Number(v.lat);
      const lon = Number(v.lon);
      return Number.isFinite(lat) && Number.isFinite(lon) && !(lat === 0 && lon === 0);
    });
    const lat = Number(a.home_lat);
    const lon = Number(a.home_lon);
    const home = Number.isFinite(lat) && Number.isFinite(lon) ? { lat, lon } : null;
    return { home, vehicles, count: vehicles.length, station: a.station || "" };
  }

  function vehicleColor(v) {
    const late = Number(v.late) || 0;
    if (late >= 10) return CRIT;
    if (late > 0) return LATE;
    const kind = String(v.kind || "");
    const line = String(v.line || "");
    if (kind === "bus") return "#c8102e";
    if (kind === "metro") {
      if (line.startsWith("L")) return "#1c9ad6";
      if (line.startsWith("B")) return "#f26100";
      if (line.startsWith("M")) return "#613393";
      return "#1c9ad6";
    }
    if (kind === "trolley") {
      if (line.startsWith("T")) return "#5a960a";
      if (line.startsWith("G")) return "#fcd602";
      if (line.startsWith("D")) return "#e5427b";
      return "#5a960a";
    }
    const code = railCode(line);
    return (code && RAIL[code]) || ONTIME;
  }

  function vehicleLabel(v) {
    const kind = String(v.kind || "");
    if (kind === "rail") return String(v.id || v.line || "RR").slice(0, 5);
    return String(v.line || v.id || "•").slice(0, 4);
  }

  function vehicleKindLabel(kind) {
    if (kind === "bus") return "Bus";
    if (kind === "metro") return "Metro";
    if (kind === "trolley") return "Trolley";
    return "Regional Rail";
  }

  function LiveOsmMap(host, opts) {
    this.host = host;
    this.dark = !opts || opts.dark !== false;
    this.z = 11;
    this.lat = PHILLY.lat;
    this.lon = PHILLY.lon;
    this.fitted = false;
    this.payload = { home: null, vehicles: [], count: 0, station: "" };
    this.drag = null;
    this.openId = "";
    host.innerHTML = `
      <div class="osm-wrap">
        <div class="osm-tiles"></div>
        <div class="osm-marks"></div>
        <div class="osm-count"></div>
        <div class="osm-zoom">
          <button type="button" data-z="1" aria-label="Zoom in">+</button>
          <button type="button" data-z="-1" aria-label="Zoom out">−</button>
        </div>
        <div class="osm-pop" hidden></div>
        <div class="osm-attr">© OpenStreetMap © CARTO</div>
      </div>
    `;
    this.wrap = host.querySelector(".osm-wrap");
    this.tiles = host.querySelector(".osm-tiles");
    this.marks = host.querySelector(".osm-marks");
    this.pop = host.querySelector(".osm-pop");
    this.countEl = host.querySelector(".osm-count");
    this._bind();
    this._ro = new ResizeObserver(() => this.draw());
    this._ro.observe(host);
  }

  LiveOsmMap.prototype._bind = function () {
    this.wrap.querySelectorAll(".osm-zoom button").forEach((btn) => {
      btn.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        this.setZoom(this.z + Number(btn.getAttribute("data-z")));
      });
    });
    this.wrap.addEventListener("pointerdown", (ev) => {
      if (ev.target.closest("button") && !ev.target.closest(".osm-mark")) return;
      if (ev.target.closest(".osm-mark")) return;
      this.drag = { x: ev.clientX, y: ev.clientY, lat: this.lat, lon: this.lon };
      this.wrap.classList.add("is-drag");
      try { this.wrap.setPointerCapture(ev.pointerId); } catch (e) { /* ignore */ }
    });
    this.wrap.addEventListener("pointermove", (ev) => {
      if (!this.drag) return;
      const origin = latLonToWorld(this.drag.lat, this.drag.lon, this.z);
      const ll = worldToLatLon(origin.x - (ev.clientX - this.drag.x), origin.y - (ev.clientY - this.drag.y), this.z);
      this.lat = ll.lat;
      this.lon = ll.lon;
      this.draw();
    });
    const endDrag = () => {
      this.drag = null;
      this.wrap.classList.remove("is-drag");
    };
    this.wrap.addEventListener("pointerup", endDrag);
    this.wrap.addEventListener("pointercancel", endDrag);
    this.wrap.addEventListener("wheel", (ev) => {
      ev.preventDefault();
      this.setZoom(this.z + (ev.deltaY > 0 ? -1 : 1));
    }, { passive: false });
    this.marks.addEventListener("click", (ev) => {
      const mark = ev.target.closest(".osm-mark");
      if (!mark) return;
      ev.preventDefault();
      ev.stopPropagation();
      this.openId = mark.getAttribute("data-id") || "";
      this.draw();
    });
  };

  LiveOsmMap.prototype.setZoom = function (next) {
    this.z = Math.max(8, Math.min(16, next));
    this.draw();
  };

  LiveOsmMap.prototype.fit = function () {
    const pts = this.payload.vehicles.map((v) => ({ lat: Number(v.lat), lon: Number(v.lon) }));
    if (this.payload.home) pts.push(this.payload.home);
    if (!pts.length) {
      this.lat = PHILLY.lat;
      this.lon = PHILLY.lon;
      this.z = 11;
      return;
    }
    const w = this.host.clientWidth || 320;
    const h = this.host.clientHeight || 200;
    let z = 14;
    for (; z >= 8; z -= 1) {
      const worlds = pts.map((p) => latLonToWorld(p.lat, p.lon, z));
      const dx = Math.max(...worlds.map((p) => p.x)) - Math.min(...worlds.map((p) => p.x));
      const dy = Math.max(...worlds.map((p) => p.y)) - Math.min(...worlds.map((p) => p.y));
      if (dx + 96 <= w && dy + 96 <= h) break;
    }
    this.z = z;
    const worlds = pts.map((p) => latLonToWorld(p.lat, p.lon, z));
    const midX = (Math.min(...worlds.map((p) => p.x)) + Math.max(...worlds.map((p) => p.x))) / 2;
    const midY = (Math.min(...worlds.map((p) => p.y)) + Math.max(...worlds.map((p) => p.y))) / 2;
    const ll = worldToLatLon(midX, midY, z);
    this.lat = ll.lat;
    this.lon = ll.lon;
  };

  LiveOsmMap.prototype.setData = function (payload) {
    const prev = (this.payload && this.payload.count) || 0;
    this.payload = payload || this.payload;
    if (!this.fitted || (prev === 0 && this.payload.count > 0)) {
      this.fit();
      this.fitted = true;
    }
    this.draw();
  };

  LiveOsmMap.prototype.draw = function () {
    const w = this.host.clientWidth || 320;
    const h = this.host.clientHeight || 200;
    const origin = latLonToWorld(this.lat, this.lon, this.z);
    const left = origin.x - w / 2;
    const top = origin.y - h / 2;
    const z = this.z | 0;
    const nTiles = Math.pow(2, z);
    const x0 = Math.floor(left / 256);
    const y0 = Math.floor(top / 256);
    const x1 = Math.floor((left + w) / 256);
    const y1 = Math.floor((top + h) / 256);
    let tiles = "";
    for (let ty = y0; ty <= y1; ty += 1) {
      if (ty < 0 || ty >= nTiles) continue;
      for (let tx = x0; tx <= x1; tx += 1) {
        const wrapped = ((tx % nTiles) + nTiles) % nTiles;
        tiles += `<img alt="" draggable="false" data-z="${z}" data-x="${wrapped}" data-y="${ty}" src="${OSM_TILE.replace("{z}", String(z)).replace("{x}", String(wrapped)).replace("{y}", String(ty))}" onerror="if(!this.dataset.fb){this.dataset.fb=1;this.src='${ESRI_TILE}'.replace('{z}',this.dataset.z).replace('{y}',this.dataset.y).replace('{x}',this.dataset.x)}" style="left:${tx * 256 - left}px;top:${ty * 256 - top}px">`;
      }
    }
    this.tiles.innerHTML = tiles;

    let marks = "";
    if (this.payload.home) {
      const p = latLonToWorld(this.payload.home.lat, this.payload.home.lon, z);
      marks += `<button type="button" class="osm-mark is-home" data-id="home" style="left:${p.x - left}px;top:${p.y - top}px" title="${esc(this.payload.station || "Home")}"></button>`;
    }
    let open = null;
    this.payload.vehicles.forEach((v, i) => {
      const p = latLonToWorld(Number(v.lat), Number(v.lon), z);
      const id = String(v.id || i);
      const kind = String(v.kind || "rail");
      const cls = kind === "metro" ? "osm-mark is-metro" : "osm-mark";
      const color = vehicleColor(v);
      const fg = String(v.line || "").startsWith("G") ? "#14110c" : "#fff";
      if (this.openId === id) open = v;
      marks += `<button type="button" class="${cls}" data-id="${esc(id)}" style="left:${p.x - left}px;top:${p.y - top}px;background:${color};color:${fg}" title="${esc(vehicleKindLabel(kind) + " " + vehicleLabel(v))}"><span>${esc(vehicleLabel(v))}</span></button>`;
    });
    this.marks.innerHTML = marks;
    this.countEl.textContent = this.payload.count
      ? `${this.payload.count} live${this.payload.station ? " · " + this.payload.station : ""}`
      : (this.payload.station ? this.payload.station : "Waiting for GPS");
    if (open) {
      const late = Number(open.late) || 0;
      const status = late > 0 ? `${late} min late` : "On time";
      this.pop.hidden = false;
      this.pop.innerHTML = `<div class="k">${esc(vehicleKindLabel(open.kind))} ${esc(open.line || open.id || "")}</div><div class="t">${esc(open.dest || "In service")}</div><div class="m">${esc(status)}${open.next ? " · " + open.next : ""}</div>`;
    } else if (this.openId === "home" && this.payload.home) {
      this.pop.hidden = false;
      this.pop.innerHTML = `<div class="k">Home</div><div class="t">${esc(this.payload.station || "Station")}</div>`;
    } else {
      this.pop.hidden = true;
      this.pop.innerHTML = "";
    }
  };

  function mountLiveMap(host, payload, opts) {
    if (!host) return null;
    let inst = host.__septaMap;
    if (!inst) {
      inst = new LiveOsmMap(host, opts);
      host.__septaMap = inst;
    }
    inst.setData(payload);
    return inst;
  }

  function modeForEntity(state, fallback) {
    const id = String((state && state.entity_id) || "");
    if (id.endsWith("_metro")) return "metro";
    if (id.endsWith("_trolley")) return "trolley";
    if (id.endsWith("_leave_in")) return "walk";
    if (id.endsWith("_status")) return "status";
    if (id.endsWith("_next_bus") || (state && attr(state, "route"))) return "bus";
    if (id.endsWith("_map") || id.endsWith("_live_map")) return "map";
    return fallback || "rail";
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
        throw new Error("Set entity to a SEPTA Transit train or next-bus sensor");
      }
      this._config = config;
      this._last = "";
    }

    set hass(hass) {
      this._hass = hass;
      const state = stateOf(hass, this._config.entity);
      const pack = trainsForDirection(hass, this._config.entity, dirFromEntity(this._config.entity));
      const sig = state
        ? `${state.state}|${JSON.stringify(pack.trains)}|${this._config.name || ""}`
        : "missing";
      if (sig === this._last) return;
      this._last = sig;
      this._render();
    }

    getCardSize() {
      const n = Number(this._config && this._config.count);
      if (n >= 5) return 6;
      if (n >= 3) return 4;
      return 3;
    }

    static getLayoutOptions() {
      return { grid_columns: 2, grid_rows: 3, grid_min_columns: 2, grid_min_rows: 2 };
    }

    static getStubConfig(hass) {
      return {
        entity:
          findEntity(hass, "_next_southbound", "") ||
          findEntity(hass, "_next_bus", "") ||
          "sensor.septa_lansdale_next_southbound",
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
          {
            name: "count",
            selector: {
              select: {
                options: [
                  { value: "2", label: "Next 2 trains" },
                  { value: "5", label: "Next 5 trains" },
                ],
              },
            },
          },
        ],
      };
    }

    _render() {
      const entity = this._config.entity;
      const state = stateOf(this._hass, entity);
      const name = this._config.name;
      if (!state) {
        this.shadowRoot.innerHTML = `<style>${BASE_CSS}</style><ha-card><div class="wrap"><div class="kicker">SEPTA Transit</div><div class="empty">Missing ${esc(entity)}</div></div></ha-card>`;
        return;
      }
      const delay = Number(attr(state, "delay_min") || 0);
      const cancelled = Boolean(state.attributes && state.attributes.cancelled);
      const isBus = Boolean(attr(state, "route")) || /_next_bus$/.test(String(entity || ""));
      const kind = modeForEntity({ ...(state || {}), entity_id: entity }, isBus ? "bus" : "rail");
      const kicker = name || (kind === "bus" ? "Next bus" : kind === "walk" ? "Leave in" : kind === "status" ? "Line status" : "SEPTA Transit");
      if (kind === "rail") {
        const dir = dirFromEntity(entity);
        const pack = trainsForDirection(this._hass, entity, dir);
        const title = name || (dir === "north" ? "Next outbound" : "Next inbound");
        const count = Number(this._config.count) > 0 ? Number(this._config.count) : 2;
        this.shadowRoot.innerHTML = `<style>${BASE_CSS}</style>
          <ha-card>${heroInner(title, pack.trains, pack.entity || entity, count)}</ha-card>`;
        this.shadowRoot.querySelector("button")?.addEventListener("click", () => moreInfo(this, pack.entity || entity));
        return;
      }
      const inner =
        kind === "bus"
          ? busInner(state, entity, name || kicker)
          : kind === "walk"
            ? leaveInner(state, entity, name || kicker)
            : kind === "status"
              ? statusInner(state, entity, name || kicker)
              : serviceBubble({
                  entity,
                  kind,
                  title: kicker,
                  extra: bulletRow(LETTERS_FOR[kind] || []),
                  clock: attr(state, "clock") || minutesOf(state),
                  late: delayLabel(delay, cancelled, attr(state, "status") || ""),
                  color: tone(delay, cancelled),
                  hint: attr(state, "destination") || attr(state, "summary") || "",
                });
      this.shadowRoot.innerHTML = `<style>${BASE_CSS}</style><ha-card>${inner}</ha-card>`;
      this.shadowRoot.querySelector("button")?.addEventListener("click", () => moreInfo(this, entity));
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
      const southPack = trainsForDirection(hass, this._config.south, "south");
      const northPack = trainsForDirection(hass, this._config.north, "north");
      const extra = ["bus", "leave", "status"].map((k) => {
        const s = stateOf(hass, this._config[k] || "");
        return s ? `${s.state}|${JSON.stringify(s.attributes)}` : "";
      });
      const sig = `${JSON.stringify(southPack.trains)}#${JSON.stringify(northPack.trains)}#${extra.join("#")}`;
      if (sig === this._last) return;
      this._last = sig;
      this._render();
    }

    getCardSize() {
      return 6;
    }

    static getLayoutOptions() {
      return { grid_columns: 4, grid_rows: 5, grid_min_columns: 2, grid_min_rows: 4 };
    }

    static getStubConfig(hass) {
      return {
        name: "SEPTA Transit",
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
          { name: "south", selector: { entity: { domain: "sensor" } } },
          { name: "north", selector: { entity: { domain: "sensor" } } },
          { name: "bus", selector: { entity: { domain: "sensor" } } },
          { name: "leave", selector: { entity: { domain: "sensor" } } },
          { name: "status", selector: { entity: { domain: "sensor" } } },
        ],
      };
    }

    _cell(label, entity, value, hint, color, kind, extra) {
      return `
        <button class="hit cell" type="button" data-entity="${esc(entity)}">
          <div class="title-row">
            <div class="kicker-row">${modeIcon(kind)}<div class="label">${esc(label)}</div></div>
            ${extra || ""}
          </div>
          <div class="clock" style="font-size:24px;margin-top:6px;color:${color || "inherit"}">${esc(value)}</div>
          ${hint ? `<div class="hint">${esc(hint)}</div>` : ""}
        </button>
      `;
    }

    _render() {
      const cfg = this._config;
      const southPack = trainsForDirection(this._hass, cfg.south, "south");
      const northPack = trainsForDirection(this._hass, cfg.north, "north");
      const bus = stateOf(this._hass, cfg.bus);
      const leave = stateOf(this._hass, cfg.leave);
      const status = stateOf(this._hass, cfg.status);
      const statusText = status ? status.state : "";
      const station =
        attr(southPack.state, "station") ||
        attr(northPack.state, "station") ||
        cfg.name ||
        "SEPTA Transit";
      const leaveHint = leave && leave.state !== "unknown" && leave.state !== "unavailable"
        ? `Leave in ${minutesOf(leave)}`
        : "";
      const bits = [statusText, station, leaveHint].filter(Boolean);

      this.shadowRoot.innerHTML = `
        <style>${BASE_CSS}</style>
        <ha-card>
          <div class="board-bar">${esc(bits.join(" · "))}</div>
          <div class="hero-grid">
            ${heroInner("Next inbound", southPack.trains, southPack.entity || cfg.south)}
            ${heroInner("Next outbound", northPack.trains, northPack.entity || cfg.north)}
            ${bus ? busInner(bus, cfg.bus, attr(bus, "route") ? `Bus ${attr(bus, "route")}` : "Next bus") : ""}
          </div>
        </ha-card>
      `;
      this.shadowRoot.querySelectorAll("[data-entity]").forEach((btn) => {
        btn.addEventListener("click", () => moreInfo(this, btn.getAttribute("data-entity")));
      });
    }
  }

  const MODULE_ORDER = ["leave", "south", "north", "bus", "status", "metro", "trolley", "map"];
  const DEFAULT_ON = ["leave", "south", "north", "bus", "status"];
  const MODULE_LABELS = {
    leave: "Leave in",
    south: "Inbound",
    north: "Outbound",
    bus: "Bus",
    status: "Status",
    metro: "Metro",
    trolley: "Trolley",
    map: "Live map",
  };

  function normalizeBubbleConfig(config) {
    const next = { ...(config || {}) };
    if (Array.isArray(next.modules)) {
      next.modules = next.modules.filter((id) => MODULE_ORDER.includes(id));
    } else {
      const flagged = MODULE_ORDER.some((id) => typeof next[`show_${id}`] === "boolean");
      next.modules = flagged
        ? MODULE_ORDER.filter((id) => next[`show_${id}`] === true)
        : DEFAULT_ON.slice();
    }
    for (const id of MODULE_ORDER) next[`show_${id}`] = next.modules.includes(id);
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
      {
        name: "modules",
        selector: {
          select: {
            multiple: true,
            mode: "list",
            options: MODULE_ORDER.map((id) => ({ value: id, label: MODULE_LABELS[id] })),
          },
        },
      },
      { name: "leave", selector: { entity: { domain: "sensor" } } },
      { name: "south", selector: { entity: { domain: "sensor" } } },
      { name: "north", selector: { entity: { domain: "sensor" } } },
      { name: "bus", selector: { entity: { domain: "sensor" } } },
      { name: "status", selector: { entity: { domain: "sensor" } } },
      { name: "metro", selector: { entity: { domain: "sensor" } } },
      { name: "trolley", selector: { entity: { domain: "sensor" } } },
      { name: "map", selector: { entity: { domain: "sensor" } } },
    ];
  }

  function bubbleLabel(schema) {
    const name = schema && schema.name;
    if (name === "name") return "Name";
    if (name === "layout") return "Layout";
    if (name === "map_url") return "Map URL (optional)";
    if (name === "map") return "Live map";
    if (name && name.startsWith("show_")) return MODULE_LABELS[name.slice(5)] || name;
    return MODULE_LABELS[name] || name;
  }

  class SeptaLiveBubble extends HTMLElement {
    constructor() {
      super();
      this._config = {};
      this._hass = null;
      this._last = "";
      this._mapSig = "";
      this.attachShadow({ mode: "open" });
    }

    setConfig(config) {
      this._config = normalizeBubbleConfig(config);
      this._last = "";
      this._render();
    }

    _modules() {
      const cfg = this._config || {};
      if (Array.isArray(cfg.modules)) {
        return cfg.modules.filter((id) => MODULE_ORDER.includes(id));
      }
      return MODULE_ORDER.filter((id) => cfg[`show_${id}`] === true);
    }

    set hass(hass) {
      this._hass = hass;
      const keys = this._modules().map((k) => this._config[k] || "");
      const uiSig = keys
        .concat([this._config.layout || "", this._modules().join(",")])
        .map((id) => {
          if (!id || MODULE_ORDER.includes(id)) return id;
          if (id === this._config.map) return "map";
          const s = stateOf(hass, id);
          return s ? `${s.state}|${JSON.stringify(s.attributes)}` : "";
        })
        .join("#");
      const mapState = stateOf(hass, this._config.map || findEntity(hass, "_map", ""));
      const mapSig = mapState ? `${mapState.state}|${((mapState.attributes && mapState.attributes.vehicles) || []).length}` : "";
      if (uiSig === this._last) {
        if (mapSig === this._mapSig) return;
        this._mapSig = mapSig;
        if (this.shadowRoot.querySelector(".map-host")) this._paintMaps();
        else this._render();
        return;
      }
      this._last = uiSig;
      this._mapSig = mapSig;
      this._render();
    }

    getCardSize() {
      const n = this._modules().length;
      return Math.max(2, Math.ceil(n / 2) + 1);
    }

    static getLayoutOptions() {
      return { grid_columns: 4, grid_rows: 3, grid_min_columns: 2, grid_min_rows: 2 };
    }

    static getConfigForm() {
      return {
        schema: bubbleSchema(),
        computeLabel: bubbleLabel,
      };
    }

    static getConfigElement() {
      return document.createElement("septa-live-bubble-editor");
    }

    static getStubConfig(hass) {
      return {
        name: "SEPTA Transit",
        layout: "bubbles",
        modules: DEFAULT_ON.slice(),
        south: findEntity(hass, "_next_southbound", "sensor.septa_lansdale_next_southbound"),
        north: findEntity(hass, "_next_northbound", "sensor.septa_lansdale_next_northbound"),
        bus: findEntity(hass, "_next_bus", "sensor.septa_lansdale_next_bus"),
        leave: findEntity(hass, "_leave_in", "sensor.septa_lansdale_leave_in"),
        status: findEntity(hass, "_status", "sensor.septa_lansdale_status"),
        metro: findEntity(hass, "_metro", ""),
        trolley: findEntity(hass, "_trolley", ""),
        map: findEntity(hass, "_map", "sensor.septa_lansdale_map"),
      };
    }

    _face(id) {
      const cfg = this._config;
      const entity = cfg[id];
      const state = stateOf(this._hass, entity);
      const delay = Number(attr(state, "delay_min") || 0);
      const color = tone(delay, Boolean(state && state.attributes && state.attributes.cancelled));
      const kind = MODE_FOR[id] || "rail";
      const letters = LETTERS_FOR[id] || [];
      let extra = bulletRow(letters);
      if (id === "leave") {
        const n = state && state.state !== "unknown" ? Number(state.state) : null;
        return {
          label: "Leave in",
          value: n == null || Number.isNaN(n) ? "—" : n <= 0 ? "Now" : `${n} min`,
          hint: attr(state, "walk_minutes") ? `${attr(state, "walk_minutes")} min walk` : "Walk window",
          color: n != null && n <= 2 ? LATE : ONTIME,
          entity,
          kind,
          extra,
        };
      }
      if (id === "south" || id === "north") {
        const dir = id === "north" ? "north" : "south";
        const pack = trainsForDirection(this._hass, entity, dir);
        const first = pack.trains[0];
        const late = first
          ? delayLabel(Number(first.delay_min || 0), Boolean(first.cancelled), first.status || (first.scheduled ? "Scheduled" : ""))
          : "";
        return {
          label: id === "south" ? "Inbound" : "Outbound",
          value: first ? (first.clock || minutesOf(state)) : "—",
          hint: first ? trainHint(first) : "None listed",
          status: late,
          color: first ? trainColor(first) : "inherit",
          entity: pack.entity || entity,
          kind,
          extra: first ? railBadge(first.line) : extra,
        };
      }
      if (id === "bus") {
        extra = attr(state, "route") ? pill(attr(state, "route")) : extra;
        const live = Boolean(attr(state, "live"));
        const clock = splitClock(attr(state, "clock") || attr(state, "depart") || "");
        const label = `${clock.time || minutesOf(state)}${clock.period ? " " + clock.period : ""}`;
        return {
          label: attr(state, "route") ? `Bus ${attr(state, "route")}` : "Next bus",
          value: label,
          hint: `${minutesOf(state)}${attr(state, "destination") ? " · " + attr(state, "destination") : ""}`,
          status: state ? (live ? delayLabel(delay, false, "") : "Scheduled") : "",
          color: live ? tone(delay, false) : "inherit",
          entity,
          kind,
          extra,
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
          kind,
          extra,
        };
      }
      if (id === "metro") {
        return {
          label: "Metro",
          value: state && state.state !== "unknown" ? state.state : "—",
          hint: attr(state, "summary") || "L · B · M",
          color: ONTIME,
          entity,
          kind,
          extra,
        };
      }
      if (id === "trolley") {
        return {
          label: "Trolley",
          value: state && state.state !== "unknown" ? state.state : "—",
          hint: attr(state, "summary") || "T · G · D",
          color: ONTIME,
          entity,
          kind,
          extra,
        };
      }
      return { label: id, value: "—", hint: "", color: ONTIME, entity, kind, extra };
    }

    _bubble(face, extraClass) {
      return `
        <button class="bubble ${extraClass || ""}" type="button" data-entity="${esc(face.entity || "")}">
          <div class="title-row">
            <div class="left">${modeIcon(face.kind)}<div class="label">${esc(face.label)}</div></div>
            ${face.extra || ""}
          </div>
          <div class="bubble-clock-row">
            <div class="value" style="color:${face.color}">${esc(face.value)}</div>
            ${face.status ? `<div class="bubble-late" style="color:${face.color}">${esc(face.status)}</div>` : ""}
          </div>
          <div class="hint">${esc(face.hint)}</div>
        </button>
      `;
    }

    _render() {
      const modules = this._modules();
      const layout = this._config.layout === "stack" || this._config.layout === "hero" ? this._config.layout : "bubbles";
      const name = this._config.name || "SEPTA Transit";
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
      this._paintMaps();
    }

    _paintMaps() {
      const dark = !(this._hass && this._hass.themes && this._hass.themes.darkMode === false);
      this.shadowRoot.querySelectorAll(".map-host").forEach((host) => {
        const entity = host.getAttribute("data-map-entity") || this._config.map || findEntity(this._hass, "_map", "");
        mountLiveMap(host, mapPayload(stateOf(this._hass, entity)), { dark });
      });
    }

    _moduleHtml(id, extraClass) {
      if (id === "map") {
        const entity = this._config.map || findEntity(this._hass, "_map", "");
        const payload = mapPayload(stateOf(this._hass, entity));
        if (payload.home || payload.vehicles.length) {
          return `<div class="bubble is-map ${extraClass || ""}"><div class="map-host" data-map-entity="${esc(entity)}"></div></div>`;
        }
        if (this._config.map_url) {
          return `<div class="bubble is-map ${extraClass || ""}"><iframe class="bubble-map" src="${esc(this._config.map_url)}" title="SEPTA live map" loading="lazy" referrerpolicy="no-referrer"></iframe></div>`;
        }
        return this._bubble({
          label: "Live map",
          value: payload.count ? String(payload.count) : "Waiting",
          hint: entity ? "GPS updates with the integration" : "Add the Map sensor",
          color: LATE,
          entity,
          kind: "map",
          extra: "",
        }, extraClass);
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
      this._ready = false;
      this.attachShadow({ mode: "open" });
    }

    set hass(hass) {
      this._hass = hass;
      if (this._form) this._form.hass = hass;
    }

    setConfig(config) {
      const next = normalizeBubbleConfig(config);
      const same = JSON.stringify(next) === JSON.stringify(this._config);
      this._config = next;
      if (!this._ready) this._build();
      else if (!same) this._sync();
    }

    _emit(partial) {
      const next = normalizeBubbleConfig({ ...this._config, ...partial });
      if (JSON.stringify(next) === JSON.stringify(this._config)) return;
      this._config = next;
      this.dispatchEvent(
        new CustomEvent("config-changed", {
          bubbles: true,
          composed: true,
          detail: { config: next },
        }),
      );
      this._sync();
    }

    _build() {
      this._ready = true;
      this.shadowRoot.innerHTML = `
        <style>
          :host { display: block; }
          .cap { font-size: 12px; opacity: 0.65; margin: 4px 0 10px; }
          .row {
            display: flex; align-items: center; justify-content: space-between;
            min-height: 48px; cursor: pointer; user-select: none; gap: 10px;
          }
          .row .name { display: flex; align-items: center; gap: 10px; font-size: 14px; }
          .row .mode { width: 28px; height: 28px; }
          .bullets { display: inline-flex; gap: 3px; }
          .bullet {
            display: inline-flex; align-items: center; justify-content: center;
            width: 18px; height: 18px; border-radius: 2px;
            font-weight: 700; font-size: 11px; line-height: 1;
          }
          .sw {
            width: 36px; height: 20px; border-radius: 12px; position: relative;
            background: var(--switch-unchecked-track-color, #63666b);
            flex-shrink: 0; transition: background 0.15s;
          }
          .sw.on { background: var(--switch-checked-color, var(--primary-color, #03a9f4)); }
          .knob {
            position: absolute; top: 2px; left: 2px; width: 16px; height: 16px;
            border-radius: 50%; background: #fff; transition: left 0.15s;
          }
          .sw.on .knob { left: 18px; }
          .form { margin-top: 12px; }
        </style>
        <div class="cap">Show on card</div>
        <div class="mods"></div>
        <div class="form"></div>
      `;
      const mods = this.shadowRoot.querySelector(".mods");
      mods.innerHTML = MODULE_ORDER.map((id) => {
        const letters = LETTERS_FOR[id] || [];
        return `
        <div class="row" data-mod="${id}">
          <span class="name">${modeIcon(MODE_FOR[id] || "rail")}<span>${MODULE_LABELS[id]}</span>${bulletRow(letters)}</span>
          <div class="sw"><div class="knob"></div></div>
        </div>`;
      }).join("");
      mods.querySelectorAll(".row").forEach((row) => {
        row.addEventListener("click", () => {
          const id = row.getAttribute("data-mod");
          const on = new Set(this._config.modules || []);
          const modules = MODULE_ORDER.filter((m) => (m === id ? !on.has(id) : on.has(m)));
          this._emit({ modules });
        });
      });
      this._form = document.createElement("ha-form");
      this._form.schema = bubbleSchema().filter((item) => item.name !== "modules");
      this._form.computeLabel = bubbleLabel;
      this._form.addEventListener("value-changed", (ev) => {
        const value = ev.detail.value || {};
        this._emit({ ...value, modules: this._config.modules });
      });
      this.shadowRoot.querySelector(".form").appendChild(this._form);
      this._sync();
    }

    _sync() {
      const on = new Set(this._config.modules || []);
      this.shadowRoot.querySelectorAll(".row").forEach((row) => {
        row.querySelector(".sw").classList.toggle("on", on.has(row.getAttribute("data-mod")));
      });
      if (this._form) {
        this._form.data = this._config;
        if (this._hass) this._form.hass = this._hass;
      }
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

  class SeptaLiveDepartures extends HTMLElement {
    constructor() {
      super();
      this._config = {};
      this._hass = null;
      this._last = "";
      this._station = "";
      this._direction = "south";
      this._size = "regular";
      this._remote = null;
      this._fetching = "";
      this.attachShadow({ mode: "open" });
    }

    setConfig(config) {
      this._config = config || {};
      this._direction = config && config.direction === "north" ? "north" : "south";
      this._station = stationApiName((config && config.station) || "");
      this._size = normalizeSize(config && config.size);
      this._last = "";
    }

    set hass(hass) {
      this._hass = hass;
      void this._refresh();
    }

    getCardSize() {
      if (this._size === "compact") return 4;
      if (this._size === "large") return 8;
      return 6;
    }

    static getLayoutOptions() {
      return { grid_columns: 2, grid_rows: 6, grid_min_columns: 2, grid_min_rows: 3 };
    }

    static getStubConfig(hass) {
      const boards = discoverBoards(hass);
      const first = boards[0];
      return {
        name: first ? first.name : "Regional Rail",
        south: first ? first.south : findEntity(hass, "_southbound_board", "sensor.septa_lansdale_southbound_board"),
        north: first ? first.north : findEntity(hass, "_northbound_board", "sensor.septa_lansdale_northbound_board"),
        station: first ? first.name : "Lansdale",
        direction: "south",
        size: "regular",
      };
    }

    static getConfigForm() {
      return {
        schema: [
          { name: "name", selector: { text: {} } },
          { name: "station", selector: { text: {} } },
          { name: "south", selector: { entity: { domain: "sensor" } } },
          { name: "north", selector: { entity: { domain: "sensor" } } },
          {
            name: "direction",
            selector: {
              select: {
                options: [
                  { value: "south", label: "Inbound" },
                  { value: "north", label: "Outbound" },
                ],
              },
            },
          },
          {
            name: "size",
            selector: {
              select: {
                options: [
                  { value: "compact", label: "Compact · 3 trains" },
                  { value: "regular", label: "Regular · 5 trains" },
                  { value: "large", label: "Large · 8 trains" },
                ],
              },
            },
          },
        ],
      };
    }

    async _refresh() {
      const hass = this._hass;
      if (!hass) return;
      const boards = discoverBoards(hass);
      if (!this._station) {
        const fromCfg = this._config.station || slugFromEntity(this._config.south || this._config.north || "");
        const local = boardForStation(boards, fromCfg) || boards[0];
        this._station = stationApiName((local && local.name) || fromCfg || "Lansdale");
      }
      const local = boardForStation(boards, this._station);
      let southTrains = [];
      let northTrains = [];
      let southEntity = (local && local.south) || this._config.south || "";
      let northEntity = (local && local.north) || this._config.north || "";
      let loading = false;
      const want = SIZE_ROWS[this._size] || 5;
      if (local) {
        southTrains = trainsOf(stateOf(hass, southEntity), 8);
        northTrains = trainsOf(stateOf(hass, northEntity), 8);
        this._remote = null;
      }
      const needRemote = !local || Math.max(southTrains.length, northTrains.length) < want;
      if (needRemote && hass.connection) {
        const stale = !this._remote || this._remote.station !== this._station || Date.now() - this._remote.at > 25000;
        if (stale && this._fetching !== this._station) {
          this._fetching = this._station;
          loading = !southTrains.length && !northTrains.length;
          try {
            const data = await hass.connection.sendMessagePromise({
              type: "septa_live/board",
              station: this._station,
            });
            if (this._station === this._fetching) {
              this._remote = {
                station: this._station,
                at: Date.now(),
                south: (data && data.southbound) || [],
                north: (data && data.northbound) || [],
              };
            }
          } catch (_err) {
            if (this._station === this._fetching && !this._remote) {
              this._remote = { station: this._station, at: Date.now(), south: [], north: [] };
            }
          }
          this._fetching = "";
          loading = false;
        }
        if (this._remote && this._remote.station === this._station) {
          if (!southTrains.length) southTrains = this._remote.south || [];
          if (!northTrains.length) northTrains = this._remote.north || [];
          if ((this._remote.south || []).length > southTrains.length) southTrains = this._remote.south;
          if ((this._remote.north || []).length > northTrains.length) northTrains = this._remote.north;
        }
      }
      const trains = (this._direction === "north" ? northTrains : southTrains).slice(0, want);
      const entity = this._direction === "north" ? northEntity : southEntity;
      const sig = `${this._station}|${this._direction}|${this._size}|${loading}|${JSON.stringify(trains)}`;
      if (sig === this._last) return;
      this._last = sig;
      this._render(trains, entity, loading);
    }

    _render(trains, entity, loading) {
      const stationName = stationApiName(this._station) || this._config.name || "Regional Rail";
      const heading = this._direction === "north" ? "Outbound" : "Inbound";
      const selected = stationApiName(this._station);
      const stationOpts = RAIL_STATIONS.map(
        (s) => `<option value="${esc(s.api)}"${s.api === selected || s.name === this._station ? " selected" : ""}>${esc(s.name)}</option>`,
      ).join("");
      const rows = loading
        ? `<div class="empty" style="padding:14px">Loading departures…</div>`
        : trains.length
          ? trains
              .map((t) => {
                const track = String(t.track || t.platform || "").trim();
                const dest = t.destination || "—";
                const clock = splitClock(t.clock);
                const mins = durationLabel(t.minutes);
                const color = tone(Number(t.delay_min || 0), Boolean(t.cancelled));
                const late = delayLabel(Number(t.delay_min || 0), Boolean(t.cancelled), t.status);
                const service = serviceLabel(t.service_type || t.service);
                return `
                <button class="hit dep-cols is-row" type="button" data-entity="${esc(entity || "")}">
                  <div class="dep-time">
                    <div>${esc(clock.time || mins)}</div>
                    ${clock.period ? `<div class="hint" style="margin:2px 0 0">${esc(clock.period)}</div>` : ""}
                  </div>
                  <div class="dep-dest">
                    <span class="to">${railBadge(t.line)}<span>${esc(dest)}</span></span>
                    <span class="id">${t.train_id ? "#" + esc(t.train_id) : ""}${service ? " · " + esc(service) : ""}</span>
                  </div>
                  <div class="dep-plat">
                    <span class="dep-trk${track ? "" : " is-empty"}">${esc(track || "—")}</span>
                  </div>
                  <div class="dep-expect">
                    <span class="dep-mins" style="color:${color}">${esc(mins)}</span>
                    <span class="late" style="color:${color}">${esc(late)}</span>
                  </div>
                </button>`;
              })
              .join("")
          : `<div class="empty" style="padding:14px">${esc(overnightEmpty(heading))}</div>`;

      this.shadowRoot.innerHTML = `
        <style>${BASE_CSS}</style>
        <ha-card class="dep-card is-${esc(this._size)}">
          <div class="head">
            <div class="kicker-row">${modeIcon("rail")}<div class="kicker">${esc(this._config.name || stationName)}</div></div>
            <div class="hint" style="margin:0">${esc(heading)}</div>
          </div>
          <div class="dep-toolbar">
            <label>
              <span>Station</span>
              <select data-pick="station">${stationOpts}</select>
            </label>
            <label>
              <span>Direction</span>
              <select data-pick="direction">
                <option value="south"${this._direction === "south" ? " selected" : ""}>Inbound</option>
                <option value="north"${this._direction === "north" ? " selected" : ""}>Outbound</option>
              </select>
            </label>
          </div>
          <div class="size-pills" role="tablist" aria-label="Card size">
            <button type="button" data-size="compact"${this._size === "compact" ? ' class="on"' : ""}>Compact</button>
            <button type="button" data-size="regular"${this._size === "regular" ? ' class="on"' : ""}>Regular</button>
            <button type="button" data-size="large"${this._size === "large" ? ' class="on"' : ""}>Large</button>
          </div>
          <div class="dep-cols is-head">
            <span>Time</span>
            <span>Destination</span>
            <span>Platform</span>
            <span>Expected</span>
          </div>
          ${rows}
        </ha-card>
      `;
      this.shadowRoot.querySelectorAll("[data-entity]").forEach((btn) => {
        const id = btn.getAttribute("data-entity");
        if (id) btn.addEventListener("click", () => moreInfo(this, id));
      });
      const stationSel = this.shadowRoot.querySelector('[data-pick="station"]');
      const dirSel = this.shadowRoot.querySelector('[data-pick="direction"]');
      if (stationSel) {
        stationSel.addEventListener("change", (ev) => {
          this._station = stationApiName(ev.target.value);
          this._remote = null;
          this._last = "";
          void this._refresh();
        });
      }
      if (dirSel) {
        dirSel.addEventListener("change", (ev) => {
          this._direction = ev.target.value === "north" ? "north" : "south";
          this._last = "";
          void this._refresh();
        });
      }
      this.shadowRoot.querySelectorAll("[data-size]").forEach((btn) => {
        btn.addEventListener("click", () => {
          this._size = normalizeSize(btn.getAttribute("data-size"));
          this._last = "";
          void this._refresh();
        });
      });
    }
  }

  if (!customElements.get("septa-live-departures")) {
    customElements.define("septa-live-departures", SeptaLiveDepartures);
  }

  function entitiesStub(hass) {
    return {
      south: findEntity(hass, "_next_southbound", "sensor.septa_lansdale_next_southbound"),
      north: findEntity(hass, "_next_northbound", "sensor.septa_lansdale_next_northbound"),
      southBoard: findEntity(hass, "_southbound_board", "sensor.septa_lansdale_southbound_board"),
      northBoard: findEntity(hass, "_northbound_board", "sensor.septa_lansdale_northbound_board"),
      bus: findEntity(hass, "_next_bus", "sensor.septa_lansdale_next_bus"),
      leave: findEntity(hass, "_leave_in", "sensor.septa_lansdale_leave_in"),
      status: findEntity(hass, "_status", "sensor.septa_lansdale_status"),
      metro: findEntity(hass, "_metro", "sensor.septa_lansdale_metro"),
      trolley: findEntity(hass, "_trolley", "sensor.septa_lansdale_trolley"),
      map: findEntity(hass, "_map", "sensor.septa_lansdale_map"),
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

  class SeptaLiveMap extends HTMLElement {
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
      this._render();
    }

    _entity() {
      return this._config.entity || findEntity(this._hass, "_map", "sensor.septa_lansdale_map");
    }

    set hass(hass) {
      this._hass = hass;
      const id = this._entity();
      const s = stateOf(hass, id);
      const sig = s ? `${s.state}|${JSON.stringify(s.attributes && s.attributes.vehicles)}` : id;
      if (sig === this._last) return;
      this._last = sig;
      if (this.shadowRoot.querySelector(".map-host")) this._paint();
      else this._render();
    }

    getCardSize() {
      return 5;
    }

    static getLayoutOptions() {
      return { grid_columns: 4, grid_rows: 4, grid_min_columns: 2, grid_min_rows: 3 };
    }

    static getStubConfig(hass) {
      return { entity: findEntity(hass, "_map", "sensor.septa_lansdale_map"), name: "Live map" };
    }

    static getConfigForm() {
      return {
        schema: [
          { name: "name", selector: { text: {} } },
          { name: "entity", selector: { entity: { domain: "sensor" } } },
        ],
      };
    }

    _render() {
      const name = this._config.name || "Live map";
      this.shadowRoot.innerHTML = `
        <style>${BASE_CSS}</style>
        <ha-card>
          <div class="head">
            <div class="kicker">${esc(name)}</div>
            <div class="status" data-count></div>
          </div>
          <div class="map-host is-card"></div>
        </ha-card>
      `;
      this._paint();
    }

    _paint() {
      const host = this.shadowRoot.querySelector(".map-host");
      const payload = mapPayload(stateOf(this._hass, this._entity()));
      const count = this.shadowRoot.querySelector("[data-count]");
      if (count) count.textContent = payload.count ? `${payload.count} live` : "Waiting for GPS";
      const dark = !(this._hass && this._hass.themes && this._hass.themes.darkMode === false);
      mountLiveMap(host, payload, { dark });
    }
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
        { label: "Board", config: { type: "custom:septa-live-board", name: "SEPTA Transit", ...e } },
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
    if (id.endsWith("_southbound_board") || id.endsWith("_northbound_board")) {
      return {
        label: "Rail departures",
        config: {
          type: "custom:septa-live-departures",
          name: "Regional Rail",
          south: e.southBoard,
          north: e.northBoard,
        },
      };
    }
    if (id.endsWith("_next_southbound")) {
      return { label: "Inbound", config: { type: "custom:septa-live-south", entity: id, name: "Inbound" } };
    }
    if (id.endsWith("_next_northbound")) {
      return { label: "Outbound", config: { type: "custom:septa-live-north", entity: id, name: "Outbound" } };
    }
    if (id.endsWith("_status")) {
      return { label: "Status", config: { type: "custom:septa-live-status", entity: id, name: "Line status" } };
    }
    if (id.endsWith("_map") || id.endsWith("_live_map")) {
      return { label: "Live map", config: { type: "custom:septa-live-map", entity: id, name: "Live map" } };
    }
    return [
      { label: "Train", config: { type: "custom:septa-live-card", entity: id } },
      { label: "Board", config: { type: "custom:septa-live-board", name: "SEPTA Transit", ...e } },
        { label: "Glance", config: { type: "custom:septa-live-glance", name: "SEPTA", layout: "bubbles", modules: ["leave", "south", "bus", "status"], ...e } },
    ];
  }

  registerCard("septa-live-card", SeptaLiveCard, "SEPTA Transit Train", "Hero card for your next train");
  registerCard("septa-live-bus", heroPreset("_next_bus", "sensor.septa_lansdale_next_bus", "Next bus"), "SEPTA Transit Next Bus", "Next bus at the stop nearest your station");
  registerCard("septa-live-leave", heroPreset("_leave_in", "sensor.septa_lansdale_leave_in", "Leave in"), "SEPTA Transit Leave", "Walk-window countdown so you know when to head out");
  registerCard("septa-live-south", heroPreset("_next_southbound", "sensor.septa_lansdale_next_southbound", "Next inbound"), "SEPTA Transit Inbound", "Next two trains into Center City");
  registerCard("septa-live-north", heroPreset("_next_northbound", "sensor.septa_lansdale_next_northbound", "Next outbound"), "SEPTA Transit Outbound", "Next two trains out of Center City");
  registerCard("septa-live-status", heroPreset("_status", "sensor.septa_lansdale_status", "Line status"), "SEPTA Transit Status", "On time, delay, alert, or suspended");
  registerCard("septa-live-board", SeptaLiveBoard, "SEPTA Transit Board", "Inbound, outbound, and next bus — same bubbles as the live board");
  registerCard(
    "septa-live-departures",
    SeptaLiveDepartures,
    "SEPTA Transit Departures",
    "Next 5 Regional Rail trains for one station and direction, with platform",
  );
  registerCard(
    "septa-live-glance",
    bubblePreset("SEPTA", ["leave", "south", "bus", "status"], "bubbles"),
    "SEPTA Transit Glance",
    "Four sensors in one compact row",
  );
  registerCard(
    "septa-live-metro",
    bubblePreset("SEPTA Metro", ["metro", "trolley", "status"], "bubbles"),
    "SEPTA Transit Metro",
    "L, B, and M in service, plus trolleys",
  );
  registerCard(
    "septa-live-trolley",
    bubblePreset("SEPTA Trolley", ["trolley"], "bubbles"),
    "SEPTA Transit Trolley",
    "T, G, and D live",
  );
  registerCard("septa-live-bubble", SeptaLiveBubble, "SEPTA Transit Bubble", "Pick bus, Metro, trolley, and map bubbles");
  registerCard("septa-live-map", SeptaLiveMap, "SEPTA Transit Map", "Live GPS map of trains, buses, Metro, and trolleys");
})();
