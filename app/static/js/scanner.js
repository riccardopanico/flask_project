$(function(){
    const { AppState, logToConsole, showError, showSuccess } = window;
    AppState.ui.currentApp = 'camera-monitor';
    AppState.ui.currentSection = 'manual-control';

    Object.assign(AppState, {
        platform: { angle: 0 },
        tilt: { angle: 0 },
        system: { status: 'Disconnesso' },
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
                {
                    id: 'quick-scan', name: 'Scansione Rapida 4x90°',
                    description: 'Scansione veloce con 4 angolazioni verticali e step di 90°',
                    config: { verticalAngles: 4, horizontalStep: 90, movementDelay: 1, operationMode: 'sequential' }
                },
                {
                    id: 'high-def-vertical', name: 'Alta Definizione Verticale',
                    description: 'Scansione dettagliata con 8 angolazioni verticali e step di 15°',
                    config: { verticalAngles: 8, horizontalStep: 15, movementDelay: 3, operationMode: 'sequential' }
                },
                {
                    id: 'three-level-inspection', name: 'Ispezione a 3 Livelli',
                    description: 'Ispezione standard con 3 livelli di inclinazione',
                    config: { verticalAngles: 3, horizontalStep: 30, movementDelay: 2, operationMode: 'alternate' }
                },
                {
                    id: 'ultra-fine-scan', name: 'Scansione Ultra Fine',
                    description: 'Scansione di precisione con step di 5° e 10 angolazioni',
                    config: { verticalAngles: 10, horizontalStep: 5, movementDelay: 4, operationMode: 'sequential' }
                }
            ],
            custom: []
        }
    });

    // -- Utility ---------------------------------------------------------------
    const VALIDATORS = {
        platform: a => { const n = parseFloat(a); return !isNaN(n) && n >= 0 && n <= 360; },
        tilt: a => { const n = parseFloat(a); return !isNaN(n) && n >= 0 && n <= 90; }
    };
    const NORMALIZE = a => ((a % 360) + 360) % 360;
    const bindEnter = (input, btn) => $(input).keypress(e => e.which === 13 && $(btn).click());

    // -- Stato & UI ------------------------------------------------------------
    function updateAngleDom(type){
        if(type === 'platform'){
            $('#platform-angle').text(`${AppState.platform.angle}°`);
            $('#camera-angle-display').text(`${AppState.platform.angle}°`);
        }else{
            $('#tilt-angle').text(`${AppState.tilt.angle}°`);
        }
    }

    function updateDashboard(){
        $('#dashboard-platform').text(`${AppState.platform.angle}°`);
        $('#dashboard-tilt').text(`${AppState.tilt.angle}°`);
        $('#dashboard-progress').text(`${AppState.task.progress}%`);

        let status = AppState.system.status || 'Idle';
        let statusClass = 'idle';
        if(AppState.task.running){
            statusClass = 'running';
        }else if(AppState.task.progress === 100){
            statusClass = 'completed';
        }else if(AppState.task.progress > 0){
            statusClass = 'error';
        }
        $('#dashboard-status').text(status).removeClass('idle running completed error').addClass(statusClass);
        $('#current-mode').text(AppState.ui.currentSection === 'manual-control' ? 'Controllo Manuale' : 'Task Automatici');
    }

    function setManualControlsEnabled(enabled){
        $('#manual-control button, #manual-control input').prop('disabled', !enabled);
    }

    function manualCommandsAllowed(){
        if(AppState.task.running){
            showError('Comando non consentito: task in corso');
            return false;
        }
        return true;
    }

    function setAngle(type, angle, {log=true} = {}){
        const validate = VALIDATORS[type];
        if(!validate || !validate(angle)){
            showError(`Angolo ${type === 'platform' ? 'piattaforma' : 'inclinazione'} non valido`);
            return false;
        }
        if(type === 'platform') angle = NORMALIZE(angle);
        AppState[type].angle = angle;
        updateAngleDom(type);
        if(log) showSuccess(`${type === 'platform' ? 'Piattaforma' : 'Inclinazione'} a ${angle}°`);
        updateDashboard();
        return true;
    }

    const changeAngle = (type, delta, opts={}) => setAngle(type, AppState[type].angle + delta, opts);

    function setTaskProgress(percent){
        const p = Math.max(0, Math.min(100, parseInt(percent)));
        updateTaskUI(AppState.task.running ? 'In Esecuzione' : 'Inattivo', p);
    }

    function setTaskState(running){
        AppState.task.running = running;
        updateTaskUI(running ? 'In Esecuzione' : 'Inattivo', AppState.task.progress);
    }

    function setSystemStatus(status){
        AppState.system.status = status;
        updateDashboard();
    }

    function updateTaskUI(status, progress){
        if(status) $('#task-status').text(status);
        AppState.task.progress = progress;
        $('#progress-text').text(`${progress}%`);
        $('#progress-bar').css('width', `${progress}%`);
        $('#start-scan').prop('disabled', AppState.task.running);
        $('#stop-scan').prop('disabled', !AppState.task.running);
        $('#reset-position').prop('disabled', AppState.task.running);
        updateDashboard();
    }

    // -- Navigazione -----------------------------------------------------------
    function switchSection(sectionId){
        $('.section-content').addClass('hidden');
        $(`#${sectionId}`).removeClass('hidden');
        $('.tab-btn').removeClass('active-tab');
        $(`.tab-btn[data-target="${sectionId}"]`).addClass('active-tab');
        AppState.ui.currentSection = sectionId;
        logToConsole(`Sezione attivata: ${$(`.tab-btn[data-target="${sectionId}"]`).text()}`);
        updateDashboard();
    }
    $('.tab-btn').click(function(){
        const target = $(this).data('target');
        if(target) switchSection(target);
    });

    // -- Controllo Manuale ----------------------------------------------------
    $('#manual-control').on('click', '.control-btn[data-action="platform"]', function(){
        if(manualCommandsAllowed()){
            changeAngle('platform', parseInt($(this).data('step')));
            WebSocketManager.movePlatform(AppState.platform.angle);
        }
    });
    $('#platform-go').click(()=>{
        if(manualCommandsAllowed()){
            setAngle('platform', parseFloat($('#platform-input').val()));
            WebSocketManager.movePlatform(AppState.platform.angle);
        }
    });
    bindEnter('#platform-input', '#platform-go');

    $('#manual-control').on('click', '.control-btn[data-action="tilt"]', function(){
        if(manualCommandsAllowed()){
            changeAngle('tilt', parseInt($(this).data('step')));
            WebSocketManager.moveTilt(AppState.tilt.angle);
        }
    });
    $('#tilt-go').click(()=>{
        if(manualCommandsAllowed()){
            setAngle('tilt', parseFloat($('#tilt-input').val()));
            WebSocketManager.moveTilt(AppState.tilt.angle);
        }
    });
    bindEnter('#tilt-input', '#tilt-go');

    // -- Task Automatici ------------------------------------------------------
    function updateTaskConfig(){
        AppState.task.config.verticalAngles = parseInt($('#vertical-angles').val()) || 3;
        AppState.task.config.horizontalStep = parseInt($('#horizontal-step').val()) || 20;
        AppState.task.config.movementDelay = parseFloat($('#movement-delay').val()) || 2;
        AppState.task.config.operationMode = $('input[name="operation-mode"]:checked').val();
    }

    function loadPresetTasks(){
        const container = $('#preset-tasks');
        container.empty();
        AppState.task.presets.forEach(task => {
            const el = $(
                `<div class="task-card" data-task-id="${task.id}">
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
                </div>`);
            container.append(el);
        });
        container.on('click', '.load-preset', function(){
            loadPresetTask($(this).data('task-id'));
        });
        container.on('click', '.start-preset', function(){
            loadPresetTask($(this).data('task-id'));
            setTimeout(startAutomaticTask, 100);
        });
    }

    function loadPresetTask(taskId){
        const t = AppState.task.presets.find(x => x.id === taskId);
        if(!t){ showError('Task non trovato'); return; }
        $('#task-name').val(t.name);
        $('#task-description').val(t.description);
        $('#vertical-angles').val(t.config.verticalAngles);
        $('#horizontal-step').val(t.config.horizontalStep);
        $('#movement-delay').val(t.config.movementDelay);
        $(`input[name="operation-mode"][value="${t.config.operationMode}"]`).prop('checked', true);
        AppState.task.config = { ...t.config };
        $('.task-card').removeClass('selected');
        $(`.task-card[data-task-id="${taskId}"]`).addClass('selected');
        logToConsole(`Task caricato: ${t.name}`,'info');
        showSuccess(`Task "${t.name}" caricato`);
    }

    function saveCustomTask(){
        const name = $('#task-name').val().trim();
        const description = $('#task-description').val().trim();
        if(!name){ showError('Nome task obbligatorio'); return; }
        updateTaskConfig();
        const task = { id: 'custom-' + Date.now(), name, description, config: { ...AppState.task.config } };
        AppState.task.custom = AppState.task.custom.filter(t => t.name !== name);
        AppState.task.custom.push(task);
        localStorage.setItem('customTasks', JSON.stringify(AppState.task.custom));
        logToConsole(`Task salvato: ${name}`, 'success');
        showSuccess(`Task "${name}" salvato`);
    }

    function loadCustomTask(){
        if(AppState.task.custom.length === 0){ showError('Nessun task personalizzato salvato'); return; }
        const names = AppState.task.custom.map(t => t.name);
        const selected = prompt('Seleziona task:\n' + names.join('\n'));
        if(!selected) return;
        const task = AppState.task.custom.find(t => t.name === selected);
        if(!task){ showError('Task non trovato'); return; }
        $('#task-name').val(task.name);
        $('#task-description').val(task.description);
        $('#vertical-angles').val(task.config.verticalAngles);
        $('#horizontal-step').val(task.config.horizontalStep);
        $('#movement-delay').val(task.config.movementDelay);
        $(`input[name="operation-mode"][value="${task.config.operationMode}"]`).prop('checked', true);
        AppState.task.config = { ...task.config };
        logToConsole(`Task personalizzato caricato: ${task.name}`, 'info');
        showSuccess(`Task "${task.name}" caricato`);
    }

    function calculateScanPositions(){
        const c = AppState.task.config; const p = [];
        if(c.operationMode === 'sequential'){
            for(let t=0;t<c.verticalAngles;t++){
                const tilt = (90 / (c.verticalAngles - 1)) * t;
                for(let plat=0; plat<360; plat+=c.horizontalStep){
                    p.push({ platform: plat, tilt, step: p.length + 1 });
                }
            }
        }else{
            for(let plat=0; plat<360; plat+=c.horizontalStep){
                for(let t=0;t<c.verticalAngles;t++){
                    const tilt = (90 / (c.verticalAngles - 1)) * t;
                    p.push({ platform: plat, tilt, step: p.length + 1 });
                }
            }
        }
        return p;
    }

    function executeMovement(platformAngle, tiltAngle, step, total){
        return new Promise(res => {
            setAngle('platform', platformAngle, {log:false});
            setAngle('tilt', tiltAngle, {log:false});
            const progress = Math.round((step / total) * 100);
            updateTaskUI('In Esecuzione', progress);
            logToConsole(`Step ${step}/${total}: Piattaforma ${platformAngle}°, Inclinazione ${tiltAngle}°`);
            setTimeout(res, AppState.task.config.movementDelay * 1000);
        });
    }

    async function startAutomaticTask(){
        if(AppState.task.running){ showError('Task già in esecuzione'); return; }
        updateTaskConfig();
        if(AppState.task.config.verticalAngles < 1 || AppState.task.config.verticalAngles > 10){
            showError('Numero angolazioni verticali deve essere tra 1 e 10'); return;
        }
        if(AppState.task.config.horizontalStep < 1 || AppState.task.config.horizontalStep > 90){
            showError('Step angolare orizzontale deve essere tra 1° e 90°'); return;
        }
        if(AppState.task.config.movementDelay < 0.5 || AppState.task.config.movementDelay > 10){
            showError('Delay movimento deve essere tra 0.5 e 10 secondi'); return;
        }
        const positions = calculateScanPositions();
        const total = positions.length;
        if(total === 0){ showError('Nessuna posizione da scansionare'); return; }
        AppState.task.running = true;
        AppState.task.current = { positions, currentStep: 0, totalSteps: total };
        updateTaskUI('Inizializzazione', 0);
        logToConsole(`Avvio scansione automatica: ${total} posizioni totali`);
        WebSocketManager.startTask(AppState.task.config);
        for(let i=0;i<positions.length;i++){
            if(!AppState.task.running){ logToConsole('Task interrotto dall\'utente','warning'); break; }
            const pos = positions[i];
            await executeMovement(pos.platform, pos.tilt, i+1, total);
        }
        if(AppState.task.running){
            AppState.task.running = false;
            updateTaskUI('Completato', 100);
            logToConsole('Scansione automatica completata con successo','success');
            showSuccess('Task automatico completato');
        }
    }

    function stopAutomaticTask(){
        if(!AppState.task.running){ showError('Nessun task in esecuzione'); return; }
        AppState.task.running = false;
        updateTaskUI('Interrotto', AppState.task.progress);
        logToConsole('Task automatico interrotto dall\'utente','warning');
        showSuccess('Task automatico interrotto');
        WebSocketManager.stopTask();
    }

    function resetToInitialPosition(){
        if(AppState.task.running){ showError('Impossibile resettare durante task in esecuzione'); return; }
        setAngle('platform', 0, {log:false});
        setAngle('tilt', 0, {log:false});
        WebSocketManager.movePlatform(0);
        WebSocketManager.moveTilt(0);
        updateTaskUI('Inattivo', 0);
        logToConsole('Posizione resettata a 0°, 0°');
        showSuccess('Posizione resettata');
    }

    $('#start-scan').click(startAutomaticTask);
    $('#stop-scan').click(stopAutomaticTask);
    $('#reset-position').click(resetToInitialPosition);
    $('#save-task').click(saveCustomTask);
    $('#load-task').click(loadCustomTask);
    $('#vertical-angles, #horizontal-step, #movement-delay').on('input', updateTaskConfig);
    $('input[name="operation-mode"]').change(updateTaskConfig);

    function loadCustomTasksFromStorage(){
        try{
            const saved = localStorage.getItem('customTasks');
            if(saved) AppState.task.custom = JSON.parse(saved);
        }catch(e){ console.warn('Errore nel caricamento task personalizzati:', e); }
    }

    function initializeApp(){
        loadCustomTasksFromStorage();
        switchSection('manual-control');
        loadPresetTasks();
        updateAngleDom('platform');
        updateAngleDom('tilt');
        updateTaskUI('Inattivo',0);
        logToConsole('Sistema di controllo meccatronico inizializzato');
        logToConsole('Piattaforma: 0°, Inclinazione: 0°');
        logToConsole('Pronto per operazioni manuali e automatiche');
        logToConsole('Sistema pronto per task automatici');
        setTimeout(()=> {
            logToConsole('Hardware connesso e operativo');
            WebSocketManager.requestStatus();
        }, 1000);
    }

    initializeApp();

    Object.assign(window, {
        setAngle,
        setTaskProgress,
        setTaskState,
        setSystemStatus
    });
});
