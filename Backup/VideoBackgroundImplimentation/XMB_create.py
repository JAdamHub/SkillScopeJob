import random
import math
from PIL import Image, ImageDraw
import numpy as np
from moviepy.editor import ImageSequenceClip
import base64
import os

# --- Videoindstillinger ---
WIDTH, HEIGHT = 1920, 1080
FPS = 25
DURATION_SECONDS = 10
OUTPUT_MP4_FILENAME = "temp_ps3_xmb_background_offwhite.mp4" # Navn for klarhed
BASE64_TARGET_FILENAME = "background_beige_base64.txt" # Beholder dette, da Streamlit forventer det

# --- Farveindstillinger ---
# Baggrundsfarve: #eee9e0  (RGB: 238, 233, 224)
BACKGROUND_COLOR_TUPLE = (238, 233, 224)
BACKGROUND_COLOR_RGBA = BACKGROUND_COLOR_TUPLE + (255,)

# Partikelfarve: Skal have kontrast til den lyse baggrund
# PARTICLE_BASE_COLOR = (100, 100, 100) # Mellemgrå (stadig en mulighed)
PARTICLE_BASE_COLOR = (140, 130, 120) # En mørkere, dæmpet grålig beige/brun
# Alternativt en renere grå:
# PARTICLE_BASE_COLOR = (120, 120, 120)


# --- Partikelindstillinger ---
NUM_PARTICLES = 300
PARTICLE_MIN_SIZE = 1
PARTICLE_MAX_SIZE = 4
PARTICLE_MIN_SPEED_X = 0.3
PARTICLE_MAX_SPEED_X = 1.5
PARTICLE_MIN_SPEED_Y = 0.1
PARTICLE_MAX_SPEED_Y = 0.6
PARTICLE_ALPHA_MIN = 70 # Lidt højere alpha for synlighed mod lys baggrund,
PARTICLE_ALPHA_MAX = 170 # men stadig dæmpet pga. Streamlits opacity

# --- Bølgeeffekt i baggrunden ---
ANIMATE_BACKGROUND_WAVE = True # Kan være slået til med denne baggrundsfarve
WAVE_SPEED = 0.2
WAVE_AMPLITUDE = 10 # Subtil amplitude. Farven vil variere ca. +/- 10 fra base.
                    # f.eks. R vil gå fra ~228 til ~248 (tæt på hvid)
WAVE_FREQUENCY = 1.5 # Brede bølger

particles = []

def initialize_particles():
    global particles
    particles = []
    for _ in range(NUM_PARTICLES):
        particles.append({
            'x': random.uniform(0, WIDTH),
            'y': random.uniform(0, HEIGHT),
            'size': random.randint(PARTICLE_MIN_SIZE, PARTICLE_MAX_SIZE),
            'speed_x': random.uniform(PARTICLE_MIN_SPEED_X, PARTICLE_MAX_SPEED_X) * random.choice([-1, 1]),
            'speed_y': random.uniform(PARTICLE_MIN_SPEED_Y, PARTICLE_MAX_SPEED_Y) * random.choice([-1, 1]),
            'alpha': random.randint(PARTICLE_ALPHA_MIN, PARTICLE_ALPHA_MAX)
        })

