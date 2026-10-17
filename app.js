(() => {
  const PAGE = 24;
  const EN = {
    "nav.about":"About","nav.shop":"Shop",
    "about.kicker":"About us","about.title":"Who we are",
    "about.p1":"Matthew's Fig Supply Co. is a LEGO® set and minifigure shop based in Budapest. We buy sealed sets in bulk, so we can sell them below retail. Every figure is checked one by one and its condition is clearly marked, used ones included.",
    "about.p2":"If something isn't in stock, we'll source it: a rare figure, a long-retired set or a whole wanted list. We ship within Hungary and abroad, and you can pick up your order in person in Budapest.",
    "about.name":"The name? Csikós Máté translates to Matthew Horseman in English. \"Fig\" stands for minifigures, and the fig on the logo is a little pun.",
    "about.f1t":"What we sell","about.f1":"Sealed sets, minifigures, parts",
    "about.f2t":"Main theme","about.f2":"Star Wars, plus Minecraft and Castle",
    "about.f3t":"Where to buy","about.f3":"Our BrickLink store, Messenger or in person",
    "about.f4t":"Based in","about.f5t":"Languages","about.f5":"Hungarian and English","nav.sourcing":"Sourcing","nav.order":"How to order","nav.contact":"Contact",
    "hero.kicker":"LEGO® sets · minifigures · parts",
    "hero.title":"If we don't have it,<br>we can get it.",
    "hero.lead":"Bulk LEGO® sets and minifigures below retail. Looking for a rare figure or a long-retired set? Message us and we'll source it within a few weeks.",
    "hero.cta1":"Browse the shop","hero.cta2":"Message us",
    "stats.lots":"lots in stock","stats.praise":"positive feedback","stats.ship":"ships in Hungary & abroad","stats.place":"pickup in Budapest",
    "shop.title":"Shop","shop.updated":"Updated:","shop.sets":"Sets","shop.figs":"Minifigures","shop.parts":"Parts","shop.all":"All",
    "shop.search":"Search by name or number…","shop.condAll":"Any condition","shop.condNew":"New","shop.condUsed":"Used",
    "shop.empty":"Nothing found. Message us and we'll source it!","shop.more":"Show more",
    "src.title":"You dream it, we source it",
    "src.c1t":"Bulk sets","src.c1":"Sealed LEGO® sets at great prices.",
    "src.c2t":"Retired sets","src.c2":"Looking for a retired or hard-to-find set? We'll find it.",
    "src.c3t":"Rare minifigures","src.c3":"Missing a character for your collection? Just send us a message.",
    "src.c4t":"Extra services","src.c4":"Part-outs, wanted list fulfilment and valuation.",
    "ord.title":"How to order",
    "ord.s1t":"Pick","ord.s1":"Browse here or in our BrickLink store.",
    "ord.s2t":"Order","ord.s2":"Check out on BrickLink, or message us on Messenger.",
    "ord.s3t":"Receive","ord.s3":"Careful packing, shipping or pickup in Budapest.",
    "ord.bl":"BrickLink store","ord.msg":"Custom request on Messenger",
    "foot.contact":"Contact",
    "foot.legal":"LEGO® is a trademark of the LEGO Group, which does not sponsor, authorize or endorse this site.",
    "cond.N":"New","cond.U":"Used","price.ask":"Ask",
    "parts.title":"Parts","parts.text":"We have {lots} lots ({qty} pieces) of parts in stock. Browse them with colour filters in our BrickLink store.","parts.cta":"Browse parts on BrickLink"
  };
  const HU = {"cond.N":"Új","cond.U":"Használt","price.ask":"Érdeklődj",
    "parts.title":"Alkatrészek","parts.text":"{lots} tétel ({qty} darab) alkatrész van raktáron. Színre és típusra szűrve a BrickLink boltunkban böngészheted őket.","parts.cta":"Alkatrészek a BrickLinken"};

  let lang = "hu";
  try { lang = localStorage.getItem("mfs-lang") || (navigator.language.startsWith("hu") ? "hu" : "en"); } catch (e) {}
  const t = k => (lang === "en" ? EN[k] : HU[k]) ?? k;

  // Remember the Hungarian originals from the markup
  document.querySelectorAll("[data-i18n]").forEach(el => { HU[el.dataset.i18n] = el.innerHTML; });
  document.querySelectorAll("[data-i18n-ph]").forEach(el => { HU[el.dataset.i18nPh] = el.placeholder; });

  function applyLang() {
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i18n]").forEach(el => { el.innerHTML = t(el.dataset.i18n); });
    document.querySelectorAll("[data-i18n-ph]").forEach(el => { el.placeholder = t(el.dataset.i18nPh); });
    document.getElementById("langBtn").textContent = lang === "hu" ? "EN" : "HU";
    render(true);
  }
  document.getElementById("langBtn").onclick = () => {
    lang = lang === "hu" ? "en" : "hu";
    try { localStorage.setItem("mfs-lang", lang); } catch (e) {}
    applyLang();
  };

  // Inventory
  let data = { items: [] }, type = "SET", shown = PAGE;
  const grid = document.getElementById("grid"), empty = document.getElementById("empty"),
        more = document.getElementById("moreBtn"), q = document.getElementById("search"),
        cond = document.getElementById("cond");

  const money = v => {
    if (v == null || v === "") return t("price.ask");
    const cur = data.currency || "EUR";
    return new Intl.NumberFormat(lang === "hu" ? "hu-HU" : "en-GB", {
      style: "currency", currency: cur, maximumFractionDigits: cur === "HUF" ? 0 : 2
    }).format(v);
  };
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;" }[c]));

  function filtered() {
    const s = q.value.trim().toLowerCase();
    return data.items.filter(i =>
      (type === "ALL" || i.type === type) &&
      (!cond.value || i.cond === cond.value) &&
      (!s || i.name.toLowerCase().includes(s) || i.no.toLowerCase().includes(s))
    );
  }

  function render(reset) {
    if (reset) shown = PAGE;
    if (type === "PART") {
      const lots = data.parts_lots || 0, qty = data.parts_qty || 0;
      grid.innerHTML = `<div class="parts">
        <h3>${t("parts.title")}</h3>
        <p>${t("parts.text").replace("{lots}", lots).replace("{qty}", qty.toLocaleString(lang === "hu" ? "hu-HU" : "en-GB"))}</p>
        <a class="btn btn--gold" href="https://store.bricklink.com/MatthewHorseman#/shop?o={%22itemType%22:%22P%22}" target="_blank" rel="noopener">${t("parts.cta")}</a>
      </div>`;
      empty.hidden = true; more.parentElement.hidden = true; return;
    }
    const list = filtered();
    grid.innerHTML = list.slice(0, shown).map(i => `
      <a class="item" href="${esc(i.url)}" target="_blank" rel="noopener">
        <div class="item__img"><img loading="lazy" src="${esc(i.img)}" alt="" onerror="this.style.opacity=0"></div>
        <div class="item__body">
          <span class="item__no">${esc(i.no)}${i.color ? " · " + esc(i.color) : ""}</span>
          <span class="item__name">${esc(i.name)}</span>
          ${i.note ? `<span class="item__note">${esc(i.note)}</span>` : ""}
          <div class="item__foot">
            <span class="price">${money(i.price)}</span>
            <span class="badge ${i.cond === "U" ? "badge--u" : ""}">${t("cond." + i.cond)}</span>
          </div>
        </div>
      </a>`).join("");
    empty.hidden = list.length > 0;
    more.parentElement.hidden = list.length <= shown;
  }

  document.querySelectorAll(".tab").forEach(b => b.onclick = () => {
    document.querySelectorAll(".tab").forEach(x => x.classList.toggle("is-on", x === b));
    type = b.dataset.type; render(true);
  });
  q.oninput = () => render(true);
  cond.onchange = () => render(true);
  more.onclick = () => { shown += PAGE; render(); };

  fetch("data/inventory.json", { cache: "no-cache" })
    .then(r => r.json())
    .then(d => {
      data = d;
      if (d.total_lots) document.getElementById("statLots").textContent = d.total_lots;
      if (d.updated) document.getElementById("updated").textContent =
        new Date(d.updated).toLocaleString(lang === "hu" ? "hu-HU" : "en-GB", { dateStyle: "medium", timeStyle: "short" });
      render(true);
    })
    .catch(() => { empty.hidden = false; });

  applyLang();
})();
