#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AllInOne.py - YouTube Shorts / multilingual video toolkit
=========================================================

One tool, six functions (one per original script):

  Menu  Command     Original script      What it does
  ----  ----------  -------------------  -------------------------------------------------
   1    publish     Publisher.py         Upload every MP4 in VideoPronti/ as PRIVATE, scheduled one per day
   2    scale       VideoScaler.py       Cut shorts from input.mp4 using timeclock.txt: 9:16 + CapCut
                                         subtitles + optional upload + Misc/ multilingual SRT/MP3
   3    capcut      Capcutter.py         Burn CapCut-style word-by-word subtitles into a video + upload
   4    audio       AudioDownloader.py   Download tracks from YouTube and convert them to MP3
   5    shuffle     Shuffle.py           Put a random slice of a song under each video in Video/
   6    multilang   AutoPublisher.py     Translate + dub into 10 languages, multi-audio MP4,
                                         upload with localized title/description

Usage:
  python AllInOne.py                          -> interactive menu
  python AllInOne.py publish --dry-run
  python AllInOne.py scale --no-upload --no-misc
  python AllInOne.py <command> --help

Requirements:
  FFmpeg + FFprobe in PATH, and
  pip install openai-whisper edge-tts deep-translator yt-dlp google-api-python-client google-auth-oauthlib
  (libraries are imported only when the function that needs them runs)

Files used (all relative to the tool's folder, or to --workdir):
  client_secret.json, token.json          YouTube OAuth (one shared token for every function)
  title.txt, description.txt, tag.txt     metadata for capcut / multilang (and description/tag for scale)
  timeclock.txt                           segments for scale:   S:00:01:00, E:00:01:45, "Title"
  Video/ Musica/ VideoPronti/ titles.txt  shuffle -> publish pipeline
"""

import argparse
import asyncio
import glob
import importlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone, time as dtime

# ============================ CONFIGURATION ============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# One scope list for every function, so a single token.json works everywhere.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
TOKEN_FILE = "token.json"
CLIENT_SECRET_FILE = "client_secret.json"

DEFAULT_START_DATE = "2027-02-27"   # first scheduled day for `publish`

RETRY_DELAY = 5          # initial wait between retries (seconds)
RETRY_DELAY_MAX = 60     # maximum wait (progressive backoff)

# Optional: raises MyMemory limits. Can also be set with --mymemory-email or $MYMEMORY_EMAIL
MYMEMORY_EMAIL = os.environ.get("MYMEMORY_EMAIL", "")
AUTO_UPDATE_EDGE_TTS = True   # old edge-tts versions give 403; updated once per run when needed

LANGUAGES_MAP = {
    "en": "english",
    "es": "spanish",
    "pt": "portuguese",
    "de": "german",
    "fr": "french",
    "hi": "hindi",
    "ja": "japanese",
    "id": "indonesian",
    "ar": "arabic",
    "ru": "russian",
}
SOURCE_NAMES = dict(LANGUAGES_MAP, it="italian")   # names accepted for the detected source language

VOICES_MAP = {
    "ar": "ar-SA-HamedNeural",
    "de": "de-DE-ConradNeural",
    "en": "en-US-ChristopherNeural",
    "es": "es-ES-AlvaroNeural",
    "fr": "fr-FR-HenriNeural",
    "hi": "hi-IN-MadhurNeural",
    "id": "id-ID-ArdiNeural",
    "ja": "ja-JP-KeitaNeural",
    "pt": "pt-BR-AntonioNeural",
    "ru": "ru-RU-DmitryNeural",
}

DEFAULT_SONGS = [
    {"artist": "Hotham", "title": "Cruising"},
    {"artist": "Kimuor", "title": "tropical journey"},
    {"artist": "Roa", "title": "Beachside"},
    {"artist": "Aftertune", "title": "Travel"},
    {"artist": "chillity", "title": "Give Me Peace"},
    {"artist": "Oraeth", "title": "so far away"},
    {"artist": "KV", "title": "Dopamine"},
    {"artist": "Qlowdy", "title": "Jungle"},
]

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: CapCut,Impact,140,&H0000FFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,2,2,50,50,250,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


# ============================ SHARED HELPERS ============================
def need(module, pip_name=None):
    """Import a library only when a function really needs it."""
    try:
        return importlib.import_module(module)
    except ImportError:
        raise SystemExit(
            f"❌ Modulo '{module}' non installato. Installalo con:  pip install {pip_name or module}"
        )


def require_binaries(*names):
    missing = [n for n in names if shutil.which(n) is None]
    if missing:
        raise SystemExit(
            "❌ Non trovo nel PATH: " + ", ".join(missing) +
            " (installa FFmpeg e riapri il terminale)."
        )


def rimuovi_se_esiste(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def read_text_file(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content:
                return content
    return None


def split_tags(raw):
    return [t.strip() for t in (raw or "").replace("\n", ",").split(",") if t.strip()]


def sanitize_filename(name):
    """Remove characters that are not valid in file names."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()


def format_ass_time(seconds):
    """Seconds -> ASS time (H:MM:SS.cs)."""
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    centiseconds = int(td.microseconds / 10000)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


def format_srt_time(seconds):
    """Seconds -> SRT time (HH:MM:SS,ms)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def ask_yes_no(question, default=True):
    suffix = "[S/n]" if default else "[s/N]"
    answer = input(f"{question} {suffix}: ").strip().lower()
    if not answer:
        return default
    return answer in ("s", "si", "sì", "y", "yes")


# ---------------------------- ffprobe / validation ----------------------------
def _ffprobe(path):
    """ffprobe info as dict, or None if the file is unreadable/corrupt."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", path],
            capture_output=True, text=True, check=True,
        )
        return json.loads(out.stdout)
    except Exception:
        return None


def get_duration(file_path):
    """Exact duration (seconds) of a media file, or None."""
    info = _ffprobe(file_path)
    try:
        return float(info["format"]["duration"])
    except Exception:
        print(f"⚠️ Errore nel calcolo durata per {file_path}")
        return None


