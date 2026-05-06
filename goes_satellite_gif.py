#!/usr/bin/env python3
"""Build GOES-18 GeoColor GIFs from NOAA STAR pages.

Defaults:
- Full Disk GeoColor (36 frames)
- WUS GeoColor (48 frames)

Uses ffmpeg palette workflow when available; otherwise falls back to Pillow.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import pathlib
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Iterable, List

DEFAULT_FULL_DISK = "https://www.star.nesdis.noaa.gov/goes/fulldisk_band.php?sat=G18&band=GEOCOLOR&length=36&dim=undefined"
DEFAULT_WUS = "https://www.star.nesdis.noaa.gov/goes/sector_band.php?sat=G18&sector=wus&band=GEOCOLOR&length=48&dim=undefined"

IMG_PATTERN = re.compile(r"https?://[^\"'\s>]+\.(?:jpg|jpeg|png|gif)", re.IGNORECASE)


@dataclass
class StreamConfig:
    name: str
    source_url: str
    expected_frames: int
    out_name: str


STREAMS = [
    StreamConfig("full-disk", DEFAULT_FULL_DISK, 36, "goes18-full-disk-geocolor.gif"),
    StreamConfig("wus", DEFAULT_WUS, 48, "goes18-wus-geocolor.gif"),
]


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (OpenClaw GOES GIF)"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read()


def parse_image_urls(page_url: str, html: str) -> List[str]:
    urls = set(IMG_PATTERN.findall(html))
    if not urls:
        # also detect root-relative src paths
        rels = re.findall(r"(?:src|href)=[\"']([^\"']+\.(?:jpg|jpeg|png|gif))", html, flags=re.IGNORECASE)
        for rel in rels:
            urls.add(urllib.parse.urljoin(page_url, rel))
    return sorted(urls)


def filter_goes_frames(urls: Iterable[str]) -> List[str]:
    framey = []
    for u in urls:
        low = u.lower()
        if any(k in low for k in ["/goes", "geocolor", "abi", "wus", "fd/"]):
            framey.append(u)
    if framey:
        return framey
    return list(urls)


def pick_latest(urls: List[str], n: int) -> List[str]:
    # NOAA frame names are usually sortable by timestamp in filename.
    return sorted(urls)[-n:]


def ensure_dir(path: pathlib.Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def download_frames(frame_urls: List[str], dst_dir: pathlib.Path) -> List[pathlib.Path]:
    files = []
    for i, url in enumerate(frame_urls, start=1):
        ext = pathlib.Path(urllib.parse.urlparse(url).path).suffix.lower() or ".jpg"
        out = dst_dir / f"frame-{i:04d}{ext}"
        out.write_bytes(http_get(url))
        files.append(out)
    return files


def validate_frames(files: List[pathlib.Path]) -> tuple[int, tuple[int, int] | None, int]:
    from PIL import Image

    dims = None
    invalid = 0
    for p in files:
        try:
            with Image.open(p) as im:
                size = im.size
        except Exception:
            invalid += 1
            continue
        if dims is None:
            dims = size
        elif dims != size:
            raise RuntimeError(f"Dimension mismatch: {p} has {size}, expected {dims}")
    return len(files), dims, invalid


def ffmpeg_available() -> bool:
    return subprocess.call(["bash", "-lc", "command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def render_gif_ffmpeg(frame_dir: pathlib.Path, out_gif: pathlib.Path, fps: int) -> None:
    palette = frame_dir / "palette.png"
    glob_in = str(frame_dir / "frame-%04d.jpg")
    # if jpg pattern has no matches, detect ext from first frame
    first = sorted(frame_dir.glob("frame-*"))[0]
    glob_in = str(frame_dir / f"frame-%04d{first.suffix.lower()}")

    subprocess.check_call([
        "ffmpeg", "-y", "-framerate", str(fps), "-i", glob_in,
        "-vf", "palettegen=stats_mode=diff", str(palette)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    subprocess.check_call([
        "ffmpeg", "-y", "-framerate", str(fps), "-i", glob_in,
        "-i", str(palette), "-lavfi", "paletteuse=dither=bayer:bayer_scale=3", "-loop", "0", str(out_gif)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def render_gif_pillow(frame_files: List[pathlib.Path], out_gif: pathlib.Path, fps: int) -> None:
    from PIL import Image

    frames = []
    for p in frame_files:
        with Image.open(p) as im:
            frames.append(im.convert("P", palette=Image.Palette.ADAPTIVE, colors=256))

    if not frames:
        raise RuntimeError("No frames to render")

    duration_ms = int(1000 / max(fps, 1))
    frames[0].save(
        out_gif,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
        disposal=2,
    )


def run_stream(stream: StreamConfig, run_root: pathlib.Path, fps: int, override_count: int | None = None) -> dict:
    html = http_get(stream.source_url).decode("utf-8", errors="ignore")
    image_urls = parse_image_urls(stream.source_url, html)
    frame_pool = filter_goes_frames(image_urls)

    target_count = override_count or stream.expected_frames
    chosen = pick_latest(frame_pool, target_count)
    if len(chosen) < target_count:
        print(f"warning: {stream.name} expected {target_count} frames but found {len(chosen)}", file=sys.stderr)

    stream_dir = run_root / stream.name
    ensure_dir(stream_dir)
    files = download_frames(chosen, stream_dir)
    count, dims, invalid = validate_frames(files)

    out_gif = run_root / stream.out_name
    renderer = "ffmpeg" if ffmpeg_available() else "pillow"
    if renderer == "ffmpeg":
        render_gif_ffmpeg(stream_dir, out_gif, fps)
    else:
        render_gif_pillow(files, out_gif, fps)

    duration = round(count / fps, 2) if fps else 0
    return {
        "stream": stream.name,
        "source": stream.source_url,
        "frames": count,
        "dimensions": dims,
        "invalid": invalid,
        "fps": fps,
        "duration_s": duration,
        "renderer": renderer,
        "output": str(out_gif),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build GOES-18 GeoColor GIFs from NOAA STAR pages")
    parser.add_argument(
        "--output-root",
        default=str(pathlib.Path.home() / ".openclaw" / "artifacts" / "noaa"),
        help="Base output directory",
    )
    parser.add_argument("--fps", type=int, default=8, help="GIF frame rate")
    parser.add_argument("--frames", type=int, default=None, help="Override frame count for both streams")
    parser.add_argument("--stream", choices=["full-disk", "wus", "both"], default="both", help="Which stream to render")
    args = parser.parse_args()

    now = dt.datetime.now()
    run_root = pathlib.Path(args.output_root) / now.strftime("%Y-%m-%d") / f"run-{now.strftime('%H%M')}"
    ensure_dir(run_root)

    selected = STREAMS if args.stream == "both" else [s for s in STREAMS if s.name == args.stream]

    summaries = []
    for stream in selected:
        summaries.append(run_stream(stream, run_root, args.fps, args.frames))

    print(f"Run root: {run_root}")
    for s in summaries:
        print(
            f"- {s['stream']}: {s['output']} | frames={s['frames']} | fps={s['fps']} | "
            f"duration={s['duration_s']}s | invalid={s['invalid']} | renderer={s['renderer']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
