# Škola OnLine pro Home Assistant

Neoficiální integrace, která vystaví **rozvrh hodin** ze
[Škola OnLine](https://aplikace.skolaonline.cz/) jako kalendářovou entitu
v Home Assistantu.

Integrace pouze čte data. Nic nezapisuje ani nemění.

## Co to umí

- Jedna entita `calendar.<jmeno>_rozvrh` na studenta.
- Každá vyučovací hodina je samostatná událost: název předmětu, učebna v poli
  `location`, učitel a případná změna v popisu.
- Zrušená hodina má v názvu prefix `Zrušeno:` a nepočítá se jako „příští hodina".
- Načítá se aktuální i příští týden, aktualizace každých 30 minut.
- Více dětí = více instancí integrace (jeden účet na instanci).

## Instalace přes HACS

1. HACS → menu (⋮) → **Custom repositories**.
2. URL: `https://github.com/elvisek2020/hacs-calendar_skolaonline`, kategorie **Integration**.
3. Nainstalovat verzi `1.0.0` (nebo novější) a restartovat Home Assistant.
4. **Nastavení → Zařízení a služby → Přidat integraci → Škola OnLine**.
5. Zadat uživatelské jméno a heslo do Škola OnLine.

Vyžaduje Home Assistant 2025.4.0 nebo novější. Integrace nemá žádné externí
závislosti, používá `aiohttp` z Home Assistanta.

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

## Známá omezení

- Ověřeno proti reálnému serveru na rodičovském účtu s jedním dítětem.
  Výběr z více dětí je implementovaný, ale na živých datech nevyzkoušený.
- U školní akce server vypíše celý učitelský sbor. Když je učitelů víc než
  tři, integrace je do popisu nepíše, protože v kalendáři nic neříkají.
- Integrace nečte známky, úkoly ani zprávy. Záměrně jen rozvrh.

## Vývoj

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/python -m pytest
```

Testy pokrývají parser rozvrhu a nepotřebují instalaci Home Assistanta.

## Poznámka

Projekt není nijak spojený se společností Škola OnLine a.s. Používáš ho na
vlastní odpovědnost.
