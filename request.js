/* Figura-igénylés („Mi kell a seregedbe?”)
   Bármelyik [data-request] gomb megnyitja. Két út:
   1) Messengeren írok – egyből a Messenger nyílik;
   2) Összeállítom a listát – ELŐSZÖR név, e-mail, telefon (kötelező), utána kereső: a figura száma vagy neve
      alapján legördülő listából választ, darabszámot ad, több figurát is felvehet; végül e-mailben vagy
      Messengeren küldi el. E-mailnél a rendelésfogadó (data/shop.json endpoint, type: "request") kapja,
      ha nincs még beállítva, előre kitöltött levél nyílik. */
(() => {
  const MSG = "https://m.me/100091130775442";
  const MAIL = "csikos.mate.ovb@gmail.com";
  const hu = () => (document.documentElement.lang || "hu") !== "en";
  const T = (h, e) => (hu() ? h : e);
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const ft = v => new Intl.NumberFormat("hu-HU").format(Math.round(v)) + " Ft";
  const norm = s => String(s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, " ").trim();

  // catalogue: every minifigure we sell (with stock and price) + every minifigure of the sets we know (to source)
  let CAT = null;
  const catalog = () => CAT ||= Promise.all([
    fetch("data/inventory.json", { cache: "no-cache" }).then(r => r.json()).catch(() => ({ items: [] })),
    fetch("data/details.json", { cache: "no-cache" }).then(r => r.json()).catch(() => ({})),
    fetch("assets/figs/index.json", { cache: "no-cache" }).then(r => r.json()).catch(() => ({})),
    fetch("data/shop.json", { cache: "no-cache" }).then(r => r.json()).catch(() => ({})),
  ]).then(([inv, det, figs, shop]) => {
    const m = new Map();
    for (const i of inv.items || []) {
      if (i.type !== "MINIFIG") continue;
      const o = m.get(i.no) || { no: i.no, name: i.name, qty: 0, price: null, pre: true };
      if (!i.preorder && i.qty > 0) { o.qty += i.qty; o.pre = false; o.price = o.price == null ? i.price : Math.min(o.price, i.price); }
      m.set(i.no, o);
    }
    for (const d of Object.values((det && det.items) || {}))
      for (const f of d.minifigs || []) if (!m.has(f.no)) m.set(f.no, { no: f.no, name: f.name, qty: 0, price: null, pre: true, src: true });
    const list = [...m.values()].map(o => ({ ...o, h: norm(o.no + " " + o.name),
      img: figs[o.no] ? `assets/figs/${encodeURIComponent(o.no)}.webp?v=20261027` : `https://img.bricklink.com/ItemImage/MN/0/${encodeURIComponent(o.no)}.png` }));
    return { list, endpoint: (shop && shop.endpoint) || "" };
  });

  const status = o => o.price != null ? T(`Raktáron: ${o.qty} db · ${ft(o.price)}`, `In stock: ${o.qty} · ${ft(o.price)}`)
    : T("Nincs raktáron – beszerezzük, árajánlatot adunk", "Not in stock – we'll source it and quote");

  let dlg, st;
  function open() {
    st = { step: "choose", name: "", email: "", phone: "", lines: [], note: "", sent: null };
    if (!dlg) {
      dlg = document.createElement("dialog"); dlg.className = "notify rq"; dlg.id = "rqDlg";
      document.body.appendChild(dlg);
      dlg.addEventListener("click", e => { if (e.target === dlg) dlg.close(); });
    }
    render(); dlg.showModal();
  }

  function msgText() {
    const L = st.lines.map(l => `${l.qty} × ${l.no ? l.no + " " : ""}${l.name}${l.price != null ? ` (${ft(l.price)}/db)` : ""}`).join("\n");
    return T(`Szia! Figurákat szeretnék rendelni:\n${L}\n\nNév: ${st.name}\nE-mail: ${st.email}\nTelefon: ${st.phone}${st.note ? "\nMegjegyzés: " + st.note : ""}`,
             `Hi! I'd like to order these minifigures:\n${L}\n\nName: ${st.name}\nE-mail: ${st.email}\nPhone: ${st.phone}${st.note ? "\nNote: " + st.note : ""}`);
  }
  const known = () => st.lines.reduce((s, l) => s + (l.price != null ? l.price * l.qty : 0), 0);
  const unknown = () => st.lines.some(l => l.price == null);

  function render() {
    const head = `<button type="button" class="rq__x" data-x aria-label="${T("Bezárás", "Close")}">×</button>
      <p class="kicker">${T("Figura-rendelés", "Minifigure order")}</p>`;
    if (st.step === "choose") {
      dlg.innerHTML = `<div class="notify__in rq__in">${head}
        <h3>${T("Mi kell a seregedbe?", "What does your army need?")}</h3>
        <p>${T("Írj nekünk Messengeren, vagy állítsd össze itt a listát: írd be a figura számát vagy nevét, válaszd ki, és add meg a darabszámot.",
               "Message us on Messenger, or build your list here: type the minifigure's number or name, pick it and set the quantity.")}</p>
        <div class="rq__choose">
          <a class="rq__tile" href="${MSG}?text=${encodeURIComponent(T("Szia! Figurákat szeretnék rendelni: ", "Hi! I'd like to order minifigures: "))}" target="_blank" rel="noopener" data-x>
            <b>💬 ${T("Messengeren írok", "Message on Messenger")}</b><span>${T("Gyors kérdés, egyedi kérés", "A quick question or special request")}</span></a>
          <button type="button" class="rq__tile is-main" data-go="contact"><b>📝 ${T("Összeállítom a listát", "Build my list")}</b><span>${T("Keresés szám vagy név alapján, darabszámmal", "Search by number or name, with quantities")}</span></button>
        </div></div>`;
    } else if (st.step === "contact") {
      dlg.innerHTML = `<form class="notify__in rq__in" novalidate>${head}
        <h3>${T("Először az elérhetőséged", "First, your contact details")}</h3>
        <p>${T("Ezen keresünk meg az ajánlattal és a visszaigazolással. Mindhárom kötelező.", "We'll contact you here with the quote and confirmation. All three are required.")}</p>
        <label>${T("Név", "Name")}<input name="name" autocomplete="name" required value="${esc(st.name)}"></label>
        <label>E-mail<input name="email" type="email" autocomplete="email" required value="${esc(st.email)}"></label>
        <label>${T("Telefonszám", "Phone")}<input name="phone" type="tel" autocomplete="tel" required placeholder="+36 30 123 4567" value="${esc(st.phone)}"></label>
        <p class="rq__err" role="alert"></p>
        <p class="rq__small">${T('Az adataidat csak a rendelésed intézéséhez használjuk, lásd az <a href="adatkezeles.html" target="_blank">adatkezelési tájékoztatót</a>.', 'We only use your details to handle your order – see our <a href="adatkezeles.html" target="_blank">privacy notice</a> (HU).')}</p>
        <div class="notify__btns"><button type="button" class="btn btn--line" data-go="choose">${T("Vissza", "Back")}</button><button class="btn btn--gold" type="submit">${T("Tovább a figurákhoz", "Next: minifigures")}</button></div>
      </form>`;
      const f = dlg.querySelector("form");
      f.onsubmit = e => {
        e.preventDefault();
        const v = k => f.elements[k].value.trim();
        const tel = v("phone").replace(/[^\d+]/g, "");
        const err = !v("name") ? T("Add meg a neved.", "Enter your name.")
          : !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v("email")) ? T("Az e-mail cím hibás.", "Invalid e-mail address.")
          : tel.replace(/\D/g, "").length < 8 ? T("Add meg a telefonszámod.", "Enter your phone number.") : "";
        if (err) { f.querySelector(".rq__err").textContent = err; return; }
        Object.assign(st, { name: v("name"), email: v("email"), phone: v("phone"), step: "list" }); render();
      };
      setTimeout(() => f.elements.name.focus(), 50);
    } else if (st.step === "list") {
      const k = known();
      dlg.innerHTML = `<div class="notify__in rq__in">${head}
        <h3>${T("Melyik figurák kellenek?", "Which minifigures?")}</h3>
        <div class="rq__search"><input id="rqQ" type="search" autocomplete="off" placeholder="${T("Figura száma vagy neve, pl. sw1094 vagy 501st", "Number or name, e.g. sw1094 or 501st")}" aria-label="${T("Keresés", "Search")}" role="combobox" aria-expanded="false" aria-controls="rqList">
          <ul id="rqList" class="rq__drop" role="listbox" hidden></ul></div>
        ${st.lines.length ? `<ul class="rq__lines">${st.lines.map((l, n) => `<li>
            ${l.img ? `<img src="${esc(l.img)}" alt="" loading="lazy">` : `<span class="rq__noimg">?</span>`}
            <span class="rq__t"><b>${esc(l.no ? l.no + " " : "")}${esc(l.name)}</b><small>${l.price != null ? ft(l.price) + T(" / db", " each") : T("árajánlatot adunk", "we'll quote")}</small></span>
            <span class="rq__qty"><button type="button" data-q="${n}" data-d="-1" aria-label="−">−</button><input type="number" min="1" max="999" value="${l.qty}" data-qi="${n}" aria-label="${T("Darabszám", "Quantity")}"><button type="button" data-q="${n}" data-d="1" aria-label="+">+</button></span>
            <button type="button" class="rq__rm" data-rm="${n}" aria-label="${T("Törlés", "Remove")}">×</button></li>`).join("")}</ul>`
          : `<p class="rq__empty">${T("Még nincs figura a listán. Kezdd el gépelni fent a számát vagy a nevét.", "No minifigures yet. Start typing a number or name above.")}</p>`}
        ${st.lines.length ? `<p class="rq__sum">${T("Raktári tételek összesen:", "In-stock items:")} <b>${ft(k)}</b>${unknown() ? T(" + árajánlat a többire", " + a quote for the rest") : ""}</p>
          <p class="rq__small">${k >= 10000 || unknown() ? T("10 000 Ft felett a hiányzó figurákat azonnal felkutatjuk és megrendeljük.", "Over 10,000 Ft we source the missing minifigures right away.") : T("Tipp: 10 000 Ft felett a hiányzó figurákat azonnal beszerezzük.", "Tip: over 10,000 Ft we source missing minifigures right away.")}</p>` : ""}
        <label class="rq__note">${T("Megjegyzés (nem kötelező)", "Note (optional)")}<textarea id="rqNote" rows="2">${esc(st.note)}</textarea></label>
        <div class="notify__btns"><button type="button" class="btn btn--line" data-go="contact">${T("Vissza", "Back")}</button>
          <button type="button" class="btn btn--gold" data-go="send"${st.lines.length ? "" : " disabled"}>${T("Tovább a küldéshez", "Next: send")}</button></div>
      </div>`;
      wireSearch();
      dlg.querySelector("#rqNote").oninput = e => { st.note = e.target.value.slice(0, 500); };
      dlg.querySelectorAll("[data-qi]").forEach(i => i.onchange = () => { st.lines[+i.dataset.qi].qty = Math.max(1, Math.min(999, parseInt(i.value, 10) || 1)); render(); });
    } else if (st.step === "send") {
      dlg.innerHTML = `<div class="notify__in rq__in">${head}
        <h3>${T("Hogyan küldjük el?", "How should we send it?")}</h3>
        <pre class="rq__pre">${esc(msgText())}</pre>
        <div class="rq__choose">
          <button type="button" class="rq__tile is-main" data-send="email"><b>✉️ ${T("Küldés e-mailben", "Send by e-mail")}</b><span>${T("Visszaigazolást kapsz e-mailben", "You'll get a confirmation by e-mail")}</span></button>
          <button type="button" class="rq__tile" data-send="messenger"><b>💬 ${T("Küldés Messengeren", "Send on Messenger")}</b><span>${T("Előre kitöltött üzenet nyílik", "Opens a pre-filled message")}</span></button>
        </div>
        <p class="rq__err" role="alert"></p>
        <div class="notify__btns"><button type="button" class="btn btn--line" data-go="list">${T("Vissza", "Back")}</button></div>
      </div>`;
    } else if (st.step === "done") {
      dlg.innerHTML = `<div class="notify__in rq__in">${head}
        <h3>${T("Köszönjük, megkaptuk!", "Thanks, we've got it!")}</h3>
        <p>${st.sent === "messenger" ? T("Küldd el a Messengerben megnyílt üzenetet, és hamarosan válaszolunk.", "Send the message that opened in Messenger and we'll reply soon.")
          : st.sent === "mailto" ? T("Küldd el a levelezőprogramodban megnyílt levelet, és hamarosan válaszolunk.", "Send the e-mail that opened in your mail app and we'll reply soon.")
          : T("A kérésed beérkezett. Hamarosan jelentkezünk az ajánlattal a megadott e-mail címen vagy telefonon.", "Your request has arrived. We'll get back to you with a quote soon by e-mail or phone.")}</p>
        <div class="notify__btns"><button type="button" class="btn btn--gold" data-x>${T("Bezárás", "Close")}</button></div></div>`;
    }
    dlg.querySelectorAll("[data-x]").forEach(b => b.addEventListener("click", () => dlg.close()));
    dlg.querySelectorAll("[data-go]").forEach(b => b.onclick = () => { st.step = b.dataset.go; render(); });
    dlg.querySelectorAll("[data-q]").forEach(b => b.onclick = () => { const l = st.lines[+b.dataset.q]; l.qty = Math.max(1, Math.min(999, l.qty + +b.dataset.d)); render(); });
    dlg.querySelectorAll("[data-rm]").forEach(b => b.onclick = () => { st.lines.splice(+b.dataset.rm, 1); render(); });
    dlg.querySelectorAll("[data-send]").forEach(b => b.onclick = () => send(b.dataset.send, b));
  }

  function wireSearch() {
    const q = dlg.querySelector("#rqQ"), ul = dlg.querySelector("#rqList");
    let hits = [], sel = -1;
    const add = o => {
      const ex = st.lines.find(l => o.no && l.no === o.no);
      if (ex) ex.qty++; else st.lines.push({ no: o.no || "", name: o.name, qty: 1, price: o.price ?? null, img: o.img || "" });
      render(); setTimeout(() => dlg.querySelector("#rqQ").focus(), 30);
    };
    const show = async () => {
      const w = norm(q.value).split(" ").filter(Boolean);
      if (!w.length) { ul.hidden = true; q.setAttribute("aria-expanded", "false"); return; }
      const { list } = await catalog();
      hits = list.filter(o => w.every(x => o.h.includes(x)))
        .sort((a, b) => (norm(a.no) === w.join(" ") ? -1 : 0) - (norm(b.no) === w.join(" ") ? -1 : 0) || (a.price == null) - (b.price == null) || a.name.localeCompare(b.name))
        .slice(0, 12);
      sel = -1;
      ul.innerHTML = hits.map((o, n) => `<li role="option" data-h="${n}"><img src="${esc(o.img)}" alt="" loading="lazy"><span><b>${esc(o.no)}</b> ${esc(o.name)}<small class="${o.price != null ? "is-in" : ""}">${esc(status(o))}</small></span></li>`).join("")
        + `<li role="option" data-free class="rq__free">➕ ${T("Nincs a listában? Felveszem így:", "Not listed? Add it as:")} <b>„${esc(q.value.trim())}”</b></li>`;
      ul.hidden = false; q.setAttribute("aria-expanded", "true");
      ul.querySelectorAll("[data-h]").forEach(li => li.onmousedown = e => { e.preventDefault(); add(hits[+li.dataset.h]); });
      ul.querySelector("[data-free]").onmousedown = e => { e.preventDefault(); add({ name: q.value.trim() }); };
    };
    q.addEventListener("input", show);
    q.addEventListener("keydown", e => {
      const items = [...ul.querySelectorAll("li")];
      if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); sel = Math.max(0, Math.min(items.length - 1, sel + (e.key === "ArrowDown" ? 1 : -1))); items.forEach((li, n) => li.classList.toggle("is-sel", n === sel)); }
      else if (e.key === "Enter") { e.preventDefault(); if (sel >= 0 && sel < hits.length) add(hits[sel]); else if (sel === hits.length && q.value.trim()) add({ name: q.value.trim() }); else if (hits.length) add(hits[0]); }
      else if (e.key === "Escape" && !ul.hidden) { e.preventDefault(); e.stopPropagation(); ul.hidden = true; }
    });
    q.addEventListener("blur", () => setTimeout(() => { ul.hidden = true; }, 120));
    setTimeout(() => q.focus(), 50);
  }

  async function send(how, btn) {
    const err = dlg.querySelector(".rq__err");
    if (how === "messenger") {
      window.open(MSG + "?text=" + encodeURIComponent(msgText()), "_blank", "noopener");
      post().catch(() => {});                      // also logged by the order handler when it is live
      st.sent = "messenger"; st.step = "done"; render(); return;
    }
    btn.disabled = true;
    try {
      const ok = await post();
      if (ok) { st.sent = "email"; st.step = "done"; render(); return; }
    } catch (e) { /* falls back to a pre-filled e-mail */ }
    location.href = `mailto:${MAIL}?subject=${encodeURIComponent(T("Figura-rendelés: ", "Minifigure order: ") + st.name)}&body=${encodeURIComponent(msgText())}`;
    st.sent = "mailto"; st.step = "done"; render();
    if (err) err.textContent = "";
  }

  async function post() {
    const { endpoint } = await catalog();
    if (!endpoint) return false;
    const r = await fetch(endpoint, { method: "POST", body: JSON.stringify({
      type: "request", lang: hu() ? "hu" : "en", customer: { name: st.name, email: st.email, phone: st.phone },
      lines: st.lines.map(l => ({ no: l.no, name: l.name, qty: l.qty, price: l.price })), note: st.note }) });
    const d = await r.json();
    return !!(d && d.ok);
  }

  document.addEventListener("click", e => {
    const b = e.target.closest("[data-request]");
    if (!b) return;
    e.preventDefault(); open();
  });
  window.MF_REQUEST = { open };
})();
