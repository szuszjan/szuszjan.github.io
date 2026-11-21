package io.github.szuszjan.irmusic;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Parser notacji tekstowej.
 * <pre>
 *   C4:4  D#5:8  Bb3:2.  R:8  440:4      – nuty, pauza, częstotliwość w Hz
 *   C4+E4+G4:2                           – akord
 *   K S H O T X Z  (np. K:8, K+H:8)      – perkusja: stopa, werbel, hi-hat,
 *                                          otwarty hi-hat, tom, crash, klaśnięcie
 *   @1 … @2 … @3 … @4                    – osobne głosy (grane równocześnie)
 *   !pluck !lead !wah …                  – barwa dla bieżącego głosu (preset)
 *   !d30 !v20 !g50 !global               – wypełnienie %, vibrato w centach, glissando ms, barwa z UI
 *   !t136  !mix  !arp                    – tempo i tryb polifonii całego utworu
 * </pre>
 */
final class Melody {

    static final int TONE = 0, KICK = 1, SNARE = 2, HAT = 3, OPEN_HAT = 4, TOM = 5, CRASH = 6, CLAP = 7;

    static final String DRUM_LETTERS = "KSHOTXZ";
    static final String[] DRUM_NAMES = {"stopa", "werbel", "hi-hat", "otwarty hi-hat", "tom", "crash", "klaśnięcie"};

    static final class Sound {
        final int type;
        final double freq;

        Sound(int type, double freq) {
            this.type = type;
            this.freq = freq;
        }
    }

    static final class Event {
        final Sound[] sounds;   // pusta tablica = pauza
        final double beats;     // w ćwierćnutach
        final String label;
        final Timbre timbre;    // null = barwa z ustawień

        Event(Sound[] sounds, double beats, String label, Timbre timbre) {
            this.sounds = sounds;
            this.beats = beats;
            this.label = label;
            this.timbre = timbre;
        }
    }

    static final class Song {
        final List<List<Event>> voices = new ArrayList<>();
        int bpm = -1;        // -1 = z UI
        int mix = -1;        // -1 = z UI, 0 = arpeggio, 1 = miks
    }

    static final int MAX_VOICES = 4;

    private static final Pattern NOTE = Pattern.compile("^([A-Ga-g])([#b]?)(-?\\d)?$");
    private static final Pattern FREQ = Pattern.compile("^\\d+(?:\\.\\d+)?$");
    private static final Pattern LEN = Pattern.compile("^(\\d+)(\\.?)$");
    private static final Pattern VOICE = Pattern.compile("^@(\\d)$");
    private static final Pattern DIRECTIVE = Pattern.compile("^!([a-zA-Z]+)(\\d*)$");

    private static final int[] SEMI = {9, 11, 0, 2, 4, 5, 7}; // A B C D E F G

    private Melody() {}

    static double noteFreq(int midi) {
        return 440.0 * Math.pow(2.0, (midi - 69) / 12.0);
    }

    static int midi(char letter, int accidental, int octave) {
        return 12 * (octave + 1) + SEMI[Character.toUpperCase(letter) - 'A'] + accidental;
    }

    private static double beats(String len) {
        if (len == null) return 1.0;
        Matcher m = LEN.matcher(len);
        if (!m.matches()) throw new IllegalArgumentException("zła długość: \"" + len + "\"");
        int n = Integer.parseInt(m.group(1));
        if (n <= 0 || n > 64) throw new IllegalArgumentException("zła długość: " + len);
        double b = 4.0 / n;
        if (!m.group(2).isEmpty()) b *= 1.5;
        return b;
    }

