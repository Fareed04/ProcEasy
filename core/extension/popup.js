/* ProcEasy popup -- toolbar surface mirroring the injected card:
 * drop / browse an invoice PDF, POST it to the local Django upload view, and
 * render returned fields as draggable chips (dragstart payload = value). */
(() => {
  "use strict";

  const DJANGO_UPLOAD_URL = "http://127.0.0.1:8000/";
  const ITEM_FIELDS = [
    ["Name", "item_name"],
    ["Qty", "quantity"],
    ["Average Price", "unit_price"],
    ["Description", "description"],
  ];

  const view = document.getElementById("view");
  const spin = document.getElementById("spin");
  const picker = document.getElementById("picker");

  picker.addEventListener("change", () => {
    const f = picker.files && picker.files[0];
    if (f) uploadFile(f);
    picker.value = "";
  });

  function setLoading(on) { spin.classList.toggle("on", !!on); }

  async function uploadFile(file) {
    if (!file) return;
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append("pdf_file", file, file.name || "invoice.pdf");
      const res = await fetch(DJANGO_UPLOAD_URL, { method: "POST", body: fd, credentials: "include" });
      let data = null;
      try { data = await res.clone().json(); } catch (_) { data = null; }
      if (data && (data.items || data.invoice)) {
        renderData(data);
      } else {
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

  async function copyText(value, btn) {
    const text = String(value == null ? "" : value);
    try {
      await navigator.clipboard.writeText(text);
    } catch (_) {
      const ta = document.createElement("textarea");
      ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); } catch (__) {}
      ta.remove();
    }
    const prev = btn.textContent;
    btn.textContent = "Copied"; btn.classList.add("copied");
    setTimeout(() => { btn.textContent = prev; btn.classList.remove("copied"); }, 1000);
  }

  function buildDropzone() {
    const dz = document.createElement("div");
    dz.className = "dropzone";
    const t = document.createElement("div");
    t.className = "dropzone__title";
    t.textContent = "Drop Invoice PDF Here";
    const h = document.createElement("div");
    h.className = "dropzone__hint";
    h.textContent = "or click to browse";
    dz.append(t, h);
    dz.addEventListener("click", () => picker.click());
    dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("dragover"); });
    dz.addEventListener("dragleave", () => dz.classList.remove("dragover"));
    dz.addEventListener("drop", (e) => {
      e.preventDefault(); dz.classList.remove("dragover");
      const f = e.dataTransfer.files && e.dataTransfer.files[0];
      if (f) uploadFile(f);
    });
    return dz;
  }

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
    });
    const btn = document.createElement("button");
    btn.className = "copy";
    btn.type = "button";
    btn.textContent = "Copy";
    btn.addEventListener("click", () => copyText(value, btn));
    row.append(lab, val, btn);
    return row;
  }

  function renderEmpty() {
    view.textContent = "";
    view.appendChild(buildDropzone());
  }

  function renderData(data, note) {
    const items = (data && data.items) || [];
    const vendor = data && data.invoice ? data.invoice.vendor : "";
    if (!vendor && !items.length) { renderEmpty(); return; }

    view.textContent = "";

    const bar = document.createElement("div");
    bar.className = "gridbar";
    const newBtn = document.createElement("button");
    newBtn.type = "button";
    newBtn.className = "linkbtn";
    newBtn.textContent = "＋ New invoice";
    newBtn.addEventListener("click", renderEmpty);
    bar.appendChild(newBtn);
    view.appendChild(bar);

    if (note) {
      const n = document.createElement("div");
      n.className = "note";
      n.textContent = note;
      view.appendChild(n);
    }

    if (vendor) {
      const v = document.createElement("div");
      v.className = "item";
      const l = document.createElement("div");
      l.className = "item__name";
      l.textContent = "Vendor";
      v.appendChild(l);
      v.appendChild(buildField("Vendor", vendor));
      view.appendChild(v);
    }

    items.forEach((item, i) => {
      const wrap = document.createElement("div");
      wrap.className = "item";
      const name = document.createElement("div");
      name.className = "item__name";
      name.textContent = `Item ${i + 1}`;
      wrap.appendChild(name);
      ITEM_FIELDS.forEach(([l, k]) => wrap.appendChild(buildField(l, item[k])));
      view.appendChild(wrap);
    });
  }

  renderEmpty();
})();
