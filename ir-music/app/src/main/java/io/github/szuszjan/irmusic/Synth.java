package io.github.szuszjan.irmusic;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Random;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Syntezator 1-bitowy: zamienia nuty / perkusję / wzorce na ciąg impulsów
 * nośnej IR (wł./wył. w µs) i wysyła je paczkami przez {@link Emitter}.
 */
final class Synth {

    interface Emitter {
        void transmit(int carrier, int[] pattern);
    }

    interface Listener {
        void status(String s);

        void error(String s);
    }

    interface FreqSource {
        double get();
    }

    static final class Settings {
        int carrier = 38000;
        double maxChunkUs = 400_000;
        int maxEntries = 1000;
        double gapUs = 25_000;
        int bpm = 120;
        double minPulse = 30;
        Timbre timbre = new Timbre();
        boolean mix = false;
        double arpUs = 20_000;
        double mixPulseUs = 350;
    }

    /** Dłuższą ciszę niż ta czekamy poza transmit() (limit ~2 s na wywołanie). */
    private static final double MAX_TAIL_OFF = 30_000;

    private final Emitter em;
    private final AtomicInteger gen;
    private final int my;
    private final Settings s;
    private final Listener l;
    private final Random rnd = new Random();

    private int carrier;
    private final double[] buf;
    private int n;
    private double acc;
    private boolean failed;

    interface Skip {
        void silence(double us);
    }

    /** false = bez czekania (testy na PC); cisza trafia wtedy do {@link #skip}. */
    boolean realtime = true;
    Skip skip;
    /** Statystyka (testy): suma czasu wysłanych wzorców i liczba wywołań transmit(). */
    long sentUs, calls;

    Synth(Emitter em, AtomicInteger gen, int my, Settings s, Listener l) {
        this.em = em;
        this.gen = gen;
        this.my = my;
        this.s = s;
        this.l = l;
        this.carrier = s.carrier;
        this.buf = new double[Math.max(4, s.maxEntries) + 2];
    }

    boolean alive() {
        return !failed && gen.get() == my;
    }

    // =================================================================
    // Bufor impulsów
    // =================================================================

    /** Nośna włączona przez {@code us}. */
    void on(double us) {
        if (us <= 0 || failed) return;
        if (n % 2 == 1) {                       // ostatni wpis to "wł." – wydłużamy
            if (acc + us > s.maxChunkUs) {      // nie przekraczaj limitu paczki
                off(s.minPulse);
                flush();
                buf[n++] = us;
            } else {
                buf[n - 1] += us;
            }
        } else {
            if (n + 2 > s.maxEntries || acc >= s.maxChunkUs) flush();
            buf[n++] = us;
        }
        acc += us;
    }

    /** Nośna wyłączona przez {@code us}. */
    void off(double us) {
        if (us <= 0 || failed) return;
        if (n == 0) {
            sleepUs(us);
            return;
        }
        if (n % 2 == 1) buf[n++] = 0;
        double room = MAX_TAIL_OFF - buf[n - 1];
        if (us <= room) {
            buf[n - 1] += us;
            acc += us;
        } else {
            double add = Math.max(0, room);
            buf[n - 1] += add;
            acc += add;
            flush();
            sleepUs(us - add);
        }
    }

    /** Wysyła zebraną paczkę i czeka, aż się "wybrzmi". */
    void flush() {
        if (n == 0 || failed) {
            n = 0;
            acc = 0;
            return;
        }
        if (n % 2 == 1) buf[n++] = s.minPulse;
        int[] pat = new int[n];
        double t = 0;
        long prev = 0, sum = 0;
        for (int i = 0; i < n; i++) {
            t += Math.max(buf[i], s.minPulse);
            long r = Math.round(t);
            int v = (int) Math.max(1, r - prev);
            pat[i] = v;
            prev = r;
            sum += v;
        }
        n = 0;
        acc = 0;
        if (gen.get() != my) return;
        long t0 = System.nanoTime();
        try {
            em.transmit(carrier, pat);
        } catch (RuntimeException e) {
            failed = true;
            l.error("Błąd transmit(): " + e.getMessage()
                    + "\nSpróbuj zmniejszyć maks. długość transmisji / liczbę wpisów lub zmienić nośną.");
            return;
        }
        sentUs += sum;
        calls++;
        // Część telefonów wraca z transmit() zanim skończy nadawać – dociągamy czas.
        long elapsedUs = (System.nanoTime() - t0) / 1000;
        if (realtime && elapsedUs < sum) sleepUs(sum - elapsedUs);
    }

