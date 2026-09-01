/* ProcEasy Clipboard Assistant -- floating, draggable dot that expands into a
 * minimalist card listing the deduplicated invoice line items, each field with
 * a one-click Copy button. Rendered inside a Shadow DOM so host-page CSS never
 * bleeds into the widget (and vice versa). */
(() => {
  "use strict";

  // Guard against double injection (SPA re-navigation, repeated injects).
  if (window.__proceasyExtLoaded) return;
  window.__proceasyExtLoaded = true;

  const DOT_SIZE = 52;
  const MARGIN = 20;

  // Fields pulled from each deduplicated row, in display order.
  const FIELDS = [
    ["Name", "item_name"],
    ["Qty", "quantity"],
    ["Average Price", "unit_price"],
    ["Description", "description"],
  ];

  const CSS = `
    * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
    .dot {
      position: fixed; width: ${DOT_SIZE}px; height: ${DOT_SIZE}px; border-radius: 50%;
      background: #2563eb; box-shadow: 0 6px 18px rgba(37,99,235,.45);
      display: flex; align-items: center; justify-content: center;
      color: #fff; font-weight: 700; font-size: 13px; letter-spacing: .02em;
      cursor: grab; user-select: none; touch-action: none;
      transition: transform .12s ease, box-shadow .12s ease;
    }
    .dot:hover { transform: scale(1.06); box-shadow: 0 8px 22px rgba(37,99,235,.55); }
    .dot:active { cursor: grabbing; }
    .card {
      position: fixed; width: 320px; max-height: 70vh;
      background: #fff; border: 1px solid #e5e7eb; border-radius: 14px;
      box-shadow: 0 12px 40px rgba(15,23,42,.22); overflow: hidden;
      display: none; flex-direction: column;
    }
    .card.open { display: flex; }
    .card__header {
      display: flex; align-items: center; justify-content: space-between;
      padding: 12px 14px; background: #2563eb; color: #fff;
    }
    .card__title { font-size: 14px; font-weight: 600; }
    .card__close {
      cursor: pointer; background: transparent; border: 0; color: #fff;
      font-size: 20px; line-height: 1; padding: 0 2px;
    }
    .card__body { padding: 8px 12px 12px; overflow-y: auto; }
    .item { padding: 10px 0; border-bottom: 1px solid #f1f5f9; }
    .item:last-child { border-bottom: 0; }
    .item__name { font-size: 12px; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 6px; }
    .field { display: flex; align-items: center; gap: 8px; padding: 3px 0; }
    .field__label { flex: 0 0 92px; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; color: #64748b; }
    .field__value { flex: 1 1 auto; font-size: 12.5px; color: #0f172a; word-break: break-word; }
    .copy {
      flex: 0 0 auto; cursor: pointer; border: 1px solid #cbd5e1; background: #f8fafc;
      color: #2563eb; border-radius: 6px; padding: 3px 9px; font-size: 11px; font-weight: 600;
    }
    .copy:hover { background: #eff6ff; }
    .copy.copied { color: #16a34a; border-color: #bbf7d0; background: #f0fdf4; }
    .card__msg { padding: 14px; color: #64748b; font-size: 12.5px; }
  `;

  // --- Shadow-DOM host -------------------------------------------------- //
  const host = document.createElement("div");
  host.id = "proceasy-ext-root";
  host.style.position = "fixed";
  host.style.top = "0";
  host.style.left = "0";
  host.style.zIndex = "2147483647";
  const shadow = host.attachShadow({ mode: "open" });
  (document.body || document.documentElement).appendChild(host);

  const style = document.createElement("style");
  style.textContent = CSS;
  shadow.appendChild(style);

  // --- Dot -------------------------------------------------------------- //
  const dot = document.createElement("div");
  dot.className = "dot";
  dot.textContent = "PE";
  dot.title = "ProcEasy line items";
  dot.style.left = `${window.innerWidth - DOT_SIZE - MARGIN}px`;
  dot.style.top = `${Math.round(window.innerHeight / 2 - DOT_SIZE / 2)}px`;
  shadow.appendChild(dot);

  // --- Card ------------------------------------------------------------- //
  const card = document.createElement("div");
  card.className = "card";
  const header = document.createElement("div");
  header.className = "card__header";
  const title = document.createElement("span");
  title.className = "card__title";
  title.textContent = "ProcEasy · Line Items";
  const close = document.createElement("button");
  close.className = "card__close";
  close.type = "button";
  close.textContent = "×";
  close.addEventListener("click", () => card.classList.remove("open"));
  header.append(title, close);
  const body = document.createElement("div");
  body.className = "card__body";
  card.append(header, body);
  shadow.appendChild(card);

  // --- Drag + click-to-toggle ------------------------------------------ //
  let dragging = false, moved = false, sx = 0, sy = 0, ox = 0, oy = 0;

  dot.addEventListener("pointerdown", (e) => {
    dragging = true;
    moved = false;
    sx = e.clientX;
    sy = e.clientY;
    const r = dot.getBoundingClientRect();
    ox = e.clientX - r.left;
    oy = e.clientY - r.top;
    dot.setPointerCapture(e.pointerId);
  });

  dot.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    if (Math.abs(e.clientX - sx) > 4 || Math.abs(e.clientY - sy) > 4) moved = true;
    let left = e.clientX - ox;
    let top = e.clientY - oy;
    left = Math.max(MARGIN, Math.min(left, window.innerWidth - DOT_SIZE - MARGIN));
    top = Math.max(MARGIN, Math.min(top, window.innerHeight - DOT_SIZE - MARGIN));
    dot.style.left = `${left}px`;
    dot.style.top = `${top}px`;
    if (card.classList.contains("open")) positionCard();
  });

  dot.addEventListener("pointerup", (e) => {
    dragging = false;
    try { dot.releasePointerCapture(e.pointerId); } catch (_) {}
    if (!moved) toggleCard();  // a real click (no drag) toggles the card
  });

  function toggleCard() {
    const open = !card.classList.contains("open");
    card.classList.toggle("open", open);
    if (open) positionCard();
  }

  function positionCard() {
    const r = dot.getBoundingClientRect();
    const cw = card.offsetWidth || 320;
    const ch = card.offsetHeight || 320;
    let left = r.left - cw - 12;                       // prefer left of the dot
    if (left < MARGIN) left = Math.min(r.right + 12, window.innerWidth - cw - MARGIN);
    let top = Math.max(MARGIN, Math.min(r.top, window.innerHeight - ch - MARGIN));
    card.style.left = `${left}px`;
    card.style.top = `${top}px`;
  }

  window.addEventListener("resize", () => {
    const left = Math.min(parseFloat(dot.style.left) || 0, window.innerWidth - DOT_SIZE - MARGIN);
    const top = Math.min(parseFloat(dot.style.top) || 0, window.innerHeight - DOT_SIZE - MARGIN);
    dot.style.left = `${Math.max(MARGIN, left)}px`;
    dot.style.top = `${Math.max(MARGIN, top)}px`;
    if (card.classList.contains("open")) positionCard();
  });

  // --- Clipboard -------------------------------------------------------- //
  async function copyText(value, btn) {
    const text = String(value == null ? "" : value);
    try {
      await navigator.clipboard.writeText(text);
    } catch (_) {
      // Fallback for non-secure contexts / blocked async clipboard.
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      (document.body || document.documentElement).appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); } catch (__) {}
      ta.remove();
    }
    const prev = btn.textContent;
    btn.textContent = "Copied";
    btn.classList.add("copied");
    setTimeout(() => { btn.textContent = prev; btn.classList.remove("copied"); }, 1000);
  }

  // --- Render ----------------------------------------------------------- //
  function buildField(label, rawValue) {
    const value = rawValue == null ? "" : String(rawValue);
    const row = document.createElement("div");
    row.className = "field";
    const lab = document.createElement("span");
    lab.className = "field__label";
    lab.textContent = label;
    const val = document.createElement("span");
    val.className = "field__value";
    val.textContent = value || "—";
    const btn = document.createElement("button");
    btn.className = "copy";
    btn.type = "button";
    btn.textContent = "Copy";
    btn.addEventListener("click", (e) => { e.stopPropagation(); copyText(value, btn); });
    row.append(lab, val, btn);
    return row;
  }

  function renderItems(items) {
    body.textContent = "";
    if (!items.length) {
      const msg = document.createElement("div");
      msg.className = "card__msg";
      msg.textContent = "No line items found in the data layout.";
      body.appendChild(msg);
      return;
    }
    items.forEach((item, i) => {
      const wrap = document.createElement("div");
      wrap.className = "item";
      const name = document.createElement("div");
      name.className = "item__name";
      name.textContent = `Item ${i + 1}`;
      wrap.appendChild(name);
      FIELDS.forEach(([label, key]) => wrap.appendChild(buildField(label, item[key])));
      body.appendChild(wrap);
    });
  }

  function renderMessage(text) {
    body.textContent = "";
    const msg = document.createElement("div");
    msg.className = "card__msg";
    msg.textContent = text;
    body.appendChild(msg);
  }

  // Load the deduplicated data layout bundled with the extension.
  fetch(chrome.runtime.getURL("data.json"))
    .then((r) => r.json())
    .then((data) => renderItems((data && data.items) || []))
    .catch(() => renderMessage("Could not load data.json."));
})();
