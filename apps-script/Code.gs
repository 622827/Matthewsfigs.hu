/**
 * Matthew's Fig Supply Co. – rendelésfogadó (Google Apps Script web app).
 *
 * A weboldal pénztára (shop.js) ide küldi a rendelést. A szkript:
 *  1. ellenőrzi az adatokat, és a weboldal aktuális készletéből (data/inventory.json)
 *     újraárazza a tételeket – a böngészőből jött árat nem hiszi el;
 *  2. rendelésszámot ad (MF-ÉÉÉÉ-0001), és elmenti a rendelést ebbe a Google-táblázatba
 *     (a vásárlói adatok így soha nem kerülnek a nyilvános GitHub-repóba);
 *  3. azonnal visszaigazolja a rendelés beérkezését a vásárlónak, mellékelve az ÁSZF-et (PDF);
 *  4. értesítést küld a tulajdonosnak.
 *
 * Beállítás: docs/webshop-beallitas.md. Titkos adat nincs a kódban; a bankszámlaszám és a
 * tulajdonos e-mail címe a Projektbeállítások → Szkripttulajdonságok között van.
 */

const SITE = 'https://matthewsfigs.hu';
const SELLER = {
  name: 'Csikós Máté egyéni vállalkozó',
  brand: "Matthew's Fig Supply Co.",
  address: '1093 Budapest, Lónyay utca 7. 2. em. 54.',
  regNo: '58315839',
  taxNo: '45731484-1-43',
  email: 'csikos.mate.ovb@gmail.com',
  phone: '+36 20 313 3292'
};
const SHEET_ORDERS = 'Rendelések';
const HEAD = ['Időpont', 'Rendelésszám', 'Állapot', 'Név', 'E-mail', 'Telefon', 'Szállítás', 'Foxpost-automata',
  'Fizetés', 'Törzsvásárló', 'Számlázási cím', 'Cégnév', 'Adószám', 'Tételek', 'Részösszeg', 'Szállítási díj',
  'Utánvét díja', 'Végösszeg', 'Megjegyzés', 'ÁSZF + adatkezelés elfogadva', 'Nyelv'];

