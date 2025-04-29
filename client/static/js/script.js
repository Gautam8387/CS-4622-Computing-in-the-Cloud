// ./client/static/js/app.js

// --- Configuration (from Flask Template) ---
const API_GATEWAY_URL = window.APP_CONFIG.api_gateway_url;
const CLIENT_TOKEN_ENDPOINT = '/get-token'; // Client backend endpoint to get JWT

// --- DOM Elements ---
const uploadForm = document.getElementById('upload-form');
const mediaFileInput = document.getElementById('media-file');
const dropArea = document.getElementById('drop-area');
const fileInfo = document.getElementById('file-info');
const submitButton = document.getElementById('submit-button');
const uploadProgressSection = document.getElementById('upload-progress');
const uploadProgressBar = document.getElementById('upload-progress-bar');
const uploadPercentage = document.getElementById('upload-percentage');
const jobStatusSection = document.getElementById('job-status-section');
const jobHistoryList = document.getElementById('job-history-list');
const refreshJobsButton = document.getElementById('refresh-jobs-button');

// --- State ---
let currentJobId = null;
let pollingIntervalId = null;
let currentUploadXhr = null; // To allow cancellation

// --- Helper Functions ---

/**
 * Fetches the JWT from the client's backend.
 * @returns {Promise<string|null>} JWT token or null if failed/not logged in.
 */
async function getJwtToken() {
    try {
        const response = await fetch(CLIENT_TOKEN_ENDPOINT);
        if (!response.ok) {
            console.error('Not authenticated or error fetching token.');
            // Optionally redirect to login or show message
            return null;
        }
        const data = await response.json();
        return data.access_token;
    } catch (error) {
        console.error('Network error fetching token:', error);
        return null;
    }
}

/**
 * Displays a status message in the job status section.
 * @param {string} message - The message to display.
 * @param {string} level - 'info', 'success', 'warning', 'error'.
 * @param {string|null} jobId - Optional job ID to associate.
 * @param {string|null} status - Optional status (PENDING, COMPLETED, etc).
 */
function displayStatus(message, level = 'info', jobId = null, status = null) {
    const statusDiv = document.createElement('div');
    statusDiv.className = `status-update status-${status || level}`; // Use job status class if available
    statusDiv.textContent = message;
    if (jobId) {
        statusDiv.setAttribute('data-job-id', jobId);
    }
    // Prepend new status messages
    jobStatusSection.insertBefore(statusDiv, jobStatusSection.firstChild);
}

/**
 * Clears old status messages for a specific job ID.
 * @param {string} jobId
 */
function clearPreviousJobStatus(jobId) {
     const existingMessages = jobStatusSection.querySelectorAll(`div[data-job-id="${jobId}"]`);
     existingMessages.forEach(msg => msg.remove());
}

// --- Event Listeners ---

// Drag and Drop File Input
if (dropArea) {
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false); // Prevent browser default behavior
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, () => dropArea.classList.add('highlight'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, () => dropArea.classList.remove('highlight'), false);
    });

    dropArea.addEventListener('drop', handleDrop, false);

    // Allow clicking the drop area to trigger the hidden file input
    dropArea.addEventListener('click', () => {
        mediaFileInput.click();
    });

     mediaFileInput.addEventListener('change', handleFileSelect, false);
}

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length > 0) {
        mediaFileInput.files = files; // Assign dropped file(s) to the input
        displayFileInfo(files[0]);
    }
}

function handleFileSelect() {
     if (mediaFileInput.files.length > 0) {
         displayFileInfo(mediaFileInput.files[0]);
     } else {
         fileInfo.textContent = '';
     }
}

function displayFileInfo(file) {
    if (file) {
        const fileSizeMB = (file.size / (1024 * 1024)).toFixed(2);
        fileInfo.textContent = `Selected: ${file.name} (${fileSizeMB} MB)`;
    } else {
         fileInfo.textContent = '';
    }
}


