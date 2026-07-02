/** Browser alert sounds for line-crossing events. */

let audioContext: AudioContext | null = null;

function getAudioContext(): AudioContext {
  if (!audioContext) {
    audioContext = new AudioContext();
  }
  if (audioContext.state === "suspended") {
    void audioContext.resume();
  }
  return audioContext;
}

function tone(frequency: number, durationMs: number, volume = 0.12): void {
  const ctx = getAudioContext();
  const oscillator = ctx.createOscillator();
  const gain = ctx.createGain();
  oscillator.type = "sine";
  oscillator.frequency.value = frequency;
  gain.gain.value = volume;
  oscillator.connect(gain);
  gain.connect(ctx.destination);
  const now = ctx.currentTime;
  oscillator.start(now);
  oscillator.stop(now + durationMs / 1000);
}

/** Single short beep for yellow-line crossing (warning). */
export function playWarningBeep(): void {
  tone(880, 250);
}

/** One pulse of the critical alarm (red restricted area). */
export function playCriticalBeep(): void {
  tone(1200, 180, 0.15);
}