def media_valido(path, tipo="audio", min_audio_streams=1):
    """True if the file exists, is not empty and can be decoded."""
    if not os.path.exists(path) or os.path.getsize(path) < 1024:
        return False
    info = _ffprobe(path)
    if not info:
        return False
    try:
        durata = float(info.get("format", {}).get("duration", 0))
    except (TypeError, ValueError):
        return False
    if durata <= 0:
        return False
    streams = info.get("streams", [])
    n_audio = sum(1 for s in streams if s.get("codec_type") == "audio")
    n_video = sum(1 for s in streams if s.get("codec_type") == "video")
    if tipo == "audio":
        return n_audio >= 1
    if tipo == "video":
        return n_video >= 1 and n_audio >= min_audio_streams
    return True


def srt_valido(path):
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            contenuto = f.read()
    except Exception:
        return False
    return "-->" in contenuto and len(contenuto.strip()) > 10


# ---------------------------- retry helpers ----------------------------
class RetryExhausted(RuntimeError):
    pass


def attesa(tentativo):
    return min(RETRY_DELAY * tentativo, RETRY_DELAY_MAX)


def retry_sync(nome, funzione, validatore=None, pulizia=None, max_tentativi=0):
    """Run funzione() until it succeeds AND validatore() is True. max_tentativi=0 -> forever."""
    tentativo = 1
    while True:
        try:
            risultato = funzione()
            if validatore is None or validatore(risultato):
                if tentativo > 1:
                    print(f"✅ {nome} riuscito al tentativo {tentativo}.")
                return risultato
            print(f"⚠️ {nome}: file non valido/corrotto (tentativo {tentativo}).")
        except RetryExhausted:
            raise
        except Exception as e:
            print(f"❌ {nome} fallito (tentativo {tentativo}): {e}")
        if pulizia:
            pulizia()
        if max_tentativi and tentativo >= max_tentativi:
            raise RetryExhausted(f"{nome}: esauriti {max_tentativi} tentativi")
        pausa = attesa(tentativo)
        print(f"🔄 Riprovo '{nome}' tra {pausa} secondi...")
        time.sleep(pausa)
        tentativo += 1


async def retry_async(nome, funzione, validatore=None, pulizia=None, max_tentativi=0):
    tentativo = 1
    while True:
        try:
            risultato = await funzione()
            if validatore is None or validatore(risultato):
                if tentativo > 1:
                    print(f"✅ {nome} riuscito al tentativo {tentativo}.")
                return risultato
            print(f"⚠️ {nome}: file non valido/corrotto (tentativo {tentativo}).")
        except RetryExhausted:
            raise
        except Exception as e:
            print(f"❌ {nome} fallito (tentativo {tentativo}): {e}")
        if pulizia:
            pulizia()
        if max_tentativi and tentativo >= max_tentativi:
            raise RetryExhausted(f"{nome}: esauriti {max_tentativi} tentativi")
        pausa = attesa(tentativo)
        print(f"🔄 Riprovo '{nome}' tra {pausa} secondi...")
        await asyncio.sleep(pausa)
        tentativo += 1


# ---------------------------- Whisper ----------------------------
_WHISPER_MODELS = {}


def get_whisper(model_size="base"):
    """Load each Whisper model only once per run."""
    if model_size not in _WHISPER_MODELS:
        whisper = need("whisper", "openai-whisper")
        print(f"   -> Caricamento modello Whisper ({model_size})...")
        _WHISPER_MODELS[model_size] = whisper.load_model(model_size)
    return _WHISPER_MODELS[model_size]


def generate_capcut_ass_subtitles(video_path, model_size="base", ass_path="capcut_style.ass"):
    """
    Whisper word timestamps -> .ASS file with CapCut-like karaoke style (4 words per line).
    Returns (ass_path, whisper_result) so callers can reuse the transcript.
    """
    model = get_whisper(model_size)
    print("   -> Analisi audio e sincronizzazione parola per parola...")
    result = model.transcribe(video_path, word_timestamps=True)

    lines = [ASS_HEADER]
    for segment in result["segments"]:
        words = segment.get("words", [])
        if not words:
            continue

        chunks, current_chunk = [], []
        for word_info in words:
            current_chunk.append(word_info)
            if len(current_chunk) >= 4:
                chunks.append(current_chunk)
                current_chunk = []
        if current_chunk:
            chunks.append(current_chunk)

        for chunk in chunks:
            karaoke_text = ""
            for word_info in chunk:
                duration_centiseconds = max(0, int((word_info["end"] - word_info["start"]) * 100))
                word = word_info["word"].strip().upper()
                karaoke_text += f"{{\\k{duration_centiseconds}}}{word} "
            start_str = format_ass_time(chunk[0]["start"])
            end_str = format_ass_time(chunk[-1]["end"])
            lines.append(f"Dialogue: 0,{start_str},{end_str},CapCut,,0,0,0,,{karaoke_text.strip()}\n")

    with open(ass_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print("   -> Sottotitoli dinamici generati correttamente!")
    return ass_path, result


def render_with_subtitles(video_path, ass_path, output_path, vertical=False):
    """Re-encode audio+video with burned-in subtitles (optionally crop to 1080x1920)."""
    vf = f"ass={ass_path}"
    if vertical:
        vf = f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,{vf}"
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "192000",
        "-fps_mode", "cfr",
        output_path,
    ]
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Errore FFmpeg durante il rendering: {e}")
        return False


# ---------------------------- translation + TTS (shared by scale/Misc and multilang) ----------------------------
_EDGE_UPDATED = False


def ensure_edge_tts():
    """Update edge-tts once per run (old versions fail with 403), then import it."""
    global _EDGE_UPDATED
    if AUTO_UPDATE_EDGE_TTS and not _EDGE_UPDATED:
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-U", "-q", "edge-tts"],
                check=False, timeout=180,
            )
        except Exception as e:
            print(f"⚠️ Impossibile aggiornare edge-tts automaticamente: {e}")
        _EDGE_UPDATED = True
    return need("edge_tts", "edge-tts")


