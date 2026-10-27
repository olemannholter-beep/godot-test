"""Generate procedural storm audio WAV files for Godot 4.7 overworld."""

import math
import os
import random
import struct
import wave


SAMPLE_RATE: int = 44100


def write_wav_mono_16bit(filepath: str, samples: list[float]) -> None:
	os.makedirs(os.path.dirname(filepath), exist_ok=True)
	with wave.open(filepath, "wb") as wav_file:
		wav_file.setnchannels(1)
		wav_file.setsampwidth(2)
		wav_file.setframerate(SAMPLE_RATE)

		packed_frames: bytearray = bytearray(len(samples) * 2)
		for i, s in enumerate(samples):
			clamped: float = max(-0.98, min(0.98, s))
			val: int = int(clamped * 32767.0)
			struct.pack_into("<h", packed_frames, i * 2, val)

		wav_file.writeframes(packed_frames)


def generate_rain_hull_loop(filepath: str, duration_sec: float = 8.0) -> None:
	rng: random.Random = random.Random(1337)
	total_samples: int = int(SAMPLE_RATE * duration_sec)
	crossfade_samples: int = int(SAMPLE_RATE * 1.0)
	raw_len: int = total_samples + crossfade_samples

	# Generate pink/brown filtered noise bed for steady rain & wind wash
	raw: list[float] = [0.0] * raw_len
	brown_state: float = 0.0
	lp1: float = 0.0
	lp2: float = 0.0
	hp_prev_in: float = 0.0
	hp_prev_out: float = 0.0

	for i in range(raw_len):
		white: float = rng.uniform(-1.0, 1.0)
		brown_state = (brown_state + 0.045 * white) * 0.965
		pink_approx: float = 0.65 * brown_state + 0.35 * white
		# Band-limit between ~120 Hz and ~3500 Hz for natural storm rain wash
		lp1 += 0.28 * (pink_approx - lp1)
		lp2 += 0.22 * (lp1 - lp2)
		hp_out: float = 0.985 * (hp_prev_out + lp2 - hp_prev_in)
		hp_prev_in = lp2
		hp_prev_out = hp_out

		# Gentle slow wind swell modulation (periodic over duration_sec)
		t: float = float(i) / float(SAMPLE_RATE)
		swell: float = 0.85 + 0.15 * math.sin(2.0 * math.pi * t / (duration_sec * 0.5))
		raw[i] = hp_out * 0.24 * swell

	# Layer subtle water droplet ticks hitting wooden deck & iron hull
	num_droplets: int = int(duration_sec * 115)
	for _ in range(num_droplets):
		start_idx: int = rng.randint(0, raw_len - 1200)
		is_iron_ping: bool = rng.random() < 0.28
		freq: float = rng.uniform(1100.0, 2400.0) if is_iron_ping else rng.uniform(480.0, 1050.0)
		decay_rate: float = rng.uniform(140.0, 260.0)
		amp: float = rng.uniform(0.025, 0.075)
		drop_len: int = min(900, raw_len - start_idx)

		for j in range(drop_len):
			dt: float = float(j) / float(SAMPLE_RATE)
			env: float = math.exp(-dt * decay_rate)
			# Subtle upward pitch chirp as droplet splashes
			instant_phase: float = 2.0 * math.pi * freq * dt * (1.0 + 0.35 * dt * 100.0)
			raw[start_idx + j] += math.sin(instant_phase) * env * amp

	# Crossfade tail into head for a click-free 8.0-second loop
	looped: list[float] = [0.0] * total_samples
	for i in range(total_samples):
		if i < crossfade_samples:
			alpha: float = float(i) / float(crossfade_samples)
			fade_in: float = math.sin(alpha * math.pi * 0.5)
			fade_out: float = math.cos(alpha * math.pi * 0.5)
			looped[i] = raw[i] * fade_in + raw[total_samples + i] * fade_out
		else:
			looped[i] = raw[i]

	write_wav_mono_16bit(filepath, looped)


def generate_distant_thunder(filepath: str, duration_sec: float = 6.0) -> None:
	rng: random.Random = random.Random(4242)
	total_samples: int = int(SAMPLE_RATE * duration_sec)
	samples: list[float] = [0.0] * total_samples

	# 2-pole low-pass filter states around 95-120 Hz for deep abyssal rumble
	cutoff_hz: float = 105.0
	rc: float = 1.0 / (2.0 * math.pi * cutoff_hz)
	dt_step: float = 1.0 / float(SAMPLE_RATE)
	alpha_lp: float = dt_step / (rc + dt_step)

	# Secondary mid-crack filter (~380 Hz) for initial lightning snap
	rc_crack: float = 1.0 / (2.0 * math.pi * 380.0)
	alpha_crack: float = dt_step / (rc_crack + dt_step)

	brown: float = 0.0
	lp_stage1: float = 0.0
	lp_stage2: float = 0.0
	crack_lp: float = 0.0

	for i in range(total_samples):
		t: float = float(i) / float(SAMPLE_RATE)
		white: float = rng.uniform(-1.0, 1.0)
		brown = (brown + 0.035 * white) * 0.982

		lp_stage1 += alpha_lp * (brown - lp_stage1)
		lp_stage2 += alpha_lp * (lp_stage1 - lp_stage2)
		crack_lp += alpha_crack * (white - crack_lp)

		# Initial sharp crack at t=0.05..0.35s + secondary rolling echoes at t=0.9s and t=2.1s
		crack_env: float = 0.0
		if t >= 0.03:
			crack_env = math.exp(-(t - 0.03) * 7.5) * (1.0 - math.exp(-(t - 0.03) * 80.0))

		echo_1: float = math.exp(-((t - 0.85) ** 2) / 0.28) * 0.85
		echo_2: float = math.exp(-((t - 1.95) ** 2) / 0.75) * 0.65
		echo_3: float = math.exp(-((t - 3.25) ** 2) / 1.40) * 0.38
		tail_decay: float = math.exp(-max(0.0, t - 0.25) * 0.62)

		rumble_env: float = (0.75 * tail_decay + echo_1 + echo_2 + echo_3)
		# Fade out smoothly over final 0.7s
		if t > duration_sec - 0.7:
			rumble_env *= max(0.0, (duration_sec - t) / 0.7)

		sub_wave: float = math.sin(2.0 * math.pi * 42.0 * t + math.sin(t * 5.0) * 1.5) * 0.18
		val: float = (lp_stage2 * 2.4 + sub_wave) * rumble_env + (crack_lp * 0.65 * crack_env)
		samples[i] = max(-0.95, min(0.95, val * 0.72))

	write_wav_mono_16bit(filepath, samples)


def main() -> None:
	audio_dir: str = os.path.join("assets", "audio")
	rain_path: str = os.path.join(audio_dir, "rain_hull_loop.wav")
	thunder_path: str = os.path.join(audio_dir, "distant_thunder.wav")

	generate_rain_hull_loop(rain_path, duration_sec=8.0)
	generate_distant_thunder(thunder_path, duration_sec=6.0)
	print(f"Generated: {rain_path} ({os.path.getsize(rain_path)} bytes)")
	print(f"Generated: {thunder_path} ({os.path.getsize(thunder_path)} bytes)")


if __name__ == "__main__":
	main()
