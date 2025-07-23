# Sistema di Controllo Meccatronico

Un'interfaccia web avanzata per il controllo di un sistema meccatronico di scansione, composto da una piattaforma rotante orizzontale e una fotocamera inclinabile verticalmente.

## 🎯 Caratteristiche Principali

### Controllo Manuale
- **Piattaforma Rotante**: Controllo incrementale (±1°, ±5°, ±15°) e posizionamento diretto (0-360°)
- **Inclinazione Verticale**: Controllo incrementale (±1°, ±5°) e posizionamento diretto (0-90°)
- **Preview Camera**: Visualizzazione simulata dello stream video
- **Console Log**: Tracciamento in tempo reale di tutte le operazioni

### Task Automatici
- **Configurazione Parametrica**: Angolazioni verticali, step orizzontale, delay movimento
- **Modalità Operative**: Sequenziale e alternata
- **Controllo Progresso**: Barra di progresso e stato operativo
- **Registro Eventi**: Log dettagliato delle operazioni automatiche

## 🛠️ Tecnologie Utilizzate

- **HTML5**: Struttura semantica e accessibile
- **CSS3 + Tailwind CSS**: Design moderno e responsive
- **JavaScript + jQuery**: Logica applicativa e manipolazione DOM
- **Responsive Design**: Ottimizzato per tablet ≥10"

## 📁 Struttura del Progetto

```
scanner/
├── index.html          # File HTML principale
├── styles.css          # Stili CSS personalizzati
├── app.js             # Logica JavaScript dell'applicazione
└── README.md          # Documentazione del progetto
```

## 🚀 Installazione e Utilizzo

1. **Clona o scarica** i file del progetto
2. **Apri** `index.html` in un browser moderno
3. **Inizia** con il controllo manuale (sezione di default)
4. **Configura** e avvia task automatici nella sezione dedicata

### Requisiti
- Browser moderno con supporto ES6+
- Connessione internet per caricare jQuery e Tailwind CSS (CDN)

## 🎮 Funzionalità Dettagliate

### Controllo Manuale

#### Piattaforma Rotante
- **Range**: 0° - 360° (rotazione continua)
- **Controlli Incrementali**: 
  - ±1° (precisione fine)
  - ±5° (precisione media)
  - ±15° (precisione grossa)
- **Posizionamento Diretto**: Campo input numerico + pulsante "Vai"

#### Inclinazione Verticale
- **Range**: 0° (orizzontale) - 90° (verticale)
- **Controlli Incrementali**: ±1°, ±5°
- **Posizionamento Diretto**: Campo input numerico + pulsante "Vai"

### Task Automatici

#### Configurazione
- **Angolazioni Verticali**: 1-10 livelli di inclinazione
- **Step Angolare Orizzontale**: 1°-90° tra posizioni consecutive
- **Delay Movimento**: 0.5-10 secondi tra operazioni
- **Modalità Operativa**:
  - **Sequenziale**: Rotazione completa per ogni angolazione
  - **Alternata**: Angolazioni alternate per ogni step orizzontale

#### Controlli Operativi
- **Avvia Scansione**: Inizia task automatico
- **Interrompi**: Ferma task in esecuzione
- **Reset Posizione**: Riporta sistema a 0°, 0°

## 🎨 Design e UX

### Principi di Design
- **Interfaccia Industriale**: Ispirata a standard HMI professionali
- **Gerarchia Visiva**: Struttura a blocchi funzionali ben definiti
- **Accessibilità**: Contrasti elevati, font leggibili, area touch estesa
- **Responsività**: Adattamento fluido a diverse dimensioni schermo

