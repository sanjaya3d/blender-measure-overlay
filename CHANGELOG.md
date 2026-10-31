# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- Relicensed from MIT to GPL-3.0-or-later (required for extensions.blender.org)
- Added author, maintainer and contact details to the manifest, README and issue chooser

## [2.0.0] - 2026-10-30

First public release.

### Added
- Live viewport overlay showing dimensions and vertex / edge / face counts
- Context-aware readout for single meshes, multi-selections and Edit Mode (selected / total)
- Combined bounding-box size for multi-object selections
- Optional face budget with green / orange / red color coding
- Sidebar tab (N > Measure) with display, position, scale and opacity settings
- Overlay checkbox in the viewport's Overlays dropdown
- Copy Stats button
- Blender 4.2+ extension manifest alongside classic `bl_info` support
