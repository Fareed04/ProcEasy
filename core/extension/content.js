/* ProcEasy Clipboard Assistant -- assistive floating widget.
 * AssistiveTouch-style dot (idle fade + conic loading ring) that expands into a
 * drag-and-drop invoice card. Files arrive by drop, file-picker, or Ctrl+V while
 * hovered; each is POSTed to the local Django upload view. Returned fields render
 * as draggable chips whose dragstart payload is the raw value string.
 * Shadow-DOM isolated so host-page CSS never bleeds in. */
(() => {
  "use strict";

  if (window.__proceasyExtLoaded) return;
  window.__proceasyExtLoaded = true;

  const DOT_SIZE = 44;                 // shrunken AssistiveTouch puck
  const MARGIN = 20;
  const IDLE_MS = 5000;                // fade after 5s untouched
  const DJANGO_UPLOAD_URL = "http://127.0.0.1:8000/?format=json";  // pdf_upload view
  const STORAGE_KEY = "proceasy_invoice";  // chrome.storage.local key for cross-tab data

  // Field label -> dedup-layout key, in display order.
  const ITEM_FIELDS = [
    ["Name", "item_name"],
    ["Qty", "quantity"],
    ["Average Price", "unit_price"],
    ["Description", "description"],
  ];

  const CSS = `
    * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }

    /* --- AssistiveTouch dot --- */
    .at-dot {
      position: fixed; width: ${DOT_SIZE}px; height: ${DOT_SIZE}px; border-radius: 24%;
      background: rgba(28,30,38,.55); backdrop-filter: blur(7px); -webkit-backdrop-filter: blur(7px);
      display: flex; align-items: center; justify-content: center;
      cursor: grab; user-select: none; touch-action: none;
      box-shadow: 0 2px 12px rgba(0,0,0,.38);
      opacity: 1; transition: opacity .55s ease, transform .12s ease;
    }
    .at-dot:active { cursor: grabbing; }
    .at-dot.idle:not(:hover) { opacity: .4; }
    .at-dot__ring {
      width: 24px; height: 24px; border-radius: 30%;
      background: rgba(255,255,255,.14); border: 2px solid rgba(255,255,255,.9);
      box-shadow: 0 0 0 4px rgba(255,255,255,.14);
    }
    /* Conic-gradient spinning loading ring */
    .at-dot::before {
      content: ""; position: absolute; inset: -4px; border-radius: 50%;
      background: conic-gradient(from 0deg, rgba(10,132,255,0), rgba(10,132,255,.2) 35%, #0a84ff);
      -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 3px), #000 calc(100% - 3px));
              mask: radial-gradient(farthest-side, transparent calc(100% - 3px), #000 calc(100% - 3px));
      opacity: 0; transition: opacity .2s ease; pointer-events: none;
    }
    .at-dot.loading::before { opacity: 1; animation: at-spin .9s linear infinite; }
    @keyframes at-spin { to { transform: rotate(360deg); } }

    /* Snap-to-edge easing -- present only while settling so live dragging stays instant */
    .at-dot.snapping { transition: opacity .55s ease, transform .12s ease,
      left .28s cubic-bezier(.22,1,.36,1), top .28s cubic-bezier(.22,1,.36,1); }
    /* File dragged directly over the resting puck */
    .at-dot.dropping { transform: scale(1.15);
      box-shadow: 0 0 0 3px rgba(10,132,255,.6), 0 2px 12px rgba(0,0,0,.38); }

    /* --- Card --- */
    .card {
      position: fixed; width: 330px; max-height: 72vh; font-size: 16px;
      background: #fff; border: 1px solid #e5e7eb; border-radius: 14px;
      box-shadow: 0 14px 44px rgba(15,23,42,.24); overflow: hidden;
      display: none; flex-direction: column;
    }
    .card.open { display: flex; }
    .card__header { display: flex; align-items: center; justify-content: space-between; padding: 12px 14px; background: #0f172a; color: #fff; }
    .card__title { font-size: 20px; font-weight: 600; }
    .card__close { cursor: pointer; background: transparent; border: 0; color: #fff; font-size: 20px; line-height: 1; padding: 0 2px; }
    .card__body { padding: 12px; overflow-y: auto; }

    /* --- Dropzone --- */
    .dropzone {
      border: 2px dashed #93c5fd; border-radius: 12px; padding: 30px 16px; text-align: center;
      color: #475569; background: #f8fafc; cursor: pointer; transition: background .15s ease, border-color .15s ease;
    }
    .dropzone.dragover { background: #eff6ff; border-color: #2563eb; color: #2563eb; }
    .dropzone__title { font-size: 16px; font-weight: 600; }
    .dropzone__hint { font-size: 12px; margin-top: 8px; color: #94a3b8; }

    /* --- Grid --- */
    .gridbar { display: flex; justify-content: flex-end; margin-bottom: 6px; }
    .linkbtn { cursor: pointer; background: transparent; border: 0; color: #2563eb; font-size: 12px; font-weight: 600; }
    .note { font-size: 12px; color: #64748b; background: #f1f5f9; border-radius: 8px; padding: 7px 10px; margin-bottom: 10px; }
    .item { padding: 10px 0; border-bottom: 1px solid #f1f5f9; }
    .item:last-child { border-bottom: 0; }
    .item__name { font-size: 12px; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 6px; }
    .field { display: flex; align-items: center; gap: 8px; padding: 3px 0; }
    .field__label { flex: 0 0 92px; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: #64748b; }
    .field__value { flex: 1 1 auto; font-size: 16px; color: #0f172a; word-break: break-word; cursor: grab; border-radius: 5px; padding: 1px 4px; }
    .field__value:hover { background: #eff6ff; }
    .field__value:active { cursor: grabbing; }
    .copy { flex: 0 0 auto; cursor: pointer; border: 1px solid #cbd5e1; background: #f8fafc; color: #2563eb; border-radius: 6px; padding: 3px 9px; font-size: 12px; font-weight: 600; }
    .copy:hover { background: #eff6ff; }
    .copy.copied { color: #16a34a; border-color: #bbf7d0; background: #f0fdf4; }
  `;

  // --- Shadow host --- //
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

  // Hidden native file picker (click-to-browse).
  const filePicker = document.createElement("input");
  filePicker.type = "file";
  filePicker.accept = "application/pdf,.pdf";
  filePicker.style.display = "none";
  filePicker.addEventListener("change", () => {
    const f = filePicker.files && filePicker.files[0];
    if (f) uploadFile(f);
    filePicker.value = "";
  });
  shadow.appendChild(filePicker);

  // --- Dot --- //
  const dot = document.createElement("div");
  dot.className = "at-dot";
  dot.title = "ProcEasy assistant";
  const ring = document.createElement("div");
  ring.className = "at-dot__ring";
  dot.appendChild(ring);
  dot.style.left = `${window.innerWidth - DOT_SIZE - MARGIN}px`;
  dot.style.top = `${Math.round(window.innerHeight / 2 - DOT_SIZE / 2)}px`;
  shadow.appendChild(dot);

  // --- Card --- //
  const card = document.createElement("div");
  card.className = "card";
  const header = document.createElement("div");
  header.className = "card__header";
  const title = document.createElement("span");
  title.className = "card__title";
  title.textContent = "ProcEasy · Invoice Capture";
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

  // Card body is always a drop target (works whether empty or showing data).
  body.addEventListener("dragover", (e) => e.preventDefault());
  body.addEventListener("drop", (e) => {
    e.preventDefault();
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) uploadFile(f);
  });

  // --- Idle fade + hover state --- //
  let hovered = false;
  let idleTimer = null;

  function wakeDot() {
    dot.classList.remove("idle");
    clearTimeout(idleTimer);
    idleTimer = setTimeout(() => dot.classList.add("idle"), IDLE_MS);
  }
  host.addEventListener("mouseenter", () => { hovered = true; wakeDot(); });
  host.addEventListener("mouseleave", () => { hovered = false; });
  wakeDot();

  // --- Drag dot + click-to-toggle --- //
  let dragging = false, moved = false, sx = 0, sy = 0, ox = 0, oy = 0;

  dot.addEventListener("pointerdown", (e) => {
    dragging = true; moved = false; sx = e.clientX; sy = e.clientY;
    dot.classList.remove("snapping");
    const r = dot.getBoundingClientRect();
    ox = e.clientX - r.left; oy = e.clientY - r.top;
    dot.setPointerCapture(e.pointerId);
    wakeDot();
  });
  dot.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    if (Math.abs(e.clientX - sx) > 4 || Math.abs(e.clientY - sy) > 4) moved = true;
    let left = Math.max(MARGIN, Math.min(e.clientX - ox, window.innerWidth - DOT_SIZE - MARGIN));
    let top = Math.max(MARGIN, Math.min(e.clientY - oy, window.innerHeight - DOT_SIZE - MARGIN));
    dot.style.left = `${left}px`;
    dot.style.top = `${top}px`;
    if (card.classList.contains("open")) positionCard();
    wakeDot();
  });
  dot.addEventListener("pointerup", (e) => {
    dragging = false;
    try { dot.releasePointerCapture(e.pointerId); } catch (_) {}
    if (!moved) toggleCard(); else snapDotToEdge();
  });

  // Direct puck dropping: dropping a file straight onto the resting dot fires
  // the spinner + upload without opening the card first.
  dot.addEventListener("dragover", (e) => {
    e.preventDefault();
    if (e.dataTransfer) e.dataTransfer.dropEffect = "copy";
    dot.classList.add("dropping");
  });
  dot.addEventListener("dragleave", () => dot.classList.remove("dropping"));
  dot.addEventListener("drop", (e) => {
    e.preventDefault();
    dot.classList.remove("dropping");
    const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) { setLoading(true); uploadFile(f); }
  });

  function toggleCard() {
    const open = !card.classList.contains("open");
    card.classList.toggle("open", open);
    if (open) { positionCard(); if (!body.childElementCount) renderEmpty(); }
  }
  function openCard() {
    if (!card.classList.contains("open")) { card.classList.add("open"); positionCard(); }
  }
  function positionCard() {
    const r = dot.getBoundingClientRect();
    const cw = card.offsetWidth || 330;
    const ch = card.offsetHeight || 340;
    let left = r.left - cw - 12;
    if (left < MARGIN) left = Math.min(r.right + 12, window.innerWidth - cw - MARGIN);
    const top = Math.max(MARGIN, Math.min(r.top, window.innerHeight - ch - MARGIN));
    card.style.left = `${left}px`;
    card.style.top = `${top}px`;
  }

  // Settle the puck against whichever vertical edge is nearer, animating with the
  // temporary `.snapping` transition; the card (if open) is glued along the way.
  function snapDotToEdge() {
    const r = dot.getBoundingClientRect();
    const toRight = (r.left + DOT_SIZE / 2) >= window.innerWidth / 2;
    const targetLeft = toRight ? window.innerWidth - DOT_SIZE - MARGIN : MARGIN;
    dot.classList.add("snapping");
    dot.style.left = `${targetLeft}px`;

    let settling = true;
    const follow = () => {
      if (!settling) return;
      if (card.classList.contains("open")) positionCard();
      requestAnimationFrame(follow);
    };
    requestAnimationFrame(follow);

    const done = (ev) => {
      if (ev && ev.propertyName && ev.propertyName !== "left") return;  // ignore opacity/transform ticks
      settling = false;
      dot.classList.remove("snapping");
      if (card.classList.contains("open")) positionCard();
      dot.removeEventListener("transitionend", done);
    };
    dot.addEventListener("transitionend", done);
    setTimeout(done, 360);  // fallback if transitionend never lands
  }

  window.addEventListener("resize", () => {
    const left = Math.max(MARGIN, Math.min(parseFloat(dot.style.left) || 0, window.innerWidth - DOT_SIZE - MARGIN));
    const top = Math.max(MARGIN, Math.min(parseFloat(dot.style.top) || 0, window.innerHeight - DOT_SIZE - MARGIN));
    dot.style.left = `${left}px`;
    dot.style.top = `${top}px`;
    if (card.classList.contains("open")) positionCard();
  });

  // --- Ctrl+V clipboard capture (only while the widget is hovered) --- //
  // Ctrl+V produces a native `paste` event carrying the clipboard file stream.
  window.addEventListener("paste", (e) => {
    if (!hovered) return;
    const dt = e.clipboardData;
    if (!dt) return;
    if (dt.files && dt.files.length) { e.preventDefault(); openCard(); uploadFile(dt.files[0]); return; }
    if (dt.items) {
      for (let i = 0; i < dt.items.length; i++) {
        if (dt.items[i].kind === "file") {
          const f = dt.items[i].getAsFile();
          if (f) { e.preventDefault(); openCard(); uploadFile(f); return; }
        }
      }
    }
  }, true);

  // Explicit keyboard hook (spec): Ctrl/Cmd+V over the dot -> async clipboard read.
  window.addEventListener("keydown", (e) => {
    if (!hovered) return;
    if ((e.ctrlKey || e.metaKey) && (e.key === "v" || e.key === "V")) tryClipboardRead();
  });

  async function tryClipboardRead() {
    if (!navigator.clipboard || !navigator.clipboard.read) return;
    try {
      const items = await navigator.clipboard.read();
      for (const it of items) {
        const type = it.types.find((t) => t === "application/pdf" || t.indexOf("image/") === 0);
        if (type) {
          const blob = await it.getType(type);
          const name = "clipboard-invoice" + (type.indexOf("pdf") >= 0 ? ".pdf" : ".png");
          openCard();
          uploadFile(new File([blob], name, { type }));
          return;
        }
      }
    } catch (_) { /* blocked; the paste-event path still handles pasted files */ }
  }

  // --- Upload -> Django extraction pipeline --- //
  function setLoading(on) { dot.classList.toggle("loading", !!on); }

  async function uploadFile(file) {
    if (!file) return;
    openCard();
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append("pdf_file", file, file.name || "invoice.pdf");
      // localhost is treated as a secure context, so this is allowed from https
      // pages too. The dev view may need CSRF exemption for the extension origin.
      const res = await fetch(DJANGO_UPLOAD_URL, { method: "POST", body: fd });
      let data = null;
      try { data = await res.clone().json(); } catch (_) { data = null; }
      if (data && (data.items || data.invoice)) {
        renderData(data);
        persistData(data);
      } else {
        // Current pdf_upload view answers with an HTML redirect, not JSON; fall
        // back to the bundled dedup layout so the draggable grid still renders.
        renderData(await loadBundled(), `Uploaded "${file.name}" · showing sample layout`);
      }
    } catch (err) {
      renderData(await loadBundled().catch(() => ({})), `Upload failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  function loadBundled() {
    return fetch(chrome.runtime.getURL("data.json")).then((r) => r.json());
  }

  // --- Cross-tab persistence (chrome.storage.local) --- //
  // Extracted data is stashed on success and rehydrated on load, so a parse in
  // one tab shows up in every other tab's sidebar grid.
  let lastStored = null;  // JSON of our own last write, to ignore the echo below

  function persistData(data) {
    try {
      lastStored = JSON.stringify(data);
      chrome.storage.local.set({ [STORAGE_KEY]: data });
    } catch (_) {}
  }
  function clearPersisted() {
    lastStored = null;
    try { chrome.storage.local.remove(STORAGE_KEY); } catch (_) {}
  }
  function restoreData() {
    try {
      chrome.storage.local.get(STORAGE_KEY, (res) => {
        const data = res && res[STORAGE_KEY];
        if (data && (data.items || data.invoice)) renderData(data);
      });
    } catch (_) {}
  }
  // Live-sync tabs already open when another tab stores a fresh extraction.
  try {
    chrome.storage.onChanged.addListener((changes, area) => {
      if (area !== "local" || !changes[STORAGE_KEY]) return;
      const nv = changes[STORAGE_KEY].newValue;
      if (!nv || JSON.stringify(nv) === lastStored) return;  // gone, or our own echo
      if (nv.items || nv.invoice) renderData(nv);
    });
  } catch (_) {}

  // --- Clipboard copy --- //
  async function copyText(value, btn) {
    const text = String(value == null ? "" : value);
    try {
      await navigator.clipboard.writeText(text);
    } catch (_) {
      const ta = document.createElement("textarea");
      ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
      (document.body || document.documentElement).appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); } catch (__) {}
      ta.remove();
    }
    const prev = btn.textContent;
    btn.textContent = "Copied"; btn.classList.add("copied");
    setTimeout(() => { btn.textContent = prev; btn.classList.remove("copied"); }, 1000);
  }

  // --- Rendering --- //
  function buildDropzone() {
    const dz = document.createElement("div");
    dz.className = "dropzone";
    const t = document.createElement("div");
    t.className = "dropzone__title";
    t.textContent = "Drop Invoice PDF Here";
    const h = document.createElement("div");
    h.className = "dropzone__hint";
    h.textContent = "or click to browse · or hover the dot and press Ctrl+V";
    dz.append(t, h);
    dz.addEventListener("click", () => filePicker.click());
    dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("dragover"); });
    dz.addEventListener("dragleave", () => dz.classList.remove("dragover"));
    dz.addEventListener("drop", (e) => {
      e.preventDefault(); dz.classList.remove("dragover");
      const f = e.dataTransfer.files && e.dataTransfer.files[0];
      if (f) uploadFile(f);
    });
    return dz;
  }

  // A draggable value chip: dragstart payload == the raw value string, so it can
  // be dropped straight into any web input/textarea.
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
    val.setAttribute("draggable", "true");
    val.title = "Drag into any form field";
    val.addEventListener("dragstart", (e) => {
      e.dataTransfer.setData("text/plain", value);
      e.dataTransfer.effectAllowed = "copy";
      chipDragging = true; lastActivated = null;  // arm the grid-cell wake-up below
    });
    val.addEventListener("dragend", endChipDrag);
    const btn = document.createElement("button");
    btn.className = "copy";
    btn.type = "button";
    btn.textContent = "Copy";
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      activeClipboardBuffer = value;  // stage this chip for click-to-inject into the next field
      copyText(value, btn);
    });
    row.append(lab, val, btn);
    return row;
  }

  function renderEmpty() {
    body.textContent = "";
    body.appendChild(buildDropzone());
    clearPersisted();  // starting fresh -> drop the stored invoice for all tabs
  }

  function renderData(data, note) {
    const items = (data && data.items) || [];
    const vendor = data && data.invoice ? data.invoice.vendor : "";
    if (!vendor && !items.length) { renderEmpty(); return; }

    body.textContent = "";

    const bar = document.createElement("div");
    bar.className = "gridbar";
    const newBtn = document.createElement("button");
    newBtn.type = "button";
    newBtn.className = "linkbtn";
    newBtn.textContent = "＋ New invoice";
    newBtn.addEventListener("click", renderEmpty);
    bar.appendChild(newBtn);
    body.appendChild(bar);

    if (note) {
      const n = document.createElement("div");
      n.className = "note";
      n.textContent = note;
      body.appendChild(n);
    }

    if (vendor) {
      const v = document.createElement("div");
      v.className = "item";
      const l = document.createElement("div");
      l.className = "item__name";
      l.textContent = "Vendor";
      v.appendChild(l);
      v.appendChild(buildField("Vendor", vendor));
      body.appendChild(v);
    }

    items.forEach((item, i) => {
      const wrap = document.createElement("div");
      wrap.className = "item";
      const name = document.createElement("div");
      name.className = "item__name";
      name.textContent = `Item ${i + 1}`;
      wrap.appendChild(name);
      ITEM_FIELDS.forEach(([l, k]) => wrap.appendChild(buildField(l, item[k])));
      body.appendChild(wrap);
    });
  }

  // --- Grid-cell wake-up during chip drag --------------------------------- //
  // Some ERP grids (AG-Grid / Handsontable-style) render a cell as static text
  // and only swap in the real <input>/<textarea> editor once the cell is
  // clicked. A plain HTML5 text drop lands on that dead cell and is ignored.
  // So while one of OUR chips is airborne, we focus()+click() the editable
  // target the cursor is over to spin up the row's editor before the drop lands.
  //
  // Three guards keep this from misfiring on the host page:
  //   1. armed ONLY while a ProcEasy chip is mid-drag (chipDragging),
  //   2. fires ONCE per target on entry, not on every dragover tick, and
  //   3. wakes ONLY editable targets -- never buttons, links, or input types
  //      (submit/checkbox/file/...) where a synthetic click has a side effect.
  const dragActivationListeners = [];  // [target, type, handler] registry
  let chipDragging = false;            // true only while a ProcEasy chip is airborne
  let lastActivated = null;            // last woken element, so we fire once per cell

  // Input types where a click does something other than place a caret -- left alone.
  const UNSAFE_INPUT_TYPES = new Set(
    ["button", "submit", "reset", "checkbox", "radio", "file", "image", "color", "range"]);

  // Walk up from the hovered node to the nearest editable cell we're willing to
  // wake; returns null (leave it be) for anything non-editable or side-effecting.
  function activatableTarget(node) {
    for (let el = node; el && el.nodeType === 1; el = el.parentElement) {
      const tag = el.tagName;
      if (tag === "TEXTAREA") return el;
      if (tag === "INPUT" && !UNSAFE_INPUT_TYPES.has((el.type || "text").toLowerCase())) return el;
      if (el.isContentEditable) return el;
      if (el.getAttribute && el.getAttribute("role") === "gridcell") return el;
    }
    return null;
  }

  function wakeDropTarget(e) {
    if (!chipDragging) return;
    const node = (e.target && e.target.nodeType === 1)
      ? e.target
      : document.elementFromPoint(e.clientX, e.clientY);
    const target = activatableTarget(node);
    if (!target || target === lastActivated) return;  // once per cell entry
    lastActivated = target;
    try { target.focus({ preventScroll: true }); } catch (_) { try { target.focus(); } catch (__) {} }
    try { target.click(); } catch (_) {}
    // No preventDefault: native inputs keep their built-in text-drop behaviour.
  }

  function endChipDrag() { chipDragging = false; lastActivated = null; }

  function addDragActivation(target, type, handler) {
    target.addEventListener(type, handler, true);  // capture: run ahead of page handlers
    dragActivationListeners.push([target, type, handler]);
  }
  addDragActivation(document, "dragenter", wakeDropTarget);
  addDragActivation(document, "dragover", wakeDropTarget);
  addDragActivation(document, "drop", endChipDrag);
  addDragActivation(document, "dragend", endChipDrag);

  // --- Click-to-Inject ----------------------------------------------------- //
  // Companion path for ERPs that reject native HTML text-drop payloads on their
  // fields. Clicking a chip's "Copy" stages its value in activeClipboardBuffer;
  // the next click into an editable ERP field writes that value in and fires
  // input/change so controlled components (and dependent totals) recompute.
  // One-shot: the buffer clears itself after a single injection.
  const clickInjectionListeners = [];  // registry, parallels dragActivationListeners
  let activeClipboardBuffer = null;    // value staged by a "Copy" click, or null

  // Set a value the way a framework-controlled input expects: through the
  // prototype's native setter, so React/Vue value trackers actually see it.
  function setNativeValue(el, value) {
    const proto = el instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const desc = Object.getOwnPropertyDescriptor(proto, "value");
    if (desc && desc.set) desc.set.call(el, value); else el.value = value;
  }

  function injectInto(el, value) {
    if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) setNativeValue(el, value);
    else if (el.isContentEditable) el.textContent = value;
    else return false;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }

  // Nearest editable target for the clicked node (same allow-list as the drag
  // path -- no buttons/links/side-effecting input types).
  function resolveInjectTarget(node) {
    for (let el = node; el && el.nodeType === 1; el = el.parentElement) {
      if (el instanceof HTMLTextAreaElement) return el;
      if (el instanceof HTMLInputElement)
        return UNSAFE_INPUT_TYPES.has((el.type || "text").toLowerCase()) ? null : el;
      if (el.isContentEditable) return el;
      if (el.getAttribute && el.getAttribute("role") === "gridcell") return el;
    }
    return null;
  }

  function onInjectClick(e) {
    if (activeClipboardBuffer == null) return;
    const hit = resolveInjectTarget(e.target);
    if (!hit) return;
    const value = activeClipboardBuffer;
    activeClipboardBuffer = null;  // one-shot: consume the staged value
    // NB: we do NOT stopPropagation/preventDefault -- the grid still needs its
    // own click to spin up the cell editor. So defer the write one tick and
    // re-resolve to the live editor (or the now-focused input) before injecting.
    setTimeout(() => {
      let target = hit;
      const editable = hit instanceof HTMLInputElement
        || hit instanceof HTMLTextAreaElement || hit.isContentEditable;
      if (!editable) {
        target = hit.querySelector("input, textarea, [contenteditable=''], [contenteditable=true]")
          || (document.activeElement && document.activeElement !== document.body ? document.activeElement : null);
      }
      if (target) injectInto(target, value);
    }, 0);
  }

  function addClickInjection(target, type, handler) {
    target.addEventListener(type, handler, true);  // capture, per spec
    clickInjectionListeners.push([target, type, handler]);
  }
  addClickInjection(document, "click", onInjectClick);

  // Rehydrate any invoice a prior tab/session parsed, once everything is wired up.
  restoreData();
})();