### Schema Cromatico
- **Sfondo**: Grigio scuro (#111827)
- **Elementi**: Grigio medio (#374151)
- **Accenti**: Blu tecnico (#3b82f6)
- **Feedback**: Verde successo (#10b981), rosso errore (#ef4444)

## 🔧 Validazioni e Sicurezza

### Validazioni Input
- **Angoli Piattaforma**: 0-360° (numerico)
- **Angoli Inclinazione**: 0-90° (numerico)
- **Parametri Task**: Range validi per ogni configurazione
- **Feedback Immediato**: Messaggi di errore contestuali

### Gestione Errori
- **Validazione Rigorosa**: Controllo tipo e range per tutti gli input
- **Fallback Visivi**: Gestione grafica per condizioni simulate
- **Logging Completo**: Tracciamento errori e operazioni
- **Stato Persistente**: Mantenimento dati durante cambio sezione

## 📱 Responsive Design

### Breakpoint
- **Desktop**: Layout a due colonne, controlli estesi
- **Tablet (≥10")**: Layout adattivo, controlli touch-friendly
- **Mobile**: Layout a colonna singola, controlli ottimizzati

### Ottimizzazioni Touch
- **Area Attiva**: Pulsanti con area minima 44px
- **Spaziatura**: Distanze adeguate per interazione touch
- **Feedback Visivo**: Stati hover e active ben definiti

## 🔄 Persistenza e Stato

### Gestione Stato
- **Posizioni Correnti**: Mantenute durante cambio sezione
- **Configurazione Task**: Salvata e ripristinata automaticamente
- **Log Operativi**: Conservati per tutta la sessione
- **Stato Task**: Tracciamento progresso e interruzioni

## 🎯 Simulazione Hardware

### Comportamento Simulato
- **Movimenti**: Aggiornamento posizioni in tempo reale
- **Delay**: Simulazione tempi di movimento configurabili
- **Connessione**: Indicatore stato hardware simulato
- **Stream Video**: Preview camera con fallback grafico

## 📊 Logging e Debug

### Console Log
- **Timestamp**: Ora esatta di ogni operazione
- **Tipi Messaggio**: Info, successo, errore, warning
- **Auto-scroll**: Scorrimento automatico ai messaggi più recenti
- **Console Browser**: Output parallelo nella console sviluppatore

### Registro Eventi Task
- **Tracciamento Step**: Log dettagliato di ogni movimento
- **Progresso**: Aggiornamento percentuale in tempo reale
- **Interruzioni**: Gestione e logging delle interruzioni
- **Completamento**: Conferma avvenuta scansione

## 🚀 Estendibilità

### Architettura Modulare
- **Separazione Responsabilità**: HTML, CSS, JS ben organizzati
- **Funzioni Modulari**: Logica segmentata per facilità manutenzione
- **Configurazione Centralizzata**: Stato globale ben definito
- **API Simulata**: Struttura pronta per integrazione hardware reale

### Possibili Estensioni
- **Integrazione Hardware**: Collegamento a sistemi embedded reali
- **Salvataggio Configurazioni**: Persistenza su localStorage o database
- **Export Log**: Esportazione log in formato CSV/JSON
- **Multi-lingua**: Supporto per altre lingue
- **Temi Personalizzabili**: Schemi cromatici configurabili

## 📝 Note Tecniche

### Compatibilità Browser
- **Chrome**: 80+
- **Firefox**: 75+
- **Safari**: 13+
- **Edge**: 80+

### Performance
- **Caricamento**: Ottimizzato per CDN esterni
- **Rendering**: CSS Grid e Flexbox per layout efficienti
- **JavaScript**: Codice ottimizzato con jQuery
- **Memory**: Gestione memoria per sessioni prolungate

## 🤝 Contributi

Il progetto è strutturato per facilitare contributi e modifiche:
- **Codice Commentato**: Documentazione inline completa
- **Struttura Chiara**: Organizzazione logica dei file
- **Standard Consistenti**: Convenzioni di naming uniformi
- **Modularità**: Funzioni indipendenti e riutilizzabili

---

**Sviluppato per ambienti industriali e di automazione con focus su ergonomia, affidabilità e precisione operativa.** 