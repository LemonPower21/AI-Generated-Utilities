import os
import time
from deep_translator import MyMemoryTranslator

# ==================== CONFIGURAZIONE ====================
# Inserisci qui il tuo testo in formato Unicode (supporta qualsiasi carattere, emoji o lingua)
TESTO_ORIGINALE = """
Ciao a tutti! Benvenuti in questo nuovo video. 
Oggi scopriremo come automatizzare la creazione di contenuti per YouTube in modo semplice e veloce. 🚀
"""

# Le 6 lingue richieste con i nomi completi per il traduttore
LANGUAGES_MAP = {
    "Inglese (EN)": "english",
    "Francese (FR)": "french",
    "Spagnolo (ES)": "spanish",
    "Portoghese (PT)": "portuguese",
    "Russo (RU)": "russian",
    "Cinese Mandarino (ZH)": "chinese simplified"
}

OUTPUT_DIR = "output_traduzioni"
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "traduzioni_output.txt")
# ========================================================

def traduci_e_salva():
    print(f"📝 Testo originale:\n{TESTO_ORIGINALE.strip()}\n")
    print("=" * 50)
    
    linee_file = []
    linee_file.append(f"TESTO ORIGINALE:\n{TESTO_ORIGINALE.strip()}\n")
    linee_file.append("=" * 50 + "\n")
    
    for nome_lingua, target_lang in LANGUAGES_MAP.items():
        try:
            translator = MyMemoryTranslator(source='italian', target=target_lang)
            testo_tradotto = translator.translate(TESTO_ORIGINALE)
            
            # Mostra a schermo
            print(f"\n🌐 {nome_lingua}:")
            print(testo_tradotto)
            
            # Prepara il blocco da scrivere nel file
            linee_file.append(f"[{nome_lingua}]\n{testo_tradotto}\n\n")
            
            time.sleep(0.3)  # Breve pausa di cortesia
        except Exception as e:
            errore_msg = f"⚠️ Errore durante la traduzione: {e}"
            print(f"\n🌐 {nome_lingua}:")
            print(errore_msg)
            linee_file.append(f"[{nome_lingua}]\n{errore_msg}\n\n")
            
    # Salvataggio sicuro in formato Unicode (UTF-8)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.writelines(linee_file)
        
    print("\n" + "=" * 50)
    print(f"🎉 Traduzioni completate e salvate con successo in: '{OUTPUT_FILE}'")

if __name__ == "__main__":
    traduci_e_salva()
