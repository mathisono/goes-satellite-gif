# GOES Satellite GIF

Follow this workflow to produce reliable GOES animations.

## Workflow

1. Collect target sources and frame counts.
2. Download frames into a workspace folder with stable naming.
3. Validate frame count, sort order, and image dimensions.
4. Render GIF with a clear frame rate and loop setting.
5. Return output path and quick summary (source, frame count, fps, duration).
6. Post both GIFs to Discord channel `Your Channel` with a message that includes the current date and time.

## OpenClaw install prompt

Paste this into OpenClaw to install and smoke-test this skill:

```text
Install the GOES Satellite GIF skill on this Linux OpenClaw host.

Tasks:
1. Clone or update https://github.com/mathisono/goes-satellite-gif under my OpenClaw skills or tools workspace.
2. Install required system packages: python3, python3-pil, ffmpeg, and git.
3. Run a smoke test: python3 goes_satellite_gif.py --stream full-disk --frames 3 --fps 2
4. Confirm the output lands under ~/.openclaw/artifacts/noaa/YYYY-MM-DD/run-HHMM/.
5. Report the final GIF path, renderer used, frame count, and any errors.

Do not change OpenClaw global config unless needed. If a dependency or permission fails, stop and show the exact command and error.
```

## Source selection

Use the canonical NOAA STAR pages from `references/goes-sources.md` unless the user provides replacements.

Default targets:
- GOES-18 Full Disk GeoColor (36-frame pull)
- GOES-18 WUS GeoColor (48-frame pull)

## Download and naming rules

- Store each run under a dated folder (for example: `artifacts/noaa/2026-04-29/`).
- Keep separate subfolders for each stream (`full-disk/`, `wus/`).
- Normalize frame names to zero-padded numeric order (`frame-0001.jpg`, ...).
- Never mix frames from different streams in one render pass.

## Validation checks

Before rendering:
- Confirm expected frame counts are present.
- Confirm all files are readable images.
- Confirm dimensions are consistent across frames.
- If checks fail, stop and report the exact mismatch.

## Rendering defaults

- GIF loop: infinite
- FPS: 8 (unless user specifies)
- Palette optimization: enabled
- Output naming:
  - `goes18-full-disk-geocolor.gif`
  - `goes18-wus-geocolor.gif`

Preferred renderer: ffmpeg + palette workflow. If ffmpeg/ffprobe are unavailable, use Pillow fallback rendering and report that fallback in the summary.

If the user asks for side-by-side comparison, build a combined canvas first, then render one GIF.

## Output placement

- Put run artifacts under: `~/.openclaw/artifacts/noaa/YYYY-MM-DD/run-HHMM/`
- Keep frame folders:
  - `full-disk/` for full-disk frames
  - `wus/` for WUS frames
- Save final GIFs at run root:
  - `goes18-full-disk-geocolor.gif`
  - `goes18-wus-geocolor.gif`

Example output from a successful run:
- `~/.openclaw/artifacts/noaa/2026-04-29/run-2331/goes18-full-disk-geocolor.gif`
- `~/.openclaw/artifacts/noaa/2026-04-29/run-2331/goes18-wus-geocolor.gif`

## Discord posting step (final)

After GIFs are generated, post both files to Discord channel `Your Channel`.

Message format:
- Include the current date/time in the text, for example: `GOES update — Thu 2026-04-30 00:11 PDT`.

CLI pattern (preferred single post):
- `openclaw message send --channel discord --target channel:Your Channel --message "GOES update — <current date/time>" --media <full-disk-gif-path> --media <wus-gif-path>`

If upload fails with payload/size limits:
- Create Discord-ready derivatives (resize, reduce colors, reduce FPS/frame count).
- Post files separately (two sends) if needed, one GIF per message.

Verification:
- Run `openclaw channels status --deep`.
- Run `openclaw message read --channel discord --target channel:Your Channel --limit 10 --json`.
- Confirm both filenames appear in recent messages:
  - `goes18-full-disk...gif`
  - `goes18-wus...gif`

## Deliverable format

Always include:
- Output file path(s)
- Source page(s)
- Frame count used
- FPS and resulting duration
- Any dropped/invalid frames
- Discord post target and confirmation evidence (message id / readback)

## Included functional script

This repository includes `goes_satellite_gif.py` to automate the fetch + render flow.

### Quick usage example

Run a fast single-stream smoke run:

```bash
python3 goes_satellite_gif.py --stream full-disk --frames 3 --fps 2
```

Sample output:

```text
Run root: ~/.openclaw/artifacts/noaa/2026-04-30/run-1421
- full-disk: ~/.openclaw/artifacts/noaa/2026-04-30/run-1421/goes18-full-disk-geocolor.gif | frames=3 | fps=2 | duration=1.5s | invalid=0 | renderer=pillow
```

Full default run (both streams):

```bash
python3 goes_satellite_gif.py --stream both --fps 8
```
