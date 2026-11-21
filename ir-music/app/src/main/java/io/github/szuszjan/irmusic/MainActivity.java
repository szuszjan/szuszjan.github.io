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

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;

public class MainActivity extends Activity {

    private static final String[] KEY_NAMES = {"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"};

    private ConsumerIrManager ir;
    private final ExecutorService exec = Executors.newSingleThreadExecutor();
    /** Licznik "generacji" – zmiana anuluje bieżące nadawanie. */
    private final AtomicInteger gen = new AtomicInteger();
    private final Handler ui = new Handler(Looper.getMainLooper());

    private EditText carrierEdit, notesEdit, bpmEdit, maxChunkEdit, maxEntriesEdit, gapEdit, minPulseEdit, patAEdit, patBEdit;
    private SeekBar toneBar;
    private TextView statusText, toneLabel, nowPlaying, octLabel, patALabel, patBLabel;
    private Spinner songSpinner, presetSpinner, polySpinner, patternSpinner;
    private CheckBox loopBox;
    private Button toneBtn;

    private Slider dStart, dEnd, lfo, vibDepth, vibRate, vibDelay, glide, arpMs, mixPulse;
    private final List<Slider> sliders = new ArrayList<>();

    private volatile boolean loop;
    private volatile double toneFreq = 440;
    private int toneGen = -1;
    private int octave = 4;
    private boolean userSong, userPreset, userPattern;

    // =================================================================
    // Suwak z etykietą
    // =================================================================

    private final class Slider {
        final String key, fmt;
        final double min, step;
        final SeekBar bar;
        final TextView label;

        Slider(LinearLayout parent, String key, String fmt, double min, double max, double step, double def) {
            this.key = key;
            this.fmt = fmt;
            this.min = min;
            this.step = step;
            label = new TextView(MainActivity.this);
            label.setPadding(0, dp(6), 0, 0);
            bar = new SeekBar(MainActivity.this);
            bar.setMax((int) Math.round((max - min) / step));
            parent.addView(label);
            parent.addView(bar);
            bar.setOnSeekBarChangeListener(new SimpleSeek() {
                @Override
                public void onProgressChanged(SeekBar s, int p, boolean u) {
                    updateLabel();
                }
            });
            set(def);
            sliders.add(this);
        }

        double get() {
            return min + bar.getProgress() * step;
        }

        void set(double v) {
            bar.setProgress((int) Math.round((v - min) / step));
            updateLabel();
        }

        void updateLabel() {
            label.setText(String.format(Locale.US, fmt, get()));
        }
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    // =================================================================
    // Cykl życia
    // =================================================================

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        ir = (ConsumerIrManager) getSystemService(CONSUMER_IR_SERVICE);

        statusText = findViewById(R.id.status);
        carrierEdit = findViewById(R.id.carrier);
        songSpinner = findViewById(R.id.songs);
        notesEdit = findViewById(R.id.notes);
        bpmEdit = findViewById(R.id.bpm);
        loopBox = findViewById(R.id.loop);
        nowPlaying = findViewById(R.id.nowPlaying);
        presetSpinner = findViewById(R.id.preset);
        polySpinner = findViewById(R.id.polyMode);
        octLabel = findViewById(R.id.octLabel);
        toneLabel = findViewById(R.id.toneLabel);
        toneBar = findViewById(R.id.tone);
        toneBtn = findViewById(R.id.toneBtn);
        patternSpinner = findViewById(R.id.pattern);
        patALabel = findViewById(R.id.patALabel);
        patBLabel = findViewById(R.id.patBLabel);
        patAEdit = findViewById(R.id.patA);
        patBEdit = findViewById(R.id.patB);
        maxChunkEdit = findViewById(R.id.maxChunk);
        maxEntriesEdit = findViewById(R.id.maxEntries);
        gapEdit = findViewById(R.id.gap);
        minPulseEdit = findViewById(R.id.minPulse);

