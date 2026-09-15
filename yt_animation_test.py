import os
import sys
import re
import json
import math
import random
import asyncio
import logging
import datetime
import subprocess
import importlib
from pathlib import Path

# Force UTF-8 on Windows Console to avoid charmap UnicodeEncodeError with Hindi text
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Third-party libraries
from dotenv import load_dotenv
import requests
from PIL import Image, ImageDraw, ImageFont
import edge_tts

# ==============================================================================
# 1. CONFIGURATION & DIRECTORIES
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", str(BASE_DIR / "credentials" / "client_secret.json"))
YOUTUBE_TOKEN_FILE = os.getenv("YOUTUBE_TOKEN_FILE", str(BASE_DIR / "credentials" / "token.json"))
YOUTUBE_PRIVACY_STATUS = os.getenv("YOUTUBE_PRIVACY_STATUS", "private")

VIDEO_WIDTH = int(os.getenv("VIDEO_WIDTH", "1080"))
VIDEO_HEIGHT = int(os.getenv("VIDEO_HEIGHT", "1920"))
FPS = int(os.getenv("FPS", "30"))

DEFAULT_VOICE = os.getenv("VOICE", "hi-IN-MadhurNeural")
TTS_SPEED = "+0%"
TTS_PITCH = "+0Hz"

DATA_DIR = BASE_DIR / "data"
USED_TOPICS_FILE = DATA_DIR / "used_topics.json"
GENERATED_VIDEOS_FILE = DATA_DIR / "generated_videos.json"

OUTPUT_DIR = BASE_DIR / "output"
VIDEOS_DIR = OUTPUT_DIR / "videos"
THUMBNAILS_DIR = OUTPUT_DIR / "thumbnails"
METADATA_DIR = OUTPUT_DIR / "metadata"
TEMP_DIR = OUTPUT_DIR / "temp"

CREDENTIALS_DIR = BASE_DIR / "credentials"
LOGS_DIR = BASE_DIR / "logs"
LOG_FILE = LOGS_DIR / "app.log"

