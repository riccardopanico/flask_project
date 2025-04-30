// static/ip_camera_monitor.js
$(function(){
    // -------- CONFIG --------
    const WS_HOST = window.location.hostname;
    const WS_PORT = 8765;
    const WS_URL  = `ws://${WS_HOST}:${WS_PORT}`;
    const INITIAL_RETRY = 1000;
    const MAX_RETRY     = 30000;
  
    // -------- STATO --------
    let socket = null;
    let connected = false;
    let waiting   = false;
    let retryInterval = INITIAL_RETRY;
    const messageQueue = [];
  
    // -------- UI HELPERS --------
    function switchTab(name){
      $('#tab-stream, #tab-models, #tab-advanced-json').hide();
      $(`#tab-${name}`).show();
      ['stream','models','advanced-json'].forEach(n=>{
        const btn = $(`#tab-${n}-btn`);
        btn.toggleClass('bg-white', n===name)
           .toggleClass('bg-gray-100', n!==name)
           .attr('aria-selected', n===name);
      });
    }
    $('#tab-stream-btn').click(e=>{e.preventDefault();switchTab('stream');});
    $('#tab-models-btn').click(e=>{e.preventDefault();switchTab('models');});
    $('#tab-advanced-json-btn').click(e=>{e.preventDefault();switchTab('advanced-json');});
  
    // -------- CONFIG BUILDER --------
    function buildConfig(){
      const parseIntOrNull = v=>{ let n=parseInt(v,10); return isNaN(n)?null:n; };
      const parseFloatOrNull = v=>{ let f=parseFloat(v); return isNaN(f)?null:f; };
      const classes = $('#classes-filter-container input:checked').map((i,el)=>el.value).get();
      return {
        source: $('#stream-url').val()||'0',
        width:  parseIntOrNull($('#width').val()),
        height: parseIntOrNull($('#height').val()),
        fps:    parseIntOrNull($('#fps').val()),
        prefetch: 10,
        skip_on_full_queue: true,
        quality: parseIntOrNull($('#quality').val())||100,
        use_cuda: $('#use-cuda').prop('checked'),
        max_workers: 1,
        model_behaviors: {
          [$('#model-name').val()||'yolo11n.pt']: {
            draw: $('#draw-boxes').prop('checked'),
            count: $('#count-objects').prop('checked'),
            confidence: parseFloatOrNull($('#confidence').val())||0.5,
            iou: parseFloatOrNull($('#iou').val())||0.5
          }
        },
        count_line: $('#count-line').val()||null,
        metrics_enabled: $('#metrics-enabled').prop('checked'),
        classes_filter: classes.length ? classes : null
      };
    }
    function updateJson(){ $('#advanced-json-textarea').val(JSON.stringify(buildConfig(),null,2)); }
    $('#quality,#fps').on('input',function(){
      $(`#${this.id}-val`).text(this.value);
      updateJson();
    });
    $('#stream-url,#width,#height,#use-cuda,#metrics-enabled,#model-name,#draw-boxes,#count-objects,#confidence,#iou,#count-line')
      .on('input change', updateJson);
    updateJson();
  
    // -------- RENDER CAMERA LIST --------
    function renderCameraList(list){
      const $section = $('section[aria-label="Camera List"]');
      $section.find('article').remove();
      list.forEach(c=>{
        const run = c.status==='running';
        const $art = $(`
          <article class="border rounded-md bg-white p-4 space-y-2">
            <div class="flex justify-between items-center">
              <span class="font-semibold text-sm">${c.name}</span>
              <span class="${run?'bg-blue-500':'bg-red-500'} text-white text-[10px] font-semibold rounded-full px-2 py-[2px] flex items-center space-x-1">
                ${run?'<span class="w-2 h-2 rounded-full bg-green-400 block"></span>':''}
                <span>${c.status}</span>
              </span>
            </div>
            <p class="text-xs text-gray-400">${c.clients} active client${c.clients!==1?'s':''}</p>
            <div class="flex space-x-2 text-xs font-semibold">
              <button data-src="${c.name}" class="btn-start border rounded px-3 py-1 ${run?'text-gray-400 cursor-not-allowed border-gray-200':'border-gray-300'}" ${run?'disabled':''}>
                <i class="fas fa-play"></i><span>Start</span>
              </button>
              <button data-src="${c.name}" class="btn-stop border rounded px-3 py-1 ${run?'border-gray-300':'text-gray-400 cursor-not-allowed border-gray-200'}" ${run?'':'disabled'}>
                <span>Stop</span>
              </button>
              <button data-src="${c.name}" class="btn-select bg-blue-600 hover:bg-blue-700 text-white rounded px-3 py-1">
                <i class="fas fa-eye"></i><span>Select</span>
              </button>
            </div>
          </article>
        `);
        $section.append($art);
      });
    }
  
    // -------- UPDATE PANELS --------
    function updatePanel(msg){
      if(msg.action==='metrics'){
        const d = msg.data;
        const $m = $('[aria-label="Camera Metrics"]');
        $m.find('p:contains("FPS") + p').text(d.avg_inf_ms? (1000/d.avg_inf_ms).toFixed(1) : '–');
        $m.find('p:contains("Frames Served") + p').text(d.frames_served);
        $m.find('p:contains("Data Transferred") + p').text((d.bytes_served/1024/1024).toFixed(2)+' MB');
        $m.find('p:contains("Avg Inference") + p').text(d.avg_inf_ms.toFixed(2)+' ms');
        const $ctr = $m.find('[aria-label^="Object detection"] .flex');
        $ctr.empty();
        Object.entries(d.counters).forEach(([cls,c])=>{
          $ctr.append(`
            <span class="bg-gray-100 rounded px-2 py-[2px] flex items-center space-x-1">
              <span>${cls}</span>
              <span class="bg-gray-300 text-gray-700 rounded-full px-2 py-[1px] font-semibold">${c}</span>
            </span>
          `);
        });
      }
      // health, inference, count, ecc. possono essere gestiti similmente
    }
  
    // -------- QUEUE & RECONNECT LOGIC --------
    function connectWS(){
      socket = new WebSocket(WS_URL);
      socket.onopen = ()=>{
        console.log('WS connected');
        connected = true;
        retryInterval = INITIAL_RETRY;
        queueMessage({action:'list_cameras'});
      };
      socket.onmessage = ev=>{
        const msg = JSON.parse(ev.data);
        if(msg.status==='readyForNext'){
          waiting = false;
          sendNextMessage();
        }
        else if(msg.action==='list_cameras'){
          renderCameraList(msg.data);
        }
        else if(['metrics','health','inference','count'].includes(msg.action)){
          updatePanel(msg);
        }
      };
      socket.onclose = ()=>{
        console.warn('WS closed, retry in', retryInterval);
        connected = false;
        setTimeout(() => { if(!connected) connectWS(); }, retryInterval);
        retryInterval = Math.min(MAX_RETRY, retryInterval*2);
      };
      socket.onerror = e=>{
        console.error('WS error', e);
        socket.close();
      };
    }
  
    function queueMessage(msg){
      messageQueue.push(JSON.stringify(msg));
      sendNextMessage();
    }
  
    function sendNextMessage(){
      if(!waiting && connected && messageQueue.length){
        const m = messageQueue.shift();
        socket.send(m);
        waiting = true;
      }
    }
  
    // -------- WIRE UI EVENTS --------
    $('section[aria-label="Camera List"]')
      .on('click','.btn-start',  function(){ queueMessage({action:'start', source_id: $(this).data('src')}); })
      .on('click','.btn-stop',   function(){ queueMessage({action:'stop',  source_id: $(this).data('src')}); })
      .on('click','.btn-select', function(){
        const sid = $(this).data('src');
        $('section[aria-label="Camera Stream"] .flex-grow').html(`
          <img class="w-full h-full object-contain" src="/api/ip_camera/stream/${sid}">
        `);
        queueMessage({action:'get_health',  source_id:sid});
        queueMessage({action:'get_metrics', source_id:sid});
      });
  
    $('#apply-btn').click(()=>{
      const src = $('section[aria-label="Camera Stream"] img').attr('src').split('/').pop();
      queueMessage({action:'update_config', source_id:src, config:buildConfig()});
    });
  
    $('button:contains("Refresh")').click(e=>{
      e.preventDefault();
      queueMessage({action:'list_cameras'});
    });
  
    // -------- STARTUP --------
    connectWS();
    switchTab('stream');
  });
  