        // --- barwa ---
        LinearLayout tb = findViewById(R.id.timbreBox);
        dStart = new Slider(tb, "dStart", "Wypełnienie na początku nuty: %.0f %%", 5, 95, 1, 50);
        dEnd = new Slider(tb, "dEnd", "Wypełnienie na końcu nuty / drugi koniec LFO: %.0f %%", 5, 95, 1, 50);
        lfo = new Slider(tb, "lfo", "LFO wypełnienia (wah): %.1f Hz  (0 = liniowo)", 0, 10, 0.5, 0);
        vibDepth = new Slider(tb, "vibDepth", "Vibrato – głębokość: %.0f centów", 0, 100, 5, 0);
        vibRate = new Slider(tb, "vibRate", "Vibrato – tempo: %.1f Hz", 1, 12, 0.5, 5);
        vibDelay = new Slider(tb, "vibDelay", "Vibrato – opóźnienie: %.0f ms", 0, 500, 10, 0);
        glide = new Slider(tb, "glide", "Glissando: %.0f ms", 0, 300, 10, 0);
        setupSpinner(presetSpinner, Timbre.PRESET_NAMES, pos -> {
            if (!userPreset) {
                userPreset = true;
                return;
            }
            applyTimbre(Timbre.preset(Timbre.PRESETS[pos]));
        });

        // --- polifonia ---
        LinearLayout pb = findViewById(R.id.polyBox);
        arpMs = new Slider(pb, "arpMs", "Arpeggio – przełączanie co %.0f ms", 5, 60, 1, 20);
        mixPulse = new Slider(pb, "mixPulse", "Miks – szerokość impulsu: %.0f µs", 100, 1000, 10, 350);
        setupSpinner(polySpinner, new String[]{
                "Arpeggio (szybkie przełączanie dźwięków)",
                "Miks impulsowy (prawdziwe akordy)"}, pos -> {});

        // --- melodie ---
        setupSpinner(songSpinner, Songs.NAMES, pos -> {
            if (!userSong) {
                userSong = true;
                return;
            }
            if (pos > 0) {
                notesEdit.setText(Songs.NOTES[pos]);
                bpmEdit.setText(String.valueOf(Songs.BPM[pos]));
            }
        });
        loopBox.setOnCheckedChangeListener((b, checked) -> loop = checked);
        findViewById(R.id.play).setOnClickListener(v -> playMelody());
        findViewById(R.id.stop).setOnClickListener(v -> stopAll());

        // --- wzorce ---
        setupSpinner(patternSpinner, Synth.PATTERNS, pos -> {
            patALabel.setText(Synth.PATTERN_A[pos]);
            patBLabel.setText(Synth.PATTERN_B[pos]);
            patAEdit.setEnabled(!"—".equals(Synth.PATTERN_A[pos]));
            patBEdit.setEnabled(!"—".equals(Synth.PATTERN_B[pos]));
            if (!userPattern) {
                userPattern = true;
                return;
            }
            patAEdit.setText(String.valueOf(Synth.PATTERN_A_DEF[pos]));
            patBEdit.setText(String.valueOf(Synth.PATTERN_B_DEF[pos]));
        });
        findViewById(R.id.patStart).setOnClickListener(v -> startPattern());
        findViewById(R.id.patStop).setOnClickListener(v -> stopAll());

        loadPrefs();
        showStatus();

        // --- klawiatura i perkusja ---
        buildKeyboard();
        buildDrumPads();
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

    // =================================================================
    // UI – pomocnicze
    // =================================================================

    private interface OnPick {
        void pick(int pos);
    }

    private void setupSpinner(Spinner sp, String[] items, OnPick cb) {
        ArrayAdapter<String> ad = new ArrayAdapter<>(this, android.R.layout.simple_spinner_item, items);
        ad.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        sp.setAdapter(ad);
        sp.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int pos, long id) {
                cb.pick(pos);
            }

