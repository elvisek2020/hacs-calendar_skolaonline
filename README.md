# Škola OnLine

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Release](https://img.shields.io/github/v/release/elvisek2020/hacs-calendar_skolaonline)](https://github.com/elvisek2020/hacs-calendar_skolaonline/releases)
[![Validate](https://github.com/elvisek2020/hacs-calendar_skolaonline/actions/workflows/validate.yml/badge.svg)](https://github.com/elvisek2020/hacs-calendar_skolaonline/actions/workflows/validate.yml)
[![Licence](https://img.shields.io/github/license/elvisek2020/hacs-calendar_skolaonline)](LICENSE)

[![Otevřít v HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=elvisek2020&repository=hacs-calendar_skolaonline&category=integration)

Neoficiální integrace, která vystaví **rozvrh hodin** ze
[Škola OnLine](https://aplikace.skolaonline.cz/) jako kalendářovou entitu
v Home Assistantu.

Integrace pouze čte data. Nic nezapisuje ani nemění.

- Jedna entita `calendar.<jmeno>_rozvrh` na studenta.
- Každá vyučovací hodina je samostatná událost: název předmětu, učebna v poli
  `location`, učitel a případná změna v popisu.
- Zrušená hodina má v názvu prefix `Zrušeno:` a nepočítá se jako „příští hodina".
- Načítá se aktuální i příští týden, aktualizace každých 30 minut.
- Více dětí = více instancí integrace (jeden účet na instanci).

## Předpoklady a závislosti

- Home Assistant 2025.4.0 nebo novější.
- Účet do Škola OnLine (studentský nebo rodičovský).
- Integrace nemá žádné externí závislosti, používá `aiohttp` z Home Assistanta.

## Instalace

### HACS (doporučeno)

1. HACS → tři tečky vpravo nahoře → **Custom repositories**
2. Vlož URL `https://github.com/elvisek2020/hacs-calendar_skolaonline`, kategorie **Integration**
3. Nainstaluj **Škola OnLine**
4. Restartuj Home Assistant a přidej integraci v **Nastavení → Zařízení a služby → Přidat integraci**.

HACS nabízí aktualizace z GitHub releases.

### Ručně

Zkopíruj `custom_components/skolaonline` do `/config/custom_components/` a restartuj Home Assistant.

## Konfigurace

**Nastavení → Zařízení a služby → Přidat integraci → Škola OnLine**

1. Zadej uživatelské jméno a heslo do Škola OnLine.
2. Pokud rodičovský účet vidí víc dětí, průvodce nabídne výběr. Pro další dítě
   přidej integraci znovu.

Integrace nemá žádné další volby.

## Jak to funguje

Používá se neoficiální REST API na `https://aplikace.skolaonline.cz/solapi/api`,
zdokumentované projektem
[Libre-SkolaOnline/API-docs](https://github.com/Libre-SkolaOnline/API-docs):

| Endpoint | K čemu |
| --- | --- |
| `POST /connect/token` | Přihlášení (OAuth2 password grant) a obnova tokenu |
| `GET /v1/user` | Zjištění studenta a jeho jména |
| `GET /v1/timeTable` | Rozvrh v rozsahu dat |

`GET /v1/user` má dva tvary. Studentský účet popisuje sám sebe (`personID`),
rodičovský má `userType: "parent"` a děti v poli `children`. Rozvrh se vždy
načítá na ID studenta; na `personID` rodiče vrací `/v1/timeTable` HTTP 403.
Pokud účet vidí víc dětí, průvodce nabídne výběr.

Rozvrh vrací dny se seznamem hodin, kde `hourType` rozlišuje typ hodiny:

| `hourType.id` | Jak se to projeví v kalendáři |
| --- | --- |
| `ROZVRH` | Běžná hodina |
| `SUPLOVANI` | Náhradní hodina; učitel je zastupující, změna v popisu |
| `SUPLOVANA` | Původní hodina; zahodí se, když je na stejném čase náhrada |
| `SKOLNI_AKCE` | Školní akce; předmět je prázdný, název se vezme z typu hodiny |

Suplovanou a náhradní hodinu server vrací na stejném čase. Bez zahození
původní by v kalendáři byly dvě události přes sebe.

Access token se obnovuje pomocí `refresh_token`. Pokud refresh selže, integrace
se přihlásí znovu heslem. Když neplatí ani heslo, Home Assistant zobrazí výzvu
k opětovnému přihlášení (reauth).

## Bezpečnost

- Přihlašovací údaje se zadávají jen v UI a zůstávají v config entry
  Home Assistanta. Heslo se nikam nevypisuje ani neloguje.
- Komunikace jde přes HTTPS.
- Neoficiální API se může kdykoli změnit bez ohlášení. Parser je proto
  napsaný tolerantně: neznámá nebo chybějící pole hodinu vynechají, místo aby
  shodila celou integraci.

## Vývoj

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements_test.txt ruff
.venv/bin/python -m pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

Testy pokrývají parser rozvrhu a nepotřebují instalaci Home Assistanta.
GitHub Actions spouští `hassfest`, validaci HACS, Ruff a Pytest.

## Vydání verze

1. Zvedni verzi v `custom_components/skolaonline/manifest.json` (SemVer).
2. Doplň sekci `## vX.Y.Z — RRRR-MM-DD` do `CHANGELOG.md`.
3. Commit `Release vX.Y.Z: …`, `git tag vX.Y.Z`, push commitu i tagu.
4. GitHub Actions vytvoří release s textem z CHANGELOG a HACS nabídne aktualizaci.

## Známá omezení

- Ověřeno proti reálnému serveru na rodičovském účtu s jedním dítětem.
  Výběr z více dětí je implementovaný, ale na živých datech nevyzkoušený.
- U školní akce server vypíše celý učitelský sbor. Když je učitelů víc než
  tři, integrace je do popisu nepíše, protože v kalendáři nic neříkají.
- Integrace nečte známky, úkoly ani zprávy. Záměrně jen rozvrh.

## Autor

**[elvisek2020](https://github.com/elvisek2020)** — vzniklo pro rodinný školní
dashboard v Home Assistantu, kde jsou rozvrhy, obědy a kroužky v jedné kartě.
Licence MIT.

Projekt není nijak spojený se společností Škola OnLine a.s. Používáš ho na
vlastní odpovědnost.
