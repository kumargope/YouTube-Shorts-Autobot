import os
import json
import random
import asyncio
import requests
import numpy as np
from PIL import Image
from dotenv import load_dotenv
from groq import Groq
import edge_tts

# MoviePy 2.0 Imports
from moviepy import VideoClip, AudioFileClip, CompositeAudioClip, concatenate_videoclips
import moviepy.video.fx as vfx

# YouTube Data API Imports
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv()
GROQ_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_KEY:
    raise ValueError("⚠️ Error: .env फ़ाइल में GROQ_API_KEY नहीं मिला!")

groq_client = Groq(api_key=GROQ_KEY)
BGM_FILE = "bgm.mp3"
HISTORY_FILE = "used_topics.txt"

# Vibrant, Colorful & Whimsical Themes (No Dark/Horror)
COLORFUL_GENRES = [
    "A magical glowing rainbow floating island above sunset clouds",
    "A cozy colorful candy village filled with friendly spirit creatures",
    "A vibrant glowing undersea coral reef with magical light pathways",
    "A breathtaking golden hour cherry blossom valley with a floating train",
    "A bright cyberpunk futuristic neon city with magical glowing rain",
    "An enchanting crystal glass castle reflecting sunset colors in the sky"
]

# 0. History Tracker
def load_used_topics():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_used_topic(topic):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(topic + "\n")

# 1. High-Hook Script Generator (Colorful & Whimsical Visuals)
def generate_viral_ghibli_story():
    used_topics = load_used_topics()
    selected_genre = random.choice(COLORFUL_GENRES)
    seed_id = random.randint(1000, 9999)
    print(f"🧠 [1/5] Generating Vibrant Story | Theme: '{selected_genre}' [{seed_id}]...")
    
    prompt = f"""
    Act as a Master Storyteller for YouTube Shorts & Reels.
    Create a 100% UNIQUE, highly engaging, magical Studio Ghibli style short story based on: '{selected_genre}'.
    
    STRICT VISUAL & STORY RULES:
    1. SCENE 1 HOOK: The first sentence MUST be an amazing, curious, or mind-blowing hook to catch user attention in 2 seconds.
    2. SCENES: Divide story into EXACTLY 5 to 6 fast-paced sequential scenes.
    3. COLORFUL VISUALS ONLY: STRICTLY NO DARK, DULL, OR HORROR THEMES. Visual prompts MUST describe bright lighting, vibrant colors, sunset, golden hour, neon glow, or fairytale aesthetics.
    4. STYLE: Every prompt MUST include 'Studio Ghibli style, Hayao Miyazaki aesthetic, colorful, vibrant lighting, highly detailed 8k anime art'.

    Return ONLY a valid JSON object:
    {{
      "title": "Catchy Hindi Title with Hashtags",
      "description": "YouTube Shorts Description",
      "scenes": [
        {{
          "narration": "मनमोहक और रोचक पहला डायलॉग...",
          "visual_prompt": "Studio Ghibli style, Hayao Miyazaki aesthetic, bright vibrant colors, glowing golden sunset..."
        }},
        {{
          "narration": "कहानी का अगला जादुई हिस्सा...",
          "visual_prompt": "Studio Ghibli style, Hayao Miyazaki aesthetic, colorful magical scenery..."
        }}
      ]
    }}
    """
    
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.95,
        response_format={"type": "json_object"}
    )
    
    data = json.loads(response.choices[0].message.content)
    save_used_topic(data.get("title", f"Ghibli Story #{seed_id}"))
    return data

# 2. Fast Voice Generator (+12% Speed)
async def generate_scene_audio_async(text, output_file):
    communicate = edge_tts.Communicate(text, "hi-IN-SwaraNeural", rate="+12%")
    await communicate.save(output_file)

def generate_scene_audio(text, index):
    filename = f"audio_scene_{index}.mp3"
    asyncio.run(generate_scene_audio_async(text, filename))
    return filename

# 3. Pollinations AI Bright Visuals Generator
def fetch_ghibli_scene_image(prompt_text, index):
    print(f"🎨 Generating Vibrant Visual for Scene {index+1}...")
    full_prompt = f"{prompt_text}, masterpiece, 8k resolution, vibrant rich colors, cinematic lighting"
    encoded_prompt = requests.utils.quote(full_prompt)
    seed = random.randint(100000, 999999)
    
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&model=flux&nologo=true&seed={seed}"
    filename = f"image_scene_{index}.jpg"
    
    res = requests.get(url)
    if res.status_code == 200:
        with open(filename, "wb") as f:
            f.write(res.content)
        return filename
    return None

