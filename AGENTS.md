# AI Agent Guidelines (`AGENTS.md`) — Godot 4.7 Project

All AI coding agents working in this repository MUST strictly adhere to the following rules. This project targets **Godot 4.7** (`config/features=PackedStringArray("4.7", ...)`).

---

## 1. Strict Godot 4.7 Static Typing

Every GDScript (`.gd`) file must use explicit static typing throughout:

- **Variables & Constants:** Always specify explicit types (`var speed: float = 200.0`, `const MAX_HP: int = 100`) or use type inference (`:=`) only when the right-hand side type is unambiguous and literal/constructor-based. Avoid untyped `var`.
- **Typed Arrays & Dictionaries:** Always parameterize collections (`var items: Array[ItemData] = []`, `var scores: Dictionary[String, int] = {}`).
- **Function Signatures:** Every function—including virtual callbacks (`_ready() -> void`, `_process(delta: float) -> void`, `_physics_process(delta: float) -> void`, `_input(event: InputEvent) -> void`)—must declare explicit parameter types and a return type (`-> void` or `-> ReturnType`).
- **Node References:** Always type `@onready` and `@export` node variables (e.g., `@onready var sprite: Sprite2D = $Sprite2D`, `@export var target: Node2D`).
- **`Variant` Warning:** Never rely on implicit `Variant` inference for arithmetic, indexing, or method return values. Cast explicitly with `as Type` when retrieving values from untyped sources (e.g., JSON, generic dictionaries).

```gdscript
# CORRECT
class_name PlayerController
extends CharacterBody2D

@export var move_speed: float = 300.0
@onready var anim_player: AnimationPlayer = $AnimationPlayer

func _physics_process(delta: float) -> void:
	var direction: Vector2 = Input.get_vector("move_left", "move_right", "move_up", "move_down")
	velocity = direction * move_speed
	move_and_slide()
```

---

## 2. Zero Godot 3.x Legacy Syntax

Godot 3.x APIs, keywords, and syntax are strictly forbidden. Always use Godot 4.x equivalents:

| Forbidden (Godot 3.x) | Required (Godot 4.x) |
| :--- | :--- |
| `export var x = 1` | `@export var x: int = 1` |
| `onready var n = $Node` | `@onready var n: Node = $Node` |
| `tool` | `@tool` (at top of file) |
| `yield(obj, "signal")` | `await obj.signal_name` |
| `connect("sig", self, "_on_sig")` | `sig.connect(_on_sig)` |
| `emit_signal("sig", arg)` | `sig.emit(arg)` |
| `instance()` (on `PackedScene`) | `instantiate()` |
| ` KinematicBody2D` / `KinematicBody` | `CharacterBody2D` / `CharacterBody3D` |
| `Spatial` | `Node3D` |
| `Position2D` / `Position3D` | `Marker2D` / `Marker3D` |
| `AnimatedSprite` | `AnimatedSprite2D` / `AnimatedSprite3D` |
| `RayCast2D.cast_to` | `RayCast2D.target_position` |
| `move_and_slide(velocity, Vector2.UP)` | Set `velocity` property, then call `move_and_slide()` with 0 args |
| `change_scene("res://...")` | `get_tree().change_scene_to_file("res://...")` |
| `File.new()` / `Directory.new()` | `FileAccess.open(...)` / `DirAccess.open(...)` |
| `OS.get_ticks_msec()` | `Time.get_ticks_msec()` |
| `Tween` node | `create_tween()` |
| `funcref(obj, "method")` | `Callable(obj, "method")` or `obj.method` |
| `.empty()` on Array/String/Dict | `.is_empty()` |
| `deg2rad()` / `rad2deg()` / `lerp()` | `deg_to_rad()` / `rad_to_deg()` / `lerpf()` |
| `rand_range(a, b)` | `randf_range(a, b)` / `randi_range(a, b)` |

---