    static Song parse(String text) {
        Song song = new Song();
        List<List<Event>> voices = new ArrayList<>();
        Timbre[] tb = new Timbre[MAX_VOICES];
        for (int i = 0; i < MAX_VOICES; i++) voices.add(new ArrayList<>());
        int voice = 0;
        for (String line : text.split("\n")) {
            int c = line.indexOf("//");
            if (c >= 0) line = line.substring(0, c);
            for (String tok : line.trim().split("[\\s,;|]+")) {
                if (tok.isEmpty()) continue;
                Matcher m = VOICE.matcher(tok);
                if (m.matches()) {
                    voice = Integer.parseInt(m.group(1)) - 1;
                    if (voice < 0 || voice >= MAX_VOICES)
                        throw new IllegalArgumentException("głosy: @1 … @" + MAX_VOICES);
                    continue;
                }
                m = DIRECTIVE.matcher(tok);
                if (m.matches()) {
                    tb[voice] = directive(song, tb[voice], m.group(1).toLowerCase(), m.group(2), tok);
                    continue;
                }
                voices.get(voice).add(parseToken(tok, tb[voice]));
            }
        }
        for (List<Event> v : voices) if (!v.isEmpty()) song.voices.add(v);
        return song;
    }

    private static Timbre directive(Song song, Timbre cur, String name, String num, String tok) {
        int v = num.isEmpty() ? -1 : Integer.parseInt(num);
        Timbre base = cur != null ? cur.copy() : new Timbre();
        switch (name) {
            case "t":
                if (v < 10 || v > 600) throw new IllegalArgumentException("tempo: " + tok);
                song.bpm = v;
                return cur;
            case "mix": song.mix = 1; return cur;
            case "arp": song.mix = 0; return cur;
            case "global": return null;
            case "d":
                if (v < 2 || v > 98) throw new IllegalArgumentException("wypełnienie 2–98 %: " + tok);
                base.d0 = base.d1 = v / 100.0;
                base.lfoHz = 0;
                return base;
            case "v":
                if (v < 0) throw new IllegalArgumentException(tok);
                base.vibCents = v;
                return base;
            case "g":
                if (v < 0) throw new IllegalArgumentException(tok);
                base.glideMs = v;
                return base;
            default:
                Timbre p = Timbre.preset(name);
                if (p == null || v >= 0) throw new IllegalArgumentException("nieznana komenda: " + tok);
                return p;
        }
    }

    private static Event parseToken(String tok, Timbre tb) {
        int colon = tok.indexOf(':');
        String body = colon >= 0 ? tok.substring(0, colon) : tok;
        double beats = beats(colon >= 0 ? tok.substring(colon + 1) : null);
        if (body.equalsIgnoreCase("R") || body.equalsIgnoreCase("P")) {
            return new Event(new Sound[0], beats, "pauza", tb);
        }
        String[] parts = body.split("\\+");
        Sound[] sounds = new Sound[parts.length];
        StringBuilder label = new StringBuilder();
        for (int i = 0; i < parts.length; i++) {
            String p = parts[i];
            if (i > 0) label.append(" + ");
            Matcher m;
            int drum = p.length() == 1 ? DRUM_LETTERS.indexOf(Character.toUpperCase(p.charAt(0))) : -1;
            if (drum >= 0) {
                sounds[i] = new Sound(KICK + drum, 0);
                label.append(DRUM_NAMES[drum]);
            } else if ((m = NOTE.matcher(p)).matches()) {
                char letter = m.group(1).charAt(0);
                int acc = "#".equals(m.group(2)) ? 1 : "b".equals(m.group(2)) ? -1 : 0;
                int oct = m.group(3) != null ? Integer.parseInt(m.group(3)) : 4;
                double f = noteFreq(midi(letter, acc, oct));
                sounds[i] = new Sound(TONE, f);
                label.append(Character.toUpperCase(letter)).append(m.group(2)).append(oct);
                if (parts.length == 1) label.append(String.format(Locale.US, "  %.1f Hz", f));
            } else if (FREQ.matcher(p).matches()) {
                double f = Double.parseDouble(p);
                if (f < 1 || f > 20000) throw new IllegalArgumentException("częstotliwość poza zakresem: " + p);
                sounds[i] = new Sound(TONE, f);
                label.append(String.format(Locale.US, "%.1f Hz", f));
            } else {
                throw new IllegalArgumentException("nie rozumiem: \"" + tok + "\"");
            }
        }
        return new Event(sounds, beats, label.toString(), tb);
    }
}
