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

    // -------- CUSTOM MODAL FUNCTIONS --------
    function showCustomConfirm(title, message, onConfirm, onCancel = null) {
      $('#modal-title').text(title);
      $('#modal-message').text(message);
      $('#confirm-modal').removeClass('hidden');
      
      // Remove existing event listeners
      $('#modal-confirm').off('click');
      $('#modal-cancel').off('click');
      
      // Add new event listeners
      $('#modal-confirm').on('click', function() {
        $('#confirm-modal').addClass('hidden');
        if (onConfirm) onConfirm();
      });
      
      $('#modal-cancel').on('click', function() {
        $('#confirm-modal').addClass('hidden');
        if (onCancel) onCancel();
      });
      
      // Close modal when clicking outside
      $('#confirm-modal').on('click', function(e) {
        if (e.target === this) {
          $('#confirm-modal').addClass('hidden');
          if (onCancel) onCancel();
        }
      });
    }

    // Carica la lista dei modelli disponibili da data/models e popola tutte le select
    let availableModels = [];
    function fetchModelListAndPopulateSelects() {
      $.get('/api/ip_camera/models/list', function(list) {
        availableModels = list;
        // Popola tutte le select già presenti
        $('#models-container .model-path').each(function() {
          const current = $(this).val();
          $(this).empty().append('<option value="">Seleziona modello...</option>');
          if (availableModels.length) {
            availableModels.forEach(m => $(this).append(`<option value="${m}">${m}</option>`));
          } else {
            $(this).append('<option value="">(Nessun modello trovato)</option>');
          }
          if (current) $(this).val(current);
        });
        // Forza popolamento hardcoded se la lista è vuota (debug)
        if (!availableModels.length) {
          $('#models-container .model-path').each(function() {
            $(this).append('<option value="data/models/yolo11n.pt">data/models/yolo11n.pt</option>');
            $(this).append('<option value="data/models/scarpe_25k_305ep.pt">data/models/scarpe_25k_305ep.pt</option>');
            $(this).append('<option value="data/models/shoes_25k_best_hyp.pt">data/models/shoes_25k_best_hyp.pt</option>');
          });
        }
      });
    }
    fetchModelListAndPopulateSelects();

    // -------- UTIL --------
    function send(msg) {
      queue.push(msg);
      flushQueue();
    }
    function flushQueue() {
      if (!waiting && socket && socket.readyState === WebSocket.OPEN && queue.length) {
        const messageToSend = queue.shift();
        socket.send(JSON.stringify(messageToSend));
        waiting = true;
      }
    }
    function debounce(fn, delay) {
      let timer;
      return function(...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
      };
    }
    const liveUpdateConfig = debounce(() => {
      if (!selectedSource) return;
      send({ action: 'update_config', source_id: selectedSource, config: buildConfig() });
    }, 500);

    function onMessage(raw) {
      waiting = false;
      const m = JSON.parse(raw);
      
      // Se è un array, è un messaggio batch di metriche
      if (Array.isArray(m)) {
        m.forEach(msg => {
          if (msg.action === 'get_metrics' && String(msg.source_id) === String(selectedSource)) {
            renderMetrics(msg.source_id, msg.data);
          }
          // Gestisci aggiornamenti contatori commessa in tempo reale
          if (msg.action === 'update_commessa_count' && String(msg.source_id) === String(selectedSource)) {
            updateCommessaCounter(msg.data);
          }
        });
        return flushQueue();
      }

      const sid = String(m.source_id);
      
      // Always update camera list (but don't force tab switching)
      if (m.action === 'list_cameras') {
        renderCameraList(m.data);
        return flushQueue();
      }

      // Ignore messages for other sources, except start/stop for UI badge
      if (sid && sid !== String(selectedSource)) {
        if (m.action === 'start' || m.action === 'stop') {
          updateCameraUI(m.source_id, m.action === 'start' ? 'running' : 'stopped');
        }
        return flushQueue();
      }

      if (!m.success) {
        console.warn(`[WS] error on ${m.action}: ${m.error}`);
        // Permetti a set_commessa di continuare allo switch anche in caso di errore
        if (m.action === 'set_commessa') {
          // Continue to switch for UI feedback
        } else {
          if (m.action === 'stop') clearPanels();
          return flushQueue();
        }
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
          // Se abbiamo dati di commessa salvati, usiamo la config per costruire la visualizzazione commessa
          if (window.currentCommessaData) {
            buildCommessaDisplayByYoloModels(m.data, window.currentCommessaData);
            window.currentCommessaData = null; // Pulisci dopo l'uso
          } else {
            // Controlla se c'è una commessa attiva e dobbiamo ricaricare la sua visualizzazione
            const currentCommessa = $('#commessa-codice').text();
            if (currentCommessa && currentCommessa !== '-' && !$('#commessa-attiva').hasClass('hidden')) {
              // C'è una commessa attiva, richiedi i suoi dati per ricostruire la visualizzazione
              send({ 
                action: 'set_commessa', 
                source_id: String(selectedSource), 
                data: { commessa: currentCommessa }
              });
            } else {
              // Altrimenti è una richiesta normale di configurazione
              renderConfig(sid, m.data);
            }
          }
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
        case 'set_commessa':
          // Riabilita il pulsante
          $('#commessa-submit').prop('disabled', false).text('Invia');
          
          if (m.success) {
            showCommessaStatus('Commessa impostata con successo', true);
            // Opzionalmente, svuota il campo
            $('#commessa-input').val('');
            
            // Mostra i dati della commessa attiva
            if (m.data) {
              showCommessaAttiva(m.data);
            }
          } else {
            const errorMessage = m.error || 'Errore durante l\'impostazione della commessa';
            showCommessaStatus(errorMessage, false);
          }
          break;
        case 'reset_counters':
          if (m.success) {
            const resetCount = m.data ? m.data.reset_count : 0;
            showCommessaStatus(`Contatori azzerati con successo (${resetCount} resettati)`, true);
          } else {
            showCommessaStatus(m.error || 'Errore durante il reset dei contatori', false);
          }
          break;
        case 'reset_commessa':
          if (m.success) {
            // Reset completo e immediato della GUI
            hideCommessaAttiva();
            
            // Reset aggiuntivo di emergenza per assicurarsi che tutto sia pulito
            setTimeout(() => {
              const $commessaPanel = $('#commessa-attiva');
              $commessaPanel.removeClass();
              $commessaPanel.addClass('hidden bg-gradient-to-r from-blue-50 to-blue-100 border-2 border-blue-300 rounded-lg p-4 shadow-md');
              $commessaPanel.find('*').removeClass('bg-purple-50 bg-purple-100 border-purple-300 border-purple-400 text-purple-600 text-purple-800 progress-over-target over-target completed');
            }, 100);
            
            showCommessaStatus('Commessa resettata con successo', true);
          } else {
            showCommessaStatus(m.error || 'Errore durante il reset della commessa', false);
          }
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
        .append(`<h2 class="font-semibold text-base mb-2 select-none">Camera List</h2>`);
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
              <span class="font-semibold text-base">Camera: ${cam.description}</span>
              <span class="${run ? 'bg-blue-500' : 'bg-red-500'} text-white text-xs font-semibold rounded-full px-2 py-[2px] flex items-center space-x-1">
                ${run && isSel ? '<span class="w-2 h-2 rounded-full bg-green-400 block"></span>' : ''}
                <span>${cam.status}</span>
              </span>
            </div>
            <p class="text-sm text-gray-400">${cam.clients} active client${cam.clients!==1?'s':''}</p>
            <div class="flex space-x-2 text-sm font-semibold">
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
      console.log('loadStream called with sid:', sid);
      const streamUrl = `/api/ip_camera/stream/${String(sid)}?_t=${Date.now()}`;
      console.log('Stream URL:', streamUrl);
      
      $('#camera-stream .flex-grow').html(
        `<img class="w-full h-full object-contain" src="${streamUrl}" onerror="console.error('Image failed to load:', this.src)">`
      );
      showConfig();
    }
    function clearStream() {
      $('#camera-stream .flex-grow').html('Nessuna camera selezionata');
    }
    function clearPanels() {
      $('#metrics-panel article[aria-label="Camera Metrics"]').html('<div class="text-center text-gray-400 italic">Nessuna metrica disponibile</div>');
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
      let html = `
        <div class="flex justify-between items-center text-sm select-none">
          <h2 class="font-semibold text-lg">Metrics</h2>
          <select aria-label="Refresh interval"
            class="border border-gray-300 rounded text-sm px-2 py-1">
            <option>5s Refresh</option>
          </select>
        </div>
        <div class="grid grid-cols-2 gap-2">
          <div><p class="text-sm">FPS</p><p class="font-semibold text-lg">${fps}</p></div>
          <div><p class="text-sm">Frames Served</p><p class="font-semibold text-lg">${data.frames_served}</p></div>
          <div><p class="text-sm">Data Transferred</p><p class="font-semibold text-lg">${(data.bytes_served/1024/1024).toFixed(2)} MB</p></div>
          <div><p class="text-sm">Avg Inference</p><p class="font-semibold text-lg">${data.avg_inf_ms.toFixed(2)} ms</p></div>
        </div>
        <p class="text-sm mt-2">Total Objects</p>
        <div class="border border-gray-300 rounded-md p-3 text-sm flex flex-wrap gap-2">` +
          Object.entries(data.counters||{}).map(([cls,c]) =>
            `<span class="bg-gray-100 rounded px-2 py-[2px] flex items-center space-x-1">
               <span>${cls}</span><span class="bg-gray-300 text-gray-700 rounded-full px-2 py-[1px] font-semibold">${c}</span>
             </span>`
          ).join('') +
        `</div>`;
      // Aggiorna solo l'articolo specifico delle metriche, non tutto il pannello
      $('#metrics-panel article[aria-label="Camera Metrics"]').html(html);
    }

    // -------- CONFIG Form & JSON --------
    function renderConfig(src, cfg) {
      if (String(src) !== String(selectedSource)) {
        return;
      }
      
      // Campi base
      $('#stream-url').val(cfg.source);
      $('#width').val(cfg.width);
      $('#height').val(cfg.height);
      $('#fps').val(cfg.fps);
      $('#quality').val(cfg.quality);
      $('#use-cuda').prop('checked', cfg.use_cuda);
      $('#metrics-enabled').prop('checked', cfg.metrics_enabled);
      
      // Gestione classes_filter globale
      if (cfg.classes_filter) {
        $('#classes-filter-container input').each(function() {
          $(this).prop('checked', cfg.classes_filter.includes(parseInt(this.value)));
        });
      }
      
      // Pulisci container modelli
      $('#models-container').empty();
      
      // Aggiungi blocchi per ogni modello
      (cfg.models||[]).forEach(m => {
        const $item = $($('#model-item-template').html()).addClass('model-item');
        // Popola la select dei modelli
        const $select = $item.find('.model-path');
        $select.empty().append('<option value="">Seleziona modello...</option>');
        availableModels.forEach(opt => $select.append(`<option value="${opt}">${opt}</option>`));
        if (m.path) $select.val(m.path);
        $item.find('.draw-boxes').prop('checked', m.draw);
        $item.find('.confidence').val(m.confidence).trigger('change');
        $item.find('.iou').val(m.iou).trigger('change');
        // Gestisci counting
        if (m.counting) {
          $item.find('.count-objects').prop('checked', true);
          if (m.counting.region) {
            const [[x1, y1], [x2, y2]] = m.counting.region;
            $item.find('.count-line').val(`${x1},${y1},${x2},${y2}`);
            $item.find('.count-x1').val(x1);
            $item.find('.count-y1').val(y1);
            $item.find('.count-x2').val(x2);
            $item.find('.count-y2').val(y2);
          }
        }
        // Gestisci classes_filter per modello
        if (m.classes_filter) {
          $item.find('.classes-filter').val(m.classes_filter.join(','));
        } else {
          $item.find('.classes-filter').val('');
        }
        $('#models-container').append($item);
        setupModelItem($item);
      });
      
      updateJson();
    }

    function buildConfig() {
      const pi = v => { let n = parseInt(v,10); return isNaN(n)?null:n };
      const pf = v => { let f = parseFloat((v||'').replace(',','.')); return isNaN(f)?null:f };
      
      // Config base
      const cfg = {
        source: $('#stream-url').val(),
        width: pi($('#width').val()),
        height: pi($('#height').val()),
        fps: pi($('#fps').val()),
        prefetch: 10,
        skip_on_full_queue: true,
        quality: pi($('#quality').val()),
        use_cuda: $('#use-cuda').prop('checked'),
        max_workers: 1,
        metrics_enabled: $('#metrics-enabled').prop('checked'),
        models: []
      };

      // Gestione classes_filter globale
      const classes = $('#classes-filter-container input:checked').map((i,e) => parseInt(e.value)).get();
      if (classes.length) {
        cfg.classes_filter = classes;
      }

      // Popola array models SOLO se la select ha un valore
      $('#models-container .model-item').each((i, el) => {
        const $m = $(el);
        const path = $m.find('.model-path').val();
        if (!path) return; // ignora modelli non selezionati
        const model = {
          path: path,
          draw: $m.find('.draw-boxes').prop('checked'),
          confidence: pf($m.find('.confidence').val()),
          iou: pf($m.find('.iou').val())
        };
        // Serializza le classi solo se non vuote
        let classes = $m.find('.classes-filter').val().split(',').map(s => s.trim()).filter(Boolean);
        if (classes && classes.length) {
          model.classes_filter = classes;
        }
        if ($m.find('.count-objects').prop('checked')) {
          const countLine = $m.find('.count-line').val();
          const arr = (countLine||'').split(',').map(Number);
          if (arr.length === 4 && arr.every(n => !isNaN(n))) {
            model.counting = {
              region: [[arr[0], arr[1]], [arr[2], arr[3]]],
              show_in: true,
              show_out: true,
              tracking: {
                show: false,
                show_labels: true,
                show_conf: true,
                verbose: false
              }
            };
          }
        }
        cfg.models.push(model);
      });
      return cfg;
    }

    function updateJson() {
      $('#advanced-json-textarea').val(JSON.stringify(buildConfig(), null, 2));
    }

    // Miglioria UX: disabilita count-objects se la count line del modello non è valida
    function updateCountObjectsAvailability() {
      $('#models-container .model-item').each((i, el) => {
        const $m = $(el);
        const arr = ($m.find('.count-line').val()||'').split(',').map(Number);
        const valid = arr.length === 4 && arr.every(n => !isNaN(n));
        $m.find('.count-objects').prop('disabled', !valid);
        if (!valid) $m.find('.count-objects').prop('checked', false);
      });
    }
    $('#models-container').on('input change', '.count-line', updateCountObjectsAvailability);

    // Sincronizza slider e campo count-line per ogni modello
    $('#models-container').on('input change', '.count-x1, .count-y1, .count-x2, .count-y2', function() {
      const $m = $(this).closest('.model-item');
      const x1 = $m.find('.count-x1').val();
      const y1 = $m.find('.count-y1').val();
      const x2 = $m.find('.count-x2').val();
      const y2 = $m.find('.count-y2').val();
      $m.find('.count-line').val(`${x1},${y1},${x2},${y2}`).trigger('input');
    });
    $('#models-container').on('input change', '.count-line', function() {
      const $m = $(this).closest('.model-item');
      const vals = $(this).val().split(',');
      if (vals.length === 4) {
        $m.find('.count-x1').val(vals[0]);
        $m.find('.count-y1').val(vals[1]);
        $m.find('.count-x2').val(vals[2]);
        $m.find('.count-y2').val(vals[3]);
      }
    });

    // Sincronizzazione tra select multi-tag e campo testo per classes_filter
    $('#models-container').on('change', '.classes-filter', function() {
      const $m = $(this).closest('.model-item');
      const val = $(this).val();
      $m.find('.classes-filter-text').val(val ? val.join(',') : '');
    });
    $('#models-container').on('input', '.classes-filter-text', function() {
      const $m = $(this).closest('.model-item');
      const arr = $(this).val().split(',').map(s => s.trim()).filter(Boolean);
      $m.find('.classes-filter').val(arr).trigger('change');
    });

    // -------- LIVE CONFIG UPDATES --------
    $('#stream-url,#width,#height,#fps,#quality,#use-cuda,#metrics-enabled,#classes-filter-container input').on('input change', () => { 
      updateJson(); 
      liveUpdateConfig(); 
    });
    $('#models-container').on('input change', '.count-line,.count-objects,.model-path,.draw-boxes,.confidence,.iou', function() {
      updateJson();
      liveUpdateConfig();
      updateCountObjectsAvailability();
    });

    // -------- CONFIG UI Show/Hide & Tabs --------
    function showConfig() {
        // Don't force tab switching - let user keep their current tab selection
        // Only switch to Stream tab if no tab is currently visible
        const $visibleTab = $('#tab-stream, #tab-models, #tab-advanced-json').not('.hidden');
        if ($visibleTab.length === 0) {
          switchTab('stream');
        }
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
        const $article = $(`#camera-list [data-src="${String(sourceId)}"]`).closest('article');
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
      
        // Se selezionata, aggiorna contenuti (but don't force tab switching)
        if (String(sourceId) === String(selectedSource)) {
          if (isRunning) {
            clearStream();
            setTimeout(() => loadStream(sourceId), 100);
            send({ action: 'get_config',  source_id: String(sourceId) });
            send({ action: 'get_health',  source_id: String(sourceId) });
            send({ action: 'get_metrics', source_id: String(sourceId) });
          } else {
            clearStream();
            clearPanels();
          }
        }
      }
      
    // -------- CONFIG Feedback --------
    function reloadStream() {
      if (selectedSource) {
        $('#camera-stream img').attr('src', `/api/ip_camera/stream/${selectedSource}?_t=${Date.now()}`);
      }
    }

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
        reloadStream(); // reload stream dopo salvataggio config
        
        // Se c'è una commessa attiva, ricarica la visualizzazione conteggi
        const currentCommessa = $('#commessa-codice').text();
        if (currentCommessa && currentCommessa !== '-') {
          // Richiedi la configurazione aggiornata per ricostruire la visualizzazione
          send({ action: 'get_config', source_id: String(selectedSource) });
        }
      } else {
        alert('Errore nel salvataggio: ' + m.error);
      }
    }

    // -------- Inputs → update JSON --------
    $('#quality,#fps').on('input', function(){
      $(`#${this.id}-val`).text(this.value);
      updateJson();
    });

    $('#model-name,#draw-boxes,#count-objects,#confidence,#iou,#count-line,#classes-filter-container input').on('input change', () => { updateJson(); liveUpdateConfig(); });
    

    // -------- Camera List Buttons --------
    $('#camera-list')
      .on('click','.btn-start',  function(){ send({ action:'start',  source_id: String($(this).data('src')) }); })
      .on('click','.btn-stop',   function(){ send({ action:'stop',   source_id: String($(this).data('src')) }); })
      .on('click','.btn-select', function(){
        selectedSource = String($(this).data('src'));
        $('#camera-name').text('Camera: ' + selectedSource);
        fetchModelListAndPopulateSelects();
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
        // Only switch to Stream tab if no tab is currently visible
        const $visibleTab = $('#tab-stream, #tab-models, #tab-advanced-json').not('.hidden');
        if ($visibleTab.length === 0) {
          switchTab('stream');
        }
        
        // Aggiorna stato dei bottoni
        updateButtonStates();
      });

    // Gestione pulsanti Add/Remove
    $('#add-model-btn').on('click', () => {
      // Controlla se c'è una camera selezionata
      if (!selectedSource) {
        console.warn('Nessuna camera selezionata');
        return;
      }
      
      const $item = $($('#model-item-template').html()).addClass('model-item');
      $('#models-container').append($item);
      setupModelItem($item);
      updateCountObjectsAvailability();
      updateJson();
      fetchModelListAndPopulateSelects(); // Popola la select dopo aggiunta
    });

    function setupModelItem($item) {
      // Gestione visibilità count line
      $item.find('.count-objects').on('change', function() {
        $item.find('.count-line-container').toggleClass('hidden', !this.checked);
      });

      // Gestione visibilità classes filter
      $item.find('.draw-boxes').on('change', function() {
        $item.find('.classes-filter-container').toggleClass('hidden', !this.checked);
      });

      // Inizializza visibilità
      $item.find('.count-line-container').toggleClass('hidden', !$item.find('.count-objects').prop('checked'));
      $item.find('.classes-filter-container').toggleClass('hidden', !$item.find('.draw-boxes').prop('checked'));
    }

    $('#models-container').on('click', '.remove-model', function() {
      $(this).closest('.model-item').remove();
      updateJson();
      updateCountObjectsAvailability();
    });

    // Gestione JSON avanzato
    $('#advanced-json-textarea').on('input', function() {
      try {
        const json = JSON.parse(this.value);
        // Valida la struttura base
        if (!json.source || !Array.isArray(json.models)) {
          throw new Error('JSON non valido');
        }
        // Aggiorna la configurazione
        renderConfig(selectedSource, json);
      } catch (e) {
        console.warn('JSON non valido:', e);
      }
    });

    // Apply config
    $('#apply-btn').click(() => {
      // Doppio controllo di sicurezza
      if (!selectedSource) {
        console.warn('Nessuna camera selezionata');
        return;
      }
      
      const config = buildConfig();
      send({ action: 'update_config', source_id: String(selectedSource), config: config });
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

    // Aggiorna setupModelItem per i modelli esistenti
    $('#models-container .model-item').each((i, el) => setupModelItem($(el)));

    // Quando selezioni dalla tendina, aggiorna il valore path
    $('#models-container').on('change', '.model-path', function() {
      // Se serve, puoi gestire altro qui
      updateJson();
    });

    // Carica le classi disponibili per un modello
    function loadAvailableClassesForModel($modelItem, modelPath, selected) {
      if (!modelPath) return;
      $.get('/api/ip_camera/model_classes?path=' + encodeURIComponent(modelPath), function(classes) {
        const $select = $modelItem.find('.classes-filter');
        $select.empty();
        classes.forEach(cls => {
          $select.append(`<option value="${cls}">${cls}</option>`);
        });
        if (selected && selected.length) {
          $select.val(selected);
        }
      });
    }

    // Quando selezioni un modello, carica le classi
    $('#models-container').on('change', '.model-path', function() {
      const $m = $(this).closest('.model-item');
      const path = $(this).val();
      loadAvailableClassesForModel($m, path, $m.find('.classes-filter').val());
    });

    // -------- COMMESSA MANAGEMENT --------
    function showCommessaStatus(message, isSuccess = true) {
      const $status = $('#commessa-status');
      
      // Rimuovi tutte le classi di colore e sfondo precedenti
      $status.removeClass('hidden text-green-600 text-red-600 bg-green-50 bg-red-50 border-green-200 border-red-200');
      
      if (isSuccess) {
        $status.addClass('text-green-600 bg-green-50 border-green-200');
      } else {
        $status.addClass('text-red-600 bg-red-50 border-red-200');
      }
      
      $status.text(message);
      
      // Auto-hide dopo 5 secondi
      setTimeout(() => {
        $status.addClass('hidden');
      }, 5000);
    }

    function showCommessaAttiva(data) {
      // Reset del pannello 
      const $commessaPanel = $('#commessa-attiva');
      $commessaPanel.removeClass(); 
      $commessaPanel.addClass('bg-gradient-to-r from-blue-50 to-blue-100 border-2 border-blue-300 rounded-lg p-4 shadow-md');
      
      // Popola i dati della commessa
      $('#commessa-codice').text(data.commessa || '-');
      $('#commessa-descrizione').text(data.descrizione || '-');
      
      // DEBUG: Log per verificare i dati ricevuti
      console.log('showCommessaAttiva - data received:', data);
      console.log('showCommessaAttiva - modelli:', data.modelli);
      
      // Pulisci il container dei modelli
      const $container = $('#modelli-container');
      $container.empty();
      $container.removeClass('grid-cols-1 grid-cols-2 lg:grid-cols-2 md:grid-cols-2 lg:grid-cols-3');
      
      // Ottieni la configurazione dei modelli YOLO attivi per raggruppare per modello
      getActiveYoloModelsForCommessa(data);
      
      // Mostra il pannello commessa attiva e nascondi l'input
      $('#commessa-attiva').removeClass('hidden');
      $('#commessa-input-section').addClass('hidden');
    }

    function getActiveYoloModelsForCommessa(commessaData) {
      if (!selectedSource) return;
      
      // Richiedi la configurazione attuale per ottenere i modelli YOLO configurati
      const message = { 
        action: 'get_config', 
        source_id: String(selectedSource)
      };
      
      // Salva i dati della commessa per usarli quando arriva la configurazione
      window.currentCommessaData = commessaData;
      send(message);
      
      // Timeout di fallback se non arriva risposta in 5 secondi
      setTimeout(() => {
        if (window.currentCommessaData) {
          console.warn('Timeout nella richiesta get_config, mostro visualizzazione fallback');
          // showCommessaFallbackDisplay(window.currentCommessaData);
          window.currentCommessaData = null;
        }
      }, 5000);
    }

    function showCommessaFallbackDisplay(commessaData) {
      const $container = $('#modelli-container');
      
      // Visualizzazione di fallback senza raggruppamento per modello YOLO
      if (commessaData.modelli && Object.keys(commessaData.modelli).length > 0) {
        let listHtml = '<div class="space-y-4">';
        listHtml += '<div class="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mb-4">';
        listHtml += '<div class="flex items-center space-x-2">';
        listHtml += '<i class="fas fa-exclamation-triangle text-yellow-600"></i>';
        listHtml += '<span class="text-sm text-yellow-800">Impossibile caricare la configurazione YOLO. Visualizzazione semplificata:</span>';
        listHtml += '</div></div>';
        
        Object.entries(commessaData.modelli).forEach(([modelKey, modelData]) => {
          if (modelData && modelData.nome_articolo) {
            const displayName = modelKey; // Usa il modelKey così com'è, senza modifiche
            const prodotti = modelData.prodotti || 0;
            const totale = modelData.totale_da_produrre || 0;
            
            listHtml += `
              <div class="class-counter bg-white border border-gray-200 rounded-lg p-3 shadow-sm" data-class="${modelKey}">
                <div class="flex justify-between items-center">
                  <div class="flex items-center space-x-3">
                    <div class="w-3 h-3 bg-blue-500 rounded-full"></div>
                    <span class="text-lg font-semibold text-gray-800">${displayName}</span>
                  </div>
                  <div class="flex items-center space-x-2">
                    <span class="counter-value text-2xl font-bold text-blue-600">${prodotti}</span>
                    <span class="text-gray-400 text-lg">/</span>
                    <span class="total-value text-2xl font-bold text-gray-700">${totale}</span>
                  </div>
                </div>
                <div class="mt-2 text-sm text-gray-600">
                  <i class="fas fa-tag mr-1"></i>
                  ${modelData.nome_articolo}
                </div>
              </div>
            `;
          }
        });
        
        listHtml += '</div>';
        $container.html(listHtml);
      } else {
        $container.html('<div class="text-gray-400 italic text-center py-8 text-lg">Nessun modello configurato</div>');
      }
    }

    function buildCommessaDisplayByYoloModels(yoloConfig, commessaData) {
      const $container = $('#modelli-container');
      
      if (!yoloConfig.models || yoloConfig.models.length === 0) {
        $container.html('<div class="text-gray-400 italic text-center py-8 text-lg">Nessun modello YOLO configurato</div>');
        return;
      }
      
      let listHtml = '';
      
      // Per ogni modello YOLO configurato - crea una sezione diretta (senza wrapper)
      yoloConfig.models.forEach((yoloModel, index) => {
        if (!yoloModel.path) return;
        
        // Estrai il nome del modello dal path
        const modelFileName = yoloModel.path.split('/').pop().replace('.pt', '');
        const modelDisplayName = modelFileName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        
        listHtml += `
          <div class="yolo-model-section bg-white rounded-lg border-2 border-gray-300 p-4 shadow-inner mb-4" data-yolo-model="${yoloModel.path}">
            <h4 class="font-black text-gray-800 text-lg mb-3 text-center uppercase tracking-wide">
              <i class="fas fa-chart-bar mr-2 text-blue-600"></i>
              ${modelDisplayName}
            </h4>
            
            <!-- CLASSI RILEVATE DA QUESTO MODELLO -->
            <div class="space-y-3" data-yolo-classes="${yoloModel.path}">
              <div class="text-gray-500 italic">Caricamento classi...</div>
            </div>
          </div>
        `;
      });
      
      $container.html(listHtml);
      
      // Carica le classi per ogni modello YOLO e mappale ai prodotti della commessa
      yoloConfig.models.forEach((yoloModel, index) => {
        if (yoloModel.path) {
          loadYoloModelClassesAndMapToCommessa(yoloModel.path, commessaData);
        }
      });
    }

    function loadYoloModelClassesAndMapToCommessa(modelPath, commessaData) {
      const $classesContainer = $(`[data-yolo-classes="${modelPath}"]`);
      
      // Ora mostriamo le classi definite nella commessa, non quelle del modello YOLO
      if (!commessaData.modelli || Object.keys(commessaData.modelli).length === 0) {
        $classesContainer.html('<div class="text-gray-400 italic">Nessuna classe definita nella commessa</div>');
        return;
      }
      
      let classesHtml = '';
      
      // Per ogni classe definita nella commessa (model_1, model_2, person, etc.)
      Object.entries(commessaData.modelli).forEach(([modelKey, modelData]) => {
        if (modelData && modelData.nome_articolo) {
          // Usa il modelKey così com'è, senza modifiche
          const displayName = modelKey;
          const prodotti = modelData.prodotti || 0;
          const totale = modelData.totale_da_produrre || 0;
          const isCompleted = prodotti >= totale;
          
          classesHtml += `
            <div class="class-counter ${isCompleted ? 'completed' : ''} bg-white border-l-4 ${isCompleted ? 'border-green-500 bg-green-50' : 'border-blue-500 bg-blue-50'} rounded-lg p-4 shadow-sm mb-3" data-class="${modelKey}">
              <div class="flex justify-between items-center">
                <div class="flex-1">
                  <div class="font-bold text-lg text-gray-800 mb-1">${displayName}</div>
                  <div class="text-sm text-gray-600">${modelData.nome_articolo}</div>
                </div>
                <div class="text-right">
                  <div class="counter-value text-5xl font-bold ${isCompleted ? 'text-green-600' : 'text-blue-600'}">${prodotti}/${totale}</div>
                </div>
              </div>
            </div>
          `;
        }
      });
      
      if (classesHtml === '') {
        classesHtml = '<div class="text-gray-400 italic">Nessun prodotto configurato nella commessa</div>';
      }
      
      $classesContainer.html(classesHtml);
    }

    function hideCommessaAttiva() {
      // Nascondi il pannello commessa attiva e mostra l'input
      $('#commessa-attiva').addClass('hidden');
      $('#commessa-input-section').removeClass('hidden');
      
      // Reset completo dei valori e degli stili
      $('#commessa-codice, #commessa-descrizione').text('-');
      
      // Pulisci il container dei modelli
      const $container = $('#modelli-container');
      $container.empty();
      $container.removeClass('grid-cols-1 grid-cols-2 lg:grid-cols-2 md:grid-cols-2 lg:grid-cols-3');
      
      // Reset del pannello commessa attiva
      const $commessaPanel = $('#commessa-attiva');
      $commessaPanel.removeClass(); 
      $commessaPanel.addClass('hidden bg-gradient-to-r from-blue-50 to-blue-100 border-2 border-blue-300 rounded-lg p-4 shadow-md');
    }

    function resetCommessa() {
      if (!selectedSource) {
        showCommessaStatus('Selezionare prima una camera', false);
        return;
      }
      
      // Conferma azione prima del reset
      // if (confirm('Vuoi resettare la commessa attiva? Questo cancellerà la commessa e tutti i contatori associati.')) {
        // Invia richiesta di reset al server
        send({ 
          action: 'reset_commessa', 
          source_id: String(selectedSource)
        });
        
        showCommessaStatus('Reset della commessa in corso...', true);
      // }
    }

    function updateCommessaCounter(data) {
      if (!data || !data.model_key) {
        return;
      }
      
      // Verifica che sia la commessa corrente
      const currentCommessa = $('#commessa-codice').text();
      if (currentCommessa !== String(data.commessa)) {
        return;
      }
      
      // Trova l'elemento della classe corrispondente nella nuova struttura class-counter
      const $classCounter = $(`#modelli-container .class-counter[data-class="${data.model_key}"]`);
      
      if ($classCounter.length > 0) {
        // Aggiorna il valore del contatore nella struttura class-counter
        const $counterValue = $classCounter.find('.counter-value');
        if ($counterValue.length > 0) {
          // Ottieni il totale dalla struttura esistente
          const currentText = $counterValue.text(); // es. "5/50"
          const total = currentText.split('/')[1] || '0';
          
          // Aggiorna con il nuovo contatore
          $counterValue.text(`${data.new_count}/${total}`);
          
          // Gestisce il completamento - aggiorna sia il colore del testo che dello sfondo
          const newCount = parseInt(data.new_count) || 0;
          const totalCount = parseInt(total) || 0;
          
          if (newCount >= totalCount && totalCount > 0) {
            $classCounter.removeClass('border-blue-500 bg-blue-50').addClass('border-green-500 bg-green-50 completed');
            $counterValue.removeClass('text-blue-600').addClass('text-green-600');
          } else {
            $classCounter.removeClass('border-green-500 bg-green-50 completed').addClass('border-blue-500 bg-blue-50');
            $counterValue.removeClass('text-green-600').addClass('text-blue-600');
          }
          
          // Animazione semplice per evidenziare l'aggiornamento
          $counterValue.addClass('animate-pulse');
          setTimeout(() => {
            $counterValue.removeClass('animate-pulse');
          }, 1000);
        }
      }
    }

    $('#commessa-submit').on('click', function() {
      const commessaValue = $('#commessa-input').val().trim();
      
      if (!commessaValue) {
        showCommessaStatus('Inserire un codice di commessa valido', false);
        return;
      }
      
      if (!selectedSource) {
        showCommessaStatus('Selezionare prima una camera', false);
        return;
      }
      
      // Disabilita il pulsante durante l'invio
      $(this).prop('disabled', true).text('Invio...');
      
      const message = { 
        action: 'set_commessa', 
        source_id: String(selectedSource), 
        data: { commessa: commessaValue }
      };
      
      // Timeout di sicurezza per riabilitare il pulsante dopo 10 secondi
      setTimeout(() => {
        if ($('#commessa-submit').prop('disabled')) {
          $('#commessa-submit').prop('disabled', false).text('Invia');
          showCommessaStatus('Timeout: nessuna risposta dal server, riprova', false);
        }
      }, 10000);
      
      // Invia tramite websocket
      send(message);
    });

    // Supporto per invio con tasto Enter
    $('#commessa-input').on('keypress', function(e) {
      if (e.which === 13) { // Enter key
        $('#commessa-submit').click();
      }
    });

    // Gestione reset commessa
    $('#reset-commessa').on('click', resetCommessa);

    // Gestione reset contatori (DEBUG)
    $('#reset-counters').on('click', function() {
      if (!selectedSource) {
        showCommessaStatus('Selezionare prima una camera', false);
        return;
      }
      
      // Mostra il modal personalizzato invece del brutto confirm
      showCustomConfirm(
        'Reset Contatori (DEBUG)',
        'Vuoi azzerare tutti i contatori della commessa attiva?',
        function() {
          // Confermato - Invia richiesta di reset contatori al server
          send({ 
            action: 'reset_counters', 
            source_id: String(selectedSource)
          });
          
          showCommessaStatus('Contatori in fase di reset...', true);
        }
      );
    });

    // -------- BUTTON STATE MANAGEMENT --------
    function updateButtonStates() {
      const hasCameraSelected = selectedSource !== null && selectedSource !== undefined && selectedSource !== '';
      
      // Aggiorna stato bottone Add Model
      $('#add-model-btn').prop('disabled', !hasCameraSelected);
      
      // Aggiorna stato bottone Apply
      $('#apply-btn').prop('disabled', !hasCameraSelected);
    }

    // -------- START --------
    connect();
    scheduleRefresh();  // start auto-refresh
    updateButtonStates();  // Inizializza stato bottoni
    // Initialize with Stream tab visible by default, but don't force it later
    if ($('#tab-stream, #tab-models, #tab-advanced-json').not('.hidden').length === 0) {
      switchTab('stream');
    }
});
