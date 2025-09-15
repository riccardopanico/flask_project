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
            sequence: [],
            presets: [
                {
                    id: 'quick-scan', name: 'Scansione Rapida',
                    description: '4 livelli verticali, rotazione oraria',
                    sequence: ['B=0','P_OR=360','B=30','P_OR=360','B=60','P_OR=360','B=90','P_OR=360']
                },
                {
                    id: 'high-def-vertical', name: 'Alta Definizione Verticale',
                    description: '8 livelli verticali, rotazione oraria',
                    sequence: ['B=0','P_OR=360','B=12.9','P_OR=360','B=25.7','P_OR=360','B=38.6','P_OR=360','B=51.4','P_OR=360','B=64.3','P_OR=360','B=77.1','P_OR=360','B=90','P_OR=360']
                },
                {
                    id: 'three-level-inspection', name: 'Ispezione a 3 Livelli',
                    description: '3 livelli verticali, rotazione antioraria',
                    sequence: ['B=0','P_AN=360','B=45','P_AN=360','B=90','P_AN=360']
                },
                {
                    id: 'ultra-fine-scan', name: 'Scansione Ultra Fine',
                    description: '10 livelli verticali, rotazione oraria',
                    sequence: ['B=0','P_OR=360','B=10','P_OR=360','B=20','P_OR=360','B=30','P_OR=360','B=40','P_OR=360','B=50','P_OR=360','B=60','P_OR=360','B=70','P_OR=360','B=80','P_OR=360','B=90','P_OR=360']
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

    function renderStatusBadge(){
        let status = AppState.system.status || 'Idle';
        if(AppState.task.running){
            status = 'In Esecuzione';
        }else if(AppState.task.progress === 100){
            status = 'Completato';
        }else if(status === 'STOP'){ // fermato manualmente
            status = 'Interrotto';
        }else if(AppState.task.progress > 0 && status !== 'Errore' && status !== 'Disconnesso'){
            status = 'Interrotto';
        }

        const classMap = {
            'Idle': 'idle',
            'Connesso': 'idle',
            'In Esecuzione': 'running',
            'Movimento': 'running',
            'Completato': 'completed',
            'Interrotto': 'error',
            'Errore': 'error',
            'Disconnesso': 'error'
        };

        $('#dashboard-status')
            .text(status)
            .removeClass('idle running completed error')
            .addClass(classMap[status] || 'idle');
    }

    function updateDashboard(){
        $('#dashboard-platform').text(`${AppState.platform.angle}°`);
        $('#dashboard-tilt').text(`${AppState.tilt.angle}°`);
        $('#dashboard-progress').text(`${AppState.task.progress}%`);
        renderStatusBadge();
        $('#current-mode').text(AppState.ui.currentSection === 'manual-control' ? 'Controllo Manuale' : 'Task Automatici');
    }

    function updateManualInputsState(){
        const disabled = AppState.task.running || AppState.system.status === 'Movimento';
        $('#platform-input, #tilt-input').prop('disabled', disabled);
    }

    function setManualControlsEnabled(enabled){
        $('#manual-control button').prop('disabled', !enabled);
        updateManualInputsState();
    }

    function manualCommandsAllowed(){
        if(AppState.task.running || AppState.system.status === 'Movimento' || SerialManager.busy){
            showError('Comando non consentito: movimento in corso');
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

    function setTaskProgress(percent){
        const p = Math.max(0, Math.min(100, parseInt(percent)));
        updateTaskUI(AppState.task.running ? 'In Esecuzione' : 'Inattivo', p);
    }

    function setTaskState(running){
        AppState.task.running = running;
        setManualControlsEnabled(!running && AppState.system.status !== 'Movimento');
        updateTaskUI(running ? 'In Esecuzione' : 'Inattivo', AppState.task.progress);
        updateManualInputsState();
    }

    function setSystemStatus(status){
        AppState.system.status = status;
        setManualControlsEnabled(!AppState.task.running && status !== 'Movimento');
        updateManualInputsState();
        updateDashboard();
    }

    function updateTaskUI(status, progress){
        if(status) $('#task-status').text(status);
        AppState.task.progress = progress;
        $('#progress-text').text(`${progress}%`);
        $('#progress-bar').css('width', `${progress}%`);
        $('#start-scan').prop('disabled', AppState.task.running);
        $('#stop-scan').prop('disabled', !AppState.task.running);
        const resetDisabled = AppState.task.running || AppState.system.status === 'Movimento';
        $('#reset-position').prop('disabled', resetDisabled);
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

    $('.task-tab-btn').click(function(){
        const target = $(this).data('target');
        $('.task-tab-content').addClass('hidden');
        $(`#${target}`).removeClass('hidden');
        $('.task-tab-btn').removeClass('active-task-tab');
        $(this).addClass('active-task-tab');
    });

    // -- Controllo Manuale ----------------------------------------------------
    $('#manual-control').on('click', '.control-btn[data-action="platform"]', function(){
        if(manualCommandsAllowed()){
            const delta = parseInt($(this).data('step'));
            const target = NORMALIZE(AppState.platform.angle + delta);
            if(VALIDATORS.platform(target)) SerialManager.movePlatform(target);
            else showError('Angolo piattaforma non valido');
        }
    });
    $('#platform-go').click(()=>{
        if(manualCommandsAllowed()){
            const val = parseFloat($('#platform-input').val());
            if(VALIDATORS.platform(val)) SerialManager.movePlatform(val);
            else showError('Angolo piattaforma non valido');
        }
    });
    bindEnter('#platform-input', '#platform-go');

    $('#manual-control').on('click', '.control-btn[data-action="tilt"]', function(){
        if(manualCommandsAllowed()){
            const delta = parseInt($(this).data('step'));
            const target = AppState.tilt.angle + delta;
            if(VALIDATORS.tilt(target)) SerialManager.moveTilt(target);
            else showError('Angolo inclinazione non valido');
        }
    });
    $('#tilt-go').click(()=>{
        if(manualCommandsAllowed()){
            const val = parseFloat($('#tilt-input').val());
            if(VALIDATORS.tilt(val)) SerialManager.moveTilt(val);
            else showError('Angolo inclinazione non valido');
        }
    });
    bindEnter('#tilt-input', '#tilt-go');

    // -- Task Automatici ------------------------------------------------------
    function renderCommandList(){
        const list = $('#command-list');
        list.empty();
        AppState.task.sequence.forEach((cmd, idx) => {
            const item = $(`<li class="flex items-center justify-between px-2 py-1" data-idx="${idx}" draggable="true">
                    <span>${cmd}</span>
                    <button class="cmd-remove text-xs px-1 text-red-600" data-idx="${idx}">✕</button>
                </li>`);
            list.append(item);
        });
    }

    function loadPresetTasks(){
        const container = $('#preset-tasks');
        container.off('click', '.load-preset');
        container.off('click', '.start-preset');
        container.off('click', '.delete-task');
        container.empty();
        const tasks = [...AppState.task.presets, ...AppState.task.custom];
        tasks.forEach(task => {
            const isCustom = AppState.task.custom.some(t => t.id === task.id);
            const deleteBtn = isCustom ? `<button class="task-btn delete-task" data-task-id="${task.id}">Elimina</button>` : '';
            const el = $(
                `<div class="task-card" data-task-id="${task.id}">
                    <div class="task-name">${task.name}</div>
                    <div class="task-description">${task.description}</div>
                    <div class="task-params">${task.sequence ? task.sequence.length : 0} comandi</div>
                    <div class="task-actions">
                        <button class="task-btn primary load-preset" data-task-id="${task.id}">Carica</button>
                        <button class="task-btn start-preset" data-task-id="${task.id}">Avvia</button>
                        ${deleteBtn}
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
        container.on('click', '.delete-task', function(){
            const btn = $(this);
            const taskId = btn.data('task-id');
            if(!btn.data('confirm')){
                btn.data('confirm', true).addClass('confirm').text('✅ Conferma');
                setTimeout(() => {
                    btn.data('confirm', false).removeClass('confirm').text('��� Elimina');
                }, 3000);
            }else{
                AppState.task.custom = AppState.task.custom.filter(t => t.id !== taskId);
                localStorage.setItem('customTasks', JSON.stringify(AppState.task.custom));
                loadPresetTasks();
                showSuccess('Task eliminato');
                logToConsole(`Task eliminato: ${taskId}`, 'warn');
            }
        });
    }

    function loadPresetTask(taskId){
        const t = [...AppState.task.presets, ...AppState.task.custom].find(x => x.id === taskId);
        if(!t){ showError('Task non trovato'); return; }
        $('#task-name').val(t.name);
        $('#task-description').val(t.description);
        AppState.task.sequence = [...t.sequence];
        $('.task-card').removeClass('selected');
        $(`.task-card[data-task-id="${taskId}"]`).addClass('selected');
        logToConsole(`Task caricato: ${t.name}`,'info');
        showSuccess(`Task "${t.name}" caricato`);
        renderCommandList();
    }

    function saveTask(){
        const name = $('#task-name').val().trim();
        const description = $('#task-description').val().trim();
        if(!name){ showError('Nome task obbligatorio'); return; }
        if(AppState.task.sequence.length === 0){ showError('Sequenza vuota'); return; }
        const task = { id: 'custom-' + Date.now(), name, description, sequence: [...AppState.task.sequence] };
        AppState.task.custom = AppState.task.custom.filter(t => t.name !== name);
        AppState.task.custom.push(task);
        localStorage.setItem('customTasks', JSON.stringify(AppState.task.custom));
        loadPresetTasks();
        logToConsole(`Task salvato: ${name}`, 'ok');
        showSuccess(`Task "${name}" salvato`);
    }

    function startAutomaticTask(){
        if(AppState.task.running){ showError('Task già in esecuzione'); return; }
        if(AppState.task.sequence.length === 0){ showError('Sequenza vuota'); return; }
        const total = AppState.task.sequence.length;
        AppState.task.current = { totalSteps: total, completed: 0 };
        AppState.task.progress = 0;
        const seq = AppState.task.sequence.join(';');
        SerialManager.startTask(seq);
        setTaskState(true);
        setSystemStatus('Movimento');
        logToConsole(`Avvio task automatico: ${total} comandi`);
    }

    function stopAutomaticTask(){
        if(!AppState.task.running){ showError('Nessun task in esecuzione'); return; }
        SerialManager.stopTask();
        setTaskState(false);
        setSystemStatus('STOP');
        logToConsole('Richiesta interruzione task automatico','warn');
    }

    function resetToInitialPosition(){
        if(AppState.task.running || AppState.system.status === 'Movimento' || SerialManager.busy){
            showError('Impossibile resettare durante movimento in corso');
            return;
        }
        SerialManager.resetPosition();
        setSystemStatus('Movimento');
        logToConsole('Reset posizione richiesto');
    }

    $('#start-scan').click(startAutomaticTask);
    $('#stop-scan').click(stopAutomaticTask);
    $('#reset-position').click(resetToInitialPosition);
    $('#save-task').click(saveTask);

    function addGroupCommands(group){
        let val;
        switch(group){
            case 'movement':
                val = parseFloat($('#cmd-B').val());
                if(!isNaN(val) && val >= 0 && val <= 90){
                    AppState.task.sequence.push(`B=${val.toFixed(1)}`);
                }
                break;
            case 'rotation':
                val = parseFloat($('#cmd-P_OR').val());
                if(!isNaN(val) && val >= 0){ AppState.task.sequence.push(`P_OR=${val}`); }
                val = parseFloat($('#cmd-P_AN').val());
                if(!isNaN(val) && val >= 0){ AppState.task.sequence.push(`P_AN=${val}`); }
                break;
            case 'config':
                val = parseInt($('#cmd-SPEED_B').val(),10);
                if(!isNaN(val) && val >= 50){ AppState.task.sequence.push(`SPEED_B=${val}`); }
                val = parseInt($('#cmd-SPEED_P').val(),10);
                if(!isNaN(val) && val >= 50){ AppState.task.sequence.push(`SPEED_P=${val}`); }
                val = parseInt($('#cmd-MOVE_DELAY').val(),10);
                if(!isNaN(val) && val >= 0){ AppState.task.sequence.push(`MOVE_DELAY=${val}`); }
                break;
            case 'limits':
                val = $('#cmd-SW_B').val();
                if(val) AppState.task.sequence.push(`SW_B_${val}`);
                val = $('#cmd-HW_B').val();
                if(val) AppState.task.sequence.push(`HW_B_${val}`);
                val = $('#cmd-SW_P').val();
                if(val) AppState.task.sequence.push(`SW_P_${val}`);
                break;
        }
        renderCommandList();
    }

    $('#command-library').on('click', '.group-add', function(){
        const group = $(this).data('group');
        addGroupCommands(group);
    });

    $('#command-library').on('click', '.action-cmd', function(){
        const cmd = $(this).data('cmd');
        if(cmd){
            AppState.task.sequence.push(cmd);
            renderCommandList();
        }
    });

    function generateAdvancedSequence(){
        const steps = parseInt($('#gen-tilt-steps').val(),10);
        const turns = parseInt($('#gen-platform-turns').val(),10);
        const direction = $('#gen-direction').val();
        const delay = parseInt($('#gen-delay').val(),10);
        if(isNaN(steps) || steps <= 0 || isNaN(turns) || turns <= 0){
            showError('Parametri generatore non validi');
            return;
        }
        const seq = [];
        const stepAngle = steps === 1 ? 0 : 90/(steps-1);
        for(let i=0;i<steps;i++){
            const angle = (stepAngle*i).toFixed(1);
            seq.push(`B=${angle}`);
            for(let r=0;r<turns;r++){
                seq.push(direction === 'ccw' ? 'P_AN=360' : 'P_OR=360');
            }
            if(!isNaN(delay)) seq.push(`MOVE_DELAY=${delay}`);
        }
        AppState.task.sequence = seq;
        renderCommandList();
    }

    $('#generate-advanced').click(generateAdvancedSequence);
    $('#gen-tilt-steps, #gen-platform-turns, #gen-direction, #gen-delay').on('input', generateAdvancedSequence);
    $('#command-list').on('click', '.cmd-remove', function(){
        const idx = parseInt($(this).data('idx'),10);
        AppState.task.sequence.splice(idx,1);
        renderCommandList();
    });

    function copySequence(){
        if(AppState.task.sequence.length === 0){ showError('Sequenza vuota'); return; }
        const seq = `TASK=${AppState.task.sequence.join(';')}`;
        navigator.clipboard.writeText(seq).then(() => {
            showSuccess('Comandi copiati negli appunti');
        }).catch(() => {
            showError('Copia negli appunti non riuscita');
        });
    }
    $('#copy-sequence').click(copySequence);

    let dragIdx = null;
    $('#command-list').on('dragstart', 'li', function(){
        dragIdx = $(this).data('idx');
        $(this).addClass('dragging');
    });
    $('#command-list').on('dragover', 'li', function(e){
        e.preventDefault();
        $(this).addClass('drag-over');
    });
    $('#command-list').on('dragleave', 'li', function(){
        $(this).removeClass('drag-over');
    });
    $('#command-list').on('drop', 'li', function(e){
        e.preventDefault();
        const targetIdx = $(this).data('idx');
        if(dragIdx !== null && dragIdx !== targetIdx){
            const seq = AppState.task.sequence;
            const [moved] = seq.splice(dragIdx,1);
            seq.splice(targetIdx,0,moved);
            renderCommandList();
        }
    });
    $('#command-list').on('dragend', 'li', function(){
        $(this).removeClass('dragging');
        $('#command-list li').removeClass('drag-over');
        dragIdx = null;
    });


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
        updateTaskUI('Inattivo',0);
        generateAdvancedSequence();
        logToConsole('Sistema di controllo meccatronico inizializzato');
        $('#connect-serial').on('click', () => SerialManager.connectSerial());
        updateManualInputsState();
    }

    initializeApp();

    Object.assign(window, {
        setAngle,
        setTaskProgress,
        setTaskState,
        setSystemStatus
    });
});
