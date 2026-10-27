class_name FishCatalog
extends RefCounted

const TIER_COASTAL: String = "Coastal"
const TIER_PELAGIC: String = "Pelagic / Deep Reef"
const TIER_ABYSSAL: String = "Abyssal Trench"

const HABITAT_ANY: String = "ANY"
const HABITAT_ROCKY_REEF: String = "ROCKY_REEF"
const HABITAT_ARCH_MONOLITH: String = "ARCH_MONOLITH"
const HABITAT_DEEP_TRENCH: String = "DEEP_TRENCH"


static func get_all_species() -> Array[Dictionary]:
	var catalog: Array[Dictionary] = [
		{
			"id": "mackerel",
			"display_name": "Atlantic Mackerel",
			"tier_name": TIER_COASTAL,
			"glb_path": "res://assets/models/fish/fish_mackerel.glb",
			"min_depth_m": 4.0,
			"max_depth_m": 35.0,
			"min_weight_kg": 0.8,
			"max_weight_kg": 3.2,
			"price_per_kg": 4.5,
			"habitat_preference": HABITAT_ANY,
			"pull_strength": 0.65,
			"surge_duration_range": Vector2(1.2, 2.0),
			"rest_duration_range": Vector2(2.4, 3.6),
			"lateral_thrash_speed": 3.8,
			"hint": "Spotted around 4m–35m in upper coastal surface shoals.",
			"lore": "Restless silver shoals that flee the deep trenches whenever the moon turns pale.",
		},
		{
			"id": "pollock",
			"display_name": "Saithe Pollock",
			"tier_name": TIER_COASTAL,
			"glb_path": "res://assets/models/fish/fish_pollock.glb",
			"min_depth_m": 8.0,
			"max_depth_m": 45.0,
			"min_weight_kg": 2.5,
			"max_weight_kg": 9.5,
			"price_per_kg": 5.2,
			"habitat_preference": HABITAT_ANY,
			"pull_strength": 0.80,
			"surge_duration_range": Vector2(1.5, 2.5),
			"rest_duration_range": Vector2(2.2, 3.4),
			"lateral_thrash_speed": 2.9,
			"hint": "Spotted around 8m–45m patrolling coastal harbor shelves.",
			"lore": "Cold-water prowlers with clouded eyes, often hauled up tangled in drownedpilings.",
		},
		{
			"id": "cod",
			"display_name": "Atlantic Cod",
			"tier_name": TIER_COASTAL,
			"glb_path": "res://assets/models/fish/fish_cod.glb",
			"min_depth_m": 10.0,
			"max_depth_m": 55.0,
			"min_weight_kg": 4.5,
			"max_weight_kg": 22.0,
			"price_per_kg": 6.5,
			"habitat_preference": HABITAT_ROCKY_REEF,
			"pull_strength": 0.95,
			"surge_duration_range": Vector2(1.8, 3.0),
			"rest_duration_range": Vector2(2.1, 3.3),
			"lateral_thrash_speed": 2.5,
			"hint": "Spotted around 10m–55m near rocky coastal reefs & island drop-offs.",
			"lore": "Heavy-jawed bottom feeders whose stomachs occasionally hold tarnished brass buttons.",
		},
		{
			"id": "rockfish",
			"display_name": "Redband Rockfish",
			"tier_name": TIER_COASTAL,
			"glb_path": "res://assets/models/fish/fish_rockfish.glb",
			"min_depth_m": 15.0,
			"max_depth_m": 50.0,
			"min_weight_kg": 1.8,
			"max_weight_kg": 6.8,
			"price_per_kg": 8.5,
			"habitat_preference": HABITAT_ROCKY_REEF,
			"pull_strength": 0.85,
			"surge_duration_range": Vector2(1.4, 2.4),
			"rest_duration_range": Vector2(2.3, 3.5),
			"lateral_thrash_speed": 2.7,
			"hint": "Spotted around 15m–50m hugging jagged rocky reefs & sea stacks.",
			"lore": "Venom-spined reef dwellers stained the color of rusted hull plates and dried brine.",
		},
		{
			"id": "hake",
			"display_name": "Silver Hake",
			"tier_name": TIER_PELAGIC,
			"glb_path": "res://assets/models/fish/fish_hake.glb",
			"min_depth_m": 30.0,
			"max_depth_m": 80.0,
			"min_weight_kg": 3.5,
			"max_weight_kg": 14.0,
			"price_per_kg": 7.8,
			"habitat_preference": HABITAT_ANY,
			"pull_strength": 1.05,
			"surge_duration_range": Vector2(1.6, 2.8),
			"rest_duration_range": Vector2(1.9, 3.0),
			"lateral_thrash_speed": 4.2,
			"hint": "Spotted around 30m–80m hunting in midwater pelagic currents.",
			"lore": "Needle-toothed nocturnal hunters that rise into the thermocline when storm bells toll.",
		},
		{
			"id": "wolffish",
			"display_name": "Spotted Wolffish",
			"tier_name": TIER_PELAGIC,
			"glb_path": "res://assets/models/fish/fish_wolffish.glb",
			"min_depth_m": 35.0,
			"max_depth_m": 85.0,
			"min_weight_kg": 6.0,
			"max_weight_kg": 24.0,
			"price_per_kg": 9.5,
			"habitat_preference": HABITAT_ROCKY_REEF,
			"pull_strength": 1.20,
			"surge_duration_range": Vector2(2.0, 3.4),
			"rest_duration_range": Vector2(1.8, 2.8),
			"lateral_thrash_speed": 3.6,
			"hint": "Spotted around 35m–85m in deep boulder crevices & razor reefs.",
			"lore": "Brutish, fang-mawed serpents of the boulder shelves that snap at iron gaffs even on deck.",
		},
		{
			"id": "monkfish",
			"display_name": "Blackbellied Monkfish",
			"tier_name": TIER_PELAGIC,
			"glb_path": "res://assets/models/fish/fish_monkfish.glb",
			"min_depth_m": 40.0,
			"max_depth_m": 95.0,
			"min_weight_kg": 8.5,
			"max_weight_kg": 32.0,
			"price_per_kg": 11.0,
			"habitat_preference": HABITAT_ARCH_MONOLITH,
			"pull_strength": 1.35,
			"surge_duration_range": Vector2(2.6, 4.2),
			"rest_duration_range": Vector2(2.0, 3.0),
			"lateral_thrash_speed": 1.9,
			"hint": "Spotted around 40m–95m lurking beneath sea arches & basalt monoliths.",
			"lore": "Distended ambush predators half-buried in black silt beneath cyclopean basalt arches.",
		},
		{
			"id": "halibut",
			"display_name": "Atlantic Halibut",
			"tier_name": TIER_PELAGIC,
			"glb_path": "res://assets/models/fish/fish_halibut.glb",
			"min_depth_m": 45.0,
			"max_depth_m": 105.0,
			"min_weight_kg": 18.0,
			"max_weight_kg": 85.0,
			"price_per_kg": 12.5,
			"habitat_preference": HABITAT_ARCH_MONOLITH,
			"pull_strength": 1.55,
			"surge_duration_range": Vector2(3.0, 4.6),
			"rest_duration_range": Vector2(1.8, 2.8),
			"lateral_thrash_speed": 2.1,
			"hint": "Spotted around 45m–105m on deep shelves near sea arches & monoliths.",
			"lore": "Ancient slab-bodied leviathans whose migrated eyes stare upward from the drowned ledges.",
		},
		{
			"id": "scabbardfish",
			"display_name": "Black Scabbardfish",
			"tier_name": TIER_ABYSSAL,
			"glb_path": "res://assets/models/fish/fish_scabbardfish.glb",
			"min_depth_m": 65.0,
			"max_depth_m": 125.0,
			"min_weight_kg": 4.0,
			"max_weight_kg": 16.5,
			"price_per_kg": 14.0,
			"habitat_preference": HABITAT_DEEP_TRENCH,
			"pull_strength": 1.25,
			"surge_duration_range": Vector2(1.5, 2.6),
			"rest_duration_range": Vector2(1.6, 2.5),
			"lateral_thrash_speed": 4.6,
			"hint": "Spotted around 65m–125m rising through deep abyssal canyons.",
			"lore": "Metallic, blade-thin horrors with coal-black skin and staring amber abyssal eyes.",
		},
		{
			"id": "grenadier",
			"display_name": "Abyssal Grenadier",
			"tier_name": TIER_ABYSSAL,
			"glb_path": "res://assets/models/fish/fish_grenadier.glb",
			"min_depth_m": 75.0,
			"max_depth_m": 135.0,
			"min_weight_kg": 3.2,
			"max_weight_kg": 12.5,
			"price_per_kg": 15.5,
			"habitat_preference": HABITAT_DEEP_TRENCH,
			"pull_strength": 1.15,
			"surge_duration_range": Vector2(2.0, 3.2),
			"rest_duration_range": Vector2(1.8, 2.8),
			"lateral_thrash_speed": 3.1,
			"hint": "Spotted around 75m–135m along the cold floor of deep trenches.",
			"lore": "Whip-tailed trench scavengers that sense the heartbeat of dying things through total darkness.",
		},
		{
			"id": "oarfish",
			"display_name": "Regal Oarfish",
			"tier_name": TIER_ABYSSAL,
			"glb_path": "res://assets/models/fish/fish_oarfish.glb",
			"min_depth_m": 80.0,
			"max_depth_m": 135.0,
			"min_weight_kg": 25.0,
			"max_weight_kg": 110.0,
			"price_per_kg": 18.0,
			"habitat_preference": HABITAT_DEEP_TRENCH,
			"pull_strength": 1.65,
			"surge_duration_range": Vector2(2.8, 4.5),
			"rest_duration_range": Vector2(1.6, 2.5),
			"lateral_thrash_speed": 3.5,
			"hint": "Spotted around 80m–135m suspended in deep oceanic trenches.",
			"lore": "Crowned in crimson dorsal spines; old whalers whisper its surfacing heralds a sinking.",
		},
		{
			"id": "angler",
			"display_name": "Void-Lantern Angler",
			"tier_name": TIER_ABYSSAL,
			"glb_path": "res://assets/models/fish/fish_angler.glb",
			"min_depth_m": 85.0,
			"max_depth_m": 135.0,
			"min_weight_kg": 12.0,
			"max_weight_kg": 44.0,
			"price_per_kg": 22.0,
			"habitat_preference": HABITAT_DEEP_TRENCH,
			"pull_strength": 1.50,
			"surge_duration_range": Vector2(2.5, 4.0),
			"rest_duration_range": Vector2(1.7, 2.6),
			"lateral_thrash_speed": 3.2,
			"hint": "Spotted around 85m–135m in pitch-black abyssal trenches.",
			"lore": "Its sickly teal esca pulses with a rhythm that does not belong to any earthly sea.",
		},
	]
	return catalog


