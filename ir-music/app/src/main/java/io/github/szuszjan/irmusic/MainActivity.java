package io.github.szuszjan.irmusic;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.SharedPreferences;
import android.hardware.ConsumerIrManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.SeekBar;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;

public class MainActivity extends Activity {

    /** Parametry nadawania odczytane z UI w chwili startu. */
    private static final class Params {
        int carrier;
        double duty;
        long maxChunkUs;
        int maxEntries;
        long gapUs;
        int bpm;
    }

    private interface FreqSource {
        double get();
    }

    private static final String[] KEY_NAMES = {"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"};

    private ConsumerIrManager ir;
    private final ExecutorService exec = Executors.newSingleThreadExecutor();
    /** Licznik "generacji" – zmiana anuluje bieżące odtwarzanie. */
    private final AtomicInteger gen = new AtomicInteger();
    private final Handler ui = new Handler(Looper.getMainLooper());

    private EditText carrierEdit, notesEdit, bpmEdit, maxChunkEdit, maxEntriesEdit, gapEdit;
    private SeekBar dutyBar, toneBar;
    private TextView statusText, dutyLabel, toneLabel, nowPlaying, octLabel;
    private Spinner songSpinner;
    private CheckBox loopBox;
    private Button toneBtn;

    private volatile boolean loop;
    private volatile double toneFreq = 440;
    private int toneGen = -1;
    private int octave = 4;
    private boolean ignoreSpinner = true;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        ir = (ConsumerIrManager) getSystemService(CONSUMER_IR_SERVICE);

        statusText = findViewById(R.id.status);
        carrierEdit = findViewById(R.id.carrier);
        dutyBar = findViewById(R.id.duty);
        dutyLabel = findViewById(R.id.dutyLabel);
        songSpinner = findViewById(R.id.songs);
        notesEdit = findViewById(R.id.notes);
        bpmEdit = findViewById(R.id.bpm);
        loopBox = findViewById(R.id.loop);
        nowPlaying = findViewById(R.id.nowPlaying);
        octLabel = findViewById(R.id.octLabel);
        toneLabel = findViewById(R.id.toneLabel);
        toneBar = findViewById(R.id.tone);
        toneBtn = findViewById(R.id.toneBtn);
        maxChunkEdit = findViewById(R.id.maxChunk);
        maxEntriesEdit = findViewById(R.id.maxEntries);
        gapEdit = findViewById(R.id.gap);

        loadPrefs();
        showStatus();

        // --- wypełnienie ---
        dutyBar.setOnSeekBarChangeListener(new SimpleSeek() {
            @Override
            public void onProgressChanged(SeekBar s, int p, boolean u) {
                dutyLabel.setText("Wypełnienie sygnału audio: " + (p + 10) + " %");
            }
        });
        dutyLabel.setText("Wypełnienie sygnału audio: " + (dutyBar.getProgress() + 10) + " %");

