/*
 * Bed Sleep Score Card for Home Assistant
 * https://github.com/artech-lab/ha-bed-sleep-score
 *
 * Dashboard card bundled with the Bed Sleep Score integration, which serves
 * and loads it automatically (no dashboard resource needed). It only displays
 * what the integration computes: score ring, night chips, score breakdown,
 * editable sleep window and history. Every entity is discovered from the
 * device of the configured score sensor.
 *
 * One dependency-free file, no build step. Localized: English and Italian.
 *
 * Copyright (C) 2026 The ha-bed-sleep-score contributors
 *
 * This program is free software: you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by the Free
 * Software Foundation, either version 3 of the License, or (at your option)
 * any later version. This program is distributed in the hope that it will be
 * useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
 * Public License for more details: <https://www.gnu.org/licenses/>.
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

// The integration appends its manifest version to the URL of this module.
const CARD_VERSION = new URL(import.meta.url).searchParams.get("v") || "dev";
const CARD_TAG = "bed-sleep-score-card";
const EDITOR_TAG = "bed-sleep-score-card-editor";
const INTEGRATION = "bed_sleep_score";

const STRINGS = {
  en: {
    card_name: "Bed Sleep Score",
    card_description:
      "Nightly sleep score from a bed motion sensor: score ring, continuity, movements, wake-ups, breakdown, sleep window and history.",
    default_title: "Sleep quality",
    out_of: "out of 100",
    no_data: "No data",
    excellent: "Excellent",
    good: "Good",
    fair: "Fair",
    poor: "Needs work",
    window_active: "Window active",
    window_inactive: "Window inactive",
    sleep_window: "Sleep window",
    start: "Start",
    end: "End",
    longest: "Longest sleep",
    movements: "Movements",
    clusters: "Clustered moves",
    last_days: "Last {n} days",
    avg: "avg {v}",
    no_history: "No history yet",
    history_error: "History not available",
    no_entity: "Select the sleep score sensor of a Bed Sleep Score device.",
    continuity: "Continuity",
    movements_short: "Movements",
    wakeups: "Wake-ups",
    calm: "Calm",
    intensity: "Intensity",
    neutral_hint: "calm and intensity neutral: not enough signal",
    // editor
    e_entity: "Sleep score sensor",
    e_name: "Title",
    e_history_days: "History days",
    e_show_breakdown: "Show score breakdown",
    e_show_window: "Show sleep window",
    e_show_history: "Show history"
  },
  it: {
    card_name: "Bed Sleep Score",
    card_description:
      "Punteggio del sonno da un sensore di movimento sul letto: anello del punteggio, continuità, movimenti, risvegli, dettaglio, finestra di sonno e storico.",
    default_title: "Qualità del sonno",
    out_of: "su 100",
    no_data: "Nessun dato",
    excellent: "Ottimo",
    good: "Buono",
    fair: "Discreto",
    poor: "Da migliorare",
    window_active: "Finestra attiva",
    window_inactive: "Finestra inattiva",
    sleep_window: "Finestra di sonno",
    start: "Inizio",
    end: "Fine",
    longest: "Sonno max",
    movements: "Movimenti",
    clusters: "Ravvicinati",
    last_days: "Ultimi {n} giorni",
    avg: "media {v}",
    no_history: "Nessun dato storico ancora disponibile",
    history_error: "Storico non disponibile",
    no_entity: "Seleziona il sensore punteggio sonno di un dispositivo Bed Sleep Score.",
    continuity: "Continuità",
    movements_short: "Movim.",
    wakeups: "Risvegli",
    calm: "Calma",
    intensity: "Intens.",
    neutral_hint: "calma e intensità neutre: segnale insufficiente",
    e_entity: "Sensore punteggio sonno",
    e_name: "Titolo",
    e_history_days: "Giorni di storico",
    e_show_breakdown: "Mostra dettaglio punteggio",
    e_show_window: "Mostra finestra di sonno",
    e_show_history: "Mostra storico"
  }
};

function langOf(hass) {
  const l = (hass && ((hass.locale && hass.locale.language) || hass.language)) ||
    (typeof navigator !== "undefined" ? navigator.language : "en");
  return String(l || "en").toLowerCase().split("-")[0];
}

function t(hass, key, vars) {
  const table = STRINGS[langOf(hass)] || STRINGS.en;
  let s = table[key] != null ? table[key] : (STRINGS.en[key] != null ? STRINGS.en[key] : key);
  if (vars) for (const k of Object.keys(vars)) s = s.replace("{" + k + "}", vars[k]);
  return s;
}

/* Maps the integration's translation keys to card config keys. */
const SIBLINGS = {
  score_7_day_average: "average_entity",
  movements: "movements_entity",
  clustered_movements: "clusters_entity",
  longest_undisturbed_sleep: "continuity_entity",
  window_active: "window_entity",
  window_start: "window_start_entity",
  window_end: "window_end_entity"
};