function prop_(k, d) { return PropertiesService.getScriptProperties().getProperty(k) || d || ''; }
function out_(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }
function ft_(n) { return Utilities.formatString('%s Ft', String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ' ')); }
function esc_(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
function str_(v, max) { return String(v == null ? '' : v).trim().slice(0, max || 200); }

function doGet() { return out_({ ok: true, service: 'matthewsfigs-orders' }); }

function doPost(e) {
  var o;
  try { o = JSON.parse(e.postData.contents); } catch (err) { return out_({ ok: false, error: 'Hibás kérés.' }); }
  var en = o.lang === 'en';
  var msg = function (hu, eng) { return en ? eng : hu; };
  if (o.website) return out_({ ok: true, orderNo: 'MF-0' });               // honeypot: bot
  var lock = LockService.getScriptLock();
  try {
    lock.waitLock(20000);
    // ---- adatok ellenőrzése ----
    var c = o.customer || {}, b = o.billing || {};
    var cust = { name: str_(c.name, 120), email: str_(c.email, 160).toLowerCase(), phone: str_(c.phone, 40) };
    var bill = { zip: str_(b.zip, 12), city: str_(b.city, 80), addr: str_(b.addr, 160), company: str_(b.company, 160), tax: str_(b.tax, 30) };
    if (!cust.name || !cust.phone || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(cust.email) || !bill.zip || !bill.city || !bill.addr)
      return out_({ ok: false, error: msg('Hiányzó vagy hibás adat.', 'Missing or invalid details.') });
    if (!o.accepted || !o.accepted.aszf || !o.accepted.privacy)
      return out_({ ok: false, error: msg('Az ÁSZF elfogadása kötelező.', 'You must accept the Terms.') });
    var cache = CacheService.getScriptCache();
    if (cache.get('rl:' + cust.email)) return out_({ ok: false, error: msg('Kérjük, várj fél percet az újabb rendeléssel.', 'Please wait half a minute before ordering again.') });

    var cfg = JSON.parse(UrlFetchApp.fetch(SITE + '/data/shop.json?t=' + Date.now()).getContentText());
    var inv = JSON.parse(UrlFetchApp.fetch(SITE + '/data/inventory.json?t=' + Date.now()).getContentText());
    var ship = str_(o.ship, 20), pay = str_(o.pay, 20);
    if (!cfg.shipping || !cfg.shipping[ship]) return out_({ ok: false, error: msg('Ismeretlen szállítási mód.', 'Unknown delivery method.') });
    var payOk = cfg.payment && cfg.payment[pay] && (pay !== 'cod' || (ship === 'foxpost' && o.regular)) && (pay !== 'onsite' || ship === 'pickup');
    if (!payOk) return out_({ ok: false, error: msg('Ez a fizetési mód ennél a szállításnál nem választható.', 'This payment method is not available for this delivery.') });
    var apt = null;
    if (ship === 'foxpost') {
      apt = { id: str_(o.apt && o.apt.id, 40), name: str_(o.apt && o.apt.name, 200) };
      if (!apt.id) return out_({ ok: false, error: msg('Válassz Foxpost-automatát.', 'Choose a Foxpost locker.') });
    }

    // ---- újraárazás a weboldal készletéből (legolcsóbb tételek elöl) ----
    var items = (o.items || []).slice(0, 60), lines = [], sub = 0;
    if (!items.length) return out_({ ok: false, error: msg('Üres a kosár.', 'Your cart is empty.') });
    for (var k = 0; k < items.length; k++) {
      var no = str_(items[k].no, 40), qty = Math.floor(Number(items[k].qty));
      if (!no || !(qty > 0) || qty > 999) return out_({ ok: false, error: msg('Hibás tétel.', 'Invalid item.') });
      var lots = inv.items.filter(function (l) { return l.no === no && !l.preorder && l.qty > 0 && l.price; })
        .sort(function (x, y) { return x.price - y.price; });
      var left = qty, sum = 0, name = (inv.items.filter(function (l) { return l.no === no; })[0] || {}).name || no;
      for (var j = 0; j < lots.length && left; j++) { var n = Math.min(left, lots[j].qty); sum += n * lots[j].price; left -= n; }
      if (left) return out_({ ok: false, error: msg('„' + name + '” időközben elfogyott vagy kevesebb van belőle. Frissítsd a kosarat.', '"' + name + '" is no longer available in this quantity. Please refresh your cart.') });
      lines.push({ no: no, name: name, qty: qty, price: sum });
      sub += sum;
    }
    var shipFee = cfg.shipping[ship].fee || 0, codFee = pay === 'cod' ? (cfg.cod_fee || 0) : 0, total = sub + shipFee + codFee;
    if (!o.totals || Number(o.totals.total) !== total)
      return out_({ ok: false, error: msg('Időközben változott az ár. Frissítsd az oldalt, és nézd át újra az összesítőt.', 'Prices changed in the meantime. Please reload and check the summary again.') });

    // ---- rendelésszám + mentés ----
    var props = PropertiesService.getScriptProperties(), year = new Date().getFullYear();
    var seqKey = 'SEQ_' + year, seq = Number(props.getProperty(seqKey) || 0) + 1;
    props.setProperty(seqKey, String(seq));
    var orderNo = 'MF-' + year + '-' + ('000' + seq).slice(-4);
    var order = { no: orderNo, cust: cust, bill: bill, ship: ship, apt: apt, pay: pay, regular: !!o.regular, lines: lines,
      sub: sub, shipFee: shipFee, codFee: codFee, total: total, note: str_(o.note, 500), en: en, cfg: cfg };

    var ss = prop_('SHEET_ID') ? SpreadsheetApp.openById(prop_('SHEET_ID')) : SpreadsheetApp.getActiveSpreadsheet();
    var sh = ss.getSheetByName(SHEET_ORDERS) || ss.insertSheet(SHEET_ORDERS);
    if (sh.getLastRow() === 0) { sh.appendRow(HEAD); sh.setFrozenRows(1); }
    sh.appendRow([new Date(), orderNo, pay === 'cod' ? 'Utánvét jóváhagyásra vár' : 'Beérkezett', cust.name, cust.email, "'" + cust.phone,
      label_(cfg.shipping[ship]), apt ? apt.name + ' [' + apt.id + ']' : '', label_(cfg.payment[pay]), o.regular ? 'igen' : '',
      bill.zip + ' ' + bill.city + ', ' + bill.addr, bill.company, bill.tax,
      lines.map(function (l) { return l.qty + ' × ' + l.no + ' ' + l.name + ' (' + l.price + ' Ft)'; }).join('\n'),
      sub, shipFee, codFee, total, order.note, o.accepted.at || new Date().toISOString(), en ? 'en' : 'hu']);

    // ---- e-mailek ----
    sendConfirmation_(order);
    try {
      GmailApp.sendEmail(prop_('OWNER_EMAIL', SELLER.email), 'Új rendelés: ' + orderNo + ' – ' + ft_(total),
        orderText_(order, false) + '\n\nTáblázat: ' + ss.getUrl() +
        '\n\nTeendő: 48 órán belül elfogadó visszaigazolás; a BrickLink-készletet kézzel csökkentsd.');
    } catch (err) { console.error(err); }
    cache.put('rl:' + cust.email, '1', 30);
    return out_({ ok: true, orderNo: orderNo });
  } catch (err) {
    console.error(err);
    return out_({ ok: false, error: msg('Szerverhiba, kérjük próbáld újra.', 'Server error, please try again.') });
  } finally {
    try { lock.releaseLock(); } catch (e2) {}
  }
}

function label_(o) { return o ? (o.label_hu || '') : ''; }

function orderText_(o, en) {
  var L = [];
  L.push((en ? 'Order number: ' : 'Rendelésszám: ') + o.no);
  L.push((en ? 'Buyer: ' : 'Vevő: ') + o.cust.name + ', ' + o.cust.email + ', ' + o.cust.phone);
  o.lines.forEach(function (l) { L.push('  ' + l.qty + ' × ' + l.no + ' ' + l.name + ' – ' + ft_(l.price)); });
  L.push((en ? 'Delivery: ' : 'Szállítás: ') + label_(o.cfg.shipping[o.ship]) + (o.apt ? ' – ' + o.apt.name : '') + ' – ' + ft_(o.shipFee));
  if (o.codFee) L.push((en ? 'COD fee: ' : 'Utánvét díja: ') + ft_(o.codFee));
  L.push((en ? 'Payment: ' : 'Fizetés: ') + label_(o.cfg.payment[o.pay]) + (o.regular ? ' (törzsvásárló)' : ''));
  L.push((en ? 'Billing: ' : 'Számlázás: ') + (o.bill.company ? o.bill.company + ', ' : '') + o.bill.zip + ' ' + o.bill.city + ', ' + o.bill.addr + (o.bill.tax ? ', ' + o.bill.tax : ''));
  if (o.note) L.push((en ? 'Note: ' : 'Megjegyzés: ') + o.note);
  L.push((en ? 'TOTAL: ' : 'VÉGÖSSZEG: ') + ft_(o.total));
  return L.join('\n');
}

function payText_(o, en) {
  var acc = prop_('BANK_ACCOUNT'), bank = prop_('BANK_NAME');
  switch (o.pay) {
    case 'transfer': return en
      ? 'Please transfer ' + ft_(o.total) + ' to ' + SELLER.name + (bank ? ' (' + bank + ')' : '') + ', account ' + acc + ', reference: ' + o.no + '. We ship once the payment arrives.'
      : 'Kérjük, utald át a ' + ft_(o.total) + ' összeget: kedvezményezett ' + SELLER.name + (bank ? ' (' + bank + ')' : '') + ', számlaszám ' + acc + ', közlemény: ' + o.no + '. A terméket a jóváírás után adjuk fel.';
    case 'card': return en
      ? 'We will send you a link to Stripe\'s secure payment page in a separate e-mail. Your card details never reach us.'
      : 'A Stripe biztonságos fizetőoldalának linkjét külön e-mailben küldjük. A kártyaadataid hozzánk nem jutnak el.';
    case 'cod': return en
      ? 'Cash on delivery is for regular customers: we approve it in our acceptance e-mail. You pay by card at the Foxpost locker.'
      : 'Az utánvét törzsvásárlóknak szól: az elfogadó visszaigazolásban jóváhagyjuk. A Foxpost-automatánál bankkártyával fizetsz.';
    default: return en ? 'You pay in cash or by card when you pick up the order.' : 'Átvételkor készpénzzel vagy kártyával fizetsz.';
  }
}

function sendConfirmation_(o) {
  var en = o.en, m = o.cfg.manufacturer || {};
  var rows = o.lines.map(function (l) {
    return '<tr><td style="padding:6px 8px;border-bottom:1px solid #eee">' + l.qty + ' ×</td><td style="padding:6px 8px;border-bottom:1px solid #eee">' + esc_(l.no.replace(/-1$/, '')) + ' ' + esc_(l.name) +
      '</td><td style="padding:6px 8px;border-bottom:1px solid #eee;text-align:right;white-space:nowrap">' + ft_(l.price) + '</td></tr>';
  }).join('');
  var sumRow = function (a, b, strong) { return '<tr><td></td><td style="padding:4px 8px;text-align:right">' + (strong ? '<b>' + a + '</b>' : a) + '</td><td style="padding:4px 8px;text-align:right;white-space:nowrap">' + (strong ? '<b>' + b + '</b>' : b) + '</td></tr>'; };
  var html = '<div style="font-family:Arial,sans-serif;font-size:15px;color:#15170f;max-width:640px">' +
    '<h2 style="color:#12321b">' + (en ? 'We have received your order' : 'Megkaptuk a rendelésedet') + ' – ' + o.no + '</h2>' +
    '<p>' + (en ? 'Dear ' : 'Kedves ') + esc_(o.cust.name) + '!</p>' +
    '<p>' + (en ? 'Thank you for your order. This e-mail confirms that it has arrived. We will send our acceptance (which forms the contract) within 48 hours.'
      : 'Köszönjük a rendelésedet! Ez az e-mail a rendelés beérkezését igazolja vissza. Az elfogadó visszaigazolást – amellyel a szerződés létrejön – 48 órán belül küldjük.') + '</p>' +
    '<table style="border-collapse:collapse;width:100%">' + rows +
    sumRow(en ? 'Subtotal' : 'Részösszeg', ft_(o.sub)) +
    sumRow((en ? 'Delivery: ' : 'Szállítás: ') + esc_(label_(o.cfg.shipping[o.ship])), o.shipFee ? ft_(o.shipFee) : (en ? 'free' : 'ingyenes')) +
    (o.codFee ? sumRow(en ? 'COD fee' : 'Utánvét díja', ft_(o.codFee)) : '') +
    sumRow(en ? 'Total' : 'Fizetendő összesen', ft_(o.total), true) + '</table>' +
    (o.apt ? '<p><b>' + (en ? 'Foxpost locker' : 'Foxpost-automata') + ':</b> ' + esc_(o.apt.name) + '</p>' : '') +
    '<p><b>' + (en ? 'Payment' : 'Fizetés') + ':</b> ' + esc_(label_(o.cfg.payment[o.pay])) + '<br>' + esc_(payText_(o, en)) + '</p>' +
    '<p><b>' + (en ? 'Billing' : 'Számlázás') + ':</b> ' + esc_((o.bill.company ? o.bill.company + ', ' : '') + o.bill.zip + ' ' + o.bill.city + ', ' + o.bill.addr + (o.bill.tax ? ', ' + o.bill.tax : '')) + '</p>' +
    (o.note ? '<p><b>' + (en ? 'Note' : 'Megjegyzés') + ':</b> ' + esc_(o.note) + '</p>' : '') +
    '<p style="background:#f6f3e6;padding:10px 12px;border-radius:8px">' + (en
      ? 'Right of withdrawal: as a consumer you may withdraw within 14 days of receiving the goods without giving a reason; you bear the cost of return. Details and a model withdrawal form are in the attached Terms (section 8).'
      : 'Elállási jog: fogyasztóként a termék átvételétől számított 14 napon belül indoklás nélkül elállhatsz a vásárlástól; a visszaküldés költségét te viseled. A részleteket és az elállási nyilatkozatmintát a mellékelt ÁSZF 8. pontja tartalmazza.') + '</p>' +
    '<p style="border:1px solid #e7c4c4;background:#fff7f6;padding:10px 12px;border-radius:8px;font-size:13px"><b>' +
    (en ? 'Warning! Not suitable for children under 3 years. Contains small parts – choking hazard.' : 'Figyelem! 3 éven aluli gyermekeknek nem adható. Apró alkatrészeket tartalmaz – fulladásveszély.') + '</b><br>' +
    (en ? 'Manufacturer: ' : 'Gyártó: ') + esc_((m.name || 'LEGO A/S') + ', ' + (en ? (m.address_en || m.address) : (m.address || 'Aastvej 1, 7190 Billund, Dánia')) + ' · ' + (m.web || 'www.lego.com/service')) + '</p>' +
    '<p style="font-size:13px;color:#5e6253">' + esc_(SELLER.name) + ' (' + esc_(SELLER.brand) + ') · ' + esc_(SELLER.address) + ' · ' +
    (en ? 'Reg. no. ' : 'Nyilvántartási szám: ') + SELLER.regNo + ' · ' + (en ? 'Tax no. ' : 'Adószám: ') + SELLER.taxNo + ' · ' + SELLER.email + ' · ' + SELLER.phone + '<br>' +
    (en ? 'Attached: our Terms and Conditions (in Hungarian).' : 'Melléklet: Általános Szerződési Feltételek (ÁSZF).') + '</p></div>';
  var attachments = [];
  try { attachments.push(aszfPdf_()); } catch (err) { console.error('ÁSZF PDF hiba', err); }
  GmailApp.sendEmail(o.cust.email, (en ? 'Order received: ' : 'Rendelés visszaigazolása: ') + o.no + " – Matthew's Fig Supply Co.",
    orderText_(o, en) + '\n\n' + payText_(o, en), {
      htmlBody: html, name: "Matthew's Fig Supply Co.", replyTo: prop_('OWNER_EMAIL', SELLER.email), attachments: attachments });
}

/** Az aktuális ÁSZF (matthewsfigs.hu/aszf.html) PDF-ben – mindig a weboldalon érvényes szöveg. */
function aszfPdf_() {
  var page = UrlFetchApp.fetch(SITE + '/aszf.html?t=' + Date.now()).getContentText();
  var a = page.indexOf('<h1'), z = page.indexOf('</article>');
  var body = a > -1 && z > a ? page.slice(a, z) : page;
  body = body.replace(/<nav[\s\S]*?<\/nav>/g, '').replace(/<script[\s\S]*?<\/script>/g, '').replace(/href="(?!https?:|mailto:|tel:|#)/g, 'href="' + SITE + '/');
  var html = '<html><head><meta charset="utf-8"><style>body{font-family:Arial,sans-serif;font-size:11pt;line-height:1.45;color:#111}' +
    'h1{font-size:20pt;color:#12321b}h2{font-size:13pt;color:#12321b;margin-top:16pt}dt{font-weight:bold}dd{margin:0 0 4pt 0}' +
    'table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:4pt}</style></head><body>' + body + '</body></html>';
  return Utilities.newBlob(html, 'text/html', 'ASZF.html').getAs('application/pdf').setName("ASZF_Matthews_Fig_Supply_Co.pdf");
}

/** Kézi próba a szerkesztőből: futtasd egyszer, és engedélyezd a hozzáférést. */
function teszt() {
  console.log(aszfPdf_().getBytes().length + ' bájtos ÁSZF PDF');
  console.log(UrlFetchApp.fetch(SITE + '/data/shop.json').getContentText().slice(0, 200));
}
