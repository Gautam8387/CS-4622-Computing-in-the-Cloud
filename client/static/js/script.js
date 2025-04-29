// ./client/static/js/app.js

// --- Wait for the DOM to be fully loaded ---
document.addEventListener('DOMContentLoaded', function() {

    console.log("DOM fully loaded. Initializing periodic history refresh.");

    // --- Configuration (from Flask Template) ---
    // Access config passed from Flask template using optional chaining for safety
    const API_GATEWAY_URL = window.APP_CONFIG?.api_gateway_url;
    const IS_LOGGED_IN = window.APP_CONFIG?.is_logged_in;
    const CLIENT_TOKEN_ENDPOINT = '/get-token'; // Client backend endpoint to get JWT
    const REFRESH_INTERVAL_MS = 30000; // 30 seconds

    // --- DOM Elements ---
    const jobHistoryList = document.getElementById('job-history-list');
    const jobHistorySection = document.getElementById('job-history-section'); // Check if section exists

    // --- State ---
    let historyIntervalId = null; // ID for the setInterval timer

    // --- Helper Functions ---

    /**
     * Fetches the JWT from the client's backend Flask session securely.
     * @returns {Promise<string|null>} JWT token or null if failed/not logged in.
     */
    async function getJwtToken() {
        try {
            const response = await fetch(CLIENT_TOKEN_ENDPOINT);
            if (response.status === 401) {
                console.warn('User not authenticated (session expired or invalid). Refresh interval will stop.');
                stopHistoryRefresh(); // Stop refreshing if not authenticated
                return null;
            }
            if (!response.ok) {
                console.error(`Error fetching token: ${response.statusText}`);
                return null;
            }
            const data = await response.json();
            if (!data.access_token) {
                 console.error('Token endpoint response did not contain access_token.');
                 return null;
            }
            return data.access_token;
        } catch (error) {
            console.error('Network or other error fetching token:', error);
            return null;
        }
    }

    /**
     * Formats an integer timestamp (seconds since epoch) into a locale-aware string.
     * @param {number|string|null} timestamp - The Unix timestamp.
     * @returns {string} Formatted date/time string or 'N/A'.
     */
     function formatTimestamp(timestamp) {
        if (timestamp === null || timestamp === undefined) {
            return "N/A";
        }
        try {
            // Multiply by 1000 for JavaScript Date (expects milliseconds)
            const date = new Date(parseInt(timestamp, 10) * 1000);
            // Use locale string for better formatting
            return date.toLocaleString();
        } catch (e) {
            console.error("Error formatting timestamp:", timestamp, e);
            return "Invalid Date";
        }
     }


    /**
     * Renders the job history list in the designated UL element.
     * @param {Array} jobs - An array of job objects from the API.
     */
    function renderJobHistoryList(jobs) {
        if (!jobHistoryList) {
            console.warn("Job history list element not found. Cannot render.");
            return;
        }

        jobHistoryList.innerHTML = ''; // Clear previous entries

        if (jobs && jobs.length > 0) {
            jobs.forEach(job => {
                const li = document.createElement('li');
                const jobStatus = (job.status || 'UNKNOWN').toUpperCase();
                const statusClass = `job-status-${jobStatus}`;
                const date = formatTimestamp(job.timestamp); // Use JS formatter

                let downloadLinkHtml = '';
                if (job.status === 'COMPLETED' && job.download_url) {
                    // Ensure URL is properly encoded if needed, but usually pre-signed URLs are safe
                    downloadLinkHtml = ` <a href="${job.download_url}" class="button download-link" target="_blank" download>Download</a>`;
                }

                const displayName = job.original_filename || job.input_s3_key?.split('/').pop() || 'Unknown File';
                const shortJobId = job.job_id ? job.job_id.substring(0, 8) : 'N/A';

                // Use textContent for safety where possible, innerHTML for links/status span
                const jobIdSpan = document.createElement('span');
                jobIdSpan.innerHTML = `<strong>Job:</strong> ${shortJobId}...`;

                const fileSpan = document.createElement('span');
                fileSpan.textContent = `File: ${displayName}`;

                const formatSpan = document.createElement('span');
                formatSpan.textContent = `Format: ${job.output_format || 'N/A'}`;

                const dateSpan = document.createElement('span');
                dateSpan.textContent = `Updated: ${date}`; // Changed label

                const statusSpan = document.createElement('span');
                statusSpan.className = `job-status ${statusClass}`;
                statusSpan.textContent = jobStatus;

                li.appendChild(jobIdSpan);
                li.appendChild(fileSpan);
                li.appendChild(formatSpan);
                li.appendChild(dateSpan);
                li.appendChild(statusSpan);

                // Append download link if exists (using innerHTML for the anchor tag)
                if (downloadLinkHtml) {
                     const downloadSpan = document.createElement('span'); // Wrap link for styling/layout
                     downloadSpan.innerHTML = downloadLinkHtml;
                     li.appendChild(downloadSpan);
                }

                if (job.status === 'FAILED' && job.error) {
                    const errorSpan = document.createElement('span');
                    errorSpan.className = 'job-error-message';
                    errorSpan.style.cssText = 'color: #dc3545; font-size: 0.9em; flex-basis: 100%; margin-top: 5px;';
                    errorSpan.textContent = `Error: ${job.error}`;
                    li.appendChild(errorSpan);
                }
                jobHistoryList.appendChild(li);
            });
        } else {
            jobHistoryList.innerHTML = '<li><em>No recent jobs found.</em></li>';
        }
    }

    /**
     * Fetches job history from API and triggers rendering.
     */
    async function fetchAndRenderHistory() {
        // Ensure needed elements/config are present before fetching
        if (!jobHistorySection || !jobHistoryList || !API_GATEWAY_URL) {
            console.log("History section, list or API URL missing, skipping fetch.");
            stopHistoryRefresh();
            return;
        }

        console.log("Fetching job history via JS...");
        const token = await getJwtToken();
        if (!token) {
            // Stop refreshing if token is invalid/missing
            console.log("No valid token found, stopping history refresh.");
            stopHistoryRefresh();
             // Optionally update UI
             // jobHistoryList.innerHTML = '<li>Session expired. Please log in.</li>';
            return;
        }

        try {
            const response = await fetch(`${API_GATEWAY_URL}/jobs`, {
                headers: { 'Authorization': `Bearer ${token}` },
                cache: 'no-store' // Prevent browser caching of the API response
            });

            if (response.status === 401 || response.status === 403) {
                 console.warn('Auth error fetching history. Stopping refresh.');
                 stopHistoryRefresh();
                 jobHistoryList.innerHTML = '<li>Session expired. Please log in again.</li>';
                 return;
            }
            if (!response.ok) {
                throw new Error(`HTTP error ${response.status} ${response.statusText}`);
            }

            const jobs = await response.json();
            if (!Array.isArray(jobs)) {
                 throw new Error("Invalid history data received from server.");
            }
            renderJobHistoryList(jobs); // Render the fetched jobs

        } catch (error) {
            console.error('Error fetching or rendering job history:', error);
            // Avoid clearing list on temporary error, maybe show subtle indicator?
            // For now, just log the error. The next interval will try again.
            // jobHistoryList.innerHTML = `<li><em style="color: red;">Could not update history: ${error.message}</em></li>`;
        }
    }

    /**
     * Stops the periodic history refresh.
     */
    function stopHistoryRefresh() {
        if (historyIntervalId) {
            clearInterval(historyIntervalId);
            historyIntervalId = null;
            console.log("Periodic history refresh stopped.");
        }
    }

    // --- Initialization ---
    // Start periodic refresh ONLY if user is logged in AND history section exists
    if (IS_LOGGED_IN && jobHistorySection) {
        console.log("User is logged in, initiating periodic history refresh.");
        // Fetch immediately once on load (to potentially get faster update than server render)
        fetchAndRenderHistory();
        // Then set up the interval
        if (!historyIntervalId) { // Prevent multiple intervals if script re-runs
             historyIntervalId = setInterval(fetchAndRenderHistory, REFRESH_INTERVAL_MS);
             console.log(`History refresh interval set for ${REFRESH_INTERVAL_MS}ms.`);
        }
    } else {
        console.log("User not logged in or history section missing, periodic refresh not started.");
        // Ensure correct message if history list exists but user isn't logged in
        if (jobHistoryList && !IS_LOGGED_IN) {
             jobHistoryList.innerHTML = '<li>Log in to view job history.</li>';
        }
    }

}); // End of DOMContentLoaded listener