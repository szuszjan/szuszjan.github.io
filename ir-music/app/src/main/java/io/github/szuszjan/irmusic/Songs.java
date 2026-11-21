package io.github.szuszjan.irmusic;

/** Wbudowane melodie (ludowe / domena publiczna). */
final class Songs {
    private Songs() {}

    static final String[] NAMES = {
            "— własna —",
            "Gama C-dur",
            "Wlazł kotek na płotek",
            "Panie Janie",
            "Oda do radości",
            "Mrugaj, gwiazdko",
            "Happy Birthday",
            "Dla Elizy (początek)",
            "Korobeiniki",
            "Test: oktawy 110–1760 Hz",
            "Test: syrena",
    };

    static final int[] BPM = {120, 160, 140, 140, 130, 130, 110, 80, 150, 60, 240};

    static final String[] NOTES = {
            "",
            // Gama
            "C4 D4 E4 F4 G4 A4 B4 C5:2 C5 B4 A4 G4 F4 E4 D4 C4:2",
            // Wlazł kotek
            "G4:8 E4:8 E4:4 F4:8 D4:8 D4:4 C4:8 E4:8 G4:4 R:4\n"
                    + "G4:8 E4:8 E4:4 F4:8 D4:8 D4:4 C4:8 E4:8 C4:4 R:4",
            // Panie Janie
            "C4 D4 E4 C4 C4 D4 E4 C4\n"
                    + "E4 F4 G4:2 E4 F4 G4:2\n"
                    + "G4:8 A4:8 G4:8 F4:8 E4 C4 G4:8 A4:8 G4:8 F4:8 E4 C4\n"
                    + "C4 G3 C4:2 C4 G3 C4:2",
            // Oda do radości
            "E4 E4 F4 G4 G4 F4 E4 D4 C4 C4 D4 E4 E4:4. D4:8 D4:2\n"
                    + "E4 E4 F4 G4 G4 F4 E4 D4 C4 C4 D4 E4 D4:4. C4:8 C4:2",
            // Twinkle
            "C4 C4 G4 G4 A4 A4 G4:2 F4 F4 E4 E4 D4 D4 C4:2\n"
                    + "G4 G4 F4 F4 E4 E4 D4:2 G4 G4 F4 F4 E4 E4 D4:2\n"
                    + "C4 C4 G4 G4 A4 A4 G4:2 F4 F4 E4 E4 D4 D4 C4:2",
            // Happy Birthday
            "G4:8. G4:16 A4 G4 C5 B4:2\n"
                    + "G4:8. G4:16 A4 G4 D5 C5:2\n"
                    + "G4:8. G4:16 G5 E5 C5 B4 A4:2\n"
                    + "F5:8. F5:16 E5 C5 D5 C5:2",
            // Dla Elizy
            "E5:16 D#5:16 E5:16 D#5:16 E5:16 B4:16 D5:16 C5:16 A4:8 R:16 C4:16 E4:16 A4:16 B4:8 R:16\n"
                    + "E4:16 G#4:16 B4:16 C5:8 R:16 E4:16\n"
                    + "E5:16 D#5:16 E5:16 D#5:16 E5:16 B4:16 D5:16 C5:16 A4:8 R:16 C4:16 E4:16 A4:16 B4:8 R:16\n"
                    + "E4:16 C5:16 B4:16 A4:4",
            // Korobeiniki
            "E5 B4:8 C5:8 D5 C5:8 B4:8 A4 A4:8 C5:8 E5 D5:8 C5:8\n"
                    + "B4:4. C5:8 D5 E5 C5 A4 A4:2\n"
                    + "R:8 D5:4. F5:8 A5 G5:8 F5:8 E5:4. C5:8 E5 D5:8 C5:8\n"
                    + "B4 B4:8 C5:8 D5 E5 C5 A4 A4:2",
            // Oktawy
            "110:4 220:4 440:4 880:4 1760:4 R:4",
            // Syrena
            "400:8 450:8 500:8 560:8 630:8 700:8 790:8 880:8 790:8 700:8 630:8 560:8 500:8 450:8",
    };
}
