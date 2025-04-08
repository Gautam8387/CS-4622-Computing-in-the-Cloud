<!-- ./PROJECT.md -->
# Final Project

## PROJECT: SaaS-Based Media Transcoding Service

### Define a use case + problem description

With the increasing consumption of multimedia content, users and businesses frequently need to convert audio and video files into different formats for compatibility, compression, or quality adjustments. Traditional transcoding tools require installation and local resources, which can be limiting. The goal is to provide a scalable, cloud-based media transcoding SaaS platform that simplifies format conversion while ensuring high availability and performance.

### Proposed Solution

The system will offer an online media transcoding service with the following capabilities:

1. Support for multiple input and output formats (e.g., MP4, AVI, MOV, WAV, MP3, FLAC).
2. Secure, efficient, and scalable transcoding powered by FFmpeg in containerised environments.
3. Real-time progress tracking and notifications on job completion.
4. *Batch processing* support for multiple files.
5. Temporary storage of files for a configurable period (e.g., 48 hours) to allow re-downloads.
6. User authentication, access control, and personalised file history.
7. Analytics and system monitoring for performance tracking.

### Architecture and Deployment Strategy

1. Frontend Service
    - Built using React.js with a responsive and intuitive UI.
    - File upload interface with drag-and-drop functionality.
    - User authentication via OAuth or JWT (Google/GitHub login support).
    - UI updates for real-time progress tracking.
2. Transcoding Service:
    - Uses Dockerized FFmpeg instances to handle audio/video conversion tasks.
    - Implements job queuing and parallel execution for efficiency in batch processing.
    - Provides detailed error reporting and logging for failed conversions.
    - Supports different encoding parameters for user-configurable output quality.
3. Data Storage & Logging
    - Stores uploaded and transcoded files temporarily in an S3-compatible object storage system.
    - Storing logs for job execution details, errors, and system performance metrics.
4. Other:
    - Allow users to download converted files over HTTPS.
    - Implements rate limiting to prevent excessive API requests.
    - Uses AWS Lambda for demand-based dynamic scaling.
