# MicroHydra apps (Cardputer)

Apki dla [MicroHydra](https://github.com/echo-lalia/MicroHydra) (launcher na MicroPythonie)
na M5Stack Cardputer. Folder `apps/` zawiera gotowe aplikacje w postaci pojedynczych plików `.py`.

## Instalacja

MicroHydra uruchamia każdy plik `.py` z folderu `apps` na pamięci flash albo na karcie SD.

### Tylko Cardputer (+ telefon do czytania instrukcji): przez Wi-Fi

1. **Ustaw Wi-Fi:** w launcherze otwórz **Settings** i wpisz `wifi_ssid` oraz `wifi_pass`.
   Może to być hotspot z telefonu (2,4 GHz).
2. **Utwórz plik:** otwórz **Files**, zejdź na sam dół listy do pozycji `/.../`, wybierz **New File**
   i wpisz nazwę `Get.py`. Potem otwórz ten plik (**open**), uruchomi się edytor.
3. **Przepisz 10 linijek** z pliku [`Get.py`](Get.py) (bez wcięć, więc łatwo):
   ```python
   import network,requests,time,machine
   from lib.hydra.config import Config
   c=Config()
   w=network.WLAN(network.STA_IF)
   w.active(True)
   w.connect(c['wifi_ssid'],c['wifi_pass'])
   while not w.isconnected():time.sleep(1)
   r=requests.get('https://raw.githubusercontent.com/szuszjan/szuszjan.github.io/ccr-7347e944-2ijb9a/microhydra-apps/apps/AppInstaller.py')
   open('/apps/AppInstaller.py','w').write(r.text)
   machine.reset()
   ```
   Na klawiaturze Cardputera: `(` `)` to Shift+9/0, `:` to Shift+`;`, `_` to Shift+`-`, apostrof `'` jest obok Enter.
4. **Uruchom:** wciśnij **G0** (przycisk z boku), wybierz **Run…** i potem **Restart and run**.
   Przez kilka-kilkanaście sekund ekran stoi na „Restarting…” (łączy się z Wi-Fi i pobiera plik),
   potem Cardputer wraca do launchera.
5. W launcherze pojawi się **AppInstaller**. Uruchom go, zaznacz apki (`SPC`, `a` zaznacza wszystkie)
   i wciśnij `ENT`. Instalator pobiera je z GitHuba do `/apps/`. Później służy też do aktualizacji.
   Plik `Get.py` możesz potem usunąć w Files.

Jeśli po kroku 4 AppInstaller się nie pojawi, najczęściej winne jest Wi-Fi (sieć 5 GHz albo literówka
w haśle) albo literówka w adresie. Możesz też uruchomić `Get.py` przez **Run here**, wtedy zobaczysz ewentualny błąd.

### Android + M5Launcher (tryb USB drive): najprościej

MicroHydra sama czyta apki z folderu `apps` na karcie SD, a M5Launcher potrafi udostępnić kartę jako pendrive.

1. Na telefonie pobierz paczkę ZIP z apkami:
   https://github.com/szuszjan/szuszjan.github.io/archive/refs/heads/ccr-7347e944-2ijb9a.zip
   i rozpakuj ją (np. w aplikacji Pliki od Google). Pliki apek są w `microhydra-apps/apps/`.
2. Na Cardputerze uruchom M5Launcher, włącz tryb USB drive i podłącz Cardputera kablem USB-C do telefonu.
3. Skopiuj wybrane pliki `.py` do folderu **`apps`** w głównym katalogu karty (jeśli go nie ma, utwórz go).
   `AppInstaller.py` i `index.json` nie są potrzebne.
4. Odłącz kabel, wyjdź z trybu USB drive i uruchom MicroHydrę. Apki pojawią się w launcherze
   (z ikonką karty SD).

### Inne sposoby

- **Karta SD:** skopiuj pliki z `apps/` do `/apps/` na karcie i włóż ją do Cardputera.
- **USB (mpremote):**
  ```sh
  mpremote connect /dev/ttyACM0 cp apps/BitTrainer.py :/apps/BitTrainer.py
  ```
  (albo przeciągnij plik w Thonny)
- **Karta SD przez telefon:** jeśli masz czytnik microSD na USB-C (OTG), pobierz pliki z folderu `apps/`
  na telefonie i skopiuj je do folderu `apps` na karcie.

Po restarcie apka pojawia się w launcherze. **Wyjście z każdej apki:** `ESC` (FN + `` ` ``),
przycisk `G0` albo systemowy skrót MicroHydry `OPT + q`.

Na Cardputerze strzałki to `;` `,` `.` `/` z wciśniętym `FN`. Tam, gdzie te znaki
nie są potrzebne do pisania, apki przyjmują je też bez `FN`.

## Gotowe apki

| Apka | Co robi | Sterowanie |
|---|---|---|
| **AppInstaller** | Instaluje i aktualizuje apki z tego folderu przez Wi-Fi (lista w `apps/index.json`). | `SPC` zaznacz, `a` wszystkie, `ENT` instaluj |
| **BitTrainer** | Trening zamiany BIN / DEC / HEX (4 albo 8 bitów). Bity widać jako „diody”; przy DEC→BIN diody zapalają się na żywo podczas pisania. Liczy wynik i serię poprawnych odpowiedzi. | `;` `.` menu, `TAB` 4/8 bit, `ENT` zatwierdź |
| **TypeRush** | Test szybkości pisania (WPM + celność), słowa EN albo PL (bez polskich znaków), 15/30/60 s. Rekord zapisuje się w `/typerush.txt`. | `TAB` język, `1/2/3` czas, `ENT` start |
| **ElecKit** | Kalkulator elektronika: kod paskowy rezystora (rysuje rezystor), prawo Ohma i moc (wpisujesz 2 z 4 wartości), rezystor do LED z dobraniem wartości z szeregów E12/E24. Liczby można wpisywać z przedrostkiem: `4k7`, `20m`, `1M`. | `TAB` następne narzędzie |
| **Morse** | Morse w trzech trybach: **SEND** (wpisujesz tekst i go odtwarzasz), **KEY** (`SPC` albo `G0` jako klucz telegraficzny, dekodowanie na żywo), **LEARN** (nauka ze słuchu metodą Kocha). | `TAB` tryb, `FN+;` / `FN+.` prędkość |
| **LogicProbe** | Mini analizator logiczny na pinach Grove (G1, G2). Szybka pętla w viperze, trigger (zbocze narastające/opadające/dowolne) z pre-triggerem, zoom i przewijanie, pomiar częstotliwości i wypełnienia, dekoder **UART** i **I2C**, zapis do `.vcd` (do otwarcia w PulseView/GTKWave). Ma tryb DEMO z przykładowymi sygnałami i wyjście testowe PWM na G2. | `SPC` ciągle, `ENT` pojedynczy pomiar, `;` `.` zoom, `,` `/` przewijanie, `s` zapis, `TAB` ustawienia |
| **Tuner** | Stroik na wbudowanym mikrofonie (PDM, algorytm YIN w viperze). Tryby: chromatyczny, gitara, bas, ukulele, skrzypce; w trybach instrumentów sam wybiera najbliższą strunę. Wskazówka ±50 centów, historia wysokości, regulowane A4 (415–466 Hz). | `TAB` tryb, `;` `.` A4 ±1 Hz, `SPC` zatrzymaj odczyt |

### LogicProbe: podłączenie i ograniczenia

- Złącze Grove: **G1 = CH1**, **G2 = CH2**, do tego GND. Kolory przewodów różnią się między kablami, więc sprawdź pinout swojego Cardputera. Do dekodowania I2C: SCL → G1, SDA → G2.
- Tylko sygnały **3,3 V**! Sygnałów 5 V nie podłączaj bezpośrednio (użyj dzielnika napięcia albo konwertera poziomów).
- Częstotliwość próbkowania zależy od tego, jak szybko MicroPython wykonuje pętlę. Apka kalibruje ją przy starcie, a wartość zmierzoną przy każdym pomiarze bez triggera pokazuje na górnym pasku. Szacuję, że wyjdzie rzędu 1 MS/s (sprawdź na pasku przy ustawieniu `max`). To wystarczy na UART do 115200 i I2C 100 kHz, ale nie na SPI kilka MHz. Przerwania systemowe mogą czasem rozjechać pojedyncze próbki.
- Trigger czeka maksymalnie ok. 1 s, potem apka sprawdza klawisze i próbuje dalej („waiting for trigger…”).
- Pliki `.vcd` trafiają na kartę SD (jeśli jest), inaczej do głównego katalogu flasha (`la_001.vcd`, …).
- Na Cardputerze ADV można dopisać piny ze złącza EXT w `PINS` na początku pliku (maks. 4, w obrębie 8 kolejnych numerów GPIO).

### Tuner: uwagi

- Mikrofon (G43/G46) dzieli pin zegara z głośnikiem, więc stroik nie wydaje dźwięków.
- Najlepiej trzymać Cardputer blisko instrumentu. Najniższa struna basu (E1, 41 Hz) jest dla małego mikrofonu trudna; wtedy pomaga stroić z flażoletu na 12. progu.
- Zakres to ok. 38 Hz – 1,7 kHz. Na atrapie sygnału dokładność wynosi ±2 centy w całym zakresie gitarowym.

> Apki są przetestowane na atrapie API MicroHydry w CPythonie (wszystkie ekrany i
> klawisze przeklikane skryptem, tekst mieści się w 240×135), ale **nie** na prawdziwym
> Cardputerze. Jeśli coś się wysypie, MicroHydra zapisuje błąd w `log.txt` w katalogu głównym urządzenia.

## Pomysły na kolejne apki

Pominąłem to, co już jest w [MicroHydra-Apps](https://github.com/echo-lalia/MicroHydra-Apps)
(kalkulator, timer, IR, Pong, Game of Life, Wikipedia, wardriving, MML player…).
Trudność: ★ prosta, ★★ średnia, ★★★ większy projekt.

### Elektronika i hardware
- **LogicLab Mini** ★★: wpisujesz wyrażenie (`A&(B|!C)`) i dostajesz tablicę prawdy, mapę Karnaugha i postać minimalną. Kieszonkowy towarzysz LogicLab ze strony.
- **Skaner I2C** ★: skanuje urządzenia na Grove (G1/G2), pokazuje adresy i zgaduje, co to za układ (0x3C OLED, 0x76 BME280, 0x68 MPU6050…).
- ~~**Mini analizator logiczny**~~: zrobione, **LogicProbe**.
- **Terminal UART** ★★: rozmowa z Arduino/ESP przez Grove, wybór prędkości, podgląd HEX, makra pod klawiszami F1–F10.
- **Tester serw / PWM** ★: generuje PWM na pinie Grove, ustawiasz kąt albo wypełnienie strzałkami.
- **Emulator 8-bitowego CPU** ★★★: własny prosty zestaw instrukcji z asemblerem w edytorze, krokowanie, podgląd rejestrów i pamięci. Dobre do nauki, jak działa procesor.

### Mikrofon i dźwięk
- ~~**Stroik**~~: zrobione, **Tuner**.
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
