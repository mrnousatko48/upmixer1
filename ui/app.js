const elements = {
    masterToggle: document.getElementById('master-toggle'),
    rearGain: document.getElementById('rear-gain'),
    rearDelay: document.getElementById('rear-delay'),
    centerGain: document.getElementById('center-gain'),
    lfeGain: document.getElementById('lfe-gain'),
    lfePhase: document.getElementById('lfe-phase'),
    crossoverFreq: document.getElementById('crossover-freq'),
    rearVal: document.getElementById('rear-val'),
    delayVal: document.getElementById('delay-val'),
    centerVal: document.getElementById('center-val'),
    lfeVal: document.getElementById('lfe-val'),
    phaseLabel: document.getElementById('phase-label'),
    crossoverVal: document.getElementById('crossover-val'),
    statusLabel: document.getElementById('status-label'),
    appList: document.getElementById('app-list')
};

// Update UI labels
function updateLabels() {
    elements.rearVal.innerText = elements.rearGain.value + '%';
    elements.delayVal.innerText = elements.rearDelay.value + ' ms';
    elements.centerVal.innerText = elements.centerGain.value + '%';
    elements.lfeVal.innerText = elements.lfeGain.value + '%';
    elements.crossoverVal.innerText = elements.crossoverFreq.value + ' Hz';
    elements.phaseLabel.innerText = elements.lfePhase.checked ? 'Inverted' : 'Normal';
}

// Master Toggle
elements.masterToggle.addEventListener('change', (e) => {
    const active = e.target.checked;
    elements.statusLabel.innerText = active ? 'Active' : 'Inactive';
    elements.statusLabel.style.color = active ? 'var(--success)' : 'var(--text-dim)';
    
    if (window.pywebview) {
        window.pywebview.api.toggle_upmixer(active, getCurrentParams());
    }
});

function getCurrentParams() {
    return {
        rear_gain: elements.rearGain.value / 100,
        rear_delay: elements.rearDelay.value / 1000,
        center_gain: elements.centerGain.value / 100,
        lfe_gain: elements.lfeGain.value / 100,
        lfe_inverted: elements.lfePhase.checked,
        crossover: elements.crossoverFreq.value
    };
}

// Slider Events
let updateTimeout;
function handleSliderChange() {
    updateLabels();
    clearTimeout(updateTimeout);
    updateTimeout = setTimeout(() => {
        if (window.pywebview) {
            window.pywebview.api.update_params(getCurrentParams());
        }
    }, 200);
}

elements.rearGain.oninput = handleSliderChange;
elements.rearDelay.oninput = handleSliderChange;
elements.centerGain.oninput = handleSliderChange;
elements.lfeGain.oninput = handleSliderChange;
elements.lfePhase.onchange = handleSliderChange;
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

// Initialization
function init() {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.get_settings().then(settings => {
            elements.rearGain.value = settings.rear_gain * 100;
            elements.rearDelay.value = (settings.rear_delay || 0.015) * 1000;
            elements.centerGain.value = settings.center_gain * 100;
            elements.lfeGain.value = settings.lfe_gain * 100;
            elements.lfePhase.checked = settings.lfe_inverted || false;
            elements.crossoverFreq.value = settings.crossover;
            elements.masterToggle.checked = settings.is_enabled;
            
            elements.statusLabel.innerText = settings.is_enabled ? 'Active' : 'Inactive';
            elements.statusLabel.style.color = settings.is_enabled ? 'var(--success)' : 'var(--text-dim)';
            
            updateLabels();
        });
    } else {
        setTimeout(init, 100);
    }
}

init();
setInterval(refreshApps, 2000);
updateLabels();