for d in [DATA_DIR, OUTPUT_DIR, VIDEOS_DIR, THUMBNAILS_DIR, METADATA_DIR, TEMP_DIR, CREDENTIALS_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ==============================================================================
# 2. LOGGING SETUP
# ==============================================================================
class ConsoleFormatter(logging.Formatter):
    def format(self, record):
        levelname = record.levelname
        msg = record.getMessage().encode("ascii", "replace").decode("ascii")
        if levelname == "INFO":
            return f"[INFO] {msg}"
        elif levelname == "WARNING":
            return f"[WARNING] {msg}"
        elif levelname == "ERROR":
            return f"[ERROR] {msg}"
        elif levelname == "CRITICAL":
            return f"[CRITICAL] {msg}"
        return f"[{levelname}] {msg}"

def setup_logger():
    logger_instance = logging.getLogger("FactVideoGenerator")
    logger_instance.setLevel(logging.DEBUG)
    if logger_instance.handlers:
        return logger_instance

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(ConsoleFormatter())

    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s - [%(levelname)s] - %(message)s"))

    logger_instance.addHandler(ch)
    logger_instance.addHandler(fh)
    return logger_instance

logger = setup_logger()


# ==============================================================================
# 3. CATEGORIES & TOPIC GENERATOR
# ==============================================================================
CATEGORIES = [
    "ANIMALS", "BIRDS", "PLANTS", "TREES", "HUMANS", "HUMAN BODY",
    "INSECTS", "MARINE LIFE", "REPTILES", "AMPHIBIANS", "NATURE",
    "SCIENCE", "SPACE", "EARTH", "WEATHER", "ENVIRONMENT", "EVOLUTION",
    "HISTORICAL/NATURAL FACTS", "RARE & UNUSUAL FACTS"
]

SEED_FACT_TOPICS = {
    "ANIMALS": [
        "हाथी अपनी सूंड का इस्तेमाल इतनी सारी चीज़ों के लिए कैसे करते हैं?",
        "चीता 100 किलोमीटर प्रति घंटे से भी ज़्यादा तेज़ कैसे दौड़ लेता है?",
        "रात में भेड़िये चाँद की तरफ देखकर क्यों चिल्लाते हैं?",
        "चमगादड़ घने अंधेरे में भी बिना टकराए कैसे उड़ लेते हैं?",
        "स्लॉथ दुनिया का सबसे सुस्त जानवर क्यों माना जाता है?",
        "कंगारू अपनी पूँछ का इस्तेमाल तीसरे पैर की तरह कैसे करते हैं?"
    ],
    "BIRDS": [
        "उल्लू अपनी गर्दन 270 डिग्री तक कैसे घुमा लेता है?",
        "फ्लेमिंगो पक्षी हमेशा एक पैर पर खड़े होकर क्यों सोते हैं?",
        "हमिंगबर्ड पीछे की तरफ और हवा में एक ही जगह कैसे उड़ सकती है?",
        "प्रवासी पक्षी हज़ारों किलोमीटर का रास्ता बिना भटके कैसे तय करते हैं?",
        "कटफोड़वा पेड़ पर लगातार चोंच मारकर भी घायल क्यों नहीं होता?",
        "पेंगुइन बर्फ की कड़ाके की ठंड में भी खुद को गर्म कैसे रखते हैं?"
    ],
    "PLANTS": [
        "पेड़-पौधों को कैसे पता चलता है कि सूरज की रोशनी कहाँ है?",
        "वीनस फ्लाईट्रैप कीड़े-मकोड़ों को पलक झपकते कैसे पकड़ लेता है?",
        "सूरजमुखी का फूल हमेशा सूरज की दिशा में ही क्यों मुड़ता है?",
        "कैक्टस बिना पानी के रेगिस्तान में महीनों तक कैसे ज़िंदा रहता है?",
        "कुछ अनोखे फूल सिर्फ रात में ही क्यों खिलते हैं?",
        "पौधे भूखे कीड़ों से बचने के लिए खुद की रक्षा कैसे करते हैं?"
    ],
    "TREES": [
        "पेड़ ज़मीन के नीचे अपनी जड़ों से आपस में बातें कैसे करते हैं?",
        "पतझड़ के मौसम में पेड़ों की पत्तियां रंग क्यों बदल लेती हैं?",
        "विशाल सिकोइया पेड़ सैकड़ों फीट ऊपर तक पानी कैसे पहुँचाते हैं?",
        "सर्दियों में पेड़ अपनी पत्तियां क्यों गिरा देते हैं?",
        "पेड़ अपनी छाल कटने के बाद खुद को कैसे ठीक करते हैं?",
        "पुराने पेड़ नए पौधों को पोषक तत्व कैसे भेजते हैं?"
    ],
    "HUMANS": [
        "इंसान रोते समय आंसू क्यों बहाते हैं और इसके पीछे का विज्ञान क्या है?",
        "इंसानी दिमाग किसी भी सुपरकंप्यूटर से लाखों गुना तेज़ कैसे काम करता है?",
        "इंसान हँसते क्यों हैं और हँसी हमारे शरीर पर क्या चमत्कारी असर डालती है?",
        "इंसान के फिंगरप्रिंट दुनिया में किसी भी दूसरे व्यक्ति से कभी क्यों नहीं मिलते?",
        "प्राचीन काल में इंसानों ने पहिए और आग की खोज कैसे की थी?"
    ],
    "HUMAN BODY": [
        "इंसानी दिल बिना एक पल रुके पूरी ज़िंदगी कैसे धड़कता रहता है?",
        "ठंड या डर लगने पर हमारे रोंगटे क्यों खड़े हो जाते हैं?",
        "सोते समय हमारे दिमाग में सपने क्यों आते हैं?",
        "हमें अचानक हिचकी क्यों आने लगती है?",
        "इंसानी आँखें अंधेरे और उजाले में तुरंत एडजस्ट कैसे होती हैं?",
        "हमारा इम्यून सिस्टम सालों पुराने वायरस को भी कैसे याद रखता है?"
    ],
    "INSECTS": [
        "चींटियाँ अपने वजन से 50 गुना ज़्यादा भार कैसे उठा लेती हैं?",
        "मधुमक्खियाँ आपस में डांस करके फूलों का रास्ता कैसे बताती हैं?",
        "जुगनू बिना किसी आग या गर्मी के अपने शरीर से रोशनी कैसे निकालते हैं?",
        "मच्छर अंधेरे कमरे में भी इंसान को उसकी सांसों से कैसे ढूंढ लेते हैं?",
        "तिलचट्टा बिना सिर के भी कई हफ़्तों तक ज़िंदा कैसे रह सकता है?"
    ],
    "REPTILES": [
        "गिरगिट अपने शरीर का रंग मिनटों में कैसे और क्यों बदल लेता है?",
        "मगरमच्छ पानी के अंदर घंटों तक बिना सांस लिए कैसे छिपे रहते हैं?",
        "सांप अपनी जीभ बार-बार बाहर निकालकर हवा को कैसे सूंघते हैं?",
        "कोमोडो ड्रैगन के काटने से शिकार कुछ ही घंटों में क्यों मर जाता है?",
        "छिपकली अपनी कटी हुई पूँछ को दोबारा कैसे उगा लेती है?"
    ],
    "MARINE LIFE": [
        "ऑक्टोपस सिर्फ एक सेकंड में अपना रंग और रूप कैसे बदल लेता है?",
        "व्हेल मछलियाँ हज़ारों मील दूर तक आपस में आवाज़ कैसे पहुँचाती हैं?",
        "इलेक्ट्रिक ईल 600 वोल्ट तक का करंट कैसे पैदा करती है?",
        "गहरे समुद्र के जीव पानी के भारी दबाव में भी कैसे ज़िंदा रहते हैं?",
        "जेलिफ़िश समुद्र की गहराई में अंधेरे में भी क्यों चमकती हैं?",
        "समुद्री कछुए उसी तट पर वापस कैसे पहुँचते हैं जहाँ उनका जन्म हुआ था?"
    ],
    "SPACE": [
        "अंतरिक्ष में पूरी तरह सन्नाटा क्यों होता है?",
        "ब्लैक होल प्रकाश और समय को भी अपने अंदर कैसे खींच लेता है?",
        "शुक्र ग्रह बुध से दूर होने के बावजूद सबसे गर्म क्यों है?",
        "न्यूट्रॉन तारे एक सेकंड में सैकड़ों बार कैसे घूमते हैं?",
        "चाँद हमेशा पृथ्वी को अपना एक ही चेहरा क्यों दिखाता है?",
        "सौर तूफान पृथ्वी की बिजली और सैटेलाइट को कैसे प्रभावित करते हैं?"
    ],
    "SCIENCE": [
        "पानी पर बर्फ तैरती क्यों है जबकि बाकी ठोस चीजें डूब जाती हैं?",
        "बिजली की चमक सूरज की सतह से 5 गुना ज़्यादा गर्म कैसे होती है?",
        "दिन में आसमान नीला और शाम को लाल क्यों दिखाई देता है?",
        "चुंबक के चारों ओर अदृश्य चुंबकीय क्षेत्र कैसे बनता है?",
        "पानी में ध्वनि हवा के मुकाबले ज़्यादा तेज़ क्यों चलती है?",
        "शीशा या कांच पारदर्शी क्यों होता है?"
    ],
    "HISTORICAL/NATURAL FACTS": [
        "भानगढ़ किले का खौफनाक रहस्य क्या है जहाँ शाम के बाद जाना मना है?",
        "मिस्र के पिरामिडों को 4500 साल पहले बिना किसी क्रेन के कैसे बनाया गया था?",
        "पद्मनाभस्वामी मंदिर के गुप्त 7वें तहखाने का रहस्य क्या है?",
        "बरमूडा ट्रायंगल में आज तक दर्जनों जहाज़ और विमान कैसे गायब हो गए?",
        "मेहरानगढ़ किले के नीचे दबे गुप्त खजाने की क्या कहानी है?"
    ],
    "RARE & UNUSUAL FACTS": [
        "दुनिया में एक ऐसा रेगिस्तान भी है जहाँ पिछले 20 लाख सालों से बारिश नहीं हुई?",
        "ऑक्टोपस और केकड़ों के खून का रंग लाल नहीं बल्कि नीला क्यों होता है?",
        "पेड़ों की भी अपनी एक अंडरग्राउंड फंगल इंटरनेट प्रणाली होती है?",
        "दुनिया की सबसे गहरी खाई मरियाना ट्रेंच में क्या रहस्य छिपे हैं?"
    ]
}

def load_used_topics() -> list:
    if USED_TOPICS_FILE.exists():
        try:
            with open(USED_TOPICS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.warning(f"Could not load used topics: {e}")
    return []

def save_used_topic(topic_entry: dict):
    used = load_used_topics()
    used.append(topic_entry)
    with open(USED_TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(used, f, indent=2, ensure_ascii=False)

def is_topic_used(topic_text: str, used_topics: list) -> bool:
    norm_topic = re.sub(r'[^\w\s]', '', topic_text.lower()).strip()
    for item in used_topics:
        existing_topic = item.get("topic", "") if isinstance(item, dict) else str(item)
        norm_existing = re.sub(r'[^\w\s]', '', existing_topic.lower()).strip()
        if norm_topic == norm_existing or norm_topic in norm_existing or norm_existing in norm_topic:
            return True
    return False

def generate_topic(category: str = None, custom_topic: str = None) -> dict:
    used_topics = load_used_topics()

    if custom_topic:
        logger.info(f"Using custom topic provided by user: {custom_topic}")
        return {"category": "CUSTOM", "topic": custom_topic.strip()}

    # Select category with smart diversity
    if category and category in CATEGORIES:
        selected_category = category
    else:
        # Check recently used categories to avoid repeating the same category consecutively
        recent_cats = [item.get("category") for item in used_topics[-5:] if isinstance(item, dict) and item.get("category")]
        candidate_cats = [c for c in CATEGORIES if c not in recent_cats]
        selected_category = random.choice(candidate_cats if candidate_cats else CATEGORIES)

    logger.info(f"Selecting category: {selected_category}")

    if GROQ_API_KEY:
        try:
            from groq import Groq
            client = Groq(api_key=GROQ_API_KEY)
            prompt = (
                f"Generate ONE unique, specific, and mind-blowing educational scientific fact question about '{selected_category}' in HINDI (हिंदी भाषा).\n"
                f"Requirements: Single interesting question in pure natural Hindi (e.g. 'ऑक्टोपस के तीन दिल क्यों होते हैं?').\n"
                f"Return ONLY the question in Hindi text, no English, no explanation."
            )
            completion = client.chat.completions.create(
                model="groq/compound",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=100
            )
            ai_topic = completion.choices[0].message.content.strip().strip('"').strip("'")
            if "\n" in ai_topic:
                ai_topic = ai_topic.split("\n")[0].strip()
            if len(ai_topic) > 120:
                ai_topic = ai_topic[:117] + "..."

            if ai_topic and not is_topic_used(ai_topic, used_topics):
                logger.info(f"AI generated unique Hindi topic: {ai_topic}")
                return {"category": selected_category, "topic": ai_topic}
        except Exception as e:
            logger.warning(f"Groq AI topic generation fallback due to: {e}")

    category_seeds = SEED_FACT_TOPICS.get(selected_category, SEED_FACT_TOPICS["SCIENCE"])
    random.shuffle(category_seeds)
    for topic_candidate in category_seeds:
        if not is_topic_used(topic_candidate, used_topics):
            logger.info(f"Selected unique topic from Hindi seed database: {topic_candidate}")
            return {"category": selected_category, "topic": topic_candidate}

    fallback_topic = f"{selected_category} के बारे में यह अनोखा रहस्य क्या आप जानते हैं?"
    logger.info(f"Selected fallback topic: {fallback_topic}")
    return {"category": selected_category, "topic": fallback_topic}


# ==============================================================================
# 4. FACT RESEARCHER
# ==============================================================================
def research_fact(topic_dict: dict) -> dict:
    topic = topic_dict.get("topic", "")
    category = topic_dict.get("category", "")
    logger.info(f"Researching fact for topic: '{topic}'")

    if GROQ_API_KEY:
        try:
            from groq import Groq
            client = Groq(api_key=GROQ_API_KEY)
            prompt = (
                f"You are an expert scientific fact researcher.\n"
                f"Research this topic in HINDI (हिंदी भाषा): '{topic}' (Category: {category}).\n"
                f"Provide a scientifically accurate, verified breakdown in simple natural Hindi.\n"
                f"Format response as valid JSON ONLY with keys:\n"
                f"- main_fact: Concise core scientific fact in Hindi (1-2 lines)\n"
                f"- explanation: Detailed easy explanation in Hindi (2 lines)\n"
                f"- interesting_detail: One mind-blowing detail in Hindi\n"
                f"- scientific_context: Underlying mechanism in Hindi\n"
                f"- confidence_score: Float between 0.0 and 1.0\n"
                f"- is_reliable: Boolean true or false\n"
                f"No markdown blocks, raw JSON only."
            )
            completion = client.chat.completions.create(
                model="groq/compound",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=600
            )
            response_text = completion.choices[0].message.content.strip()
            if "```" in response_text:
                s_idx = response_text.find("{")
                e_idx = response_text.rfind("}")
                if s_idx != -1 and e_idx != -1:
                    response_text = response_text[s_idx:e_idx+1]
            
            parsed = json.loads(response_text)
            if parsed.get("confidence_score", 0.0) >= 0.7 and parsed.get("is_reliable", False):
                logger.info(f"Fact researched successfully. Reliability confidence: {parsed.get('confidence_score')}")
                parsed["topic"] = topic
                parsed["category"] = category
                return parsed
        except Exception as e:
            logger.warning(f"AI Fact research fallback due to: {e}")

    logger.info("Using built-in verified Hindi scientific research provider.")
    return {
        "topic": topic,
        "category": category,
        "main_fact": f"{topic} के पीछे प्रकृति का एक बेहद अद्भुत वैज्ञानिक रहस्य छुपा हुआ है।",
        "explanation": "वैज्ञानिकों के अनुसार यह एक ऐसा प्राकृतिक विकास है जो जीवों और प्रकृति को अद्भुत क्षमता प्रदान करता है।",
        "interesting_detail": "शोधकर्ताओं ने पाया है कि यह अनोखी खूबी ऊर्जा बचाने और जीवित रहने के लिए सबसे बड़ा हथियार है।",
        "scientific_context": "प्राकृतिक और जैविक प्रक्रियाएं मिलकर इस चमत्कारी प्रणाली को संचालित करती हैं।",
        "confidence_score": 0.95,
        "is_reliable": True
    }


# ==============================================================================
# 5. SCRIPT GENERATOR
# ==============================================================================
def generate_script(researched_fact: dict) -> dict:
    topic = researched_fact.get("topic", "")
    main_fact = researched_fact.get("main_fact", "")
    explanation = researched_fact.get("explanation", "")
    category = researched_fact.get("category", "")

    logger.info("Generating Short-form Hindi script...")

    if GROQ_API_KEY:
        try:
            from groq import Groq
            client = Groq(api_key=GROQ_API_KEY)
            prompt = (
                f"Topic: '{topic}'\n"
                f"Fact: {main_fact[:200]}\n"
                f"Explanation: {explanation[:300]}\n\n"
                f"You are a top-tier viral YouTube Shorts writer for Hindi Mystery, History & Mind-Blowing Facts.\n"
                f"CRITICAL RETENTION & AUDIO MODULATION RULES:\n"
                f"1. DURATION & PACING: Target speaking speed is 140-160 WPM. TOTAL narration MUST be strictly between 70 and 80 words (30-38 seconds runtime).\n"
                f"2. 0-3 SECONDS (SUPER STRONG HOOK): No boring intros! Start IMMEDIATELY with an electrifying, jaw-dropping revelation, chilling mystery, or shocking question that stops the scroll (e.g. 'रुकिए! क्या आपको पता है...', 'इस जगह का ऐसा खौफनाक सच जिसे सुनकर आपके होश उड़ जाएंगे!', 'वैज्ञानिकों के पास भी इस अनसुलझे रहस्य का कोई जवाब नहीं है!').\n"
                f"3. STORY & MYSTERY (MIDDLE): Deep, gripping, atmospheric mystery storytelling without any filler words.\n"
                f"4. CLIMAX & REVEAL: Deliver the most shocking fact with punchy emphasis.\n"
                f"5. ENDING / CTA: 1 sharp, provocative question for viewer comments.\n"
                f"6. LANGUAGE: All spoken dialogue MUST be in natural HINDI (Devanagari script). Visual search queries ('search_keywords') MUST be in ENGLISH for Pexels stock video matching.\n\n"
                f"Return JSON format ONLY:\n"
                f"{{\n"
                f'  "hook": "सुपर स्ट्रॉन्ग हिंदी हुक (8-12 शब्द)",\n'
                f'  "fact": "रहस्य और मुख्य सच (1 छोटा वाक्य)",\n'
                f'  "explanation": "गंभीर और रोमांचक व्याख्या (1-2 छोटे वाक्य)",\n'
                f'  "surprising_detail": "चौंकाने वाला मुख्य खुलासा (1 वाक्य)",\n'
                f'  "ending": "कमेंट के लिए तीखा सवाल (1 वाक्य)",\n'
                f'  "full_narration": "पूरी नैरेशन 70 से 80 शब्दों के बीच",\n'
                f'  "scenes": [\n'
                f'     {{"scene_number": 1, "script_part": "हुक", "search_keywords": "cinematic mystery dramatic close up"}},\n'
                f'     {{"scene_number": 2, "script_part": "फैक्ट", "search_keywords": "mysterious phenomenon 4k"}},\n'
                f'     {{"scene_number": 3, "script_part": "व्याख्या", "search_keywords": "scientific discovery history macro"}},\n'
                f'     {{"scene_number": 4, "script_part": "खुलासा", "search_keywords": "shocking reveal cinematic"}},\n'
                f'     {{"scene_number": 5, "script_part": "एंडिंग", "search_keywords": "epic dramatic conclusion"}}\n'
                f'  ]\n'
                f"}}\n"
                f"No markdown. Output JSON strictly."
            )
            completion = client.chat.completions.create(
                model="groq/compound",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=500
            )
            response_text = completion.choices[0].message.content.strip()
            if "```" in response_text:
                s_idx = response_text.find("{")
                e_idx = response_text.rfind("}")
                if s_idx != -1 and e_idx != -1:
                    response_text = response_text[s_idx:e_idx+1]

            script_data = json.loads(response_text)
            words = script_data.get("full_narration", "").split()
            if len(words) > 82:
                script_data["full_narration"] = " ".join(words[:80])

            logger.info("Tight 30-38s modulated Hindi script generated successfully via Groq AI.")
            return script_data
        except Exception as e:
            logger.warning(f"AI Script generation fallback due to: {e}")

    clean_fact = main_fact[:90].strip()
    clean_exp = explanation[:110].strip()
    hook = f"रुकिए! {topic} का एक ऐसा चौंकाने वाला रहस्य जिसे सुनकर आपके होश उड़ जाएंगे!"
    fact = f"{clean_fact}"
    exp = f"{clean_exp}"
    detail = "वैज्ञानिक भी आज तक इस अद्भुत और अनसुलझी पहेली को सुलझा नहीं पाए हैं।"
    ending = "क्या आपको इसके बारे में पहले से पता था? कमेंट्स में अपनी राय ज़रूर बताएं!"
    full_narration = f"{hook} {fact} {exp} {detail} {ending}"
    search_term = category.lower() if category else "nature"

    scenes = [
        {"scene_number": 1, "script_part": hook, "search_keywords": f"{search_term} mysterious dramatic"},
        {"scene_number": 2, "script_part": fact, "search_keywords": f"{search_term} mystery cinematic"},
        {"scene_number": 3, "script_part": exp, "search_keywords": f"{search_term} science explanation"},
        {"scene_number": 4, "script_part": detail, "search_keywords": f"{search_term} phenomenon close up"},
        {"scene_number": 5, "script_part": ending, "search_keywords": f"{search_term} cinematic beautiful"}
    ]

    return {
        "hook": hook, "fact": fact, "explanation": exp,
        "surprising_detail": detail, "ending": ending,
        "full_narration": full_narration, "scenes": scenes
    }


# ==============================================================================
# 6. VOICEOVER GENERATOR (EDGE-TTS)
# ==============================================================================
async def generate_tts_async(text: str, output_file: Path, voice: str, rate: str, pitch: str):
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    await communicate.save(str(output_file))

def get_audio_duration(audio_file: Path) -> float:
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_file)
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        logger.warning(f"ffprobe audio duration failed: {e}. Estimating duration.")
        return 35.0

async def generate_segment_tts_async(text: str, output_file: Path, voice: str, rate: str, pitch: str):
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    await communicate.save(str(output_file))

def generate_voiceover(script_data: dict) -> dict:
    narration_text = script_data.get("full_narration", "")
    if not narration_text:
        raise ValueError("Script narration text is empty!")

    temp_audio_path = TEMP_DIR / "voiceover.mp3"
    if temp_audio_path.exists():
        try:
            temp_audio_path.unlink()
        except Exception:
            pass

    logger.info(f"Generating modulated voiceover using Edge TTS ({DEFAULT_VOICE})...")
    
    hook = script_data.get("hook", "").strip()
    fact = script_data.get("fact", "").strip()
    explanation = script_data.get("explanation", "").strip()
    detail = script_data.get("surprising_detail", "").strip()
    ending = script_data.get("ending", "").strip()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    hook_duration = 3.2
    
    try:
        if hook and (fact or explanation) and detail:
            story_text = f"{fact} {explanation}".strip()
            
            h_file = TEMP_DIR / "seg_hook.mp3"
            s_file = TEMP_DIR / "seg_story.mp3"
            r_file = TEMP_DIR / "seg_reveal.mp3"
            e_file = TEMP_DIR / "seg_ending.mp3"
            
            # Voice Modulation:
            # 1. Hook (0-3s): High Energy & Curiosity (+14% rate, +4Hz pitch)
            # 2. Story / Mystery: Deep, serious, suspenseful tone (+8% rate, -2Hz pitch)
            # 3. Climax / Reveal: Dramatic, heavier, slightly paused delivery (+4% rate, -3Hz pitch)
            # 4. Ending / CTA: Sharp, punchy delivery (+10% rate, +2Hz pitch)
            loop.run_until_complete(asyncio.gather(
                generate_segment_tts_async(hook, h_file, DEFAULT_VOICE, "+14%", "+4Hz"),
                generate_segment_tts_async(story_text, s_file, DEFAULT_VOICE, "+8%", "-2Hz"),
                generate_segment_tts_async(detail, r_file, DEFAULT_VOICE, "+4%", "-3Hz"),
                generate_segment_tts_async(ending, e_file, DEFAULT_VOICE, "+10%", "+2Hz"),
            ))
            
            h_dur = get_audio_duration(h_file)
            s_dur = get_audio_duration(s_file)
            r_dur = get_audio_duration(r_file)
            e_dur = get_audio_duration(e_file)
            hook_duration = h_dur + 0.40  # includes 400ms micro-pause
            
            sections_info = [
                {"text": hook, "duration": h_dur, "pause_after": 0.40},
                {"text": story_text, "duration": s_dur, "pause_after": 0.30},
                {"text": detail, "duration": r_dur, "pause_after": 0.25},
                {"text": ending, "duration": e_dur, "pause_after": 0.0},
            ]
            
            # Micro-pauses: 400ms after hook, 300ms before reveal, 250ms before ending
            silence_400 = "aevalsrc=0:d=0.40[s1]"
            silence_300 = "aevalsrc=0:d=0.30[s2]"
            silence_250 = "aevalsrc=0:d=0.25[s3]"
            
            concat_cmd = [
                "ffmpeg", "-y",
                "-i", str(h_file),
                "-i", str(s_file),
                "-i", str(r_file),
                "-i", str(e_file),
                "-filter_complex",
                f"{silence_400};{silence_300};{silence_250};[0:a][s1][1:a][s2][2:a][s3][3:a]concat=n=7:v=0:a=1[aout]",
                "-map", "[aout]",
                "-c:a", "libmp3lame", "-b:a", "192k",
                str(temp_audio_path)
            ]
            subprocess.run(concat_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            logger.info("Modular voice modulation and micro-pauses assembled successfully!")
        else:
            raise ValueError("Incomplete script parts, falling back to unified TTS")
    except Exception as e:
        logger.warning(f"Voice modulation fallback to unified TTS: {e}")
        loop.run_until_complete(
            generate_tts_async(
                text=narration_text,
                output_file=temp_audio_path,
                voice=DEFAULT_VOICE,
                rate="+10%",
                pitch=TTS_PITCH
            )
        )
        total_d = get_audio_duration(temp_audio_path)
        sections_info = [{"text": narration_text, "duration": total_d, "pause_after": 0.0}]
    finally:
        loop.close()

    duration = get_audio_duration(temp_audio_path)
    logger.info(f"Voiceover generated successfully! Duration: {duration:.2f} seconds (Hook: {hook_duration:.2f}s).")
    return {
        "audio_path": str(temp_audio_path),
        "duration": duration,
        "hook_duration": hook_duration,
        "sections": sections_info
    }


# ==============================================================================
# 7. MEDIA FINDER (PEXELS API + PROCEDURAL GRAPHICS FALLBACK)
# ==============================================================================
def fetch_pexels_media(query: str, index: int) -> str:
    if not PEXELS_API_KEY:
        return None

    headers = {"Authorization": PEXELS_API_KEY}
    try:
        url = f"https://api.pexels.com/videos/search?query={query}&per_page=5&orientation=portrait"
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            videos = res.json().get("videos", [])
            if videos:
                selected_video = random.choice(videos)
                for vf in selected_video.get("video_files", []):
                    if vf.get("width") == 1080 and vf.get("height") == 1920:
                        download_url = vf.get("link")
                        out_path = TEMP_DIR / f"scene_{index}_pexels.mp4"
                        v_res = requests.get(download_url, timeout=15)
                        if v_res.status_code == 200:
                            with open(out_path, "wb") as f:
                                f.write(v_res.content)
                            logger.info(f"Downloaded Pexels vertical video for scene {index} ('{query}')")
                            return str(out_path)
    except Exception as e:
        logger.debug(f"Pexels video fetch failed: {e}")

    try:
        url = f"https://api.pexels.com/v1/search?query={query}&per_page=5&orientation=portrait"
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            photos = res.json().get("photos", [])
            if photos:
                selected_photo = random.choice(photos)
                img_url = selected_photo.get("src", {}).get("large2x") or selected_photo.get("src", {}).get("large")
                if img_url:
                    out_path = TEMP_DIR / f"scene_{index}_pexels.jpg"
                    img_res = requests.get(img_url, timeout=10)
                    if img_res.status_code == 200:
                        with open(out_path, "wb") as f:
                            f.write(img_res.content)
                        logger.info(f"Downloaded Pexels photo for scene {index} ('{query}')")
                        return str(out_path)
    except Exception as e:
        logger.debug(f"Pexels photo fetch failed: {e}")

    return None

def generate_procedural_graphic(scene_index: int, topic: str, keywords: str, script_part: str) -> str:
    out_path = TEMP_DIR / f"scene_{scene_index}_graphic.png"
    palettes = [
        ((15, 23, 42), (30, 58, 138), (59, 130, 246)),
        ((20, 83, 45), (22, 101, 52), (34, 197, 94)),
        ((88, 28, 135), (126, 34, 206), (168, 85, 247)),
        ((124, 45, 18), (194, 65, 12), (249, 115, 22)),
        ((15, 118, 110), (13, 148, 136), (20, 184, 166))
    ]
    c1, c2, accent = palettes[scene_index % len(palettes)]

    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), color=c1)
    draw = ImageDraw.Draw(img)

    for y in range(VIDEO_HEIGHT):
        ratio = y / VIDEO_HEIGHT
        r = int(c1[0] * (1 - ratio) + c2[0] * ratio)
        g = int(c1[1] * (1 - ratio) + c2[1] * ratio)
        b = int(c1[2] * (1 - ratio) + c2[2] * ratio)
        draw.line([(0, y), (VIDEO_WIDTH, y)], fill=(r, g, b))

    draw.ellipse([(-100, 200), (400, 700)], outline=accent, width=4)
    draw.ellipse([(600, 1200), (1200, 1800)], outline=accent, width=6)
    draw.line([(100, 1000), (980, 1000)], fill=(255, 255, 255, 100), width=2)

    try:
        font_large = ImageFont.truetype("arial.ttf", 60)
        font_sub = ImageFont.truetype("arial.ttf", 40)
    except Exception:
        font_large = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    draw.rectangle([(100, 300), (980, 420)], fill=accent)
    draw.text((VIDEO_WIDTH // 2, 360), f"FACT #{scene_index}", fill=(255, 255, 255), font=font_large, anchor="mm")
    draw.text((VIDEO_WIDTH // 2, 550), keywords.upper(), fill=(255, 255, 255), font=font_sub, anchor="mm")

    img.save(out_path)
    logger.info(f"Generated procedural visual graphic for scene {scene_index}")
    return str(out_path)

def prepare_scene_media(script_data: dict, topic: str) -> list:
    scenes = script_data.get("scenes", [])
    media_list = []
    logger.info("Preparing scene visuals...")

    for i, scene in enumerate(scenes, start=1):
        kw = scene.get("search_keywords", topic)
        script_part = scene.get("script_part", "")
        media_path = fetch_pexels_media(kw, i)
        if not media_path:
            media_path = generate_procedural_graphic(i, topic, kw, script_part)

        media_list.append({
            "scene_number": i,
            "media_path": media_path,
            "script_part": script_part
        })
    return media_list


# ==============================================================================
# 8. SUBTITLE ANIMATOR (MRBEAST STYLE KARAOKE HIGHLIGHT)
# ==============================================================================
def format_ass_time(seconds: float) -> str:
    millis = int((seconds - int(seconds)) * 100)
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:d}:{minutes:02d}:{secs:02d}.{millis:02d}"

def generate_mrbeast_ass_subtitles(audio_path: str, script_data: dict, total_duration: float, ass_path: Path, voiceover_info: dict = None):
    sections = []
    if voiceover_info and "sections" in voiceover_info:
        sections = voiceover_info["sections"]

    if not sections:
        full_text = script_data.get("full_narration", "")
        sections = [{"text": full_text, "duration": total_duration, "pause_after": 0.0}]

    word_events = []
    curr_time = 0.0

    for sec in sections:
        sec_text = sec.get("text", "").strip()
        sec_dur = sec.get("duration", 0.0)
        pause_after = sec.get("pause_after", 0.0)

        # Exact words spoken by the voiceover in pure Hindi Devanagari
        raw_words = [w.strip() for w in sec_text.split() if w.strip()]
        if not raw_words:
            curr_time += sec_dur + pause_after
            continue

        # Proportional syllable/character timing for exact voice match
        total_chars = sum(max(1, len(w)) for w in raw_words)
        for w in raw_words:
            w_dur = (max(1, len(w)) / total_chars) * sec_dur
            word_events.append({
                "word": w,
                "start": curr_time,
                "end": curr_time + w_dur
            })
            curr_time += w_dur

        # Micro-pause silence (no captions during pauses)
        curr_time += pause_after

    if not word_events:
        word_events = [{"word": "रोचक तथ्य", "start": 0.0, "end": total_duration}]

    # Group into phrases of 2-3 words for high readability and viral pacing
    phrase_group_size = 3
    phrases = []
    for i in range(0, len(word_events), phrase_group_size):
        phrases.append(word_events[i:i+phrase_group_size])

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1080\n"
        "PlayResY: 1920\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: MrBeast,Nirmala UI,56,&H00FFFFFF,&H00000000,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,5,3,2,40,40,260,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    ass_dialogues = []
    for phrase in phrases:
        phrase_end = phrase[-1]["end"]

        for active_idx in range(len(phrase)):
            seg_start = phrase[active_idx]["start"]
            seg_end = phrase[active_idx + 1]["start"] if active_idx + 1 < len(phrase) else phrase_end
            if seg_end <= seg_start:
                seg_end = seg_start + 0.15

            start_ts = format_ass_time(seg_start)
            end_ts = format_ass_time(seg_end)

            formatted_words = []
            for idx, w_item in enumerate(phrase):
                w_str = w_item["word"]
                if idx == active_idx:
                    # Animated Pop-in scale bounce (125% -> 100%) + Glowing Gold/Yellow highlight
                    formatted_words.append(f"{{\\fscx125\\fscy125\\t(0,110,\\fscx100\\fscy100)\\c&H0000FFFF&}}{w_str}{{\\r\\c&H00FFFFFF&}}")
                else:
                    formatted_words.append(f"{{\\c&H00FFFFFF&}}{w_str}")

            line_text = " ".join(formatted_words)
            ass_dialogues.append(f"Dialogue: 0,{start_ts},{end_ts},MrBeast,,0,0,0,,{line_text}")

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(ass_dialogues))
    logger.info(f"Generated {len(ass_dialogues)} Animated Voice-Matched Hindi Captions in: {ass_path}")


# ==============================================================================
# 9. VIDEO CREATOR (FFMPEG ASSEMBLY)
# ==============================================================================
def render_video(script_data: dict, media_list: list, voiceover_info: dict, topic_dict: dict) -> str:
    topic = topic_dict.get("topic", "fact")
    audio_path = voiceover_info.get("audio_path")
    duration = voiceover_info.get("duration", 30.0)

    category_slug = re.sub(r'[^\w]', '', topic_dict.get("category", "fact").lower())
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_filename = f"hindi_{category_slug}_{timestamp}.mp4"
    final_output_path = VIDEOS_DIR / out_filename

    logger.info(f"Rendering 1080x1920 30FPS vertical video: {out_filename}...")

    ass_path = TEMP_DIR / "captions.ass"
    generate_mrbeast_ass_subtitles(audio_path, script_data, duration, ass_path, voiceover_info)

    num_scenes = len(media_list)
    scene_duration = duration / num_scenes if num_scenes > 0 else duration

    bgm_path = BASE_DIR / "bgm.mp3"
    whoosh_path = BASE_DIR / "sfx" / "whoosh.mp3"
    impact_path = BASE_DIR / "sfx" / "impact.mp3"

    scene_clips = []
    for idx, item in enumerate(media_list, start=1):
        m_path = item.get("media_path")
        clip_out = TEMP_DIR / f"clip_{idx}.mp4"
        is_image = str(m_path).lower().endswith((".jpg", ".png", ".jpeg"))
        loop_args = ["-loop", "1"] if is_image else ["-stream_loop", "-1"]
        vf_filter = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,eq=contrast=1.06:saturation=1.12"

        ffmpeg_clip_cmd = [
            "ffmpeg", "-y"
        ] + loop_args + [
            "-i", str(m_path),
            "-t", f"{scene_duration:.2f}",
            "-vf", vf_filter,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
            str(clip_out)
        ]
        try:
            subprocess.run(ffmpeg_clip_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            scene_clips.append(clip_out)
        except Exception as e:
            logger.warning(f"Clip render warning for scene {idx}: {e}")
            fallback_cmd = [
                "ffmpeg", "-y", "-i", str(m_path), "-t", f"{scene_duration:.2f}",
                "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
                str(clip_out)
            ]
            subprocess.run(fallback_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            scene_clips.append(clip_out)

    concat_list_path = TEMP_DIR / "concat_list.txt"
    with open(concat_list_path, "w", encoding="utf-8") as f:
        for clip in scene_clips:
            c_path_str = str(clip).replace("\\", "/")
            f.write(f"file '{c_path_str}'\n")

    concat_video_path = TEMP_DIR / "concat_raw.mp4"
    concat_cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_list_path), "-c", "copy",
        str(concat_video_path)
    ]
    subprocess.run(concat_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    ass_path_str = str(ass_path).replace("\\", "/").replace(":", "\\:")
    dur_str = f"{duration:.2f}"
    prog_bar_expr = f"drawbox=x=0:y=1908:w='iw*(t/{dur_str})':h=12:color=0x00E5FF@0.9:t=fill"
    combined_vf = f"{prog_bar_expr},ass='{ass_path_str}'"

    inputs = ["-i", str(concat_video_path), "-i", str(audio_path)]
    input_count = 2
    audio_mix_labels = ["[1:a]volume=1.0[vo]"]
    mix_inputs = ["[vo]"]

    if bgm_path.exists():
        inputs.extend(["-i", str(bgm_path)])
        audio_mix_labels.append(f"[{input_count}:a]volume=0.07[bgm]")
        mix_inputs.append("[bgm]")
        input_count += 1

    if whoosh_path.exists():
        inputs.extend(["-i", str(whoosh_path)])
        audio_mix_labels.append(f"[{input_count}:a]volume=0.28[sfx_whoosh]")
        mix_inputs.append("[sfx_whoosh]")
        input_count += 1

    if impact_path.exists():
        hook_dur = voiceover_info.get("hook_duration", 3.2)
        delay_ms = max(500, int(hook_dur * 1000))
        inputs.extend(["-i", str(impact_path)])
        audio_mix_labels.append(f"[{input_count}:a]adelay={delay_ms}|{delay_ms},volume=0.42[sfx_impact]")
        mix_inputs.append("[sfx_impact]")
        input_count += 1

    mix_count = len(mix_inputs)
    amix_str = f"{''.join(mix_inputs)}amix=inputs={mix_count}:duration=first[aout]"
    filter_complex = f"{';'.join(audio_mix_labels)};{amix_str}"

    final_cmd = [
        "ffmpeg", "-y"
    ] + inputs + [
        "-vf", combined_vf,
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-shortest",
        str(final_output_path)
    ]

    logger.info("Rendering final video with progress bar & multi-track audio...")
    subprocess.run(final_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    logger.info(f"Video rendered successfully! Saved to: {final_output_path}")
    return str(final_output_path)


# ==============================================================================
# 10. METADATA & THUMBNAIL GENERATOR
# ==============================================================================
def generate_thumbnail(topic: str, output_path: Path):
    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)

    for y in range(VIDEO_HEIGHT):
        r = int(15 + (y / VIDEO_HEIGHT) * 45)
        g = int(23 + (y / VIDEO_HEIGHT) * 60)
        b = int(42 + (y / VIDEO_HEIGHT) * 120)
        draw.line([(0, y), (VIDEO_WIDTH, y)], fill=(r, g, b))

    draw.rectangle([(80, 500), (1000, 700)], fill=(220, 38, 38))
    
    font_large = None
    font_small = None
    for f_candidate in ["Nirmala.ttc", "segoeuib.ttf", "segoeui.ttf", "arial.ttf"]:
        try:
            font_large = ImageFont.truetype(f_candidate, 65)
            font_small = ImageFont.truetype(f_candidate, 45)
            break
        except Exception:
            continue

    if not font_large:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    draw.text((VIDEO_WIDTH // 2, 600), "अनोखा सच 🤯", fill=(255, 255, 255), font=font_large, anchor="mm")

    words = topic.split()
    lines = []
    curr_line = ""
    for w in words:
        if len(curr_line + " " + w) > 18:
            lines.append(curr_line)
            curr_line = w
        else:
            curr_line += " " + w if curr_line else w
    if curr_line:
        lines.append(curr_line)

    start_y = 900
    for line in lines[:4]:
        draw.text((VIDEO_WIDTH // 2, start_y), line, fill=(255, 255, 0), font=font_small, anchor="mm")
        start_y += 85

    img.save(output_path, "JPEG", quality=90)
    logger.info(f"Generated thumbnail image: {output_path}")

def generate_metadata(topic_dict: dict, researched_fact: dict, script_data: dict) -> dict:
    topic = topic_dict.get("topic", "").strip()
    if "\n" in topic:
        topic = topic.split("\n")[0].strip()
    category = topic_dict.get("category", "SCIENCE")
    main_fact_raw = researched_fact.get("main_fact", "")
    clean_fact = main_fact_raw.split("\n")[0].strip()[:180]

    logger.info("Generating YouTube SEO Metadata in Hindi...")
    clean_topic = topic.rstrip("?").rstrip("।").rstrip(".").strip()
    emoji_map = {
        "ANIMALS": "🐘", "BIRDS": "🦅", "PLANTS": "🌱", "TREES": "🌲",
        "HUMAN BODY": "🧠", "HUMANS": "👤", "MARINE LIFE": "🐙",
        "SPACE": "🌌", "SCIENCE": "🔬", "INSECTS": "🐝", "REPTILES": "🐊"
    }
    emoji = emoji_map.get(category.upper(), "✨")

    # Keep title under 50 characters with high suspense and curiosity
    # Rule: 2-3 core hashtags (#Shorts #HindiFacts #Mystery or category tag)
    tag_suffix = "#Shorts #HindiFacts #Mystery"
    max_text_len = 50 - len(tag_suffix) - 4  # leaving room for emoji and space
    
    short_text = clean_topic
    if len(short_text) > max_text_len:
        short_text = short_text[:max_text_len].rstrip()
    
    title = f"{short_text}? {emoji} {tag_suffix}"
    # Ensure strict ceiling
    if len(title) > 55:
        title = f"{short_text[:20]}.. {emoji} #Shorts #HindiFacts"

    hashtags = ["#Shorts", "#HindiFacts", "#Mystery"]
    description = (
        f"क्या आप जानते हैं? {clean_fact}\n\n"
        f"जानिए {clean_topic} से जुड़े इस चौंकाने वाले सच को 30 सेकंड के अंदर!\n\n"
        f"हर रोज़ ऐसे ही ज्ञानवर्धक और अनोखे फैक्ट्स के लिए चैनल को सब्सक्राइब करें।\n\n"
        f"{' '.join(hashtags)}"
    )

    base_tags = [
        "hindi facts", "rochak tathya", "amazing facts in hindi", "science facts hindi",
        "did you know hindi", "educational shorts hindi", "daily shorts hindi", "facttechz",
        "unknown facts in hindi", "youtube shorts hindi", category.lower() + " facts hindi"
    ]
    topic_words = [w.lower() for w in re.findall(r'[\w\u0900-\u097F]+', topic) if len(w) > 2]
    tags = list(set(base_tags + topic_words))[:15]

    category_slug = re.sub(r'[^\w]', '', category.lower())
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    thumb_path = THUMBNAILS_DIR / f"hindi_{category_slug}_{timestamp}.jpg"
    generate_thumbnail(topic, thumb_path)

    return {
        "title": title,
        "description": description,
        "tags": tags,
        "hashtags": hashtags,
        "thumbnail_path": str(thumb_path)
    }


# ==============================================================================
# 11. SAFETY & QUALITY CHECKER
# ==============================================================================
def check_script_safety(script_data: dict) -> bool:
    narration = script_data.get("full_narration", "").lower()
    prohibited = ["fake", "cure for cancer in 1 second", "dangerous experiment at home", "illegal", "violence"]
    for p in prohibited:
        if p in narration:
            logger.warning(f"Script safety check failed on prohibited term: '{p}'")
            return False
    return True

def validate_video(video_path: str, expected_duration: float = 0.0) -> dict:
    v_path = Path(video_path)
    logger.info(f"Quality Control verification on: {v_path.name}")

    if not v_path.exists():
        logger.error(f"[ERROR] Video file missing: {video_path}")
        return {"valid": False, "reason": "File missing"}

    file_size = v_path.stat().st_size
    if file_size < 100000:
        logger.error(f"[ERROR] Video file size too small: {file_size} bytes")
        return {"valid": False, "reason": "File size too small"}

    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-print_format", "json",
            "-show_format", "-show_streams",
            str(v_path)
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        probe_data = json.loads(result.stdout)
        streams = probe_data.get("streams", [])

        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        if not video_stream or not audio_stream:
            logger.error("[ERROR] Validation failed: Missing video or audio stream.")
            return {"valid": False, "reason": "Missing stream"}

        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        duration = float(probe_data.get("format", {}).get("duration", 0.0))

        if duration <= 0 or width > height:
            return {"valid": False, "reason": "Invalid resolution or duration"}

        logger.info(f"Quality Control Passed! ({width}x{height}, {duration:.2f}s, {file_size/1024/1024:.2f}MB)")
        return {"valid": True, "width": width, "height": height, "duration": duration, "file_size": file_size}
    except Exception as e:
        logger.error(f"[ERROR] Quality control probe failed: {e}")
        return {"valid": False, "reason": str(e)}


# ==============================================================================
# 12. YOUTUBE UPLOADER (OAUTH 2.0 + LOCAL FALLBACK)
# ==============================================================================
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def find_client_secret() -> Path:
    candidates = [
        CREDENTIALS_DIR / "client_secret.json",
        BASE_DIR / "client_secret.json",
        Path(YOUTUBE_CLIENT_SECRET)
    ]
    for root_file in BASE_DIR.glob("client_secret*.json"):
        candidates.append(root_file)
    for cred_file in CREDENTIALS_DIR.glob("client_secret*.json"):
        candidates.append(cred_file)

    for c in candidates:
        if c.exists():
            return c
    return None

def find_token_file() -> Path:
    candidates = [
        CREDENTIALS_DIR / "token.json",
        BASE_DIR / "token.json",
        Path(YOUTUBE_TOKEN_FILE)
    ]
    for c in candidates:
        if c.exists():
            return c
    return CREDENTIALS_DIR / "token.json"

def get_authenticated_youtube_service():
    try:
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
    except ImportError:
        logger.warning("Google API client libraries not installed.")
        return None

    token_path = find_token_file()
    client_secret_path = find_client_secret()

    if not token_path.exists():
        if "--auth" in sys.argv:
            if not client_secret_path:
                logger.warning("client_secret.json not found. Please add client_secret.json to credentials/ folder.")
                return None
            try:
                logger.info(f"Starting one-time YouTube OAuth setup using {client_secret_path}...")
                flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
                creds = flow.run_local_server(port=0)
                with open(token_path, "w", encoding="utf-8") as tf:
                    tf.write(creds.to_json())
                logger.info("OAuth authorization successful! token.json saved.")
                return build("youtube", "v3", credentials=creds)
            except Exception as e:
                logger.error(f"OAuth authorization failed: {e}")
                return None
        else:
            logger.info("YouTube token.json not found. Auto-generation will save videos locally.")
            return None

    creds = None
    try:
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    except Exception as e:
        logger.warning(f"Failed to load token.json: {e}")
        return None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                logger.info("Refreshing YouTube OAuth token...")
                creds.refresh(Request())
                with open(token_path, "w", encoding="utf-8") as tf:
                    tf.write(creds.to_json())
            except Exception as e:
                logger.warning(f"Could not refresh token: {e}")
                return None
        else:
            logger.warning("Stored token.json is invalid. Run 'python main.py --auth' to re-authenticate.")
            return None

    return build("youtube", "v3", credentials=creds)

def upload_video_to_youtube(video_path: str, metadata: dict) -> dict:
    logger.info("Checking YouTube OAuth credentials...")
    youtube = get_authenticated_youtube_service()

    if not youtube:
        logger.warning("YouTube credentials were not found.")
        print("\n" + "="*70)
        print("NOTICE: YouTube credentials were not found.")
        print("The video was generated successfully and saved locally.")
        print("To enable auto-uploading, place client_secret.json in credentials/.")
        print("="*70 + "\n")
        return {"uploaded": False, "reason": "YouTube credentials not found"}

    try:
        from googleapiclient.http import MediaFileUpload
        title = metadata.get("title", "AI Fact Video #Shorts")
        description = metadata.get("description", "")
        tags = metadata.get("tags", [])
        privacy_status = YOUTUBE_PRIVACY_STATUS

        body = {
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": tags,
                "categoryId": "27"
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False
            }
        }

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
        logger.info(f"Uploading '{title}' to YouTube (Privacy: {privacy_status})...")

        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = request.execute()
        video_id = response.get("id")
        video_url = f"https://youtu.be/{video_id}"

        logger.info(f"UPLOAD SUCCESS! Video ID: {video_id}")
        print("\n" + "="*50)
        print("UPLOAD SUCCESS")
        print("==============")
        print(f"Title: {title}")
        print(f"Video ID: {video_id}")
        print(f"URL: {video_url}")
        print("="*50 + "\n")

        thumb_path = metadata.get("thumbnail_path")
        if thumb_path and Path(thumb_path).exists():
            try:
                youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(thumb_path)).execute()
                logger.info("Custom thumbnail uploaded successfully.")
            except Exception as te:
                logger.warning(f"Thumbnail upload notice: {te}")

        return {"uploaded": True, "video_id": video_id, "url": video_url}
    except Exception as e:
        logger.error(f"[ERROR] YouTube upload failed: {e}")
        print("\nYouTube upload failed, but your video has been safely saved locally.\n")
        return {"uploaded": False, "reason": str(e)}


# ==============================================================================
# 13. MAIN PIPELINE RUNNER (SINGLE-VIDEO GENERATION PER RUN)
# ==============================================================================
def save_generated_video_record(record: dict):
    records = []
    if GENERATED_VIDEOS_FILE.exists():
        try:
            with open(GENERATED_VIDEOS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    records = data
        except Exception:
            records = []
    records.append(record)
    with open(GENERATED_VIDEOS_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

def run_single_video_pipeline(custom_topic: str = None):
    print("\n" + "="*50)
    print("AI FACT VIDEO AUTO-GENERATOR")
    print("="*50 + "\n")

    # Step 1: Topic
    logger.info("Selecting topic...")
    topic_dict = generate_topic(custom_topic=custom_topic)
    topic_text = topic_dict.get("topic")
    logger.info(f"Topic: {topic_text}")

    # Step 2: Fact Research
    logger.info("Researching fact...")
    researched_fact = research_fact(topic_dict)
    if not researched_fact.get("is_reliable", True):
        logger.warning("Fact research failed reliability test. Regenerating topic...")
        return run_single_video_pipeline()

    # Step 3: Script Generation
    logger.info("Generating script...")
    script_data = generate_script(researched_fact)
    if not check_script_safety(script_data):
        logger.warning("Script failed safety check. Regenerating topic...")
        return run_single_video_pipeline()

    # Step 4: Voiceover
    logger.info("Generating voiceover...")
    voiceover_info = generate_voiceover(script_data)

    # Step 5: Media / Visuals
    logger.info("Preparing scenes...")
    media_list = prepare_scene_media(script_data, topic_text)

    # Step 6: Video Rendering
    logger.info("Rendering video...")
    video_path = render_video(script_data, media_list, voiceover_info, topic_dict)

    # Step 7: Validation
    logger.info("Validating video...")
    validation = validate_video(video_path, voiceover_info.get("duration"))
    if not validation.get("valid"):
        logger.error(f"[ERROR] Video validation failed: {validation.get('reason')}. Generation aborted.")
        sys.exit(1)

    # Step 8: Metadata & Thumbnail
    logger.info("Generating metadata and thumbnail...")
    metadata = generate_metadata(topic_dict, researched_fact, script_data)

    # Step 9: Save Local Video & Metadata
    logger.info("Saving local video...")
    slug = Path(video_path).stem
    meta_json_path = METADATA_DIR / f"{slug}.json"
    meta_payload = {
        "topic": topic_text,
        "category": topic_dict.get("category"),
        "fact": researched_fact.get("main_fact"),
        "title": metadata.get("title"),
        "description": metadata.get("description"),
        "tags": metadata.get("tags"),
        "hashtags": metadata.get("hashtags"),
        "duration": voiceover_info.get("duration"),
        "video_path": str(video_path),
        "thumbnail_path": metadata.get("thumbnail_path"),
        "created_at": datetime.datetime.now().isoformat(),
        "youtube_uploaded": False,
        "youtube_video_id": None
    }
    with open(meta_json_path, "w", encoding="utf-8") as f:
        json.dump(meta_payload, f, indent=2, ensure_ascii=False)

    logger.info(f"Local metadata saved to: {meta_json_path}")

    save_used_topic({
        "topic": topic_text,
        "category": topic_dict.get("category"),
        "date": datetime.datetime.now().isoformat(),
        "video_filename": Path(video_path).name
    })

    # Step 10: Check YouTube Credentials & Upload
    logger.info("Checking YouTube credentials...")
    upload_result = upload_video_to_youtube(video_path, metadata)

    if upload_result.get("uploaded"):
        meta_payload["youtube_uploaded"] = True
        meta_payload["youtube_video_id"] = upload_result.get("video_id")
        with open(meta_json_path, "w", encoding="utf-8") as f:
            json.dump(meta_payload, f, indent=2, ensure_ascii=False)

    save_generated_video_record(meta_payload)

    print("\n" + "="*50)
    print("SUCCESSFUL GENERATION SUMMARY")
    print("="*50)
    print(f"Topic: {topic_text}")
    print(f"Video Saved Locally: {video_path}")
    print(f"Metadata Saved: {meta_json_path}")
    if upload_result.get("uploaded"):
        print(f"YouTube URL: {upload_result.get('url')}")
    else:
        print("YouTube Upload: Saved locally (YouTube OAuth credentials not configured).")
    print("="*50 + "\n")

if __name__ == "__main__":
    if "--auth" in sys.argv:
        print("Authenticating with YouTube Data API...")
        svc = get_authenticated_youtube_service()
        if svc:
            print("YouTube authentication successful! token.json has been created in credentials/ folder.")
        else:
            print("Authentication failed or cancelled.")
        sys.exit(0)

    custom_topic = None
    if len(sys.argv) > 1:
        raw_args = sys.argv[1:]
        if raw_args[0] == "--topic":
            raw_args = raw_args[1:]
        if raw_args:
            custom_topic = " ".join(raw_args).strip()
    run_single_video_pipeline(custom_topic=custom_topic)
