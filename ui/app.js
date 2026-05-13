const elements = {
    masterToggle: document.getElementById('master-toggle'),
    resetBtn: document.getElementById('reset-btn'),
    rearGain: document.getElementById('rear-gain'),
    rearDelay: document.getElementById('rear-delay'),
    centerGain: document.getElementById('center-gain'),
    lfeGain: document.getElementById('lfe-gain'),
    lfeDelay: document.getElementById('lfe-delay'),
    bassBoost: document.getElementById('bass-boost'),
    stereoWidth: document.getElementById('stereo-width'),
    lfePhase: document.getElementById('lfe-phase'),
    swapSubCenter: document.getElementById('swap-sub-center'),
    crossoverFreq: document.getElementById('crossover-freq'),
    rearVal: document.getElementById('rear-val'),
    delayVal: document.getElementById('delay-val'),
    centerVal: document.getElementById('center-val'),
    lfeVal: document.getElementById('lfe-val'),
    lfeDelayVal: document.getElementById('lfe-delay-val'),
    bassBoostVal: document.getElementById('bass-boost-val'),
    widthVal: document.getElementById('width-val'),
    phaseLabel: document.getElementById('phase-label'),
    swapLabel: document.getElementById('swap-label'),
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
    elements.lfeDelayVal.innerText = elements.lfeDelay.value + ' ms';
    elements.bassBoostVal.innerText = elements.bassBoost.value + ' dB';
    elements.widthVal.innerText = elements.stereoWidth.value + '%';
    elements.crossoverVal.innerText = elements.crossoverFreq.value + ' Hz';
    elements.phaseLabel.innerText = elements.lfePhase.checked ? 'Inverted' : 'Normal';
    elements.swapLabel.innerText = elements.swapSubCenter.checked ? 'Swapped' : 'Normal';
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
        lfe_delay: elements.lfeDelay.value / 1000,
        bass_boost: parseFloat(elements.bassBoost.value),
        stereo_width: elements.stereoWidth.value / 100,
        lfe_inverted: elements.lfePhase.checked,
        swap_sub_center: elements.swapSubCenter.checked,
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
elements.lfeDelay.oninput = handleSliderChange;
elements.bassBoost.oninput = handleSliderChange;
elements.stereoWidth.oninput = handleSliderChange;
elements.lfePhase.onchange = handleSliderChange;
elements.swapSubCenter.onchange = handleSliderChange;
elements.crossoverFreq.oninput = handleSliderChange;

// Reset to Defaults
elements.resetBtn.onclick = () => {
    if (confirm("Reset all settings to default?")) {
        const defaults = {
            rear_gain: 0.7,
            rear_delay: 0.015,
            center_gain: 0.8,
            lfe_gain: 1.0,
            lfe_delay: 0,
            bass_boost: 0,
            stereo_width: 1.0,
            lfe_inverted: false,
            swap_sub_center: false,
            crossover: 120
        };
        elements.rearGain.value = 70;
        elements.rearDelay.value = 15;
        elements.centerGain.value = 80;
        elements.lfeGain.value = 100;
        elements.lfeDelay.value = 0;
        elements.bassBoost.value = 0;
        elements.stereoWidth.value = 100;
        elements.lfePhase.checked = false;
        elements.swapSubCenter.checked = false;
        elements.crossoverFreq.value = 120;
        
        updateLabels();
        if (window.pywebview) {
            window.pywebview.api.update_params(defaults);
        }
    }
};

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
            if (settings.rear_gain !== undefined) elements.rearGain.value = settings.rear_gain * 100;
            if (settings.rear_delay !== undefined) elements.rearDelay.value = settings.rear_delay * 1000;
            if (settings.center_gain !== undefined) elements.centerGain.value = settings.center_gain * 100;
            if (settings.lfe_gain !== undefined) elements.lfeGain.value = settings.lfe_gain * 100;
            if (settings.lfe_delay !== undefined) elements.lfeDelay.value = settings.lfe_delay * 1000;
            if (settings.bass_boost !== undefined) elements.bassBoost.value = settings.bass_boost;
            if (settings.stereo_width !== undefined) elements.stereoWidth.value = settings.stereo_width * 100;
            if (settings.lfe_inverted !== undefined) elements.lfePhase.checked = settings.lfe_inverted;
            if (settings.swap_sub_center !== undefined) elements.swapSubCenter.checked = settings.swap_sub_center;
            if (settings.crossover !== undefined) elements.crossoverFreq.value = settings.crossover;
            if (settings.is_enabled !== undefined) elements.masterToggle.checked = settings.is_enabled;
            
            elements.statusLabel.innerText = elements.masterToggle.checked ? 'Active' : 'Inactive';
            elements.statusLabel.style.color = elements.masterToggle.checked ? 'var(--success)' : 'var(--text-dim)';
            
            updateLabels();
        });
    } else {
        setTimeout(init, 100);
    }
}

init();
setInterval(refreshApps, 2000);
updateLabels();