function findScoreEntity(hass) {
  const reg = (hass && hass.entities) || {};
  for (const id of Object.keys(reg)) {
    const e = reg[id];
    if (e && e.platform === INTEGRATION && e.translation_key === "score") return id;
  }
  return null;
}

function discoverSiblings(hass, scoreEntity) {
  const out = {};
  const reg = (hass && hass.entities) || {};
  const me = reg[scoreEntity];
  if (!me || !me.device_id) return out;
  for (const id of Object.keys(reg)) {
    const e = reg[id];
    if (!e || e.device_id !== me.device_id || e.platform !== INTEGRATION) continue;
    const key = SIBLINGS[e.translation_key];
    if (key) out[key] = id;
  }
  return out;
}

async function ensureHaForm() {
  if (customElements.get("ha-form")) return;
  try {
    const helpers = await window.loadCardHelpers();
    const card = await helpers.createCardElement({ type: "entities", entities: [] });
    if (card && card.constructor && card.constructor.getConfigElement) await card.constructor.getConfigElement();
  } catch (e) {
    /* ha-form will be loaded by the edit dialog */
  }
}

const dayKey = (d) =>
  d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");

class BedSleepScoreCard extends HTMLElement {
  static getStubConfig(hass) {
    return { entity: findScoreEntity(hass) || "", history_days: 7 };
  }

  static async getConfigElement() {
    await ensureHaForm();
    return document.createElement(EDITOR_TAG);
  }

  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    const entity = config.entity || "";
    this._config = Object.assign(
      { history_days: 7, show_breakdown: true, show_window: true, show_history: true },
      config,
      { entity }
    );
    this._lastHist = 0;
    this._histError = false;
    this._days = [];
    this._built = false;
    if (this.shadowRoot && this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    if (!this._built) this._render();
    this._update();
    this._fetchHistory();
  }

  getCardSize() {
    return 6;
  }

  getGridOptions() {
    return { columns: 6, min_columns: 6, rows: "auto" };
  }

  /* Entities of the same device as the score sensor. */
  _ents() {
    const c = this._config;
    const found = c.entity ? discoverSiblings(this._hass, c.entity) : {};
    const out = {};
    for (const key of Object.values(SIBLINGS)) out[key] = found[key] || null;
    return out;
  }

  _t(key, vars) {
    return t(this._hass, key, vars);
  }

  _color(v) {
    if (v >= 80) return "var(--green-color, #4caf50)";
    if (v >= 60) return "var(--yellow-color, #fdd835)";
    if (v >= 40) return "var(--orange-color, #ff9800)";
    return "var(--red-color, #f44336)";
  }

  _label(v) {
    if (v >= 80) return this._t("excellent");
    if (v >= 60) return this._t("good");
    if (v >= 40) return this._t("fair");
    return this._t("poor");
  }

