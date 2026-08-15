import os
import json
import random
import asyncio
import math
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from groq import Groq
import edge_tts

from moviepy import (
    VideoFileClip,
    AudioFileClip,
    ImageClip,
    CompositeAudioClip,
    CompositeVideoClip,
    concatenate_videoclips,
    concatenate_audioclips,
)
import moviepy.video.fx as vfx

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


# ============================================================
# CONFIG
# ============================================================

load_dotenv()

GROQ_KEY = os.getenv("GROQ_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

if not GROQ_KEY:
    raise ValueError("GROQ_API_KEY missing.")

if not PEXELS_API_KEY:
    raise ValueError("PEXELS_API_KEY missing.")

groq_client = Groq(api_key=GROQ_KEY)

OUTPUT_DIR = Path("output")
CLIPS_DIR = OUTPUT_DIR / "clips"
AUDIO_DIR = OUTPUT_DIR / "audio"
CAPTION_DIR = OUTPUT_DIR / "captions"
THUMBNAIL_DIR = OUTPUT_DIR / "thumbnails"
SFX_DIR = Path("sfx")

for folder in (
    OUTPUT_DIR,
    CLIPS_DIR,
    AUDIO_DIR,
    CAPTION_DIR,
    THUMBNAIL_DIR,
    SFX_DIR,
):
    folder.mkdir(parents=True, exist_ok=True)

BGM_FILE = Path("bgm.mp3")
WHOOSH_FILE = SFX_DIR / "whoosh.mp3"
IMPACT_FILE = SFX_DIR / "impact.mp3"
HEARTBEAT_FILE = SFX_DIR / "heartbeat.mp3"
HIT_FILE = SFX_DIR / "hit.mp3"

TOKEN_FILE = Path("token.json")

# GitHub Actions secret names supported by this script.
# Recommended: YOUTUBE_TOKEN_JSON
# Also supported: TOKEN_JSON
GITHUB_TOKEN_SECRET_NAMES = ("YOUTUBE_TOKEN_JSON", "TOKEN_JSON")
CLIENT_SECRET_FILE = Path("client_secret.json")

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30

VOICE = "hi-IN-MadhurNeural"
VOICE_RATE = "+16%"
VOICE_PITCH = "-2Hz"

YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube.upload"

# YouTube / Shorts limits
MAX_SHORT_DURATION = 35.0
YOUTUBE_UPLOAD_CHUNK_SIZE = 8 * 1024 * 1024
YOUTUBE_UPLOAD_MAX_RETRIES = 6



# ============================================================
# INDIA-ONLY MYSTERY TOPICS
# ============================================================

MYSTERY_TOPICS = [
    "Bhangarh Fort Rajasthan mystery",
    "Kuldhara abandoned village Rajasthan mystery",
    "Roopkund skeleton lake Uttarakhand mystery",
    "Konark Sun Temple Odisha mystery",
    "Meenakshi Temple Madurai hidden history",
    "Ellora Caves Maharashtra unexplained mystery",
    "Ajanta Caves Maharashtra hidden history",
    "Golconda Fort Hyderabad secret tunnels",
    "Daulatabad Fort Maharashtra secret history",
    "Lepakshi Temple Andhra Pradesh mystery",
    "Padmanabhaswamy Temple Kerala hidden history",
    "Jagannath Temple Puri unexplained mystery",
    "Brihadeeswarar Temple Tamil Nadu mystery",
    "Rani ki Vav Gujarat hidden history",
    "Lothal Gujarat ancient civilization mystery",
    "Dholavira Gujarat ancient city mystery",
    "Mohenjo-daro Indian civilization mystery",
    "Nalanda Bihar ancient university mystery",
    "Vikramshila Bihar ancient university mystery",
    "Sanchi Stupa Madhya Pradesh hidden history",
    "Khajuraho Madhya Pradesh hidden history",
    "Hampi Karnataka lost city mystery",
    "Vijayanagara Empire mystery",
    "Shani Shingnapur Maharashtra mystery",
    "Shiv Temple India ancient architecture mystery",
    "Kailasa Temple Ellora construction mystery",
    "Iron Pillar Delhi rust mystery",
    "Delhi Sultanate forgotten history",
    "Red Fort Delhi hidden history",
    "Qutub Minar Delhi hidden history",
    "Agrasen ki Baoli Delhi mystery",
    "Jaisalmer Fort Rajasthan hidden history",
    "Kumbhalgarh Fort Rajasthan secret history",
    "Mehrangarh Fort Rajasthan mystery",
    "Chittorgarh Fort Rajasthan hidden history",
    "Amer Fort Jaipur secret passage mystery",
    "Bhangarh village folklore mystery",
    "Indian freedom movement unsolved mystery",
    "Subhas Chandra Bose historical mystery",
    "Lal Bahadur Shastri historical mystery",
    "Indian ancient manuscript mystery",
    "Indian archaeological discovery mystery",
    "Indian temple underground tunnel mystery",
    "Indian lost city historical mystery",
    "Indian shipwreck historical mystery",
    "Indian haunted fort folklore mystery",
    "Indian cave civilization mystery",
    "Indian ancient engineering mystery",
    "Indian astronomy ancient history mystery",
    "Indian stepwell hidden history",
    "Indian railway historical mystery",
    "Indian historical artifact mystery",
]


# ============================================================
# INDIA-ONLY VALIDATION
# ============================================================

FORBIDDEN_FOREIGN_TERMS = [
    "bermuda",
    "dyatlov",
    "roanoke",
    "mary celeste",
    "tutankhamun",
    "egypt",
    "egyptian",
    "nazca",
    "antikythera",
    "voynich",
    "oak island",
    "atlantis",
    "stonehenge",
    "jack the ripper",
    "amelia earhart",
    "d.b. cooper",
    "pompeii",
    "roman empire",
    "viking",
    "europe",
    "america",
    "new york",
    "london",
    "paris",
    "japan",
    "china",
    "greece",
    "mesopotamia",
]

INDIA_TERMS = [
    "india",
    "indian",
    "भारत",
    "भारतीय",
    "rajasthan",
    "delhi",
    "uttarakhand",
    "odisha",
    "karnataka",
    "kerala",
    "tamil nadu",
    "tamil",
    "andhra",
    "telangana",
    "maharashtra",
    "gujarat",
    "bihar",
    "madhya pradesh",
    "west bengal",
    "punjab",
    "assam",
    "goa",
    "hampi",
    "varanasi",
    "jaipur",
    "agra",
    "hyderabad",
    "mumbai",
    "kolkata",
    "chennai",
    "puri",
    "konark",
]


def ensure_india_query(query):
    query = str(query or "").strip()
    lowered = query.lower()

    if any(term in lowered for term in FORBIDDEN_FOREIGN_TERMS):
        raise ValueError(f"Non-Indian visual query rejected: {query}")

    if not any(term in lowered for term in INDIA_TERMS):
        query = f"India {query}"

    return query


def validate_indian_story(data):
    combined = " ".join(
        str(data.get(key, ""))
        for key in ("topic", "title", "description", "hook")
    ).lower()

    if any(term in combined for term in FORBIDDEN_FOREIGN_TERMS):
        raise ValueError(
            "Generated story contains a non-Indian topic."
        )

    if not any(term in combined for term in INDIA_TERMS):
        raise ValueError(
            "Generated story does not clearly identify India."
        )

    scenes = data.get("scenes", [])

    if len(scenes) != 7:
        raise ValueError(
            f"Expected exactly 7 scenes, got {len(scenes)}"
        )

    for scene in scenes:
        scene["pexels_query"] = ensure_india_query(
            scene.get("pexels_query", "")
        )

    return data


# ============================================================
# STORY GENERATOR
# ============================================================

def generate_mystery_story():
    topic = random.choice(MYSTERY_TOPICS)

    print("\n" + "=" * 75)
    print("🧠 GENERATING HIGH-RETENTION MYSTERY SHORT")
    print("🎯 Topic:", topic)
    print("=" * 75)

    prompt = f"""
You are a professional Hindi YouTube Shorts writer for an INDIA-ONLY channel.

TOPIC:
{topic}

Create ONE factual, highly engaging Hindi YouTube Short about India.

TARGET:
20-32 seconds.
Create exactly 7 visual scenes.

FACTUAL RULE:
Only established information may be presented as fact.
For uncertain claims use:
"एक सिद्धांत के अनुसार..."
"कुछ इतिहासकार मानते हैं..."
"लोककथाओं के अनुसार..."
"आज तक इसका निश्चित जवाब नहीं मिला..."
"इस दावे की स्वतंत्र पुष्टि नहीं हुई है..."

Never invent dates, people, discoveries, scientific claims, quotes or evidence.
Separate folklore from documented history.

RETENTION — CRITICAL:
0-3 SEC = EXTREMELY STRONG HOOK. This is the most important part.
Scene 1 MUST start at 0 seconds and end at 3 seconds.
Scene 1 narration MUST be EXACTLY the same as the "hook" field.
The hook must be short enough to finish naturally within about 3 seconds.
Keep the hook around 8-14 Hindi words.
The hook must create an immediate curiosity gap and preferably mention a concrete Indian place, person, object, or discovery.

Strong hook examples:
"भारत के इस किले का सबसे बड़ा राज़ क्या है?"
"इस भारतीय मंदिर को बनाया कैसे गया?"
"इस झील में मिले कंकालों का राज़ क्या है?"
"राजस्थान की इस जगह पर रात में लोग क्यों नहीं जाते?"

NEVER begin the hook with:
"आज हम बात करेंगे..."
"क्या आप जानते हैं..."
"नमस्कार दोस्तों..."
"दोस्तों आज की वीडियो में..."

2-6 sec = mystery setup.
6-18 sec = clue chain.
18-27 sec = strongest documented revelation.
Final seconds = unanswered question.

Every pexels_query MUST target India or an Indian location.
Never request foreign visuals.

Captions must be maximum 4 words.

Return ONLY valid JSON:

{{
  "topic": "...",
  "title": "... #Shorts",
  "description": "...",
  "hook": "...",
  "scenes": [
    {{
      "scene_number": 1,
      "start_time": 0,
      "end_time": 3,
      "narration": "...",
      "pexels_query": "...",
      "caption": "...",
      "sfx": "impact"
    }}
  ]
}}

The final scene MUST ask a question that encourages comments.
"""

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a factual, high-retention Hindi "
                    "Indian dark-history YouTube Shorts writer."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.82,
        response_format={"type": "json_object"},
    )

    data = json.loads(
        response.choices[0].message.content
    )

    data = validate_indian_story(data)

    # HARD RULE: scene 1 is always the 0-3 second hook.
    hook = str(data.get("hook", "")).strip()

    if not hook:
        raise RuntimeError("AI did not return a valid hook.")

    if not data.get("scenes"):
        raise RuntimeError("AI did not return scenes.")

    data["scenes"][0]["start_time"] = 0
    data["scenes"][0]["end_time"] = 3
    data["scenes"][0]["narration"] = hook
    data["scenes"][0]["caption"] = (
        data["scenes"][0].get("caption") or "राज़ क्या है?"
    )
    data["scenes"][0]["sfx"] = (
        data["scenes"][0].get("sfx") or "impact"
    )

    print("\n🔥 0-3 SEC STRONG HOOK:")
    print(hook)

    print("\n🎬 TITLE:")
    print(data.get("title", "Untitled"))

    print("\n🎯 HOOK:")
    print(data.get("hook", ""))

    return data