def make_translator(source_name, target_name):
    MyMemoryTranslator = need("deep_translator", "deep-translator").MyMemoryTranslator
    if MYMEMORY_EMAIL.strip():
        return MyMemoryTranslator(source=source_name, target=target_name, email=MYMEMORY_EMAIL.strip())
    return MyMemoryTranslator(source=source_name, target=target_name)


def traduci_con_retry(translator, testo, etichetta, max_tentativi=0, soft=False):
    """Translate with retries. soft=True -> if it keeps failing, keep the original text."""
    def _ok(t):
        return isinstance(t, str) and t.strip() != "" and not t.upper().startswith("MYMEMORY WARNING")

    try:
        risultato = retry_sync(f"Traduzione {etichetta}", lambda: translator.translate(testo),
                               validatore=_ok, max_tentativi=max_tentativi)
    except RetryExhausted:
        if soft:
            return testo
        raise
    time.sleep(0.1)
    return risultato


async def seleziona_voce(lang_code, edge_tts):
    """Male voice for the language: fixed map first, then search the Edge-TTS catalog."""
    if lang_code in VOICES_MAP:
        return VOICES_MAP[lang_code]
    try:
        all_voices = await edge_tts.list_voices()
        base_code = lang_code.split("-")[0].lower()
        for voice in all_voices:
            if voice["Locale"].split("-")[0].lower() == base_code and voice["Gender"] == "Male":
                return voice["ShortName"]
        for voice in all_voices:
            if voice["Locale"].split("-")[0].lower() == base_code:
                return voice["ShortName"]
    except Exception:
        pass
    return "en-US-ChristopherNeural"


def spezza_testo(testo, max_car=700):
    """Split text into short blocks on sentence ends (avoids 'No audio was received')."""
    frasi = re.split(r'(?<=[.!?؟。！？।])\s+', testo.strip())
    blocchi, corrente = [], ""
    for frase in frasi:
        frase = frase.strip()
        if not frase:
            continue
        while len(frase) > max_car:
            taglio = frase.rfind(" ", 0, max_car)
            if taglio <= 0:
                taglio = max_car
            if corrente:
                blocchi.append(corrente)
                corrente = ""
            blocchi.append(frase[:taglio].strip())
            frase = frase[taglio:].strip()
        if len(corrente) + len(frase) + 1 <= max_car:
            corrente = f"{corrente} {frase}".strip()
        else:
            if corrente:
                blocchi.append(corrente)
            corrente = frase
    if corrente:
        blocchi.append(corrente)
    return blocchi


async def genera_audio_a_blocchi(testo, voice, audio_path, lang_code, tmp_dir, edge_tts, max_tentativi=0):
    """Generate TTS block by block (each verified + retried) and concatenate into one MP3."""
    blocchi = spezza_testo(testo)
    file_blocchi = []
    lista_path = os.path.join(tmp_dir, f"_lista_{lang_code}.txt")
    try:
        for n, blocco in enumerate(blocchi):
            blocco_path = os.path.join(tmp_dir, f"_tmp_{lang_code}_{n:04d}.mp3")
            file_blocchi.append(blocco_path)

            async def _genera_blocco(b=blocco, p=blocco_path):
                await edge_tts.Communicate(b, voice).save(p)
                return p

            await retry_async(
                f"Audio {lang_code.upper()} blocco {n + 1}/{len(blocchi)}", _genera_blocco,
                validatore=lambda p: media_valido(p, "audio"),
                pulizia=lambda p=blocco_path: rimuovi_se_esiste(p),
                max_tentativi=max_tentativi,
            )

        with open(lista_path, "w", encoding="utf-8") as f:
            for p in file_blocchi:
                p_abs = os.path.abspath(p).replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{p_abs}'\n")

        rimuovi_se_esiste(audio_path)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
             "-i", lista_path, "-c", "copy", audio_path],
            check=True,
        )
        return audio_path
    finally:
        for p in file_blocchi:
            rimuovi_se_esiste(p)
        rimuovi_se_esiste(lista_path)


async def elabora_lingua(segments, lang_code, source_lang_code, srt_dir, audio_dir,
                         max_tentativi=0, soft=False):
    """
    Translate the segments into lang_code, write SRT (srt_dir) and dubbed MP3 (audio_dir).
    soft=True (used by Misc/): never abort - keep original text / skip audio if something keeps failing.
    Returns (audio_path or None, srt_path or None).
    """
    if lang_code == source_lang_code:
        return None, None

    lang_name = LANGUAGES_MAP.get(lang_code, "english")
    source_name = SOURCE_NAMES.get(source_lang_code, "italian")
    print(f"\n🌐 Elaborazione lingua: {lang_code.upper()} ({lang_name})")

    translator = make_translator(source_name, lang_name)
    pezzi_tradotti, srt_righe, n = [], [], 0

    for i, seg in enumerate(segments):
        testo_originale = seg["text"].strip()
        if not testo_originale:
            continue
        testo_tradotto = traduci_con_retry(translator, testo_originale, f"{lang_code} segmento {i}",
                                           max_tentativi, soft)
        pezzi_tradotti.append(testo_tradotto)
        n += 1
        srt_righe.append(
            f"{n}\n{format_srt_time(seg['start'])} --> {format_srt_time(seg['end'])}\n{testo_tradotto}\n\n"
        )

    os.makedirs(srt_dir, exist_ok=True)
    os.makedirs(audio_dir, exist_ok=True)

    srt_path = os.path.join(srt_dir, f"sottotitoli_{lang_code}.srt")

    def _scrivi_srt():
        with open(srt_path, "w", encoding="utf-8") as f:
            f.writelines(srt_righe)
        return srt_path

    retry_sync(f"Scrittura SRT {lang_code}", _scrivi_srt, validatore=srt_valido,
               pulizia=lambda: rimuovi_se_esiste(srt_path), max_tentativi=max_tentativi or 3)

    testo_totale = " ".join(pezzi_tradotti)
    audio_path = None
    if testo_totale.strip():
        edge_tts = ensure_edge_tts()
        audio_path = os.path.join(audio_dir, f"traccia_audio_{lang_code}.mp3")
        voice = await seleziona_voce(lang_code, edge_tts)

        async def _genera_audio():
            return await genera_audio_a_blocchi(testo_totale, voice, audio_path, lang_code,
                                                audio_dir, edge_tts, max_tentativi)
        try:
            await retry_async(
                f"Audio {lang_code.upper()}", _genera_audio,
                validatore=lambda p: media_valido(p, "audio"),
                pulizia=lambda: rimuovi_se_esiste(audio_path),
                max_tentativi=max_tentativi,
            )
            print(f"✅ {lang_code.upper()} -> Traccia audio generata e verificata!")
        except RetryExhausted as e:
            if not soft:
                raise
            print(f"⚠️ {lang_code.upper()}: audio saltato ({e})")
            audio_path = None

    await asyncio.sleep(2)
    return audio_path, srt_path


