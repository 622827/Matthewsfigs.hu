/* Matthew's Fig Supply Co. – kosár és pénztár (webshop).
   - A kosár a böngésző helyi tárhelyén van (mfs-cart); személyes adat nem kerül a repóba.
   - A rendelés a data/shop.json "endpoint" címére megy (Google Apps Script), amely
     újraárazza a tételeket, menti a rendelést a tulajdonos Google-táblázatába és
     visszaigazoló e-mailt küld az ÁSZF-fel.
   - Amíg a bolt nincs nyitva (open:false és a nyitás napja előtt), a kosár csak
     ?shop=preview előnézettel látszik. */
(() => {
  "use strict";
  const LS_CART = "mfs-cart", LS_PREVIEW = "mfs-shop-preview", LS_FORM = "mfs-checkout";
  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} },
    del(k) { try { localStorage.removeItem(k); } catch (e) {} }
  };
  const lang = () => { try { return localStorage.getItem("mfs-lang") || (navigator.language.startsWith("hu") ? "hu" : "en"); } catch (e) { return "hu"; } };
  const hu = () => lang() !== "en";
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const ft = v => new Intl.NumberFormat(hu() ? "hu-HU" : "en-GB", { style: "currency", currency: "HUF", maximumFractionDigits: 0 }).format(v || 0);
  const shortNo = i => (i.type === "SET" ? i.no.replace(/-1$/, "") : i.no);

  // preview switch: ?shop=preview turns it on for this browser, ?shop=off turns it off
  const qs = new URLSearchParams(location.search).get("shop");
  if (qs === "preview") store.set(LS_PREVIEW, 1);
  if (qs === "off") store.del(LS_PREVIEW);

  let CFG = null, LOTS = [];
  const ready = fetch("data/shop.json", { cache: "no-cache" }).then(r => r.ok ? r.json() : {}).catch(() => ({}))
    .then(c => { CFG = c || {}; return CFG; });

  const isOpen = () => !!CFG && (CFG.open === true || (CFG.endpoint && CFG.launch && new Date() >= new Date(CFG.launch + "T00:00:00+01:00")));
  const enabled = () => isOpen() || !!store.get(LS_PREVIEW, 0);
  const preview = () => !isOpen() && !!store.get(LS_PREVIEW, 0);

  // ---------- termékbiztonság (GPSR, játékbiztonsági figyelmeztetés) ----------
  const maker = () => CFG && CFG.manufacturer || { name: "LEGO A/S", address: "Aastvej 1, 7190 Billund, Dánia", address_en: "Aastvej 1, 7190 Billund, Denmark", web: "www.lego.com/service" };
  const WARN_HU = "Figyelem! 3 éven aluli gyermekeknek nem adható. Apró alkatrészeket tartalmaz – fulladásveszély.";
  const WARN_EN = "Warning! Not suitable for children under 3 years. Contains small parts – choking hazard.";
  const safetyLine = () => {
    const m = maker();
    return hu()
      ? `<span class="safety"><b>⚠ 3 éven aluliaknak nem adható</b> – apró alkatrészek. Gyártó: ${esc(m.name)}, ${esc(m.address)}</span>`
      : `<span class="safety"><b>⚠ Not for children under 3</b> – small parts. Manufacturer: ${esc(m.name)}, ${esc(m.address_en || m.address)}</span>`;
  };
  const safetyBlock = () => {
    const m = maker();
    return `<div class="safety-box"><span class="age3" aria-hidden="true">0–3</span><div>
      <b>${hu() ? WARN_HU : WARN_EN}</b><br>
      ${hu() ? "Gyártó" : "Manufacturer"}: ${esc(m.name)}, ${esc(hu() ? m.address : (m.address_en || m.address))} · ${esc(m.web)}<br>
      ${hu() ? "Azonosító: a termék neve mellett feltüntetett LEGO cikkszám. Biztonsági információk és összeszerelési útmutató a termék csomagolásán és a gyártó weboldalán." : "Identification: the LEGO item number shown with each product. Safety information and building instructions are on the packaging and on the manufacturer's website."}
    </div></div>`;
  };

  // ---------- ajánlatok e-mailben (külön, önkéntes hozzájárulás minden e-mail mezőnél) ----------
  const MKT = {
    hu: ["Elsőként szeretném tudni, ha ritka figura, új szállítmány vagy akció érkezik – küldjetek róla e-mailt.",
         "Szólhattok e-mailben a kedvezményekről és a frissen érkezett szettekről.",
         "Kérem a nálatok elsőként elérhető ajánlatokat és akciókat e-mailben.",
         "Ha jó áron jön valami, írjatok – kérem az akciós ajánlatokat e-mailben."],
    en: ["Let me know first by e-mail when rare figures, new stock or deals arrive.",
         "You may e-mail me about discounts and newly arrived sets.",
         "Send me your early offers and deals by e-mail.",
         "If something good comes in at a great price, e-mail me about it."]
  };
  const mktPick = Math.floor(Math.random() * MKT.hu.length);
  const mktText = () => (hu() ? MKT.hu : MKT.en)[mktPick] + (hu() ? " Bármikor leiratkozhatok." : " I can unsubscribe at any time.");
  const mktBox = checked => `<label class="co-check mkt" data-mkt hidden><input type="checkbox" name="mkt"${checked ? " checked" : ""}>
    <span>${esc(mktText())} <a href="adatkezeles.html#celok" target="_blank">${hu() ? "Részletek" : "Details"}</a></span></label>`;
  const validEmail = v => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(String(v || "").trim());
  // appears (with a short flash) as soon as a valid e-mail is typed
  function wireMkt(scope, emailInput) {
    const box = scope.querySelector("[data-mkt]"); if (!box || !emailInput) return;
    const upd = () => {
      if (validEmail(emailInput.value)) {
        if (box.hidden) { box.hidden = false; box.classList.remove("flash"); void box.offsetWidth; box.classList.add("flash"); }
      } else box.hidden = true;
    };
    emailInput.addEventListener("input", upd); upd();
  }

  // ---------- kosár ----------
  const cart = () => store.get(LS_CART, {});
  const saveCart = c => { store.set(LS_CART, c); badge(); };
  const lotsOf = no => LOTS.filter(l => l.no === no && !l.preorder && l.qty > 0 && l.price).sort((a, b) => a.price - b.price);
  const stockOf = no => lotsOf(no).reduce((s, l) => s + l.qty, 0);
  // cheapest lots first (one item number can be listed in several lots at different prices)
  function priceOf(no, qty) {
    let left = qty, sum = 0;
    for (const l of lotsOf(no)) { const n = Math.min(left, l.qty); sum += n * l.price; left -= n; if (!left) break; }
    return left ? null : sum;
  }
  const count = () => Object.values(cart()).reduce((s, n) => s + n, 0);
  function add(no, n = 1) {
    const c = cart(), max = LOTS.length ? stockOf(no) : 99, cur = c[no] || 0;
    if (cur + n > max) { toast(hu() ? "Ebből ennyit tudunk raktárról adni. Ha több kell, írj nekünk, és beszerezzük." : "That's all we have in stock. Need more? Message us and we'll source it."); return false; }
    c[no] = cur + n; saveCart(c); return true;
  }
  function setQty(no, n) {
    const c = cart();
    if (n <= 0) delete c[no]; else c[no] = Math.min(n, stockOf(no) || n);
    saveCart(c);
  }

  function badge() {
    if (!enabled()) return;
    const top = document.querySelector(".top__in");
    if (!top) return;
    let a = document.getElementById("cartBtn");
    if (!a) {
      a = document.createElement("a"); a.id = "cartBtn"; a.className = "cart-btn"; a.href = "kosar.html";
      const lb = document.getElementById("langBtn"); top.insertBefore(a, lb || null);
    }
    const n = count();
    a.innerHTML = `<span class="cart-btn__ic" aria-hidden="true"></span><span class="cart-btn__t">${hu() ? "Kosár" : "Cart"}</span>${n ? `<b>${n}</b>` : ""}`;
    a.setAttribute("aria-label", (hu() ? "Kosár" : "Cart") + (n ? ` (${n})` : ""));
  }

  let toastT;
  function toast(html, link) {
    let el = document.getElementById("shopToast");
    if (!el) { el = document.createElement("div"); el.id = "shopToast"; el.className = "shop-toast"; el.setAttribute("role", "status"); document.body.appendChild(el); }
    el.innerHTML = html + (link ? ` <a href="kosar.html">${hu() ? "Kosárhoz →" : "View cart →"}</a>` : "");
    el.classList.add("is-on"); clearTimeout(toastT); toastT = setTimeout(() => el.classList.remove("is-on"), 3200);
  }

  // card hook (app.js): in-stock cards add to the cart when the shop is on
  document.addEventListener("click", e => {
    const a = e.target.closest("[data-add]");
    if (!a || !enabled()) return;
    e.preventDefault();
    const name = a.dataset.name || a.dataset.add;
    const qEl = a.dataset.qtyFrom && document.querySelector(a.dataset.qtyFrom);
    const n = Math.max(1, parseInt(qEl && qEl.value, 10) || 1);
    if (add(a.dataset.add, n)) toast(`<b>${n > 1 ? n + " × " : ""}${esc(name)}</b> ${hu() ? "a kosárba került." : "added to cart."}`, true);
  });

  // ---------- pénztár (kosar.html) ----------
  const T = {
    hu: {
      empty: "A kosarad üres.", browse: "Kínálat böngészése", cart: "Kosár", qty: "Mennyiség", remove: "Törlés",
      sub: "Részösszeg", ship: "Szállítás", cod: "Utánvét díja", total: "Fizetendő összesen", gross: "A feltüntetett árak bruttó árak.",
      data: "Adataid", name: "Teljes név", email: "E-mail cím", phone: "Telefonszám", shipT: "Szállítási mód", apt: "Foxpost csomagautomata",
      aptPh: "Kezdd el írni a település, utca vagy automata nevét…", bill: "Számlázási adatok", zip: "Irányítószám", city: "Település",
      addr: "Utca, házszám", company: "Cégnév (ha cégre kéred a számlát)", tax: "Adószám (cégnél)", note: "Megjegyzés (nem kötelező)",
      pay: "Fizetési mód", regular: "Törzsvásárló vagyok – az utánvétet a visszaigazolásban hagyjuk jóvá.", next: "Tovább az összesítőhöz",
      review: "Rendelés összesítése", reviewLead: "Kérjük, ellenőrizd az adatokat a megrendelés előtt. Ha valamit javítanál, lépj vissza.",
      back: "← Vissza, módosítom", items: "Termékek", deliv: "Szállítás", payT: "Fizetés", buyer: "Vevő", billT: "Számlázás",
      withdraw: "Elállási jog: fogyasztóként a termék átvételétől számított 14 napon belül indoklás nélkül elállhatsz a vásárlástól. A visszaküldés költségét te viseled. Részletek és nyilatkozatminta az ÁSZF 8. pontjában.",
      payInfo: { card: "A visszaigazoló e-mailben küldjük a Stripe biztonságos fizetőoldalának linkjét. A kártyaadataid hozzánk nem jutnak el.",
        transfer: "A visszaigazoló e-mailben megadjuk a számlaszámot és a közleményt. A terméket a jóváírás után adjuk fel.",
        cod: "Az utánvét a Foxpost-automatánál bankkártyával fizethető. Csak törzsvásárlóknak – a visszaigazolásban jóváhagyjuk.",
        onsite: "Személyes átvételkor készpénzzel vagy kártyával fizetsz." },
      acceptAszf: 'Elolvastam és elfogadom az <a href="aszf.html" target="_blank">Általános Szerződési Feltételeket</a>.',
      acceptPriv: 'Elolvastam az <a href="adatkezeles.html" target="_blank">adatkezelési tájékoztatót</a>, és tudomásul veszem, hogy a rendeléshez szükséges adataimat kezelitek.',
      order: "Megrendelés fizetési kötelezettséggel", sending: "Küldés…",
      after: "A megrendelés elküldése után e-mailben azonnal visszaigazoljuk a beérkezését, mellékelve az ÁSZF-et. A szerződés a 48 órán belül küldött elfogadó visszaigazolással jön létre.",
      okT: "Köszönjük a rendelést!", okL: "A rendelésed beérkezett. Rendelésszám:", okMail: "A visszaigazolást elküldtük a megadott e-mail címre (nézd meg a Spam mappát is).",
      previewT: "Előnézet – a webshop január 5-én indul", previewL: "Ez csak előnézet: a rendelés nem lett elküldve, adat nem került sehová.",
      notOpen: "A webshop január 5-én indul. Addig Messengeren tudsz rendelni.",
      err: "A rendelést nem sikerült elküldeni. Próbáld újra, vagy írj nekünk Messengeren.", req: "Kérjük, töltsd ki a kötelező mezőket.",
      aptReq: "Válassz Foxpost-automatát a listából.", stock: "Időközben változott a készlet, ezért a kosarat frissítettük.",
      safety: "Termékbiztonsági információ", gone: "már nem kapható", sameBill: "A számla a fenti névre szóljon"
    },
    en: {
      empty: "Your cart is empty.", browse: "Browse products", cart: "Cart", qty: "Quantity", remove: "Remove",
      sub: "Subtotal", ship: "Shipping", cod: "Cash on delivery fee", total: "Total to pay", gross: "All prices include VAT where applicable.",
      data: "Your details", name: "Full name", email: "E-mail", phone: "Phone", shipT: "Delivery", apt: "Foxpost parcel locker",
      aptPh: "Start typing a town, street or locker name…", bill: "Billing details", zip: "Postcode", city: "Town",
      addr: "Street address", company: "Company name (for a company invoice)", tax: "Tax number (companies)", note: "Note (optional)",
      pay: "Payment", regular: "I'm a regular customer – we approve cash on delivery in our confirmation.", next: "Continue to summary",
      review: "Order summary", reviewLead: "Please check your details before placing the order. Go back to change anything.",
      back: "← Back to edit", items: "Items", deliv: "Delivery", payT: "Payment", buyer: "Buyer", billT: "Billing",
      withdraw: "Right of withdrawal: as a consumer you may withdraw within 14 days of receiving the goods without giving a reason. You bear the cost of returning the goods. Details and a model form are in section 8 of our Terms.",
      payInfo: { card: "We send you a link to Stripe's secure payment page in the confirmation e-mail. Your card details never reach us.",
        transfer: "The confirmation e-mail contains our bank account and the payment reference. We ship once the payment arrives.",
        cod: "Pay by card at the Foxpost locker. Regular customers only – we approve it in our confirmation.",
        onsite: "Pay in cash or by card when you pick up." },
      acceptAszf: 'I have read and accept the <a href="aszf.html" target="_blank">Terms and Conditions</a> (in Hungarian).',
      acceptPriv: 'I have read the <a href="adatkezeles.html" target="_blank">privacy notice</a> (in Hungarian) and understand that you process my data to fulfil the order.',
      order: "Place order with obligation to pay", sending: "Sending…",
      after: "Once you place the order we immediately confirm receipt by e-mail, with our Terms attached. The contract is formed by our acceptance sent within 48 hours.",
      okT: "Thank you for your order!", okL: "Your order has been received. Order number:", okMail: "We've sent the confirmation to your e-mail (check your spam folder too).",
      previewT: "Preview – the webshop opens on 5 January", previewL: "This is a preview only: the order was not sent and no data went anywhere.",
      notOpen: "Our webshop opens on 5 January. Until then you can order on Messenger.",
      err: "We couldn't send your order. Please try again or message us on Messenger.", req: "Please fill in the required fields.",
      aptReq: "Please choose a Foxpost locker from the list.", stock: "Stock changed in the meantime, so we updated your cart.",
      safety: "Product safety information", gone: "no longer available", sameBill: "Invoice in the name above"
    }
  };
  const t = k => (hu() ? T.hu : T.en)[k];
  const lbl = o => o && (hu() ? o.label_hu : (o.label_en || o.label_hu));

  // Foxpost automaták (nyilvános lista)
  let APM = null;
  const nrm = x => String(x || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/\s+/g, " ").trim();
  const apms = () => APM ||= fetch("https://cdn.foxpost.hu/foxplus.json").then(r => r.json()).then(l => l
    .filter(a => a.operator_id || a.place_id)
    .map(a => ({ id: String(a.operator_id || a.place_id), name: String(a.name || "").replace(/^FOXPOST\s*/i, ""), addr: a.address || [a.zip, a.city, a.street].filter(Boolean).join(" "),
      h: nrm([a.name, a.zip, a.city, a.street, a.address].join(" ")) }))).catch(e => { APM = null; throw e; });

  function lines() {
    const c = cart(), out = [];
    for (const [no, qty] of Object.entries(c)) {
      const any = LOTS.find(l => l.no === no);
      const stock = stockOf(no), q = Math.min(qty, stock);
      out.push({ no, qty: q, want: qty, item: any, price: q ? priceOf(no, q) : null, unit: lotsOf(no)[0]?.price, gone: !stock });
    }
    return out;
  }
  function fees(f) {
    const ship = CFG.shipping?.[f.ship]?.fee || 0;
    const cod = f.pay === "cod" ? (CFG.cod_fee || 0) : 0;
    return { ship, cod };
  }
  function totals(f) {
    const ls = lines().filter(l => l.qty), sub = ls.reduce((s, l) => s + l.price, 0), { ship, cod } = fees(f);
    return { ls, sub, ship, cod, total: sub + ship + cod };
  }

  let form = store.get(LS_FORM, { ship: "foxpost", pay: "card", sameBill: true });
  let step = "cart";
  const saveForm = () => { const { regular, mkt, ...keep } = form; store.set(LS_FORM, keep); };

  function payOptions() {
    const all = ["card", "transfer", "cod", "onsite"];
    return all.filter(p => (p !== "cod" || form.ship === "foxpost") && (p !== "onsite" || form.ship === "pickup") && CFG.payment?.[p]);
  }

  function renderCart() {
    const root = document.getElementById("checkout");
    if (!root || !CFG) return;
    if (!enabled()) {
      root.innerHTML = `<div class="co-card"><p>${t("notOpen")}</p><p><a class="btn btn--gold" href="https://m.me/100091130775442" target="_blank" rel="noopener">Messenger</a> <a class="btn btn--line" href="szettek.html">${t("browse")}</a></p></div>`;
      return;
    }
    if (!payOptions().includes(form.pay)) form.pay = payOptions()[0];
    const ls = lines();
    const banner = preview() ? `<div class="co-preview">${esc(t("previewT"))}</div>` : "";
    if (step === "done") return;
    if (!ls.length) {
      root.innerHTML = banner + `<div class="co-card co-empty"><p>${t("empty")}</p><a class="btn btn--gold" href="szettek.html">${t("browse")}</a></div>`;
      return;
    }
    const tt = totals(form);
    const itemRows = ls.map(l => {
      const i = l.item || { no: l.no, name: l.no, type: "" };
      const href = l.item ? `termek.html?no=${encodeURIComponent(i.no)}` : "";   // back to the product page
      const lk = (inner, cls) => href ? `<a class="${cls}" href="${esc(href)}">${inner}</a>` : inner;
      return `<li class="co-line${l.gone ? " is-gone" : ""}">
        ${lk(`<img src="${esc(i.img || "")}" alt="" loading="lazy">`, "co-line__img")}
        <div class="co-line__t"><span class="item__no">${esc(shortNo(i))}</span>${lk(`<b>${esc(i.name)}</b>`, "co-line__name")}
          ${l.gone ? `<span class="co-warn">${t("gone")}</span>` : `<span class="co-muted">${ft(l.unit)} / ${hu() ? "db" : "pc"}</span>`}</div>
        ${step === "cart" ? `<div class="co-qty"><button type="button" data-q="${esc(l.no)}" data-d="-1" aria-label="−">−</button><span>${l.qty}</span><button type="button" data-q="${esc(l.no)}" data-d="1" aria-label="+"${l.qty >= stockOf(l.no) ? " disabled" : ""}>+</button></div>
        <button type="button" class="co-rm" data-rm="${esc(l.no)}">${t("remove")}</button>` : `<span class="co-muted">${l.qty} ${hu() ? "db" : "pcs"}</span>`}
        <b class="co-line__p">${l.price != null ? ft(l.price) : "–"}</b></li>`;
    }).join("");
    const sum = `<dl class="co-sum">
        <dt>${t("sub")}</dt><dd>${ft(tt.sub)}</dd>
        <dt>${t("ship")} – ${esc(lbl(CFG.shipping?.[form.ship]) || "")}</dt><dd>${tt.ship ? ft(tt.ship) : (hu() ? "ingyenes" : "free")}</dd>
        ${tt.cod ? `<dt>${t("cod")}</dt><dd>${ft(tt.cod)}</dd>` : ""}
        <dt class="co-total">${t("total")}</dt><dd class="co-total">${ft(tt.total)}</dd></dl>
      <p class="co-muted co-small">${t("gross")}</p>`;

    if (step === "cart") {
      const ship = Object.entries(CFG.shipping || {}).map(([k, v]) => `<label class="co-opt"><input type="radio" name="ship" value="${k}"${form.ship === k ? " checked" : ""}> <span>${esc(lbl(v))}</span> <b>${v.fee ? ft(v.fee) : (hu() ? "ingyenes" : "free")}</b></label>`).join("");
      const pay = payOptions().map(p => `<label class="co-opt"><input type="radio" name="pay" value="${p}"${form.pay === p ? " checked" : ""}> <span>${esc(lbl(CFG.payment[p]))}</span></label>`).join("");
      root.innerHTML = banner + `
      <div class="co-grid">
        <div class="co-main">
          <section class="co-card"><h2>${t("cart")}</h2><ul class="co-lines">${itemRows}</ul></section>
          <form class="co-card co-form" id="coForm" novalidate>
            <h2>${t("data")}</h2>
            <div class="co-fields">
              <label class="co-f co-wide">${t("name")} *<input class="field" name="name" autocomplete="name" required value="${esc(form.name)}"></label>
              <label class="co-f">${t("email")} *<input class="field" name="email" type="email" autocomplete="email" required value="${esc(form.email)}"></label>
              <label class="co-f">${t("phone")} *<input class="field" name="phone" type="tel" autocomplete="tel" required value="${esc(form.phone)}" placeholder="+36 …"></label>
              <div class="co-wide">${mktBox(form.mkt)}</div>
            </div>
            <h3>${t("shipT")}</h3>${ship}
            <div class="co-apt"${form.ship === "foxpost" ? "" : " hidden"}>
              <label class="co-f co-wide">${t("apt")} *<input class="field" id="aptIn" autocomplete="off" placeholder="${esc(t("aptPh"))}" value="${esc(form.aptName || "")}"></label>
              <ul class="co-apts" id="aptList" hidden></ul>
            </div>
            <h3>${t("bill")}</h3>
            <div class="co-fields">
              <label class="co-f">${t("zip")} *<input class="field" name="zip" autocomplete="postal-code" required value="${esc(form.zip)}" inputmode="numeric"></label>
              <label class="co-f">${t("city")} *<input class="field" name="city" autocomplete="address-level2" required value="${esc(form.city)}"></label>
              <label class="co-f co-wide">${t("addr")} *<input class="field" name="addr" autocomplete="street-address" required value="${esc(form.addr)}"></label>
              <label class="co-f">${t("company")}<input class="field" name="company" autocomplete="organization" value="${esc(form.company)}"></label>
              <label class="co-f">${t("tax")}<input class="field" name="tax" value="${esc(form.tax)}"></label>
            </div>
            <h3>${t("pay")}</h3>${pay}
            ${form.pay === "cod" ? `<label class="co-check"><input type="checkbox" name="regular"${form.regular ? " checked" : ""}> <span>${t("regular")}</span></label>` : ""}
            <p class="co-muted co-small">${esc(t("payInfo")[form.pay] || "")}</p>
            <label class="co-f co-wide">${t("note")}<textarea class="field" name="note" rows="2" maxlength="500">${esc(form.note)}</textarea></label>
            <input type="text" name="website" class="co-hp" tabindex="-1" autocomplete="off" aria-hidden="true">
            <p class="co-err" id="coErr" hidden></p>
          </form>
        </div>
        <aside class="co-card co-side">${sum}<button type="button" class="btn btn--gold co-next" id="coNext">${t("next")}</button></aside>
      </div>`;
      wireCart();
      return;
    }

    // step === "review": a jogszabály szerinti összesítő a megrendelés előtt
    const f = form, apt = f.ship === "foxpost" ? `<br>${esc(f.aptName)}` : "";
    root.innerHTML = banner + `
      <div class="co-grid">
        <div class="co-main">
          <section class="co-card"><h2>${t("review")}</h2><p class="co-muted">${t("reviewLead")}</p>
            <h3>${t("items")}</h3><ul class="co-lines">${itemRows}</ul>
            <div class="co-review">
              <div><h3>${t("buyer")}</h3><p>${esc(f.name)}<br>${esc(f.email)}<br>${esc(f.phone)}</p></div>
              <div><h3>${t("deliv")}</h3><p>${esc(lbl(CFG.shipping?.[f.ship]))}${apt}</p></div>
              <div><h3>${t("billT")}</h3><p>${f.company ? esc(f.company) + "<br>" : ""}${esc(f.zip)} ${esc(f.city)}, ${esc(f.addr)}${f.tax ? "<br>" + esc(f.tax) : ""}</p></div>
              <div><h3>${t("payT")}</h3><p>${esc(lbl(CFG.payment[f.pay]))}<br><span class="co-muted co-small">${esc(t("payInfo")[f.pay])}</span></p></div>
            </div>
            ${f.note ? `<p><b>${t("note").replace(/ \(.*\)/, "")}:</b> ${esc(f.note)}</p>` : ""}
            ${f.mkt ? `<p class="co-muted co-small">✓ ${hu() ? "Ajánlatokat is kérsz e-mailben." : "You also asked for offers by e-mail."}</p>` : ""}
            <p class="co-legal">${t("withdraw")}</p>
            <p class="co-safety">${safetyLine()}</p>
          </section>
        </div>
        <aside class="co-card co-side">${sum}
          <label class="co-check"><input type="checkbox" id="accAszf"> <span>${t("acceptAszf")}</span></label>
          <label class="co-check"><input type="checkbox" id="accPriv"> <span>${t("acceptPriv")}</span></label>
          <button type="button" class="btn btn--gold co-order" id="coOrder" disabled>${t("order")}</button>
          <p class="co-muted co-small">${t("after")}</p>
          <p class="co-err" id="coErr" hidden></p>
          <button type="button" class="co-back" id="coBack">${t("back")}</button>
        </aside>
      </div>`;
    const acc = () => { document.getElementById("coOrder").disabled = !(document.getElementById("accAszf").checked && document.getElementById("accPriv").checked); };
    document.getElementById("accAszf").onchange = acc; document.getElementById("accPriv").onchange = acc;
    document.getElementById("coBack").onclick = () => { step = "cart"; renderCart(); scrollTo(0, 0); };
    document.getElementById("coOrder").onclick = submit;
  }

  function wireCart() {
    const root = document.getElementById("checkout");
    root.querySelectorAll("[data-q]").forEach(b => b.onclick = () => { const no = b.dataset.q; setQty(no, (cart()[no] || 0) + +b.dataset.d); renderCart(); });
    root.querySelectorAll("[data-rm]").forEach(b => b.onclick = () => { setQty(b.dataset.rm, 0); renderCart(); });
    const fm = document.getElementById("coForm");
    wireMkt(fm, fm.querySelector("[name=email]"));
    fm.addEventListener("input", e => {
      const el = e.target; if (!el.name || el.name === "website") return;
      form[el.name] = el.type === "checkbox" ? el.checked : el.value; saveForm();
    });
    fm.addEventListener("change", e => {
      const el = e.target;
      if (el.name === "ship" || el.name === "pay") { form[el.name] = el.value; saveForm(); renderCart(); }
    });
    // automata-kereső
    const inp = document.getElementById("aptIn"), list = document.getElementById("aptList");
    if (inp) {
      let tm;
      inp.addEventListener("input", () => {
        form.aptId = ""; form.aptName = inp.value; saveForm();
        clearTimeout(tm); tm = setTimeout(async () => {
          const q = nrm(inp.value); if (q.length < 2) { list.hidden = true; return; }
          try {
            const words = q.split(" "), hits = (await apms()).filter(a => words.every(w => a.h.includes(w))).slice(0, 8);
            list.innerHTML = hits.map(a => `<li><button type="button" data-apt="${esc(a.id)}" data-nm="${esc(a.name + " – " + a.addr)}"><b>${esc(a.name)}</b><span>${esc(a.addr)}</span></button></li>`).join("") || `<li class="co-muted">${hu() ? "Nincs találat" : "No match"}</li>`;
            list.hidden = false;
          } catch (e) { list.innerHTML = `<li class="co-muted">${hu() ? "Az automatalista most nem érhető el; írd be az automata nevét." : "Locker list unavailable; type the locker name."}</li>`; list.hidden = false; }
        }, 150);
      });
      list.addEventListener("click", e => {
        const b = e.target.closest("[data-apt]"); if (!b) return;
        form.aptId = b.dataset.apt; form.aptName = b.dataset.nm; inp.value = b.dataset.nm; list.hidden = true; saveForm();
      });
    }
    document.getElementById("coNext").onclick = () => {
      const err = document.getElementById("coErr");
      const bad = [...fm.querySelectorAll("[required]")].filter(el => !el.value.trim() || (el.type === "email" && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(el.value.trim())));
      fm.querySelectorAll(".field").forEach(el => el.classList.toggle("is-bad", bad.includes(el)));
      if (bad.length) { err.textContent = t("req"); err.hidden = false; bad[0].focus(); return; }
      if (form.ship === "foxpost" && !form.aptId) { err.textContent = t("aptReq"); err.hidden = false; inp.focus(); inp.classList.add("is-bad"); return; }
      if (form.pay === "cod" && !form.regular) { err.textContent = t("regular"); err.hidden = false; return; }
      if (lines().some(l => l.gone || l.qty < l.want)) { fixCart(); err.textContent = t("stock"); err.hidden = false; return; }
      step = "review"; renderCart(); scrollTo(0, 0);
    };
  }
  function fixCart() { const c = cart(); for (const l of lines()) { if (!l.qty) delete c[l.no]; else c[l.no] = l.qty; } saveCart(c); renderCart(); }

  async function submit() {
    const btn = document.getElementById("coOrder"), err = document.getElementById("coErr");
    const tt = totals(form);
    const payload = {
      v: 1, lang: lang(), website: document.querySelector(".co-hp")?.value || "",
      items: tt.ls.map(l => ({ no: l.no, qty: l.qty, price: l.price })),
      ship: form.ship, pay: form.pay, regular: !!form.regular,
      apt: form.ship === "foxpost" ? { id: form.aptId, name: form.aptName } : null,
      customer: { name: form.name, email: form.email, phone: form.phone },
      marketing: form.mkt ? { text: mktText(), at: new Date().toISOString() } : null,
      billing: { zip: form.zip, city: form.city, addr: form.addr, company: form.company || "", tax: form.tax || "" },
      note: form.note || "", totals: { sub: tt.sub, ship: tt.ship, cod: tt.cod, total: tt.total },
      accepted: { aszf: true, privacy: true, at: new Date().toISOString() }
    };
    if (!CFG.endpoint || preview()) { done(null, true); return; }
    btn.disabled = true; btn.textContent = t("sending"); err.hidden = true;
    try {
      const r = await fetch(CFG.endpoint, { method: "POST", body: JSON.stringify(payload) }); // text/plain: nincs CORS-előkérés
      const j = await r.json();
      if (!j.ok) throw new Error(j.error || "error");
      done(j.orderNo, false);
    } catch (e) {
      err.textContent = (e.message && e.message !== "error" && e.message.length < 200 ? e.message + " – " : "") + t("err"); err.hidden = false;
      btn.disabled = false; btn.textContent = t("order");
    }
  }
  function done(orderNo, isPreview) {
    step = "done";
    if (!isPreview) { store.del(LS_CART); badge(); }
    document.getElementById("checkout").innerHTML = `<div class="co-card co-done">
      <h2>${isPreview ? t("previewT") : t("okT")}</h2>
      <p>${isPreview ? t("previewL") : `${t("okL")} <b>${esc(orderNo)}</b>`}</p>
      ${isPreview ? "" : `<p>${t("okMail")}</p>`}
      <a class="btn btn--gold" href="szettek.html">${t("browse")}</a></div>`;
    scrollTo(0, 0);
  }

  window.MFShop = {
    ready, enabled, safetyLine, safetyBlock, add, badge, mktBox, mktText, wireMkt, endpoint: () => (CFG && CFG.endpoint) || "",
    setLots(items) { LOTS = items || []; badge(); if (document.body.dataset.page === "cart") renderCart(); },
    rerender() { badge(); if (document.body.dataset.page === "cart") renderCart(); }
  };
  document.addEventListener("mfs:lang", () => window.MFShop.rerender());
  ready.then(() => badge());
})();
