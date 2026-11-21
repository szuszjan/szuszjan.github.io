package io.github.szuszjan.irmusic;

import java.util.ArrayList;
import java.util.List;
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

    private static String rep(String bar, int times) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < times; i++) sb.append(bar).append(i % 4 == 3 ? "\n" : " | ");
        return sb.toString();
    }

    private static String octUp(String note) {
        int o = note.charAt(note.length() - 1) - '0';
        return note.substring(0, note.length() - 1) + (o + 1);
    }

    private static final String KOROBEINIKI = join(PART_A, PART_A, PART_B, PART_A, PART_A);

    private static final String KOROBEINIKI_TECHNO =
            (techno(PART_A, BASS_A) + techno(PART_A, BASS_A)
                    + techno(PART_B, BASS_B) + techno(PART_A, BASS_A)).trim();

    /** Korobeiniki na 3 głosy: melodia (lead), bas ósemkami, perkusja. */
    private static String korobeinikiTrio() {
        StringBuilder mel = new StringBuilder("@1 !lead\n");
        StringBuilder bass = new StringBuilder("@2 !bas\n");
        StringBuilder dr = new StringBuilder("@3\n");
        String[][] parts = {PART_A, PART_A, PART_B, PART_A};
        String[][] basses = {BASS_A, BASS_A, BASS_B, BASS_A};
        for (int p = 0; p < parts.length; p++) {
            boolean slow = parts[p] == PART_B;
            for (int b = 0; b < 8; b++) {
                mel.append(parts[p][b]).append(b % 4 == 3 ? "\n" : " | ");
                String r = basses[p][b], u = octUp(r);
                bass.append(slow ? r + ":2 " + u + ":2" : rep4(r + ":8 " + u + ":8")).append(b % 4 == 3 ? "\n" : " | ");
                String drum;
                if (b == 0) drum = "K+X:8 H:8 S:8 H:8 K:8 K:8 S:8 H:8";
                else if (b == 7 && !slow) drum = "K:8 H:8 S:8 H:8 S:16 S:16 T:16 T:16 S:16 S:16 T:16 T:16";
                else if (slow) drum = "K:4 O:4 Z:4 O:4";
                else drum = "K:8 H:8 S:8 H:8 K:8 K:8 S:8 H:8";
                dr.append(drum).append(b % 4 == 3 ? "\n" : " | ");
            }
        }
        return "!t140 !mix\n" + mel + "\n" + bass + "\n" + dr;
    }

    private static String rep4(String beatPair) {
        return beatPair + " " + beatPair + " " + beatPair + " " + beatPair;
    }

    // ---------------------------------------------------------------
    // "Podczerwień" – własny utwór techno, 32 takty, 4 głosy
    // ---------------------------------------------------------------

    private static final String[] ROOTS = {"A2", "F2", "C3", "G2"};
    private static final String[] CHORDS = {"A3+C4+E4", "F3+A3+C4", "G3+C4+E4", "G3+B3+D4"};
    private static final String[][] ARP = {
            {"A3", "C4", "E4", "A4"}, {"F3", "A3", "C4", "F4"}, {"G3", "C4", "E4", "G4"}, {"G3", "B3", "D4", "G4"}};
    private static final String[] LEAD = {
            "E5:8 A4:8 C5:8 E5:8 D5:4 C5:8 B4:8",
            "C5:4 A4:4 F4:8 A4:8 C5:4",
            "G4:8 C5:8 E5:8 G5:8 E5:4 D5:8 C5:8",
            "D5:2 B4:4 G4:4",
            "E5:8 A5:8 G5:8 E5:8 C5:4 E5:4",
            "F5:4. E5:8 C5:4 A4:4",
            "G4:8 C5:8 E5:8 G5:8 C6:4 B5:8 G5:8",
            "B5:2. R:4",
    };

    private static final String D_INTRO = "K:8 H:8 K:8 H:8 K:8 H:8 K:8 H:8";
    private static final String D_MAIN = "K:8 H:8 K+S:8 H:8 K:8 H:16 H:16 K+Z:8 O:8";
    private static final String D_CRASH = "K+X:8 H:8 K+S:8 H:8 K:8 H:16 H:16 K+Z:8 O:8";
    private static final String D_FILL = "S:16 S:16 S:16 S:16 T:16 T:16 S:16 S:16 T:8 T:8 S:16 S:16 S:16 S:16";
    private static final String D_CLAP = "R:4 Z:4 R:4 Z:4";
    private static final String STAB = "R:8 %1$s:8 R:8 %1$s:16 %1$s:16 R:4 %1$s:8 R:8";

    private static String bars(String fmtPerChord, int times) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < times; i++) {
            int c = i % 4;
            String bar;
            if (fmtPerChord.equals("bass")) {
                String r = ROOTS[c];
                bar = rep4("R:16 " + r + ":16 " + r + ":16 " + r + ":16");
            } else if (fmtPerChord.equals("stab")) {
                bar = String.format(STAB, CHORDS[c]);
            } else if (fmtPerChord.equals("pad")) {
                bar = CHORDS[c] + ":1";
            } else if (fmtPerChord.equals("arp")) {
                StringBuilder a = new StringBuilder();
                for (int k = 0; k < 16; k++) a.append(ARP[c][k % 4]).append(":16 ");
                bar = a.toString().trim();
            } else {
                bar = fmtPerChord;
            }
            sb.append(bar).append(i % 4 == 3 ? "\n" : " | ");
        }
        return sb.toString();
    }

    private static String rep4bars(String[] b) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < b.length; i++) sb.append(b[i]).append(i % 4 == 3 ? "\n" : " | ");
        return sb.toString();
    }

    private static String podczerwien() {
        String lead8 = rep4bars(LEAD);
        String drums8 = D_CRASH + " | " + rep(D_MAIN, 6) + D_FILL + "\n";
        return "// Podczerwień – techno na diodę IR (tryb miks, 4 głosy)\n"
                + "!t136 !mix\n\n"
                // --- lead: cisza 8 taktów, melodia, acid-arpeggio w breakdownie, melodia, cisza
                + "@1 !lead\n"
                + "// intro + wejście basu\n" + rep("R:1", 8)
                + "// temat\n" + lead8
                + "// breakdown – acid arpeggio\n!acid\n" + bars("arp", 4)
                + "// drop\n!lead !v30\n" + lead8
                + "// outro\n" + rep("R:1", 4) + "\n"
                // --- akordy
                + "@2 !pluck\n"
                + rep("R:1", 8) + bars("stab", 8)
                + "!wah\n" + bars("pad", 4)
                + "!pluck\n" + bars("stab", 8)
                + rep("R:1", 4) + "\n"
                // --- bas
                + "@3 !bas\n"
                + rep("R:1", 4) + bars("bass", 12)
                + rep("R:1", 4)
                + "!acid\n" + bars("bass", 12) + "\n"
                // --- perkusja
                + "@4\n"
                + rep(D_INTRO, 4)
                + rep(D_MAIN, 3) + D_FILL + "\n"
                + drums8
                + rep(D_CLAP, 3) + D_FILL + "\n"
                + drums8
                + rep(D_INTRO, 3) + "K+X:1\n";
    }

    // ---------------------------------------------------------------
    // "Techno 135, d-moll" – przepisane z bytebeatu na nuty (4 głosy)
    // ---------------------------------------------------------------

    private static final String[] NOTE_NAMES = {"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"};

    private static String nn(int midi) {
        return NOTE_NAMES[midi % 12] + (midi / 12 - 1);
    }

    private static final String ACA = "0.0<.03.0.5.0:7.", ACB = "0.0<0.75.03.0<?.",
            STABS = "..1...1...1..1..", TOMS = "..1..2....1..2..";
    private static final int[][] CHORD7 = {{62, 65, 69, 72}, {60, 63, 67, 70}}; // Dm7, Cm7

    private static int secOf(int b) {
        return b < 16 ? 0 : b < 32 ? 1 : b < 48 ? 2 : b < 64 ? 3 : b < 96 ? 4 : b < 112 ? 5 : 6;
    }

    /** Zamienia 16 pozycji (null = cisza) na tokeny, scalając pauzy. */
    private static String grid(String[] g) {
        StringBuilder sb = new StringBuilder();
        int rest = 0;
        for (int i = 0; i <= 16; i++) {
            if (i < 16 && g[i] == null) {
                rest++;
                continue;
            }
            while (rest > 0) {
                int[] lens = {16, 12, 8, 6, 4, 3, 2, 1};
                String[] toks = {"R:1", "R:2.", "R:2", "R:4.", "R:4", "R:8.", "R:8", "R:16"};
                for (int k = 0; k < lens.length; k++) {
                    if (lens[k] <= rest) {
                        sb.append(toks[k]).append(' ');
                        rest -= lens[k];
                        break;
                    }
                }
            }
            if (i < 16) sb.append(g[i]).append(":16 ");
        }
        return sb.toString().trim();
    }

    /** Zwija powtarzające się frazy (1, 2, 4 lub 8 taktów) w [ … ]xN, każda fraza w osobnej linii. */
    private static String compress(List<String> bars) {
        StringBuilder sb = new StringBuilder();
        int i = 0;
        while (i < bars.size()) {
            int bestP = 1, bestK = 1;
            for (int p : new int[]{1, 2, 4, 8}) {
                int k = 1;
                while (i + (k + 1) * p <= bars.size()
                        && bars.subList(i, i + p).equals(bars.subList(i + k * p, i + (k + 1) * p))) k++;
                if (k > 1 && k * p > bestK * bestP) {
                    bestP = p;
                    bestK = k;
                }
            }
            StringBuilder phrase = new StringBuilder();
            for (int j = 0; j < bestP; j++) phrase.append(j > 0 ? " | " : "").append(bars.get(i + j));
            sb.append(bestK > 1 ? "[" + phrase + "]x" + bestK : phrase).append("\n");
            i += bestP * bestK;
        }
        return sb.toString().trim();
    }

    private static String technoFromBytebeat() {
        final int BARS = 124;  // takty 124–127 to w oryginale już tylko wybrzmienie
        List<String> acid = new ArrayList<>(), stab = new ArrayList<>(), low = new ArrayList<>(), dr = new ArrayList<>();
        for (int b = 0; b < BARS; b++) {
            int sc = secOf(b), ci = b & 3;
            boolean gapBar = b == 63;   // cisza przez ostatnie pół miary przed dropem
            // --- acid
            String[] g = new String[16];
            if (sc == 2 || sc == 4 || sc == 5 || (sc == 3 && b >= 56) || (sc == 6 && b < 108)) {
                String pat = (b & 1) != 0 ? ACB : ACA;
                int base = 50 - (ci == 3 ? 2 : 0);
                for (int st = 0; st < 16; st++) {
                    int c = pat.charAt(st) - 48;
                    if (c >= 0 && !(gapBar && st >= 14)) g[st] = nn(base + c);
                }
            }
            acid.add(grid(g));
            // --- stabsy
            g = new String[16];
            if ((sc == 2 && b >= 40) || sc == 3 || sc == 4) {
                int[] ch = CHORD7[ci == 3 ? 1 : 0];
                String chord = nn(ch[0]) + "+" + nn(ch[1]) + "+" + nn(ch[2]) + "+" + nn(ch[3]);
                for (int st = 0; st < 16; st++) if (STABS.charAt(st) == '1') g[st] = chord;
            }
            stab.add(grid(g));
            // --- bas / pad / riser
            if (sc == 3 && b < 56) {
                int[] ch = CHORD7[ci == 3 ? 1 : 0];
                low.add(nn(ch[0]) + "+" + nn(ch[1]) + "+" + nn(ch[2]) + "+" + nn(ch[3]) + ":1");
            } else if (b >= 56 && b < 64) {
                g = new String[16];
                for (int st = 0; st < 16; st++) {
                    if (gapBar && st >= 14) break;
                    double r = ((b - 56) * 16 + st) / 128.0;
                    g[st] = String.valueOf(Math.round(150 * Math.pow(10, r)));   // 150 → 1500 Hz
                }
                low.add(grid(g));
            } else if (b >= 16 && sc != 3 && !(sc == 6 && b >= 120)) {
                String n = ci == 3 ? "C2" : "D2";
                low.add("R:8 " + n + ":8 R:8 " + n + ":8 R:8 " + n + ":8 R:8 " + n + ":8");
            } else {
                low.add("R:1");
            }
            // --- perkusja
            g = new String[16];
            boolean kick = sc != 3 && !(sc == 6 && b >= 124);
            boolean open = b >= 4 && sc != 3 && !(sc == 6 && b >= 124);
            boolean closed = b >= 8 && (sc != 3 || b >= 56) && !(sc == 6 && b >= 124);
            boolean clap = b >= 24 && sc != 3 && !(sc == 6 && b >= 116);
            boolean toms = (sc == 1 && b >= 24) || sc == 2 || sc == 4 || sc == 5 || (sc == 6 && b < 116);
            boolean crash = b == 32 || b == 64 || b == 96 || b == 112;
            for (int st = 0; st < 16; st++) {
                int sub = st & 3;
                StringBuilder d = new StringBuilder();
                if (kick && sub == 0) d.append("+K");
                if (crash && st == 0) d.append("+X");
                if (open && sub == 2) d.append("+O");
                if ((closed && sub == 1) || (sc == 4 && (sub == 0 || sub == 3))) d.append("+H");
                if (clap && (st == 4 || st == 12)) d.append("+Z");
                if (toms && TOMS.charAt(st) != '.') d.append("+T");
                if (b == 62 && st % 2 == 0) d.append("+S");
                if (b == 63 && st < 14) d.append("+S");
                if (gapBar && st >= 14) d.setLength(0);
                if (d.length() > 0) g[st] = d.substring(1);
            }
            dr.add(grid(g));
        }
        return "// Techno 135 BPM, d-moll – przepisane z bytebeatu na nuty\n"
                + "// takty: 0 intro, 16 bas, 32 acid, 48 breakdown (pad, riser, werbelek), 64 drop, 96, 112 outro\n"
                + "!t135 !mix\n\n"
                + "@1 !acid   // linia acid\n" + compress(acid) + "\n\n"
                + "@2 !pluck  // stabsy Dm7 / Cm7\n" + compress(stab) + "\n\n"
                + "@3 !bas    // bas na offbeat; w breakdownie pad i riser\n" + compress(low.subList(0, 48))
                + "\n!wah\n" + compress(low.subList(48, 56))
                + "\n!czysty !g0\n" + compress(low.subList(56, 64))
                + "\n!bas\n" + compress(low.subList(64, BARS)) + "\n\n"
                + "@4        // perkusja\n" + compress(dr) + "\n";
    }

    static final String[] NAMES = {
            "— własna —",
            "Korobeiniki (pełna: A A B A A)",
            "Korobeiniki – szybka",
            "Korobeiniki – techno (przeplatany bas)",
            "Korobeiniki – 3 głosy + perkusja (miks)",
            "Podczerwień – techno, 4 głosy (miks)",
            "Techno 135 d-moll – z bytebeatu (miks)",
            "Demo perkusji",
            "Test: akordy (porównaj arpeggio / miks)",
            "Test: gama C-dur",
            "Test: oktawy 110–1760 Hz",
            "Test: syrena",
    };

    static final int[] BPM = {120, 150, 230, 140, 140, 136, 135, 120, 70, 160, 60, 240};

    static final String[] NOTES = {
            "",
            KOROBEINIKI,
            KOROBEINIKI,
            KOROBEINIKI_TECHNO,
            korobeinikiTrio(),
            podczerwien(),
            technoFromBytebeat(),
            "// pojedynczo: stopa, werbel, hi-hat, otwarty hi-hat, tom, crash, klaśnięcie\n"
                    + "K:4 S:4 H:4 O:4 T:4 X:2. Z:4 R:4\n"
                    + "// rytm\n"
                    + rep(D_MAIN, 3) + D_FILL + "\n" + rep(D_MAIN, 3) + "K+X:1",
            "C4+E4+G4:2 A3+C4+E4:2 F3+A3+C4:2 G3+B3+D4:2\n"
                    + "@2 C3:2 A2:2 F2:2 G2:2",
            "C4 D4 E4 F4 G4 A4 B4 C5:2 C5 B4 A4 G4 F4 E4 D4 C4:2",
            "110:4 220:4 440:4 880:4 1760:4 R:4",
            "400:8 450:8 500:8 560:8 630:8 700:8 790:8 880:8 790:8 700:8 630:8 560:8 500:8 450:8",
    };

    static final int DEFAULT = 5;
}