    private void sleepUs(double us) {
        if (!realtime) {
            if (skip != null && alive()) skip.silence(us);
            return;
        }
        long end = System.nanoTime() + (long) (us * 1000);
        while (alive()) {
            long left = (end - System.nanoTime()) / 1000;
            if (left <= 0) return;
            long chunk = Math.min(left, 20_000);
            try {
                Thread.sleep(chunk / 1000, (int) (chunk % 1000) * 1000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return;
            }
        }
    }

    // =================================================================
    // Dźwięki
    // =================================================================

    private static final class Act {
        int type;
        double freq, prevFreq;
        double start, len;
        Timbre tb;
        double np;       // tryb miks: czas następnego impulsu
    }

    static double drumLen(int type) {
        switch (type) {
            case Melody.KICK: return 150_000;
            case Melody.TOM: return 180_000;
            case Melody.SNARE: return 130_000;
            case Melody.HAT: return 35_000;
            case Melody.OPEN_HAT: return 220_000;
            case Melody.CRASH: return 700_000;
            case Melody.CLAP: return 110_000;
            default: return 0;
        }
    }

    private static double clamp(double v, double a, double b) {
        return v < a ? a : Math.min(v, b);
    }

    private double rnd(double a, double b) {
        return a + rnd.nextDouble() * (b - a);
    }

    private static double duty(Timbre tb, double tn, double len) {
        double d;
        if (tb.lfoHz > 0) {
            d = tb.d0 + (tb.d1 - tb.d0) * (0.5 - 0.5 * Math.cos(2 * Math.PI * tb.lfoHz * tn / 1e6));
        } else {
            d = tb.d0 + (tb.d1 - tb.d0) * Math.min(1, tn / len);
        }
        return clamp(d, 0.02, 0.98);
    }

    private static double freq(Act a, double tn) {
        double f = a.freq;
        Timbre tb = a.tb;
        double glide = tb.glideMs * 1000;
        if (glide > 0 && a.prevFreq > 0 && tn < glide) {
            f = a.prevFreq * Math.pow(f / a.prevFreq, tn / glide);
        }
        double vd = tb.vibDelayMs * 1000;
        if (tb.vibCents > 0 && tn > vd) {
            f *= Math.pow(2, tb.vibCents / 1200.0 * Math.sin(2 * Math.PI * tb.vibHz * (tn - vd) / 1e6));
        }
        return f;
    }

    private static double sweepFreq(int type, double tn, double len) {
        double f0 = type == Melody.KICK ? 180 : 260, f1 = type == Melody.KICK ? 45 : 120;
        return f0 * Math.pow(f1 / f0, Math.min(1, tn / len));
    }

    /** Szum: długość impulsu i przerwy. */
    private void noise(int type, double tn, double len, double[] out) {
        double x = Math.min(1, tn / len);
        switch (type) {
            case Melody.HAT:
                out[0] = rnd(200, 300);
                out[1] = rnd(250, 550);
                break;
            case Melody.OPEN_HAT:
                out[0] = rnd(200, 320);
                out[1] = rnd(250, 550 + 1500 * x);
                break;
            case Melody.CLAP: {
                double ms = tn / 1000;
                boolean burst = ms < 8 || (ms > 12 && ms < 20) || (ms > 24 && ms < 32) || ms > 36;
                out[0] = rnd(250, 420);
                out[1] = burst ? rnd(260, 500 + 2500 * x) : rnd(2000, 3000);
                break;
            }
            case Melody.CRASH:
                out[0] = rnd(250, 400);
                out[1] = rnd(260, 400 + 3500 * x);
                break;
            default: // werbel
                out[0] = rnd(260, 450);
                out[1] = rnd(260, 400 + 2500 * x);
        }
    }

    private final double[] tmp = new double[2];

    /** Jeden okres dźwięku (tryb mono / arpeggio): out = {wł, wył}. */
    private void cycle(Act a, double tn, double[] out) {
        switch (a.type) {
            case Melody.TONE: {
                double per = 1e6 / freq(a, tn);
                double d = duty(a.tb, tn, a.len);
                out[0] = per * d;
                out[1] = per - out[0];
                return;
            }
            case Melody.KICK:
            case Melody.TOM: {
                double per = 1e6 / sweepFreq(a.type, tn, a.len);
                out[0] = per * 0.5;
                out[1] = per * 0.5;
                return;
            }
            default:
                noise(a.type, tn, a.len, out);
        }
    }

    /** Tryb miks: szerokość impulsu w chwili tn. */
    private double pulseWidth(Act a, double tn) {
        if (a.type == Melody.TONE) return s.mixPulseUs * clamp(2 * duty(a.tb, tn, a.len), 0.3, 2.0);
        if (a.type == Melody.KICK || a.type == Melody.TOM) return s.mixPulseUs * 1.5;
        noise(a.type, tn, a.len, tmp);
        return tmp[0];
    }

    /** Tryb miks: odstęp do następnego impulsu. */
    private double period(Act a, double tn) {
        if (a.type == Melody.TONE) return 1e6 / freq(a, tn);
        if (a.type == Melody.KICK || a.type == Melody.TOM) return 1e6 / sweepFreq(a.type, tn, a.len);
        noise(a.type, tn, a.len, tmp);
        return tmp[0] + tmp[1];
    }

    // =================================================================
    // Utwór
    // =================================================================

    boolean playSong(Melody.Song song) {
        List<List<Melody.Event>> voices = song.voices;
        int bpm = song.bpm > 0 ? song.bpm : s.bpm;
        boolean mix = song.mix >= 0 ? song.mix == 1 : s.mix;
        double quarter = 60e6 / bpm;
        int V = voices.size();

        double[][] start = new double[V][];
        double total = 0;
        for (int v = 0; v < V; v++) {
            List<Melody.Event> ev = voices.get(v);
            start[v] = new double[ev.size() + 1];
            double t = 0;
            for (int i = 0; i < ev.size(); i++) {
                start[v][i] = t;
                t += ev.get(i).beats * quarter;
            }
            start[v][ev.size()] = t;
            total = Math.max(total, t);
        }

        int[] idx = new int[V];
        Act[][] acts = new Act[V][];
        List<Act> list = new ArrayList<>();
        double mixGap = s.mixPulseUs * 0.8;
        int shown = -1;
        double t = 0;

        while (t < total) {
            if (!alive()) return false;
            // przesuń wskaźniki głosów
            for (int v = 0; v < V; v++) {
                List<Melody.Event> ev = voices.get(v);
                while (idx[v] < ev.size() && start[v][idx[v] + 1] <= t) {
                    idx[v]++;
                    acts[v] = null;
                }
                if (idx[v] < ev.size() && acts[v] == null) {
                    acts[v] = buildActs(ev, idx[v], start[v][idx[v]], start[v][idx[v] + 1] - start[v][idx[v]]);
                }
            }
            if (V > 0 && idx[0] != shown && idx[0] < voices.get(0).size()) {
                shown = idx[0];
                l.status(String.format(Locale.US, "%d:%04.1f s  %s", shown + 1, t / 1e6,
                        voices.get(0).get(shown).label));
            }
            // aktywne dźwięki i najbliższa granica
            list.clear();
            double nb = total;
            for (int v = 0; v < V; v++) {
                if (acts[v] == null) continue;
                double evEnd = start[v][idx[v] + 1];
                nb = Math.min(nb, evEnd);
                for (Act a : acts[v]) {
                    double endS = a.start + a.len;
                    if (t < endS) {
                        list.add(a);
                        nb = Math.min(nb, endS);
                    }
                }
            }
            if (list.isEmpty()) {
                off(nb - t);
                t = nb;
                continue;
            }
            if (!mix) {
                Act a = list.size() == 1 ? list.get(0)
                        : list.get((int) (t / s.arpUs) % list.size());
                cycle(a, t - a.start, tmp);
                double on = tmp[0], off = tmp[1];
                on(on);
                off(off);
                t += on + off;
            } else {
                double sMin = Double.MAX_VALUE;
                for (Act a : list) {
                    if (a.np < t) a.np = t;
                    sMin = Math.min(sMin, a.np);
                }
                if (sMin >= nb) {
                    off(nb - t);
                    t = nb;
                    continue;
                }
                if (sMin > t) {
                    off(sMin - t);
                    t = sMin;
                }
                double e = t;
                double cap = t + 4 * s.mixPulseUs;
                for (Act a : list) {
                    int guard = 0;
                    while (a.np <= e + mixGap && guard++ < 8) {
                        double tn = a.np - a.start;
                        e = Math.max(e, Math.min(a.np + pulseWidth(a, tn), cap));
                        a.np += Math.max(period(a, tn), 50);
                    }
                }
                if (e <= t) e = t + s.minPulse;
                on(e - t);
                t = e;
            }
        }
        flush();
        return alive();
    }

    private Act[] buildActs(List<Melody.Event> evs, int i, double start, double dur) {
        Melody.Event ev = evs.get(i);
        Melody.Event prev = i > 0 ? evs.get(i - 1) : null;
        Act[] out = new Act[ev.sounds.length];
        for (int k = 0; k < out.length; k++) {
            Melody.Sound snd = ev.sounds[k];
            Act a = new Act();
            a.type = snd.type;
            a.freq = snd.freq;
            a.tb = ev.timbre != null ? ev.timbre : s.timbre;
            a.start = start;
            a.np = start;
            if (snd.type == Melody.TONE) {
                a.len = Math.max(dur - s.gapUs, dur * 0.5);
                if (prev != null && k < prev.sounds.length && prev.sounds[k].type == Melody.TONE) {
                    a.prevFreq = prev.sounds[k].freq;
                }
            } else {
                a.len = Math.min(dur, drumLen(snd.type));
            }
            out[k] = a;
        }
        return out;
    }

    // =================================================================
    // Pojedyncze dźwięki
    // =================================================================

    /** Ciągły ton do anulowania (klawiatura, ton testowy). */
    void hold(FreqSource src, Timbre tb) {
        Act a = new Act();
        a.type = Melody.TONE;
        a.tb = tb;
        a.len = 1_000_000;
        double t = 0;
        while (alive()) {
            a.freq = src.get();
            cycle(a, t, tmp);
            on(tmp[0]);
            off(tmp[1]);
            t += tmp[0] + tmp[1];
        }
    }

    /** Ton o zadanej długości (bez flush). */
    boolean toneFor(double f, double us, Timbre tb) {
        Act a = new Act();
        a.type = Melody.TONE;
        a.freq = f;
        a.tb = tb;
        a.len = us;
        double t = 0;
        while (t < us) {
            if (!alive()) return false;
            cycle(a, t, tmp);
            on(tmp[0]);
            off(tmp[1]);
            t += tmp[0] + tmp[1];
        }
        return true;
    }

    /** Jedno uderzenie perkusji. */
    void drum(int type) {
        Act a = new Act();
        a.type = type;
        a.len = drumLen(type);
        double t = 0;
        while (t < a.len && alive()) {
            cycle(a, t, tmp);
            on(tmp[0]);
            off(tmp[1]);
            t += tmp[0] + tmp[1];
        }
        flush();
    }

    // =================================================================
    // Strumień audio (bytebeat) -> 1 bit
    // =================================================================

    interface SampleSource {
        double sample(long t);
    }

    /**
     * Liczy próbki w osobnym wątku (z wyprzedzeniem), koduje je do 1 bitu i nadaje.
     *
     * @param lengthSamples długość utworu (do pętli i wyświetlania czasu)
     */
    boolean playStream(final SampleSource src, final int sampleRate, final long lengthSamples,
                       final long startSample, final boolean loop,
                       final int mode, final double minRunUs, final double gain) {
        final ArrayBlockingQueue<double[]> q = new ArrayBlockingQueue<>(80);
        final double[] END = new double[0];
        final int block = sampleRate / 20;                        // 50 ms na blok
        Thread producer = new Thread(() -> {
            OneBit enc = new OneBit(mode, minRunUs, gain, sampleRate);
            double dt = enc.dtUs();
            long t = startSample;
            boolean cur = false;
            double dur = 0;
            try {
                while (alive()) {
                    if (!loop && t >= lengthSamples) break;
                    double[] runs = new double[block + 1];
                    int k = 0;
                    for (int i = 0; i < block; i++, t++) {
                        boolean b = enc.step(src.sample(t));
                        if (b == cur) {
                            dur += dt;
                        } else {
                            runs[k++] = cur ? dur : -dur;     // + = wł., - = wył.
                            cur = b;
                            dur = dt;
                        }
                    }
                    double[] out = new double[k + 1];
                    System.arraycopy(runs, 0, out, 0, k);
                    out[k] = Double.NaN;                        // znacznik: koniec bloku
                    while (alive() && !q.offer(out, 50, TimeUnit.MILLISECONDS)) { /* czekaj */ }
                }
                if (dur > 0) q.offer(new double[]{cur ? dur : -dur}, 200, TimeUnit.MILLISECONDS);
                q.offer(END, 200, TimeUnit.MILLISECONDS);
            } catch (InterruptedException ignored) {
            }
        }, "bytebeat");
        producer.setPriority(Thread.MAX_PRIORITY);
        producer.start();

        // chwila na zapas (~0,5 s)
        long waitEnd = System.nanoTime() + 3_000_000_000L;
        while (alive() && q.size() < 10 && producer.isAlive() && System.nanoTime() < waitEnd) {
            sleepMs(10);
        }

        double audioUs = startSample * 1e6 / sampleRate;
        double total = lengthSamples * 1e6 / sampleRate;
        long shownSec = -1;
        try {
            while (alive()) {
                double[] runs = q.poll(100, TimeUnit.MILLISECONDS);
                if (runs == null) continue;
                if (runs == END) break;
                for (double r : runs) {
                    if (Double.isNaN(r)) {
                        long sec = (long) ((audioUs % total) / 1e6);
                        if (sec != shownSec) {
                            shownSec = sec;
                            l.status(String.format(Locale.US, "%d:%02d / %d:%02d   bufor %d ms",
                                    sec / 60, sec % 60, (long) (total / 6e7), (long) (total / 1e6) % 60, q.size() * 50));
                        }
                        continue;
                    }
                    if (r > 0) on(r);
                    else off(-r);
                    audioUs += Math.abs(r);
                }
            }
        } catch (InterruptedException ignored) {
        }
        flush();
        producer.interrupt();
        return alive();
    }

    private void sleepMs(long ms) {
        if (!realtime) return;
        try {
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    // =================================================================
    // Wzorce testowe
    // =================================================================

    static final String[] PATTERNS = {
            "Czysta nośna (ciągła)",
            "Pojedynczy impuls co B ms",
            "Prostokąt: A µs wł. / B µs wył.",
            "Rosnąca paczka (szuka min. długości)",
            "Rosnąca przerwa (szuka min. przerwy)",
            "PWM: wypełnienie 5→95 % przy A Hz",
            "Sweep nośnej 30–60 kHz (ton A Hz)",
    };
    static final String[] PATTERN_A = {"—", "Impuls [µs]", "Wł. [µs]", "Maks. okresów nośnej", "Paczka [µs]", "Częstotliwość [Hz]", "Ton [Hz]"};
    static final String[] PATTERN_B = {"—", "Co ile [ms]", "Wył. [µs]", "Przerwa [µs]", "Maks. okresów nośnej", "Czas sweepu [ms]", "Na nośną [ms]"};
    static final int[] PATTERN_A_DEF = {0, 600, 600, 40, 600, 500, 1000};
    static final int[] PATTERN_B_DEF = {0, 100, 600, 1200, 40, 5000, 400};

    /** @param ranges obsługiwane zakresy nośnej {min,max} albo null */
    void pattern(int type, double A, double B, int[][] ranges) {
        double per = 1e6 / carrier;
        switch (type) {
            case 0:
                l.status("czysta nośna " + carrier + " Hz");
                while (alive()) {
                    on(Math.min(50_000, s.maxChunkUs * 0.9));
                    off(Math.max(s.minPulse, 300));
                }
                break;
            case 1:
                l.status(String.format(Locale.US, "impuls %.0f µs co %.0f ms", A, B));
                while (alive()) {
                    on(A);
                    off(Math.max(s.minPulse, B * 1000 - A));
                    flush();
                }
                break;
            case 2:
                l.status(String.format(Locale.US, "prostokąt %.0f / %.0f µs  (%.1f Hz)", A, B, 1e6 / (A + B)));
                while (alive()) {
                    on(A);
                    off(B);
                }
                break;
            case 3:
                for (int k = 1; k <= Math.max(1, (int) A) && alive(); k++) {
                    double len = k * per;
                    l.status(String.format(Locale.US, "paczka: %d okr. nośnej = %.0f µs, przerwa %.0f µs", k, len, B));
                    for (double t = 0; t < 300_000 && alive(); t += len + B) {
                        on(len);
                        off(B);
                    }
                }
                break;
            case 4:
                for (int k = 1; k <= Math.max(1, (int) B) && alive(); k++) {
                    double gap = k * per;
                    l.status(String.format(Locale.US, "przerwa: %d okr. nośnej = %.0f µs, paczka %.0f µs", k, gap, A));
                    for (double t = 0; t < 300_000 && alive(); t += A + gap) {
                        on(A);
                        off(gap);
                    }
                }
                break;
            case 5: {
                double T = 1e6 / Math.max(1, A), dur = Math.max(100, B) * 1000;
                int lastPct = -1;
                for (double t = 0; t < dur && alive(); t += T) {
                    double d = 0.05 + 0.9 * t / dur;
                    int pct = (int) (d * 100);
                    if (pct != lastPct && pct % 5 == 0) {
                        lastPct = pct;
                        l.status(String.format(Locale.US, "PWM %.0f Hz, wypełnienie %d %%", A, pct));
                    }
                    on(T * d);
                    off(T * (1 - d));
                }
                break;
            }
            case 6: {
                Timbre pure = new Timbre();
                for (int c = 30_000; c <= 60_000 && alive(); c += 1000) {
                    if (!supported(c, ranges)) {
                        l.status("nośna " + c + " Hz – nieobsługiwana, pomijam");
                        continue;
                    }
                    flush();
                    carrier = c;
                    l.status("nośna " + c + " Hz");
                    toneFor(A, B * 1000, pure);
                    flush();
                    off(100_000);
                }
                carrier = s.carrier;
                break;
            }
        }
        flush();
        if (alive()) l.status("koniec wzorca");
    }

    private static boolean supported(int c, int[][] ranges) {
        if (ranges == null || ranges.length == 0) return true;
        for (int[] r : ranges) if (c >= r[0] && c <= r[1]) return true;
        return false;
    }
}