# ============================================================
# PEXELS SEARCH
# ============================================================

def search_pexels_video(query):
    query = ensure_india_query(query)

    print(f"\n🔎 PEXELS SEARCH: {query}")

    url = "https://api.pexels.com/videos/search"

    headers = {
        "Authorization": PEXELS_API_KEY,
        "User-Agent": "Mozilla/5.0",
    }

    params = {
        "query": query,
        "per_page": 20,
        "orientation": "portrait",
        "size": "large",
    }

    for attempt in range(1, 4):
        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=(20, 45),
            )

            if response.status_code != 200:
                print(
                    f"❌ Pexels error {response.status_code}"
                )
                return None

            data = response.json()
            videos = data.get("videos", [])

            if not videos:
                print(
                    "⚠️ No portrait footage. Trying landscape..."
                )

                params["orientation"] = "landscape"

                response = requests.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=(20, 45),
                )

                if response.status_code != 200:
                    return None

                videos = response.json().get(
                    "videos",
                    []
                )

            if not videos:
                return None

            candidates = []

            for video in videos:
                for file in video.get("video_files", []):
                    width = file.get("width") or 0
                    height = file.get("height") or 0
                    link = file.get("link")

                    if not link:
                        continue

                    if width >= 720 or height >= 720:
                        candidates.append(
                            {
                                "url": link,
                                "width": width,
                                "height": height,
                                "duration": video.get(
                                    "duration",
                                    0,
                                ),
                            }
                        )

            if not candidates:
                return None

            vertical = [
                x for x in candidates
                if x["height"] > x["width"]
            ]

            if vertical:
                candidates = vertical

            candidates.sort(
                key=lambda x: (
                    x["width"] * x["height"]
                ),
                reverse=True,
            )

            selected = random.choice(
                candidates[:min(8, len(candidates))]
            )

            print(
                "✅ Selected:",
                selected["width"],
                "x",
                selected["height"],
            )

            return selected

        except Exception as e:
            print(
                f"⚠️ Pexels attempt {attempt}/3 failed:",
                e,
            )

            if attempt < 3:
                time.sleep(3 * attempt)

    print("❌ Pexels search failed after retries.")
    return None


