# Keesing Content API - spec

Dokumenterar vad vi lärt oss om Keesing-APIet som används av
`playpuzzlesonline.com` (och sannolikt andra licensierade utgivare).

## Bakgrund

`playpuzzlesonline.com` är en tunn wrapper som laddar Keesing-spelaren
(`web.keesing.com/pub/player/v2.25.6/dist/main-bundle.js`) via en `<div
id="puzzle-portal" data-customerid="dnmag">`. All pussel-logik och alla
API-anrop sker inuti bundlen. **Ingen JS-rendering behövs** för att hämta
bilderna - de är tillgängliga direkt via HTTP.

## Klient-ID:n och kända spel

**Portal-URL (playpuzzlesonline):** `https://playpuzzlesonline.com/{client_id}/?gametype={gametype}&puzzleid={gametype}_{slot}_today`
**Portal-URL (braintainment):** `https://portal.braintainment.com/{client_id}/?gametype={gametype}&puzzleid={gametype}_{slot}_today`

`bn` är en gemensam pool för hela Bonnier News-nätverket (Expressen, Sydsvenskan, Ångermanland m.fl.).
Varje tidning har ett eller flera dedikerade slots. Slot-nummer framgår av portalsidans `puzzleid`-parameter.
Titelfältet i XML är alltid tomt för `bn` (liksom för `dnmag`) - ingen XML-metadata avslöjar vilken tidning sloten tillhör.

Svårighetsgrad anges i `difficulty`-attributet (1-7) och i `ipsrecipe` (t.ex. `Shared Sudoku 9x9 5*`).

### dnmag (Dagens Nyheter)

| Gametype | Slots | Gridstorlek | Anteckningar |
|----------|-------|-------------|--------------|
| `arrowword_plus` | x1-x9 | varierar | 9 pilkorsord per rullande vecka, x9 = Söndagskrysset |
| `crossword` | x1-x6 | 10x10, 11x5, 13x13 | x1-x4: "Bryderi" (10x10), x5: kompaktformat (11x5), x6: "Klassikern" (13x13) |
| `sudoku` | x1-x21 | 9x9 | 3 sudokus/dag × 7 dagar. Svårighetsgrad per slot: 1★, 5★, 7★ (de flesta dagar), ibland 4 per dag |
| `tectonic` | x1 | 9x5 | Lättare format (diff=2) |

### bn (Bonnier News-poolen)

| Gametype | Slots | Gridstorlek | Anteckningar |
|----------|-------|-------------|--------------|
| `arrowword_plus` | x1-x34+ | varierar | x1-x25 dagliga (rullande ~1 vecka), x26-x34 äldre/veckopussel |
| `crossword` | x1-x34+ | 7x9, 5x5 | x1-x2,x4-x7 etc: "BNLO" 7x9, x3,x19 etc: "Gota" 5x5 (Göteborgs-Tidningen?) |
| `sudoku` | x1-x34+ | 9x9 | Varierad svårighetsgrad (1-5★), vissa slots har "ResultNumbers4"-suffix |
| `tectonic` | x1-x27+ | 9x9, 8x8 | Blandad gridstorlek per slot, alla diff=3 |

## API-endpoints

Bas-URL: `https://web.keesing.com`

### GetPuzzleInfo (metadata)
```
GET /Content/GetPuzzleInfo?clientid={clientid}&puzzleid={puzzleid}&epochtime={ts}
```
Returnerar JSON:
```json
{
  "puzzleID": "KSE-11360886",
  "puzzleType": "Arrowword_Plus",
  "date": "2026-04-27T00:00:00+02:00",
  "title": "",       ← alltid tom, hämta från getxml istället
  ...
}
```
- `puzzleID: null` om pusslet inte finns/inte är tillgängligt.
- `epochtime` kan sättas till `1` (ignoreras i praktiken).

### getxml (puzzle-data inkl. titel)
```
GET /content/getxml?clientid={clientid}&puzzleid={puzzleid}
```
Returnerar UTF-8 XML med BOM. Relevant data:
```xml
<puzzle id="KSE-..." variation="Arrowword DPG" width="15" height="19" ...>
  <title>Måndagskrysset</title>
  <byline>Lina Otterdahl</byline>
  <grid>
    <cells>
      <cell x="0" y="0" visible="1" fillable="1" iscluecell="0" .../>
      <cell x="1" y="0" visible="0" .../>   ← osynlig = del av bildytan
      <cell x="2" y="0" visible="1" fillable="0" iscluecell="1" ...>
        <clue arrow="arrowdown" groupindex="1" wordindex="3">ledtrådstext</clue>
      </cell>
      ...
    </cells>
  </grid>
  <sentences>
    <sentence groupid="..." length="5" content="TAPIR">
      <word content="TAPIR" length="5">
        <cell x="4" y="8"/>
        <cell x="4" y="9"/>
        ...
      </word>
    </sentence>
  </sentences>
</puzzle>
```

