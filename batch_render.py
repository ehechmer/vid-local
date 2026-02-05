import argparse
import os
import shutil
import tempfile
import zipfile
import subprocess

import numpy as np
import pandas as pd
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
from PIL import Image, ImageFont, ImageDraw

# --- COMPATIBILITY PATCH ---
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def get_col(df, options):
    for opt in options:
        if opt in df.columns:
            return opt
    return None


def get_duration_ffprobe(filepath):
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            filepath,
        ]
        return float(subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().strip())
    except Exception:
        return None


def find_video_path(root_dir, filename):
    direct = os.path.join(root_dir, filename)
    if os.path.exists(direct):
        return direct
    for root, _dirs, files in os.walk(root_dir):
        for f in files:
            if f == filename:
                return os.path.join(root, f)
    return direct


def get_scaled_font(text, font_path, max_size, target_width, target_height, stroke_w=0, spacing=-12):
    size = max_size
    try:
        font = ImageFont.truetype(font_path, int(size)) if font_path else ImageFont.load_default()
    except Exception:
        return ImageFont.load_default(), size

    dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    for s in range(int(max_size), 20, -2):
        test_font = ImageFont.truetype(font_path, s) if font_path else font
        bbox = dummy.textbbox(
            (0, 0),
            text,
            font=test_font,
            spacing=spacing,
            stroke_width=stroke_w,
            align="center",
        )
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        if text_w <= target_width and text_h <= target_height:
            return test_font, s
    return font, size


def draw_text_on_image(
    base_img,
    text,
    font_path,
    font_size,
    color,
    stroke,
    stroke_w,
    shadow_off,
    offset_x=0,
    offset_y=0,
):
    img = base_img.copy().convert("RGBA")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    target_w = w * 0.85
    target_h = h * 0.85
    font, _final_size = get_scaled_font(
        text,
        font_path,
        font_size,
        target_w,
        target_h,
        stroke_w=stroke_w,
        spacing=-12,
    )

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font,
        align="center",
        stroke_width=stroke_w,
        spacing=-12,
    )
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    x = ((w - text_w) / 2 - bbox[0]) + offset_x
    y = ((h - text_h) / 2 - bbox[1]) + offset_y

    if shadow_off > 0:
        draw.text(
            (x + shadow_off, y + shadow_off),
            text,
            font=font,
            fill=stroke,
            align="center",
            spacing=-12,
        )

    draw.text(
        (x, y),
        text,
        font=font,
        fill=color,
        align="center",
        stroke_width=stroke_w,
        stroke_fill=stroke,
        spacing=-12,
    )
    return img


def create_split_convergence(
    text,
    font_path,
    font_size,
    video_w,
    video_h,
    duration,
    start_time,
    text_rgb,
    stroke_rgb,
    stroke_w,
    shadow_off,
    offset_x=0,
    offset_y=0,
):
    lines = text.split("\n")
    clips = []
    target_w = video_w * 0.85
    target_h = video_h * 0.85
    font, _final_size = get_scaled_font(
        text,
        font_path,
        font_size,
        target_w,
        target_h,
        stroke_w=stroke_w,
        spacing=-12,
    )

    dummy_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    line_heights = []
    for line in lines:
        bbox = dummy_draw.textbbox((0, 0), line, font=font, stroke_width=stroke_w)
        line_heights.append((bbox[3] - bbox[1]) + 20)

    total_h = sum(line_heights)
    start_y_cursor = ((video_h / 2) - (total_h / 2)) + offset_y

    for i, line in enumerate(lines):
        dummy_img = Image.new("RGBA", (1, 1))
        draw = ImageDraw.Draw(dummy_img)
        bbox = draw.textbbox((0, 0), line, font=font, align="center", stroke_width=stroke_w)
        w, h = int((bbox[2] - bbox[0]) + 80), int((bbox[3] - bbox[1]) + 80)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        pos = (int(40 - bbox[0]), int(40 - bbox[1]))
        if shadow_off > 0:
            draw.text(
                (pos[0] + shadow_off, pos[1] + shadow_off),
                line,
                font=font,
                fill=stroke_rgb,
                align="center",
            )
        draw.text(
            pos,
            line,
            font=font,
            fill=text_rgb,
            align="center",
            stroke_width=stroke_w,
            stroke_fill=stroke_rgb,
        )

        line_clip = ImageClip(np.array(img)).set_duration(duration).set_start(start_time)

        final_y = start_y_cursor
        start_y_cursor += line_heights[i]

        final_x = ((video_w / 2) - (w / 2)) + offset_x
        start_x = -w if i % 2 == 0 else video_w

        def pos_func(t, sx=start_x, fx=final_x, fy=final_y, st=start_time):
            rel_t = t - st
            if rel_t < 0:
                return (sx, fy)
            progress = min(1, rel_t / 0.5)
            ease = 1 - (1 - progress) ** 4
            curr_x = sx + (fx - sx) * ease
            return (curr_x, fy)

        clips.append(line_clip.set_position(pos_func))
    return CompositeVideoClip(clips, size=(video_w, video_h)).set_duration(duration).set_start(start_time)