// Form Submission
if (uploadForm) {
    uploadForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        submitButton.disabled = true;
        submitButton.textContent = 'Processing...';
        jobStatusSection.innerHTML = ''; // Clear previous statuses
        uploadProgressSection.style.display = 'none'; // Hide progress initially
        uploadProgressBar.value = 0;
        uploadPercentage.textContent = '0';

        const token = await getJwtToken();
        if (!token) {
            displayStatus('Authentication error. Please log in again.', 'error');
            submitButton.disabled = false;
            submitButton.textContent = 'Start Transcoding';
            return;
        }

        const file = mediaFileInput.files[0];
        const email = document.getElementById('email').value;
        const outputFormat = document.getElementById('output_format').value;

        if (!file) {
            displayStatus('Please select a file to upload.', 'warning');
            submitButton.disabled = false;
            submitButton.textContent = 'Start Transcoding';
            return;
        }

        const formData = new FormData();
        formData.append('media_file', file);
        formData.append('output_format', outputFormat);
        if (email) {
             formData.append('email', email);
        }

        displayStatus(`Starting upload for ${file.name}...`, 'info');
        uploadProgressSection.style.display = 'block';

        // Use XMLHttpRequest for progress tracking
        currentUploadXhr = new XMLHttpRequest();
        currentUploadXhr.open('POST', `${API_GATEWAY_URL}/upload`, true);
        currentUploadXhr.setRequestHeader('Authorization', `Bearer ${token}`);
        // No Content-Type header needed for FormData, browser sets it with boundary

        currentUploadXhr.upload.onprogress = (event) => {
            if (event.lengthComputable) {
                const percentComplete = Math.round((event.loaded / event.total) * 100);
                uploadProgressBar.value = percentComplete;
                uploadPercentage.textContent = percentComplete;
            }
        };

        currentUploadXhr.onload = () => {
            uploadProgressSection.style.display = 'none'; // Hide progress on completion/error
            if (currentUploadXhr.status >= 200 && currentUploadXhr.status < 300) {
                try {
                    const data = JSON.parse(currentUploadXhr.responseText);
                    if (data.job_id) {
                        currentJobId = data.job_id;
                        displayStatus(`Upload complete. Job ID: ${currentJobId}. Waiting for transcoding...`, 'success', currentJobId, 'PENDING');
                        // Start polling for status
                        stopPolling(); // Clear any previous polling
                        pollStatus(currentJobId);
                    } else {
                        displayStatus('Upload succeeded but no Job ID received.', 'warning');
                    }
                } catch (e) {
                    console.error("Error parsing upload response:", e);
                    displayStatus('Upload complete but received invalid response from server.', 'error');
                }
            } else {
                console.error('Upload failed:', currentUploadXhr.statusText, currentUploadXhr.responseText);
                 try {
                     const errorData = JSON.parse(currentUploadXhr.responseText);
                     displayStatus(`Upload failed: ${errorData.error || currentUploadXhr.statusText}`, 'error');
                 } catch (e) {
                     displayStatus(`Upload failed: ${currentUploadXhr.statusText}`, 'error');
                 }
            }
             submitButton.disabled = false;
             submitButton.textContent = 'Start Transcoding';
        };

        currentUploadXhr.onerror = () => {
            console.error('Upload failed (network error)');
            displayStatus('Upload failed due to network error. Please try again.', 'error');
            uploadProgressSection.style.display = 'none';
            submitButton.disabled = false;
            submitButton.textContent = 'Start Transcoding';
        };

        currentUploadXhr.send(formData);
    });
}

// Refresh Job History Button
if (refreshJobsButton) {
    refreshJobsButton.addEventListener('click', fetchJobHistory);
}

// --- Core Logic ---

/**
 * Polls the API Gateway for the status of a specific job.
 * @param {string} jobId
 */
