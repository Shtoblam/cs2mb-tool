# Inputs for auto-generation

Put user-provided, already extracted map resources here:

```text
inputs/de_dust2/
  de_dust2.nav
  entities.txt
  world_physics_physics.gltf
  world_physics_physics.bin
```

Do **not** commit game resources. This directory is ignored except this README.

Start the local app:

```powershell
python app\server.py --port 8765
```

Open <http://127.0.0.1:8765/> and drag files into the drop zone, or use
`Scan inputs` for this local-path fallback.

Browser upload/drop is the preferred path; this directory remains useful for
large files or repeated runs.
