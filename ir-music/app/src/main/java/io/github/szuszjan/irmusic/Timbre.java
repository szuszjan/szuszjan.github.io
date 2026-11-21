package io.github.szuszjan.irmusic;

/** Barwa dźwięku: obwiednia wypełnienia, LFO, vibrato, glissando. */
final class Timbre {
    double d0 = 0.5;        // wypełnienie na początku nuty (0..1)
    double d1 = 0.5;        // wypełnienie na końcu nuty (albo drugi koniec LFO)
    double lfoHz = 0;       // >0: wypełnienie oscyluje d0<->d1 zamiast liniowo
    double vibCents = 0;    // głębokość vibrato
    double vibHz = 5;       // tempo vibrato
    double vibDelayMs = 0;  // vibrato startuje po tym czasie
    double glideMs = 0;     // glissando z poprzedniej nuty

    static final String[] PRESETS = {"czysty", "pluck", "wah", "vibrato", "lead", "cienki", "bas", "acid"};
    static final String[] PRESET_NAMES = {
            "Czysty (50 %)", "Pluck (wypełnienie opada)", "Wah (LFO wypełnienia)", "Vibrato",
            "Chip lead (vibrato + glissando)", "Cienki (12 %)", "Bas (punch)", "Acid (narastający)"};

    Timbre copy() {
        Timbre t = new Timbre();
        t.d0 = d0; t.d1 = d1; t.lfoHz = lfoHz; t.vibCents = vibCents;
        t.vibHz = vibHz; t.vibDelayMs = vibDelayMs; t.glideMs = glideMs;
        return t;
    }

    /** @return preset albo null, jeśli nazwa nieznana */
    static Timbre preset(String name) {
        Timbre t = new Timbre();
        switch (name.toLowerCase()) {
            case "czysty": break;
            case "pluck": t.d0 = 0.5; t.d1 = 0.08; break;
            case "wah": t.d0 = 0.12; t.d1 = 0.6; t.lfoHz = 3; break;
            case "vibrato": t.vibCents = 30; t.vibHz = 6; break;
            case "lead": t.d0 = t.d1 = 0.25; t.vibCents = 18; t.vibHz = 6; t.vibDelayMs = 120; t.glideMs = 40; break;
            case "cienki": t.d0 = t.d1 = 0.12; break;
            case "bas": t.d0 = 0.5; t.d1 = 0.22; break;
            case "acid": t.d0 = 0.06; t.d1 = 0.5; break;
            default: return null;
        }
        return t;
    }
}
