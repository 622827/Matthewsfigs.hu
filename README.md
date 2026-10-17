# matthewsfigs.hu

Matthew's Fig Supply Co. bemutató oldala. Statikus oldal GitHub Pages-en; a kínálatot egy GitHub Action 6 óránként frissíti a BrickLink boltból.

## 1. GitHub repó és Pages
1. Hozz létre egy új repót (pl. `matthewsfigs`), és töltsd fel ennek a mappának a teljes tartalmát (a `.github` mappát is).
2. Repó → **Settings → Pages** → Source: *Deploy from a branch*, branch: `main`, mappa: `/ (root)`.
3. Ugyanitt a **Custom domain** mezőben: `matthewsfigs.hu` (a `CNAME` fájl már benne van). Ha a tanúsítvány elkészült, kapcsold be az **Enforce HTTPS**-t.

## 2. DNS a Rackhostnál
A domain DNS-beállításainál:

| Típus | Név | Érték |
|---|---|---|
| A | @ | 185.199.108.153 |
| A | @ | 185.199.109.153 |
| A | @ | 185.199.110.153 |
| A | @ | 185.199.111.153 |
| CNAME | www | `<github-felhasználóneved>.github.io.` |

A régi A rekordokat (ha vannak) töröld. A változás pár perctől néhány óráig tart.

## 3. BrickLink API-kulcsok
1. BrickLinken: <https://www.bricklink.com/v2/api/register_consumer.page> → regisztrálj egy Consumer Key-t.
2. Hozz létre Access Tokent. **IP-címnek `0.0.0.0`-t adj meg**, mert a GitHub szerverei változó IP-ről futnak.
3. Repó → **Settings → Secrets and variables → Actions** → *New repository secret*, négy darab:
   `BL_CONSUMER_KEY`, `BL_CONSUMER_SECRET`, `BL_TOKEN`, `BL_TOKEN_SECRET`
4. Ha a boltod nem forintban árazik, a *Variables* fülön adj meg egy `STORE_CURRENCY` változót (pl. `EUR`).
5. **Actions** fül → *BrickLink készlet szinkron* → **Run workflow**. Pár perc múlva az oldalon a valódi készlet látszik.

Addig a `data/inventory.json` csak minta-tételeket tartalmaz.

## Szerkesztés
- Szövegek: `index.html` (magyar), `app.js` elején az `EN` szótár (angol).
- Színek, betűk: `style.css` teteje.
- Képek: `assets/` (logó, fejléckép).

## Később: webshop
A következő lépés lehet a saját kosár és fizetés (Stripe, PayPal, átutalás, utánvét, készpénz átvételkor). Ehhez a statikus oldal mellé egy kis háttérszolgáltatás kell, ami a rendeléseket kezeli és a BrickLink-készletet zárolja.
