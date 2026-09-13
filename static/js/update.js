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
let currentUpdateId = null;

const elements = {
    idle: document.getElementById('state-idle'),
    checking: document.getElementById('state-checking'),
    updating: document.getElementById('state-updating'),
    reconnecting: document.getElementById('state-reconnecting'),
    completed: document.getElementById('state-completed'),
    failed: document.getElementById('state-failed'),

    btnCheck: document.getElementById('btn-check'),
    btnUpdate: document.getElementById('btn-update'),
    btnRetry: document.getElementById('btn-retry'),

    checkResult: document.getElementById('check-result'),
    checkResultBox: document.getElementById('check-result-box'),
    commitListWrap: document.getElementById('commit-list-wrap'),
    commitList: document.getElementById('commit-list'),
    stagesList: document.getElementById('stages-list'),
    progressCount: document.getElementById('progress-count'),
    updateLog: document.getElementById('update-log'),
    errorDetails: document.getElementById('error-details'),
    countdown: document.getElementById('countdown'),

    lastUpdateInfo: document.getElementById('last-update-info'),
    lastUpdateDate: document.getElementById('last-update-date'),
    lastUpdateWsWrap: document.getElementById('last-update-ws-wrap'),
    lastUpdateWs: document.getElementById('last-update-ws'),
};

function showState(state) {
    const states = ['idle', 'checking', 'updating', 'reconnecting', 'completed', 'failed'];
    states.forEach(s => {
        if (elements[s]) elements[s].classList.add('hidden');
    });

    if (elements[state]) elements[state].classList.remove('hidden');
}

// Show the result of "Check for Updates" inline. Enables "Update Now" only
// when an update is actually available (`type === 'available'`).
function showCheckResult(type, message) {
    const box = elements.checkResultBox;
    box.className = 'flex items-center gap-4 p-4 rounded-lg border';
    if (type === 'available') {
        box.classList.add('bg-info/10', 'border-info/20', 'text-info');
    } else if (type === 'error') {
        box.classList.add('bg-error/10', 'border-error/20', 'text-error');
    } else {
        box.classList.add('bg-success/10', 'border-success/20', 'text-success');
    }
    box.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
        <span class="font-semibold">${message}</span>`;
    elements.checkResult.classList.remove('hidden');
    if (type !== 'available') {
        elements.commitListWrap.classList.add('hidden');
    }
}

function setUpdateEnabled(enabled) {
    elements.btnUpdate.disabled = !enabled;
    elements.btnUpdate.classList.toggle('opacity-50', !enabled);
}

// True when the status belongs to the run we started (or carries no id).
// The status file keeps the PREVIOUS run's terminal state until the daemon
// overwrites it, so we must not treat a stale completed/failed as ours.
function isCurrentUpdate(data) {
    return currentUpdateId === null
        || data.update_id === undefined
        || String(data.update_id) === String(currentUpdateId);
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
        elements.updateLog.innerText = data.logs.map(l => `[${l.time}] ${l.message}`).join('\n');
        elements.updateLog.scrollTop = elements.updateLog.scrollHeight;
    }
}

async function checkUpdates() {
    showState('checking');
    try {
        const res = await fetch(`${API_BASE}/check/`);
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            showCheckResult('error', err.error || 'Server error');
            showState('idle');
            return;
        }
        const data = await res.json();

        if (data.available) {
            const n = data.commits.length;
            showCheckResult('available', `${n} update${n === 1 ? '' : 's'} available`);
            elements.commitList.innerHTML = data.commits.map(c => `<li>${c}</li>`).join('');
            elements.commitListWrap.classList.remove('hidden');
            setUpdateEnabled(true);
        } else {
            showCheckResult('ok', 'System is up to date!');
            setUpdateEnabled(false);
        }
        showState('idle');
    } catch (e) {
        showCheckResult('error', 'Error checking for updates');
        showState('idle');
    }
}

async function startUpdate() {
    if (!confirm('This will restart the service. Continue?')) return;

    try {
        const res = await fetch(`${API_BASE}/start/`, { method: 'POST' });
        const resJson = await res.json().catch(() => ({}));
        if (!res.ok) {
            alert(resJson.error);
            return;
        }

        if (socket) socket.close();
        currentUpdateId = resJson.update_id;
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
        // Ignore the previous run's leftover terminal state (race right after
        // starting a new update) and never react to a different run's result.
        if (!isCurrentUpdate(data)) return;

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

            if (!isCurrentUpdate(data)) return;

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
elements.btnUpdate.onclick = startUpdate;
elements.btnRetry.onclick = startUpdate;

function formatDate(iso) {
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    return d.toLocaleString(undefined, {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit'
    });
}

// Show "last update" on tab load: last commit date on the installed code,
// plus the last successful web update (if any). Non-fatal on failure.
(async function loadLastUpdateInfo() {
    try {
        const res = await fetch(`${API_BASE}/last-update/`);
        if (!res.ok) return;
        const data = await res.json();
        let visible = false;
        if (data.git_last_commit) {
            elements.lastUpdateDate.innerText = formatDate(data.git_last_commit);
            visible = true;
        }
        if (data.last_successful_update) {
            elements.lastUpdateWsWrap.classList.remove('hidden');
            elements.lastUpdateWs.innerText = formatDate(data.last_successful_update);
            visible = true;
        }
        if (visible) elements.lastUpdateInfo.classList.remove('hidden');
    } catch (e) { /* info display only, never block the tab */ }
})();
