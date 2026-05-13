const elements = {
    masterToggle: document.getElementById('master-toggle'),
    rearGain: document.getElementById('rear-gain'),
    centerGain: document.getElementById('center-gain'),
    lfeGain: document.getElementById('lfe-gain'),
    crossoverFreq: document.getElementById('crossover-freq'),
    rearVal: document.getElementById('rear-val'),
    centerVal: document.getElementById('center-val'),
    lfeVal: document.getElementById('lfe-val'),
    crossoverVal: document.getElementById('crossover-val'),
    statusLabel: document.getElementById('status-label'),
    appList: document.getElementById('app-list')
};

// Update UI labels
function updateLabels() {
    elements.rearVal.innerText = elements.rearGain.value + '%';
    elements.centerVal.innerText = elements.centerGain.value + '%';
    elements.lfeVal.innerText = elements.lfeGain.value + '%';
    elements.crossoverVal.innerText = elements.crossoverFreq.value + ' Hz';
}

// Master Toggle
elements.masterToggle.addEventListener('change', (e) => {
    const active = e.target.checked;
    elements.statusLabel.innerText = active ? 'Active' : 'Inactive';
    elements.statusLabel.style.color = active ? 'var(--success)' : 'var(--text-dim)';
    
    if (window.pywebview) {
        window.pywebview.api.toggle_upmixer(active, {
            rear_gain: elements.rearGain.value / 100,
            center_gain: elements.centerGain.value / 100,
            lfe_gain: elements.lfeGain.value / 100,
            crossover: elements.crossoverFreq.value
        });
    }
});

// Slider Events (Debounced for the crossover/reload params)
let updateTimeout;
function handleSliderChange() {
    updateLabels();
    clearTimeout(updateTimeout);
    updateTimeout = setTimeout(() => {
        if (window.pywebview) {
            window.pywebview.api.update_params({
                rear_gain: elements.rearGain.value / 100,
                center_gain: elements.centerGain.value / 100,
                lfe_gain: elements.lfeGain.value / 100,
                crossover: elements.crossoverFreq.value
            });
        }
    }, 200);
}

elements.rearGain.oninput = handleSliderChange;
elements.centerGain.oninput = handleSliderChange;
elements.lfeGain.oninput = handleSliderChange;
elements.crossoverFreq.oninput = handleSliderChange;

// Polling for active apps
function refreshApps() {
    if (window.pywebview) {
        window.pywebview.api.get_active_apps().then(apps => {
            if (apps.length === 0) {
                elements.appList.innerHTML = '<li class="empty-msg">No active upmixed streams</li>';
            } else {
                elements.appList.innerHTML = apps.map(app => `<li><span>${app.name}</span> <small>${app.channels}ch</small></li>`).join('');
            }
        });
    }
}

setInterval(refreshApps, 2000);
updateLabels();