# ============================================================
# DOWNLOAD VIDEO WITH RETRIES
# ============================================================

def download_video(url, filename):
    path = CLIPS_DIR / filename

    print(f"⬇️ Downloading {filename}")

    for attempt in range(1, 4):
        try:
            print(
                f"   Download attempt {attempt}/3"
            )

            with requests.get(
                url,
                stream=True,
                timeout=(20, 180),
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 "
                        "(Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 "
                        "Chrome/151 Safari/537.36"
                    )
                },
            ) as response:

                response.raise_for_status()

                with open(path, "wb") as file:
                    for chunk in response.iter_content(
                        chunk_size=1024 * 1024
                    ):
                        if chunk:
                            file.write(chunk)

            if path.exists() and path.stat().st_size > 10000:
                print("✅ Saved:", path)
                return str(path)

        except Exception as e:
            print(
                f"⚠️ Download attempt {attempt} failed:",
                e,
            )

            if attempt < 3:
                time.sleep(3 * attempt)

    print(
        f"❌ Could not download {filename}"
    )
    return None


def get_scene_video(scene_number, query):
    result = search_pexels_video(query)

    if not result:
        print(
            f"⚠️ Scene {scene_number}: No suitable footage."
        )
        return None

    return download_video(
        result["url"],
        f"scene_{scene_number}.mp4",
    )


