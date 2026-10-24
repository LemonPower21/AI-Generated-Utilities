# AllInOne.py — Documentazione

Toolkit unico per produrre, sottotitolare, doppiare e pubblicare Shorts su YouTube.
Riunisce in un solo file i sei script originali, ognuno diventato un comando:

| Menu | Comando     | Script originale     | Cosa fa                                                                                   |
|------|-------------|----------------------|-------------------------------------------------------------------------------------------|
| 1    | `publish`   | `Publisher.py`       | Carica i video di `VideoPronti/` come **privati e programmati**, uno al giorno            |
| 2    | `scale`     | `VideoScaler.py`     | Ritaglia Shorts 9:16 da un video lungo (`timeclock.txt`), con sottotitoli stile CapCut    |
| 3    | `capcut`    | `Capcutter.py`       | Masterizza sottotitoli stile CapCut in un video e lo carica                               |
| 4    | `audio`     | `AudioDownloader.py` | Scarica brani da YouTube e li converte in MP3                                             |
| 5    | `shuffle`   | `Shuffle.py`         | Mette una canzone (partenza casuale) sotto ogni video di `Video/`                         |
| 6    | `multilang` | `AutoPublisher.py`   | Traduce e doppia in 10 lingue, crea un MP4 multi-audio e lo carica con titolo localizzato |

---

## 1. Requisiti e installazione

**Programmi esterni** (devono essere nel `PATH`):

