// ./client/static/js/script.js
document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('file');
    const form = document.getElementById('uploadForm');
    const statusDiv = document.getElementById('status');
    const formatSelector = document.getElementById('formatSelector');
    const outputFormatSelect = document.getElementById('output_format');
    const submitBtn = document.getElementById('submitBtn');
    const recentJobsContainer = document.getElementById('recentJobsContainer'); // Added an ID to the container
    const emailInput = document.getElementById('email'); // Get email input

    // Check if user is logged in (simple check based on email field being pre-filled/readonly)
    const isLoggedIn = emailInput && emailInput.readOnly;

    // Supported formats (Consider fetching from backend or config)
    const VIDEO_FORMATS = ['MP4', 'AVI', 'MOV', 'MKV', 'WebM'];
    const AUDIO_FORMATS = ['MP3', 'WAV', 'FLAC', 'AAC'];

    // --- Event Listeners ---

    if (dropZone && fileInput) {
        // Drag-and-drop functionality
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });

        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('dragover');
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                fileInput.files = e.dataTransfer.files;
                handleFileSelection();
            }
        });

        // File input click
        dropZone.addEventListener('click', () => {
            fileInput.click();
        });

        fileInput.addEventListener('change', handleFileSelection);
    }

    if (form) {
        // Form submission
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            submitBtn.disabled = true; // Disable button during upload
            statusDiv.innerHTML = '<p class="text-muted"><div class="spinner-border spinner-border-sm" role="status"><span class="visually-hidden">Loading...</span></div> Uploading...</p>';

            const formData = new FormData(form);

            try {
                // No need to manually add Authorization header if using standard session cookies
                // If using JWT in localStorage/sessionStorage, add it here:
                // const token = sessionStorage.getItem('jwt_token');
                // const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData,
                    // headers: headers // Add headers if using storage-based JWT
                });

                const result = await response.json();

                if (response.ok) {
                    statusDiv.innerHTML = `<p class="text-info">Upload successful! Job ID: ${result.job_id}. Processing...</p>`;
                    pollStatus(result.job_id);
                    // Optionally reset form:
                    // form.reset();
                    // formatSelector.classList.add('d-none');
                    // dropZone.querySelector('p').textContent = 'Drag & drop or click to select another file';
                } else {
                    statusDiv.innerHTML = `<p class="text-danger">Upload Error: ${result.error || 'Unknown error'}</p>`;
                    submitBtn.disabled = false; // Re-enable button on error
                }
            } catch (error) {
                console.error("Upload fetch error:", error);
                statusDiv.innerHTML = `<p class="text-danger">Network Error: Could not connect to the upload service.</p>`;
                submitBtn.disabled = false; // Re-enable button on error
            }
        });
    }

    // --- Helper Functions ---

    function handleFileSelection() {
        const file = fileInput.files[0];
        if (file) {
            const mimeType = file.type;
            const isVideo = mimeType && mimeType.startsWith('video/');
            const isAudio = mimeType && mimeType.startsWith('audio/');

            if (!isVideo && !isAudio) {
                alert('Unsupported file type. Please upload video or audio files.');
                resetFormState();
                return;
            }

            // Update drop zone text
            dropZone.querySelector('p').textContent = `Selected: ${file.name}`;

            // Clear and populate format selector
            outputFormatSelect.innerHTML = '';
            const availableOutputFormats = isVideo ? [...VIDEO_FORMATS, ...AUDIO_FORMATS] : AUDIO_FORMATS;

            if (isVideo) {
                 addFormatOptions('Video Formats', VIDEO_FORMATS, outputFormatSelect);
                 addFormatOptions('Audio Only Formats', AUDIO_FORMATS, outputFormatSelect);
            } else { // isAudio
                 addFormatOptions('Audio Formats', AUDIO_FORMATS, outputFormatSelect);
            }

            formatSelector.classList.remove('d-none');
            submitBtn.disabled = false; // Enable submit button
            submitBtn.textContent = 'Start Transcoding'; // Reset button text
            statusDiv.innerHTML = ''; // Clear previous status
        } else {
             resetFormState();
        }
    }

     function addFormatOptions(groupLabel, formats, selectElement) {
        const optgroup = document.createElement('optgroup');
        optgroup.label = groupLabel;
        formats.forEach(format => {
            const option = document.createElement('option');
            option.value = format.toLowerCase(); // Use lowercase value
            option.textContent = format;
            optgroup.appendChild(option);
        });
        selectElement.appendChild(optgroup);
    }

    function resetFormState() {
        fileInput.value = ''; // Clear file input
        formatSelector.classList.add('d-none');
        submitBtn.disabled = true;
        dropZone.querySelector('p').textContent = 'Drag & drop your files here or click to select files for transcoding';
        statusDiv.innerHTML = '';
         outputFormatSelect.innerHTML = '';
    }

    // Poll job status
    async function pollStatus(jobId) {
        const pollInterval = 5000; // Poll every 5 seconds
        let consecutiveErrors = 0;
        const maxErrors = 3;

        const intervalId = setInterval(async () => {
            try {
                // No need to manually add Authorization header if using standard session cookies
                // const token = sessionStorage.getItem('jwt_token');
                // const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

                const response = await fetch(`/status/${jobId}`); // Add headers if needed

                if (!response.ok) {
                     // Handle non-2xx responses gracefully
                     console.error(`Status check failed for ${jobId}: ${response.status}`);
                     consecutiveErrors++;
                     if (consecutiveErrors >= maxErrors) {
                        statusDiv.innerHTML = `<p class="text-warning">Could not get status update for Job ID: ${jobId}. Please check history later.</p>`;
                        clearInterval(intervalId);
                     }
                     return; // Skip processing this interval
                }

                const statusData = await response.json();
                consecutiveErrors = 0; // Reset error count on success

                let statusText = '';
                let statusClass = 'text-muted';

                switch (statusData.status.toLowerCase()) {
                    case 'completed':
                        statusText = `✓ Completed! Check email for download link.`;
                        statusClass = 'text-success';
                        clearInterval(intervalId); // Stop polling
                        submitBtn.disabled = false; // Re-enable button
                        submitBtn.textContent = 'Transcode Another File';
                        // Maybe refresh job list automatically:
                        // loadJobs();
                        break;
                    case 'failed':
                        statusText = `✗ Failed. ${statusData.error || 'Reason unknown.'}`;
                        statusClass = 'text-danger';
                        clearInterval(intervalId); // Stop polling
                        submitBtn.disabled = false; // Re-enable button
                         submitBtn.textContent = 'Try Transcoding Again';
                        break;
                    case 'pending':
                        statusText = `<div class="spinner-border spinner-border-sm" role="status"><span class="visually-hidden">Loading...</span></div> Pending...`;
                        statusClass = 'text-info';
                        break;
                    case 'processing':
                    case 'started': // Celery states
                        statusText = `<div class="spinner-border spinner-border-sm" role="status"><span class="visually-hidden">Loading...</span></div> Processing...`;
                        statusClass = 'text-primary';
                        break;
                    default:
                        statusText = `Status: ${statusData.status}`;
                        statusClass = 'text-muted';
                }

                statusDiv.innerHTML = `<p class="${statusClass}">${statusText}</p>`;

            } catch (error) {
                console.error(`Error polling status for ${jobId}:`, error);
                consecutiveErrors++;
                if (consecutiveErrors >= maxErrors) {
                    statusDiv.innerHTML = `<p class="text-warning">Network error checking status for Job ID: ${jobId}. Please check history later.</p>`;
                    clearInterval(intervalId); // Stop polling on repeated errors
                    submitBtn.disabled = false;
                }
            }
        }, pollInterval);
    }

    // Function to load and display recent jobs (assuming the HTML structure exists)
    // This part relies on the jobs being passed from Flask template initially.
    // If dynamic loading is needed without page refresh:
    /*
    async function loadJobs() {
        if (!isLoggedIn || !recentJobsContainer) return; // Only load if logged in and container exists

        try {
            const response = await fetch('/jobs'); // Assumes a '/jobs' endpoint exists
            if (!response.ok) throw new Error(`Failed to fetch jobs: ${response.status}`);

            const jobs = await response.json();
            renderJobs(jobs);

        } catch (error) {
            console.error('Error loading jobs:', error);
            recentJobsContainer.innerHTML = '<p class="text-warning">Could not load job history.</p>';
        }
    }

    function renderJobs(jobs) {
        if (!recentJobsContainer) return;
        if (jobs.length === 0) {
            recentJobsContainer.innerHTML = '<p class="text-muted">No recent jobs found.</p>';
            return;
        }

        let tableHtml = `
            <h2 class="mb-3 text-dark">Recent Transcoding Jobs</h2>
            <div class="table-responsive">
                <table class="table table-bordered table-striped table-hover">
                    <thead class="table-light">
                        <tr>
                            <th>Filename</th>
                            <th>Input</th>
                            <th>Output</th>
                            <th>Status</th>
                            <th>Timestamp</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>`;

        jobs.forEach(job => {
            let statusBadge = '';
            switch (job.status.toLowerCase()) {
                 case 'completed': statusBadge = '<span class="badge bg-success">Completed</span>'; break;
                 case 'failed': statusBadge = '<span class="badge bg-danger">Failed</span>'; break;
                 case 'pending': statusBadge = '<span class="badge bg-info text-dark">Pending</span>'; break;
                 case 'processing': // or started
                 case 'started':
                    statusBadge = '<span class="badge bg-primary">Processing</span>'; break;
                 default: statusBadge = `<span class="badge bg-secondary">${job.status}</span>`;
            }
            const downloadButton = job.status.toLowerCase() === 'completed' && job.download_url
                ? `<a href="${job.download_url}" class="btn btn-sm btn-outline-primary" title="Download" target="_blank" download>↓</a>`
                : `<button class="btn btn-sm btn-outline-secondary" disabled title="Download unavailable">↓</button>`;

            tableHtml += `
                <tr>
                    <td>${job.filename || 'N/A'}</td>
                    <td>${job.input_format || 'N/A'}</td>
                    <td>${job.output_format || 'N/A'}</td>
                    <td>${statusBadge}</td>
                    <td>${job.timestamp || 'N/A'}</td>
                    <td>${downloadButton}</td>
                </tr>`;
        });

        tableHtml += '</tbody></table></div>';
        recentJobsContainer.innerHTML = tableHtml;
    }

    // Initial load if logged in
    if (isLoggedIn) {
       // Jobs are loaded via template rendering in this setup.
       // If you switch to dynamic loading, call loadJobs() here.
       // loadJobs();
    }
    */
});