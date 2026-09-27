import os
import time
import asyncio
from deep_translator import MyMemoryTranslator
import whisper
import edge_tts
from moviepy.video.io.VideoFileClip import VideoFileClip

# ==================== CONFIGURAZIONE ====================
VIDEO_PATH = "video.mp4"  # Inserisci il nome o il percorso del tuo file video

# Mappatura delle lingue con i nomi completi richiesti da MyMemoryTranslator
LANGUAGES_MAP = {
    "en": "english",
    "fr": "french",
    "es": "spanish",
    "pt": "portuguese",
    "ru": "russian",
    "zh-CN": "chinese simplified"
}

AUDIO_OUTPUT_DIR = "output_6_lingue"
os.makedirs(AUDIO_OUTPUT_DIR, exist_ok=True)
# ========================================================

def estrai_audio(video_path, audio_output="temp_audio.mp3"):
    """Estrae la traccia audio dal video."""
    print("⏳ Estrazione dell'audio dal video in corso...")
    video = VideoFileClip(video_path)
    video.audio.write_audiofile(audio_output, codec='mp3')
    video.close()
    print("✅ Audio estratto con successo.")
    return audio_output

def trascrivi_audio(audio_path):
    """Trascrive l'audio usando OpenAI Whisper."""
    print("🤖 Trascrizione e generazione dei timestamp con Whisper (può richiedere qualche minuto)...")
    model = whisper.load_model("base")
    result = model.transcribe(audio_path)
    print("✅ Trascrizione completata.")
    return result

async def genera_audio_tradotto(text, lang_code, output_filename):
    """Genera il file audio TTS usando voci maschili native pure."""
    # Voci maschili native di alta qualità per ciascuna lingua
    voices = {
        "en": "en-US-ChristopherNeural",  # Inglese maschile (Stati Uniti)
        "fr": "fr-FR-HenriNeural",        # Francese maschile (Francia)
        "es": "es-ES-AlvaroNeural",       # Spagnolo maschile (Spagna)
        "pt": "pt-BR-AntonioNeural",      # Portoghese maschile (Brasile)
        "ru": "ru-RU-DmitryNeural",       # Russo maschile (Russia)
        "zh-CN": "zh-CN-YunxiNeural"      # Cinese Mandarino maschile
    }
    voice = voices.get(lang_code, "en-US-ChristopherNeural")
    
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_filename)

def elabora_lingua(segments, lang_code):
    """Traduce usando MyMemoryTranslator e genera SRT e Audio con voce maschile."""
    lang_name = LANGUAGES_MAP.get(lang_code, "english")
    print(f"\n🌐 Traduzione e doppiaggio maschile nativo per: {lang_code.upper()} ({lang_name})")
    
    translator = MyMemoryTranslator(source='italian', target=lang_name)
    
    pezzi_tradotti = []
    srt_righe = []

    for i, seg in enumerate(segments):
        testo_originale = seg['text'].strip()
        if not testo_originale:
            continue
            
        testo_tradotto = testo_originale
        try:
            testo_tradotto = translator.translate(testo_originale)
            time.sleep(0.2)  # Breve pausa di cortesia
        except Exception as e:
            print(f"⚠️ Errore sul segmento {i}, tengo l'originale: {e}")
            
        pezzi_tradotti.append(testo_tradotto)
        
        start_time = format_time(seg['start'])
        end_time = format_time(seg['end'])
        srt_righe.append(f"{i + 1}\n{start_time} --> {end_time}\n{testo_tradotto}\n\n")

    # 1. Scrittura file SRT con i testi tradotti
    srt_path = os.path.join(AUDIO_OUTPUT_DIR, f"sottotitoli_{lang_code}.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.writelines(srt_righe)
    print(f"📁 Sottotitoli tradotti salvati in: {srt_path}")

    # 2. Creazione traccia audio doppiata maschile
    testo_totale_tradotto = " ".join(pezzi_tradotti)
    audio_output_path = os.path.join(AUDIO_OUTPUT_DIR, f"traccia_audio_{lang_code}.mp3")
    
    try:
        asyncio.run(genera_audio_tradotto(testo_totale_tradotto, lang_code, audio_output_path))
        print(f"🎵 Traccia audio maschile in {lang_code.upper()} salvata con successo!")
    except Exception as e:
        print(f"❌ Errore nella generazione audio per {lang_code}: {e}")

def format_time(seconds):
    """Converte i secondi nel formato SRT (HH:MM:SS,ms)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

def main():
    if not os.path.exists(VIDEO_PATH):
        print(f"❌ Errore: Il file video '{VIDEO_PATH}' non è stato trovato.")
        return

    audio_file = estrai_audio(VIDEO_PATH)
    transcript_result = trascrivi_audio(audio_file)
    segments = transcript_result['segments']

    for lang_code in LANGUAGES_MAP.keys():
        elabora_lingua(segments, lang_code)

    if os.path.exists(audio_file):
        os.remove(audio_file)

    print(f"\n🎉 Processo completato! Trovi tutto nella cartella: '{AUDIO_OUTPUT_DIR}'")

if __name__ == "__main__":
    main()