package io.github.szuszjan.irmusic;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Wbudowane melodie (domena publiczna). */
final class Songs {
    private Songs() {}

    // ---------------------------------------------------------------
    // Korobeiniki (rosyjska pieśń ludowa) – takty
    // ---------------------------------------------------------------

    /** Część A (8 taktów, 4/4). */
    private static final String[] PART_A = {
            "E5:4 B4:8 C5:8 D5:4 C5:8 B4:8",
            "A4:4 A4:8 C5:8 E5:4 D5:8 C5:8",
            "B4:4. C5:8 D5:4 E5:4",
            "C5:4 A4:4 A4:2",
            "R:8 D5:4 F5:8 A5:4 G5:8 F5:8",
            "E5:4. C5:8 E5:4 D5:8 C5:8",
            "B4:4 B4:8 C5:8 D5:4 E5:4",
            "C5:4 A4:4 A4:2",
    };
    private static final String[] BASS_A = {"E2", "A2", "E2", "A2", "D3", "C3", "E2", "A2"};

    /** Część B (wolna, 8 taktów). */
    private static final String[] PART_B = {
            "E5:2 C5:2",
            "D5:2 B4:2",
            "C5:2 A4:2",
            "G#4:2 B4:2",
            "E5:2 C5:2",
            "D5:2 B4:2",
            "C5:4 E5:4 A5:2",
            "G#5:1",
    };
    private static final String[] BASS_B = {"A2", "E2", "A2", "E2", "A2", "E2", "A2", "E2"};

    private static String join(String[]... parts) {
        StringBuilder sb = new StringBuilder();
        for (String[] part : parts) {
            for (int i = 0; i < part.length; i++) {
                sb.append(part[i]).append(i % 4 == 3 ? "\n" : " | ");
            }
            sb.append("\n");
        }
        return sb.toString().trim();
    }

    private static final Pattern TOK = Pattern.compile("^([^:]+):(\\d+)(\\.?)$");

    /**
     * Własna aranżacja "techno": każda szesnastka na przemian melodia / bas.
     * Dźwięki melodii dłuższe niż ósemka są powtarzane, co daje pulsujący efekt.
     */
    private static String techno(String[] bars, String[] bass) {
        StringBuilder sb = new StringBuilder();
        for (int b = 0; b < bars.length; b++) {
            int step = 0;
            for (String tok : bars[b].trim().split("\\s+")) {
                Matcher m = TOK.matcher(tok);
                if (!m.matches()) throw new IllegalStateException(tok);
                int sixteenths = 16 / Integer.parseInt(m.group(2));
                if (!m.group(3).isEmpty()) sixteenths = sixteenths * 3 / 2;
                String mel = m.group(1);
                for (int i = 0; i < sixteenths; i++, step++) {
                    sb.append(step % 2 == 0 ? mel : bass[b]).append(":16 ");
                }
            }
            sb.append(b % 4 == 3 ? "\n" : "| ");
        }
        return sb.toString();
    }

    private static final String KOROBEINIKI = join(PART_A, PART_A, PART_B, PART_A, PART_A);

    private static final String KOROBEINIKI_TECHNO =
            (techno(PART_A, BASS_A) + techno(PART_A, BASS_A)
                    + techno(PART_B, BASS_B) + techno(PART_A, BASS_A)).trim();

    static final String[] NAMES = {
            "— własna —",
            "Korobeiniki (pełna: A A B A A)",
            "Korobeiniki – szybka",
            "Korobeiniki – techno (własna aranżacja z basem)",
            "Test: gama C-dur",
            "Test: oktawy 110–1760 Hz",
            "Test: syrena",
    };

    static final int[] BPM = {120, 150, 230, 140, 160, 60, 240};

    static final String[] NOTES = {
            "",
            KOROBEINIKI,
            KOROBEINIKI,
            KOROBEINIKI_TECHNO,
            "C4 D4 E4 F4 G4 A4 B4 C5:2 C5 B4 A4 G4 F4 E4 D4 C4:2",
            "110:4 220:4 440:4 880:4 1760:4 R:4",
            "400:8 450:8 500:8 560:8 630:8 700:8 790:8 880:8 790:8 700:8 630:8 560:8 500:8 450:8",
    };

    static final int DEFAULT = 1;
}
