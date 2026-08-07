import os
import json
import random
import asyncio
import requests
from dotenv import load_dotenv
from groq import Groq
import edge_tts

# MoviePy 2.0 Imports
from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip, concatenate_videoclips
import moviepy.video.fx as vfx

# YouTube Data API Imports
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Load Environment Variables
load_dotenv()
GROQ_KEY = os.getenv("GROQ_API_KEY")
PEXELS_KEY = os.getenv("PEXELS_API_KEY")

if not GROQ_KEY or not PEXELS_KEY:
    raise ValueError("⚠️ Error: .env फ़ाइल में GROQ_API_KEY या PEXELS_API_KEY नहीं मिला!")

groq_client = Groq(api_key=GROQ_KEY)

HISTORY_FILE = "used_topics.txt"
BGM_FILE = "bgm.mp3"  # Background Music File Path

# 1. Used Topics Checker & History Saver
def load_used_topics():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_used_topic(topic):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(topic + "\n")

# 2. Dynamic Auto-Trending Topic Generator
def fetch_daily_trending_topic():
    used_topics = load_used_topics()
    print("🔎 Searching for TODAY'S Fresh Trending Topic...")

    prompt = f"""
    Act as a YouTube Shorts Trend Analyzer. 
    Generate 5 fresh, viral, funny, and highly engaging story ideas/topics that are currently popular on YouTube Shorts & Instagram Reels.
    
    Return ONLY a valid JSON object:
    {{
      "topics": [
        "Topic idea 1",
        "Topic idea 2",
        "Topic idea 3",
        "Topic idea 4",
        "Topic idea 5"
      ]
    }}
    """
    
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=1.0,
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        candidates = data.get("topics", [])
        
        for topic in candidates:
            if topic not in used_topics:
                save_used_topic(topic)
                return topic

    except Exception as e:
        print(f"⚠️ Trend Search Warning: {e}")
        
    fallback_topic = f"Funny viral moment of a mischievous character #{random.randint(100, 999)}"
    save_used_topic(fallback_topic)
    return fallback_topic

print("🚀 Starting 1-Minute Dynamic Trending Shorts Pipeline with Background Music...\n")

# 3. Groq AI: Full 1-Minute Script Generator
def generate_story_and_prompts(topic):
    print(f"🧠 [1/5] Generating FULL 1-MINUTE Script for Trending Topic: '{topic}'...")
    
    prompt = f"""
    Write a detailed, exciting, humorous, and full-length story script for a 1-MINUTE YouTube Short based on this topic:
    Topic: '{topic}'
    
    STRICT SCRIPT RULES:
    1. WORD COUNT: MUST BE AT LEAST 160 TO 180 WORDS LONG in natural spoken Hindi.
    2. DURATION: Must fill around 55 to 60 seconds when spoken out loud.
    3. Include character names, funny dialogue, suspenseful story build-up, and a climax/twist.

    Return ONLY a valid JSON object:
    {{
      "title": "Catchy YouTube Shorts Title in Hindi with hashtags",
      "description": "Short description for YouTube.",
      "script": "Full Hindi narration script (160-180 words)",
      "keywords": ["array of EXACTLY 12 visual English keywords for Pexels stock video clips"]
    }}
    """
    
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.85,
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

# 4. Edge-TTS: Voice Generator
async def generate_voice_async(script, output_audio="voice.mp3"):
    print("🎙️ [2/5] Generating Hindi Voice Over...")
    communicate = edge_tts.Communicate(script, "hi-IN-MadhurNeural", rate="-8%")
    await communicate.save(output_audio)
    return output_audio

def generate_voice(script):
    asyncio.run(generate_voice_async(script))
    return "voice.mp3"

# 5. Pexels API Downloader
def download_pexels_clip(query, index):
    print(f"🎬 [3/5] Downloading Scene {index+1}/12 for keyword '{query}'...")
    
    headers = {"Authorization": PEXELS_KEY}
    url = f"https://api.pexels.com/videos/search?query={query}&orientation=portrait&per_page=10"
    
    response = requests.get(url, headers=headers).json()
    
    if response.get('videos') and len(response['videos']) > 0:
        chosen_video = random.choice(response['videos'][:5])
        video_files = chosen_video['video_files']
        video_url = next((f['link'] for f in video_files if f.get('height', 0) > f.get('width', 0)), video_files[0]['link'])
    else:
        fallback_url = "https://api.pexels.com/videos/search?query=lifehacks&orientation=portrait&per_page=5"
        res = requests.get(fallback_url, headers=headers).json()
        video_url = random.choice(res['videos'])['video_files'][0]['link']
        
    filename = f"clip_{index}.mp4"
    video_bytes = requests.get(video_url).content
    with open(filename, "wb") as f:
        f.write(video_bytes)
        
    print(f"✅ Downloaded Scene {index+1}: {filename}")
    return filename

