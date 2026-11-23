# Gemeentebelangen Urk – Instagram-generator

Een kleine webapp voor op je eigen server. Je vult een formulier in (soort post, titel,
tekst, afbeelding en bij moties/amendementen de stemming) en krijgt:

- een **Instagram-post** als carrousel (PNG's van 1080×1350), en
- een **Instagram-story** (PNG van 1080×1920),

altijd in dezelfde opmaak als de huidige Canva-templates: donkerblauw verloop, logo
bovenin, schuin label (*Motie*, *Vraag*, …), grote titel, en onderin de havenfoto,
de beursgolf of je eigen foto.

## Installeren op Windows (eenvoudigst)

1. Installeer **Python** via https://www.python.org/downloads/ en vink tijdens de
   installatie **"Add python.exe to PATH"** aan.
2. Download dit project: op GitHub **Code → Download ZIP**, en pak de zip uit
   (bijvoorbeeld naar `C:\gb-instagram`).
3. Dubbelklik op **`start-windows.bat`**. De eerste keer worden de onderdelen
   geïnstalleerd (duurt een paar minuten), daarna opent de browser vanzelf op
   `http://localhost:8080`.

Zolang het zwarte venster open staat, draait het programma. Andere apparaten in hetzelfde
netwerk kunnen het openen via het adres dat in het venster staat (`http://192.168.x.x:8080`);
Windows vraagt dan de eerste keer of je dit via de firewall wilt toestaan.
Een wachtwoord stel je in door in `start-windows.bat` de regel `set GB_WACHTWOORD=` aan te vullen.

## Installeren met Docker (Linux-server)

1. Zet deze map op de server.
2. Pas in `docker-compose.yml` het wachtwoord aan (`GB_WACHTWOORD`).
3. Start de app:

   ```bash
   docker compose up -d --build
   ```

4. Ga naar `http://<jouw-server>:8080`. De gebruikersnaam mag je vrij invullen; het
   wachtwoord is het wachtwoord uit stap 2.

Voor gebruik via internet zet je er bij voorkeur een reverse proxy met https voor
(bijv. Caddy, Nginx of Traefik).

## Installeren zonder Docker (Linux/Mac)

Python 3.10 of nieuwer:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export GB_WACHTWOORD=kies-een-wachtwoord
python start.py
```

## Instellingen

| Variabele         | Betekenis                                                  | Standaard |
|-------------------|------------------------------------------------------------|-----------|
| `GB_WACHTWOORD`   | Wachtwoord voor het formulier. Leeg = geen wachtwoord.      | leeg      |
| `GB_BEWAAR_DAGEN` | Na hoeveel dagen gemaakte posts automatisch worden gewist. | 30        |
| `GB_OUTPUT`       | Map waar de gemaakte afbeeldingen komen.                   | `output/` |

## Partijen, zetels en standaardteksten aanpassen

Alles staat in **`config.json`**:

- `partijen` – de fracties met het aantal zetels (wordt vooraf ingevuld in de stemtabel).
  In het formulier staan ook twee lege regels voor een extra partij.
- `soorten` – per soort post het label, de kop boven de tekst, de kop boven de lijst,
  of er een stemming bij hoort, en de standaard achtergrond (`golf` of `haven`) en
  fotoplaatsing (`onder` of `achtergrond`). Je kunt hier ook nieuwe soorten toevoegen.
- `uitslagen` – de keuzes bij *Uitslag*.

Na een wijziging de app herstarten (`docker compose restart`).

## Hoe de slides worden opgebouwd

1. **Titelslide** – label, titel (lettergrootte past zich automatisch aan), eventueel
   ondertitel, en bij moties/amendementen de uitslag met *Voor/Tegen* en vinkjes/kruisjes.
2. **Tekstslides** – de kop (bijv. "Gemeentebelangen heeft vragen gesteld") met de tekst.
   Tekst die niet past loopt vanzelf door naar de volgende slide; alinea's worden niet
   midden in gesplitst.
3. **Lijstslide(s)** – de genummerde vragen of punten. Als ze op één slide passen wordt de
   letter iets kleiner gemaakt; anders worden ze over meerdere slides verdeeld.
4. **Slotslide** – optioneel, voor het standpunt en de afsluiting.

De story bevat de titelslide-inhoud (bij moties met de stemming, anders met het begin van
de tekst) en een knop "Lees meer in onze nieuwste post".

### Opmaak in de tekstvakken

| Typ                | Resultaat                                     |
|--------------------|-----------------------------------------------|
| lege regel         | nieuwe alinea                                 |
| `## Kopje`         | nieuwe slide met dat kopje                    |
| `---`              | nieuwe slide forceren                         |
| `- punt`           | opsommingsteken •                             |
| `1. punt`          | genummerd punt                                |
| `**tekst**`        | **vet**                                       |

### Foto's met mensen

Na het kiezen van een foto verschijnt een voorbeeld: **klik waar de hoofden zitten**.
Dat punt komt altijd in het heldere deel van de foto: het valt nooit onder het
vervaagde blauwe deel en nooit achter tekst of de stemtabel. De foto begint op elke slide
pas onder de tekst. Is er te weinig ruimte (zoals op de titelslide met de stemtabel), dan
krijgt die slide de standaard achtergrond.

Bij "Hele achtergrond" ligt er een doorzichtige blauwe laag over de foto (zoals bij de
algemene beschouwingen); gezichten blijven daar zichtbaar.

Tekst blijft altijd leesbaar: als de foto achter de tekst te licht is, komt er automatisch
een zachte donkerblauwe gloed achter de letters, alleen op die plek en alleen zo sterk als nodig.

Na het maken kun je op **Aanpassen** klikken: het formulier staat dan nog ingevuld
(ook de foto blijft bewaard), zodat je snel een correctie kunt maken.

## Lettertypen

In Canva gebruiken de templates **Garet** (tekst) en **Lato Black** (titels). Die mogen
niet zomaar worden meegeleverd, dus de app gebruikt vergelijkbare vrije lettertypen:
Poppins (tekst) en Open Sans ExtraBold (titels).

Wil je het exact gelijk hebben? Zet deze bestanden in de map `fonts/`; ze worden dan
automatisch gebruikt:

- `Garet-Regular.ttf` en `Garet-Bold.ttf`
- `Lato-Black.ttf` (gratis via Google Fonts)

## Achtergronden vervangen

In `assets/` staan `logo.png`, `haven.png` (havenfoto) en `golf.png` (beursgolf). Je kunt
ze vervangen door een ander bestand met dezelfde naam.