# ---------------------------- YouTube ----------------------------
_YOUTUBE = None


def get_authenticated_service():
    """OAuth2 login with a cached token.json shared by every function."""
    global _YOUTUBE
    if _YOUTUBE is not None:
        return _YOUTUBE

    Credentials = need("google.oauth2.credentials", "google-auth").Credentials
    Request = need("google.auth.transport.requests", "google-auth").Request
    flow_mod = need("google_auth_oauthlib.flow", "google-auth-oauthlib")
    discovery = need("googleapiclient.discovery", "google-api-python-client")

    if not os.path.exists(CLIENT_SECRET_FILE):
        raise FileNotFoundError(
            f"❌ File '{CLIENT_SECRET_FILE}' non trovato! "
            "Inseriscilo nella cartella principale del progetto."
        )

    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                info = json.load(f)
            # An old token with fewer scopes (e.g. upload-only) can't be reused.
            if set(SCOPES) <= set(info.get("scopes") or []):
                creds = Credentials.from_authorized_user_info(info, SCOPES)
        except Exception:
            creds = None

    changed = False
    if creds and not creds.valid and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            changed = True
        except Exception:
            creds = None

    if not creds or not creds.valid:
        flow = flow_mod.InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
        changed = True

    if changed:
        with open(TOKEN_FILE, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())

    _YOUTUBE = discovery.build("youtube", "v3", credentials=creds)
    return _YOUTUBE


def check_channel_name(youtube):
    try:
        response = youtube.channels().list(part="snippet", mine=True).execute()
        if response.get("items"):
            return response["items"][0]["snippet"]["title"]
    except Exception as e:
        print(f"⚠️ Impossibile verificare il nome del canale: {e}")
    return "Canale Sconosciuto"


def upload_video_file(youtube, video_path, body, part="snippet,status"):
    """Resumable upload with progress output. Returns the API response."""
    http = need("googleapiclient.http", "google-api-python-client")
    media = http.MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part=part, body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"   └─ Progresso caricamento: {int(status.progress() * 100)}%")
    return response


def upload_private_video(video_path, title, category_id):
    """Upload as PRIVATE using description.txt / tag.txt. Errors are printed, never fatal."""
    print("3. Preparazione caricamento su YouTube (PRIVATO)...")
    description = read_text_file("description.txt") or ""
    tags = split_tags(read_text_file("tag.txt"))
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False},
    }
    try:
        youtube = get_authenticated_service()
        print(f"Caricamento in corso di '{title}' su YouTube...")
        response = upload_video_file(youtube, video_path, body)
        print(f"\nCaricamento completato! ID Video: {response.get('id')}")
        return response
    except (Exception, SystemExit) as e:
        print(f"⚠️ Upload su YouTube non riuscito: {e}")
        return None


# ============================ 1) PUBLISH  (Publisher.py) ============================
def load_titles(titles_file):
    """Titles from titles.txt, one per line."""
    if not os.path.exists(titles_file):
        print(f"⚠️ File '{titles_file}' non trovato! Verranno usati i nomi dei file come titoli.")
        return []
    with open(titles_file, "r", encoding="utf-8") as f:
        titles = [line.strip() for line in f.readlines() if line.strip()]
    print(f"📋 Caricati {len(titles)} titoli da '{os.path.basename(titles_file)}'.\n")
    return titles