# ============================================================
# VOICE
# ============================================================

async def create_voice(text, output_file):
    communicate = edge_tts.Communicate(
        text=text,
        voice=VOICE,
        rate=VOICE_RATE,
        pitch=VOICE_PITCH,
    )
    await communicate.save(output_file)


def generate_voice(text, scene_number):
    filename = (
        AUDIO_DIR /
        f"voice_{scene_number}.mp3"
    )

    print(
        f"🎙️ Generating Hindi voice scene {scene_number}"
    )

    asyncio.run(
        create_voice(
            text,
            str(filename),
        )
    )

    return str(filename)


# ============================================================
# FONT
# ============================================================

def find_font():
    fonts = [
        "C:/Windows/Fonts/NirmalaB.ttf",
        "C:/Windows/Fonts/mangal.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansDevanagari-Bold.ttf",
        "/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]

    for font in fonts:
        if os.path.exists(font):
            return font

    return None


# ============================================================
# CAPTIONS
# ============================================================

def create_caption_image(
    text,
    filename,
    emphasis=False,
):
    image = Image.new(
        "RGBA",
        (VIDEO_WIDTH, 360),
        (0, 0, 0, 0),
    )

    draw = ImageDraw.Draw(image)
    font_path = find_font()

    if font_path:
        font = ImageFont.truetype(
            font_path,
            78 if emphasis else 68,
        )
    else:
        font = ImageFont.load_default()

    words = str(text).split()
    lines = []
    current = ""

    for word in words:
        test = f"{current} {word}".strip()

        if len(test) > 22:
            if current:
                lines.append(current)
            current = word
        else:
            current = test

    if current:
        lines.append(current)

    lines = lines[:2]
    y = 180 - (len(lines) * 90) // 2

    for line in lines:
        bbox = draw.textbbox(
            (0, 0),
            line,
            font=font,
        )

        text_width = bbox[2] - bbox[0]
        x = (VIDEO_WIDTH - text_width) // 2

        draw.text(
            (x + 5, y + 5),
            line,
            font=font,
            fill="black",
            stroke_width=12,
            stroke_fill="black",
        )

        draw.text(
            (x, y),
            line,
            font=font,
            fill="white",
            stroke_width=5,
            stroke_fill="black",
        )

        y += 90

    image.save(filename)
    return filename


# ============================================================
# VIDEO FORMAT
# ============================================================

def prepare_clip_for_shorts(clip):
    width = clip.w
    height = clip.h

    target_ratio = VIDEO_WIDTH / VIDEO_HEIGHT
    current_ratio = width / height

    if current_ratio > target_ratio:
        new_width = int(height * target_ratio)
        x1 = (width - new_width) // 2

        clip = clip.cropped(
            x1=x1,
            x2=x1 + new_width,
        )

    else:
        new_height = int(width / target_ratio)
        y1 = (height - new_height) // 2

        clip = clip.cropped(
            y1=y1,
            y2=y1 + new_height,
        )

    return clip.resized(
        width=VIDEO_WIDTH,
        height=VIDEO_HEIGHT,
    )


def create_rapid_segments(video, target_duration):
    if video.duration <= 0:
        return []

    segments = []

    segment_count = max(
        2,
        math.ceil(target_duration / 2.5),
    )

    segment_duration = (
        target_duration / segment_count
    )

    for i in range(segment_count):
        if video.duration <= segment_duration:
            start = 0
        else:
            available = (
                video.duration -
                segment_duration
            )

            start = (
                available *
                i /
                max(1, segment_count - 1)
            )

        end = min(
            start + segment_duration,
            video.duration,
        )

        if end <= start:
            continue

        piece = video.subclipped(
            start,
            end,
        )

        piece = prepare_clip_for_shorts(
            piece
        )

        try:
            if i % 3 == 0:
                piece = piece.with_effects(
                    [vfx.CrossFadeIn(0.08)]
                )
        except Exception:
            pass

        segments.append(piece)

    return segments


# ============================================================
# AUDIO
# ============================================================

def load_sfx(effect_name):
    mapping = {
        "whoosh": WHOOSH_FILE,
        "impact": IMPACT_FILE,
        "heartbeat": HEARTBEAT_FILE,
        "hit": HIT_FILE,
    }

    file_path = mapping.get(effect_name)

    if not file_path or not file_path.exists():
        return None

    return str(file_path)


def make_looped_audio(audio, duration):
    if audio.duration >= duration:
        return audio.subclipped(0, duration)

    pieces = []
    remaining = duration

    while remaining > 0:
        part_duration = min(
            audio.duration,
            remaining,
        )

        pieces.append(
            audio.subclipped(
                0,
                part_duration,
            )
        )

        remaining -= part_duration

    return concatenate_audioclips(pieces)


# ============================================================
# BUILD SCENE
# ============================================================

def build_scene(
    video_path,
    audio_path,
    caption,
    scene_number,
    sfx_name=None,
):
    print(
        f"\n🎬 Building scene {scene_number}"
    )

    narration_audio = AudioFileClip(
        audio_path
    )

    duration = narration_audio.duration

    source_video = VideoFileClip(
        video_path
    )

    if source_video.duration < duration:
        loops = (
            int(
                duration /
                max(
                    source_video.duration,
                    0.1,
                )
            ) + 1
        )

        video = concatenate_videoclips(
            [source_video] * loops,
            method="compose",
        )
    else:
        video = source_video

    video = video.subclipped(
        0,
        min(
            duration,
            video.duration,
        ),
    )

    rapid_segments = create_rapid_segments(
        video,
        duration,
    )

    if rapid_segments:
        video = concatenate_videoclips(
            rapid_segments,
            method="compose",
        )

        video = video.subclipped(
            0,
            min(
                duration,
                video.duration,
            ),
        )
    else:
        video = prepare_clip_for_shorts(
            video
        )

    caption_file = (
        CAPTION_DIR /
        f"caption_{scene_number}.png"
    )

    create_caption_image(
        caption,
        str(caption_file),
        emphasis=(scene_number == 1),
    )

    caption_image = (
        Image.open(
            caption_file
        ).convert("RGBA")
    )

    caption_array = __import__(
        "numpy"
    ).array(caption_image)

    caption_clip = (
        ImageClip(caption_array)
        .with_duration(duration)
        .with_position(("center", "center"))
    )

    audio_layers = [narration_audio]

    sfx_file = load_sfx(sfx_name)

    if sfx_file:
        try:
            sfx = AudioFileClip(sfx_file)
            sfx = sfx.with_volume_scaled(0.28)

            if sfx.duration > 0.9:
                sfx = sfx.subclipped(
                    0,
                    min(0.9, sfx.duration),
                )

            sfx = sfx.with_start(0.02)
            audio_layers.append(sfx)

        except Exception as e:
            print("⚠️ SFX skipped:", e)

    combined_audio = CompositeAudioClip(
        audio_layers
    )

    final_scene = CompositeVideoClip(
        [video, caption_clip],
        size=(VIDEO_WIDTH, VIDEO_HEIGHT),
    )

    return final_scene.with_audio(
        combined_audio
    )


# ============================================================
# BGM
# ============================================================

def add_background_music(final_video):
    if not BGM_FILE.exists():
        print("⚠️ bgm.mp3 not found.")
        return final_video

    print("🎵 Adding suspense BGM...")

    bgm = AudioFileClip(
        str(BGM_FILE)
    )

    bgm = make_looped_audio(
        bgm,
        final_video.duration,
    )

    bgm = bgm.with_volume_scaled(0.045)

    if final_video.audio:
        audio = CompositeAudioClip(
            [
                final_video.audio,
                bgm,
            ]
        )
    else:
        audio = bgm

    return final_video.with_audio(audio)


# ============================================================
# THUMBNAIL
# ============================================================

def create_thumbnail(video_path, title):
    print("\n🖼️ Creating thumbnail...")

    video = VideoFileClip(video_path)

    frame_time = min(
        1.5,
        max(
            0,
            video.duration - 0.1,
        ),
    )

    frame = video.get_frame(frame_time)

    image = (
        Image.fromarray(frame)
        .convert("RGB")
        .resize((1280, 720))
        .filter(ImageFilter.SHARPEN)
    )

    draw = ImageDraw.Draw(image)
    font_path = find_font()

    if font_path:
        font = ImageFont.truetype(
            font_path,
            72,
        )
    else:
        font = ImageFont.load_default()

    words = str(title).split()

    if len(words) > 6:
        words = words[:6]

    thumbnail_text = " ".join(words)

    bbox = draw.textbbox(
        (0, 0),
        thumbnail_text,
        font=font,
    )

    text_width = bbox[2] - bbox[0]
    x = (1280 - text_width) // 2
    y = 530
    padding = 22

    draw.rounded_rectangle(
        (
            x - padding,
            y - padding,
            x + text_width + padding,
            y + 100,
        ),
        radius=20,
        fill=(0, 0, 0, 190),
    )

    draw.text(
        (x, y),
        thumbnail_text,
        font=font,
        fill="white",
        stroke_width=7,
        stroke_fill="black",
    )

    output = (
        THUMBNAIL_DIR /
        "mystery_thumbnail.jpg"
    )

    image.save(
        output,
        quality=95,
    )

    video.close()

    print("✅ Thumbnail:", output)

    return str(output)


# ============================================================
# ASSEMBLE FULL SHORT
# ============================================================

def assemble_video(story):
    print("\n" + "=" * 75)
    print("🎞️ BUILDING HIGH-RETENTION SHORT")
    print("=" * 75)

    scene_clips = []

    for scene in story["scenes"]:
        number = scene["scene_number"]
        query = scene["pexels_query"]
        narration = scene["narration"]
        caption = scene.get("caption", "")
        sfx = scene.get("sfx")

        print(f"\n🎥 SCENE {number}")

        if number == 1:
            print("🔥 0-3 SEC STRONG HOOK")
        print("Visual:", query)
        print("Narration:", narration)

        video_file = get_scene_video(
            number,
            query,
        )

        if not video_file:
            print(
                f"⚠️ Scene {number} could not be downloaded."
            )
            continue

        try:
            audio_file = generate_voice(
                narration,
                number,
            )

            clip = build_scene(
                video_file,
                audio_file,
                caption,
                number,
                sfx,
            )

            scene_clips.append(clip)

        except Exception as e:
            print(
                f"⚠️ Scene {number} build failed:",
                e,
            )

    if not scene_clips:
        raise RuntimeError(
            "❌ No video scenes available."
        )

    print("\n🔗 Joining all scenes...")

    final_video = concatenate_videoclips(
        scene_clips,
        method="compose",
    )

    final_video = add_background_music(
        final_video
    )

    # --------------------------------------------------------
    # HARD MAXIMUM: keep the final video inside Shorts target.
    # Voice clips can make the assembled video longer than the
    # AI-generated scene timestamps, so enforce the limit here.
    # --------------------------------------------------------

    if final_video.duration > MAX_SHORT_DURATION:
        print(
            f"\n✂️ Final video is {final_video.duration:.2f}s. "
            f"Trimming to {MAX_SHORT_DURATION:.0f}s..."
        )

        final_video = final_video.subclipped(
            0,
            MAX_SHORT_DURATION,
        )

    output = (
        OUTPUT_DIR /
        "mystery_short.mp4"
    )

    print("\n📤 Exporting:", output)

    final_video.write_videofile(
        str(output),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        bitrate="8M",
        pixel_format="yuv420p",
        threads=4,
    )

    duration = final_video.duration

    final_video.close()

    for clip in scene_clips:
        try:
            clip.close()
        except Exception:
            pass

    print("\n🎉 VIDEO CREATED")
    print(
        "⏱️ Duration:",
        round(duration, 2),
        "seconds",
    )
    print("📁", output)

    return str(output)


# ============================================================
# YOUTUBE AUTHENTICATION
#
# IMPORTANT:
# LOCAL:
#   token.json + browser OAuth
#
# GITHUB ACTIONS:
#   YOUTUBE_TOKEN_JSON secret
#   NO browser
# ============================================================

def get_youtube_service():

    """
    YouTube OAuth loader.

    LOCAL:
        Reads ./client_secret.json and ./token.json

    GITHUB ACTIONS:
        The workflow creates ./client_secret.json from the
        CLIENT_SECRET_JSON GitHub Secret and ./token.json from
        YOUTUBE_TOKEN_JSON / TOKEN_JSON.

    IMPORTANT:
        CLIENT_SECRET_JSON must contain the COMPLETE Google
        OAuth client JSON, not only the client_secret string.
    """

    scopes = [
        "https://www.googleapis.com/auth/youtube.upload"
    ]

    credentials = None

    # --------------------------------------------------------
    # 1. Load existing token.json
    # --------------------------------------------------------

    if os.path.exists(TOKEN_FILE):

        print("🔐 Loading YouTube token.json...")

        try:
            credentials = Credentials.from_authorized_user_file(
                TOKEN_FILE,
                scopes,
            )
        except Exception as e:
            print("⚠️ token.json could not be loaded:", e)
            credentials = None

    # --------------------------------------------------------
    # 2. Refresh expired token automatically
    # --------------------------------------------------------

    if credentials is not None and credentials.expired:

        if credentials.refresh_token:

            print("🔄 Refreshing YouTube access token...")

            try:
                from google.auth.transport.requests import Request

                credentials.refresh(Request())

                with open(
                    TOKEN_FILE,
                    "w",
                    encoding="utf-8",
                ) as token:

                    token.write(
                        credentials.to_json()
                    )

                print("✅ YouTube token refreshed.")

            except Exception as e:

                print(
                    "⚠️ Token refresh failed:",
                    e,
                )

                credentials = None

    # --------------------------------------------------------
    # 3. If valid credentials exist, use them.
    # --------------------------------------------------------

    if credentials is not None and credentials.valid:

        print("✅ YouTube OAuth token is valid.")

        return build(
            "youtube",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )

    # --------------------------------------------------------
    # 4. GitHub/local client_secret.json check
    # --------------------------------------------------------

    if not os.path.exists(CLIENT_SECRET_FILE):

        raise RuntimeError(
            "\n"
            "❌ client_secret.json missing.\n\n"
            "For GitHub Actions, create a GitHub Secret named:\n"
            "CLIENT_SECRET_JSON\n\n"
            "The Secret must contain the COMPLETE contents of\n"
            "Google's client_secret.json file.\n\n"
            "The GitHub workflow will automatically create:\n"
            "./client_secret.json\n"
            "before this Python script runs.\n"
        )

    # --------------------------------------------------------
    # 5. Local first-time OAuth
    # --------------------------------------------------------

    print("🔑 Starting YouTube OAuth...")

    flow = InstalledAppFlow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes,
    )

    # GitHub Actions usually has no browser.
    # Never attempt local browser OAuth in CI.
    if os.getenv("GITHUB_ACTIONS", "").lower() == "true":

        raise RuntimeError(
            "\n"
            "❌ YouTube token.json is missing or expired in GitHub Actions.\n\n"
            "GitHub cannot perform the first browser OAuth login.\n"
            "Run the script locally once, complete Google OAuth,\n"
            "then put the resulting token.json contents into the\n"
            "GitHub Secret named YOUTUBE_TOKEN_JSON.\n"
        )

    credentials = flow.run_local_server(
        port=0,
        open_browser=True,
    )

    with open(
        TOKEN_FILE,
        "w",
        encoding="utf-8",
    ) as token:

        token.write(
            credentials.to_json()
        )

    print("✅ YouTube token.json created.")

    return build(
        "youtube",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )


