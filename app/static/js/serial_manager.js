(function(window){
    'use strict';

    const SerialManager = {
        port: null,
        reader: null,
        writer: null,
        encoder: null,
        decoder: null,
        queue: [],
        busy: false,
        stopFlag: false,
        statusBuffer: null,

        async connectSerial(){
            if(!('serial' in navigator)){
                window.showError('Web Serial API non supportata');
                return;
            }
            try{
                this.port = await navigator.serial.requestPort();
                await this.port.open({ baudRate: 115200 });

                this.encoder = new TextEncoderStream();
                this.encoder.readable.pipeTo(this.port.writable);
                this.writer = this.encoder.writable.getWriter();

                this.decoder = new TextDecoderStream();
                this.port.readable.pipeTo(this.decoder.writable);
                this.reader = this.decoder.readable.getReader();

                window.logToConsole('Porta seriale connessa','ok');
                window.setSystemStatus('Connesso');

                this.readLoop();
                this.requestStatus();
            }catch(e){
                window.showError('Errore apertura seriale: ' + e.message);
            }
        },

        async readLoop(){
            let buffer = '';
            try{
                while(true){
                    const { value, done } = await this.reader.read();
                    if(done) break;
                    if(value) buffer += value;
                    let idx;
                    while((idx = buffer.indexOf('\n')) !== -1){
                        const line = buffer.slice(0, idx).trim();
                        buffer = buffer.slice(idx + 1);
                        if(line) this.handleLine(line);
                    }
                }
            }catch(e){
                window.showError('Errore lettura seriale: ' + e.message);
            }
        },

        handleLine(line){
            if(this.statusBuffer){
                this.statusBuffer.push(line);
                if(line.startsWith('}')) this.finishStatus();
                return;
            }
            if(line.startsWith('STATUS')){
                window.logToConsole(`<- ${line}`, 'status');
                this.statusBuffer = [line.substring(line.indexOf('{'))];
                if(line.includes('}')) this.finishStatus();
                return;
            }

            let type = 'info';
            if(line.startsWith('ERROR') || line.startsWith('STOP')) type = 'error';
            else if(line.startsWith('WARN')) type = 'warn';
            else if(line.startsWith('OK')) type = 'ok';
            else if(line.startsWith('MOVE_START')) type = 'move_start';
            else if(line.startsWith('MOVE_DONE') || line.startsWith('TASK: DONE')) type = 'move_done';

            window.logToConsole(`<- ${line}`, type);

            if(line.startsWith('TASK: STARTED')){
                window.setTaskState(true);
                window.setTaskProgress(0);
                window.setSystemStatus('Movimento');
                return;
            }
            if(line.startsWith('TASK: DONE')){
                window.setTaskState(false);
                window.setTaskProgress(100);
                window.setSystemStatus('Completato');
                return;
            }
            if(line.startsWith('STOP')){
                window.setTaskState(false);
                window.setSystemStatus('STOP');
                window.showError(line.substring(line.indexOf(':')+1).trim());
                return;
            }
            if(line.startsWith('OK')) window.showSuccess(line.substring(3).trim());
            else if(line.startsWith('ERROR')) window.showError(line.substring(6).trim());
            // La coda viene sbloccata solo dopo il messaggio STATUS
        },

        finishStatus(){
            try{
                const text = this.statusBuffer.join('\n');
                const json = text.replace(/(\w+)\s*:/g, '"$1":');
                const data = JSON.parse(json);
                if(data.angle_piattaforma !== undefined)
                    window.setAngle('platform', parseFloat(data.angle_piattaforma), {log:false});
                if(data.angle_braccio !== undefined)
                    window.setAngle('tilt', parseFloat(data.angle_braccio), {log:false});
                if(data.is_moving !== undefined)
                    window.setSystemStatus(data.is_moving ? 'Movimento' : 'Idle');
                if(window.AppState.task.running && data.last_command){
                    const m = data.last_command.match(/^P_(OR|AN)=(\d+)/);
                    if(m){
                        const angle = parseInt(m[2], 10);
                        if(angle % 360 === 0){
                            const cur = window.AppState.task.current;
                            if(cur && cur.totalSteps){
                                cur.completed = (cur.completed || 0) + angle / 360;
                                const prog = Math.round((cur.completed / cur.totalSteps) * 100);
                                window.setTaskProgress(prog);
                            }
                        }
                    }
                }
            }catch(e){
                window.showError('Errore parsing STATUS: ' + e.message);
            }
            this.statusBuffer = null;
            this.busy = false;
            this.processQueue();
        },

        sendCommand(cmd){
            if(this.stopFlag) return;
            this.queue.push(cmd.trim() + '\n');
            this.processQueue();
        },

        async processQueue(){
            if(this.busy || !this.writer || this.queue.length === 0 || this.stopFlag) return;
            const msg = this.queue.shift();
            try{
                this.busy = true;
                await this.writer.write(msg);
                const type = msg.trim()==='STOP' ? 'warn' : 'info';
                window.logToConsole(`-> ${msg.trim()}`, type);
            }catch(e){
                window.showError('Errore invio: ' + e.message);
                this.busy = false;
            }
        },

        handleStop(){
            this.queue = [];
            this.stopFlag = true;
            if(this.writer) this.writer.write('STOP\n');
            window.logToConsole('-> STOP','warn');
            setTimeout(()=>{ this.stopFlag = false; this.busy = false; this.processQueue(); }, 100);
        },

        movePlatform(angle, dir){
            if(angle === 360){
                const d = dir || (window.AppState?.task?.config?.rotationDirection || 'cw');
                this.sendCommand(d === 'ccw' ? 'P_AN=360' : 'P_OR=360');
            }else{
                this.sendCommand(`P=${angle}`);
            }
        },
        moveTilt(angle){ this.sendCommand(`B=${angle}`); },
        startTask(seq){ this.sendCommand(`TASK=${seq}`); },
        stopTask(){ this.handleStop(); },
        resetPosition(){ this.sendCommand('RESET_POS'); },
        requestStatus(){ this.sendCommand('STATUS'); }
    };

    window.SerialManager = SerialManager;
})(window);

