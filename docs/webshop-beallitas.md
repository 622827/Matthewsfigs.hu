# Webshop – beállítás és élesítés

A kosár és a pénztár kész (`kosar.html`, `shop.js`). Rendelést akkor tud fogadni, ha a rendelésfogadó (Google Apps Script) él, és a `data/shop.json` fájlban be van kapcsolva.

## Előnézet

- Bekapcsolás a saját böngésződben: `https://matthewsfigs.hu/szettek.html?shop=preview`
- Kikapcsolás: `?shop=off`
- Előnézetben a rendelés **nem megy el sehová**, csak az utolsó lépést mutatja.

## 1. Rendelésfogadó létrehozása (egyszer, kb. 10 perc – Máté csinálja)

1. Hozz létre egy új Google-táblázatot a saját Drive-odban, például „Matthew's Fig – Rendelések” néven.
2. Nyisd meg: **Bővítmények → Apps Script**.
3. Töröld a mintakódot, és másold be az `apps-script/Code.gs` teljes tartalmát. Mentsd el.
4. Nyisd meg a **Projektbeállítások** (fogaskerék) oldalt, és a **Szkripttulajdonságok** között vedd fel ezeket:
   - `OWNER_EMAIL`: erre a címre jön az értesítés az új rendelésekről.
   - `BANK_ACCOUNT`: az egyéni vállalkozás bankszámlaszáma (ez kerül az átutalási útmutatóba).
   - `BANK_NAME`: a bank neve (nem kötelező).
5. Futtasd egyszer a `teszt` függvényt: felül válaszd ki, majd **Futtatás**. Engedélyezd a hozzáférést (Gmail, táblázat, külső URL).
6. **Telepítés → Új telepítés → Webalkalmazás**:
   - Végrehajtás: **Saját magamként**
   - Hozzáférés: **Bárki**
7. Másold ki a kapott webalkalmazás-URL-t (`https://script.google.com/macros/s/…/exec`).

### Értesítés, ha újra kapható (előrendelés e-mailben)

Ugyanez a szkript fogadja az előrendelési ablak „E-mailes értesítést kérek” kéréseit. Ezek a táblázat **Értesítések** lapjára kerülnek.

Hogy a kért termék újbóli megérkezésekor automatikusan menjen az e-mail, egyszer be kell állítani egy időzítőt:

1. Az Apps Script bal oldali menüjében nyisd meg az **Eseményindítók** (óra ikon) oldalt.
2. **Eseményindító hozzáadása**:
   - függvény: `checkRestock`
   - esemény forrása: **Idővezérelt**
   - típus: **Óránkénti időzítő**

A szkript az egy évnél régebbi, teljesítetlen kéréseket lezárja, és törli belőlük az e-mail címet.

Amíg a rendelésfogadó nincs beállítva, az e-mailes kérés a vásárló levelezőprogramjából, előre kitöltött levélként érkezik hozzád.

## 2. Bekötés a weboldalba

A `data/shop.json` fájlban:

- `"endpoint"`: a fenti URL
- `"open": true` (élesítéskor, január 5-én)

Ha az `endpoint` ki van töltve, a bolt a `launch` napon (2027-01-05) magától is kinyit.

Díjak ugyanitt: `shipping.foxpost.fee` (most 1 490 Ft) és `cod_fee` (utánvét díja, most 0 Ft). **Élesítés előtt ellenőrizd őket.**

## Mi történik egy rendelésnél

1. A pénztár elküldi a rendelést a rendelésfogadónak.
2. A rendelésfogadó a weboldal aktuális készletéből újraárazza a tételeket. Ha az ár vagy a készlet változott, a rendelést visszautasítja, és a vásárló frissítést kér.
3. Rendelésszámot ad (`MF-2027-0001`), és új sort ír a táblázat **Rendelések** lapjára.
4. A vásárló azonnal e-mailt kap a rendelés beérkezéséről, mellékelve az aktuális ÁSZF-et PDF-ben.
5. Te értesítést kapsz.

**A te teendőid minden rendelésnél:**

- 48 órán belül elfogadó visszaigazolás. A szerződés ezzel jön létre.
- A BrickLink-készlet kézi csökkentése.
- Utánvétnél a törzsvásárló ellenőrzése.
- Kártyás fizetésnél a fizetési link elküldése (amíg a Stripe nincs bekötve).

## Adatvédelem

- A vásárlói adatok csak a te Google-táblázatodba és a Gmailedbe kerülnek. A nyilvános GitHub-repóba és a weboldalra soha.
- A kosár és a kitöltött pénztárűrlap csak a vásárló böngészőjében tárolódik.

## Még hátravan

- **Stripe bekötése** (kártyás fizetés): külön lépés. A Stripe titkos kulcsa a rendelésfogadó szkripttulajdonságai közé kerül, a weboldalra soha.
- **Automatikus BrickLink-készletlevonás**: most kézi.
