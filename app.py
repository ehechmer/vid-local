def render_video(row, videos_dir, font_path, output_path):
    filename = row.get('Filename', None)
    video_full_path = os.path.join(videos_dir, str(filename))

    if not filename or not os.path.exists(video_full_path):
        return None

    city_name = str(row.get('City', 'Unknown')).upper()
    clip = VideoFileClip(video_full_path)
    w, h = clip.size
    duration = clip.duration
    scale = 1.0 if (w / h) < 0.7 else 0.75

    # Timing Segments
    t1_end = duration * 0.20
    t2_end = duration * 0.85

    # LAYER 1: Band Name
    txt1 = create_pil_text_clip("LAWRENCE\nWITH JACOB JEFFRIES", font_path, int(80 * scale), 'white')
    txt1 = txt1.set_position(('center', 'center')).set_start(0).set_duration(t1_end).crossfadeout(0.3)

    # LAYER 2: Date & City (Slide Up Animation)
    content2 = f"{row.get('Date', '')}\n{city_name}\n{row.get('Venue', '')}".upper()
    txt2 = create_pil_text_clip(content2, font_path, int(70 * scale), 'white')
    
    # --- TWEAK SPEED HERE ---
    # Change '0.5' to '0.2' for a faster snap, or '1.0' for a slow drift.
    # Change '50' to '100' to make the text travel a further distance upward.
    slide_speed = 0.5 
    travel_distance = 50 
    
    txt2 = txt2.set_position(lambda t: ('center', (h/2 + travel_distance) - (min(1, t/slide_speed) * travel_distance)))
    txt2 = txt2.set_start(t1_end).set_duration(t2_end - t1_end).crossfadein(0.3)

    # LAYER 3: Link
    content3 = f"TICKETS ON SALE NOW\n{row.get('Ticket_Link', '')}".upper()
    txt3 = create_pil_text_clip(content3, font_path, int(70 * scale), 'white')
    txt3 = txt3.set_position(('center', 'center')).set_start(t2_end).set_duration(duration - t2_end).crossfadein(0.2)

    final = CompositeVideoClip([clip, txt1, txt2, txt3])
    final.write_videofile(output_path, codec='libx264', audio_codec='aac', fps=24, verbose=False, logger=None, preset='ultrafast')
    clip.close()
    return output_path
