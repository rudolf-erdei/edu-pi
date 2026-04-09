const API_BASE = '/updates';
const WS_BASE = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/updates/`;

const STAGES = [
    { id: 'check_git', label: 'Check git repository' },
    { id: 'stop_service', label: 'Stop service' },
    { id: 'pull', label: 'Pull latest changes' },
    { id: 'dependencies', label: 'Update dependencies' },
    { id: 'migrations', label: 'Run migrations' },
    { id: 'static', label: 'Collect static files' },
    { id: 'translations', label: 'Compile translations' },
    { id: 'wifi_connect', label: 'Update wifi-connect files' },
    { id: 'restart_service', label: 'Restart service' },
];

let socket = null;
let pollingInterval = null;

const elements = {
    idle: document.getElementById('state-idle'),
    checking: document.getElementById('state-checking'),
    available: document.getElementById('state-available'),
    updating: document.getElementById('state-updating'),
    reconnecting: document.getElementById('state-reconnecting'),
    completed: document.getElementById('state-completed'),
    failed: document.getElementById('state-failed'),

    btnCheck: document.getElementById('btn-check'),
    btnUpdate: document.getElementById('btn-update'),
    btnUpdateConfirm: document.getElementById('btn-update-confirm'),
    btnRetry: document.getElementById('btn-retry'),

    commitList: document.getElementById('commit-list'),
    updateInfo: document.getElementById('update-info-text'),
    stagesList: document.getElementById('stages-list'),
    progressCount: document.getElementById('progress-count'),
    updateLog: document.getElementById('update-log'),
    errorDetails: document.getElementById('error-details'),
    countdown: document.getElementById('countdown'),
};

function showState(state) {
    Object.values(elements).forEach(el => {
        if (el && el.id && el.classList && el.classList.contains('hidden')) {
            // ignore logic
        }
    });

    const states = ['idle', 'checking', 'available', 'updating', 'reconnecting', 'completed', 'failed'];
    states.forEach(s => {
        if (elements[s]) elements[s].classList.add('hidden');
    });

    if (elements[state]) elements[state].classList.remove('hidden');
}

function initStages() {
    elements.stagesList.innerHTML = STAGES.map(s => `
        <div id="stage-${s.id}" class="flex items-center gap-3 text-sm opacity-50">
            <span class="stage-icon">○</span>
            <span class="stage-label">${s.label}</span>
        </div>
    `).join('');
}

function updateProgressUI(data) {
    const stage = data.stage;
    const completed = data.stages_completed || [];

    // Update checkboxes
    STAGES.forEach(s => {
        const el = document.getElementById(`stage-${s.id}`);
        if (!el) return;

        if (completed.includes(s.id)) {
            el.classList.remove('opacity-50');
            el.classList.add('text-success');
            el.querySelector('.stage-icon').innerText = '✓';
        } else if (stage === s.id) {
            el.classList.remove('opacity-50');
            el.classList.add('text-primary');
            el.querySelector('.stage-icon').innerText = '●';
        }
    });

    elements.progressCount.innerText = `${completed.length}/${STAGES.length}`;

    // Append logs
    if (data.logs && data.logs.length > 0) {
        const lastLog = data.logs[data.logs.length - 1];
        elements.updateLog.innerText = data.logs.map(l => `[${l.time}] ${l.message}`).join('\\n');
        elements.updateLog.scrollTop = elements.updateLog.scrollHeight;
    }
}

async function checkUpdates() {
    showState('checking');
    try {
        const res = await fetch(`${API_BASE}/check/`);
        const data = await res.json();

        if (data.available) {
            showState('available');
            elements.updateInfo.innerText = `Update available (${data.commits.length} commits ahead)`;
            elements.commitList.innerHTML = data.commits.map(c => `<li>${c}</li>`).join('');
            elements.btnUpdate.disabled = false;
            elements.btnUpdate.classList.remove('opacity-50');
        } else {
            alert('System is up to date!');
            showState('idle');
        }
    } catch (e) {
        alert('Error checking for updates');
        showState('idle');
    }
}

async function startUpdate() {
    if (!confirm('This will restart the service. Continue?')) return;

    try {
        const res = await fetch(`${API_BASE}/start/`, { method: 'POST' });
        if (!res.ok) {
            const err = await res.json();
            alert(err.error);
            return;
        }

        showState('updating');
        initStages();
        connectWebSocket();
    } catch (e) {
        alert('Error starting update');
        showState('idle');
    }
}

function connectWebSocket() {
    socket = new WebSocket(WS_BASE);

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateProgressUI(data);

        if (data.status === 'completed') {
            completeUpdate();
        } else if (data.status === 'failed') {
            failUpdate(data.error);
        }
    };

    socket.onclose = () => {
        showState('reconnecting');
        startPolling();
    };

    socket.onerror = () => {
        showState('reconnecting');
        startPolling();
    };
}

function startPolling() {
    if (pollingInterval) return;

    pollingInterval = setInterval(async () => {
        try {
            const res = await fetch(`${API_BASE}/status/`);
            const data = await res.json();

            if (data.status === 'completed') {
                stopPolling();
                completeUpdate();
            } else if (data.status === 'failed') {
                stopPolling();
                failUpdate(data.error);
            } else if (data.status === 'in_progress') {
                showState('updating');
                updateProgressUI(data);
                // If service is back, try to reconnect WS
                connectWebSocket();
                stopPolling();
            }
        } catch (e) {
            // Server still down, keep polling
        }
    }, 2000);
}

function stopPolling() {
    clearInterval(pollingInterval);
    pollingInterval = null;
}

function completeUpdate() {
    stopPolling();
    if (socket) socket.close();
    showState('completed');

    let seconds = 10;
    const timer = setInterval(() => {
        seconds--;
        elements.countdown.innerText = seconds;
        if (seconds <= 0) {
            clearInterval(timer);
            location.reload();
        }
    }, 1000);
}

function failUpdate(error) {
    stopPolling();
    if (socket) socket.close();
    showState('failed');
    elements.errorDetails.innerText = error || 'Unknown error occurred during update.';
}

elements.btnCheck.onclick = checkUpdates;
elements.btnUpdateConfirm.onclick = startUpdate;
elements.btnRetry.onclick = startUpdate;
