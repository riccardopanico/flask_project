$(function(){
    const { AppState, logToConsole, showError, showSuccess } = window;
    AppState.ui.currentApp = 'monitor';
    AppState.ui.currentSection = 'monitoring';

    const AppStateMonitoring = {
        cameras: [],
        selectedCamera: null,
        models: []
    };

    function loadCameraList(){
        // Placeholder: recupera la lista telecamere via WebSocket o AJAX
        // Qui simuliamo dati fittizi
        AppStateMonitoring.cameras = [
            {id: 'cam1', name: 'Camera 1'},
            {id: 'cam2', name: 'Camera 2'}
        ];
        const box = $('#camera-list');
        box.empty();
        AppStateMonitoring.cameras.forEach(c => {
            const btn = $(`<button class="w-full text-left px-2 py-1 border border-gray-300 camera-item" data-id="${c.id}">${c.name}</button>`);
            box.append(btn);
        });
        box.on('click', '.camera-item', function(){
            const id = $(this).data('id');
            AppStateMonitoring.selectedCamera = AppStateMonitoring.cameras.find(c => c.id === id);
            $('#video-container').html(`<img src="/api/ip_camera/stream/${id}" class="w-full h-full object-contain">`);
        });
    }

    function addModelRow(){
        const row = $(
            `<div class="model-row border p-2">
                <input type="text" class="model-path w-full border border-gray-300 px-2 py-1 mb-2" placeholder="Path modello">
                <div class="grid grid-cols-5 gap-1">
                    <input type="number" step="0.01" class="model-confidence border border-gray-300 px-1 py-1" placeholder="conf" value="0.5">
                    <input type="number" step="0.01" class="model-iou border border-gray-300 px-1 py-1" placeholder="iou" value="0.45">
                    <input type="number" class="model-min-area border border-gray-300 px-1 py-1" placeholder="min area">
                    <input type="number" class="model-max-area border border-gray-300 px-1 py-1" placeholder="max area">
                    <button class="remove-model bg-red-500 text-white">X</button>
                </div>
            </div>`
        );
        $('#models-container').append(row);
    }

    function collectConfig(){
        const cfg = {
            source: AppStateMonitoring.selectedCamera ? AppStateMonitoring.selectedCamera.id : '',
            width: parseInt($('#cfg-width').val()) || null,
            height: parseInt($('#cfg-height').val()) || null,
            fps: parseInt($('#cfg-fps').val()) || null,
            use_cuda: $('#cfg-cuda').is(':checked'),
            max_workers: parseInt($('#cfg-workers').val()) || 1,
            models: []
        };
        $('#models-container .model-row').each(function(){
            const row = $(this);
            const m = {
                path: row.find('.model-path').val(),
                confidence: parseFloat(row.find('.model-confidence').val()) || 0.5,
                iou: parseFloat(row.find('.model-iou').val()) || 0.45,
                min_area: parseFloat(row.find('.model-min-area').val()) || null,
                max_area: parseFloat(row.find('.model-max-area').val()) || null
            };
            cfg.models.push(m);
        });
        return cfg;
    }

    function sendConfiguration(){
        const json = collectConfig();
        logToConsole('PipelineSettings: ' + JSON.stringify(json));
        // Qui il JSON verrà inviato tramite WebSocket o AJAX
    }

    $('#models-container').on('click', '.remove-model', function(){
        $(this).closest('.model-row').remove();
    });

    $('#add-model').click(addModelRow);
    $('#send-config').click(sendConfiguration);

    loadCameraList();

    Object.assign(window, { AppStateMonitoring, loadCameraList, sendConfiguration });
});
