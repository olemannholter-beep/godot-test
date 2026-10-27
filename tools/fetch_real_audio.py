"""Fetch real field-recorded Ogg Vorbis audio from Wikimedia Commons API with click-free low-pass fallback."""

import json
import math
import os
import random
import struct
import urllib.parse
import urllib.request
import wave


USER_AGENT: str = "GodotAudioFetcher/1.0 (https://godotengine.org; godot-test-project)"
COMMONS_API_URL: str = "https://commons.wikimedia.org/w/api.php"


def is_valid_ogg_vorbis(data: bytes) -> bool:
	return len(data) > 64 and data[:4] == b"OggS" and b"\x01vorbis" in data[:256]


def search_and_download_commons_ogg(queries: list[str], min_duration: float, max_duration: float) -> bytes | None:
	for query in queries:
		params: dict[str, str] = {
			"action": "query",
			"format": "json",
			"generator": "search",
			"gsrsearch": f"filetype:audio {query}",
			"gsrnamespace": "6",
			"gsrlimit": "15",
			"prop": "imageinfo",
			"iiprop": "url|size|mime",
		}
		url: str = f"{COMMONS_API_URL}?{urllib.parse.urlencode(params)}"
		req: urllib.request.Request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
		try:
			with urllib.request.urlopen(req, timeout=15) as resp:
				payload: dict = json.loads(resp.read().decode("utf-8"))
		except Exception as exc:
			print(f"Search request failed for '{query}': {exc}")
			continue

		pages: dict = payload.get("query", {}).get("pages", {})
		for page in pages.values():
			title: str = page.get("title", "")
			if not title.lower().endswith(".ogg"):
				continue
			imageinfo_list: list = page.get("imageinfo", [])
			if not imageinfo_list:
				continue
			info: dict = imageinfo_list[0]
			file_url: str = info.get("url", "")
			size: int = int(info.get("size", 0))
			# Keep file size reasonable (50 KB to 6 MB)
			if not file_url or size < 40000 or size > 6500000:
				continue

			try:
				dl_req: urllib.request.Request = urllib.request.Request(file_url, headers={"User-Agent": USER_AGENT})
				with urllib.request.urlopen(dl_req, timeout=20) as dl_resp:
					audio_bytes: bytes = dl_resp.read()
				if is_valid_ogg_vorbis(audio_bytes):
					print(f"Downloaded valid Ogg Vorbis: {title} ({len(audio_bytes)} bytes) from {file_url}")
					return audio_bytes
			except Exception as exc:
				print(f"Failed downloading {file_url}: {exc}")
				continue

	return None


def write_fallback_stereo_wav(filepath: str, duration_sec: float, mode: str) -> None:
	sample_rate: int = 44100
	total_samples: int = int(sample_rate * duration_sec)
	crossfade_samples: int = int(sample_rate * 1.2)
	raw_len: int = total_samples + crossfade_samples
	rng: random.Random = random.Random(hash(mode) & 0xFFFFFFFF)

	cutoff_hz: float = 260.0 if mode != "engine" else 180.0
	rc: float = 1.0 / (2.0 * math.pi * cutoff_hz)
	dt: float = 1.0 / float(sample_rate)
	alpha: float = dt / (rc + dt)

	left_raw: list[float] = [0.0] * raw_len
	right_raw: list[float] = [0.0] * raw_len

	b_l: float = 0.0
	b_r: float = 0.0
	lp1_l: float = 0.0
	lp2_l: float = 0.0
	lp1_r: float = 0.0
	lp2_r: float = 0.0

	for i in range(raw_len):
		t: float = float(i) / float(sample_rate)
		w_l: float = rng.uniform(-1.0, 1.0)
		w_r: float = rng.uniform(-1.0, 1.0)
		b_l = (b_l + 0.03 * w_l) * 0.985
		b_r = (b_r + 0.03 * w_r) * 0.985
		lp1_l += alpha * (b_l - lp1_l)
		lp2_l += alpha * (lp1_l - lp2_l)
		lp1_r += alpha * (b_r - lp1_r)
		lp2_r += alpha * (lp1_r - lp2_r)

		if mode == "engine":
			hum: float = math.sin(2.0 * math.pi * 36.0 * t) * 0.18 + math.sin(2.0 * math.pi * 72.0 * t) * 0.09
			left_raw[i] = (lp2_l * 0.4 + hum) * 0.5
			right_raw[i] = (lp2_r * 0.4 + hum) * 0.5
		else:
			swell: float = 0.8 + 0.2 * math.sin(2.0 * math.pi * t / duration_sec)
			left_raw[i] = lp2_l * 0.45 * swell
			right_raw[i] = lp2_r * 0.45 * swell

	os.makedirs(os.path.dirname(filepath), exist_ok=True)
	with wave.open(filepath, "wb") as wav_file:
		wav_file.setnchannels(2)
		wav_file.setsampwidth(2)
		wav_file.setframerate(sample_rate)
		packed: bytearray = bytearray(total_samples * 4)
		for i in range(total_samples):
			if i < crossfade_samples:
				w: float = float(i) / float(crossfade_samples)
				fi: float = math.sin(w * math.pi * 0.5)
				fo: float = math.cos(w * math.pi * 0.5)
				sl: float = left_raw[i] * fi + left_raw[total_samples + i] * fo
				sr: float = right_raw[i] * fi + right_raw[total_samples + i] * fo
			else:
				sl = left_raw[i]
				sr = right_raw[i]
			vl: int = int(max(-0.95, min(0.95, sl)) * 32767.0)
			vr: int = int(max(-0.95, min(0.95, sr)) * 32767.0)
			struct.pack_into("<hh", packed, i * 4, vl, vr)
		wav_file.writeframes(packed)


def main() -> None:
	audio_dir: str = os.path.join("assets", "audio")
	os.makedirs(audio_dir, exist_ok=True)

	# Remove old synthetic WAV files and their .import files
	for old_file in [
		"rain_hull_loop.wav",
		"rain_hull_loop.wav.import",
		"distant_thunder.wav",
		"distant_thunder.wav.import",
	]:
		old_path: str = os.path.join(audio_dir, old_file)
		if os.path.exists(old_path):
			os.remove(old_path)
			print(f"Removed old file: {old_path}")

	targets: list[tuple[str, list[str], float, float, str]] = [
		(
			"rain_ocean_loop.ogg",
			["ocean waves", "sea waves", "heavy rain ambient", "rain storm"],
			8.0,
			120.0,
			"rain",
		),
		(
			"thunder_strike.ogg",
			["thunder clap", "thunder rumble", "thunder strike", "thunder"],
			2.0,
			30.0,
			"thunder",
		),
		(
			"boat_engine_loop.ogg",
			["boat engine", "diesel engine idle", "marine diesel", "ship engine"],
			3.0,
			90.0,
			"engine",
		),
	]

	for filename, queries, min_d, max_d, mode in targets:
		out_path: str = os.path.join(audio_dir, filename)
		ogg_data: bytes | None = search_and_download_commons_ogg(queries, min_d, max_d)
		if ogg_data is not None:
			with open(out_path, "wb") as f:
				f.write(ogg_data)
			print(f"Saved: {out_path} ({len(ogg_data)} bytes)")
		else:
			wav_fallback: str = os.path.splitext(out_path)[0] + ".wav"
			write_fallback_stereo_wav(wav_fallback, 8.0, mode)
			print(f"Network fallback: wrote {wav_fallback}")


if __name__ == "__main__":
	main()