#### Celltyper
| fillable | iscluecell | visible | Typ |
|----------|------------|---------|-----|
| 1 | 0 | 1 | Svarscell (vit, fylls av spelaren) |
| 0 | 1 | 1 | Ledtrådsruta (grå, innehåller clue-element med text och pil) |
| 0 | 0 | 0 | Bildyta (osynlig, täcks av getimage-bilden) |
| 0 | 0 | 1 | Svart ruta |

#### Clue-element
```xml
<clue arrow="arrowdownright" groupindex="2" wordindex="5">ledtrådstext</clue>
```
- `arrow`: piltyp, se Pilrendering nedan
- `groupindex`: 1 = vågrätt, 2 = lodrätt
- `wordindex`: löpnummer inom gruppen
- Text: ledtråden. `\` i texten markerar stavelsegränser/radbrytningspunkter.
- Special: `Quiz_RedCircle_N.ai` = quiz-referensruta (se Quiz-celler nedan)

#### Quiz-celler (bildfrågeceller)
Celler med clue-text `Quiz_RedCircle_N.ai` är referenser till bildgåtor.
Numret N (1-indexerat) matchar positionen i `<sentences>`-listan.

Svarcellerna för quiz-gåtan definieras i `<sentences>`, **inte** i `<grid>`.
De kan finnas som `fillable=1`-celler i grid (x3) eller saknas helt (x1).

Renderingen visar:
- Quiz-referensrutan: ljusgul bakgrund + röd fylld cirkel med vitt nummer
- Svarcellerna: ljusgul bakgrund (oavsett om de är fillable i grid eller ej)

#### Stig-celler för sentencearrow (bildpil)
Vissa pusslar har `fillable=1`-celler med en clue vars `arrow`-attribut börjar på
`sentencearrow` (t.ex. `sentencearrowdoubledownright`). Dessa är **inte** svarsceller
utan pilceller som visar vägen från bildytan till svarsrutorna i `<sentences>`.

I originalet visas en stor röd fet pil. Pilens riktning (t.ex. `["down", "right"]`)
och eventuella mellanceller (celler utan clue ovanför/till vänster om hörncellen)
bildar tillsammans en L-formad pilstig.

| Egenskap | Värde |
|----------|-------|
| `fillable` | `1` (trots att det inte är en svarscell) |
| `iscluecell` | `0` |
| clue arrow | börjar med `sentencearrow`, t.ex. `sentencearrowdoubledownright` |
| clue text | tom/whitespace |

Renderingen:
- Vit bakgrund (ej gul - de är inte svarsceller)
- En enda sammansatt röd L-pil ritas över alla stig-celler: från toppen av den
  översta mellancellen, ned till hörncellen, och sedan åt sidan med pilhuvud
- Mellanceller (mellan bildkanten och hörncellen) identifieras genom att gå bakåt
  längs `dirs[0]`-riktningen tills en `visible=0`-cell (bildyta) nås

### getimage (PNG-bild)
```
GET /content/getimage?clientid={clientid}&puzzleid={puzzleid}
```
Returnerar `image/png`. Storlek varierar: 300 KB - 1,7 MB.

Bilden täcker hela gridytan. Osynliga celler (`visible=0`) i grid definierar
bounding box för bilden - den klistras in där.

## Pussel-ID:n och slots

### Slot-format (alias)
```
{gametype}_x{N}_today_
```
Notera det avslutande understrecket. För `dnmag`/`arrowword_plus` finns 9 aktiva slots.

**Rullande fönster:** `_today_`-aliasen ger alltid det senast tillgängliga
pusslet per slot - ungefär 7-9 dagars bakåtrullning.

**Duplikat-kontroll:** kontrollera alltid KSE-ID för att undvika dubbellagring.

## PDF-konvertering

### Variation: Arrowword DPG

XML-data räcker - `render_pdf(xml_bytes, output, image_bytes=png_bytes)` bygger
SVG från XML och konverterar till PDF via cairosvg. Bild används för de osynliga
cellerna (bildytan).

Cellstorlek anpassas automatiskt för A4 (~50px för 15-kolumns-grid).

#### Textrendering i ledtrådsrutor
- Uttömmande sökning över alla kombinationer av mellanslags- och stavelsesnitt
  för maximal fontstorlek.
- Strategi A: enbart mellanslag (hela ord). Strategi B: även stavelsesnitt
  (pyphen + XML-tips) → bindestreck vid brott.
- B föredras om den ger klart större font, men ej om A redan passar på en rad
  med tillräcklig storlek, eller om A är inom 95% av B utan stavelsefragment.

#### Expansion av ledtrådsrutor in i bildytan
Ledtrådsrutor som gränsar till en osynlig cell (bildyta) kan expandera in i den
för att ge mer plats åt lång text. Renderingen sker i ett utökat rektangelområde
som täcker både ledtrådsrutan och den osynliga cellen.

Kriterier för expansion (alla måste uppfyllas):
1. Den osynliga cellen får ha max 1 osynlig granne (exkl. källcellen) - dvs det
   är en kantcell i bildytan, inte ett inre bildområde.
2. Expansionsriktningen får inte vara en pilriktning för klueelementet.

Konfliktlösning när flera ledtrådsrutor konkurrerar om samma osynliga cell:
- Prioritet 0 (bäst): bilden slutar vid expansionscellen (cellen bortom är synlig)
- Prioritet 1: bilden fortsätter bortom expansionscellen (fler osynliga celler i riktningen)
- Prioritet 2 (sämst): ledtrådsrutan har diagonal primärpil (t.ex. `arrow4590leftdown`)
- Vid lika prioritet: koordinatordning (minst y, sedan minst x) avgör

#### Pilrendering
Pilindikatorerna ritas i den angränsande svarscellen (inte i ledtrådsrutan).

| Arrow-namn | Placering |
|------------|-----------|
| `arrowdownright` | cellen nedanför |
| `arrowrightdown` | cellen till höger |
| `arrowrighttop` / `arrowrightdowntop` | cellen till höger |
| `arrowdownbottom` / `arrowdown` | cellen nedanför |
| `arrow4590rightdown` / `arrow4590downright` | diagonalt nedre-höger |
| `arrow4590leftdown` | diagonalt nedre-vänster |
| `arrowleftdown` | vänster sedan ned (L-pil) |

#### Ordavgränsare i svarsceller
Flerordssvar (med mellanslag i `puzzleword`) markeras med en röd ifylld triangel
(1/5 cellhöjd) vid ordgränsen. Riktning baseras på `_cell_dir` mellan angränsande
svarsceller i ordets path.

#### Svängindikator för L-formade meningar
Svarsceller där ett ord svänger (riktningsbyte) markeras med en liten svart L-pil
i svängens ytterhörn. Riktningsbyte identifieras via `cells/cell`-elementet i XML.

#### Sentencearrow (bildpil)
Celler med `sentencearrow`-pil (fillable=1, tom text) ritas med vit bakgrund och
en stor röd L-pil eller rätpil som visar vägen från bildytan till svarsrutorna.
Bakåtgång längs `dirs[0]`-riktningen identifierar mellanceller; stoppas vid
`visible=0` eller `fillable=0` (klueruta eller bildyta).

### Variation: PuzzleConstruction Arrowword, Arrowword Pictorial

Saknar ledtrådstexter i XML - konverteras direkt från PNG via `img2pdf`.

## Gametype: crossword (Vanligt korsord)

`getimage` returnerar 500 - ingen bild. Allt renderas från XML.

### XML-struktur

```xml
<puzzle type="Crossword" variation="Crossword General" width="10" height="10" difficulty="1">
  <title />
  <grid>
    <cells>
      <cell x="0" y="0" visible="1" content="F" giveaway="0" fillable="1" />
      <cell x="1" y="0" visible="1" content="" giveaway="0" fillable="0" />
      ...
    </cells>
  </grid>
  <wordgroups>
    <wordgroup index="1" kind="horizontal">
      <header>Vågrätt</header>
      <words>
        <word length="10" content="INTERVJUAT" giveaway="0" number="6">
          <cells>
            <cell x="0" y="1" />
            ...
          </cells>
          <puzzleword>intervjuat</puzzleword>
          <clue>varit frågvis</clue>
        </word>
        ...
      </words>
    </wordgroup>
    <wordgroup index="2" kind="vertical">...</wordgroup>
  </wordgroups>