# ============================================================
# YOUTUBE UPLOAD
# ============================================================

def _is_retryable_youtube_error(error):
    """Return True for temporary/network errors worth retrying."""

    text = str(error).lower()

    retry_terms = [
        "10053",
        "10054",
        "10060",
        "connection aborted",
        "connection reset",
        "connection broken",
        "remote end closed",
        "timed out",
        "timeout",
        "temporarily unavailable",
        "service unavailable",
        "internal error",
        "backend error",
        "rate limit",
        "too many requests",
        "503",
        "502",
        "500",
        "504",
    ]

    if any(term in text for term in retry_terms):
        return True

    if isinstance(error, HttpError):
        try:
            status = int(error.resp.status)
            return status in {408, 429, 500, 502, 503, 504}
        except Exception:
            return False

    return False


def _upload_video_resumable(youtube, video_path, body):
    """Upload a video using Google's resumable upload API with retries."""

    media = MediaFileUpload(
        str(video_path),
        chunksize=YOUTUBE_UPLOAD_CHUNK_SIZE,
        resumable=True,
        mimetype="video/mp4",
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    print(
        "📦 Upload mode: resumable chunks of "
        f"{YOUTUBE_UPLOAD_CHUNK_SIZE // (1024 * 1024)} MB"
    )

    response = None
    last_error = None

    while response is None:
        try:
            status, response = request.next_chunk()

            if status is not None:
                try:
                    progress = int(status.progress() * 100)
                    print(
                        f"📤 YouTube upload progress: {progress}%",
                        flush=True,
                    )
                except Exception:
                    pass

            if response is not None:
                break

        except Exception as error:
            last_error = error

            if not _is_retryable_youtube_error(error):
                raise

            # Google resumable requests keep the resumable upload URI in
            # the request object. Calling next_chunk() again allows the
            # library to continue the same resumable upload instead of
            # starting a new normal upload request.
            print(
                "⚠️ Temporary YouTube upload/network error:"
            )
            print(error)

            recovered = False

            for retry in range(1, YOUTUBE_UPLOAD_MAX_RETRIES + 1):
                delay = min(60, 2 ** retry)

                print(
                    f"🔄 Upload retry {retry}/"
                    f"{YOUTUBE_UPLOAD_MAX_RETRIES} "
                    f"in {delay}s..."
                )

                time.sleep(delay)

                try:
                    status, response = request.next_chunk()

                    if status is not None:
                        try:
                            progress = int(status.progress() * 100)
                            print(
                                f"📤 YouTube upload progress: {progress}%",
                                flush=True,
                            )
                        except Exception:
                            pass

                    recovered = True
                    break

                except Exception as retry_error:
                    last_error = retry_error
                    print(
                        f"⚠️ Retry {retry} failed:",
                        retry_error,
                    )

                    if not _is_retryable_youtube_error(
                        retry_error
                    ):
                        raise

            if not recovered:
                raise RuntimeError(
                    "YouTube resumable upload failed after "
                    f"{YOUTUBE_UPLOAD_MAX_RETRIES} retries. "
                    f"Last error: {last_error}"
                ) from last_error

    if not response or not response.get("id"):
        raise RuntimeError(
            "YouTube upload finished without a video ID."
        )

    return response["id"]


def _upload_thumbnail_with_retry(youtube, video_id, thumbnail_path):
    """Upload the custom thumbnail with a few network retries."""

    if not thumbnail_path or not os.path.exists(thumbnail_path):
        return

    print("🖼️ Uploading custom thumbnail...")

    last_error = None

    for attempt in range(1, 4):
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(
                    str(thumbnail_path),
                    mimetype="image/jpeg",
                ),
            ).execute()

            print("✅ Thumbnail uploaded.")
            return

        except Exception as error:
            last_error = error
            print(
                f"⚠️ Thumbnail attempt {attempt}/3 failed:",
                error,
            )

            if attempt < 3 and _is_retryable_youtube_error(error):
                time.sleep(2 * attempt)
            else:
                break

    print(
        "⚠️ Thumbnail upload failed after retries:",
        last_error,
    )


