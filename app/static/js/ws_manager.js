(function(window, $){
    'use strict';

    const WS_URL = `ws://${location.hostname}:8765`;
    const RECONNECT_DELAY = 3000;

    class WebSocketManager {
        constructor(url){
            this.url = url;
            this.ws = null;
            this.reconnectTimeout = null;
            this.connect();
        }

        connect(){
            if(this.ws){
                try{ this.ws.close(); }catch(e){}
            }
            const ws = new WebSocket(this.url);
            this.ws = ws;
            ws.addEventListener('open', () => {
                logToConsole('WebSocket connesso','success');
                setSystemStatus('Connesso');
                this.requestStatus();
            });
            ws.addEventListener('message', e => this.handleMessage(e.data));
            ws.addEventListener('close', () => {
                logToConsole('WebSocket chiuso','warning');
                setSystemStatus('Disconnesso');
                this.scheduleReconnect();
            });
            ws.addEventListener('error', () => {
                logToConsole('Errore WebSocket','error');
            });
        }

        scheduleReconnect(){
            if(this.reconnectTimeout) return;
            this.reconnectTimeout = setTimeout(() => {
                this.reconnectTimeout = null;
                logToConsole('Riconnessione WebSocket...','warning');
                this.connect();
            }, RECONNECT_DELAY);
        }

        send(action, data={}){
            const payload = JSON.stringify({action, data});
            if(this.ws && this.ws.readyState === WebSocket.OPEN){
                this.ws.send(payload);
                logToConsole(`WS -> ${payload}`);
            } else {
                logToConsole('Impossibile inviare: WebSocket non connesso','error');
            }
        }

        requestStatus(){ this.send('get_status'); }
        startTask(config){ this.send('start_task', config); }
        stopTask(){ this.send('stop_task'); }
        movePlatform(angle){ this.send('move_platform', {angle}); }
        moveTilt(angle){ this.send('move_tilt', {angle}); }

        handleMessage(msg){
            logToConsole(`WS <- ${msg}`,'info');
            try{
                const data = JSON.parse(msg);
                if(Array.isArray(data)) return data.forEach(d => this.applyMessage(d));
                this.applyMessage(data);
            }catch(e){
                console.error('WS message error', e);
            }
        }

        applyMessage({action, data}){
            switch(action){
                case 'status':
                    if(data.platform !== undefined) setAngle('platform', parseFloat(data.platform), {log:false});
                    if(data.tilt !== undefined) setAngle('tilt', parseFloat(data.tilt), {log:false});
                    if(data.task){
                        if(typeof data.task.running === 'boolean') setTaskState(data.task.running);
                        if(typeof data.task.progress === 'number') setTaskProgress(data.task.progress);
                    }
                    if(data.systemStatus) setSystemStatus(data.systemStatus);
                    break;
                case 'update_platform':
                    if(data.angle !== undefined) setAngle('platform', parseFloat(data.angle), {log:false});
                    break;
                case 'update_tilt':
                    if(data.angle !== undefined) setAngle('tilt', parseFloat(data.angle), {log:false});
                    break;
                case 'task_progress':
                    if(data.progress !== undefined) setTaskProgress(data.progress);
                    break;
                case 'task_state':
                    if(data.running !== undefined) setTaskState(data.running);
                    break;
                case 'system_status':
                    if(data.status) setSystemStatus(data.status);
                    break;
                default:
                    console.warn('Azione WS sconosciuta', action);
            }
        }
    }

    window.WebSocketManager = new WebSocketManager(WS_URL);
})(window, jQuery);