</puzzle>
```

#### Celltyper

| fillable | Typ |
|----------|-----|
| `1` | Svarscell (vit, fylls av spelaren) |
| `0` | Svart ruta (avdelare) |

Alla celler är `visible=1`. Inget `iscluecell` eller `arrow`-attribut.

#### Ledtrådar

Ledtrådar finns i `<wordgroups>/<wordgroup>/<words>/<word>/<clue>`.
Varje ord har ett `number`-attribut som visas i gridens övre vänstra hörn på
ordets första cell. Numrering är inte sammanhängande - luckor förekommer.

`<puzzleword>` innehåller svaret i lowercase med mellanslag för flerordssvar.
`content`-attributet på `<word>` är svaret i versaler utan mellanslag.

#### Rendering (ej implementerad)

Tänkt renderingsansats:
- Grid med svarsceller (vita) och svarta rutor
- Cellnummer i övre vänstra hörnet (liten font) för ord-startar
- Separat kluelist under grid: "Vågrätt" och "Lodrätt" med nummer och ledtrådstext
- Cellstorlek anpassas för A4

## Gametype: sudoku

`getimage` returnerar 500 - ingen bild. Allt renderas från XML.

### XML-struktur

```xml
<puzzle type="Sudoku" variation="Sudoku 9x9" variationcode="su9di"
        width="9" height="9" difficulty="5">
  <title>Sudoku</title>
  <grid>
    <cells>
      <cell x="0" y="0" visible="1" content="8" giveaway="1" />
      <cell x="1" y="0" visible="1" content="2" giveaway="0" />
      ...
    </cells>
  </grid>
