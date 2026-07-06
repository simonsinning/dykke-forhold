# Dykke forhold

En lille Python webapp, der vurderer hvor gode forholdene er til dykning og undervandsjagt ved danske kystspots.

Appen bruger:

- vejrprognose fra Open-Meteo
- marine prognoser fra Open-Meteo
- en lokal regelbaseret model med 72 timers historik, recovery-tid og spot-profiler
- grafer for vind, vindretning, bølger, regn, strøm og vandtemperatur
- et vindkompas med slider, roterende pil og regn-indikation
- rangliste over de bedste spots for i dag og de kommende dage
- Danmarkskort med heatmap-markører for spot-scorer
- infoside med forklaring af model, datakilder, usikkerheder og forbehold
- lokale spot-profiler
- dine egne observationer af faktisk sigtbarhed

## Kør appen

```powershell
python app.py
```

Åbn derefter:

```text
http://127.0.0.1:8765
```

Der kræves ingen pip-installation.

Hvis `python` ikke findes i din terminal, kan du i stedet bruge en af launcherne i projektmappen:

```powershell
.\run_app.ps1
```

Eller dobbeltklik på:

```text
run_app.bat
```

Lad terminalvinduet stå åbent mens du bruger appen. Når vinduet lukkes, stopper webserveren.

## Læg appen online

Den nemmeste vej er at hoste appen som en lille Python-webservice på Render, Railway eller Fly.io.

### Render

1. Lav et GitHub-repository og push projektmappen dertil.
2. Gå til <https://render.com> og vælg **New +** -> **Blueprint**.
3. Vælg dit GitHub-repository.
4. Render finder `render.yaml` og opretter webservicen.
5. Når deploy er færdigt, får du en offentlig URL, som andre kan åbne.

Render sætter selv `PORT`. `render.yaml` sætter `HOST=0.0.0.0`, så appen kan modtage trafik udefra.

### Railway eller Heroku-lignende hosting

Projektet har også en `Procfile`, så platformen kan starte appen med:

```text
web: python app.py
```

Sæt miljøvariablen:

```text
HOST=0.0.0.0
```

Platformen sætter normalt selv `PORT`.

### Vigtigt om observationer

Observationer gemmes lige nu i `data/observations.csv`. På gratis hosting kan lokale filer forsvinde ved genstart eller redeploy. Hvis andre skal bruge appen fast, bør observationer senere flyttes til en database eller en persistent disk.

## Tilpas spots

Rediger `data/spots.json`.

De klassiske felter er:

- `bad_wind_directions`: vindretninger der typisk giver pålandsvind eller roder bunden op
- `good_wind_directions`: vindretninger der typisk giver læ/fralandsvind
- `direction_tolerance`: hvor bredt vindretningerne matcher
- `typical_visibility_m`: normal god sigt på spottet
- `sensitivity`: hvor følsomt spottet er for vind, bølger, regn og strøm

Hvert spot har desuden en `visibility_model`, som styrer den nye lokale model:

- `base_score`: spottets lokale udgangspunkt før vejrfradrag
- `sediment_risk`: hvor let bunden hvirvles op
- `shallow_factor`: hvor kraftigt lavt vand forstærker bølgeeffekt
- `runoff_sensitivity`: følsomhed for regn, udløb, havn og dræn
- `algae_sensitivity`: sæson-/algefølsomhed
- `current_sensitivity`: hvor vigtigt strøm er lokalt
- `water_exchange`: hvor hurtigt spottet typisk renser sig selv
- `required_calm_hours`: hvor længe spottet skal have ro før sigten forventes at komme tilbage
- `fetch_sectors`: lokale vindsektorer med hver sin eksponering
- `clear_water_directions` og `dirty_water_directions`: transportretninger der typisk hjælper eller forværrer sigten
- `special_factors`: tekst der vises i spotinfo-vinduet

Vindretninger er grader: nord `0`, øst `90`, syd `180`, vest `270`.

## Log observationer

Observationer gemmes i `data/observations.csv`. Jo flere du logger, jo bedre grundlag får du til senere at lave en maskinlæringsmodel.

## Test

```powershell
python -m unittest discover -s tests
```

## Næste gode udvidelser

- DMI Open Data provider ved siden af Open-Meteo
- kortvisning af spots
- ML-model trænet på observationer
- automatisk spot-anbefaling: "hvor skal jeg tage hen i morgen?"
