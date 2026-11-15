// Copy of frontend/shared/chat/call-sounds.ts (the Client app has no shared alias). Keep in sync.
/*
 * Call sounds (owner request 2026-11-14: "sounds anni sariga ravali"). Every sound is made in the
 * browser with Web Audio, so there are no files to load and nothing to block.
 *
 * Browsers keep sound off until the person clicks on the page. The call page's Join button calls
 * unlockSounds(), which also lets the other people's voices play.
 */

let context: AudioContext | null = null;

/** The shared audio context (also used to measure who is speaking). */
export function audioContext(): AudioContext | null {
  try {
    context = context ?? new AudioContext();
    if (context.state === "suspended") void context.resume().catch(() => undefined);
    return context;
  } catch {
    return null;
  }
}

/** Call from a click: turns sound on for this tab. */
export function unlockSounds(): void {
  audioContext();
}

function tone(
  frequency: number | number[],
  start: number,
  length: number,
  volume = 0.12,
  type: OscillatorType = "sine",
): void {
  const audio = audioContext();
  if (!audio) return;
  const at = audio.currentTime + start;
  const gain = audio.createGain();
  gain.gain.setValueAtTime(0.0001, at);
  gain.gain.exponentialRampToValueAtTime(volume, at + 0.02);
  gain.gain.setValueAtTime(volume, at + Math.max(0.03, length - 0.06));
  gain.gain.exponentialRampToValueAtTime(0.0001, at + length);
  gain.connect(audio.destination);
  for (const value of Array.isArray(frequency) ? frequency : [frequency]) {
    const oscillator = audio.createOscillator();
    oscillator.type = type;
    oscillator.frequency.value = value;
    oscillator.connect(gain);
    oscillator.start(at);
    oscillator.stop(at + length + 0.02);
  }
}

export const sounds = {
  /** Incoming call: a bright two-note ring. */
  ring() {
    tone(880, 0, 0.28, 0.16);
    tone(660, 0.36, 0.28, 0.16);
    tone(880, 0.9, 0.28, 0.16);
    tone(660, 1.26, 0.28, 0.16);
  },
  /** What the caller hears while the other side rings (phone-style 440 + 480 Hz). */
  ringback() {
    tone([440, 480], 0, 1.6, 0.06);
  },
  /** Someone joined. */
  join() {
    tone(587, 0, 0.14, 0.1);
    tone(880, 0.13, 0.22, 0.1);
  },
  /** Someone left. */
  leave() {
    tone(880, 0, 0.14, 0.09);
    tone(523, 0.13, 0.24, 0.09);
  },
  /** Someone is waiting in the lobby. */
  knock() {
    tone(1046, 0, 0.09, 0.13, "triangle");
    tone(1046, 0.16, 0.09, 0.13, "triangle");
    tone(1318, 0.4, 0.25, 0.1);
  },
  /** I was let in. */
  admitted() {
    tone(523, 0, 0.12, 0.1);
    tone(659, 0.12, 0.12, 0.1);
    tone(784, 0.24, 0.24, 0.1);
  },
  /** The call ended or I left. */
  end() {
    tone(659, 0, 0.16, 0.1);
    tone(523, 0.16, 0.16, 0.1);
    tone(392, 0.32, 0.3, 0.1);
  },
};

/** Play a sound now and then every `everyMs` until the returned function is called. */
export function repeat(play: () => void, everyMs: number): () => void {
  play();
  const timer = window.setInterval(play, everyMs);
  return () => window.clearInterval(timer);
}
