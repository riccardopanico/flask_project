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

    // auto-refresh
    let refreshTimer = null;
    const intervals = [
      { label: '5s Refresh',  value: 5000  },
      { label: '10s Refresh', value: 10000 },
      { label: '30s Refresh', value: 30000 },
      { label: '1m Refresh',  value: 60000 }
    ];

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
      const sid = m.source_id;

      // Always update camera list
      if (m.action === 'list_cameras') {
        renderCameraList(m.data);
        return flushQueue();
      }

      // Ignore messages for other sources, except start/stop for UI badge
      if (sid && sid !== selectedSource) {
        if (m.action === 'start' || m.action === 'stop') {
          updateCameraUI(m.source_id, m.action === 'start' ? 'running' : 'stopped');
        }
        return flushQueue();
      }

      if (!m.success) {
        console.warn(`[WS] error on ${m.action}: ${m.error}`);
        if (m.action === 'stop') clearPanels();
        return flushQueue();
      }

      switch (m.action) {
        case 'start':
          updateCameraUI(sid, 'running');
          if (sid === selectedSource) {
            send({ action:'get_config',  source_id: sid });
            send({ action:'get_health',  source_id: sid });
            send({ action:'get_metrics', source_id: sid });
          }
          break;
        case 'stop':
          updateCameraUI(sid, 'stopped');
          break;
        case 'get_config':
          renderConfig(sid, m.data);
          break;
        case 'get_health':
          renderHealth(sid, m.data);
          break;
        case 'get_metrics':
          renderMetrics(sid, m.data);
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
      socket.onopen    = () => { retryInterval = RETRY_INIT; send({ action:'list_cameras' }); };
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
              <span class="${run ? 'bg-blue-500' : 'bg-red-500'} text-white text-[10px] font-semibold rounded-full px-2 py-[2px] flex items-center space-x-1">
                ${run && isSel ? '<span class="w-2 h-2 rounded-full bg-green-400 block"></span>' : ''}
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
        `<img class="w-full h-full object-contain" src="/api/ip_camera/stream/${sid}?_t=${Date.now()}">`
      );
      showConfig();
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
      let html = `<h4 class="font-semibold mb-2">Health (${src})</h4><ul class="text-sm space-y-1">`;
      html += `<li>• Running: ${data.running ? '✅' : '❌'}</li>`;
      html += `<li>• Received: ${data.frames_received} frames</li>`;
      html += `<li>• Processed: ${data.frames_processed} frames</li>`;
      html += `<li>• Avg Inference: ${data.avg_inf_ms.toFixed(2)} ms</li>`;
      html += `<li>• Clients: ${data.clients_active}</li>`;
      if (data.last_error) html += `<li class="text-red-500">• Last error: ${data.last_error}</li>`;
      html += `</ul>`;
      $('#health-panel').html(html);
    }

    function renderMetrics(src, data) {
      const fps = data.frames_received
        ? (data.frames_processed/data.frames_received*(data.avg_inf_ms?1000/data.avg_inf_ms:0)).toFixed(1)
        : '–';
      let html = `<h4 class="font-semibold mb-2">Metrics (${src})</h4>
        <div class="grid grid-cols-2 gap-2">
          <div><p class="text-xs">FPS</p><p class="font-semibold text-lg">${fps}</p></div>
          <div><p class="text-xs">Frames Served</p><p class="font-semibold text-lg">${data.frames_served}</p></div>
          <div><p class="text-xs">Data Transferred</p><p class="font-semibold text-lg">${(data.bytes_served/1024/1024).toFixed(2)} MB</p></div>
          <div><p class="text-xs">Avg Inference</p><p class="font-semibold text-lg">${data.avg_inf_ms.toFixed(2)} ms</p></div>
        </div>
        <p class="text-xs mt-2">Total Objects</p>
        <div class="border border-gray-300 rounded-md p-3 text-xs flex flex-wrap gap-2">` +
          Object.entries(data.counters||{}).map(([cls,c]) =>
            `<span class="bg-gray-100 rounded px-2 py-[2px] flex items-center space-x-1">
               <span>${cls}</span><span class="bg-gray-300 text-gray-700 rounded-full px-2 py-[1px] font-semibold">${c}</span>
             </span>`
          ).join('') +
        `</div>`;
      $('#metrics-panel article').html(html);
    }

    // -------- CONFIG Form & JSON --------
    function renderConfig(src, cfg) {
      if (src !== selectedSource) return;
      $('#stream-url').val(cfg.source);
      $('#width').val(cfg.width||'');
      $('#height').val(cfg.height||'');
      $('#fps').val(cfg.fps||30).trigger('input');
      $('#quality').val(cfg.quality).trigger('input');
      $('#use-cuda').prop('checked', cfg.use_cuda);
      $('#metrics-enabled').prop('checked', cfg.metrics_enabled);

      const [mname, mb] = Object.entries(cfg.model_behaviors)[0]||[];
      $('#model-name').val(mname||'');
      $('#draw-boxes').prop('checked', mb?.draw||false);
      $('#count-objects').prop('checked', mb?.count||false);
      $('#confidence').val(mb?.confidence||0).trigger('change');
      $('#iou').val(mb?.iou||0).trigger('change');
      $('#count-line').val(cfg.count_line||'');

      const cls = cfg.classes_filter||[];
      $('#classes-filter-container input').each((i,e) => {
        $(e).prop('checked', cls.includes(e.value));
      });

      updateJson();
      showConfig();
    }

    function buildConfig() {
      const pi=v=>{let n=parseInt(v,10);return isNaN(n)?null:n},
            pf=v=>{let f=parseFloat(v);return isNaN(f)?null:f};
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
        classes_filter: cls.length?cls:null
      };
    }

    function updateJson() {
      $('#advanced-json-textarea').val(JSON.stringify(buildConfig(), null, 2));
    }

    // -------- CONFIG UI Show/Hide & Tabs --------
    function showConfig() {
        switchTab('stream');
      }
      function hideConfig() {
        // non nascondiamo nulla più
      }
      

    // tabs
    $('#tab-stream-btn,#tab-models-btn,#tab-advanced-json-btn').on('click', e => {
      e.preventDefault();
      switchTab(e.target.id.replace('-btn',''));
    });
    function switchTab(name) {
        // Nascondi subito tutti i pannelli
        $('#tab-stream, #tab-models, #tab-advanced-json').addClass('hidden');
      
        // Dopo un piccolo delay, mostra quello giusto
        // setTimeout(() => {
          $(`#${name}`).removeClass('hidden');
        // }, 10);
      
        // Aggiorna lo stile visivo dei bottoni tab
        ['stream', 'models', 'advanced-json'].forEach(n => {
          $(`#tab-${n}-btn`)
            .toggleClass('bg-white', n === name)
            .toggleClass('bg-gray-100', n !== name)
            .attr('aria-selected', n === name);
        });
      }
      
    function updateCameraUI(sourceId, status) {
        const $article = $(`#camera-list [data-src="${sourceId}"]`).closest('article');
        const isRunning = status === 'running';
      
        // Badge
        const $badgeWrapper = $article.find('.flex.justify-between > span').last();
        $badgeWrapper
          .removeClass('bg-blue-500 bg-red-500')
          .addClass(isRunning ? 'bg-blue-500' : 'bg-red-500')
          .html(`
            ${isRunning ? '<span class="w-2 h-2 rounded-full bg-green-400 block"></span>' : ''}
            <span>${status}</span>
          `);
      
        // Bottoni
        $article.find('.btn-start')
          .prop('disabled', isRunning)
          .toggleClass('cursor-not-allowed text-gray-400', isRunning)
          .toggleClass('border-gray-200', isRunning)
          .toggleClass('border-gray-300', !isRunning);
      
        $article.find('.btn-stop')
          .prop('disabled', !isRunning)
          .toggleClass('cursor-not-allowed text-gray-400', !isRunning)
          .toggleClass('border-gray-300', isRunning)
          .toggleClass('border-gray-200', !isRunning);
      
        // Se selezionata, aggiorna contenuti
        if (sourceId === selectedSource) {
          if (isRunning) {
            clearStream();
            setTimeout(() => loadStream(sourceId), 100);
            send({ action: 'get_config',  source_id: selectedSource });
            send({ action: 'get_health',  source_id: selectedSource });
            send({ action: 'get_metrics', source_id: selectedSource });
          } else {
            clearStream();
            clearPanels();
          }
        }
      }
      
    // -------- CONFIG Feedback --------
    function showConfigResult(m) {
      if (m.success) {
        $('#apply-btn')
          .text('✓ Saved')
          .addClass('bg-green-500').removeClass('bg-blue-600');
        setTimeout(() => {
          $('#apply-btn')
            .text('Apply')
            .addClass('bg-blue-600').removeClass('bg-green-500');
        }, 1500);
      } else {
        alert('Errore nel salvataggio: ' + m.error);
      }
    }

    // -------- Inputs → update JSON --------
    $('#quality,#fps').on('input', function(){
      $(`#${this.id}-val`).text(this.value);
      updateJson();
    });
    $('#stream-url,#width,#height,#use-cuda,#metrics-enabled,#model-name,#draw-boxes,#count-objects,#confidence,#iou,#count-line,#classes-filter-container input')
      .on('input change', updateJson);

    // -------- Camera List Buttons --------
    $('#camera-list')
      .on('click','.btn-start',  function(){ send({ action:'start',  source_id: $(this).data('src') }); })
      .on('click','.btn-stop',   function(){ send({ action:'stop',   source_id: $(this).data('src') }); })
      .on('click','.btn-select', function(){
        selectedSource = $(this).data('src');
        send({ action:'list_cameras' });
        const $art = $(this).closest('article');
        const isRunning = $art.find('span').text().includes('running');
        if (isRunning) {
          loadStream(selectedSource);
          send({ action:'get_config',  source_id: selectedSource });
          send({ action:'get_health',  source_id: selectedSource });
          send({ action:'get_metrics', source_id: selectedSource });
        } else {
          clearStream();
          clearPanels();
        }
      });

    // Apply config
    $('#apply-btn').click(()=>{
      if (!selectedSource) return;
      send({ action:'update_config', source_id: selectedSource, config: buildConfig() });
    });

    // header buttons
    $('button:contains("Refresh")').click(() => send({ action:'list_cameras' }));
    $('button:contains("Start All")').click(() => $('.btn-start:enabled').click());
    $('button:contains("Stop All")').click(() => $('.btn-stop:enabled').click());

    // -------- Refresh Interval Setup --------
    const $refreshSelect = $('select[aria-label="Refresh interval"]');
    // popola opzioni
    $refreshSelect.empty();
    intervals.forEach(it => {
      $refreshSelect.append(`<option value="${it.value}">${it.label}</option>`);
    });
    // gestisce cambio intervallo
    $refreshSelect.on('change', scheduleRefresh);
    function scheduleRefresh() {
      if (refreshTimer) clearInterval(refreshTimer);
      const ms = parseInt($refreshSelect.val(), 10) || 5000;
      refreshTimer = setInterval(() => {
        if (selectedSource) {
          send({ action:'get_health',  source_id: selectedSource });
          send({ action:'get_metrics', source_id: selectedSource });
        }
      }, ms);
    }

    // -------- START --------
    connect();
    hideConfig();
    scheduleRefresh();  // avvia auto-refresh con default
});