def cmd_publish(args):
    """Upload every MP4 in the folder as PRIVATE, scheduled one per day starting at --start-date."""
    video_dir = args.video_dir
    titles_file = args.titles or os.path.join(video_dir, "titles.txt")

    try:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
        hh, mm = (int(x) for x in args.time.split(":"))
        publish_time = dtime(hh, mm)
    except ValueError:
        raise SystemExit("❌ Data/ora non valide. Usa --start-date AAAA-MM-GG e --time HH:MM (UTC).")

    video_files = sorted(glob.glob(os.path.join(video_dir, "*.mp4")))
    if not video_files:
        print(f"❌ Nessun video MP4 trovato nella cartella {video_dir}!")
        return

    channel = "(dry-run)"
    youtube = None
    if not args.dry_run:
        youtube = get_authenticated_service()
        channel = check_channel_name(youtube)
    print("---------------------------------------------------")
    print(f"📺 CANALE COLLEGATO: \"{channel}\"")
    print("---------------------------------------------------\n")

    titles_list = load_titles(titles_file)
    print(f"Trovati {len(video_files)} Shorts da caricare su \"{channel}\".\n")

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    for index, video_path in enumerate(video_files):
        filename = os.path.basename(video_path)

        title = titles_list[index] if index < len(titles_list) else os.path.splitext(filename)[0]
        if "#shorts" not in title.lower():
            title = f"{title} #Shorts"

        publish_datetime = datetime.combine((start_date + timedelta(days=index)).date(), publish_time)
        publish_at_iso = publish_datetime.strftime("%Y-%m-%dT%H:%M:%SZ")

        print(f"[{index + 1}/{len(video_files)}] Caricamento: {filename}")
        print(f"   ├─ Titolo: \"{title}\"")
        print(f"   └─ Programmato per: {publish_datetime.strftime('%d/%m/%Y alle %H:%M')} UTC")
        if publish_datetime <= now_utc:
            print("   ⚠️ Data nel passato: YouTube pubblicherà subito o rifiuterà la programmazione.")

        if args.dry_run:
            print("   (dry-run: nessun upload)\n")
            continue

        body = {
            "snippet": {
                "title": title,
                "description": f"{title}\n\n#Shorts #Travel #Viaggi",
                "tags": ["Shorts", "Travel", "Viaggi", "TravelShorts"],
                "categoryId": args.category,
            },
            "status": {
                "privacyStatus": "private",   # must be private for scheduling via publishAt
                "publishAt": publish_at_iso,
                "selfDeclaredMadeForKids": False,
            },
        }
        upload_video_file(youtube, video_path, body)
        print("   ✓ Caricato con successo!\n")

    if args.dry_run:
        print("🧪 Dry-run completato: nessun video è stato caricato.")
    else:
        print(f"🎉 Tutti i video sono stati caricati e programmati su \"{channel}\"!")


