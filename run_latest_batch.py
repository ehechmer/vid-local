import argparse
import os
import subprocess
import sys
import zipfile
from pathlib import Path


def find_latest(path, patterns):
    candidates = []
    for pattern in patterns:
        candidates.extend(Path(path).glob(pattern))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def zip_has_video(zip_path):
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            for name in z.namelist():
                lower = name.lower()
                if lower.endswith((".mp4", ".mov", ".m4v")):
                    return True
    except Exception:
        return False
    return False


def find_latest_video_zip(path):
    zips = list(Path(path).glob("*.zip")) + list(Path(path).glob("*.ZIP"))
    zips = [p for p in zips if zip_has_video(p)]
    if not zips:
        return None
    return max(zips, key=lambda p: p.stat().st_mtime)


def main():
    parser = argparse.ArgumentParser(description="Find newest ZIP/CSV/TTF in a folder and run batch_render.py.")
    parser.add_argument("--dir", default="~/Downloads", help="Directory to search (default: ~/Downloads)")
    parser.add_argument("--output", default="output", help="Output directory")
    parser.add_argument("--motion", default="Static", help="Motion profile (default: Static)")
    parser.add_argument("--text-color", default="#FFFFFF", help="Text color hex (default: #FFFFFF)")
    parser.add_argument("--stroke-color", default="#000000", help="Stroke color hex (default: #000000)")
    parser.add_argument("--title-size", type=int, default=150, help="Title size (default: 150)")
    parser.add_argument("--body-size", type=int, default=120, help="Body size (default: 120)")
    parser.add_argument("--stroke-width", type=int, default=4, help="Stroke width (default: 4)")
    parser.add_argument("--shadow", type=int, default=4, help="Shadow offset (default: 4)")
    parser.add_argument("--offset-x", type=int, default=0, help="Horizontal offset (default: 0)")
    parser.add_argument("--offset-y", type=int, default=0, help="Vertical offset (default: 0)")
    args = parser.parse_args()

    search_dir = os.path.expanduser(args.dir)
    if not os.path.isdir(search_dir):
        raise SystemExit(f"Directory not found: {search_dir}")

    zip_path = find_latest_video_zip(search_dir) or find_latest(search_dir, ["*.zip", "*.ZIP"])
    csv_path = find_latest(search_dir, ["*.csv", "*.CSV"])
    font_path = find_latest(search_dir, ["*.ttf", "*.TTF"])

    if not zip_path or not csv_path:
        raise SystemExit("Could not find a ZIP and CSV in the search directory.")

    cmd = [
        sys.executable,
        "batch_render.py",
        "--zip",
        str(zip_path),
        "--csv",
        str(csv_path),
        "--output",
        args.output,
        "--motion",
        args.motion,
        "--text-color",
        args.text_color,
        "--stroke-color",
        args.stroke_color,
        "--title-size",
        str(args.title_size),
        "--body-size",
        str(args.body_size),
        "--stroke-width",
        str(args.stroke_width),
        "--shadow",
        str(args.shadow),
        "--offset-x",
        str(args.offset_x),
        "--offset-y",
        str(args.offset_y),
    ]
    if font_path:
        cmd += ["--font", str(font_path)]

    print(f"Using ZIP: {zip_path}")
    print(f"Using CSV: {csv_path}")
    print(f"Using Font: {font_path if font_path else 'None'}")
    print(f"Output: {args.output}")
    print("Running batch render...")
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
