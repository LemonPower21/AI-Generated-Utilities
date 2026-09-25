from PIL import Image

# Caratteri ASCII ordinati dal più scuro al più chiaro
ASCII_CHARS = ["@", "#", "S", "%", "?", "*", "+", ";", ":", ",", "."]

def ridimensiona_immagine(immagine, nuovo_larghezza=100):
    """Ridimensiona l'immagine mantenendo le proporzioni corrette."""
    larghezza_orig, altezza_orig = immagine.size
    # I caratteri ASCII sono più alti che larghi, quindi correggiamo il rapporto d'aspetto
    rapporto_aspetto = altezza_orig / larghezza_orig / 1.65
    nuova_altezza = int(nuovo_larghezza * rapporto_aspetto)
    return immagine.resize((nuovo_larghezza, nuova_altezza))

def converti_in_scala_di_grigi(immagine):
    """Converte l'immagine in scala di grigi."""
    return immagine.convert("L")

def pixel_in_ascii(immagine):
    """Mappa ogni pixel a un carattere ASCII in base alla sua luminosità."""
    pixel_luminosita = immagine.getdata()
    caratteri = ""
    for pixel in pixel_luminosita:
        # Mappa il valore del pixel (0-255) all'indice della lista ASCII_CHARS (0-10)
        indice = pixel * len(ASCII_CHARS) // 256
        caratteri += ASCII_CHARS[indice]
    return caratteri

def immagine_a_ascii(percorso_immagine, percorso_output="output_ascii.txt", larghezza=100):
    try:
        # 1. Apertura dell'immagine
        immagine = Image.open(percorso_immagine)
    except Exception as e:
        print(f"Errore nell'apertura dell'immagine: {e}")
        return

    # 2. Elaborazione dell'immagine
    immagine = ridimensiona_immagine(immagine, larghezza)
    immagine_grigio = converti_in_scala_di_grigi(immagine)
    
    # 3. Generazione della stringa ASCII
    stringa_ascii = pixel_in_ascii(immagine_grigio)
    lunghezza_pixel = len(stringa_ascii)
    
    # Formattazione della stringa in righe basate sulla nuova larghezza
    immagine_ascii = "\n".join([stringa_ascii[index:(index + larghezza)] for index in range(0, lunghezza_pixel, larghezza)])

    # 4. Salvataggio su file di testo
    with open(percorso_output, "w") as f:
        f.write(immagine_ascii)
        
    print(f"Successo! Il file ASCII è stato salvato come: {percorso_output}")

# --- ESEMPIO DI UTILIZZO ---
# Sostituisci 'tua_foto.jpg' con il percorso reale della tua immagine
percorso_input = "picture.jpg" 
percorso_txt = "picture_ascii.txt"

# Puoi modificare la larghezza (es. 120 o 150 per immagini più grandi e dettagliate)
immagine_a_ascii(percorso_input, percorso_txt, larghezza=120)