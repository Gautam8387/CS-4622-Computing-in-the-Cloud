// ./client/static/js/script.js
document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('file');
    const form = document.getElementById('uploadForm');
    const statusDiv = document.getElementById('status');
    const formatSelector = document.getElementById('formatSelector');
    const outputFormat = document.getElementById('output_format');
    const submitBtn = document.getElementById('submitBtn');
    const uploadCard = document.getElementById('uploadCard');

    // Supported formats
    const VIDEO_FORMATS = ['MP4', 'AVI', 'MOV', 'MKV', 'WebM'];
    const AUDIO_FORMATS = ['MP3', 'WAV', 'FLAC', 'AAC'];

    // Load jobs on page load
    loadJobs();

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
        fileInput.files = e.dataTransfer.files;
        handleFileSelection();
    });

    // File input click
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', handleFileSelection);

    function handleFileSelection() {
        const file = fileInput.files[0];
        if (file) {
            const mimeType = file.type;
            const isVideo = mimeType.startsWith('video/');
            const isAudio = mimeType.startsWith('audio/');

            if (!isVideo && !isAudio) {
                alert('Unsupported file type. Please upload video or audio files.');
                return;
            }

            // Clear and populate format selector
            outputFormat.innerHTML = '';
            if (isVideo) {
                const videoGroup = document.createElement('optgroup');
                videoGroup.label = 'Video Formats';
                VIDEO_FORMATS.forEach(format => {
                    const option = document.createElement('option');
                    option.value = format.toLowerCase();
                    option.textContent = format;
                    videoGroup.appendChild(option);
                });
                outputFormat.appendChild(videoGroup);

                const audioGroup = document.createElement('optgroup');
                audioGroup.label = 'Audio Formats';
                AUDIO_FORMATS.forEach(format => {
                    const option = document.createElement('option');
                    option.value = format.toLowerCase();
                    option.textContent = format;
                    audioGroup.appendChild(option);
                });
                outputFormat.appendChild(audioGroup);
            } else if (isAudio) {
                const audioGroup = document.createElement('optgroup');
                audioGroup.label = 'Audio Formats';
                AUDIO_FORMATS.forEach(format => {
                    const option = document.createElement('option');
                    option.value = format.toLowerCase();
                    option.textContent = format;
                    audioGroup.appendChild(option);
                });
                outputFormat.appendChild(audioGroup);
            }

            formatSelector.classList.remove('d-none');
            submitBtn.disabled = false;
            submitBtn.textContent = 'Start Transcoding';
        }
    }

    // Form submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(form);
        statusDiv.innerHTML = '<p class="text-muted">Uploading...</p>';

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });
            const result = await response.json();

            if (response.ok) {
                statusDiv.innerHTML = `<p class="text-success">Upload successful! Job ID: ${result.job_id}</p>`;
                pollStatus(result.job_id);
                loadJobs();  // Refresh jobs after upload
            } else {
                statusDiv.innerHTML = `<p class="text-danger">Error: ${result.error}</p>`;
            }
        } catch (error) {
            statusDiv.innerHTML = `<p class="text-danger">Error: ${error.message}</p>`;
        }
    });

    // Poll job status
    async function pollStatus(jobId) {
        const interval = setInterval(async () => {
            try {
                const response = await fetch(`/status/${jobId}`);
                const status = await response.json();
                statusDiv.innerHTML = `<p class="text-muted">Status: ${status.status}</p>`;
                if (status.status === 'completed') {
                    clearInterval(interval);
                    statusDiv.innerHTML += `<p class="text-success">Check your email for the download link!</p>`;
                    loadJobs();  // Refresh jobs on completion
                }
            } catch (error) {
                statusDiv.innerHTML = `<p class="text-danger">Error checking status: ${error.message}</p>`;
                clearInterval(interval);
            }
        }, 2000);  // Poll every 2 seconds
    }

    // Load recent jobs
    async function loadJobs() {
        try {
            const response = await fetch('/jobs');
            const jobs = await response.json();
            if (response.ok && jobs.length > 0) {
                let html = '<div class="card p-4 shadow-sm mt-4"><h2 class="mb-3 text-dark">Recent Transcoding Jobs</h2><table class="table table-bordered"><thead><tr><th>Filename</th><th>Input Format</th><th>Output Format</th><th>Status</th><th>Timestamp</th><th>Action</th></tr></thead><tbody>';
                jobs.forEach(job => {
                    html += `<tr><td>${job.filename}</td><td>${job.input_format}</td><td>${job.output_format}</td><td>${job.status === 'completed' ? '<span class="text-success">✓ Completed</span>' : '<span class="text-danger">✗ Failed</span>'}</td><td>${job.timestamp}</td><td><a href="${job.download_url}" class="btn btn-sm btn-outline-secondary">↓</a></td></tr>`;
                });
                html += '</tbody></table></div>';
                document.querySelector('.container').insertAdjacentHTML('beforeend', html);
            }
        } catch (error) {
            console.error('Error loading jobs:', error);
        }
    }
});