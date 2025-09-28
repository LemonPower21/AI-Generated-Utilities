import sys
import json # Import per la gestione dei dati persistenti
import os   # Import per controllare l'esistenza del file
import urllib.parse
from PyQt5.QtCore import QUrl, Qt, QDateTime
from PyQt5.QtWidgets import QApplication, QMainWindow, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QMenu, QDialog, QListWidget, QListWidgetItem, QInputDialog
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile, QWebEngineSettings 

# Importazioni PyQt5
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile

# Costante per la ricerca
DUCKDUCKGO_SEARCH_URL = "https://duckduckgo.com/?q="
# Costanti per il salvataggio dei dati
BOOKMARKS_FILE = "bookmarks.json"
HISTORY_FILE = "history.json"

class SimpleBrowser(QMainWindow):
    """
    Un browser web di base costruito con PyQt5.
    """
    def __init__(self):
        super().__init__()

        # Imposta la finestra a schermo intero
        self.showMaximized()
        self.setWindowTitle('Simple Browser')
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # Inizializza o carica la lista dei preferiti e la cronologia
        self.bookmarks = self.load_bookmarks()
        self.history = self.load_history()
        
        # Inizializza lo stato di JavaScript
        self.is_js_enabled = True

        # --- Elementi UI ---

        # Status Bar
        self.status_bar = QLabel("Browser pronto.") 
        self.main_layout.addWidget(self.status_bar)
        
        # User Agent Input
        self.user_agent_layout = QHBoxLayout()
        self.user_agent_input = QLineEdit()
        self.user_agent_input.setPlaceholderText('Inserisci User-Agent (opzionale)')
        self.user_agent_layout.addWidget(self.user_agent_input)

        # Navigaton Bar (con pulsanti aggiunti)
        self.nav_layout = QHBoxLayout()

        # Pulsanti di navigazione
        self.back_button = QPushButton('< Indietro')
        self.back_button.clicked.connect(self.go_back)
        self.nav_layout.addWidget(self.back_button)

        self.forward_button = QPushButton('Avanti >')
        self.forward_button.clicked.connect(self.go_forward)
        self.nav_layout.addWidget(self.forward_button)

        self.reload_button = QPushButton('Ricarica')
        self.reload_button.clicked.connect(self.reload_page)
        self.nav_layout.addWidget(self.reload_button)
        
        # URL Bar
        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText('Inserisci URL o termine di ricerca (es. https://www.google.com)')
        self.nav_layout.addWidget(self.url_bar)
        
        # Pulsante Aggiungi Preferito (Ora apre QInputDialog)
        self.add_bookmark_button = QPushButton('+ Preferiti')
        self.add_bookmark_button.clicked.connect(self.prompt_and_add_bookmark)
        self.nav_layout.addWidget(self.add_bookmark_button)
        
        # Pulsante Toggle JS
        self.toggle_js_button = QPushButton('JS ON/OFF')
        self.toggle_js_button.clicked.connect(self.toggle_javascript)
        self.nav_layout.addWidget(self.toggle_js_button)

        # Go Button
        self.go_button = QPushButton('Go')
        self.go_button.clicked.connect(self.navigate)
        self.url_bar.returnPressed.connect(self.navigate)
        self.nav_layout.addWidget(self.go_button)

        self.main_layout.addLayout(self.user_agent_layout)
        self.main_layout.addLayout(self.nav_layout)
        
        # --- History Bar ---
        self.history_button = QPushButton('Cronologia')
        self.history_button.clicked.connect(self.show_history_window)
        
        self.history_layout = QHBoxLayout()
        self.history_layout.addWidget(self.history_button)
        self.history_layout.addStretch(1) # Spinge il pulsante a sinistra
        self.main_layout.addLayout(self.history_layout)

        # --- Bookmark Bar Placeholder ---
        self.bookmark_widget = QWidget()
        self.bookmark_layout = QHBoxLayout(self.bookmark_widget)
        self.bookmark_layout.setContentsMargins(0, 0, 0, 0)
        self.bookmark_layout.addWidget(QLabel("Preferiti:"))
        
        self.main_layout.addWidget(self.bookmark_widget)
        # ---------------------
        
        # Inizializza la barra dei preferiti
        self.setup_bookmarks()

        # Browser View
        self.browser_view = QWebEngineView()
        self.main_layout.addWidget(self.browser_view)
        
        # Configura le impostazioni iniziali di JavaScript
        self.browser_view.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, self.is_js_enabled)
        
        # Applica lo stile iniziale al pulsante JS
        self.update_js_button_style()

        # Aggiorna l'URL bar e registra la cronologia quando la pagina cambia
        self.browser_view.urlChanged.connect(self.update_url_bar)
        self.browser_view.loadFinished.connect(self.update_history_on_load)

        # Carica una pagina di default all'avvio
        self.browser_view.setUrl(QUrl("https://www.duckduckgo.com"))
        
    # --- Metodi di Utility (JS, Storia, Preferiti) ---
        
    def update_js_button_style(self):
        """Aggiorna il colore del pulsante JS in base allo stato."""
        if self.is_js_enabled:
            # Verde per abilitato
            style = "background-color: #4CAF50; color: white; border: 1px solid #4CAF50;"
            status_text = "Attivo"
        else:
            # Rosso per disabilitato
            style = "background-color: #F44336; color: white; border: 1px solid #F44336;"
            status_text = "Disattivo"
            
        self.toggle_js_button.setStyleSheet(style)
        self.toggle_js_button.setText(f"JS: {status_text}")
        self.status_bar.setText(f"Browser pronto.")
        
    def toggle_javascript(self):
        """Abilita o disabilita l'esecuzione di JavaScript, aggiorna lo stile del pulsante e la UI."""
        self.is_js_enabled = not self.is_js_enabled
        
        settings = self.browser_view.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, self.is_js_enabled)
        
        self.update_js_button_style() # Aggiorna lo stile e lo stato nella barra inferiore
        self.status_bar.setText("JavaScript modificato. Ricarica la pagina per applicare.")
        
    def load_bookmarks(self):
        """Carica i preferiti dal file JSON o usa i valori predefiniti."""
        if os.path.exists(BOOKMARKS_FILE):
            try:
                with open(BOOKMARKS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Errore nel caricamento dei preferiti: {e}")
                return {"DuckDuckGo": "https://www.duckduckgo.com"}
        else:
            return {"DuckDuckGo": "https://www.duckduckgo.com"}

    def save_bookmarks(self):
        """Salva i preferiti attuali nel file JSON."""
        try:
            with open(BOOKMARKS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.bookmarks, f, indent=4)
        except Exception as e:
            self.status_bar.setText(f"Errore nel salvataggio dei preferiti: {e}")

    def load_history(self):
        """Carica la cronologia dal file JSON."""
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    # La cronologia viene salvata come lista di oggetti {'url', 'title', 'timestamp'}
                    return json.load(f)
            except Exception as e:
                print(f"Errore nel caricamento della cronologia: {e}")
                return []
        else:
            return []

    def save_history(self):
        """Salva la cronologia attuale nel file JSON."""
        try:
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=4)
        except Exception as e:
            self.status_bar.setText(f"Errore nel salvataggio della cronologia: {e}")

    def update_history_on_load(self):
        """Registra la pagina nella cronologia solo dopo che il caricamento è terminato."""
        current_url = self.browser_view.url().toString()
        title = self.browser_view.title()

        if not current_url or current_url.startswith("about:"):
            return
            
        # Timestamp (per ordinamento)
        timestamp = QDateTime.currentDateTime().toString(Qt.ISODate)
        
        new_entry = {
            'url': current_url, 
            'title': title if title else current_url,
            'timestamp': timestamp
        }
        
        # Previene duplicati consecutivi (se ricarichi la stessa pagina)
        if self.history and self.history[-1]['url'] == current_url:
            self.history[-1] = new_entry # Aggiorna solo il timestamp e il titolo
        else:
            self.history.append(new_entry)

        # Mantiene la cronologia a una dimensione ragionevole (es. 500 voci)
        if len(self.history) > 500:
            self.history = self.history[-500:]

        self.save_history()

    def show_history_window(self):
        """Mostra una finestra di dialogo con la cronologia."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Cronologia Browser")
        dialog.setGeometry(100, 100, 600, 400)
        
        layout = QVBoxLayout(dialog)
        list_widget = QListWidget()
        layout.addWidget(list_widget)

        # Inserisce gli elementi della cronologia (dal più recente)
        for entry in reversed(self.history):
            # Formatta l'etichetta: Titolo | URL (Timestamp)
            display_text = f"{entry['title']} | {entry['url']} ({entry['timestamp'].split('T')[0]})"
            item = QListWidgetItem(display_text)
            
            # Memorizza l'URL nei dati dell'elemento per la navigazione
            item.setData(Qt.UserRole, entry['url'])
            list_widget.addItem(item)
            
        def item_clicked(item):
            url = item.data(Qt.UserRole)
            self.navigate_to_url(url)
            dialog.close()

        list_widget.itemClicked.connect(item_clicked)
        
        # Pulsante per chiudere
        close_button = QPushButton("Chiudi")
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button)

        dialog.exec_()


    def setup_bookmarks(self):
        """Crea e ricrea i pulsanti per i preferiti."""
        # 1. Trova e pulisci il layout esistente, mantenendo l'etichetta "Preferiti:"
        bookmark_label = self.bookmark_widget.findChild(QLabel)
        
        # Rimuove tutti i widget che non sono l'etichetta "Preferiti:"
        for i in reversed(range(self.bookmark_layout.count())):
            item = self.bookmark_layout.itemAt(i)
            widget = item.widget()
            if widget and widget != bookmark_label:
                widget.deleteLater()
                
        # 2. Ricrea i pulsanti
        for name, url in self.bookmarks.items():
            btn = QPushButton(name)
            btn.setToolTip(url) # Mostra l'URL nel tooltip
            btn.setContextMenuPolicy(Qt.CustomContextMenu) # Abilita menu contestuale
            
            # Connessione per la navigazione (click sinistro)
            btn.clicked.connect(lambda checked, u=url: self.navigate_to_url(u))
            
            # Connessione per la rimozione (click destro)
            btn.customContextMenuRequested.connect(lambda point, n=name: self.show_bookmark_context_menu(n, btn.mapToGlobal(point)))
            
            self.bookmark_layout.addWidget(btn)

    def show_bookmark_context_menu(self, name, global_pos):
        """Mostra il menu contestuale per rimuovere un preferito."""
        menu = QMenu(self)
        remove_action = menu.addAction(f"Rimuovi {name}")
        
        action = menu.exec_(global_pos)
        
        if action == remove_action:
            self.remove_bookmark(name)

    def remove_bookmark(self, name):
        """Rimuove un preferito dalla lista, aggiorna la UI e salva su disco."""
        if name in self.bookmarks:
            del self.bookmarks[name]
            self.status_bar.setText(f"Preferito '{name}' rimosso.")
            self.setup_bookmarks() # Ridisegna la barra
            self.save_bookmarks() # Salva la modifica su disco
        
    def prompt_and_add_bookmark(self):
        """Richiede all'utente il nome del preferito prima di aggiungerlo."""
        current_url = self.browser_view.url().toString()
        title = self.browser_view.title() or current_url
        
        if not current_url or current_url.startswith("about:"):
            self.status_bar.setText("Impossibile aggiungere: Nessuna pagina valida caricata.")
            return

        # Finestra di dialogo per l'input
        text, ok = QInputDialog.getText(self, 'Aggiungi Preferito', 'Dai un nome a questo preferito:', QLineEdit.Normal, title)

        if ok and text:
            bookmark_name = text.strip()
            
            # Controllo anti-duplicato
            if bookmark_name in self.bookmarks:
                 self.status_bar.setText(f"Errore: Il nome '{bookmark_name}' esiste già.")
                 return
            if current_url in self.bookmarks.values():
                self.status_bar.setText("Questo URL è già nei preferiti con un altro nome.")
                return

            self.bookmarks[bookmark_name] = current_url
            self.status_bar.setText(f"Aggiunto ai preferiti: {bookmark_name}")
            self.setup_bookmarks() # Ridisegna la barra
            self.save_bookmarks() # Salva la modifica su disco
        elif ok:
             self.status_bar.setText("Nome preferito non valido o vuoto.")

        
    def navigate_to_url(self, url_str):
        """Naviga direttamente a un URL fornito (usato dai preferiti e dalla cronologia)."""
        self.browser_view.setUrl(QUrl(url_str))
        self.url_bar.setText(url_str)
        self.status_bar.setText(f"Navigo a: {url_str}")
        
    def navigate(self):
        """Carica l'URL inserito, applicando un User-Agent se specificato o cerca su DuckDuckGo."""
        url_text = self.url_bar.text().strip()
        user_agent_text = self.user_agent_input.text()

        if not url_text:
            return

        # Imposta l'User-Agent se presente
        if user_agent_text:
            profile = QWebEngineProfile.defaultProfile()
            profile.setHttpUserAgent(user_agent_text)
        
        # 1. Tenta di interpretare come URL valido (deve contenere almeno un punto e non contenere spazi)
        is_url_candidate = '.' in url_text and ' ' not in url_text
        
        # Controlla se l'input inizia con protocollo o sembra un URL
        if url_text.startswith(('http://', 'https://')):
            url = QUrl(url_text)
        elif is_url_candidate:
            # Tenta di aggiungere http:// e spera che QWebEngineView lo gestisca
            url = QUrl('http://' + url_text)
        else:
            # 2. Se non sembra un URL, effettua una ricerca su DuckDuckGo
            search_query = QUrl.toPercentEncoding(url_text)
            full_search_url = DUCKDUCKGO_SEARCH_URL + search_query.data().decode()
            url = QUrl(full_search_url)
            self.status_bar.setText(f"Eseguo ricerca per: {url_text}")

        self.browser_view.setUrl(url)

    def update_url_bar(self, url):
        """Aggiorna la barra URL con l'indirizzo della pagina corrente."""
        self.url_bar.setText(url.toString())

    def go_back(self):
        """Torna alla pagina precedente nella cronologia."""
        self.browser_view.back()

    def go_forward(self):
        """Vai alla pagina successiva nella cronologia."""
        self.browser_view.forward()

    def reload_page(self):
        """Ricarica la pagina corrente."""
        self.browser_view.reload()

if __name__ == '__main__':
    # È necessario impostare l'attributo per alta risoluzione per una migliore visualizzazione
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling) 
    app = QApplication(sys.argv)
    browser = SimpleBrowser()
    browser.show()
    sys.exit(app.exec_())
