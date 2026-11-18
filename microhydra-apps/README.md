# MicroHydra apps (Cardputer)

Apki dla [MicroHydra](https://github.com/echo-lalia/MicroHydra) (launcher na MicroPythonie)
na M5Stack Cardputer. Folder `apps/` zawiera gotowe aplikacje w postaci pojedynczych plików `.py`.

## Instalacja

MicroHydra uruchamia każdy plik `.py` z folderu `apps` na pamięci flash albo na karcie SD.

- **Karta SD:** skopiuj pliki z `apps/` do `/apps/` na karcie i włóż ją do Cardputera.
- **USB (mpremote):**
  ```sh
  mpremote connect /dev/ttyACM0 cp apps/BitTrainer.py :/apps/BitTrainer.py
  ```
  (albo przeciągnij plik w Thonny)

Po restarcie apka pojawia się w launcherze. **Wyjście z każdej apki:** `ESC` (FN + `` ` ``),
przycisk `G0` albo systemowy skrót MicroHydry `OPT + q`.

Na Cardputerze strzałki to `;` `,` `.` `/` z wciśniętym `FN`. Tam, gdzie te znaki
nie są potrzebne do pisania, apki przyjmują je też bez `FN`.

## Gotowe apki

| Apka | Co robi | Sterowanie |
|---|---|---|
| **BitTrainer** | Trening zamiany BIN / DEC / HEX (4 albo 8 bitów). Bity widać jako „diody”; przy DEC→BIN diody zapalają się na żywo podczas pisania. Liczy wynik i serię poprawnych odpowiedzi. | `;` `.` menu, `TAB` 4/8 bit, `ENT` zatwierdź |
| **TypeRush** | Test szybkości pisania (WPM + celność), słowa EN albo PL (bez polskich znaków), 15/30/60 s. Rekord zapisuje się w `/typerush.txt`. | `TAB` język, `1/2/3` czas, `ENT` start |
| **ElecKit** | Kalkulator elektronika: kod paskowy rezystora (rysuje rezystor), prawo Ohma i moc (wpisujesz 2 z 4 wartości), rezystor do LED z dobraniem wartości z szeregów E12/E24. Liczby można wpisywać z przedrostkiem: `4k7`, `20m`, `1M`. | `TAB` następne narzędzie |
| **Morse** | Morse w trzech trybach: **SEND** (wpisujesz tekst i go odtwarzasz), **KEY** (`SPC` albo `G0` jako klucz telegraficzny, dekodowanie na żywo), **LEARN** (nauka ze słuchu metodą Kocha). | `TAB` tryb, `FN+;` / `FN+.` prędkość |

> Apki są przetestowane na atrapie API MicroHydry w CPythonie (wszystkie ekrany i
> klawisze przeklikane skryptem, tekst mieści się w 240×135), ale **nie** na prawdziwym
> Cardputerze. Jeśli coś się wysypie, MicroHydra zapisuje błąd w `log.txt` w katalogu głównym urządzenia.

## Pomysły na kolejne apki

Pominąłem to, co już jest w [MicroHydra-Apps](https://github.com/echo-lalia/MicroHydra-Apps)
(kalkulator, timer, IR, Pong, Game of Life, Wikipedia, wardriving, MML player…).
Trudność: ★ prosta, ★★ średnia, ★★★ większy projekt.

### Elektronika i hardware
- **LogicLab Mini** ★★: wpisujesz wyrażenie (`A&(B|!C)`) i dostajesz tablicę prawdy, mapę Karnaugha i postać minimalną. Kieszonkowy towarzysz LogicLab ze strony.
- **Skaner I2C** ★: skanuje Grove (SDA=G2, SCL=G1), pokazuje adresy i zgaduje, co to za układ (0x3C OLED, 0x76 BME280, 0x68 MPU6050…).
- **Mini analizator logiczny** ★★★: próbkuje 1–2 piny Grove i rysuje przebiegi, mierzy częstotliwość i wypełnienie. Prosty dekoder UART/I2C.
- **Terminal UART** ★★: rozmowa z Arduino/ESP przez Grove, wybór prędkości, podgląd HEX, makra pod klawiszami F1–F10.
- **Tester serw / PWM** ★: generuje PWM na pinie Grove, ustawiasz kąt albo wypełnienie strzałkami.
- **Emulator 8-bitowego CPU** ★★★: własny prosty zestaw instrukcji z asemblerem w edytorze, krokowanie, podgląd rejestrów i pamięci. Dobre do nauki, jak działa procesor.

### Mikrofon i dźwięk
- **Stroik** ★★: PDM mikrofon + autokorelacja, pokazuje nutę i odchyłkę w centach.
- **Miernik hałasu / spektrum** ★★: poziom dB i prosty wykres FFT na żywo.
- **Metronom + tap tempo** ★: BPM ustawiasz albo wystukujesz spacją; akcent na pierwszą miarę.
- **Mini sekwencer / drum machine** ★★★: siatka 16 kroków na klawiaturze, kilka próbek, zapis patternów na SD.

### Sieć (Wi-Fi / ESP-NOW)
- **Czat ESP-NOW** ★★: pisanie między dwoma Cardputerami bez routera. Pełna klawiatura robi tu robotę. Można to połączyć z pomysłami z MeshForge (przekazywanie wiadomości po węzłach).
- **Pogoda** ★: Open-Meteo (bez klucza API): temperatura, opady, wykres na 24 h.
- **Monitor stron** ★: co kilka minut sprawdza, czy np. `szuszjan.github.io` odpowiada; zielona albo czerwona lista z czasami odpowiedzi.
- **Kody 2FA (TOTP)** ★★: HMAC-SHA1 z `hashlib`, czas z NTP (MicroHydra sama synchronizuje zegar). Sekrety trzymane na SD.
- **Wykres kanałów Wi-Fi** ★: zajętość kanałów 1–13 i RSSI jako słupki, przydatne przy ustawianiu routera.

### Narzędzia
- **Fiszki (SRS)** ★★: plik CSV na SD (`pytanie;odpowiedź`), powtórki z algorytmem typu Leitner/SM-2.
- **Generator haseł + diceware** ★: offline, z wyborem długości i znaków.
- **Zegar szachowy** ★: dwie połówki ekranu, klawisze `z` i `/` jako przyciski graczy, tryby z dodawaniem czasu.
- **Konwerter jednostek** ★: długość, masa, temperatura, AWG ↔ mm².
- **Kalkulator RPN** ★★: z trybem programisty (bin/hex, operacje bitowe).

### Gry (własne pomysły)
- **Typing dungeon** ★★: roguelike, w którym atakujesz potwory, przepisując słowa (silnik z TypeRush).
- **Bulls & Cows** ★: zgadywanie 4-cyfrowego kodu z podpowiedziami.
- **Saper** ★★: kursor na strzałkach, `SPC` odkrywa, `F` flaguje.
- **Lądownik** ★★: grawitacja, ciąg i paliwo, losowy teren do lądowania.
- **Kółko i krzyżyk / statki przez ESP-NOW** ★★: multiplayer na dwa Cardputery.

## Struktura apki (ściąga)

```python
import time, machine
from lib import display, userinput
from lib.hydra import config

DISPLAY = display.Display()     # 240x135, DISPLAY.show() wysyła ramkę
CONFIG = config.Config()        # CONFIG.palette[0..15] = kolory motywu użytkownika
INPUT = userinput.UserInput()   # INPUT.get_new_keys() -> ['a', 'ENT', 'UP', ...]

while True:
    keys = INPUT.get_new_keys()
    if "ESC" in keys:
        machine.reset()          # powrót do launchera
    DISPLAY.fill(CONFIG.palette[2])
    DISPLAY.text("Hello", 10, 10, CONFIG.palette[8])
    DISPLAY.show()
    time.sleep_ms(10)
```

Większe czcionki: `from font import vga1_8x16` / `vga2_16x32` i `DISPLAY.text(..., font=vga2_16x32)`.
Dźwięk: `lib.hydra.beeper.Beeper().play(("C5", "G5"), 80)`.
