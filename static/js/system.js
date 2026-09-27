/**
 * The connected-clients list on the settings page's System tab.
 *
 * The server renders the list, and this refreshes it while the tab is open —
 * so a teacher who opens the dashboard in one window and this page in another
 * watches the count change without reloading anything.
 *
 * Every value written here comes from the server, so every value is written as
 * text and never as markup. The rows are built as elements rather than as a
 * string of HTML: a route or a username can never become markup this page
 * executes.
 *
 * Polling runs only while the tab is visible. The registry drops a browser
 * that has been quiet for two minutes, so a hidden tab that kept polling would
 * be the one thing keeping itself on the list.
 */

const clientsCard = document.getElementById('clients-card');

if (clientsCard) {
    const clientsUrl = clientsCard.getAttribute('data-clients-url');
    const pollSeconds = parseInt(clientsCard.getAttribute('data-poll-seconds'), 10);
    // The unit is translated by the server and handed over, so this file needs
    // no translation catalogue of its own.
    const idleSuffix = clientsCard.getAttribute('data-idle-suffix') || '';
    const countElement = document.getElementById('clients-count');
    const rowsElement = document.getElementById('clients-rows');

    /**
     * One table cell holding text and nothing else.
     *
     * @param {string} text - The value to show.
     * @param {string} [className] - Classes for the cell.
     * @returns {HTMLTableCellElement} The cell.
     */
    function clientCell(text, className) {
        const cell = document.createElement('td');
        if (className) {
            cell.className = className;
        }
        cell.textContent = text;
        return cell;
    }

    /**
     * Replace the whole table body with what the server just reported.
     *
     * @param {Object} data - The JSON body from the clients endpoint.
     */
    function renderClients(data) {
        const clients = (data && data.clients) || [];
        if (countElement) {
            countElement.textContent = String(data && data.count ? data.count : clients.length);
        }
        if (!rowsElement) {
            return;
        }
        rowsElement.replaceChildren();

        if (clients.length === 0) {
            const row = document.createElement('tr');
            const cell = clientCell(rowsElement.getAttribute('data-empty-text') || '', 'text-base-content/60');
            cell.colSpan = 4;
            row.appendChild(cell);
            rowsElement.appendChild(row);
            return;
        }

        clients.forEach((client) => {
            const row = document.createElement('tr');
            row.appendChild(clientCell(client.ip || '', 'font-mono'));
            row.appendChild(clientCell(client.user || '—'));
            row.appendChild(clientCell(client.route || '—', 'font-mono'));
            row.appendChild(clientCell(`${client.idle_seconds} ${idleSuffix}`.trim()));
            rowsElement.appendChild(row);
        });
    }

    /** Ask the server who is connected, and leave the list alone if it fails. */
    async function refreshClients() {
        try {
            const response = await fetch(clientsUrl, {
                headers: { Accept: 'application/json' },
                credentials: 'same-origin',
            });
            if (!response.ok) {
                return;
            }
            renderClients(await response.json());
        } catch (error) {
            // A failed poll is not worth an error on screen: the list the
            // server rendered is still there, just older.
        }
    }

    if (pollSeconds > 0) {
        setInterval(() => {
            if (!document.hidden) {
                refreshClients();
            }
        }, pollSeconds * 1000);
    }

    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') {
            refreshClients();
        }
    });
}
