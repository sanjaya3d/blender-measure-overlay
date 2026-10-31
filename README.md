# Measure Overlay

![Blender 3.0+](https://img.shields.io/badge/Blender-3.0%2B-orange)
[![License: GPL v3+](https://img.shields.io/badge/License-GPLv3%2B-blue.svg)](LICENSE)

[![Download latest release](https://img.shields.io/badge/Download-Latest%20Release-2ea44f?style=for-the-badge&logo=github&logoColor=white)](../../releases/latest)

Measure Overlay is a free Blender add-on that draws **live dimensions and geometry stats directly in the 3D viewport**: object size, vertex, edge and face counts, and an optional face budget. No need to keep the sidebar open or switch on the Statistics overlay.

![Measure Overlay screenshot 1](docs/images/Screenshot.png)

![Measure Overlay screenshot 2](docs/images/export-1793434757409.mp4)

## Features

- **Context-aware readout** that changes with what you're doing:
  - *One mesh selected*: name, dimensions, vertex / edge / face counts
  - *Several meshes selected*: combined world-space bounding box and total counts
  - *Edit Mode*: selected / total counts (e.g. `12 / 1,024`), including multi-object editing
  - *Camera, light, empty*: a clear "Not a mesh" note instead of misleading numbers
- **Face budget**: set a limit and the face count turns green, orange at 75%, and red when you go over
- **Respects your scene units** (metric, imperial, unit scale)
- **Stays out of the way**: avoids the toolbar, sidebar, headers and navigation gizmo, and hides with the viewport's Overlays button
- **Native toggle** in the viewport's Overlays dropdown
- **Copy Stats** button that copies exactly what's on screen to the clipboard
- Optionally counts geometry **with or without modifiers**
- **Works offline**: no internet access, no data collection, no extra dependencies

## Installation

Download the latest zip from the [Releases page](../../releases/latest).

| Your Blender | Download | How to install |
|---|---|---|
| **4.2 or newer** | `measure_overlay-x.y.z-extension.zip` | Edit > Preferences > **Get Extensions** > dropdown arrow (top right) > **Install from Disk...** |
| **3.0 to 4.1** | `measure_overlay-x.y.z-legacy.zip` | Edit > Preferences > **Add-ons** > **Install...**, then tick the checkbox to enable it |

## Usage

1. In the 3D viewport, select an object. The overlay appears in the bottom-left corner.
2. Press **N** and open the **Measure** tab to change settings.
3. Toggle the overlay on/off from the **Overlays** dropdown or the checkbox in the Measure panel header.

### Settings

| Setting | What it does |
|---|---|
| Include Modifiers | Count geometry after modifiers (e.g. Subdivision Surface) |
| Show: Dimensions / Geometry | Choose which sections appear |
| Position | Bottom Left, Bottom Right, Top Left or Top Right |
| Scale / Opacity | Size and background transparency of the panel |
| Face Budget | Color-code the face count against your own limit |

Settings are stored per scene.

## Compatibility

Built for Blender **3.0 and newer**. The viewport drawing code handles the `gpu` and `blf` API changes in Blender 4.0, but it has had limited real-world testing, so if something looks off on your version, please [open an issue](../../issues/new/choose) and include your Blender version.

## Development

```bash
# run the unit tests (no Blender needed)
python -m unittest discover -s tests -v

# build installable zips into ./dist
python tools/build_zip.py
```

The tests cover the measuring and report logic using stand-ins for Blender's modules. The drawing code needs a real Blender session to check: build the zips, install one, and look at the viewport.

To work on the add-on live, symlink or copy the `measure_overlay/` folder into your Blender add-ons directory, or use **Reload Scripts** after editing.

### Making a release

1. Bump the version in **both** `measure_overlay/__init__.py` (`bl_info`) and `measure_overlay/blender_manifest.toml`. A test fails if they disagree.
2. Add an entry to [CHANGELOG.md](CHANGELOG.md).
3. Commit, then tag and push:
   ```bash
   git tag v2.0.1
   git push origin v2.0.1
   ```
4. GitHub Actions runs the tests, builds both zips and attaches them to a new GitHub Release.

## Ideas for later

- Triangle count
- Dimensions of just the selected geometry in Edit Mode
- A keyboard shortcut to toggle the overlay

## Author

Made by **SANJAYA3D**. For questions, ideas or feedback, contact me on [Facebook](https://www.facebook.com/sanjaya3d). For bugs, please [open an issue](../../issues/new/choose).

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
