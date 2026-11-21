package io.github.szuszjan.irmusic;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Parser prostej notacji tekstowej, np. "C4:4 D#4:8 R:8 440:4 E5:4." */
final class Melody {

    static final class Note {
        final double freq;   // 0 = pauza
        final double beats;  // w ćwierćnutach
        final String label;

        Note(double freq, double beats, String label) {
            this.freq = freq;
            this.beats = beats;
            this.label = label;
        }

        boolean isRest() {
            return freq <= 0;
        }
    }

    private static final Pattern NOTE =
            Pattern.compile("^([A-Ga-g])([#b]?)(-?\\d)?(?::(\\d+)(\\.?))?$");
    private static final Pattern REST =
            Pattern.compile("^[RrPp](?::(\\d+)(\\.?))?$");
    private static final Pattern FREQ =
            Pattern.compile("^(\\d+(?:\\.\\d+)?)(?::(\\d+)(\\.?))?$");

    private static final int[] SEMI = {9, 11, 0, 2, 4, 5, 7}; // A B C D E F G

    private Melody() {}

    static double noteFreq(int midi) {
        return 440.0 * Math.pow(2.0, (midi - 69) / 12.0);
    }

    static int midi(char letter, int accidental, int octave) {
        int semi = SEMI[Character.toUpperCase(letter) - 'A'];
        return 12 * (octave + 1) + semi + accidental;
    }

    private static double beats(String len, String dot) {
        double b = 1.0;
        if (len != null && !len.isEmpty()) {
            int n = Integer.parseInt(len);
            if (n <= 0 || n > 64) throw new IllegalArgumentException("zła długość: " + len);
            b = 4.0 / n;
        }
        if (dot != null && !dot.isEmpty()) b *= 1.5;
        return b;
    }

    static List<Note> parse(String text) {
        List<Note> out = new ArrayList<>();
        for (String line : text.split("\n")) {
            int c = line.indexOf("//");
            if (c >= 0) line = line.substring(0, c);
            for (String tok : line.trim().split("[\\s,;|]+")) {
                if (tok.isEmpty()) continue;
                Matcher m;
                if ((m = REST.matcher(tok)).matches()) {
                    out.add(new Note(0, beats(m.group(1), m.group(2)), "pauza"));
                } else if ((m = NOTE.matcher(tok)).matches()) {
                    char letter = m.group(1).charAt(0);
                    int acc = "#".equals(m.group(2)) ? 1 : "b".equals(m.group(2)) ? -1 : 0;
                    int oct = m.group(3) != null ? Integer.parseInt(m.group(3)) : 4;
                    double f = noteFreq(midi(letter, acc, oct));
                    String label = String.format(Locale.US, "%s%s%d  %.1f Hz",
                            Character.toUpperCase(letter), m.group(2), oct, f);
                    out.add(new Note(f, beats(m.group(4), m.group(5)), label));
                } else if ((m = FREQ.matcher(tok)).matches()) {
                    double f = Double.parseDouble(m.group(1));
                    if (f < 1 || f > 20000) throw new IllegalArgumentException("częstotliwość poza zakresem: " + tok);
                    out.add(new Note(f, beats(m.group(2), m.group(3)),
                            String.format(Locale.US, "%.1f Hz", f)));
                } else {
                    throw new IllegalArgumentException("nie rozumiem: \"" + tok + "\"");
                }
            }
        }
        return out;
    }
}
