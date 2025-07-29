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

                window.logToConsole('Porta seriale connessa','success');
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
                this.statusBuffer = [line.substring(line.indexOf('{'))];
                if(line.includes('}')) this.finishStatus();
                return;
            }
            window.logToConsole(`<- ${line}`);
            if(line.startsWith('OK')) window.showSuccess(line.substring(3));
            if(line.startsWith('ERROR')) window.showError(line.substring(6));
            this.busy = false;
            this.processQueue();
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
                window.logToConsole(`-> ${msg.trim()}`);
            }catch(e){
                window.showError('Errore invio: ' + e.message);
                this.busy = false;
            }
        },

        handleStop(){
            this.queue = [];
            this.stopFlag = true;
            if(this.writer) this.writer.write('STOP\n');
            window.logToConsole('-> STOP');
            setTimeout(()=>{ this.stopFlag = false; this.busy = false; this.processQueue(); }, 100);
        },

        movePlatform(angle){ this.sendCommand(`P=${angle}`); },
        moveTilt(angle){ this.sendCommand(`B=${angle}`); },
        startTask(seq){ this.sendCommand(`TASK=${seq}`); },
        stopTask(){ this.handleStop(); },
        requestStatus(){ this.sendCommand('STATUS'); }
    };

    window.SerialManager = SerialManager;
})(window);

