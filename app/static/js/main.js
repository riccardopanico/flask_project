(function (window, $) {
    'use strict';

    const AppState = {
        ui: { currentApp: 'scanner', currentSection: 'manual-control' },
        log: { filter: 'all' }
    };

    const Utils = {
        fetchJSON: (url, options = {}) => fetch(url, options).then(r => {
            if (!r.ok) throw new Error('Network error');
            return r.json();
        }),
        getTimestamp: () => new Date().toLocaleTimeString('it-IT')
    };

    // Formatta timestamp per i log
    const formatTimestamp = ts => {
        const d = new Date(ts);
        return (
            d.toLocaleDateString('it-IT', { year: 'numeric', month: '2-digit', day: '2-digit' }) +
            ' ' +
            d.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
        );
    };
    // Logga un messaggio nel container specificato
    function logMessage(containerId, message, type = 'info') {
        const timestamp = formatTimestamp(Date.now()), container = $(containerId);
        if (!container.length) return console.log(`[${timestamp}] ${message} (${containerId} missing)`);
        container.append(`<div class="log-entry log-${type}" data-type="${type}"><span class="text-gray-500">[${timestamp}]</span> ${message}</div>`);
        const el = container[0];
        if (el?.scrollHeight) container.scrollTop(el.scrollHeight);
        applyLogFilters(containerId);
        console.log(`[${timestamp}] ${message}`);
    }

    const logToConsole = (m, t = 'info') => logMessage('#console-log', m, t);

    function applyLogFilters(containerId){
        const container = $(containerId); if(!container.length) return;
        container.find('.log-entry').each(function(){
            const entry = $(this);
            const type = entry.data('type');
            entry.toggleClass('hidden', !(AppState.log.filter === 'all' || AppState.log.filter === type));
        });
    }

    function setupLogFilters(){
        const box = $(".log-filters"); if(!box.length) return;
        box.on("click", ".filter-btn", function(){
            const btn = $(this), f = btn.data("filter");
            if(f === 'clear'){
                $('#console-log').empty();
                btn.removeClass('active');
                return;
            }
            box.find('.filter-btn').removeClass('active');
            btn.addClass('active');
            AppState.log.filter = f;
            applyLogFilters('#console-log');
        });
        box.find(`.filter-btn[data-filter="${AppState.log.filter}"]`).addClass('active');
    }

    const showError = msg => logToConsole(`❌ ERRORE: ${msg}`, 'error');
    const showSuccess = msg => logToConsole(`✅ ${msg}`, 'success');

    const initGlobalEvents = () => setupLogFilters();

    $(document).ready(() => {
        initGlobalEvents();
        Object.assign(window, { AppState, AppUtils: Utils, logToConsole, showError, showSuccess, applyLogFilters });
    });

    window.addEventListener('error', e => showError(`Errore JavaScript: ${e.message}`));
    window.addEventListener('unhandledrejection', e => showError(`Errore asincrono: ${e.reason}`));

})(window, jQuery);