def update_and_draw_frame(frame_index):
    img = Image.new('RGBA', (WIDTH, HEIGHT), BACKGROUND_COLOR_RGBA)
    draw = ImageDraw.Draw(img)

    if ANIMATE_BACKGROUND_WAVE:
        base_r, base_g, base_b = BACKGROUND_COLOR_TUPLE
        for y_scan in range(HEIGHT):
            phase = (frame_index / FPS) * WAVE_SPEED * 2 * math.pi
            norm_y_wave = (y_scan / HEIGHT) * WAVE_FREQUENCY * 2 * math.pi
            s = math.sin(norm_y_wave + phase) # -1 til 1
            
            # Varier alle RGB kanaler med samme offset for en lysstyrkeændring
            # s * WAVE_AMPLITUDE vil give en værdi mellem -WAVE_AMPLITUDE og +WAVE_AMPLITUDE
            r_offset = s * WAVE_AMPLITUDE
            g_offset = s * WAVE_AMPLITUDE # Kan bruge samme offset for en ren lysstyrkeændring
            b_offset = s * WAVE_AMPLITUDE # Eller differentiere lidt som før for subtil farvetone
            # g_offset = s * WAVE_AMPLITUDE * 0.98 # Meget lidt variation
            # b_offset = s * WAVE_AMPLITUDE * 0.95

            r_wave = int(base_r + r_offset)
            g_wave = int(base_g + g_offset)
            b_wave = int(base_b + b_offset)
            
            line_color = (
                max(0, min(255, r_wave)),
                max(0, min(255, g_wave)),
                max(0, min(255, b_wave)),
                255
            )
            draw.line([(0, y_scan), (WIDTH, y_scan)], fill=line_color)

    # Tegn partikler
    for p in particles:
        p['x'] += p['speed_x']
        p['y'] += p['speed_y']
        if p['x'] > WIDTH + p['size']: p['x'] = -p['size']
        if p['x'] < -p['size']: p['x'] = WIDTH + p['size']
        if p['y'] > HEIGHT + p['size']: p['y'] = -p['size']
        if p['y'] < -p['size']: p['y'] = HEIGHT + p['size']

        particle_color_with_alpha = PARTICLE_BASE_COLOR + (p['alpha'],)
        x0, y0 = int(p['x'] - p['size'] / 2), int(p['y'] - p['size'] / 2)
        x1, y1 = int(p['x'] + p['size'] / 2), int(p['y'] + p['size'] / 2)
        draw.ellipse((x0, y0, x1, y1), fill=particle_color_with_alpha)

    return np.array(img)

def generate_video_mp4():
    print("Initialiserer partikler...")
    initialize_particles()
    print(f"Genererer frames til {OUTPUT_MP4_FILENAME} (Baggrund #eee9e0, 1920x1080)...")
    frames = []
    num_total_frames = int(FPS * DURATION_SECONDS)
    for i in range(num_total_frames):
        if (i + 1) % FPS == 0:
             print(f"  Frame {i+1}/{num_total_frames} ({(i+1)/FPS:.0f}s ud af {DURATION_SECONDS}s)")
        frame_data = update_and_draw_frame(i)
        frames.append(frame_data)
    print("Skaber MP4 videoklip...")
    video_clip = ImageSequenceClip(frames, fps=FPS)
    print(f"Skriver video til {OUTPUT_MP4_FILENAME}...")
    try:
        video_clip.write_videofile(
            OUTPUT_MP4_FILENAME, codec="libx264", fps=FPS, preset="medium", threads=4, logger='bar'
        )
        print(f"MP4 video '{OUTPUT_MP4_FILENAME}' genereret!")
        return True
    except Exception as e:
        print(f"FEJL under skrivning af MP4 video: {e}")
        return False
    finally:
        video_clip.close()

def mp4_to_base64_and_save(video_filepath, base64_filepath):
    try:
        with open(video_filepath, "rb") as video_file:
            video_bytes = video_file.read()
        base64_encoded_video = base64.b64encode(video_bytes).decode('utf-8')
        with open(base64_filepath, "w", encoding='utf-8') as f:
            f.write(base64_encoded_video)
        print(f"Base64-kodet video gemt i '{base64_filepath}'")
        print(f"Længde af Base64 streng: {len(base64_encoded_video)} tegn.")
        return True
    except FileNotFoundError:
        print(f"Fejl: Videofilen {video_filepath} blev ikke fundet.")
        return False
    except Exception as e:
        print(f"Fejl under base64 konvertering eller skrivning: {e}")
        return False

if __name__ == "__main__":
    if generate_video_mp4():
        print(f"\nKonverterer '{OUTPUT_MP4_FILENAME}' til Base64 og gemmer som '{BASE64_TARGET_FILENAME}'...")
        if mp4_to_base64_and_save(OUTPUT_MP4_FILENAME, BASE64_TARGET_FILENAME):
            print(f"\nFærdig! '{BASE64_TARGET_FILENAME}' er klar til brug i din Streamlit app.")
            try:
                os.remove(OUTPUT_MP4_FILENAME)
                print(f"Midlertidig fil '{OUTPUT_MP4_FILENAME}' slettet.")
            except OSError as e:
                print(f"Fejl under sletning af midlertidig fil '{OUTPUT_MP4_FILENAME}': {e}")
        else:
            print(f"Kunne ikke gemme base64 streng til '{BASE64_TARGET_FILENAME}'.")
    else:
        print("Videogenerering fejlede. Base64-konvertering springes over.")