# 4. Camera Motion Effects
def make_ghibli_motion_frame(image_path, t, duration, motion_type="fast_zoom_in", target_w=1080, target_h=1920):
    img = Image.open(image_path).convert("RGB")
    orig_w, orig_h = img.size
    progress = t / duration if duration > 0 else 0
    
    if motion_type == "fast_zoom_in":
        zoom = 1.0 + (0.20 * progress)
        pan_x, pan_y = np.sin(t * 2.0) * 10, np.cos(t * 1.5) * 6
    elif motion_type == "zoom_out":
        zoom = 1.20 - (0.16 * progress)
        pan_x, pan_y = np.cos(t * 1.5) * 8, np.sin(t * 1.2) * 5
    else:
        zoom = 1.12
        pan_x = (progress - 0.5) * 40
        pan_y = np.sin(t * 2.0) * 6

    crop_w, crop_h = orig_w / zoom, orig_h / zoom
    left = (orig_w - crop_w) / 2 + pan_x
    top = (orig_h - crop_h) / 2 + pan_y
    
    cropped = img.crop((left, top, left + crop_w, top + crop_h))
    return np.array(cropped.resize((target_w, target_h), Image.Resampling.LANCZOS))

# 5. Video Assembly with Single BGM Support
def assemble_exact_synced_video(scenes_data, output_path="final_synced_ghibli.mp4"):
    print("\n⚙️ Assembling Colorful High-Retention Video...")
    
    scene_clips = []
    motions = ["fast_zoom_in", "zoom_out", "pan_right"]
    
    for i, scene in enumerate(scenes_data):
        print(f"\n🎬 Processing Scene {i+1}/{len(scenes_data)}...")
        
        audio_file = generate_scene_audio(scene['narration'], i)
        audio_clip = AudioFileClip(audio_file)
        duration = audio_clip.duration
        
        img_file = fetch_ghibli_scene_image(scene['visual_prompt'], i)
        
        if not img_file or not os.path.exists(img_file):
            print(f"⚠️ Failed scene {i+1}, skipping...")
            continue
            
        motion_style = motions[i % len(motions)]
        
        def make_frame(t, path=img_file, dur=duration, m_style=motion_style):
            return make_ghibli_motion_frame(path, t, dur, motion_type=m_style)
            
        clip = VideoClip(make_frame, duration=duration)
        clip = clip.with_audio(audio_clip)
        scene_clips.append(clip)
        
    print("\n🎞️ Stitching scenes together...")
    full_video = concatenate_videoclips(scene_clips, method="compose")
    
    # Simple Single bgm.mp3 Integration
    if os.path.exists(BGM_FILE):
        print("🎵 Mixing single 'bgm.mp3' in background...")
        bgm_clip = AudioFileClip(BGM_FILE)
        if bgm_clip.duration < full_video.duration:
            bgm_clip = bgm_clip.with_effects([vfx.Loop(duration=full_video.duration)])
        else:
            bgm_clip = bgm_clip.subclipped(0, full_video.duration)
            
        bgm_clip = bgm_clip.with_volume_scaled(0.08)  # Soft Volume
        combined_audio = CompositeAudioClip([full_video.audio, bgm_clip])
        full_video = full_video.with_audio(combined_audio)
    else:
        print("⚠️ 'bgm.mp3' not found, proceeding with narration voice only.")
        
    print(f"📥 Exporting Final Video ({full_video.duration:.1f}s)...")
    full_video.write_videofile(
        output_path, 
        fps=24, 
        codec="libx264", 
        audio_codec="aac",
        preset="fast",
        pixel_format="yuv420p"
    )
    print(f"\n🎉 SUCCESS! Video Ready: {os.path.abspath(output_path)}")
    return output_path

# 6. YouTube Auto-Upload Feature
def upload_to_youtube(video_path, title, description):
    print("\n📤 [5/5] Auto-Uploading to YouTube Shorts...")
    
    if not os.path.exists("client_secret.json") and not os.path.exists("token.json"):
        print("⚠️ Credentials missing ('client_secret.json' / 'token.json'). Skipping YouTube Upload.")
        return

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    creds = None
    
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    elif os.path.exists("client_secret.json"):
        flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
        creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    youtube = build("youtube", "v3", credentials=creds)

    body = {
        'snippet': {
            'title': title[:100],
            'description': f"{description}\n\n#Shorts #Ghibli #Anime #Animation #ViralShorts",
            'tags': ['Shorts', 'Ghibli', 'AnimeStory', 'Animation', 'ViralShorts'],
            'categoryId': '1'
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False
        }
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    
    response = request.execute()
    print(f"🎉 SUCCESS! Video Uploaded to YouTube. Video ID: {response.get('id')}")

if __name__ == "__main__":
    story_data = generate_viral_ghibli_story()
    print(f"🎯 Title: {story_data['title']}\n")
    
    video_file = assemble_exact_synced_video(story_data['scenes'])
    
    try:
        upload_to_youtube(video_file, story_data['title'], story_data['description'])
    except Exception as e:
        print(f"⚠️ YouTube Auto-Upload Skipped/Failed: {e}")