# ============================ 2) SCALE  (VideoScaler.py) ============================
def parse_timeclock(timeclock_path):
    """timeclock.txt lines:  S:00:01:00, E:00:01:45, "Title"  ->  [(start, end, title), ...]"""
    segments = []
    if not os.path.exists(timeclock_path):
        print(f"Attenzione: Il file '{timeclock_path}' non è stato trovato.")
        return segments
    with open(timeclock_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                parts = line.split(",", 2)
                start_str = parts[0].replace("S:", "").strip()
                end_str = parts[1].replace("E:", "").strip()
                title = parts[2].strip().strip("\"'")
                segments.append((start_str, end_str, title))
            except Exception as e:
                print(f"Errore nel parsing della riga '{line}': {e}")
    return segments


async def genera_misc_folder(transcript_result, source_lang, safe_title, misc_root):
    """Misc/<title>/ with SRT + dubbed MP3 for every language (reuses the short's transcript)."""
    print(f"   -> Generazione risorse multilingua (Misc) per: {safe_title}")
    misc_dir = os.path.join(misc_root, safe_title)
    os.makedirs(misc_dir, exist_ok=True)
    segments = transcript_result["segments"]

    for lang_code in LANGUAGES_MAP:
        try:
            await elabora_lingua(segments, lang_code, source_lang, misc_dir, misc_dir,
                                 max_tentativi=3, soft=True)
        except Exception as e:
            print(f"   ⚠️ Lingua {lang_code} saltata: {e}")
    print(f"   -> Risorse multilingua salvate in: '{misc_dir}'")


def process_short_clip(input_video, start_time, end_time, title, output_path, safe_title, args):
    """Cut -> subtitles -> 9:16 render -> (upload) -> (Misc folder)."""
    print(f"\n[ELABORAZIONE SHORT] \"{title}\" (Da {start_time} a {end_time})")
    temp_clip = "temp_cut.mp4"
    ass_file, result, ok = None, None, False

    try:
        print("1. Taglio del segmento dal video originale...")
        subprocess.run(
            ["ffmpeg", "-y", "-i", input_video, "-ss", start_time, "-to", end_time,
             "-c:v", "libx264", "-c:a", "aac", temp_clip],
            check=True,
        )
        ass_file, result = generate_capcut_ass_subtitles(temp_clip, model_size=args.model)
        print("2. Rendering in formato 9:16 e masterizzazione sottotitoli...")
        ok = render_with_subtitles(temp_clip, ass_file, output_path, vertical=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Errore FFmpeg durante il taglio: {e}")
    finally:
        rimuovi_se_esiste(temp_clip)
        rimuovi_se_esiste(ass_file)

    if not ok:
        print("⚠️ Short saltato.")
        return

    print(f"Short salvato con successo in: {output_path}")

    if not args.no_upload:
        upload_private_video(output_path, title, args.category)

    if not args.no_misc:
        source_lang = result.get("language", "it")
        asyncio.run(genera_misc_folder(result, source_lang, safe_title, args.misc_dir))


def cmd_scale(args):
    """Cut shorts from a long video using timeclock.txt."""
    require_binaries("ffmpeg")
    if not os.path.exists(args.input):
        print(f"Errore: Il file video '{args.input}' non è presente nella cartella.")
        return

    segments = parse_timeclock(args.timeclock)
    if not segments:
        print(f"Nessun intervallo trovato in {args.timeclock}.")
        return

    os.makedirs(args.out_dir, exist_ok=True)
    if not args.no_misc:
        os.makedirs(args.misc_dir, exist_ok=True)

    print(f"Trovati {len(segments)} segmenti da elaborare.")
    for index, (start, end, title) in enumerate(segments, start=1):
        safe_title = sanitize_filename(title) or f"short_{index}"
        output_path = os.path.join(args.out_dir, f"{safe_title}.mp4")
        process_short_clip(args.input, start, end, title, output_path, safe_title, args)

    print("\nTutti gli shorts sono stati elaborati!")


# ============================ 3) CAPCUT  (Capcutter.py) ============================
def cmd_capcut(args):
    """CapCut-style subtitles burned into one video (+ optional vertical crop) and upload."""
    require_binaries("ffmpeg")
    if not os.path.exists(args.input):
        print(f"Assicurati che il file '{args.input}' sia presente nella cartella.")
        return

    print(f"1. Generazione sottotitoli per '{args.input}'...")
    ass_file = None
    try:
        ass_file, _ = generate_capcut_ass_subtitles(args.input, model_size=args.model)
        print("2. Rendering e sincronizzazione audio/video in corso...")
        ok = render_with_subtitles(args.input, ass_file, args.output, vertical=args.vertical)
    finally:
        rimuovi_se_esiste(ass_file)

    if not ok:
        return
    print(f"\nVideo renderizzato con successo in: {args.output}")

    if not args.no_upload:
        title = read_text_file("title.txt") or "Video Generato"
        upload_private_video(args.output, title, args.category)


# ============================ 4) AUDIO  (AudioDownloader.py) ============================
def parse_songs_file(path):
    """One song per line:  Artist - Title   (lines starting with # are ignored)."""
    songs = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if " - " in line:
                artist, title = line.split(" - ", 1)
                songs.append({"artist": artist.strip(), "title": title.strip()})
            else:
                songs.append({"artist": "", "title": line})
    return songs


def cmd_audio(args):
    """Download each song from YouTube search and convert to MP3."""
    require_binaries("ffmpeg")
    yt_dlp = need("yt_dlp", "yt-dlp")

    songs = DEFAULT_SONGS
    if args.songs_file:
        if not os.path.exists(args.songs_file):
            print(f"❌ File '{args.songs_file}' non trovato.")
            return
        songs = parse_songs_file(args.songs_file)
        if not songs:
            print(f"❌ Nessuna canzone valida in '{args.songs_file}'.")
            return

    os.makedirs(args.out_dir, exist_ok=True)

    ydl_opts = {
        # lightest MP4 available (<= 480p), then audio extracted to MP3
        "format": "b[ext=mp4][height<=480]/w[ext=mp4]/b",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "outtmpl": os.path.join(args.out_dir, "%(title)s.%(ext)s"),
        "quiet": False,
        "no_warnings": True,
        # avoids HTTP 403 Forbidden
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
        "http_headers": {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
        },
    }

    print("--- Download MP4 leggero -> Conversione MP3 -> Elimina MP4 ---\n")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for index, song in enumerate(songs, 1):
            name = f"{song['artist']} {song['title']}".strip()
            query = f"ytsearch1:{name} {args.suffix}".strip()
            print(f"[{index}/{len(songs)}] Download e conversione in MP3: {name}...")
            try:
                ydl.download([query])
                print("✓ Convertito in MP3 (MP4 rimosso).\n")
            except Exception as e:
                print(f"❌ Errore su {song['title']}: {e}\n")

    print(f"🎉 Operazione completata! Nella cartella '{args.out_dir}' trovi i file .mp3")


# ============================ 5) SHUFFLE  (Shuffle.py) ============================
def cmd_shuffle(args):
    """Add one song (cycled) starting at a random second to every MP4 in the video folder."""
    require_binaries("ffmpeg", "ffprobe")
    os.makedirs(args.out_dir, exist_ok=True)

    video_files = sorted(glob.glob(os.path.join(args.video_dir, "*.mp4")))
    musica_files = sorted(glob.glob(os.path.join(args.music_dir, "*.mp3")))

    if not video_files:
        print(f"❌ Nessun video trovato nella cartella {args.video_dir}!")
        return
    if not musica_files:
        print(f"❌ Nessun file audio trovato nella cartella {args.music_dir}!")
        return

    print(f"Trovati {len(video_files)} video e {len(musica_files)} tracce audio.\n")

    for i, video_path in enumerate(video_files):
        audio_path = musica_files[i % len(musica_files)]
        nome_video = os.path.basename(video_path)
        nome_audio = os.path.basename(audio_path)
        output_path = os.path.join(args.out_dir, nome_video)

        video_duration = get_duration(video_path)
        audio_duration = get_duration(audio_path)

        start_time = 0.0
        if video_duration and audio_duration and audio_duration > video_duration:
            start_time = random.uniform(0, audio_duration - video_duration)

        dur_txt = f"{audio_duration:.2f}s" if audio_duration else "n/d"
        print(f"[{i + 1}/{len(video_files)}] Elaborazione: {nome_video}")
        print(f"   ├─ Musica: {nome_audio}")
        print(f"   └─ Inizio audio casuale: {start_time:.2f}s (su {dur_txt} totali)")
        if video_duration and audio_duration and audio_duration < video_duration:
            print("   ⚠️ La canzone è più corta del video: il video verrà tagliato alla fine dell'audio.")

        # -ss before the 2nd -i = audio start point; -c:v copy = video not re-encoded;
        # -shortest = audio cut to the video length
        command = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-ss", f"{start_time:.2f}",
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            output_path,
        ]
        try:
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"   ✓ Salvato in {args.out_dir}!\n")
        except subprocess.CalledProcessError as e:
            print(f"   ❌ Errore durante l'elaborazione di {nome_video}: {e}\n")

    print(f"🎉 Processo completato! Tutti i video si trovano in:\n{os.path.abspath(args.out_dir)}")


# ============================ 6) MULTILANG  (AutoPublisher.py) ============================
def estrai_audio(video_path, audio_output="temp_audio.mp3", max_tentativi=0):
    print("⏳ Estrazione dell'audio dal video...")

    def _estrai():
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", video_path,
             "-vn", "-acodec", "libmp3lame", "-q:a", "2", audio_output],
            check=True,
        )
        return audio_output

    retry_sync("Estrazione audio", _estrai, validatore=lambda p: media_valido(p, "audio"),
               pulizia=lambda: rimuovi_se_esiste(audio_output), max_tentativi=max_tentativi)
    print("✅ Audio estratto.")
    return audio_output


def trascrivi_audio(audio_path, model_size="base", max_tentativi=0):
    print("🤖 Trascrizione e analisi in corso con Whisper...")
    result = retry_sync(
        "Trascrizione Whisper", lambda: get_whisper(model_size).transcribe(audio_path),
        validatore=lambda r: bool(r) and isinstance(r.get("segments"), list),
        max_tentativi=max_tentativi,
    )
    source_lang = result.get("language", "it")
    print(f"✅ Trascrizione completata. Lingua sorgente rilevata: '{source_lang.upper()}'")
    return result, source_lang


