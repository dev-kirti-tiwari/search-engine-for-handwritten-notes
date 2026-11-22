const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const page = document.body.dataset.page;

function toast(msg, type = "") {
  const t = document.createElement("div");
  t.className = "toast " + type; t.textContent = msg;
  $("#toasts").appendChild(t);
  setTimeout(() => t.remove(), 5000);
}
async function api(url, opts) {
  const r = await fetch(url, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || "Request failed");
  return data;
}
function highlight(text, terms) {
  let out = esc(text);
  (terms || []).filter(Boolean).sort((a, b) => b.length - a.length).forEach(t => {
    out = out.replace(new RegExp("(" + t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")(?![^<]*>)", "gi"), "<mark>$1</mark>");
  });
  return out;
}
const modal = $("#modal");
function openModal(html) { $("#modalBody").innerHTML = html; modal.hidden = false; }
function closeModal() { modal.hidden = true; $("#modalBody").innerHTML = ""; }
$("#modalX").onclick = closeModal;
modal.addEventListener("click", e => { if (e.target === modal) closeModal(); });
document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });

let pvTerms = [];
async function showPage(pid, terms) {
  if (terms) pvTerms = terms;
  if (modal.hidden) openModal('<p class="muted">Loading…</p>');
  try {
    const p = await api("/api/pages/" + pid);
    openModal(`<div class="pv-head">
        <div><h2>${esc(p.file_name)}</h2>
        <div class="badges"><span class="badge pg">Page ${p.page_number} of ${p.total_pages}</span>${p.tags.map(t => `<span class="badge">${esc(t)}</span>`).join("")}</div></div>
        <div class="pv-nav">
          <button class="btn sm" id="pvPrev" ${p.prev_id ? "" : "disabled"}>← Prev</button>
          <button class="btn sm" id="pvNext" ${p.next_id ? "" : "disabled"}>Next →</button>
        </div></div>
      <div class="pv">
        <div class="pv-img"><img id="pvImg" src="/api/pages/${pid}/image" alt="Original page ${p.page_number}" title="Click to zoom"></div>
        <div class="pv-txt"><div class="pv-txt-bar"><b>Extracted text</b><button class="btn sm" id="pvCopy">Copy text</button></div>
          <pre>${p.text ? highlight(p.text, pvTerms) : "No text was extracted from this page."}</pre></div>
      </div>
      <div class="acts"><a class="btn sm" href="/api/notes/${p.note_id}/file" target="_blank">Open original file</a>
        <span class="muted hint">Tip: use ← → keys to change page · click the page image to zoom</span></div>`);
    $("#pvPrev").onclick = () => p.prev_id && showPage(p.prev_id);
    $("#pvNext").onclick = () => p.next_id && showPage(p.next_id);
    $("#pvImg").onclick = e => e.target.classList.toggle("zoom");
    $("#pvCopy").onclick = () => navigator.clipboard.writeText(p.text).then(() => toast("Text copied"), () => toast("Could not copy", "err"));
    modal._nav = { prev: p.prev_id, next: p.next_id };
  } catch (e) { toast(e.message, "err"); closeModal(); }
}
document.addEventListener("keydown", e => {
  if (modal.hidden || !modal._nav || !$("#pvImg")) return;
  if (e.key === "ArrowLeft" && modal._nav.prev) showPage(modal._nav.prev);
  if (e.key === "ArrowRight" && modal._nav.next) showPage(modal._nav.next);
});

/* ---------- home ---------- */
if (page === "home") {
  api("/api/stats").then(s => {
    $("#heroStats").innerHTML = [["Notes", s.notes], ["Pages searchable", s.pages], ["Topics found", s.tags]]
      .map(([l, v]) => `<div><b>${v}</b>${l}</div>`).join("");
  }).catch(() => { });
}

