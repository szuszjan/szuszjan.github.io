package io.github.szuszjan.irmusic;

/**
 * Zamiana sygnału audio (-1..1) na 1 bit (nośna wł./wył.) z ograniczeniem
 * minimalnej długości stanu – tyle potrzebuje odbiornik TSOP.
 */
final class OneBit {
    static final int COMPARATOR = 0, SIGMA_DELTA = 1;
    static final String[] MODES = {
            "Komparator (twardy przester, cisza = cisza)",
            "Sigma-delta (zachowuje głośność, szumi)"};

    private final int mode;
    private final double minRun, gain, dt, vMax;
    private boolean y;
    private double run, v, env;

    OneBit(int mode, double minRunUs, double gain, double sampleRate) {
        this.mode = mode;
        this.minRun = minRunUs;
        this.gain = gain;
        this.dt = 1e6 / sampleRate;
        this.vMax = 2 * Math.max(1, minRunUs / dt) + 2;   // integrator musi pomieścić cały wymuszony stan
    }

    double dtUs() {
        return dt;
    }

    /** @return stan nośnej po tej próbce */
    boolean step(double s) {
        double x = Math.max(-1, Math.min(1, s * gain));
        boolean want;
        if (mode == SIGMA_DELTA) {
            env = Math.max(Math.abs(x), env * 0.999);          // obwiednia (~23 ms)
            if (env < 0.03) {                                   // bramka: w ciszy nie piszczymy
                want = false;
                v = 0;
            } else {
                v += x - (y ? 1 : -1);
                v = Math.max(-vMax, Math.min(vMax, v));
                want = v > 0;
            }
        } else {
            want = y ? x > -0.02 : x > 0.02;                    // histereza
        }
        run += dt;
        if (want != y && run >= minRun) {
            y = want;
            run = 0;
        }
        return y;
    }
}