def assembla_video_multilingua(video_originale, tracce_audio, output, source_lang, max_tentativi=0):
    """Original video + one extra audio track per language (video stream copied)."""
    print("\n🎞️ Assemblaggio del video multilingua con FFmpeg...")
    cmd = ["ffmpeg", "-y", "-i", video_originale]
    lang_codes = []
    for lang, audio_path in tracce_audio.items():
        cmd.extend(["-i", audio_path])
        lang_codes.append(lang)

    cmd.extend(["-map", "0:v", "-map", "0:a"])
    for idx in range(1, len(lang_codes) + 1):
        cmd.extend(["-map", f"{idx}:a"])
    cmd.extend(["-c:v", "copy", "-c:a", "aac"])
    cmd.extend(["-metadata:s:a:0", f"language={source_lang}"])
    for idx, lang in enumerate(lang_codes, start=1):
        cmd.extend([f"-metadata:s:a:{idx}", f"language={lang}"])
    cmd.append(output)

    def _assembla():
        subprocess.run(cmd, check=True)
        return output

    retry_sync("Assemblaggio FFmpeg", _assembla,
               validatore=lambda p: media_valido(p, "video", min_audio_streams=len(lang_codes) + 1),
               pulizia=lambda: rimuovi_se_esiste(output), max_tentativi=max_tentativi)
    print(f"✅ Video multilingua generato e verificato: '{output}'")


def pubblica_multilingua(video_da_caricare, max_tentativi=0):
    """Read title/tag/description (Italian), translate them and upload as PRIVATE with localizations."""
    print("\n🚀 Preparazione dei metadati multilingua e dei file per YouTube...")

    titolo_it = read_text_file("title.txt") or "Video Automatico"
    tags_list = split_tags(read_text_file("tag.txt") or "Shorts, Video")
    descrizione_it = read_text_file("description.txt") or "Descrizione del video."

    localizations = {}
    for code, lang_name in LANGUAGES_MAP.items():
        translator = make_translator("italian", lang_name)
        localizations[code] = {
            "title": traduci_con_retry(translator, titolo_it, f"titolo {lang_name}", max_tentativi),
            "description": traduci_con_retry(translator, descrizione_it, f"descrizione {lang_name}",
                                             max_tentativi),
        }
        time.sleep(0.1)

    try:
        youtube = get_authenticated_service()
        body = {
            "snippet": {
                "title": titolo_it,
                "description": descrizione_it,
                "tags": tags_list,
                "defaultLanguage": "it",
                "categoryId": "22",
            },
            "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False},
            "localizations": localizations,
        }

        def _carica():
            print(f"📤 Caricamento in corso di '{video_da_caricare}' come PRIVATO con metadati multilingua...")
            return upload_video_file(youtube, video_da_caricare, body, part="snippet,status,localizations")

        retry_sync("Upload YouTube", _carica,
                   validatore=lambda r: isinstance(r, dict) and "id" in r, max_tentativi=max_tentativi)

        print("🎉 Video pubblicato con successo come PRIVATO su YouTube con titolo e descrizione tradotti!")
        print("ℹ️ Le tracce audio generate sono nella cartella Audio/, pronte per essere aggiunte "
              "manualmente da YouTube Studio.")
    except (Exception, SystemExit) as e:
        print(f"⚠️ Impossibile completare l'upload automatico su YouTube: {e}")
        print("📁 I file multimediali, le tracce audio e i sottotitoli sono comunque salvi nelle cartelle locali.")


def cmd_multilang(args):
    """Transcribe -> translate -> dub in 10 languages -> multi-audio MP4 -> upload."""
    require_binaries("ffmpeg", "ffprobe")
    if not os.path.exists(args.video):
        print(f"❌ Errore: Il file '{args.video}' non esiste.")
        return

    info = _ffprobe(args.video)
    if not info or not any(s.get("codec_type") == "audio" for s in info.get("streams", [])):
        print(f"❌ Il file '{args.video}' non contiene una traccia audio leggibile.")
        return

    os.makedirs(args.audio_dir, exist_ok=True)
    os.makedirs(args.sub_dir, exist_ok=True)
    mt = args.max_retries

    audio_file = estrai_audio(args.video, max_tentativi=mt)
    transcript_result, source_lang = trascrivi_audio(audio_file, args.model, mt)
    segments = transcript_result["segments"]

    async def _tutte_le_lingue():
        tracce = {}
        for lang_code in LANGUAGES_MAP:
            audio_p, _sub = await elabora_lingua(segments, lang_code, source_lang,
                                                 args.sub_dir, args.audio_dir, max_tentativi=mt)
            if audio_p:
                tracce[lang_code] = audio_p
        return tracce

    try:
        tracce_audio = asyncio.run(_tutte_le_lingue())
    finally:
        rimuovi_se_esiste(audio_file)

    video_da_caricare = args.video
    if tracce_audio:
        assembla_video_multilingua(args.video, tracce_audio, args.output, source_lang, mt)
        video_da_caricare = args.output

    print(f"\n🎉 File salvati nelle cartelle dedicate: '{args.audio_dir}/' e '{args.sub_dir}/'")

    if args.no_upload:
        print("⏭️ Upload su YouTube saltato (--no-upload).")
    else:
        pubblica_multilingua(video_da_caricare, mt)


# ============================ CLI + MENU ============================
MENU = {
    "1": ("publish",   "Programma e carica gli Shorts di VideoPronti/ (Publisher)"),
    "2": ("scale",     "Ritaglia Shorts 9:16 da input.mp4 con sottotitoli + Misc (VideoScaler)"),
    "3": ("capcut",    "Sottotitoli stile CapCut su un video + upload (Capcutter)"),
    "4": ("audio",     "Scarica musica da YouTube in MP3 (AudioDownloader)"),
    "5": ("shuffle",   "Aggiungi musica casuale ai video in Video/ (Shuffle)"),
    "6": ("multilang", "Doppiaggio/sottotitoli in 10 lingue + upload (AutoPublisher)"),
}