# 6. Assembly & MoviePy Edit
def assemble_final_short(clip_files, audio_file, output_path="final_cartoon_short.mp4"):
    print("\n⚙️ [4/5] Editing & Assembling Full Video with Background Music...")
    
    voice_audio = AudioFileClip(audio_file)
    target_duration = voice_audio.duration
    print(f"📏 Generated Voiceover Duration: {target_duration:.2f} seconds")
    
    # Background Music Handling
    if os.path.exists(BGM_FILE):
        print("🎵 Mixing Background Music (Soft Volume)...")
        bgm_clip = AudioFileClip(BGM_FILE)
        
        # Loop or trim BGM to match video length
        if bgm_clip.duration < target_duration:
            bgm_clip = bgm_clip.with_effects([vfx.Loop(duration=target_duration)])
        else:
            bgm_clip = bgm_clip.subclipped(0, target_duration)
            
        # MoviePy 2.0 Correct Volume Scaling
        bgm_clip = bgm_clip.with_volume_scaled(0.12)
        
        # Combine Voiceover + BGM
        final_audio = CompositeAudioClip([voice_audio, bgm_clip])
    else:
        print("⚠️ Warning: 'bgm.mp3' file not found. Proceeding with voiceover only.")
        final_audio = voice_audio

    clip_duration = target_duration / len(clip_files)
    loaded_clips = [VideoFileClip(f) for f in clip_files]
    edited_clips = []
    
    for clip in loaded_clips:
        if clip.duration < clip_duration:
            sub_clip = clip.with_effects([vfx.Loop(duration=clip_duration)])
        else:
            sub_clip = clip.subclipped(0, clip_duration)
            
        sub_clip = sub_clip.resized(height=1280)
        if sub_clip.w > 720:
            sub_clip = sub_clip.cropped(x_center=sub_clip.w / 2, width=720)
            
        edited_clips.append(sub_clip)
    
    full_video = concatenate_videoclips(edited_clips, method="compose")
    
    if full_video.duration > target_duration:
        full_video = full_video.subclipped(0, target_duration)
        
    final_video = full_video.with_audio(final_audio)
    
    print(f"📥 Exporting Final {final_video.duration:.1f}s HD Short Video...")
    final_video.write_videofile(
        output_path, 
        fps=30, 
        codec="libx264", 
        audio_codec="aac",
        preset="fast"
    )
    
    # Safely close handles
    voice_audio.close()
    if os.path.exists(BGM_FILE):
        bgm_clip.close()
    final_audio.close()
    final_video.close()
    full_video.close()
    for c in loaded_clips:
        c.close()
    for c in edited_clips:
        c.close()
        
    return output_path

# 7. YouTube Auto-Upload
def upload_to_youtube(video_path, title, description):
    print("\n📤 [5/5] Auto-Uploading to YouTube Shorts...")
    
    if not os.path.exists("client_secret.json"):
        raise FileNotFoundError("'client_secret.json' फ़ाइल नहीं मिली।")

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    creds = None
    
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
        creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    youtube = build("youtube", "v3", credentials=creds)

    body = {
        'snippet': {
            'title': title[:100],
            'description': description,
            'tags': ['Shorts', 'Trending', 'FunnyStory', 'ViralShorts'],
            'categoryId': '23'
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

# Execution Block
if __name__ == "__main__":
    topic = fetch_daily_trending_topic()
    print(f"🎯 Selected Trending Topic for Today: '{topic}'\n")
    
    data = generate_story_and_prompts(topic)
    audio_file = generate_voice(data['script'])
    
    video_clips = []
    keywords = data.get('keywords', [])
    while len(keywords) < 12:
        keywords.append("lifehacks")
        
    for i, keyword in enumerate(keywords[:12]):
        clip_path = download_pexels_clip(keyword, i)
        video_clips.append(clip_path)
        
    final_video_path = assemble_final_short(video_clips, audio_file)
    
    try:
        upload_to_youtube(final_video_path, data['title'], data['description'])
    except Exception as e:
        print(f"\n✅ Final 1-Minute Trending Video with BGM saved at: {final_video_path}")
        print(f"⚠️ YouTube Auto-Upload Skipped/Failed: {e}")