- **FFmpeg** e **FFprobe**. Serve FFmpeg 5.1 o più recente (viene usata l'opzione `-fps_mode`).

**Librerie Python** (Python 3.8+):

```bash
pip install openai-whisper edge-tts deep-translator yt-dlp google-api-python-client google-auth-oauthlib
```

Le librerie vengono importate solo quando serve la funzione che le usa: puoi usare `shuffle` o `publish --dry-run` anche senza aver installato Whisper o yt-dlp. Se manca un modulo, il programma stampa il comando `pip install` corretto.

| Libreria                                      | Usata da                         |
|-----------------------------------------------|----------------------------------|
| `openai-whisper`                              | `scale`, `capcut`, `multilang`   |
| `edge-tts`                                    | `scale` (Misc), `multilang`      |
| `deep-translator`                             | `scale` (Misc), `multilang`      |
| `yt-dlp`                                      | `audio`                          |
| `google-api-python-client`, `google-auth-oauthlib` | `publish`, `scale`, `capcut`, `multilang` (upload) |

Al primo utilizzo Whisper scarica il modello scelto (`base` di default).

---

## 2. Configurazione di YouTube (una sola volta)

Serve solo se vuoi caricare video. Tutti i comandi condividono lo stesso login.

1. Vai su **Google Cloud Console** e crea un progetto.
2. Abilita **YouTube Data API v3**.
3. Configura la **schermata di consenso OAuth**. Se l'app è in modalità *Test*, aggiungi il tuo account Google tra gli utenti di test.
4. Crea una credenziale **ID client OAuth** di tipo **App desktop** e scarica il file JSON.
5. Rinominalo **`client_secret.json`** e mettilo nella cartella di lavoro (di default, la cartella dello script).
6. Alla prima esecuzione che carica un video si apre il browser per il consenso. Viene creato **`token.json`**, riusato dalle volte successive.

Permessi richiesti: `youtube.upload` e `youtube.readonly` (quest'ultimo serve a leggere il nome del canale collegato).

> **Sicurezza:** `client_secret.json` e `token.json` danno accesso al tuo canale. Non condividerli e non caricarli su repository pubblici.

Se hai un vecchio `token.json` creato da uno script con meno permessi, lo strumento lo ignora e ti chiede un nuovo login una volta.

---

## 3. Come si usa

### Menu interattivo

```bash
python AllInOne.py
```

Mostra il menu con le sei funzioni. Per `publish` chiede la data di inizio e se fare solo l'anteprima (dry-run); per `scale`, `capcut` e `multilang` chiede se caricare su YouTube.

### Da riga di comando

```bash
python AllInOne.py <comando> [opzioni]
python AllInOne.py <comando> --help
```

### Opzioni globali

Vanno scritte **prima** del comando.

| Opzione                  | Descrizione                                                                                   |
|--------------------------|-----------------------------------------------------------------------------------------------|
| `--workdir CARTELLA`     | Cartella di lavoro con video, file `.txt` e `client_secret.json` (default: cartella dello script) |
| `--mymemory-email EMAIL` | Email per alzare i limiti gratuiti di MyMemory (in alternativa, variabile `MYMEMORY_EMAIL`)   |
| `--no-update-edge-tts`   | Non aggiornare `edge-tts` con pip prima dell'uso                                              |

Esempio: `python AllInOne.py --workdir D:\Progetto publish --dry-run`

Tutti i percorsi relativi nelle opzioni dei comandi sono riferiti alla cartella di lavoro.

---

## 4. I sei comandi

### 4.1 `publish` — programmazione e upload (Publisher.py)

Carica tutti gli MP4 della cartella, ordinati per nome, come video **privati con data di pubblicazione programmata**: il primo nel giorno di inizio, il secondo il giorno dopo, e così via.

```bash
python AllInOne.py publish --dry-run
python AllInOne.py publish --start-date 2027-02-27 --time 09:30
```

| Opzione        | Default          | Descrizione                                                         |
|----------------|------------------|---------------------------------------------------------------------|
| `--video-dir`  | `VideoPronti`    | Cartella con gli MP4                                                |
| `--titles`     | `<video-dir>/titles.txt` | File dei titoli, uno per riga                               |
| `--start-date` | `2027-02-27`     | Primo giorno di pubblicazione (`AAAA-MM-GG`)                        |
| `--time`       | `00:00`          | Ora di pubblicazione in **UTC** (`HH:MM`)                           |
| `--category`   | `19`             | `categoryId` YouTube (19 = Travel & Events)                         |
| `--dry-run`    | —                | Mostra il calendario senza autenticarsi né caricare nulla           |

Comportamento:

- Il titolo di ogni video è la riga corrispondente di `titles.txt`; se le righe sono meno dei video, usa il nome del file. Se manca `#Shorts`, viene aggiunto.
- Descrizione: `<titolo>` + `#Shorts #Travel #Viaggi`. Tag: `Shorts, Travel, Viaggi, TravelShorts`.
- Prima di caricare stampa il nome del canale collegato, così puoi accorgerti subito se hai fatto login con l'account sbagliato.
- Se una data programmata è nel passato, viene stampato un avviso.
- L'orario è UTC: l'Italia è UTC+1 in inverno e UTC+2 in estate.

### 4.2 `scale` — Shorts 9:16 da un video lungo (VideoScaler.py)

Per ogni riga di `timeclock.txt`: taglia il segmento, genera i sottotitoli parola per parola con Whisper, ritaglia in 1080×1920 e masterizza i sottotitoli. Poi, a scelta, carica lo short e crea la cartella `Misc` con sottotitoli e doppiaggi in altre lingue.

```bash
python AllInOne.py scale
python AllInOne.py scale --no-upload --no-misc --model small
```

| Opzione       | Default        | Descrizione                                           |
|---------------|----------------|-------------------------------------------------------|
| `--input`     | `input.mp4`    | Video sorgente                                        |
| `--timeclock` | `timeclock.txt`| File con gli intervalli                               |
| `--out-dir`   | `Shorts`       | Cartella degli short finiti                           |
| `--misc-dir`  | `Misc`         | Cartella delle risorse multilingua                    |
| `--model`     | `base`         | Modello Whisper (`tiny`, `base`, `small`, `medium`, `large`) |
| `--category`  | `28`           | `categoryId` YouTube (28 = Scienza e tecnologia)      |
| `--no-upload` | —              | Non caricare su YouTube                               |
| `--no-misc`   | —              | Non generare la cartella Misc                         |

**Formato di `timeclock.txt`** (una riga per short, `#` per i commenti):

```
# S:inizio, E:fine, "Titolo"
S:00:01:00, E:00:01:45, "Come funziona il motore"
S:00:05:10, E:00:05:58, "Il trucco che nessuno ti dice, davvero"
```

I tempi accettano il formato `HH:MM:SS` (o secondi). Il titolo può contenere virgole. Dal titolo si ricava il nome del file, togliendo i caratteri non validi (`\ / * ? : " < > |`).

**Output**

- `Shorts/<titolo>.mp4`
- `Misc/<titolo>/sottotitoli_<lingua>.srt` e `traccia_audio_<lingua>.mp3` per ogni lingua (vedi sezione 6)

L'upload è **privato** e usa il titolo di `timeclock.txt`, la descrizione di `description.txt` e i tag di `tag.txt` (se presenti). Nella cartella Misc ogni lingua ha 3 tentativi: se la traduzione continua a fallire resta il testo originale, se fallisce il doppiaggio quella traccia viene saltata. Il resto del lavoro prosegue comunque.

### 4.3 `capcut` — sottotitoli stile CapCut (Capcutter.py)

Genera i sottotitoli dinamici parola per parola, li masterizza nel video e (a scelta) lo carica come privato.

```bash
python AllInOne.py capcut --input mio_video.mp4 --vertical --no-upload
```

| Opzione       | Default                        | Descrizione                                   |
|---------------|--------------------------------|-----------------------------------------------|
| `--input`     | `input.mp4`                    | Video sorgente                                |
| `--output`    | `output_verticale_capcut.mp4`  | File di uscita                                |
| `--model`     | `base`                         | Modello Whisper                               |
| `--category`  | `22`                           | `categoryId` YouTube (22 = People & Blogs)    |
| `--vertical`  | —                              | Ritaglia anche in 9:16 (1080×1920)            |
| `--no-upload` | —                              | Non caricare su YouTube                       |

Senza `--vertical` il formato del video non viene modificato (come nello script originale). Titolo, descrizione e tag vengono letti da `title.txt`, `description.txt`, `tag.txt` (titolo di riserva: «Video Generato»).

### 4.4 `audio` — download musica (AudioDownloader.py)

Cerca ogni brano su YouTube (primo risultato), scarica una versione leggera (≤ 480p) e la converte in MP3 a 192 kbps. Il video temporaneo viene eliminato.

```bash
python AllInOne.py audio
python AllInOne.py audio --songs-file brani.txt --suffix "no copyright music"
```

| Opzione        | Default             | Descrizione                                              |
|----------------|---------------------|----------------------------------------------------------|
| `--out-dir`    | `RFM_Travel_Music`  | Cartella di destinazione degli MP3                       |
| `--songs-file` | (lista integrata)   | File con un brano per riga, formato `Artista - Titolo`   |
| `--suffix`     | `RFM NCM`           | Testo aggiunto alla ricerca YouTube                      |

Nel file dei brani le righe vuote e quelle che iniziano con `#` vengono ignorate; una riga senza ` - ` viene trattata come solo titolo. La lista integrata contiene gli 8 brani del tuo script originale.

Prima di usare un brano nei tuoi video controlla che la sua licenza lo permetta: il suffisso di ricerca non garantisce che il risultato sia libero da diritti.

### 4.5 `shuffle` — musica sotto i video (Shuffle.py)

Per ogni MP4 di `Video/` sceglie una canzone di `Musica/` (a rotazione, in ordine alfabetico) e la applica partendo da un punto casuale, in modo che copra tutta la durata del video.

```bash
python AllInOne.py shuffle
```

| Opzione       | Default        | Descrizione                         |
|---------------|----------------|-------------------------------------|
| `--video-dir` | `Video`        | Video di partenza                   |
| `--music-dir` | `Musica`       | MP3 da usare                        |
| `--out-dir`   | `VideoPronti`  | Video finiti (stesso nome del file) |

Dettagli:

- Il video non viene ricodificato (`-c:v copy`): l'operazione è veloce e senza perdita di qualità. L'audio originale viene sostituito dalla canzone, in AAC.
- Il punto di partenza è casuale tra 0 e (durata canzone − durata video).
- Se la canzone è **più corta** del video, il risultato viene tagliato alla fine dell'audio. Il programma stampa un avviso.
- L'output di `shuffle` è la cartella che `publish` legge di default.

### 4.6 `multilang` — video multilingua (AutoPublisher.py)

Flusso completo su un video con parlato:

1. estrae l'audio e lo trascrive con Whisper, rilevando la lingua;
2. per ognuna delle 10 lingue traduce i segmenti, scrive il `.srt` e genera il doppiaggio `.mp3` con una voce maschile di Edge-TTS;
3. crea un MP4 con la traccia originale più una traccia audio per lingua (video copiato, audio in AAC, lingua indicata nei metadati);
4. carica il video come **privato**, con titolo e descrizione tradotti in tutte le lingue.

```bash
python AllInOne.py multilang --video video.mp4
python AllInOne.py multilang --no-upload --max-retries 5
```

| Opzione         | Default                  | Descrizione                                                              |
|-----------------|--------------------------|--------------------------------------------------------------------------|
| `--video`       | `video.mp4`              | Video sorgente (deve avere una traccia audio)                            |
| `--output`      | `video_multilingua.mp4`  | MP4 multi-audio                                                          |
| `--audio-dir`   | `Audio`                  | Cartella dei doppiaggi                                                   |
| `--sub-dir`     | `Sottotitoli`            | Cartella dei sottotitoli                                                 |
| `--model`       | `base`                   | Modello Whisper                                                          |
| `--max-retries` | `0`                      | Tentativi massimi per ogni passo; `0` = riprova all'infinito (come l'originale) |
| `--no-upload`   | —                        | Salta l'upload su YouTube                                                |

Note importanti:

- **Retry:** ogni passo (estrazione, trascrizione, traduzione, sintesi vocale, assemblaggio, upload) viene verificato e ripetuto con pause crescenti (5 s, 10 s, … fino a 60 s). Con `--max-retries 0` non si ferma finché non riesce: puoi interromperlo con `Ctrl+C`.
- **Metadati:** `title.txt`, `description.txt` e `tag.txt` vengono letti **in italiano** e tradotti. Valori di riserva: «Video Automatico», «Descrizione del video.», «Shorts, Video».
- **Tracce audio su YouTube:** l'upload via API non aggiunge le tracce audio multiple. Le trovi in `Audio/` e vanno aggiunte a mano da YouTube Studio.
- **Lingua di partenza:** pensato per video in italiano o in una delle 10 lingue elencate. Una lingua rilevata non presente nell'elenco viene trattata come italiano nella traduzione.
- Se la lingua rilevata coincide con una delle 10, quella lingua viene saltata.

---

## 5. Formato dei file di testo

| File               | Usato da                      | Contenuto                                                              |
|--------------------|-------------------------------|------------------------------------------------------------------------|
| `titles.txt`       | `publish`                     | Un titolo per riga, nell'ordine alfabetico dei video                   |
| `timeclock.txt`    | `scale`                       | `S:inizio, E:fine, "Titolo"`, una riga per short                       |
| `title.txt`        | `capcut`, `multilang`         | Titolo del video                                                       |
| `description.txt`  | `scale`, `capcut`, `multilang`| Descrizione del video                                                  |
| `tag.txt`          | `scale`, `capcut`, `multilang`| Tag separati da virgola (o su righe diverse)                           |
| file brani (`--songs-file`) | `audio`              | `Artista - Titolo`, uno per riga                                       |

Tutti i file sono letti in UTF-8.

---

## 6. Lingue e voci

Lingue di destinazione: inglese (`en`), spagnolo (`es`), portoghese (`pt`), tedesco (`de`), francese (`fr`), hindi (`hi`), giapponese (`ja`), indonesiano (`id`), arabo (`ar`), russo (`ru`).

Voci Edge-TTS usate:

| Lingua | Voce                    | Lingua | Voce                    |
|--------|-------------------------|--------|-------------------------|
| `ar`   | `ar-SA-HamedNeural`     | `ja`   | `ja-JP-KeitaNeural`     |
| `de`   | `de-DE-ConradNeural`    | `pt`   | `pt-BR-AntonioNeural`   |
| `en`   | `en-US-ChristopherNeural` | `ru` | `ru-RU-DmitryNeural`    |
| `es`   | `es-ES-AlvaroNeural`    | `hi`   | `hi-IN-MadhurNeural`    |
| `fr`   | `fr-FR-HenriNeural`     | `id`   | `id-ID-ArdiNeural`      |

La traduzione usa MyMemory (servizio gratuito con limite giornaliero). Il testo di risposta «MYMEMORY WARNING» viene riconosciuto come errore e ritentato, invece di finire nei sottotitoli.

---

## 7. Flussi di lavoro tipici

**A. Video di viaggio con musica, pubblicati un giorno dopo l'altro**

1. `python AllInOne.py audio`: scarica i brani, poi copia gli MP3 in `Musica/`.
2. Metti i clip in `Video/`.
3. `python AllInOne.py shuffle`: crea `VideoPronti/`.
4. Scrivi `VideoPronti/titles.txt`.
5. `python AllInOne.py publish --dry-run`: controlla il calendario.
6. `python AllInOne.py publish`: carica davvero.

**B. Estrarre Shorts da un video lungo**

1. Metti il video in `input.mp4` e compila `timeclock.txt`.
2. `python AllInOne.py scale --no-upload`: controlla i risultati in `Shorts/`.
3. Quando sei soddisfatto, rilancia senza `--no-upload`, oppure copia gli short in `VideoPronti/` e usa `publish`.

**C. Un video con sottotitoli e doppiaggio in più lingue**

1. `python AllInOne.py capcut --input video.mp4 --no-upload` per i sottotitoli dinamici.
2. `python AllInOne.py multilang --video video.mp4` per doppiaggi, sottotitoli e upload.

---

## 8. Risoluzione dei problemi

| Problema                                              | Causa / soluzione                                                                                         |
|-------------------------------------------------------|-----------------------------------------------------------------------------------------------------------|
| `Non trovo nel PATH: ffmpeg`                          | Installa FFmpeg e riapri il terminale.                                                                    |
| FFmpeg: opzione `-fps_mode` non riconosciuta          | FFmpeg troppo vecchio (< 5.1). Aggiornalo, oppure nel file sostituisci `"-fps_mode", "cfr"` con `"-vsync", "cfr"`. |
| `Modulo 'X' non installato`                           | Esegui il comando `pip install` mostrato dal messaggio.                                                   |
| `File 'client_secret.json' non trovato`               | Vedi sezione 2. Controlla anche `--workdir`: il file deve stare nella cartella di lavoro.                 |
| Dopo circa 7 giorni torna a chiedere il login         | Con l'app OAuth in modalità *Test* i token scadono. Pubblica l'app nella schermata di consenso, oppure rifai il login. |
| Upload rifiutato o video bloccati come privati        | Le app API non verificate possono avere limiti di visibilità: controlla lo stato del progetto nella Google Cloud Console. |
| Errore di quota (`quotaExceeded`)                     | Ogni upload consuma molta quota API (circa 1600 unità; il limite giornaliero predefinito è 10.000). Carica meno video al giorno o richiedi più quota. |
| Il font dei sottotitoli non è Impact                  | Il font non è installato: installalo oppure cambia `Fontname` in `ASS_HEADER`.                            |
| `edge-tts` dà errore 403                              | Aggiorna con `pip install -U edge-tts` (il programma lo fa da solo, a meno che usi `--no-update-edge-tts`). |
| Traduzioni ferme o in attesa continua                 | Probabile limite MyMemory raggiunto: usa `--mymemory-email`, riprova il giorno dopo, oppure imposta `--max-retries`. |
| `Data nel passato` in `publish`                       | La data programmata è già trascorsa: correggi `--start-date`.                                             |
| Short saltato in `scale`                              | Errore FFmpeg sul taglio o sul rendering: controlla i tempi in `timeclock.txt` e il messaggio stampato.   |

Con `Ctrl+C` interrompi in sicurezza qualsiasi comando. Dal menu si torna alla scelta delle funzioni.

---

## 9. Differenze rispetto agli script originali

- **Login unico** con un solo `token.json` per tutte le funzioni.
- **Upload attivo di default** dove c'era già, con `--no-upload` per disattivarlo.
- **`title.txt` non viene più sovrascritto** da `scale`: il titolo di ogni short passa direttamente alla funzione di upload.
- **`scale` più robusto:** se il rendering di uno short fallisce, quello short viene saltato invece di tentare l'upload di un file inesistente.
- **Trascrizione riutilizzata:** `scale` usa la stessa trascrizione per i sottotitoli e per la cartella Misc, senza trascrivere due volte. Il modello Whisper viene caricato una sola volta per esecuzione.
- **`moviepy` non serve più:** l'audio viene estratto direttamente con FFmpeg.
- **Aggiornamento di `edge-tts`** eseguito una volta sola, e solo quando serve.
- **Elenco file concatenati più sicuro:** i nomi di cartella con l'apostrofo non rompono più l'unione dei blocchi audio.
- **Numerazione SRT continua**, senza salti quando un segmento è vuoto.
- **Novità:** `publish --dry-run`, `--start-date`, `--time`, `capcut --vertical`, `audio --songs-file`, `multilang --max-retries`, menu interattivo e `--workdir`.

---

## 10. Dove modificare le impostazioni

Le impostazioni principali sono costanti all'inizio di `AllInOne.py`:

| Costante               | Cosa controlla                                                              |
|------------------------|------------------------------------------------------------------------------|
| `SCOPES`               | Permessi OAuth richiesti                                                     |
| `DEFAULT_START_DATE`   | Data di inizio predefinita di `publish`                                      |
| `RETRY_DELAY`, `RETRY_DELAY_MAX` | Attesa iniziale e massima tra i tentativi                          |
| `LANGUAGES_MAP`        | Lingue di destinazione                                                       |
| `VOICES_MAP`           | Voce Edge-TTS per lingua                                                     |
| `DEFAULT_SONGS`        | Brani scaricati da `audio` quando non usi `--songs-file`                     |
| `ASS_HEADER`           | Stile dei sottotitoli: riga `Style: CapCut,...` (font, dimensione, colori in formato `&HAABBGGRR`, contorno, margine) |

I sottotitoli mostrano 4 parole per riga, in maiuscolo, con effetto karaoke. Per cambiare il numero di parole modifica il valore `>= 4` in `generate_capcut_ass_subtitles`.

### Mappa del codice

| Sezione del file          | Funzioni principali                                                                                   |
|---------------------------|--------------------------------------------------------------------------------------------------------|
| Funzioni condivise        | `need`, `require_binaries`, `retry_sync`/`retry_async`, `get_whisper`, `generate_capcut_ass_subtitles`, `render_with_subtitles`, `elabora_lingua`, `genera_audio_a_blocchi` |
| YouTube                   | `get_authenticated_service`, `check_channel_name`, `upload_video_file`, `upload_private_video`        |
| Una per script originale  | `cmd_publish`, `cmd_scale`, `cmd_capcut`, `cmd_audio`, `cmd_shuffle`, `cmd_multilang`                  |
| Interfaccia               | `build_parser`, `menu`, `main`                                                                         |