static func get_species_by_id(species_id: String) -> Dictionary:
	var all_species: Array[Dictionary] = get_all_species()
	for spec: Dictionary in all_species:
		if (spec.get("id", "") as String) == species_id:
			return spec
	return all_species[0]


static func get_tier_color(tier_name: String) -> Color:
	if tier_name == TIER_ABYSSAL:
		return Color(0.96, 0.34, 0.38, 1.0)
	elif tier_name == TIER_PELAGIC:
		return Color(0.96, 0.74, 0.28, 1.0)
	return Color(0.48, 0.78, 0.84, 1.0)


static func roll_species_for_hook(
	hook_depth_m: float,
	seabed_depth_m: float,
	near_rock_hazard: bool,
	biomass: float,
	near_arch_monolith: bool = false,
	near_poi_hotspot: bool = false
) -> Dictionary:
	var all_species: Array[Dictionary] = get_all_species()
	var candidates: Array[Dictionary] = []
	var weights: Array[float] = []
	var total_weight: float = 0.0

	for spec: Dictionary in all_species:
		var min_d: float = spec.get("min_depth_m", 0.0) as float
		var max_d: float = spec.get("max_depth_m", 140.0) as float
		if hook_depth_m >= min_d and hook_depth_m <= max_d:
			var w: float = 1.0
			var pref: String = spec.get("habitat_preference", HABITAT_ANY) as String
			if pref == HABITAT_ROCKY_REEF and near_rock_hazard:
				w *= 2.5
			elif pref == HABITAT_ARCH_MONOLITH and (near_arch_monolith or near_rock_hazard):
				w *= 2.6
			elif pref == HABITAT_DEEP_TRENCH and seabed_depth_m >= 75.0:
				w *= 2.8

			# High biomass boosts deeper/rarer predators within the active depth band
			var price: float = spec.get("price_per_kg", 5.0) as float
			if biomass >= 0.55 and price >= 9.0:
				w *= lerpf(1.1, 2.1, clampf((biomass - 0.55) / 0.45, 0.0, 1.0))

			# Slight bell-curve preference toward center of species depth window
			var mid_d: float = 0.5 * (min_d + max_d)
			var half_span: float = maxf(1.0, 0.5 * (max_d - min_d))
			var center_fit: float = 1.0 - 0.35 * clampf(absf(hook_depth_m - mid_d) / half_span, 0.0, 1.0)
			w *= center_fit

			candidates.append(spec)
			weights.append(w)
			total_weight += w

	if candidates.is_empty():
		candidates.append(all_species[0])
		weights.append(1.0)
		total_weight = 1.0

	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	rng.randomize()
	var pick: float = rng.randf() * total_weight
	var chosen: Dictionary = candidates[0]
	var accum: float = 0.0
	for i: int in range(candidates.size()):
		accum += weights[i]
		if pick <= accum:
			chosen = candidates[i]
			break

	var min_w: float = chosen.get("min_weight_kg", 2.0) as float
	var max_w: float = chosen.get("max_weight_kg", 12.0) as float
	# Biomass biases the weight distribution toward heavier trophy specimens
	var raw_t: float = rng.randf()
	var biomass_exponent: float = lerpf(1.45, 0.68, clampf(biomass, 0.0, 1.0))
	var weight_t: float = clampf(pow(raw_t, biomass_exponent), 0.0, 1.0)
	var rolled_weight: float = snappedf(lerpf(min_w, max_w, weight_t), 0.1)
	if near_poi_hotspot:
		# Boost trophy fish weight (+20%) when casting near a discovered POI!
		rolled_weight = snappedf(rolled_weight * 1.20, 0.1)

	var price_kg: float = chosen.get("price_per_kg", 6.0) as float
	var catch_value: float = snappedf(rolled_weight * price_kg, 0.5)

	var result: Dictionary = chosen.duplicate()
	result["name"] = chosen.get("display_name", "Atlantic Cod") as String
	result["weight_kg"] = rolled_weight
	result["depth_m"] = snappedf(hook_depth_m, 0.1)
	result["value"] = catch_value
	return result
