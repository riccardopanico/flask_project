/**
 * Sistema di Controllo Meccatronico - JavaScript principale
 * Gestisce l'interfaccia utente per il controllo di piattaforma rotante e fotocamera inclinabile
 * Design Light con dashboard visuale, filtri log e gestione task strutturata
 */

$(document).ready(function() {
    // ========================================
    // STATO GLOBALE DELL'APPLICAZIONE
    // ========================================

    const AppState = {
        platform: { angle: 0 },
        tilt: { angle: 0 },
        task: {
            running: false,
            current: null,
            progress: 0,
            config: {
                verticalAngles: 3,
                horizontalStep: 20,
                movementDelay: 2,
                operationMode: 'sequential'
            },
            presets: [
                { id: 'quick-scan', name: 'Scansione Rapida 4x90°',
                  description: 'Scansione veloce con 4 angolazioni verticali e step di 90°',
                  config: { verticalAngles: 4, horizontalStep: 90, movementDelay: 1, operationMode: 'sequential' }
                },
                { id: 'high-def-vertical', name: 'Alta Definizione Verticale',
                  description: 'Scansione dettagliata con 8 angolazioni verticali e step di 15°',
                  config: { verticalAngles: 8, horizontalStep: 15, movementDelay: 3, operationMode: 'sequential' }
                },
                { id: 'three-level-inspection', name: 'Ispezione a 3 Livelli',
                  description: 'Ispezione standard con 3 livelli di inclinazione',
                  config: { verticalAngles: 3, horizontalStep: 30, movementDelay: 2, operationMode: 'alternate' }
                },
                { id: 'ultra-fine-scan', name: 'Scansione Ultra Fine',
                  description: 'Scansione di precisione con step di 5° e 10 angolazioni',
                  config: { verticalAngles: 10, horizontalStep: 5, movementDelay: 4, operationMode: 'sequential' }
                }
            ],
            custom: []
        },
        log: { filters: ['info','success','warning','error'] },
        ui: { currentSection: 'manual-control' }
    };
    // ========================================
    // UTILITY FUNCTIONS
    // ========================================
    
    /**
     * Normalizza un angolo nel range 0-360°
     */
    function normalizeAngle(angle) {
        return ((angle % 360) + 360) % 360;
    }
    
    /**
     * Valida un angolo per la piattaforma (0-360°)
     */
    function validatePlatformAngle(angle) {
        const num = parseFloat(angle);
        return !isNaN(num) && num >= 0 && num <= 360;
    }
    
    /**
     * Valida un angolo per l'inclinazione (0-90°)
     */
    function validateTiltAngle(angle) {
        const num = parseFloat(angle);
        return !isNaN(num) && num >= 0 && num <= 90;
    }
    
    /**
     * Formatta timestamp per i log
     */
    function getTimestamp() {
        const now = new Date();
        return now.toLocaleTimeString('it-IT');
    }
    
    /**
     * Aggiorna la dashboard visuale
     */
    function updateDashboard() {
        $('#dashboard-platform').text(`${AppState.platform.angle}°`);
        $('#dashboard-tilt').text(`${AppState.tilt.angle}°`);
        $('#dashboard-progress').text(`${AppState.task.progress}%`);
        
        // Aggiorna stato sistema
        let status = 'Idle';
        let statusClass = 'idle';
        
        if (AppState.task.running) {
            status = 'In Esecuzione';
            statusClass = 'running';
        } else if (AppState.task.progress === 100) {
            status = 'Completato';
            statusClass = 'completed';
        }
        
        $('#dashboard-status').text(status).removeClass('idle running completed error').addClass(statusClass);
    }
    
    /**
     * Aggiunge messaggio alla console log con filtri
     */
    function logToConsole(message, type = 'info') {
        const timestamp = getTimestamp();
        const logElement = $(`<div class="log-entry log-${type}" data-type="${type}">
            <span class="text-gray-500">[${timestamp}]</span> ${message}
        </div>`);
        
        $('#console-log').append(logElement);
        $('#console-log').scrollTop($('#console-log')[0].scrollHeight);
        
        // Applica filtri
        applyLogFilters('#console-log');
        
        // Log anche nella console del browser
        console.log(`[${timestamp}] ${message}`);
    }
    
    /**
     * Aggiunge messaggio al registro eventi task con filtri
     */
    function logToTaskLog(message, type = 'info') {
        const timestamp = getTimestamp();
        const logElement = $(`<div class="log-entry log-${type}" data-type="${type}">
            <span class="text-gray-500">[${timestamp}]</span> ${message}
        </div>`);
        
        $('#task-log').append(logElement);
        $('#task-log').scrollTop($('#task-log')[0].scrollHeight);
        
        // Applica filtri
        applyLogFilters('#task-log');
    }
    
    /**
     * Applica filtri ai log
     */
    function applyLogFilters(containerId) {
        const container = $(containerId);
        const entries = container.find('.log-entry');
        
        entries.each(function() {
            const entry = $(this);
            const type = entry.data('type');
            
            if (AppState.log.filters.includes(type) || AppState.log.filters.includes('all')) {
                entry.removeClass('hidden');
            } else {
                entry.addClass('hidden');
            }
        });
    }
    
    /**
     * Gestisce i filtri dei log
     */
    function setupLogFilters() {
        $(".log-filters").on("click", ".filter-btn", function() {
            const filter = $(this).data("filter");
            const button = $(this);

            if (filter === "all") {
                $(".log-filters .filter-btn").addClass("active");
                AppState.log.filters = ["info", "success", "warning", "error", "all"];
            } else if (filter === "clear") {
                $("#console-log, #task-log").empty();
                return;
            } else {
                if (button.hasClass("active")) {
                    button.removeClass("active");
                    AppState.log.filters = AppState.log.filters.filter(f => f !== filter);
                } else {
                    button.addClass("active");
                    AppState.log.filters.push(filter);
                }
            }
            applyLogFilters("#console-log");
            applyLogFilters("#task-log");
        });
    }
    function showError(message) {
        logToConsole(`❌ ERRORE: ${message}`, 'error');
    }

    
    /**
     * Mostra messaggio di successo
     */
    function showSuccess(message) {
        logToConsole(`✅ ${message}`, 'success');
    }

    // ========================================
    // GESTIONE NAVIGAZIONE
    // ========================================
    
    /**
     * Cambia sezione attiva
     */
    function switchSection(sectionId) {
        // Nasconde tutte le sezioni
        $('.section-content').addClass('hidden');
        
        // Mostra la sezione selezionata
        $(`#${sectionId}`).removeClass('hidden');
        
        // Aggiorna stato pulsanti navigazione
        $('.nav-btn').removeClass('active');
        $(`#nav-${sectionId.replace('-', '')}`).addClass('active');
        
        // Aggiorna modalità corrente
        AppState.ui.currentSection = sectionId;
        const modeName = sectionId === 'manual-control' ? 'Controllo Manuale' : 'Task Automatici';
        $('#current-mode').text(modeName);
        
        logToConsole(`Sezione attivata: ${modeName}`);
    }
    
    // Event listeners per navigazione
    $('#nav-manual').click(function() {
        switchSection('manual-control');
    });
    
    $('#nav-automatic').click(function() {
        switchSection('automatic-tasks');
    });

    // ========================================
    // CONTROLLO PIATTAFORMA ROTANTE
    // ========================================
    
    /**
     * Aggiorna visualizzazione angolo piattaforma
     */
    function updatePlatformDisplay() {
        $('#platform-angle').text(`${AppState.platform.angle}°`);
        $('#camera-angle-display').text(`${AppState.platform.angle}°`);
        updateDashboard();
    }
    
    /**
     * Ruota la piattaforma di un determinato step
     */
    function rotatePlatform(step) {
        const newAngle = normalizeAngle(AppState.platform.angle + step);
        AppState.platform.angle = newAngle;
        updatePlatformDisplay();
        
        showSuccess(`Piattaforma ruotata a ${newAngle}°`);
    }
    
    /**
     * Vai a posizione specifica della piattaforma
     */
    function goToPlatformPosition(angle) {
        if (!validatePlatformAngle(angle)) {
            showError('Angolo piattaforma non valido. Inserire un valore tra 0 e 360°');
            return false;
        }
        
        const targetAngle = normalizeAngle(parseFloat(angle));
        AppState.platform.angle = targetAngle;
        updatePlatformDisplay();
        
        showSuccess(`Piattaforma posizionata a ${targetAngle}°`);
        return true;
    }
    
    // Event listeners per controllo piattaforma
$("#manual-control").on('click', '.control-btn[data-action="platform"]', function() {
        const step = parseInt($(this).data("step"));
        rotatePlatform(step);
    });
    
    $('#platform-go').click(function() {
        const angle = $('#platform-input').val();
        goToPlatformPosition(angle);
    });
    
    $('#platform-input').keypress(function(e) {
        if (e.which === 13) { // Enter key
            $('#platform-go').click();
        }
    });

    // ========================================
    // CONTROLLO INCLINAZIONE VERTICALE
    // ========================================
    
    /**
     * Aggiorna visualizzazione inclinazione
     */
    function updateTiltDisplay() {
        $('#tilt-angle').text(`${AppState.tilt.angle}°`);
        updateDashboard();
    }
    
    /**
     * Inclina la fotocamera di un determinato step
     */
    function tiltCamera(step) {
        const newAngle = AppState.tilt.angle + step;
        
        if (newAngle < 0 || newAngle > 90) {
            showError('Inclinazione fuori range. Valore deve essere tra 0° e 90°');
            return;
        }
        
        AppState.tilt.angle = newAngle;
        updateTiltDisplay();
        
        showSuccess(`Fotocamera inclinata a ${newAngle}°`);
    }
    
    /**
     * Vai a inclinazione specifica
     */
    function goToTiltPosition(angle) {
        if (!validateTiltAngle(angle)) {
            showError('Angolo inclinazione non valido. Inserire un valore tra 0 e 90°');
            return false;
        }
        
        const targetAngle = parseFloat(angle);
        AppState.tilt.angle = targetAngle;
        updateTiltDisplay();
        
        showSuccess(`Fotocamera posizionata a ${targetAngle}°`);
    return true;
}
$("#manual-control").on('click', '.control-btn[data-action="tilt"]', function() {
    const step = parseInt($(this).data("step"));
    tiltCamera(step);
});
    $('#tilt-go').click(function() {
        const angle = $('#tilt-input').val();
        goToTiltPosition(angle);
    });
    
    $('#tilt-input').keypress(function(e) {
        if (e.which === 13) { // Enter key
            $('#tilt-go').click();
        }
    });

    // ========================================
    // GESTIONE TASK
    // ========================================
    
    /**
     * Carica task preimpostati
     */
    function loadPresetTasks() {
        const container = $('#preset-tasks');
        container.empty();
        
        AppState.task.presets.forEach(task => {
            const taskElement = $(`
                <div class="task-card" data-task-id="${task.id}">
                    <div class="task-name">${task.name}</div>
                    <div class="task-description">${task.description}</div>
                    <div class="task-params">
                        ${task.config.verticalAngles} angolazioni, step ${task.config.horizontalStep}°, 
                        delay ${task.config.movementDelay}s, ${task.config.operationMode}
                    </div>
                    <div class="task-actions">
                        <button class="task-btn primary load-preset" data-task-id="${task.id}">Carica</button>
                        <button class="task-btn start-preset" data-task-id="${task.id}">Avvia</button>
                    </div>
                </div>
            `);
            
            container.append(taskElement);
        });
        
        // Event listeners per task preimpostati
        $("#preset-tasks").on("click", ".load-preset", function() {
            const taskId = $(this).data("task-id");
            loadPresetTask(taskId);
        });

        $("#preset-tasks").on("click", ".start-preset", function() {
            const taskId = $(this).data("task-id");
            loadPresetTask(taskId);
            setTimeout(() => startAutomaticTask(), 100);
        });
    }
    
    /**
     * Carica un task preimpostato
     */
    function loadPresetTask(taskId) {
        const task = AppState.task.presets.find(t => t.id === taskId);
        if (!task) {
            showError('Task non trovato');
            return;
        }
        
        // Aggiorna interfaccia
        $('#task-name').val(task.name);
        $('#task-description').val(task.description);
        $('#vertical-angles').val(task.config.verticalAngles);
        $('#horizontal-step').val(task.config.horizontalStep);
        $('#movement-delay').val(task.config.movementDelay);
        $(`input[name="operation-mode"][value="${task.config.operationMode}"]`).prop('checked', true);
        
        // Aggiorna stato
        AppState.task.config = { ...task.config };
        
        // Evidenzia task selezionato
        $('.task-card').removeClass('selected');
        $(`.task-card[data-task-id="${taskId}"]`).addClass('selected');
        
        logToTaskLog(`Task caricato: ${task.name}`, 'info');
        showSuccess(`Task "${task.name}" caricato`);
    }
    
    /**
     * Salva task personalizzato
     */
    function saveCustomTask() {
        const name = $('#task-name').val().trim();
        const description = $('#task-description').val().trim();
        
        if (!name) {
            showError('Nome task obbligatorio');
            return;
        }
        
        // Valida configurazione
        updateTaskConfig();
        
        const task = {
            id: 'custom-' + Date.now(),
            name: name,
            description: description,
            config: { ...AppState.task.config }
        };
        
        // Rimuovi task con stesso nome se esiste
        AppState.task.custom = AppState.task.custom.filter(t => t.name !== name);
        AppState.task.custom.push(task);
        
        // Salva in localStorage
        localStorage.setItem('customTasks', JSON.stringify(AppState.task.custom));
        
        logToTaskLog(`Task salvato: ${name}`, 'success');
        showSuccess(`Task "${name}" salvato`);
    }
    
    /**
     * Carica task personalizzato
     */
    function loadCustomTask() {
        if (AppState.task.custom.length === 0) {
            showError('Nessun task personalizzato salvato');
            return;
        }
        
        // Mostra dialog di selezione (semplificato)
        const taskNames = AppState.task.custom.map(t => t.name);
        const selectedName = prompt('Seleziona task:\n' + taskNames.join('\n'));
        
        if (!selectedName) return;
        
        const task = AppState.task.custom.find(t => t.name === selectedName);
        if (!task) {
            showError('Task non trovato');
            return;
        }
        
        // Carica task
        $('#task-name').val(task.name);
        $('#task-description').val(task.description);
        $('#vertical-angles').val(task.config.verticalAngles);
        $('#horizontal-step').val(task.config.horizontalStep);
        $('#movement-delay').val(task.config.movementDelay);
        $(`input[name="operation-mode"][value="${task.config.operationMode}"]`).prop('checked', true);
        
        AppState.task.config = { ...task.config };
        
        logToTaskLog(`Task personalizzato caricato: ${task.name}`, 'info');
        showSuccess(`Task "${task.name}" caricato`);
    }
    
    /**
     * Aggiorna configurazione task
     */
    function updateTaskConfig() {
        AppState.task.config.verticalAngles = parseInt($('#vertical-angles').val()) || 3;
        AppState.task.config.horizontalStep = parseInt($('#horizontal-step').val()) || 20;
        AppState.task.config.movementDelay = parseFloat($('#movement-delay').val()) || 2;
        AppState.task.config.operationMode = $('input[name="operation-mode"]:checked').val();
        
        logToTaskLog(`Configurazione aggiornata: ${AppState.task.config.verticalAngles} angolazioni, step ${AppState.task.config.horizontalStep}°, delay ${AppState.task.config.movementDelay}s, modalità ${AppState.task.config.operationMode}`);
    }
    
    /**
     * Aggiorna stato visuale del task
     */
    function updateTaskStatus(status, progress = 0) {
        $('#task-status').text(status);
        $('#progress-text').text(`${progress}%`);
        $('#progress-bar').css('width', `${progress}%`);
        
        AppState.task.progress = progress;
        updateDashboard();
        
        // Gestione pulsanti
        if (AppState.task.running) {
            $('#start-scan').prop('disabled', true);
            $('#stop-scan').prop('disabled', false);
            $('#reset-position').prop('disabled', true);
        } else {
            $('#start-scan').prop('disabled', false);
            $('#stop-scan').prop('disabled', true);
            $('#reset-position').prop('disabled', false);
        }
    }
    
    /**
     * Calcola posizioni per la scansione
     */
    function calculateScanPositions() {
        const config = AppState.task.config;
        const positions = [];
        
        if (config.operationMode === 'sequential') {
            // Modalità sequenziale: per ogni angolazione, ruota completamente
            for (let tilt = 0; tilt < config.verticalAngles; tilt++) {
                const tiltAngle = (90 / (config.verticalAngles - 1)) * tilt;
                for (let platform = 0; platform < 360; platform += config.horizontalStep) {
                    positions.push({
                        platform: platform,
                        tilt: tiltAngle,
                        step: positions.length + 1
                    });
                }
            }
        } else {
            // Modalità alternata: alterna angolazioni per ogni step orizzontale
            for (let platform = 0; platform < 360; platform += config.horizontalStep) {
                for (let tilt = 0; tilt < config.verticalAngles; tilt++) {
                    const tiltAngle = (90 / (config.verticalAngles - 1)) * tilt;
                    positions.push({
                        platform: platform,
                        tilt: tiltAngle,
                        step: positions.length + 1
                    });
                }
            }
        }
        
        return positions;
    }
    
    /**
     * Esegue un singolo movimento
     */
    function executeMovement(platformAngle, tiltAngle, stepNumber, totalSteps) {
        return new Promise((resolve) => {
            // Simula movimento piattaforma
            AppState.platform.angle = normalizeAngle(platformAngle);
            updatePlatformDisplay();
            
            // Simula movimento inclinazione
            AppState.tilt.angle = tiltAngle;
            updateTiltDisplay();
            
            // Aggiorna progresso
            const progress = Math.round((stepNumber / totalSteps) * 100);
            updateTaskStatus('In Esecuzione', progress);
            
            logToTaskLog(`Step ${stepNumber}/${totalSteps}: Piattaforma ${platformAngle}°, Inclinazione ${tiltAngle}°`);
            
            // Simula delay movimento
            setTimeout(() => {
                resolve();
            }, AppState.task.config.movementDelay * 1000);
        });
    }
    
    /**
     * Avvia task automatico
     */
    async function startAutomaticTask() {
        if (AppState.task.running) {
            showError('Task già in esecuzione');
            return;
        }
        
        // Aggiorna configurazione
        updateTaskConfig();
        
        // Valida configurazione
        if (AppState.task.config.verticalAngles < 1 || AppState.task.config.verticalAngles > 10) {
            showError('Numero angolazioni verticali deve essere tra 1 e 10');
            return;
        }
        
        if (AppState.task.config.horizontalStep < 1 || AppState.task.config.horizontalStep > 90) {
            showError('Step angolare orizzontale deve essere tra 1° e 90°');
            return;
        }
        
        if (AppState.task.config.movementDelay < 0.5 || AppState.task.config.movementDelay > 10) {
            showError('Delay movimento deve essere tra 0.5 e 10 secondi');
            return;
        }
        
        // Calcola posizioni
        const positions = calculateScanPositions();
        const totalSteps = positions.length;
        
        if (totalSteps === 0) {
            showError('Nessuna posizione da scansionare');
            return;
        }
        
        // Avvia task
        AppState.task.running = true;
        AppState.task.current = {
            positions: positions,
            currentStep: 0,
            totalSteps: totalSteps
        };
        
        updateTaskStatus('Inizializzazione', 0);
        logToTaskLog(`Avvio scansione automatica: ${totalSteps} posizioni totali`);
        
        // Esegui movimenti
        for (let i = 0; i < positions.length; i++) {
            if (!AppState.task.running) {
                logToTaskLog('Task interrotto dall\'utente', 'warning');
                break;
            }
            
            const pos = positions[i];
            await executeMovement(pos.platform, pos.tilt, i + 1, totalSteps);
        }
        
        // Completamento
        if (AppState.task.running) {
            AppState.task.running = false;
            updateTaskStatus('Completato', 100);
            logToTaskLog('Scansione automatica completata con successo', 'success');
            showSuccess('Task automatico completato');
        }
    }
    
    /**
     * Interrompe task automatico
     */
    function stopAutomaticTask() {
        if (!AppState.task.running) {
            showError('Nessun task in esecuzione');
            return;
        }
        
        AppState.task.running = false;
        updateTaskStatus('Interrotto', AppState.task.progress);
        logToTaskLog('Task automatico interrotto dall\'utente', 'warning');
        showSuccess('Task automatico interrotto');
    }
    
    /**
     * Reset posizione iniziale
     */
    function resetToInitialPosition() {
        if (AppState.task.running) {
            showError('Impossibile resettare durante task in esecuzione');
            return;
        }
        
        AppState.platform.angle = 0;
        AppState.tilt.angle = 0;
        updatePlatformDisplay();
        updateTiltDisplay();
        
        updateTaskStatus('Inattivo', 0);
        logToTaskLog('Posizione resettata a 0°, 0°');
        showSuccess('Posizione resettata');
    }
    
    // Event listeners per task automatici
    $('#start-scan').click(startAutomaticTask);
    $('#stop-scan').click(stopAutomaticTask);
    $('#reset-position').click(resetToInitialPosition);
    $('#save-task').click(saveCustomTask);
    $('#load-task').click(loadCustomTask);
    
    // Aggiorna configurazione quando cambiano i valori
    $('#vertical-angles, #horizontal-step, #movement-delay').on('input', updateTaskConfig);
    $('input[name="operation-mode"]').change(updateTaskConfig);

    // ========================================
    // INIZIALIZZAZIONE
    // ========================================
    
    /**
     * Carica task personalizzati da localStorage
     */
    function loadCustomTasksFromStorage() {
        try {
            const saved = localStorage.getItem('customTasks');
            if (saved) {
                AppState.task.custom = JSON.parse(saved);
            }
        } catch (error) {
            console.warn('Errore nel caricamento task personalizzati:', error);
        }
    }
    
    /**
     * Inizializza l'applicazione
     */
    function initializeApp() {
        // Carica task personalizzati
        loadCustomTasksFromStorage();
        
        // Imposta sezione di default
        switchSection('manual-control');
        
        // Carica task preimpostati
        loadPresetTasks();
        
        // Setup filtri log
        setupLogFilters();
        
        // Aggiorna display iniziali
        updatePlatformDisplay();
        updateTiltDisplay();
        updateTaskStatus('Inattivo', 0);
        
        // Log inizializzazione
        logToConsole('Sistema di controllo meccatronico inizializzato');
        logToConsole('Piattaforma: 0°, Inclinazione: 0°');
        logToConsole('Pronto per operazioni manuali e automatiche');
        
        logToTaskLog('Sistema pronto per task automatici');
        
        // Simula connessione hardware
        setTimeout(() => {
            logToConsole('Hardware connesso e operativo');
        }, 1000);
    }
    
    // Avvia applicazione
    initializeApp();
    
    // ========================================
    // GESTIONE ERRORI GLOBALE
    // ========================================
    
    // Intercetta errori JavaScript
    window.addEventListener('error', function(e) {
        showError(`Errore JavaScript: ${e.message}`);
    });
    
    // Intercetta promesse rifiutate
    window.addEventListener('unhandledrejection', function(e) {
        showError(`Errore asincrono: ${e.reason}`);
    });
}); 