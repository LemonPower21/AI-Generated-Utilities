from PIL import Image
import itertools
import re

# Caratteri ASCII ordinati dal più scuro al più chiaro
ASCII_CHARS = ["@", "#", "S", "%", "?", "*", "+", ";", ":", ",", "."]

def immagine_a_ascii(percorso_immagine="picture.jpg", percorso_output="picture_ascii.txt"):
    try:
        immagine = Image.open(percorso_immagine)
    except Exception as e:
        print(f"Errore nell'apertura dell'immagine: {e}")
        return

    # 1. Preleviamo le dimensioni originali esatte dell'immagine
    larghezza_orig, altezza_orig = immagine.size
    
    # Calcoliamo l'altezza della griglia ASCII compensando il fattore d'altezza dei caratteri (~1.65)
    nuova_altezza = int(altezza_orig / 1.65)
    
    # 2. Convertiamo in scala di grigi e ridimensioniamo alla risoluzione nativa proporzionata
    immagine_grigio = immagine.convert("L").resize((larghezza_orig, nuova_altezza), Image.Resampling.LANCZOS)
    
    # 3. Mappatura dei pixel in caratteri ASCII
    pixel_luminosita = immagine_grigio.getdata()
    caratteri = ""
    for pixel in pixel_luminosita:
        indice = pixel * len(ASCII_CHARS) // 256
        caratteri += ASCII_CHARS[indice]
        
    lunghezza_pixel = len(caratteri)
    
    # Suddivisione in righe basata sulla larghezza originale
    righe = [caratteri[index:(index + larghezza_orig)] for index in range(0, lunghezza_pixel, larghezza_orig)]
    
    # 4. Compressione Run-Length (soglia >= 4 caratteri uguali consecutivi)
    righe_compresse = []
    for riga in righe:
        riga_comp = []
        for char, group in itertools.groupby(riga):
            count = len(list(group))
            if count >= 4:
                riga_comp.append(f"${count}${char}")
            else:
                riga_comp.append(char * count)
        righe_compresse.append("".join(riga_comp))
        
    immagine_ascii = "\n".join(righe_compresse)

    # 5. Salvataggio su file
    with open(percorso_output, "w", encoding="utf-8") as f:
        f.write(immagine_ascii)
        
    print(f"\nSuccesso! File ASCII creato con risoluzione nativa ({larghezza_orig}x{nuova_altezza}) e salvato come: {percorso_output}")

def decomprimi_riga_ascii(riga):
    """Decomprime una riga nel formato $N$char ricostruendo la sequenza originale."""
    pattern = r'\$(\d+)\$(.)'
    def sostituisci(match):
        return match.group(2) * int(match.group(1))
    return re.sub(pattern, sostituisci, riga)

def ascii_a_immagine(percorso_txt="picture_ascii.txt", percorso_output="fot.jpg", percorso_originale="picture.jpg"):
    try:
        with open(percorso_txt, "r", encoding="utf-8") as f:
            righe_compresse = f.read().splitlines()
    except Exception as e:
        print(f"Errore nell'apertura del file di testo: {e}")
        return

    righe_decompresse = [decomprimi_riga_ascii(riga) for riga in righe_compresse]
    
    if not righe_decompresse:
        print("Il file ASCII è vuoto.")
        return

    altezza_griglia = len(righe_decompresse)
    larghezza_griglia = len(righe_decompresse[0])
    
    dati_pixel = []
    mappa_caratteri = {char: int(i * 255 / (len(ASCII_CHARS) - 1)) for i, char in enumerate(ASCII_CHARS)}
    
    for riga in righe_decompresse:
        for char in riga.ljust(larghezza_griglia, '.'):
            dati_pixel.append(mappa_caratteri.get(char, 128))

    # Creazione dell'immagine intermedia dai dati ASCII
    nuova_img = Image.new("L", (larghezza_griglia, altezza_griglia))
    nuova_img.putdata(dati_pixel)
    
    # Recuperiamo le dimensioni esatte dell'immagine originale per fare il match perfetto
    try:
        img_orig = Image.open(percorso_originale)
        dimensione_esatta = img_orig.size  # (larghezza, altezza) originali
    except Exception:
        dimensione_esatta = (larghezza_griglia, int(altezza_griglia * 1.65))

    # Riportiamo l'immagine esattamente alle dimensioni e proporzioni originali
    img_finale = nuova_img.resize(dimensione_esatta, Image.Resampling.BICUBIC)
    
    img_finale.save(percorso_output, quality=95)
    print(f"\nSuccesso! L'immagine è stata generata con dimensioni identiche all'originale e salvata come: {percorso_output}")

# --- MENU INTERATTIVO ---
if __name__ == "__main__":
    print("Scegli un'operazione:")
    print("1) Comprimi (legge le dimensioni native di picture.jpg)")
    print("2) Genera fot.jpg (ripristina la risoluzione originale)")
    
    scelta = input("\nInserisci il numero dell'operazione desiderata (1 o 2): ").strip()
    
    if scelta == "1":
        immagine_a_ascii("picture.jpg", "picture_ascii.txt")
    elif scelta == "2":
        ascii_a_immagine("picture_ascii.txt", "fot.jpg", "picture.jpg")
    else:
        print("Scelta non valida. Esegui nuovamente lo script e seleziona 1 o 2.")