  _render() {
    const C = (2 * Math.PI * 54).toFixed(2);
    const ARC = (2 * Math.PI * 54 * 0.75).toFixed(2);
    this._built = true;
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { padding: 12px 12px 14px; overflow: hidden; height: 100%; box-sizing: border-box; }
        .head { display: flex; align-items: center; gap: 12px; margin-bottom: 4px; }
        .shape { width: 40px; height: 40px; min-width: 40px; border-radius: 50%;
          display: flex; align-items: center; justify-content: center;
          background: color-mix(in srgb, var(--indigo-color, #3f51b5) 20%, transparent);
          color: var(--indigo-color, #3f51b5); }
        .shape ha-icon { --mdc-icon-size: 22px; }
        .title { font-size: 1rem; font-weight: 500; color: var(--primary-text-color); flex: 1;
          line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .pill { display: inline-flex; align-items: center; gap: 6px; font-size: 12px;
          color: var(--secondary-text-color); transition: color .3s; }
        .pill .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--disabled-text-color);
          transition: background .3s; }
        .pill.on { color: var(--indigo-color, #3f51b5); }
        .pill.on .dot { background: var(--indigo-color, #3f51b5); }
        .ring-wrap { position: relative; width: 172px; margin: 4px auto -24px; cursor: pointer; }
        svg { width: 100%; height: auto; display: block; }
        .track, .prog { fill: none; stroke-width: 11; stroke-linecap: round;
          transform: rotate(135deg); transform-origin: 50% 50%; }
        .track { stroke: var(--divider-color, rgba(127,127,127,.25)); stroke-dasharray: ${ARC} ${C}; }
        .prog { stroke-dasharray: 0 ${C}; transition: stroke-dasharray 1s cubic-bezier(.4,0,.2,1), stroke .6s; }
        .center { position: absolute; inset: 0; display: flex; flex-direction: column;
          align-items: center; justify-content: center; pointer-events: none; }
        .score { font-size: 2.2rem; font-weight: 500; line-height: 1; color: var(--primary-text-color); }
        .of { font-size: 11px; color: var(--secondary-text-color); margin-top: 2px; }
        .status { font-size: 13px; font-weight: 500; margin-top: 6px; transition: color .6s; }
        .chips { display: flex; gap: 8px; margin: 12px 0 4px; }
        .chip { flex: 1; min-width: 0; display: flex; align-items: center; gap: 10px; padding: 4px 0; }
        .chip ha-icon { color: var(--indigo-color, #3f51b5); --mdc-icon-size: 20px; flex: 0 0 auto; }
        .chip .val { font-size: 1rem; font-weight: 500; color: var(--primary-text-color); line-height: 1.2; }
        .chip .lbl { font-size: 11px; color: var(--secondary-text-color);
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .chip.link { cursor: pointer; border-radius: 8px; padding: 4px 6px; margin: 0 -6px;
          transition: background .2s, transform .1s; }
        .chip.link:hover { background: color-mix(in srgb, var(--indigo-color, #3f51b5) 10%, transparent); }
        .chip.link:active { transform: scale(.98); }
        .detail { font-size: 11px; color: var(--secondary-text-color); line-height: 1.5; margin: 4px 0 0; }
        .detail .part { white-space: nowrap; }
        .wintime { margin-top: 12px; }
        .wt-head { font-size: 11px; letter-spacing: .5px; text-transform: uppercase;
          color: var(--secondary-text-color); margin-bottom: 8px; }
        .wt-row { display: flex; align-items: center; gap: 10px; }
        .wt-btn { box-sizing: border-box; flex: 1; display: flex; flex-direction: column;
          align-items: flex-start; gap: 4px; padding: 10px 14px; border-radius: 12px;
          border: none; background: color-mix(in srgb, var(--primary-text-color) 8%, transparent);
          color: var(--primary-text-color); font: inherit; text-align: left; cursor: pointer;
          transition: background .2s, transform .1s; }
        .wt-btn:hover { background: color-mix(in srgb, var(--indigo-color, #3f51b5) 16%, transparent); }
        .wt-btn:active { transform: scale(.98); }
        .wt-btn.ro { cursor: default; pointer-events: none; }
        .wt-lbl { display: inline-flex; align-items: center; gap: 6px; font-size: 11px;
          color: var(--secondary-text-color); }
        .wt-lbl ha-icon { --mdc-icon-size: 16px; color: var(--indigo-color, #3f51b5); }
        .wt-time { font-size: 1.45rem; font-weight: 600; line-height: 1.1; color: var(--primary-text-color);
          font-variant-numeric: tabular-nums; letter-spacing: .5px; }
        .wt-arrow { flex: 0 0 auto; color: var(--secondary-text-color); --mdc-icon-size: 22px; }
        .hist { margin-top: 14px; }
        .hist-title { display: flex; justify-content: space-between; font-size: 11px; letter-spacing: .5px;
          text-transform: uppercase; color: var(--secondary-text-color); margin-bottom: 6px; }
        .bars { display: flex; gap: 6px; align-items: stretch; height: 64px; }
        .col { flex: 1 1 0; min-width: 0; display: flex; flex-direction: column; }
        .bar-track { flex: 1; display: flex; align-items: flex-end; justify-content: center; }
        .bar { width: 100%; max-width: 40px; border-radius: 4px 4px 2px 2px; min-height: 4px;
          background: var(--divider-color); transition: height .6s cubic-bezier(.4,0,.2,1), background .4s; }
        .day { height: 16px; line-height: 16px; text-align: center; font-size: 10px;
          color: var(--secondary-text-color); }
        .empty { width: 100%; text-align: center; font-size: 12px; color: var(--secondary-text-color);
          padding: 16px 0; }
        .warn { padding: 8px 4px; font-size: 13px; color: var(--secondary-text-color); }
      </style>
      <ha-card>
        <div class="head">
          <div class="shape"><ha-icon icon="mdi:sleep"></ha-icon></div>
          <div class="title" id="title"></div>
          <div class="pill" id="win"><span class="dot"></span><span id="wintxt"></span></div>
        </div>
        <div class="warn" id="warn" style="display:none"></div>
        <div class="ring-wrap" id="ring">
          <svg viewBox="0 0 140 140" aria-hidden="true">
            <circle class="track" cx="70" cy="70" r="54"></circle>
            <circle class="prog" id="prog" cx="70" cy="70" r="54"></circle>
          </svg>
          <div class="center">
            <div class="score" id="score">--</div>
            <div class="of" id="of"></div>
            <div class="status" id="status"></div>
          </div>
        </div>
        <div class="chips" id="chips">
          <div class="chip" id="chip-cont" style="display:none">
            <ha-icon icon="mdi:timer-sand"></ha-icon>
            <div style="min-width:0"><div class="val" id="cont-val">--</div><div class="lbl" id="cont-lbl"></div></div>
          </div>
          <div class="chip" id="chip-mov" style="display:none">
            <ha-icon icon="mdi:bed-clock"></ha-icon>
            <div style="min-width:0"><div class="val" id="mov-val">--</div><div class="lbl" id="mov-lbl"></div></div>
          </div>
          <div class="chip" id="chip-clu" style="display:none">
            <ha-icon icon="mdi:run-fast"></ha-icon>
            <div style="min-width:0"><div class="val" id="clu-val">--</div><div class="lbl" id="clu-lbl"></div></div>
          </div>
        </div>
        <div class="detail" id="detail" style="display:none"></div>
        <div class="wintime" id="wintime"></div>
        <div class="hist" id="hist">
          <div class="hist-title"><span id="hist-title"></span><span id="hist-avg"></span></div>
          <div class="bars" id="bars"></div>
        </div>
      </ha-card>`;

    const more = (entityId) => {
      if (!entityId) return;
      this.dispatchEvent(new CustomEvent("hass-more-info", {
        detail: { entityId }, bubbles: true, composed: true
      }));
    };
    const moreHandler = (ev) => {
      const el = ev.target && ev.target.closest ? ev.target.closest("[data-more]") : null;
      if (el) more(el.getAttribute("data-more"));
    };
    const sr = this.shadowRoot;
    sr.getElementById("ring").addEventListener("click", () => more(this._config.entity));
    sr.getElementById("wintime").addEventListener("click", moreHandler);
    sr.getElementById("chips").addEventListener("click", moreHandler);
    this._renderBars();
  }

  _setText(id, txt) {
    const el = this.shadowRoot.getElementById(id);
    if (el && el.textContent !== txt) el.textContent = txt;
  }

  _linkChip(el, ent) {
    if (el.getAttribute("data-more") !== ent) el.setAttribute("data-more", ent);
    el.classList.add("link");
  }

  _chip(id, ent, format) {
    const el = this.shadowRoot.getElementById("chip-" + id);
    const st = ent && this._hass.states[ent];
    const num = st ? parseFloat(st.state) : NaN;
    if (!st || isNaN(num)) {
      el.style.display = "none";
      return;
    }
    el.style.display = "";
    this._linkChip(el, ent);
    this._setText(id + "-val", format(num));
  }

  _fmtMinutes(m) {
    m = Math.max(0, Math.round(m));
    return m >= 60 ? Math.floor(m / 60) + "h " + String(m % 60).padStart(2, "0") + "m" : m + " min";
  }

  _update() {
    if (!this._built || !this._hass) return;
    const h = this._hass, c = this._config, sr = this.shadowRoot;
    const ents = this._ents();

    this._setText("title", c.name || this._t("default_title"));
    this._setText("of", this._t("out_of"));
    this._setText("cont-lbl", this._t("longest"));
    this._setText("mov-lbl", this._t("movements"));
    this._setText("clu-lbl", this._t("clusters"));

    const warn = sr.getElementById("warn");
    if (!c.entity || !h.states[c.entity]) {
      warn.style.display = "";
      this._setText("warn", this._t("no_entity"));
    } else {
      warn.style.display = "none";
    }

    const st = h.states[c.entity];
    const raw = st ? parseFloat(st.state) : NaN;
    const has = !isNaN(raw);
    const v = has ? Math.max(0, Math.min(100, raw)) : 0;
    const col = this._color(v);
    const ARC = 2 * Math.PI * 54 * 0.75, C = 2 * Math.PI * 54;
    const prog = sr.getElementById("prog");
    prog.style.strokeDasharray = `${(ARC * v / 100).toFixed(2)} ${C.toFixed(2)}`;
    prog.style.stroke = col;
    this._setText("score", has ? String(Math.round(v)) : "--");
    const status = sr.getElementById("status");
    this._setText("status", has ? this._label(v) : this._t("no_data"));
    status.style.color = has ? col : "var(--secondary-text-color)";

    const pill = sr.getElementById("win");
    const ws = ents.window_entity && h.states[ents.window_entity];
    if (ws) {
      const on = ws.state === "on";
      pill.style.display = "";
      pill.classList.toggle("on", on);
      this._setText("wintxt", on ? this._t("window_active") : this._t("window_inactive"));
    } else {
      pill.style.display = "none";
    }

    this._chip("cont", ents.continuity_entity, (n) => this._fmtMinutes(n));
    this._chip("mov", ents.movements_entity, (n) => String(Math.round(n)));
    this._chip("clu", ents.clusters_entity, (n) => String(Math.round(n)));

    this._renderBreakdown(st);
    this._renderWindow(ents);

    const hist = sr.getElementById("hist");
    hist.style.display = c.show_history === false ? "none" : "";
    this._setText("hist-title", this._t("last_days", { n: this._historyDays() }));
    const avgSt = ents.average_entity && h.states[ents.average_entity];
    const avg = avgSt ? parseFloat(avgSt.state) : NaN;
    this._setText("hist-avg", isNaN(avg) ? "" : this._t("avg", { v: Math.round(avg) }));
  }

  _renderBreakdown(st) {
    const el = this.shadowRoot.getElementById("detail");
    const comps = st && st.attributes && st.attributes.components;
    if (this._config.show_breakdown === false || !comps || typeof comps !== "object") {
      el.style.display = "none";
      return;
    }
    const max = (st.attributes.max_points) || { continuity: 30, movements: 25, wakeups: 20, calm: 15, intensity: 10 };
    const order = [
      ["continuity", "continuity"],
      ["movements", "movements_short"],
      ["wakeups", "wakeups"],
      ["calm", "calm"],
      ["intensity", "intensity"]
    ];
    const parts = [];
    for (const [k, label] of order) {
      if (comps[k] == null) continue;
      parts.push(`${this._t(label)} ${Math.round(Number(comps[k]))}/${max[k] != null ? max[k] : "?"}`);
    }
    if (st.attributes.neutral_signal) parts.push("(" + this._t("neutral_hint") + ")");
    const key = parts.join("|");
    el.style.display = parts.length ? "" : "none";
    if (el.getAttribute("data-key") === key) return;
    el.setAttribute("data-key", key);
    el.innerHTML = "";
    parts.forEach((p, i) => {
      if (i) el.appendChild(document.createTextNode(" · "));
      const span = document.createElement("span");
      span.className = "part";
      span.textContent = p;
      el.appendChild(span);
    });
  }

  _hhmm(v) {
    if (!v) return null;
    let m = String(v).match(/T(\d{2}:\d{2})/);
    if (m) return m[1];
    m = String(v).match(/^(\d{1,2}:\d{2})/);
    return m ? m[1].padStart(5, "0") : null;
  }

  _renderWindow(ents) {
    const el = this.shadowRoot.getElementById("wintime");
    const h = this._hass;
    const se = ents.window_start_entity, ee = ents.window_end_entity;
    const s = se && h.states[se] ? this._hhmm(h.states[se].state) : null;
    const e = ee && h.states[ee] ? this._hhmm(h.states[ee].state) : null;
    if (this._config.show_window === false || !s || !e) {
      el.style.display = "none";
      return;
    }
    el.style.display = "";
    const lang = langOf(h);
    if (el.getAttribute("data-built") !== lang) {
      el.innerHTML = `
        <div class="wt-head"></div>
        <div class="wt-row">
          <button class="wt-btn" id="wt-start" type="button">
            <span class="wt-lbl"><ha-icon icon="mdi:weather-night"></ha-icon><span id="wt-start-l"></span></span>
            <span class="wt-time" id="wt-start-t">--:--</span>
          </button>
          <ha-icon class="wt-arrow" icon="mdi:arrow-right"></ha-icon>
          <button class="wt-btn" id="wt-end" type="button">
            <span class="wt-lbl"><ha-icon icon="mdi:weather-sunny"></ha-icon><span id="wt-end-l"></span></span>
            <span class="wt-time" id="wt-end-t">--:--</span>
          </button>
        </div>`;
      el.querySelector(".wt-head").textContent = this._t("sleep_window");
      this.shadowRoot.getElementById("wt-start-l").textContent = this._t("start");
      this.shadowRoot.getElementById("wt-end-l").textContent = this._t("end");
      el.setAttribute("data-built", lang);
    }
    this.shadowRoot.getElementById("wt-start").setAttribute("data-more", se);
    this.shadowRoot.getElementById("wt-end").setAttribute("data-more", ee);
    this._setText("wt-start-t", s);
    this._setText("wt-end-t", e);
  }

  _historyDays() {
    return Math.max(3, Math.min(14, parseInt(this._config.history_days, 10) || 7));
  }

  async _fetchHistory() {
    const c = this._config;
    if (!c.entity || c.show_history === false || !this._hass || !this._hass.connection) return;
    const now = Date.now();
    const minGap = this._days && this._days.length ? 5 * 60 * 1000 : 20 * 1000;
    if (this._histBusy || now - (this._lastHist || 0) < minGap) return;
    this._histBusy = true;
    this._lastHist = now;

    const n = this._historyDays();
    const first = new Date();
    first.setHours(0, 0, 0, 0);
    first.setDate(first.getDate() - (n - 1));
    const startISO = new Date(first.getTime() - 864e5).toISOString();
    const endISO = new Date(now).toISOString();
    const ent = c.entity;
    const toMs = (x) => (typeof x === "number" ? (x < 1e12 ? x * 1000 : x) : Date.parse(x));
    const byDay = {};
    let ok = false;

    // 1) Long-term statistics (survive the recorder purge): the last hourly
    //    bucket of each day holds the score computed that morning.
    try {
      const res = await this._hass.connection.sendMessagePromise({
        type: "recorder/statistics_during_period",
        start_time: startISO,
        end_time: endISO,
        statistic_ids: [ent],
        period: "hour",
        types: ["mean"]
      });
      const rows = (res && res[ent]) || [];
      const last = {};
      for (const r of rows) {
        const d = new Date(toMs(r.start));
        if (isNaN(d.getTime()) || r.mean == null || isNaN(r.mean)) continue;
        const k = dayKey(d);
        if (!last[k] || d > last[k].d) last[k] = { d, v: Number(r.mean) };
      }
      for (const k of Object.keys(last)) byDay[k] = last[k].v;
      ok = true;
    } catch (e) {
      /* statistics not available yet */
    }

    // 2) Raw history with attributes: exact, keyed by the night_of attribute.
    try {
      const res = await this._hass.connection.sendMessagePromise({
        type: "history/history_during_period",
        start_time: startISO,
        end_time: endISO,
        entity_ids: [ent],
        minimal_response: false,
        no_attributes: false,
        significant_changes_only: false
      });
      const rows = (res && res[ent]) || [];
      for (const p of rows) {
        const val = parseFloat(p.s !== undefined ? p.s : p.state);
        if (isNaN(val)) continue;
        const attrs = p.a || p.attributes || {};
        let k = attrs.night_of;
        if (!k) {
          const d = new Date(toMs(p.lu != null ? p.lu : (p.lc != null ? p.lc : p.last_updated)));
          if (isNaN(d.getTime())) continue;
          k = dayKey(d);
        }
        byDay[k] = val;
      }
      ok = true;
    } catch (e) {
      /* history not available */
    }

    const firstKey = dayKey(first);
    this._days = Object.keys(byDay)
      .filter((k) => k >= firstKey)
      .sort()
      .map((k) => {
        const [y, m, d] = k.split("-").map(Number);
        return { date: new Date(y, m - 1, d, 12), value: byDay[k] };
      });
    this._histError = !ok;
    this._histBusy = false;
    this._renderBars();
  }

  _renderBars() {
    const el = this.shadowRoot && this.shadowRoot.getElementById("bars");
    if (!el) return;
    const days = this._days || [];
    el.innerHTML = "";
    if (!days.length) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = this._histError ? this._t("history_error") : this._t("no_history");
      el.appendChild(empty);
      return;
    }
    const TRACK = 48;
    const locale = (this._hass && ((this._hass.locale && this._hass.locale.language) || this._hass.language)) || "en";
    let wd;
    try {
      wd = new Intl.DateTimeFormat(locale, { weekday: "narrow" });
    } catch (e) {
      wd = new Intl.DateTimeFormat("en", { weekday: "narrow" });
    }
    for (const d of days) {
      const v = Math.max(0, Math.min(100, d.value));
      const col = document.createElement("div");
      col.className = "col";
      col.title = d.date.toLocaleDateString(locale, { day: "numeric", month: "numeric" }) + ": " + Math.round(d.value);
      const track = document.createElement("div");
      track.className = "bar-track";
      const bar = document.createElement("div");
      bar.className = "bar";
      bar.style.height = Math.max(4, Math.round(v / 100 * TRACK)) + "px";
      bar.style.background = this._color(v);
      track.appendChild(bar);
      const lbl = document.createElement("div");
      lbl.className = "day";
      lbl.textContent = wd.format(d.date);
      col.appendChild(track);
      col.appendChild(lbl);
      el.appendChild(col);
    }
  }
}

function editorSchema() {
  const ent = (domain) => ({ entity: { filter: [{ integration: INTEGRATION, domain }] } });
  return [
    { name: "entity", required: true, selector: ent("sensor") },
    { name: "name", selector: { text: {} } },
    { name: "history_days", selector: { number: { min: 3, max: 14, step: 1, mode: "slider" } } },
    {
      type: "grid",
      name: "",
      schema: [
        { name: "show_breakdown", selector: { boolean: {} } },
        { name: "show_window", selector: { boolean: {} } },
        { name: "show_history", selector: { boolean: {} } }
      ]
    }
  ];
}

const EDITOR_KEYS = [
  "entity", "name", "history_days", "show_breakdown", "show_window", "show_history"];

class BedSleepScoreCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = Object.assign({}, config);
    this._update();
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  async _update() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      await ensureHaForm();
      if (this._form) return;
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (s) => (s.name ? t(this._hass, "e_" + s.name) : "");
      this._form.addEventListener("value-changed", (ev) => {
        const v = ev.detail.value || {};
        const config = Object.assign({}, this._config);
        for (const k of EDITOR_KEYS) {
          if (v[k] === "" || v[k] === undefined || v[k] === null) delete config[k];
          else config[k] = v[k];
        }
        config.type = "custom:" + CARD_TAG;
        this._config = config;
        this.dispatchEvent(new CustomEvent("config-changed", {
          detail: { config: JSON.parse(JSON.stringify(config)) }, bubbles: true, composed: true
        }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = Object.assign(
      { history_days: 7, show_breakdown: true, show_window: true, show_history: true },
      this._config
    );
    this._form.schema = editorSchema();
  }
}

if (!customElements.get(EDITOR_TAG)) customElements.define(EDITOR_TAG, BedSleepScoreCardEditor);
if (!customElements.get(CARD_TAG)) {
  customElements.define(CARD_TAG, BedSleepScoreCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: CARD_TAG,
    name: t(null, "card_name"),
    description: t(null, "card_description"),
    preview: true,
    documentationURL: "https://github.com/artech-lab/ha-bed-sleep-score"
  });
  console.info(
    `%c BED-SLEEP-SCORE-CARD %c v${CARD_VERSION} `,
    "color:#fff;background:#3f51b5;font-weight:700;border-radius:3px 0 0 3px",
    "color:#3f51b5;background:#e8eaf6;font-weight:700;border-radius:0 3px 3px 0"
  );
}