            @Override
            public void onNothingSelected(AdapterView<?> parent) {}
        });
    }

    private void applyTimbre(Timbre t) {
        if (t == null) return;
        dStart.set(t.d0 * 100);
        dEnd.set(t.d1 * 100);
        lfo.set(t.lfoHz);
        vibDepth.set(t.vibCents);
        vibRate.set(t.vibHz);
        vibDelay.set(t.vibDelayMs);
        glide.set(t.glideMs);
    }

    private Timbre readTimbre() {
        Timbre t = new Timbre();
        t.d0 = dStart.get() / 100;
        t.d1 = dEnd.get() / 100;
        t.lfoHz = lfo.get();
        t.vibCents = vibDepth.get();
        t.vibHz = vibRate.get();
        t.vibDelayMs = vibDelay.get();
        t.glideMs = glide.get();
        return t;
    }

    private int[][] carrierRanges() {
        try {
            ConsumerIrManager.CarrierFrequencyRange[] rs = ir.getCarrierFrequencies();
            if (rs == null) return null;
            int[][] out = new int[rs.length][];
            for (int i = 0; i < rs.length; i++)
                out[i] = new int[]{rs[i].getMinFrequency(), rs[i].getMaxFrequency()};
            return out;
        } catch (Exception e) {
            return null;
        }
    }

    private void showStatus() {
        StringBuilder sb = new StringBuilder();
        if (ir == null || !ir.hasIrEmitter()) {
            sb.append("⚠ Ten telefon nie ma diody IR (ConsumerIrManager).");
        } else {
            sb.append("✔ Dioda IR wykryta. Obsługiwane nośne: ");
            int[][] rs = carrierRanges();
            if (rs == null || rs.length == 0) {
                sb.append("brak danych");
            } else {
                for (int i = 0; i < rs.length; i++) {
                    if (i > 0) sb.append(", ");
                    sb.append(rs[i][0]);
                    if (rs[i][1] != rs[i][0]) sb.append("–").append(rs[i][1]);
                }
                sb.append(" Hz");
            }
        }
        statusText.setText(sb);
    }

    private void buildKeyboard() {
        LinearLayout sharps = findViewById(R.id.keysSharp);
        LinearLayout whites = findViewById(R.id.keysWhite);
        int[] whiteSemis = {0, 2, 4, 5, 7, 9, 11, 12};
        int[] sharpSemis = {1, 3, -1, 6, 8, 10, -1, -1};
        for (int i = 0; i < whiteSemis.length; i++) {
            whites.addView(makeKey(whiteSemis[i], false));
            if (sharpSemis[i] >= 0) {
                sharps.addView(makeKey(sharpSemis[i], true));
            } else {
                sharps.addView(new View(this), new LinearLayout.LayoutParams(0, 1, 1f));
            }
        }
        setOctave(octave);
    }

    private Button smallButton(String text) {
        Button b = new Button(this);
        b.setAllCaps(false);
        b.setTextSize(12);
        b.setPadding(0, 0, 0, 0);
        b.setText(text);
        b.setLayoutParams(new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        return b;
    }

    @SuppressLint("ClickableViewAccessibility")
    private Button makeKey(final int semi, boolean sharp) {
        Button b = smallButton("");
        b.setTag(semi);
        if (sharp) b.setAlpha(0.75f);
        final int[] myGen = {-1};
        b.setOnTouchListener((v, ev) -> {
            switch (ev.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    v.setPressed(true);
                    final double f = Melody.noteFreq(12 * (octave + 1) + semi);
                    nowPlaying.setText(String.format(Locale.US, "%s  %.1f Hz", keyName(semi), f));
                    myGen[0] = startContinuous(() -> f, readTimbre());
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

    private void buildDrumPads() {
        LinearLayout row = findViewById(R.id.drumPads);
        for (int i = 0; i < Melody.DRUM_LETTERS.length(); i++) {
            final int type = Melody.KICK + i;
            String name = Melody.DRUM_NAMES[i];
            Button b = smallButton(Melody.DRUM_LETTERS.charAt(i) + "\n" + name.substring(0, Math.min(5, name.length())));
            b.setOnClickListener(v -> {
                if (!checkIr()) return;
                stopAll();
                final Synth sy = newSynth(readSettings());
                nowPlaying.setText(name);
                exec.execute(() -> sy.drum(type));
            });
            row.addView(b);
        }
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
        toneFreq = 50.0 * Math.pow(60.0, toneBar.getProgress() / 1000.0); // 50 … 3000 Hz, log
        toneLabel.setText(String.format(Locale.US, "Częstotliwość: %.0f Hz", toneFreq));
    }

    private void setNow(final String s) {
        ui.post(() -> nowPlaying.setText(s));
    }

    private static int intOf(EditText e, int def, int min, int max) {
        try {
            int v = Integer.parseInt(e.getText().toString().trim());
            return Math.max(min, Math.min(max, v));
        } catch (NumberFormatException ex) {
            return def;
        }
    }

    private Synth.Settings readSettings() {
        Synth.Settings s = new Synth.Settings();
        s.carrier = intOf(carrierEdit, 38000, 15000, 100000);
        s.maxChunkUs = intOf(maxChunkEdit, 400, 20, 1900) * 1000.0;
        s.maxEntries = intOf(maxEntriesEdit, 1000, 4, 100000);
        s.gapUs = intOf(gapEdit, 25, 0, 1000) * 1000.0;
        s.minPulse = intOf(minPulseEdit, 30, 1, 5000);
        s.bpm = intOf(bpmEdit, 120, 10, 600);
        s.timbre = readTimbre();
        s.mix = polySpinner.getSelectedItemPosition() == 1;
        s.arpUs = arpMs.get() * 1000;
        s.mixPulseUs = mixPulse.get();
        return s;
    }

    private final Synth.Listener listener = new Synth.Listener() {
        @Override
        public void status(String s) {
            setNow(s);
        }

        @Override
        public void error(String s) {
            ui.post(() -> {
                Toast.makeText(MainActivity.this, s, Toast.LENGTH_LONG).show();
                nowPlaying.setText("błąd");
            });
        }
    };

    /** Anuluje poprzednie nadawanie i tworzy syntezator dla nowego. */
    private Synth newSynth(Synth.Settings s) {
        int my = gen.incrementAndGet();
        return new Synth((c, p) -> ir.transmit(c, p), gen, my, s, listener);
    }

    private boolean checkIr() {
        if (ir == null || !ir.hasIrEmitter()) {
            Toast.makeText(this, "Brak diody IR w tym telefonie", Toast.LENGTH_SHORT).show();
            return false;
        }
        return true;
    }

    // =================================================================
    // Akcje
    // =================================================================

    private void stopAll() {
        gen.incrementAndGet();
        toneGen = -1;
        toneBtn.setText("Ton ciągły");
        nowPlaying.setText("");
    }

    private void playMelody() {
        if (!checkIr()) return;
        final Melody.Song song;
        try {
            song = Melody.parse(notesEdit.getText().toString());
        } catch (IllegalArgumentException e) {
            Toast.makeText(this, "Błąd w nutach: " + e.getMessage(), Toast.LENGTH_LONG).show();
            return;
        }
        if (song.voices.isEmpty()) {
            Toast.makeText(this, "Wpisz jakieś nuty", Toast.LENGTH_SHORT).show();
            return;
        }
        stopAll();
        if (song.bpm > 0) bpmEdit.setText(String.valueOf(song.bpm));
        if (song.mix >= 0) polySpinner.setSelection(song.mix);
        loop = loopBox.isChecked();
        final Synth sy = newSynth(readSettings());
        exec.execute(() -> {
            do {
                if (!sy.playSong(song)) return;
            } while (loop && sy.alive());
            if (sy.alive()) setNow("koniec");
        });
    }

    private void toggleTone() {
        if (toneGen >= 0 && gen.get() == toneGen) {
            stopAll();
            return;
        }
        if (!checkIr()) return;
        stopAll();
        toneGen = startContinuous(() -> toneFreq, new Timbre());
        toneBtn.setText("Zatrzymaj ton");
        nowPlaying.setText("ton ciągły");
    }

    private void sweep() {
        if (!checkIr()) return;
        stopAll();
        final Synth sy = newSynth(readSettings());
        exec.execute(() -> {
            final double f0 = 100, f1 = 2000;
            final int steps = 100;          // 100 × 50 ms = 5 s
            Timbre pure = new Timbre();
            for (int i = 0; i <= steps; i++) {
                double f = f0 * Math.pow(f1 / f0, i / (double) steps);
                setNow(String.format(Locale.US, "sweep %.0f Hz", f));
                if (!sy.toneFor(f, 50_000, pure)) return;
            }
            sy.flush();
            if (sy.alive()) setNow("koniec sweepu");
        });
    }

    private void startPattern() {
        if (!checkIr()) return;
        stopAll();
        final int type = patternSpinner.getSelectedItemPosition();
        final double a = intOf(patAEdit, Synth.PATTERN_A_DEF[type], 0, 10_000_000);
        final double b = intOf(patBEdit, Synth.PATTERN_B_DEF[type], 0, 10_000_000);
        final int[][] ranges = carrierRanges();
        final Synth sy = newSynth(readSettings());
        exec.execute(() -> sy.pattern(type, a, b, ranges));
    }

    /** Ciągły ton (krótkie paczki dla szybkiej reakcji) do zmiany generacji. */
    private int startContinuous(final Synth.FreqSource src, final Timbre tb) {
        if (ir == null || !ir.hasIrEmitter()) return -1;
        Synth.Settings s = readSettings();
        s.maxChunkUs = Math.min(s.maxChunkUs, 100_000);
        final Synth sy = newSynth(s);
        final int my = gen.get();
        exec.execute(() -> sy.hold(src, tb));
        return my;
    }

    // =================================================================
    // Ustawienia
    // =================================================================

    private void loadPrefs() {
        SharedPreferences sp = getPreferences(MODE_PRIVATE);
        carrierEdit.setText(sp.getString("carrier", "38000"));
        notesEdit.setText(sp.getString("notes", Songs.NOTES[Songs.DEFAULT]));
        bpmEdit.setText(sp.getString("bpm", String.valueOf(Songs.BPM[Songs.DEFAULT])));
        maxChunkEdit.setText(sp.getString("maxChunk", "400"));
        maxEntriesEdit.setText(sp.getString("maxEntries", "1000"));
        gapEdit.setText(sp.getString("gap", "25"));
        minPulseEdit.setText(sp.getString("minPulse", "30"));
        toneBar.setProgress(sp.getInt("tone", 500));
        octave = sp.getInt("octave", 4);
        for (Slider s : sliders) {
            if (sp.contains("sl_" + s.key)) s.set(sp.getFloat("sl_" + s.key, 0));
        }
        int song = sp.getInt("song", Songs.DEFAULT);
        if (song >= 0 && song < Songs.NAMES.length) songSpinner.setSelection(song);
        int preset = sp.getInt("preset", 0);
        if (preset >= 0 && preset < Timbre.PRESETS.length) presetSpinner.setSelection(preset);
        polySpinner.setSelection(sp.getInt("poly", 0) == 1 ? 1 : 0);
        int pat = sp.getInt("pattern", 0);
        if (pat < 0 || pat >= Synth.PATTERNS.length) pat = 0;
        patternSpinner.setSelection(pat);
        patAEdit.setText(sp.getString("patA", String.valueOf(Synth.PATTERN_A_DEF[pat])));
        patBEdit.setText(sp.getString("patB", String.valueOf(Synth.PATTERN_B_DEF[pat])));
    }

    private void savePrefs() {
        SharedPreferences.Editor e = getPreferences(MODE_PRIVATE).edit()
                .putString("carrier", carrierEdit.getText().toString())
                .putString("notes", notesEdit.getText().toString())
                .putString("bpm", bpmEdit.getText().toString())
                .putString("maxChunk", maxChunkEdit.getText().toString())
                .putString("maxEntries", maxEntriesEdit.getText().toString())
                .putString("gap", gapEdit.getText().toString())
                .putString("minPulse", minPulseEdit.getText().toString())
                .putInt("tone", toneBar.getProgress())
                .putInt("octave", octave)
                .putInt("song", songSpinner.getSelectedItemPosition())
                .putInt("preset", presetSpinner.getSelectedItemPosition())
                .putInt("poly", polySpinner.getSelectedItemPosition())
                .putInt("pattern", patternSpinner.getSelectedItemPosition())
                .putString("patA", patAEdit.getText().toString())
                .putString("patB", patBEdit.getText().toString());
        for (Slider s : sliders) e.putFloat("sl_" + s.key, (float) s.get());
        e.apply();
    }

    private abstract static class SimpleSeek implements SeekBar.OnSeekBarChangeListener {
        @Override
        public void onStartTrackingTouch(SeekBar s) {}

        @Override
        public void onStopTrackingTouch(SeekBar s) {}
    }
}