/* ---------- dashboard ---------- */
if (page === "dashboard") {
  const input = $("#fileInput"), drop = $("#drop"), btn = $("#uploadBtn");
  const OK = ["jpg", "jpeg", "png", "pdf"];
  const IDLE = "Drop files here or click to browse";
  function pick(files) {
    const good = [];
    for (const f of files || []) {
      const ext = f.name.split(".").pop().toLowerCase();
      if (!OK.includes(ext)) { toast(`“${f.name}” skipped: use JPG, PNG or PDF.`, "err"); continue; }
      if (f.size > 50 * 1024 * 1024) { toast(`“${f.name}” skipped: larger than 50 MB.`, "err"); continue; }
      good.push(f);
    }
    if (!good.length) return;
    drop._files = good; btn.disabled = false;
    $("#dropText").textContent = good.length === 1 ? good[0].name : `${good.length} files selected`;
  }
  input.onchange = () => pick([...input.files]);
  ["dragenter", "dragover"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", e => pick([...e.dataTransfer.files]));
  $("#uploadForm").onsubmit = async e => {
    e.preventDefault();
    const files = drop._files || []; if (!files.length) return;
    btn.disabled = true; $("#progress").hidden = false;
    let failed = [];
    for (const f of files) {
      $("#progress span").textContent = `Processing “${f.name}”… OCR can take a while for large files.`;
      const fd = new FormData(); fd.append("file", f);
      try {
        const r = await api("/api/upload", { method: "POST", body: fd });
        toast(`Uploaded “${r.file_name}” · ${r.pages} page${r.pages > 1 ? "s" : ""} processed`);
        if (r.warning) toast(r.warning, "warn");
      } catch (err) { failed.push(f); toast(`“${f.name}”: ${err.message}`, "err"); }
    }
    drop._files = failed; input.value = "";
    $("#dropText").textContent = failed.length ? `${failed.length} file(s) failed - click Upload to retry` : IDLE;
    btn.disabled = !failed.length;
    $("#progress").hidden = true;
    load();
  };

  let notes = [];
  function render() {
    const f = ($("#filterNotes").value || "").toLowerCase();
    const list = notes.filter(n => n.file_name.toLowerCase().includes(f));
    $("#notesList").innerHTML = list.length ? list.map(n => `
      <div class="nrow">
        <div class="ftype ${n.file_type === "pdf" ? "pdf" : ""}">${esc(n.file_type.toUpperCase())}</div>
        <div class="ninfo"><b>${esc(n.file_name)}</b><span>${n.pages} page${n.pages > 1 ? "s" : ""} · ${esc(n.upload_date)}</span></div>
        <a class="btn sm" href="/results?note=${n.note_id}">Search in file</a>
        <button class="btn sm" data-view="${n.note_id}">View</button>
        <button class="btn sm danger" data-del="${n.note_id}">Delete</button>
      </div>`).join("") : `<div class="empty">${notes.length ? "No notes match your filter." : "No notes yet — upload your first one above."}</div>`;
  }
  $("#filterNotes").oninput = render;
  $("#notesList").onclick = async e => {
    const v = e.target.closest("[data-view]"), d = e.target.closest("[data-del]");
    if (v) {
      const n = await api("/api/notes/" + v.dataset.view);
      openModal(`<h2>${esc(n.file_name)}</h2><p class="muted">${n.pages} pages</p>` +
        n.page_list.map(p => `<div class="pl"><b>Page ${p.page_number}</b>
          ${p.tags.map(t => `<span class="badge">${esc(t)}</span>`).join(" ")}
          <div class="acts"><button class="btn sm" data-pg="${p.page_id}">Preview page</button></div></div>`).join(""));
      $("#modalBody").onclick = ev => { const b = ev.target.closest("[data-pg]"); if (b) showPage(b.dataset.pg); };
    }
    if (d && confirm("Delete this note and all its extracted data?")) {
      try { await api("/api/notes/" + d.dataset.del, { method: "DELETE" }); toast("Note deleted"); load(); }
      catch (err) { toast(err.message, "err"); }
    }
  };
  async function load() {
    const [s, n] = await Promise.all([api("/api/stats"), api("/api/notes")]);
    notes = n; render();
    $("#sNotes").textContent = s.notes; $("#sPages").textContent = s.pages;
    $("#sTags").textContent = s.tags;
    if (s.top_tags.length) $("#topTags").innerHTML = s.top_tags.map(t => `<a class="chip" href="/results?q=${encodeURIComponent(t)}">${esc(t)}</a>`).join("");
    $("#ocrNote").textContent = s.ocr_engine === "none"
      ? "No OCR engine detected: text PDFs work, but images and scanned pages need EasyOCR (pip install easyocr) or Tesseract." : "";
  }
  load();
}

/* ---------- results ---------- */
if (page === "results") {
  const params = new URLSearchParams(location.search);
  const q = params.get("q") || "", subject = params.get("subject") || "", noteId = params.get("note") || "";
  api("/api/notes").then(ns => {
    const sel = $("#noteSel");
    ns.forEach(n => { const o = document.createElement("option"); o.value = n.note_id; o.textContent = n.file_name; sel.appendChild(o); });
    sel.value = noteId;
  }).catch(() => { });
  const list = $("#resultList"), meta = $("#meta");
  (async () => {
    if (!q.trim() && !subject) { meta.textContent = "Type a topic above to search all your notes."; return; }
    list.innerHTML = '<p class="muted">Searching…</p>';
    try {
      let data;
      if (q.trim()) data = await api(`/api/search?q=${encodeURIComponent(q)}&note_id=${encodeURIComponent(noteId)}`);
      else { // subject-only browse
        const notes = await api("/api/notes");
        const ns = notes.filter(n => n.subject === subject);
        meta.textContent = `${ns.length} note${ns.length === 1 ? "" : "s"} in ${subject}`;
        list.innerHTML = ns.length ? ns.map(n => `<div class="card nrow"><div class="ftype ${n.file_type === "pdf" ? "pdf" : ""}">${esc(n.file_type.toUpperCase())}</div>
          <div class="ninfo"><b>${esc(n.file_name)}</b><span>${n.pages} pages · ${esc(n.upload_date)}</span></div></div>`).join("")
          : '<div class="empty card">No notes in this subject yet.</div>';
        return;
      }
      meta.textContent = data.count ? `${data.count} matching page${data.count > 1 ? "s" : ""} for “${q}”`
        : "";
      list.innerHTML = data.count ? data.results.map(r => `
        <article class="card res">
          <img class="thumb" loading="lazy" src="/api/pages/${r.page_id}/image" alt="Page ${r.page_number} preview" data-pg="${r.page_id}">
          <div>
            <h3>${esc(r.file_name)}</h3>
            <div class="badges"><span class="badge pg">Page ${r.page_number}</span>${r.fuzzy ? '<span class="badge sim" title="Matched approximately - the text may have been misread by OCR">Similar match</span>' : ""}
              ${r.tags.slice(0, 5).map(t => `<span class="badge">${esc(t)}</span>`).join("")}</div>
            <p class="snip">${highlight(r.snippet, data.terms.concat(r.hl || [])) || '<span class="muted">Matched by topic tag</span>'}</p>
            <div class="acts"><button class="btn sm primary" data-pg="${r.page_id}">Preview page</button>
              <a class="btn sm" href="/api/notes/${r.note_id}/file" target="_blank">Open file</a></div>
          </div></article>`).join("")
        : `<div class="empty card"><h3>No results for “${esc(q)}”</h3><p>Try a shorter keyword, or check the spelling.</p></div>`;
      list.onclick = e => { const b = e.target.closest("[data-pg]"); if (b) { const r = data.results.find(x => String(x.page_id) === b.dataset.pg); showPage(b.dataset.pg, data.terms.concat((r && r.hl) || [])); } };
    } catch (e) { list.innerHTML = ""; toast(e.message, "err"); }
  })();
}
