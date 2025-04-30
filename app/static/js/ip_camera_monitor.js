// static/js/ip_camera_monitor.js
$(function() {
    // -------- CONFIG --------
    const WS_URL      = `ws://${window.location.hostname}:8765`;
    const RETRY_INIT  = 1000;
    const RETRY_MAX   = 30000;
  
    // -------- STATE --------
    let socket = null;
    let retryInterval = RETRY_INIT;
    let waiting = false;
    const queue = [];
    let selectedSource = null;
  
    // -------- UTIL --------
    function send(msg) {
      queue.push(msg);
      flushQueue();
    }
    function flushQueue() {
      if (!waiting && socket && socket.readyState === WebSocket.OPEN && queue.length) {
        socket.send(JSON.stringify(queue.shift()));
        waiting = true;
      }
    }
    function onMessage(raw) {
      waiting = false;
      const m = JSON.parse(raw);
      switch (m.action) {
        case 'list_cameras':
          renderCameraList(m.data);
          break;
        case 'start':
          if (m.success && m.source_id === selectedSource) {
            loadStream(selectedSource);
            send({action:'get_config',    source_id: selectedSource});
            send({action:'get_health',    source_id: selectedSource});
            send({action:'get_metrics',   source_id: selectedSource});
          }
          send({action:'list_cameras'});
          break;
        case 'stop':
          if (m.success && m.source_id === selectedSource) {
            clearStream();
            clearPanels();
          }
          send({action:'list_cameras'});
          break;
        case 'health':
          renderHealth(m.source_id, m.data);
          break;
        case 'metrics':
          renderMetrics(m.source_id, m.data);
          break;
        case 'config':
          renderConfig(m.source_id, m.data);
          break;
        case 'update_config':
          showConfigResult(m);
          break;
        default:
          console.warn('[WS] unhandled:', m);
      }
      flushQueue();
    }
  
    // -------- WS LIFECYCLE --------
    function connect() {
      socket = new WebSocket(WS_URL);
      socket.onopen    = () => { retryInterval = RETRY_INIT; send({action:'list_cameras'}); };
      socket.onmessage = e => onMessage(e.data);
      socket.onclose   = () => {
        setTimeout(connect, retryInterval);
        retryInterval = Math.min(RETRY_MAX, retryInterval * 2);
      };
      socket.onerror   = () => socket.close();
    }
  
    // -------- RENDER CAMERA LIST --------
    function renderCameraList(list) {
      const $sec = $('#camera-list').empty()
        .append(`<h2 class="font-semibold text-base mb-2 select-none">Camera List</h2>
                 <button class="mb-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded px-3 py-1">+ Add</button>`);
      if (!list.length) {
        $sec.append(`<article class="border border-dashed border-gray-300 rounded-md bg-white p-4 text-center text-gray-400 italic">Nessuna camera disponibile</article>`);
        return;
      }
      list.forEach(cam => {
        const run = cam.status === 'running';
        const isSel = cam.name === selectedSource;
        const border = run ? 'border-blue-500' : 'border-gray-300';
        const selCls = isSel ? 'border-2 border-indigo-600' : '';
        const $a = $(`
          <article class="border ${border} ${selCls} rounded-md bg-white p-4 space-y-2">
            <div class="flex justify-between items-center">
              <span class="font-semibold text-sm">${cam.name}</span>
              <span class="${run?'bg-blue-500':'bg-red-500'} text-white text-[10px] font-semibold rounded-full px-2 py-[2px] flex items-center space-x-1">
                ${run?'<span class="w-2 h-2 rounded-full bg-green-400 block"></span>':''}
                <span>${cam.status}</span>
              </span>
            </div>
            <p class="text-xs text-gray-400">${cam.clients} active client${cam.clients!==1?'s':''}</p>
            <div class="flex space-x-2 text-xs font-semibold">
              <button data-src="${cam.name}" class="btn-start border rounded px-3 py-1 ${run?'text-gray-400 cursor-not-allowed border-gray-200':'border-gray-300'}" ${run?'disabled':''}>
                <i class="fas fa-play"></i><span>Start</span>
              </button>
              <button data-src="${cam.name}" class="btn-stop border rounded px-3 py-1 ${run?'border-gray-300':'text-gray-400 cursor-not-allowed border-gray-200'}" ${run?'':'disabled'}>
                <span>Stop</span>
              </button>
              <button data-src="${cam.name}" class="btn-select bg-blue-600 hover:bg-blue-700 text-white rounded px-3 py-1">
                <i class="fas fa-eye"></i><span>Select</span>
              </button>
            </div>
          </article>`);
        $sec.append($a);
      });
    }
  
    // -------- STREAM + PANELS --------
    function loadStream(sid) {
      $('#camera-stream .flex-grow').html(
        `<img class="w-full h-full object-contain" src="/api/ip_camera/stream/${sid}">`
      );
      $('#camera-stream').find('.border-blue-500, .border-gray-300').removeClass('border-gray-300').addClass('border-blue-500');
    }
    function clearStream() {
      $('#camera-stream .flex-grow').html('Nessuna camera selezionata');
    }
    function clearPanels() {
      $('#metrics-panel article').html('<div class="text-center text-gray-400 italic">Nessuna metrica disponibile</div>');
      $('#health-panel').html('<div class="text-center text-gray-400 italic">Nessun health check disponibile</div>');
      hideConfig();
    }
  
    // -------- RENDER HEALTH & METRICS --------
    function renderHealth(src, data) {
      let html = `<h4 class="font-semibold mb-2">Health (${src})</h4>`;
      html += Object.entries(data).map(([k,v])=>`<div><strong>${k}:</strong> ${v}</div>`).join('');
      $('#health-panel').html(html);
    }
    function renderMetrics(src, data) {
      let html = `<h4 class="font-semibold mb-2">Metrics (${src})</h4>`;
      html += `<div class="grid grid-cols-2 gap-2">
        <div><p class="text-xs">FPS</p><p class="font-semibold text-lg">${ data.frames_received? (data.frames_processed/data.frames_received*(data.avg_inf_ms?1000/data.avg_inf_ms:0)).toFixed(1) : '–' }</p></div>
        <div><p class="text-xs">Frames Served</p><p class="font-semibold text-lg">${data.frames_served}</p></div>
        <div><p class="text-xs">Data Transferred</p><p class="font-semibold text-lg">${(data.bytes_served/1024/1024).toFixed(2)} MB</p></div>
        <div><p class="text-xs">Avg Inference</p><p class="font-semibold text-lg">${data.avg_inf_ms.toFixed(2)} ms</p></div>
      </div>
      <p class="text-xs mt-2">Total Objects</p>
      <div class="border border-gray-300 rounded-md p-3 text-xs flex flex-wrap gap-2">`+
        Object.entries(data.counters||{}).map(([cls,c])=>
          `<span class="bg-gray-100 rounded px-2 py-[2px] flex items-center space-x-1">
             <span>${cls}</span><span class="bg-gray-300 text-gray-700 rounded-full px-2 py-[1px] font-semibold">${c}</span>
           </span>`
        ).join('')+
      `</div>`;
      $('#metrics-panel article').html(html);
    }
  
    // -------- CONFIG FORM & JSON --------
    function renderConfig(src, cfg) {
      if (src !== selectedSource) return;
      // Stream URL
      $('#stream-url').val(cfg.source);
      $('#width').val(cfg.width || '');
      $('#height').val(cfg.height || '');
      $('#fps').val(cfg.fps || 30);   $('#fps-val').text(cfg.fps||30);
      $('#quality').val(cfg.quality); $('#quality-val').text(cfg.quality);
  
      $('#use-cuda').prop('checked', cfg.use_cuda);
      $('#metrics-enabled').prop('checked', cfg.metrics_enabled);
  
      // model_behaviors: prendo primo key
      const [mname, mb] = Object.entries(cfg.model_behaviors)[0] || [];
      $('#model-name').val(mname||'');
      $('#draw-boxes').prop('checked', mb?.draw||false);
      $('#count-objects').prop('checked', mb?.count||false);
      $('#confidence').val(mb?.confidence||0).trigger('change');
      $('#iou').val(mb?.iou||0).trigger('change');
  
      $('#count-line').val(cfg.count_line||'');
  
      // classes_filter
      const cls = cfg.classes_filter||[];
      $('#classes-filter-container input').each((i,el)=>{
        $(el).prop('checked', cls.includes(el.value));
      });
  
      updateJson();
      showConfig();
    }
    function buildConfig() {
      const pi = v=>{ let n=parseInt(v,10); return isNaN(n)?null:n; };
      const pf = v=>{ let f=parseFloat(v); return isNaN(f)?null:f; };
      const cls = $('#classes-filter-container input:checked').map((i,e)=>e.value).get();
      return {
        source: $('#stream-url').val(),
        width: pi($('#width').val()),
        height: pi($('#height').val()),
        fps: pi($('#fps').val()),
        prefetch: 10,
        skip_on_full_queue: true,
        quality: pi($('#quality').val()),
        use_cuda: $('#use-cuda').prop('checked'),
        max_workers: 1,
        model_behaviors: {
          [$('#model-name').val()]: {
            draw: $('#draw-boxes').prop('checked'),
            count: $('#count-objects').prop('checked'),
            confidence: pf($('#confidence').val()),
            iou: pf($('#iou').val())
          }
        },
        count_line: $('#count-line').val()||null,
        metrics_enabled: $('#metrics-enabled').prop('checked'),
        classes_filter: cls.length ? cls : null
      };
    }
    function updateJson() {
      $('#advanced-json-textarea').val(JSON.stringify(buildConfig(),null,2));
    }
  
    // -------- CONFIG UI SHOW/HIDE --------
    function showConfig() {
      $('form[id^="tab-"]').show();
      $('#tab-stream').show(); switchTab('stream');
    }
    function hideConfig() {
      $('form[id^="tab-"]').hide();
      $('#tab-stream, #tab-models, #tab-advanced-json').hide();
    }
  
    // -------- UI EVENTS --------
    // tabs
    $('#tab-stream-btn,#tab-models-btn,#tab-advanced-json-btn').on('click', e=>{
      e.preventDefault();
      switchTab(e.target.id.replace('-btn',''));
    });
    function switchTab(name) {
      $('#tab-stream,#tab-models,#tab-advanced-json').hide();
      $(`#tab-${name}`).show();
      ['stream','models','advanced-json'].forEach(n=>{
        $(`#tab-${n}-btn`)
          .toggleClass('bg-white', n===name)
          .toggleClass('bg-gray-100', n!==name)
          .attr('aria-selected', n===name);
      });
    }
  
    // inputs → update JSON
    $('#quality,#fps').on('input',function(){
      $(`#${this.id}-val`).text(this.value);
      updateJson();
    });
    $('#stream-url,#width,#height,#use-cuda,#metrics-enabled,#model-name,#draw-boxes,#count-objects,#confidence,#iou,#count-line,#classes-filter-container input')
      .on('input change', updateJson);
  
    // camera list buttons
    $('#camera-list')
      .on('click','.btn-start', function(){ send({action:'start', source_id:$(this).data('src')}); })
      .on('click','.btn-stop',  function(){ send({action:'stop',  source_id:$(this).data('src')}); })
      .on('click','.btn-select',function(){
        selectedSource = $(this).data('src');
        renderCameraList( $('.btn-select').map((i,btn)=>({name:$(btn).data('src'),status:null,clients:0})).get() );
        // avvia o mostra stream
        send({action:'start', source_id: selectedSource});
      });
  
    // Apply config
    $('#apply-btn').click(()=>{
      send({action:'update_config', source_id: selectedSource, config: buildConfig()});
    });
  
    // header buttons
    $('button:contains("Refresh")').click(()=> send({action:'list_cameras'}));
    $('button:contains("Start All")').click(()=> $('.btn-start:enabled').click());
    $('button:contains("Stop All")').click(()=> $('.btn-stop:enabled').click());
  
    // -------- START --------
    connect();
    hideConfig();
  });
  