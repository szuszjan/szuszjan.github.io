package io.github.szuszjan.irmusic;

/**
 * Port 1:1 bytebeatu "Techno, 135 BPM, D minor, 3:48" (oryginał w JS, tryb Bytebeat 44100 Hz).
 * {@link #sample(long)} zwraca próbkę w zakresie -1..1 (oryginał: 128 + 127·wynik).
 */
final class Bytebeat {

    static final String NAME = "Techno 135 BPM, d-moll, 3:48";
    static final int R = 44100;
    private static final double T = 6.2832, BPM = 135, beat = 60 / BPM, bar = beat * 4, s16 = beat / 4, LEN = 128 * bar;
    static final double LENGTH_S = LEN;

    private static final String CHs = ">AEH>AEH>AEH<?CF", ACA = "0.0<.03.0.5.0:7.", ACB = "0.0<0.75.03.0<?.",
            STs = "..1...1...1..1..", PRs = "..1..2....1..2..";

    private Bytebeat() {}

    private static int sec(int b) {
        return b < 16 ? 0 : b < 32 ? 1 : b < 48 ? 2 : b < 64 ? 3 : b < 96 ? 4 : b < 112 ? 5 : 6;
    }

    private static double M(double n) {
        return 440 * Math.pow(2, (n - 69) / 12);
    }

    private static double H(int i) {
        i = i ^ 61 ^ (i >>> 16);
        i = i * 9;
        i ^= i >>> 4;
        i = i * 0x27d4eb2d;
        i ^= i >>> 15;
        return (i & 0xffffffffL) / 2147483648.0 - 1;
    }

    /** ToInt32 z JS dla wartości z zakresu. */
    private static int i32(double v) {
        return (int) (long) v;
    }

    private static double w(double f, double v, double o) {
        return 2 * ((f * v + o) % 1) - 1;
    }

    private static double Q(double f, double v, double k) {
        return k * .8 * (w(f * .988, v, 0) + w(f * .994, v, .37) + w(f, v, .74) + w(f * 1.006, v, .11) + w(f * 1.012, v, .48))
                + (1 - k) * 1.2 * (Math.sin(T * f * .994 * v) + Math.sin(T * f * 1.006 * v));
    }

    private static double clamp01(double v) {
        return Math.max(0, Math.min(1, v));
    }

    private static double acid(double v) {
        if (v < 0) return 0;
        int b = i32(v / bar);
        double tb = v - b * bar;
        int st = i32(tb / s16);
        double ts = tb - st * s16;
        int sc = sec(b);
        if (!(sc == 2 || sc == 4 || sc == 5 || (sc == 3 && b >= 56) || (sc == 6 && b < 108)) || (b == 63 && tb > 3.5 * beat))
            return 0;
        int c = ((b & 1) != 0 ? ACB : ACA).charAt(st) - 48;
        if (c < 0) return 0;
        double f = M(50 - 2 * ((b & 3) == 3 ? 1 : 0) + c), e = Math.exp(-ts * 20),
                cut = sc == 3 ? .1 + .9 * Math.min(1, (b - 56 + tb / bar) / 8) : sc == 5 ? .6 : 1,
                br = Math.min(1, cut * (.2 + .8 * e) * 1.4),
                g = Math.min(1, ts / .002) * clamp01((s16 * .7 - ts) / .01),
                pp = sc == 3 ? 1 : 1 - .88 * Math.exp(-(tb % beat) * 10);
        return ((w(f, v, 0) * br + Math.sin(T * f * v) * (1 - br) * .8)
                + Math.sin(T * f * (3 * ts + 8 * (1 - Math.exp(-ts * 25)) / 25)) * .35 * Math.exp(-ts * 25))
                * g * (st % 3 == 0 ? 1 : .65) * pp * .22;
    }

    private static double stab(double v) {
        if (v < 0) return 0;
        int b = i32(v / bar);
        double tb = v - b * bar;
        int st = i32(tb / s16);
        double ts = tb - st * s16;
        int sc = sec(b);
        if (!((sc == 2 && b >= 40) || sc == 3 || sc == 4) || STs.charAt(st) != '1' || (b == 63 && tb > 3.5 * beat))
            return 0;
        int ci = b & 3;
        double e = Math.exp(-ts * 20), br = .25 + .75 * e, s = 0;
        for (int j = 0; j < 4; j++) {
            double f = M(CHs.charAt(ci * 4 + j));
            s += (w(f, v, 0) + w(f * 1.007, v, .3)) * br * .5 + Math.sin(T * f * v) * (1 - br) * .7;
        }
        return s * Math.min(1, ts / .002) * clamp01((s16 - ts) / .012) * e * .09
                * (sc == 3 ? 1 : 1 - .9 * Math.exp(-(tb % beat) * 10));
    }