</puzzle>
```

`giveaway="1"` = förifylld (ges till spelaren, visas i fetstil/grå bakgrund).
`giveaway="0"` = tom cell i startläget (spelaren ska fylla i).
`content` innehåller alltid rätt svar (1-9) oavsett giveaway.

Svårighetsgrad i `difficulty` (1-7) och `ipsrecipe` (t.ex. `Shared Sudoku 9x9 5*`).

#### Rendering (ej implementerad)

Tänkt renderingsansats:
- 9x9 grid med tunna inre linjer och tjocka kanter runt 3x3-boxarna
- Förifyllda siffror i fetstil eller med grå bakgrund
- Tomma celler lämnas vita
- Svårighetsgrad och datum som rubrik

## Gametype: tectonic

`getimage` returnerar 500 - ingen bild. Allt renderas från XML.

### XML-struktur

```xml
<puzzle type="Tectonic" variation="Tectonic" variationcode="tectc"
        width="9" height="9" difficulty="3">
  <title>Tectonic</title>
  <grid>
    <colors>
      <color id="1" name="color1" ARGB="0xffba55d3" />
      <color id="2" name="color2" ARGB="0xffe0ffff" />
      ...
    </colors>
    <cells>
      <cell x="0" y="0" visible="1" content="2" giveaway="0" />
      ...
    </cells>
    <regions>
      <region colorid="1" border="1">
        <cells>
          <cell x="7" y="5" />
          <cell x="7" y="6" />
          <cell x="8" y="6" />
          ...
        </cells>
      </region>
      ...
    </regions>
    <constraints />
  </grid>
</puzzle>
```

Varje region innehåller 1-5 celler. Siffrorna 1..regionstorlek ska placeras
en gång var i regionen, utan upprepning i angränsande celler (alla 8 riktningar).

`colorid` refererar till `<color id>` och anger bakgrundsfärg per region.
`ARGB`-värdet är i hex med alpha (`0xff` = helt ogenomskinlig).

`giveaway="1"` = förifylld siffra. `content` innehåller alltid rätt svar.

#### Rendering (ej implementerad)

Tänkt renderingsansats:
- Grid där varje cell färgas med regionens bakgrundsfärg
- Tjocka kanter ritas mellan celler som tillhör olika regioner
- Tunna kanter ritas mellan celler i samma region
- Förifyllda siffror i fetstil; tomma celler lämnas vita/tomma

## Implementationsnoter

- Inget cookie/session-krav för läsoperationer
- BOM (`﻿`) i XML-svaret - strip innan parse
- `epochtime`-parametern i GetPuzzleInfo kan sättas till `1`