        // --- melodie ---
        ArrayAdapter<String> ad = new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_item, Songs.NAMES);
        ad.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        songSpinner.setAdapter(ad);
        songSpinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int pos, long id) {
                if (ignoreSpinner) {
                    ignoreSpinner = false;
                    return;
                }
                if (pos > 0) {
                    notesEdit.setText(Songs.NOTES[pos]);
                    bpmEdit.setText(String.valueOf(Songs.BPM[pos]));
                }
            }

            @Override
            public void onNothingSelected(AdapterView<?> parent) {}
        });

        loopBox.setOnCheckedChangeListener((b, checked) -> loop = checked);
        findViewById(R.id.play).setOnClickListener(v -> playMelody());
        findViewById(R.id.stop).setOnClickListener(v -> stopAll());

        // --- klawiatura ---
        buildKeyboard();
        findViewById(R.id.octDown).setOnClickListener(v -> setOctave(octave - 1));
        findViewById(R.id.octUp).setOnClickListener(v -> setOctave(octave + 1));

        // --- ton testowy ---
        toneBar.setOnSeekBarChangeListener(new SimpleSeek() {
            @Override
            public void onProgressChanged(SeekBar s, int p, boolean u) {
                updateToneFreq();
            }
        });
        updateToneFreq();
        toneBtn.setOnClickListener(v -> toggleTone());
        findViewById(R.id.sweepBtn).setOnClickListener(v -> sweep());
    }

    @Override
    protected void onPause() {
        super.onPause();
        savePrefs();
    }

    @Override
    protected void onStop() {
        super.onStop();
        stopAll();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        gen.incrementAndGet();
        exec.shutdownNow();
    }

    // ===================================================================
    // UI
    // ===================================================================

    private void showStatus() {
        StringBuilder sb = new StringBuilder();
        if (ir == null || !ir.hasIrEmitter()) {
            sb.append("⚠ Ten telefon nie ma diody IR (ConsumerIrManager).");
        } else {
            sb.append("✔ Dioda IR wykryta. Obsługiwane nośne: ");
            ConsumerIrManager.CarrierFrequencyRange[] rs = null;
            try {
                rs = ir.getCarrierFrequencies();
            } catch (Exception ignored) {
            }
            if (rs == null || rs.length == 0) {
                sb.append("brak danych");
            } else {
                for (int i = 0; i < rs.length; i++) {
                    if (i > 0) sb.append(", ");
                    if (rs[i].getMinFrequency() == rs[i].getMaxFrequency()) {
                        sb.append(rs[i].getMinFrequency());
                    } else {
                        sb.append(rs[i].getMinFrequency()).append("–").append(rs[i].getMaxFrequency());
                    }
                }
                sb.append(" Hz");
            }
        }
        statusText.setText(sb);
    }

    private void buildKeyboard() {
        LinearLayout sharps = findViewById(R.id.keysSharp);
        LinearLayout whites = findViewById(R.id.keysWhite);
        // Białe: C D E F G A B C ; czarne nad nimi (puste miejsca jako odstępy)
        int[] whiteSemis = {0, 2, 4, 5, 7, 9, 11, 12};
        int[] sharpSemis = {1, 3, -1, 6, 8, 10, -1, -1};
        for (int i = 0; i < whiteSemis.length; i++) {
            whites.addView(makeKey(whiteSemis[i], false));
            if (sharpSemis[i] >= 0) {
                sharps.addView(makeKey(sharpSemis[i], true));
            } else {
                View spacer = new View(this);
                sharps.addView(spacer, new LinearLayout.LayoutParams(0, 1, 1f));
            }
        }
        setOctave(octave);
    }

    @SuppressLint("ClickableViewAccessibility")
    private Button makeKey(final int semi, boolean sharp) {
        Button b = new Button(this);
        b.setTag(semi);
        b.setAllCaps(false);
        b.setTextSize(12);
        b.setPadding(0, 0, 0, 0);
        b.setLayoutParams(new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        if (sharp) b.setAlpha(0.75f);
        final int[] myGen = {-1};
        b.setOnTouchListener((v, ev) -> {
            switch (ev.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    v.setPressed(true);
                    final double f = Melody.noteFreq(12 * (octave + 1) + semi);
                    nowPlaying.setText(String.format(Locale.US, "%s  %.1f Hz", keyName(semi), f));
                    myGen[0] = startContinuous(() -> f);
                    return true;
                case MotionEvent.ACTION_UP:
                case MotionEvent.ACTION_CANCEL:
                    v.setPressed(false);
                    gen.compareAndSet(myGen[0], myGen[0] + 1);
                    return true;
            }
            return false;
        });
        return b;
    }

    private String keyName(int semi) {
        return KEY_NAMES[semi % 12] + (octave + semi / 12);
    }

    private void setOctave(int o) {
        octave = Math.max(1, Math.min(7, o));
        octLabel.setText(String.valueOf(octave));
        relabel(findViewById(R.id.keysWhite));
        relabel(findViewById(R.id.keysSharp));
    }

    private void relabel(LinearLayout row) {
        for (int i = 0; i < row.getChildCount(); i++) {
            View v = row.getChildAt(i);
            if (v instanceof Button) ((Button) v).setText(keyName((Integer) v.getTag()));
        }
    }

    private void updateToneFreq() {
        // skala logarytmiczna 50 Hz … 3000 Hz
        toneFreq = 50.0 * Math.pow(60.0, toneBar.getProgress() / 1000.0);
        toneLabel.setText(String.format(Locale.US, "Częstotliwość: %.0f Hz", toneFreq));
    }

    private void setNow(final String s) {
        ui.post(() -> nowPlaying.setText(s));
    }

    private void toast(final String s) {
        ui.post(() -> Toast.makeText(this, s, Toast.LENGTH_LONG).show());
    }

    private static int intOf(EditText e, int def, int min, int max) {
        try {
            int v = Integer.parseInt(e.getText().toString().trim());
            return Math.max(min, Math.min(max, v));
        } catch (NumberFormatException ex) {
            return def;
        }
    }

    private Params readParams() {
        Params p = new Params();
        p.carrier = intOf(carrierEdit, 38000, 15000, 100000);
        p.duty = (dutyBar.getProgress() + 10) / 100.0;
        p.maxChunkUs = intOf(maxChunkEdit, 400, 20, 1900) * 1000L;
        p.maxEntries = intOf(maxEntriesEdit, 1000, 4, 100000);
        p.gapUs = intOf(gapEdit, 25, 0, 1000) * 1000L;
        p.bpm = intOf(bpmEdit, 120, 10, 600);
        return p;
    }

    private boolean checkIr() {
        if (ir == null || !ir.hasIrEmitter()) {
            Toast.makeText(this, "Brak diody IR w tym telefonie", Toast.LENGTH_SHORT).show();
            return false;
        }
        return true;
    }

    // ===================================================================
    // Akcje
    // ===================================================================

    private void stopAll() {
        gen.incrementAndGet();
        toneGen = -1;
        toneBtn.setText("Ton ciągły");
        nowPlaying.setText("");
    }

    private void playMelody() {
        if (!checkIr()) return;
        final List<Melody.Note> notes;
        try {
            notes = Melody.parse(notesEdit.getText().toString());
        } catch (IllegalArgumentException e) {
            Toast.makeText(this, "Błąd w nutach: " + e.getMessage(), Toast.LENGTH_LONG).show();
            return;
        }
        if (notes.isEmpty()) {
            Toast.makeText(this, "Wpisz jakieś nuty", Toast.LENGTH_SHORT).show();
            return;
        }
        stopAll();
        final Params p = readParams();
        final int my = gen.incrementAndGet();
        loop = loopBox.isChecked();
        exec.execute(() -> {
            long quarterUs = 60_000_000L / p.bpm;
            do {
                for (int i = 0; i < notes.size(); i++) {
                    if (gen.get() != my) return;
                    Melody.Note n = notes.get(i);
                    long durUs = Math.round(n.beats * quarterUs);
                    setNow((i + 1) + "/" + notes.size() + "  " + n.label);
                    if (n.isRest()) {
                        if (!silence(durUs, my)) return;
                    } else {
                        long toneUs = Math.max(durUs - p.gapUs, durUs / 2);
                        if (!tone(p, n.freq, toneUs, my)) return;
                        if (!silence(durUs - toneUs, my)) return;
                    }
                }
            } while (loop && gen.get() == my);
            if (gen.get() == my) setNow("koniec");
        });
    }

    private void toggleTone() {
        if (toneGen >= 0 && gen.get() == toneGen) {
            stopAll();
            return;
        }
        if (!checkIr()) return;
        stopAll();
        toneGen = startContinuous(() -> toneFreq);
        toneBtn.setText("Zatrzymaj ton");
        nowPlaying.setText("ton ciągły");
    }

    private void sweep() {
        if (!checkIr()) return;
        stopAll();
        final Params p = readParams();
        final int my = gen.incrementAndGet();
        exec.execute(() -> {
            final double f0 = 100, f1 = 2000;
            final int steps = 100;          // 100 × 50 ms = 5 s
            for (int i = 0; i <= steps; i++) {
                if (gen.get() != my) return;
                double f = f0 * Math.pow(f1 / f0, i / (double) steps);
                setNow(String.format(Locale.US, "sweep %.0f Hz", f));
                if (!tone(p, f, 50_000, my)) return;
            }
            if (gen.get() == my) setNow("koniec sweepu");
        });
    }

    /** Uruchamia nadawanie ciągłego tonu (krótkimi paczkami) aż do zmiany generacji. */
    private int startContinuous(final FreqSource src) {
        if (ir == null || !ir.hasIrEmitter()) return -1;
        final Params p = readParams();
        p.maxChunkUs = Math.min(p.maxChunkUs, 100_000); // szybka reakcja na puszczenie klawisza
        final int my = gen.incrementAndGet();
        exec.execute(() -> {
            while (gen.get() == my) {
                if (!tone(p, src.get(), p.maxChunkUs, my)) return;
            }
        });
        return my;
    }

    // ===================================================================
    // Nadawanie
    // ===================================================================

    /**
     * Nadaje prostokąt o częstotliwości {@code freq}: nośna IR włączona przez duty·T,
     * wyłączona przez (1−duty)·T. Długie dźwięki są dzielone na kilka wywołań transmit().
     *
     * @return false, jeśli anulowano lub wystąpił błąd
     */
    private boolean tone(Params p, double freq, long durUs, int my) {
        if (freq <= 0) return silence(durUs, my);
        final double period = 1e6 / freq;
        final int minPulse = (int) Math.ceil(1e6 / p.carrier); // min. jeden okres nośnej
        long totalCycles = Math.max(1, Math.round(durUs / period));
        int perChunk = (int) Math.max(1, Math.min(p.maxEntries / 2, p.maxChunkUs / period));

        long done = 0;
        while (done < totalCycles) {
            if (gen.get() != my) return false;
            int n = (int) Math.min(perChunk, totalCycles - done);
            int[] pat = new int[n * 2];
            long prev = 0, sum = 0;
            for (int k = 0; k < n; k++) {
                // krawędzie liczone od początku paczki – błędy zaokrągleń się nie kumulują
                long onEnd = Math.round(k * period + p.duty * period);
                long cycEnd = Math.round((k + 1) * period);
                int on = (int) Math.max(minPulse, onEnd - prev);
                int off = (int) Math.max(minPulse, cycEnd - onEnd);
                pat[2 * k] = on;
                pat[2 * k + 1] = off;
                sum += on + off;
                prev = cycEnd;
            }
            long t0 = System.nanoTime();
            try {
                ir.transmit(p.carrier, pat);
            } catch (Exception e) {
                toast("Błąd transmit(): " + e.getMessage()
                        + "\nSpróbuj zmniejszyć maks. długość transmisji / liczbę wpisów lub zmienić nośną.");
                gen.compareAndSet(my, my + 1);
                setNow("błąd");
                return false;
            }
            // Część telefonów wraca z transmit() zanim skończy nadawać – dociągamy czas.
            long elapsedUs = (System.nanoTime() - t0) / 1000;
            if (elapsedUs < sum) sleepUs(sum - elapsedUs);
            done += n;
        }
        return true;
    }

    private boolean silence(long us, int my) {
        long end = System.nanoTime() + us * 1000;
        while (true) {
            if (gen.get() != my) return false;
            long left = (end - System.nanoTime()) / 1000;
            if (left <= 0) return true;
            sleepUs(Math.min(left, 20_000));
        }
    }

    private static void sleepUs(long us) {
        if (us <= 0) return;
        try {
            Thread.sleep(us / 1000, (int) (us % 1000) * 1000);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    // ===================================================================
    // Ustawienia
    // ===================================================================

    private void loadPrefs() {
        SharedPreferences sp = getPreferences(MODE_PRIVATE);
        carrierEdit.setText(sp.getString("carrier", "38000"));
        dutyBar.setProgress(sp.getInt("duty", 40));
        notesEdit.setText(sp.getString("notes", Songs.NOTES[3]));
        bpmEdit.setText(sp.getString("bpm", "140"));
        maxChunkEdit.setText(sp.getString("maxChunk", "400"));
        maxEntriesEdit.setText(sp.getString("maxEntries", "1000"));
        gapEdit.setText(sp.getString("gap", "25"));
        toneBar.setProgress(sp.getInt("tone", 500));
        octave = sp.getInt("octave", 4);
    }

    private void savePrefs() {
        getPreferences(MODE_PRIVATE).edit()
                .putString("carrier", carrierEdit.getText().toString())
                .putInt("duty", dutyBar.getProgress())
                .putString("notes", notesEdit.getText().toString())
                .putString("bpm", bpmEdit.getText().toString())
                .putString("maxChunk", maxChunkEdit.getText().toString())
                .putString("maxEntries", maxEntriesEdit.getText().toString())
                .putString("gap", gapEdit.getText().toString())
                .putInt("tone", toneBar.getProgress())
                .putInt("octave", octave)
                .apply();
    }

    private abstract static class SimpleSeek implements SeekBar.OnSeekBarChangeListener {
        @Override
        public void onStartTrackingTouch(SeekBar s) {}

        @Override
        public void onStopTrackingTouch(SeekBar s) {}
    }
}
