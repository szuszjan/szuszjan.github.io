# IR Muzyczka

Aplikacja na Androida, która gra proste melodie przez diodę IR telefonu (ConsumerIrManager).
Nośna IR (domyślnie 38 kHz) jest kluczowana z częstotliwością nuty, więc odbiornik IR typu
TSOP4838 / VS1838B oddaje na wyjściu prostokąt o częstotliwości dźwięku — do podglądu na oscyloskopie
(np. Cardputer w trybie audio) albo do głośnika przez kondensator.

- melodie wbudowane + własne w prostej notacji (`C4:4 D#5:8 R:8 440:4 E4:4.`)
- klawiatura (przytrzymanie = ton), ton testowy 50–3000 Hz, sweep 100–2000 Hz
- regulacja nośnej, wypełnienia, długości paczek transmisji

APK budowany jest przez GitHub Actions (`.github/workflows/ir-music.yml`) i publikowany
w release `ir-music-latest`. Lokalnie: `./gradlew assembleDebug` (wymaga Android SDK).

Podłączenie odbiornika (VS1838B / TSOP4838): VCC 3,3–5 V, GND, OUT → wejście oscyloskopu.
Wyjście jest aktywne stanem niskim (cisza = stan wysoki), więc przebieg jest odwrócony.
