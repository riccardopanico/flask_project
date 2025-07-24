$(function(){
    const { AppState, logToConsole, showError } = window;
    AppState.ui.currentApp = 'monitor';
    AppState.ui.currentSection = 'tab-general';

    const PipelineSettings = {
        source: '0',
        width: 640,
        height: 480,
        fps: 30,
        prefetch: 10,
        skip_on_full_queue: true,
        quality: 95,
        use_cuda: true,
        max_workers: 1,
        metrics_enabled: true,
        log_level: 'INFO',
        enable_counting: true,
        show_window: false,
        tracker: 'botsort.yaml',
        models: [
            {
                path: 'data/models/yolo11n.pt',
                draw: true,
                confidence: 0.4,
                iou: 0.45,
                classes_filter: null,
                min_area: 15000,
                max_area: null,
                counting: {
                    region: [[320,0],[320,480]],
                    show_in: false,
                    show_out: false,
                    show: false,
                    id_timeout: 5.0,
                    min_frames_before_count: 3,
                    tracking: {
                        show: false,
                        show_labels: true,
                        show_conf: true,
                        verbose: false
                    }
                }
            }
        ]
    };

    const CommessaInfo = {
        code: 'CM-001',
        description: 'Linea Sneaker Demo',
        models: [
            {name:'Sneaker A', previsto:100, contato:40},
            {name:'Sneaker B', previsto:80, contato:65}
        ],
        classes: ['shoe','box','label']
    };

const State = {
        cameras: [
            {id:'cam1', name:'Camera 1'},
            {id:'cam2', name:'Camera 2'}
        ],
        selectedCamera: null
    };

    let modelCounter = 0;

    function logChange(field, value){
        logToConsole(`Aggiornato ${field}: ${value}`,'info');
    }

    function populateCommessa(){
        const box = $('#commessa-info').empty();
        box.append(`<div class="font-semibold">${CommessaInfo.code} - ${CommessaInfo.description}</div>`);
        const models = $('<div class="space-y-1"></div>');
        CommessaInfo.models.forEach(m=>{
            const perc = Math.min(100, Math.round((m.contato/m.previsto)*100));
            models.append(
                `<div>
                    <div class="flex justify-between text-sm"><span>${m.name}</span><span>${m.contato}/${m.previsto}</span></div>
                    <div class="w-full bg-gray-200 h-2"><div class="bg-blue-600 h-2" style="width:${perc}%"></div></div>
                </div>`
            );
        });
        box.append(`<h4 class="font-medium mt-2">Modelli</h4>`);
        box.append(models);
        box.append(`<h4 class="font-medium mt-2">Classi Rilevate</h4>`);
        box.append(`<div class="flex flex-wrap gap-1">${CommessaInfo.classes.map(c=>`<span class="px-2 py-0.5 bg-gray-100 border text-xs">${c}</span>`).join('')}</div>`);
    }

    function populateCameras(){
        const box = $('#camera-list').empty();
        State.cameras.forEach(c=>{
            const btn = $(`<button class="w-full text-left px-2 py-1 border border-gray-300 camera-item" data-id="${c.id}">${c.name}</button>`);
            box.append(btn);
        });
    }

    $('#camera-list').on('click','.camera-item',function(){
        const id = $(this).data('id');
        State.selectedCamera = State.cameras.find(c=>c.id===id);
        $('#video-container').html(`<div class="text-gray-500">Stream ${State.selectedCamera.name}</div>`);
        PipelineSettings.source = id;
        logChange('camera', id);
    });

    function addModelRow(model){
        const m = model || {path:'',draw:false,confidence:0.5,iou:0.45,min_area:null,max_area:null,counting:null};
        const idx = modelCounter++;
        m._idx = idx;
        const row = $(
            `<div class="model-row border p-2 space-y-1" data-index="${idx}">
                <div class="flex items-center gap-2">
                    <input type="text" list="available-models" class="model-path flex-1 border border-gray-300 px-2 py-1" value="${m.path}">
                    <label class="flex items-center text-sm space-x-2"><span class="toggle"><input type="checkbox" class="model-draw" ${m.draw?'checked':''}><span class="slider"></span></span><span>Draw</span></label>
                </div>
                <div class="grid grid-cols-2 gap-2 items-center">
                    <label class="text-xs flex-1">Conf <input type="range" min="0" max="1" step="0.01" class="model-confidence w-full" value="${m.confidence}"></label>
                    <label class="text-xs flex-1">IoU <input type="range" min="0" max="1" step="0.01" class="model-iou w-full" value="${m.iou}"></label>
                </div>
                <div class="grid grid-cols-2 gap-2">
                    <input type="number" class="model-min-area border border-gray-300 px-1 py-1" placeholder="Min Area" value="${m.min_area||''}">
                    <input type="number" class="model-max-area border border-gray-300 px-1 py-1" placeholder="Max Area" value="${m.max_area||''}">
                </div>
                <button class="remove-model bg-red-500 text-white px-2 w-full">Rimuovi</button>
            </div>`
        );
        row.find('.model-path').on('input change',function(){
            $(`#counting-${idx} .count-model-path`).text($(this).val());
        });
        $('#models-container').append(row);
        addCountingSection(m, idx);
    }

    function updateRegionDisplay(idx){
        const x1=parseInt($(`#region-x1-${idx}`).val());
        const y1=parseInt($(`#region-y1-${idx}`).val());
        const x2=parseInt($(`#region-x2-${idx}`).val());
        const y2=parseInt($(`#region-y2-${idx}`).val());
        $(`#count-region-${idx}`).val(`[[${x1},${y1}],[${x2},${y2}]]`);
        const c=document.getElementById(`region-preview-${idx}`);
        const ctx=c.getContext('2d');
        ctx.clearRect(0,0,c.width,c.height);
        ctx.beginPath();
        ctx.moveTo(x1,y1);
        ctx.lineTo(x2,y2);
        ctx.strokeStyle='red';
        ctx.stroke();
    }

    function addCountingSection(model, idx){
        const c = model.counting || {region:[[320,0],[320,480]],show:false,show_in:false,show_out:false,id_timeout:5.0,min_frames_before_count:3,tracking:{show:false,show_labels:true,show_conf:true,verbose:false}};
        const section = $(
            `<div id="counting-${idx}" class="model-counting border p-2 space-y-2" data-index="${idx}">
                <h3 class="font-semibold text-sm">Modello <span class="count-model-path">${model.path||''}</span></h3>
                <div class="grid md:grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm mb-1">Regione di conteggio</label>
                        <canvas id="region-preview-${idx}" class="border border-gray-300 bg-gray-50 w-full" width="640" height="480"></canvas>
                        <div class="grid grid-cols-4 gap-1 mt-2 text-xs">
                            <input id="region-x1-${idx}" type="range" min="0" max="640">
                            <input id="region-y1-${idx}" type="range" min="0" max="480">
                            <input id="region-x2-${idx}" type="range" min="0" max="640">
                            <input id="region-y2-${idx}" type="range" min="0" max="480">
                        </div>
                        <input id="count-region-${idx}" type="text" class="w-full border border-gray-300 px-2 py-1 mt-2" readonly>
                    </div>
                    <div class="space-y-2">
                        <label class="flex items-center space-x-2"><span class="toggle"><input id="count-enable-${idx}" type="checkbox"><span class="slider"></span></span><span class="text-sm">Abilita Conteggio</span></label>
                        <label class="flex items-center space-x-2"><span class="toggle"><input id="count-tracking-${idx}" type="checkbox"><span class="slider"></span></span><span class="text-sm">Tracking</span></label>
                        <label class="flex items-center space-x-2"><span class="toggle"><input id="count-showin-${idx}" type="checkbox"><span class="slider"></span></span><span class="text-sm">Show IN</span></label>
                        <label class="flex items-center space-x-2"><span class="toggle"><input id="count-showout-${idx}" type="checkbox"><span class="slider"></span></span><span class="text-sm">Show OUT</span></label>
                        <label class="flex items-center space-x-2"><span class="toggle"><input id="count-showlabels-${idx}" type="checkbox" checked><span class="slider"></span></span><span class="text-sm">Show Labels</span></label>
                        <label class="flex items-center space-x-2"><span class="toggle"><input id="count-showconf-${idx}" type="checkbox" checked><span class="slider"></span></span><span class="text-sm">Show Conf</span></label>
                        <label class="flex items-center space-x-2"><span class="toggle"><input id="count-verbose-${idx}" type="checkbox"><span class="slider"></span></span><span class="text-sm">Verbose</span></label>
                        <div>
                            <label class="block text-sm">ID Timeout</label>
                            <input id="count-timeout-${idx}" type="number" step="0.1" class="w-full border border-gray-300 px-2 py-1">
                        </div>
                        <div>
                            <label class="block text-sm">Frame Minimi</label>
                            <input id="count-minframes-${idx}" type="number" class="w-full border border-gray-300 px-2 py-1">
                        </div>
                    </div>
                </div>
            </div>`
        );
        $('#counting-container').append(section);
        $(`#region-x1-${idx}`).val(c.region[0][0]);
        $(`#region-y1-${idx}`).val(c.region[0][1]);
        $(`#region-x2-${idx}`).val(c.region[1][0]);
        $(`#region-y2-${idx}`).val(c.region[1][1]);
        $(`#count-enable-${idx}`).prop('checked',c.show);
        $(`#count-tracking-${idx}`).prop('checked',c.tracking.show);
        $(`#count-showlabels-${idx}`).prop('checked',c.tracking.show_labels);
        $(`#count-showconf-${idx}`).prop('checked',c.tracking.show_conf);
        $(`#count-verbose-${idx}`).prop('checked',c.tracking.verbose);
        $(`#count-showin-${idx}`).prop('checked',c.show_in);
        $(`#count-showout-${idx}`).prop('checked',c.show_out);
        $(`#count-timeout-${idx}`).val(c.id_timeout);
        $(`#count-minframes-${idx}`).val(c.min_frames_before_count);
        updateRegionDisplay(idx);
        $(`#region-x1-${idx},#region-y1-${idx},#region-x2-${idx},#region-y2-${idx}`).on('input change',()=>updateRegionDisplay(idx));
    }

    $('#models-container').on('click','.remove-model',function(){
        const idx = $(this).closest('.model-row').data('index');
        $(`#counting-${idx}`).remove();
        $(this).closest('.model-row').remove();
    });

    $('#add-model').click(()=>addModelRow());

    function readConfig(){
        PipelineSettings.width = parseInt($('#cfg-width').val())||null;
        PipelineSettings.height = parseInt($('#cfg-height').val())||null;
        PipelineSettings.fps = parseInt($('#cfg-fps').val())||null;
        PipelineSettings.use_cuda = $('#cfg-cuda').is(':checked');
        PipelineSettings.max_workers = parseInt($('#cfg-workers').val())||1;
        PipelineSettings.prefetch = parseInt($('#adv-prefetch').val())||10;
        PipelineSettings.quality = parseInt($('#adv-quality').val())||80;
        PipelineSettings.skip_on_full_queue = $('#adv-skipqueue').is(':checked');
        PipelineSettings.log_level = $('#adv-loglevel').val();
        PipelineSettings.enable_counting = $('#count-global-enable').is(':checked');
        const models=[];
        $('#models-container .model-row').each(function(){
            const idx=$(this).data('index');
            const base=PipelineSettings.models.find(m=>m._idx===idx)||{};
            const m={
                _idx: idx,
                path:$(this).find('.model-path').val(),
                draw:$(this).find('.model-draw').is(':checked'),
                confidence:parseFloat($(this).find('.model-confidence').val())||0.5,
                iou:parseFloat($(this).find('.model-iou').val())||0.45,
                min_area:parseFloat($(this).find('.model-min-area').val())||null,
                max_area:parseFloat($(this).find('.model-max-area').val())||null,
                classes_filter:base.classes_filter||null,
                counting:{}
            };
            const sec=$(`#counting-${idx}`);
            m.counting={
                region:[
                    [parseInt($(`#region-x1-${idx}`).val()),parseInt($(`#region-y1-${idx}`).val())],
                    [parseInt($(`#region-x2-${idx}`).val()),parseInt($(`#region-y2-${idx}`).val())]
                ],
                show_in:$(`#count-showin-${idx}`).is(':checked'),
                show_out:$(`#count-showout-${idx}`).is(':checked'),
                show:$(`#count-enable-${idx}`).is(':checked'),
                id_timeout:parseFloat($(`#count-timeout-${idx}`).val())||5.0,
                min_frames_before_count:parseInt($(`#count-minframes-${idx}`).val())||3,
                tracking:{
                    show:$(`#count-tracking-${idx}`).is(':checked'),
                    show_labels:$(`#count-showlabels-${idx}`).is(':checked'),
                    show_conf:$(`#count-showconf-${idx}`).is(':checked'),
                    verbose:$(`#count-verbose-${idx}`).is(':checked')
                }
            };
            models.push(m);
        });
        PipelineSettings.models=models;
    }

    $('#config-panel').on('change','input,select',function(){
        readConfig();
        const fld=$(this).data('field')||$(this).attr('id');
        const val=$(this).is(':checkbox')?$(this).is(':checked'):$(this).val();
        logChange(fld,val);
    });

    function switchTab(id){
        $('.section-content').addClass('hidden');
        $('#'+id).removeClass('hidden');
        $('.tab-btn').removeClass('active-tab');
        $(`.tab-btn[data-target="${id}"]`).addClass('active-tab');
        AppState.ui.currentSection = id;
        logToConsole(`Cambio tab: ${id}`);
    }

    $('.tab-btn').click(function(){
        const target=$(this).data('target');
        if(target) switchTab(target);
    });

    $('#send-config').click(function(){
        readConfig();
        logToConsole('PipelineSettings: '+JSON.stringify(PipelineSettings));
    });

    function init(){
        populateCameras();
        populateCommessa();
        PipelineSettings.models.forEach(m=>addModelRow(m));
        $('#cfg-width').val(PipelineSettings.width);
        $('#cfg-height').val(PipelineSettings.height);
        $('#cfg-fps').val(PipelineSettings.fps);
        $('#cfg-cuda').prop('checked',PipelineSettings.use_cuda);
        $('#cfg-workers').val(PipelineSettings.max_workers);
        $('#adv-prefetch').val(PipelineSettings.prefetch);
        $('#adv-quality').val(PipelineSettings.quality);
        $('#adv-skipqueue').prop('checked',PipelineSettings.skip_on_full_queue);
        $('#adv-loglevel').val(PipelineSettings.log_level);
        $('#count-global-enable').prop('checked',PipelineSettings.enable_counting);
        logToConsole('Configurazione iniziale caricata');
    }

    init();

    Object.assign(window,{PipelineSettings,CommessaInfo});
});