def render_video(
    row,
    videos_dir,
    font_path,
    output_path,
    col_map,
    motion_profile,
    text_rgb,
    stroke_rgb,
    size_main,
    size_small,
    stroke_w,
    shadow_off,
    pos_x,
    pos_y,
):
    filename = str(row.get(col_map["filename"])).strip()
    video_full_path = find_video_path(videos_dir, filename)

    clip = None
    try:
        clip = VideoFileClip(video_full_path)
        if not clip.duration:
            clip.duration = get_duration_ffprobe(video_full_path) or 10.0

        w, h = clip.size
        dur = clip.duration
        t1_dur, t2_start = dur * 0.25, dur * 0.25
        t2_dur, t3_start = dur * 0.55, dur * 0.80
        t3_dur = dur * 0.20

        # Intro
        txt1_img = draw_text_on_image(
            Image.new("RGBA", (w, h)),
            "LAWRENCE\nWITH JACOB JEFFRIES",
            font_path,
            size_main,
            text_rgb,
            stroke_rgb,
            stroke_w,
            shadow_off,
            pos_x,
            pos_y,
        )
        txt1 = ImageClip(np.array(txt1_img)).set_duration(t1_dur).set_position("center").crossfadeout(0.2)

        # Middle
        city = str(row.get(col_map["city"], "Unknown")).upper()
        content2 = f"{row.get('Date','')}\n{city}\n{row.get('Venue','')}".upper()
        if motion_profile == "Split Convergence":
            txt2 = create_split_convergence(
                content2,
                font_path,
                size_small,
                w,
                h,
                t2_dur,
                t2_start,
                text_rgb,
                stroke_rgb,
                stroke_w,
                shadow_off,
                pos_x,
                pos_y,
            )
        else:
            base_img = Image.new("RGBA", (w, h))
            overlay = draw_text_on_image(
                base_img,
                content2,
                font_path,
                size_small,
                text_rgb,
                stroke_rgb,
                stroke_w,
                shadow_off,
                pos_x,
                pos_y,
            )
            txt2 = ImageClip(np.array(overlay)).set_duration(t2_dur).set_position("center").set_start(t2_start).crossfadein(0.2)

        # Outro
        content3 = f"TICKETS ON SALE NOW\n{row.get('Ticket_Link','')}".upper()
        if motion_profile == "Split Convergence":
            txt3 = create_split_convergence(
                content3,
                font_path,
                size_small,
                w,
                h,
                t3_dur,
                t3_start,
                text_rgb,
                stroke_rgb,
                stroke_w,
                shadow_off,
                pos_x,
                pos_y,
            )
        else:
            overlay3 = draw_text_on_image(
                Image.new("RGBA", (w, h)),
                content3,
                font_path,
                size_small,
                text_rgb,
                stroke_rgb,
                stroke_w,
                shadow_off,
                pos_x,
                pos_y,
            )
            txt3 = ImageClip(np.array(overlay3)).set_duration(t3_dur).set_position("center").set_start(t3_start)

        final = CompositeVideoClip([clip, txt1, txt2, txt3])
        final.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            fps=24,
            preset="ultrafast",
            verbose=False,
            logger=None,
        )
        clip.close()
        return True, "Success"
    except Exception as e:
        if clip:
            clip.close()
        return False, str(e)


def main():
    parser = argparse.ArgumentParser(description="Batch render promo videos from a zip and CSV.")
    parser.add_argument("--zip", required=True, help="Path to input ZIP containing videos")
    parser.add_argument("--csv", required=True, help="Path to input CSV")
    parser.add_argument("--font", default=None, help="Path to .ttf font (optional)")
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

    df = pd.read_csv(args.csv)
    col_map = {
        "filename": get_col(df, ["Filename", "File Name", "Video", "filename"]),
        "city": get_col(df, ["City", "Location", "city"]),
    }
    if not col_map["filename"]:
        raise SystemExit("CSV missing filename column (Filename/File Name/Video/filename).")

    text_rgb = hex_to_rgb(args.text_color)
    stroke_rgb = hex_to_rgb(args.stroke_color)

    os.makedirs(args.output, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        with zipfile.ZipFile(args.zip, "r") as z:
            z.extractall(temp_dir)

        total = len(df)
        results = []
        for i, r in df.iterrows():
            c_name = str(r.get(col_map["city"], "Unknown")).replace(" ", "_")
            fname = str(r.get(col_map["filename"]))
            out_name = f"Promo_{c_name}_{fname}"
            out_path = os.path.join(args.output, out_name)
            success, msg = render_video(
                r,
                temp_dir,
                args.font,
                out_path,
                col_map,
                args.motion,
                text_rgb,
                stroke_rgb,
                args.title_size,
                args.body_size,
                args.stroke_width,
                args.shadow,
                args.offset_x,
                args.offset_y,
            )
            results.append(f"{i+1}/{total} {c_name}: {'OK' if success else 'FAIL ' + msg}")

        for line in results:
            print(line)


if __name__ == "__main__":
    main()