async function pollStatus(jobId) {
    const token = await getJwtToken();
    if (!token) {
        displayStatus(`Cannot poll status for Job ${jobId}: Not authenticated.`, 'error', jobId);
        stopPolling();
        return;
    }

    try {
        const response = await fetch(`${API_GATEWAY_URL}/status/${jobId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) {
            // Handle specific errors like 404 Not Found, etc.
            if (response.status === 404) {
                 displayStatus(`Job ${jobId} not found.`, 'error', jobId);
                 stopPolling();
                 return;
            }
             if (response.status === 401 || response.status === 403) {
                 displayStatus(`Authentication error checking status for Job ${jobId}. Please log in again.`, 'error', jobId);
                 stopPolling();
                 return;
            }
            // General error
            throw new Error(`HTTP error ${response.status}`);
        }

        const data = await response.json();
        //clearPreviousJobStatus(jobId); // Remove older status messages for this job

        switch (data.status) {
            case 'PENDING':
                displayStatus(`Job ${jobId}: Queued for processing...`, 'info', jobId, 'PENDING');
                // Continue polling
                pollingIntervalId = setTimeout(() => pollStatus(jobId), 5000); // Poll every 5 seconds
                break;
            case 'PROCESSING':
                displayStatus(`Job ${jobId}: Transcoding in progress...`, 'info', jobId, 'PROCESSING');
                pollingIntervalId = setTimeout(() => pollStatus(jobId), 5000);
                break;
            case 'COMPLETED':
                displayStatus(`Job ${jobId}: Transcoding complete! Download link sent via email (if provided) or available in Job History.`, 'success', jobId, 'COMPLETED');
                stopPolling();
                fetchJobHistory(); // Refresh history to show download link
                break;
            case 'FAILED':
                displayStatus(`Job ${jobId}: Transcoding failed. Reason: ${data.error || 'Unknown error'}`, 'error', jobId, 'FAILED');
                stopPolling();
                 fetchJobHistory(); // Refresh history
                break;
            default:
                 displayStatus(`Job ${jobId}: Unknown status received: ${data.status}`, 'warning', jobId);
                 pollingIntervalId = setTimeout(() => pollStatus(jobId), 10000); // Poll less frequently for unknown status
                 break;
        }

    } catch (error) {
        console.error(`Error polling status for job ${jobId}:`, error);
        displayStatus(`Error checking status for Job ${jobId}. Will retry shortly. (${error.message})`, 'warning', jobId);
        // Don't stop polling on temporary network errors, retry after a longer delay
        pollingIntervalId = setTimeout(() => pollStatus(jobId), 15000); // Retry after 15 seconds
    }
}

/**
 * Stops the current polling interval.
 */
function stopPolling() {
    if (pollingIntervalId) {
        clearTimeout(pollingIntervalId);
        pollingIntervalId = null;
    }
}

/**
 * Fetches and displays the user's recent job history.
 */
async function fetchJobHistory() {
    if (!jobHistoryList) return; // Don't run if the element doesn't exist

    const token = await getJwtToken();
    if (!token) {
        jobHistoryList.innerHTML = '<li>Please log in to view job history.</li>';
        return;
    }

    jobHistoryList.innerHTML = '<li>Loading job history...</li>'; // Show loading state

    try {
        const response = await fetch(`${API_GATEWAY_URL}/jobs`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) {
             if (response.status === 401 || response.status === 403) {
                 jobHistoryList.innerHTML = '<li>Authentication error fetching job history. Please log in again.</li>';
                 return;
            }
            throw new Error(`HTTP error ${response.status}`);
        }

        const jobs = await response.json();

        if (jobs && jobs.length > 0) {
            jobHistoryList.innerHTML = ''; // Clear loading state
            jobs.forEach(job => {
                const li = document.createElement('li');
                const statusClass = `job-status-${job.status || 'UNKNOWN'}`;
                const date = job.timestamp ? new Date(job.timestamp * 1000).toLocaleString() : 'N/A';

                let downloadLink = '';
                if (job.status === 'COMPLETED' && job.download_url) {
                     // Target _blank to open in new tab
                    downloadLink = `<a href="${job.download_url}" class="button download-link" target="_blank" download>Download</a>`;
                }

                 // Truncate long filenames or keys if necessary
                const displayName = job.original_filename || job.input_s3_key?.split('/').pop() || 'Unknown File';
                const shortJobId = job.job_id.substring(0, 8); // Show shorter ID

                li.innerHTML = `
                    <span><strong>Job:</strong> ${shortJobId}...</span>
                    <span><strong>File:</strong> ${displayName}</span>
                    <span><strong>Format:</strong> ${job.output_format || 'N/A'}</span>
                    <span><strong>Submitted:</strong> ${date}</span>
                    <span class="job-status ${statusClass}">${job.status || 'UNKNOWN'}</span>
                    ${downloadLink}
                `;
                 if (job.status === 'FAILED' && job.error) {
                     const errorSpan = document.createElement('span');
                     errorSpan.style.color = '#dc3545'; // Red color for error
                     errorSpan.style.fontSize = '0.9em';
                     errorSpan.style.flexBasis = '100%'; // Take full width
                     errorSpan.textContent = `Error: ${job.error}`;
                     li.appendChild(errorSpan);
                 }

                jobHistoryList.appendChild(li);
            });
        } else {
            jobHistoryList.innerHTML = '<li>No recent jobs found.</li>';
        }

    } catch (error) {
        console.error('Error fetching job history:', error);
        jobHistoryList.innerHTML = `<li>Error loading job history: ${error.message}. Please try refreshing.</li>`;
    }
}


// --- Initial Load ---
document.addEventListener('DOMContentLoaded', () => {
    // Fetch job history only if the history list element exists (i.e., user is logged in)
    if (jobHistoryList) {
        fetchJobHistory();
    }

    // // Example: If a job ID was passed via URL parameter (e.g., from email link)
    // const urlParams = new URLSearchParams(window.location.search);
    // const jobIdFromUrl = urlParams.get('job_id');
    // if (jobIdFromUrl) {
    //     displayStatus(`Checking status for Job ${jobIdFromUrl}...`, 'info', jobIdFromUrl);
    //     pollStatus(jobIdFromUrl);
    // }
});