def upload_to_youtube(
    video_path,
    title,
    description,
    thumbnail_path=None,
):
    print("\n📤 UPLOADING TO YOUTUBE...")

    youtube = get_youtube_service()

    final_title = str(
        title or "Indian Mystery Short #Shorts"
    )[:100]

    final_description = (
        str(description or "")
        + "\n\n"
        + "#Shorts #IndianMystery #IndianHistory #IndiaFacts"
    )

    body = {
        "snippet": {
            "title": final_title,
            "description": final_description,
            "tags": [
                "Shorts",
                "Indian Mystery",
                "Indian History",
                "India Facts",
                "Indian Facts",
                "Dark History India",
                "Unsolved Indian Mystery",
                "Hindi Facts",
                "Hindi Mystery",
                "Indian Archaeology",
                "Ancient India",
                "Indian History Facts",
            ],
            "categoryId": "27",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    file_size_mb = (
        os.path.getsize(video_path) / (1024 * 1024)
        if os.path.exists(video_path)
        else 0
    )

    print(
        f"🎬 Video size: {file_size_mb:.2f} MB"
    )

    video_id = _upload_video_resumable(
        youtube,
        video_path,
        body,
    )

    print("\n🎉 YOUTUBE UPLOAD SUCCESS")
    print("🆔 Video ID:", video_id)
    print(
        "🔗 https://www.youtube.com/watch?v="
        + video_id
    )

    _upload_thumbnail_with_retry(
        youtube,
        video_id,
        thumbnail_path,
    )

    return video_id


# ============================================================
# CLEANUP
# ============================================================

def cleanup_old_scene_files():
    print(
        "\n🧹 Cleaning old temporary files..."
    )

    for folder in (
        CLIPS_DIR,
        AUDIO_DIR,
        CAPTION_DIR,
    ):
        if not folder.exists():
            continue

        for item in folder.iterdir():
            try:
                if item.is_file():
                    item.unlink()
            except Exception:
                pass


# ============================================================
# MAIN
# ============================================================

def main():
    print("\n")
    print("=" * 75)
    print(
        "🇮🇳 INDIA-ONLY DARK HISTORY & MYSTERY SHORTS AUTOBOT"
    )
    print("=" * 75)
    print("🎙️ Male Hindi Voice:", VOICE)
    print("⚡ Voice Speed:", VOICE_RATE)
    print("🔥 Hook:", "FORCED INTO SCENE 1 / 0-3 SEC")
    print("🎬 Format:", "1080x1920")
    print("📱 Shorts:", "9:16")
    print("✂️ Rapid Cuts:", "Enabled")
    print("💥 SFX:", "Enabled when files exist")
    print("📝 Captions:", "Enabled")
    print("🖼️ Thumbnail:", "Enabled")
    print("▶️ YouTube Upload:", "Enabled")
    print(
        "🇮🇳 Niche:",
        "INDIA ONLY — Indian Facts / History / Mysteries",
    )
    print("=" * 75)

    cleanup_old_scene_files()

    story = generate_mystery_story()

    print("\n📜 GENERATED STORY:")
    print(
        json.dumps(
            story,
            ensure_ascii=False,
            indent=2,
        )
    )

    video_path = assemble_video(story)

    thumbnail = create_thumbnail(
        video_path,
        story.get("title", "Mystery"),
    )

    try:
        upload_to_youtube(
            video_path,
            story.get(
                "title",
                "Mystery Short #Shorts",
            ),
            story.get(
                "description",
                "",
            ),
            thumbnail,
        )

    except Exception as e:
        print(
            "\n⚠️ YouTube upload skipped/failed:"
        )
        print(e)

    print("\n" + "=" * 75)
    print("🎉 COMPLETE")
    print("=" * 75)
    print(
        "🎬 Video:",
        os.path.abspath(video_path),
    )
    print(
        "🖼️ Thumbnail:",
        os.path.abspath(thumbnail),
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    try:
        main()

    except Exception as e:
        print("\n" + "=" * 75)
        print("❌ FATAL ERROR")
        print("=" * 75)
        print(e)
        raise
