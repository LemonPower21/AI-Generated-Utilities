import yt_dlp
import sys
import os


def download_youtube_channel_videos(channel_url):
    """
    Scarica tutti i video da un canale YouTube.

    Args:
        channel_url (str): L'URL del canale YouTube.
    """
    
    # Crea una cartella per i video scaricati
    channel_name = channel_url.split('/')[-1]
    download_folder = f"video_del_canale_{channel_name}"
    
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)

    # Opzioni di yt-dlp per il download
    # 'best' significa la migliore qualità video e audio
    # 'format' serve a specificare la qualità video e audio da scaricare
    # 'outtmpl' è il nome del file di output e dove viene salvato
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
        'outtmpl': os.path.join(download_folder, '%(title)s.%(ext)s'),
        'merge_output_format': 'mp4'
    }

    try:
        # Crea un'istanza di YoutubeDL con le opzioni specificate
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Sto per scaricare i video dal canale: {channel_url}")
            
            # Scarica la playlist (il canale è visto come una playlist da yt-dlp)
            ydl.download([channel_url])
            
        print("Download completato!")

    except Exception as e:
        print(f"Si è verificato un errore: {e}")
        sys.exit(1)

if __name__ == "__main__":
    youtube_channel_url = input("Inserisci l'URL del canale YouTube: ")
    
    # Controlla se l'URL è valido
    if not youtube_channel_url.startswith("https://www.youtube.com/"):
        print("URL non valido. Assicurati che sia un URL di un canale YouTube.")
    else:
        download_youtube_channel_videos(youtube_channel_url)