## 3. Code-Based Signal Connections Only

- **No `.tscn` Signal Connections:** Never add `[connection signal=...]` blocks inside `.tscn` scene files.
- **Connect in GDScript:** All signals must be connected in code (typically inside `_ready() -> void`) using Godot 4.x first-class `Signal` and `Callable` syntax.
- **Disconnect When Needed:** Use `signal_name.is_connected(callable)` / `signal_name.disconnect(callable)` or flags like `CONNECT_ONE_SHOT` when managing dynamic lifecycles.

```gdscript
# CORRECT
func _ready() -> void:
	start_button.pressed.connect(_on_start_button_pressed)
	health_component.died.connect(_on_died, CONNECT_ONE_SHOT)

func _on_start_button_pressed() -> void:
	pass

func _on_died() -> void:
	pass
```

```gdscript
# FORBIDDEN
connect("pressed", self, "_on_pressed")
start_button.connect("pressed", _on_start_button_pressed) # Avoid string-based signal names
```

---

## 4. Never Guess or Fabricate `uid://` Strings in `.tscn` / `.tres` Files

- **Ban on Invented UIDs:** Never fabricate, increment, or guess `uid="uid://..."` values in `.tscn`, `.tres`, or `.import` files. Invalid or colliding UIDs corrupt Godot's resource cache (`uid_cache.bin`).
- **Omit UIDs When Creating/Editing Text Resources:**
  - In `[gd_scene ...]` or `[gd_resource ...]` headers for newly created files, **omit the `uid` attribute entirely** (e.g., `[gd_scene load_steps=2 format=3]`). Godot will generate and assign a valid UID automatically when the project is opened or imported.
  - In `[ext_resource ...]` entries, reference resources strictly by `type`, `path="res://..."`, and `id="..."` unless you have **read the exact `uid://` string directly** from the target file's header or `.uid` / `.import` file in the workspace.

```ini
# CORRECT (when creating a new .tscn or adding an ext_resource without a known UID)
[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://scripts/player.gd" id="1_player"]

[node name="Player" type="CharacterBody2D"]
script = ExtResource("1_player")
```

---

## 5. Mandatory Headless CLI Verification After Every Script Edit

After **every** creation or modification of a `.gd` script (or related `.tscn` / `project.godot` file), you **MUST** verify the script/project using the Godot CLI in headless check-only mode before concluding your task or moving on:

```bash
# Check a specific modified script:
godot --headless --check-only -s res://path/to/script.gd

# Or run from project root to validate project-wide context alongside the script:
godot --headless --path . --check-only -s res://path/to/script.gd
```

- **Zero Tolerance for Parse/Type Errors:** If `--check-only` outputs any parse errors, static typing errors, or missing identifier errors, fix them immediately and re-run verification until it exits cleanly (`exit code 0`).
- **First-Time Import / Class Cache:** If a new `class_name` or resource was added and `--check-only` cannot resolve it yet, run a headless import pass first:
  ```bash
  godot --headless --import
  ```
  Then re-run `godot --headless --check-only -s res://path/to/script.gd`.

---

## 3D Asset & Art Direction Pipeline (Headless Blender 5.4.0)

1. **Mandatory Headless Blender `.glb` Pipeline**:
   - NEVER use placeholder Godot primitive meshes (`BoxMesh`, `CylinderMesh`, `PrismMesh`, `SphereMesh`) or raw Python `.obj`/`.mtl` vertex scripts for 3D props, boats, buildings, creatures, or environment assets.
   - ALL 3D assets must be generated via standalone Blender 5.4.0 Python scripts (`tools/blender_build_<asset>.py`) executed headlessly (`blender --background --python tools/blender_build_<asset>.py`) and exported as binary glTF 2.0 (`bpy.ops.export_scene.gltf(filepath=..., export_format='GLB', export_apply=True)`) into `res://assets/models/`.
   - **Blender 5.4.0 Executable**: `C:\Users\olema\Downloads\blender-5.4.0-alpha+main.0d0b51704b28-windows.amd64-release\blender-5.4.0-alpha+main.0d0b51704b28-windows.amd64-release\blender.exe` (or `blender` when added to `PATH`).
   - Always follow every Blender export with `godot --headless --editor --quit` so Godot generates `.import` metadata before referencing the `.glb` in scenes or GDScript.