def build_parser():
    p = argparse.ArgumentParser(
        prog="AllInOne",
        description="Toolkit all-in-one per Shorts e video multilingua. Senza comando apre il menu.",
        epilog="Le opzioni globali (--workdir, ...) vanno prima del comando.",
    )
    p.add_argument("--workdir", default=BASE_DIR,
                   help="cartella di lavoro con video, txt e client_secret.json (default: cartella dello script)")
    p.add_argument("--mymemory-email", default=MYMEMORY_EMAIL,
                   help="email per aumentare i limiti di MyMemory (o variabile MYMEMORY_EMAIL)")
    p.add_argument("--no-update-edge-tts", action="store_true",
                   help="non aggiornare edge-tts con pip prima dell'uso")
    sub = p.add_subparsers(dest="cmd", metavar="comando")

    s = sub.add_parser("publish", help=MENU["1"][1])
    s.add_argument("--video-dir", default="VideoPronti")
    s.add_argument("--titles", default=None, help="file titoli (default: <video-dir>/titles.txt)")
    s.add_argument("--start-date", default=DEFAULT_START_DATE, help="primo giorno, AAAA-MM-GG")
    s.add_argument("--time", default="00:00", help="ora di pubblicazione UTC, HH:MM")
    s.add_argument("--category", default="19", help="categoryId YouTube (19 = Travel & Events)")
    s.add_argument("--dry-run", action="store_true", help="mostra il calendario senza caricare nulla")
    s.set_defaults(func=cmd_publish)

    s = sub.add_parser("scale", help=MENU["2"][1])
    s.add_argument("--input", default="input.mp4")
    s.add_argument("--timeclock", default="timeclock.txt")
    s.add_argument("--out-dir", default="Shorts")
    s.add_argument("--misc-dir", default="Misc")
    s.add_argument("--model", default="base", help="modello Whisper (tiny/base/small/medium/large)")
    s.add_argument("--category", default="28", help="categoryId YouTube (28 = Tecnologia)")
    s.add_argument("--no-upload", action="store_true", help="non caricare su YouTube")
    s.add_argument("--no-misc", action="store_true", help="non generare la cartella Misc multilingua")
    s.set_defaults(func=cmd_scale)

    s = sub.add_parser("capcut", help=MENU["3"][1])
    s.add_argument("--input", default="input.mp4")
    s.add_argument("--output", default="output_verticale_capcut.mp4")
    s.add_argument("--model", default="base")
    s.add_argument("--category", default="22", help="categoryId YouTube (22 = People & Blogs)")
    s.add_argument("--vertical", action="store_true", help="ritaglia anche in 9:16 (1080x1920)")
    s.add_argument("--no-upload", action="store_true")
    s.set_defaults(func=cmd_capcut)

    s = sub.add_parser("audio", help=MENU["4"][1])
    s.add_argument("--out-dir", default="RFM_Travel_Music")
    s.add_argument("--songs-file", default=None, help="file con una canzone per riga: Artista - Titolo")
    s.add_argument("--suffix", default="RFM NCM", help="testo aggiunto alla ricerca YouTube")
    s.set_defaults(func=cmd_audio)

    s = sub.add_parser("shuffle", help=MENU["5"][1])
    s.add_argument("--video-dir", default="Video")
    s.add_argument("--music-dir", default="Musica")
    s.add_argument("--out-dir", default="VideoPronti")
    s.set_defaults(func=cmd_shuffle)

    s = sub.add_parser("multilang", help=MENU["6"][1])
    s.add_argument("--video", default="video.mp4")
    s.add_argument("--output", default="video_multilingua.mp4")
    s.add_argument("--audio-dir", default="Audio")
    s.add_argument("--sub-dir", default="Sottotitoli")
    s.add_argument("--model", default="base")
    s.add_argument("--max-retries", type=int, default=0,
                   help="tentativi massimi per ogni passo (0 = riprova all'infinito, come l'originale)")
    s.add_argument("--no-upload", action="store_true")
    s.set_defaults(func=cmd_multilang)

    return p


def apply_globals(args):
    global MYMEMORY_EMAIL, AUTO_UPDATE_EDGE_TTS
    MYMEMORY_EMAIL = args.mymemory_email or ""
    AUTO_UPDATE_EDGE_TTS = not args.no_update_edge_tts
    os.chdir(os.path.abspath(args.workdir))


def run_command(args, keep_going=False):
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\n⏹️ Interrotto dall'utente.")
    except (Exception, SystemExit) as e:
        if not keep_going:
            raise
        print(e)


def menu(parser, base_argv):
    while True:
        print("\n" + "=" * 62)
        print("  ALL-IN-ONE  -  Shorts & Video Toolkit")
        print("=" * 62)
        for key, (_cmd, text) in MENU.items():
            print(f"  {key}) {text}")
        print("  0) Esci")
        choice = input("\nScelta: ").strip()
        if choice in ("0", "q", "Q"):
            return
        if choice not in MENU:
            continue

        cmd = MENU[choice][0]
        extra = [cmd]
        if cmd == "publish":
            d = input(f"Data di inizio [{DEFAULT_START_DATE}]: ").strip()
            if d:
                extra += ["--start-date", d]
            if ask_yes_no("Solo anteprima del calendario (dry-run)?", False):
                extra.append("--dry-run")
        elif cmd in ("scale", "capcut", "multilang"):
            if not ask_yes_no("Caricare su YouTube (privato)?", True):
                extra.append("--no-upload")

        args = parser.parse_args(base_argv + extra)
        apply_globals(args)
        run_command(args, keep_going=True)


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not args.cmd:
        menu(parser, sys.argv[1:])
        return
    apply_globals(args)
    run_command(args)


if __name__ == "__main__":
    main()