    /** @param t numer próbki (44100 Hz), może przekraczać długość – utwór się zapętla */
    static double sample(long t) {
        double tt = t % (long) Math.round(LEN * R), u = tt / R;
        int ti = (int) tt;
        int b = i32(u / bar);
        double tb = u - b * bar;
        int bt = i32(tb / beat);
        double tq = tb - bt * beat;
        int st = i32(tb / s16);
        double ts = tb - st * s16;
        int sub = st & 3, sc = sec(b), ci = b & 3;
        double n0 = H(ti), hp = n0 - H(ti - 1), cq = (n0 - H(ti - 2)) * .5;
        double pp = 1 - .88 * Math.exp(-tq * 10);
        double x = 0;
        // stopa
        if (sc != 3 && !(sc == 6 && b >= 124)) {
            double ph = 46 * tq + 4.62 * (1 - Math.exp(-tq / .03));
            x += Math.tanh(2.2 * Math.sin(T * ph)) * Math.exp(-tq * 6.5) * (1 - tq / beat) + H(ti * 3 + 7) * Math.exp(-tq * 1500) * .25;
        }
        // rumble
        if (b >= 8 && sc != 3 && !(sc == 6 && b >= 120))
            x += Math.tanh(2.5 * Math.sin(T * M(26 - 2 * (ci == 3 ? 1 : 0)) * u)) * (1 - Math.exp(-tq * 14)) * .2;
        // hi-haty
        if (b >= 4 && sc != 3 && !(sc == 6 && b >= 124) && sub >= 2) x += hp * .15 * Math.exp(-((sub - 2) * s16 + ts) * 16);
        if (b >= 8 && (sc != 3 || b >= 56) && !(sc == 6 && b >= 124) && sub == 1) x += hp * .06 * Math.exp(-ts * 100) * 3.3;
        if (sc == 4 && (sub == 0 || sub == 3)) x += cq * .12 * Math.exp(-ts * 60);
        // klaśnięcie na 2 i 4
        if ((bt & 1) != 0 && b >= 24 && sc != 3 && !(sc == 6 && b >= 116)) {
            double e = (tq > .033 ? Math.exp(-(tq - .033) * 20) * .6 : 0) + Math.exp(-tq * 250)
                    + (tq >= .011 ? Math.exp(-(tq - .011) * 250) : 0) + (tq >= .022 ? Math.exp(-(tq - .022) * 250) : 0);
            x += cq * e * 1.1;
        }
        // tomy
        if (((sc == 1 && b >= 24) || sc == 2 || sc == 4 || sc == 5 || (sc == 6 && b < 116)) && PRs.charAt(st) != '.') {
            double fT = PRs.charAt(st) == '1' ? 140 : 210;
            x += Math.sin(T * fT * (ts + .018 * (1 - Math.exp(-ts / .03)))) * Math.exp(-ts * 22) * .3;
        }
        // bas na offbeat
        if (sub >= 2 && b >= 16 && sc != 3 && !(sc == 6 && b >= 120)) {
            double to = (sub - 2) * s16 + ts, f = M(38 - 2 * (ci == 3 ? 1 : 0)),
                    e = Math.min(1, to / .003) * clamp01((beat / 2 - .02 - to) / .02);
            x += (w(f, u, 0) * (.2 + .5 * Math.exp(-to * 18)) + Math.sin(T * f * u) * .9) * e * pp * .5;
        }
        // pad w breakdownie
        if (sc == 3) {
            double g = Math.min(1, tb / .4) * Math.min(1, (bar - tb) / .05), k = Math.min(1, .1 + .9 * (b - 48 + tb / bar) / 16), s = 0;
            for (int j = 0; j < 4; j++) s += Q(M(CHs.charAt(ci * 4 + j)), u, k);
            x += s * g * .03;
        }
        // riser
        if (b >= 56 && b < 64) {
            double t2 = u - 56 * bar, r = t2 / (8 * bar), k = Math.log(20) / (8 * bar);
            x += H(i32(Math.floor(ti / (40 * (1 - r) + 2)))) * r * r * .3
                    + (2 * ((200 / k * (Math.exp(k * t2) - 1)) % 1) - 1) * r * r * .06;
        }
        // werbel – werbelek przed dropem
        if (b == 62 || b == 63) {
            double pos = (u - 62 * bar) / (2 * bar), xs = tb % (b == 62 ? beat / 2 : s16);
            x += (cq * Math.exp(-xs * 30) + Math.sin(T * 190 * xs) * Math.exp(-xs * 25) * .25) * (.3 + .7 * pos) * 1.3;
        }
        // crashe na 32, 64, 96, 112
        if (b >= 32) {
            int cb = b >= 112 ? 112 : (b >> 5) << 5;
            double xc = u - cb * bar;
            if (xc < 4) x += hp * Math.exp(-xc * 1.7) * .4;
        }
        // cisza przed dropem
        if (b == 63 && tb > 3.5 * beat) x = 0;
        // acid i stabsy z echem
        x += acid(u) + .3 * acid(u - beat * .75) + .12 * acid(u - beat * 1.5)
                + stab(u) + .55 * stab(u - beat * .75) + .3 * stab(u - beat * 1.5) + .16 * stab(u - beat * 2.25);
        double fd = clamp01((LEN - u) / 10);
        return Math.tanh(x * 1.1) * .92 * fd;
    }
}