2. **Minimum Geometric Detail & Modifier Standards**:
   Every `tools/blender_build_*.py` script MUST enforce high-detail architectural and organic modeling standards:
   - **No Flat Boxes or Cylinders**: All structural edges must use `BEVEL` modifiers, `SUBSURF`, or multi-station `bmesh` lofting. Buildings and hulls must never be single flat cubes.
   - **Real Boolean Cavities (`BOOLEAN` `DIFFERENCE`)**: Windows, doors, portholes, archways, and structural damage must be physically carved out using Boolean modifiers with recessed 3D frames/mullions and internal emissive glass panes where appropriate.
   - **Weathered Structural Asymmetry**: Man-made structures (shacks, piers, buoys, wrecks) must apply subtle vertex/lattice warping (`2–4` degree slump, sagging roof ridges, warped individual timber planks with `2cm` gaps) so nothing looks sterile or computer-perfect.
   - **Micro-Clutter & 3D Splines (`CURVE`)**: Include tactile maritime micro-details such as beveled 3D `CURVE` ropes, drooping catenary cables, chains, rivets, rubbing strakes, barnacle collars at the waterline, and environmental props.
   - **Geological & Organic Displacement (`DISPLACE`)**: Rocks, cliffs, and organic horror elements must use high-subdivision meshes driven by layered Voronoi/Clouds/Musgrave procedural displacement and sharp faceted normals or smooth vertex groups.

3. **Mandatory PBR Material & Godot Integration Standards**:
   - Every Blender script must assign multi-slot `Principled BSDF` materials with explicit `Base Color` (dark, desaturated eldritch maritime palette), `Metallic`, `Roughness`, and `Emission` values.
   - Wet tidal zones (`y < 1.8m`) must use low roughness (`0.10–0.18`) for realistic specular water sheen; weathered wood/stone must use high roughness (`0.80–0.92`) paired with runtime `NoiseTexture2D` micro-normal maps in Godot.
   - When instantiating `.glb` scenes in GDScript, recursively traverse child `MeshInstance3D` nodes to attach accurate concave trimesh collision (`create_trimesh_collision()`) or optimized physics shapes and configure `visibility_range_end` for smooth 60+ FPS performance.

---

## Visual & Scene Inspection via Godot MCP Bridge

Agents can visually inspect 4K in-game screenshots, lighting, volumetric fog, shaders, UI layout, and 3D models at any time without asking the user for manual screenshots:

- **MCP Server (`godot-inspector` in `.mcp.json` / `tools/godot_mcp_server.py`)**:
  - `godot_capture_screenshot(view_mode, frames)`: Renders the live scene for `frames` frames (default `45`) and writes a 4K screenshot to `res://.mcp_captures/latest_frame.png` alongside live telemetry in `res://.mcp_captures/scene_state.json`. View the image directly with `read_file` on `.mcp_captures/latest_frame.png`.
  - `godot_inspect_scene_tree(scene_path)`: Instantiates and dumps the node hierarchy, attached scripts, transforms, and exported properties of a `.tscn` scene.
  - `godot_check_scripts(script_paths)`: Runs `godot --headless --path . --check-only -s <script>` across the given scripts and returns structured diagnostics.
- **Direct CLI Capture (`tools/mcp_capture_frame.gd`)**:
  - Run `godot --path . -s res://tools/mcp_capture_frame.gd -- --view=<preset> --frames=45` where `<preset>` is `helm`, `first_person`, `harbor_ui`, or `bow_light`.



