import os

def split_file(input_file, chunk_size_mb=20):
    # Converte i MB in byte
    chunk_size = chunk_size_mb * 1024 * 1024
    
    # Crea una cartella di output per non intasare la directory corrente
    output_dir = "split_files"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    file_number = 1
    try:
        with open(input_file, 'rb') as f:  # Leggiamo in modalità binaria per sicurezza
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break  # Fine del file
                
                output_filename = os.path.join(output_dir, f"part_{file_number}.txt")
                with open(output_filename, 'wb') as chunk_file:
                    chunk_file.write(chunk)
                
                print(f"Creato: {output_filename}")
                file_number += 1
                
        print(f"\nOperazione completata! Il file è stato diviso in {file_number - 1} parti.")
        
    except FileNotFoundError:
        print("Errore: Il file specificato non esiste.")

# Utilizzo
split_file("rockyou.txt")