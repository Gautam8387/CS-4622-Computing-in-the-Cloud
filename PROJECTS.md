# Project Ideas

## PROJECT 1: Simple Online Compiler and Code Execution Platform
### Define a use case + problem description:
We often need quick, accessible code compilation environments. Setting up a development environment can be platform-dependent. This project involves developing a basic online compiler where users can write, compile, and run code snippets in three programming languages (Python, C, and C++). The platform will handle code execution securely in isolated environments.

### Define a solution:
1. Supports three programming languages (Python, C, and C++)
2. Provides real-time code compilation and execution.
3. Offers secure, sandboxed execution environments.
4. Provides basic runtime output and error reporting.

### Define an architecture for deployment:
1. Frontend Service
    - React-based web interface.
    - Code editor with syntax highlighting.
    - Language selection dropdown.
2. Compiler/Execution Service
    - Uses Docker containers for language-specific environments.
    - Implements resource and time limitations.
    - Captures stdout/stderr.
3. Storage Service
    - Persistent storage for user code snippets for a limited time (1 day).

## PROJECT 2: Media Transcoding Service (for Video/Audio Files)

### Define a use case + problem description:
Create a service that automatically converts audio or video files from one format to another (e.g., MP4 to AVI, WAV to MP3). This could be especially useful for people who deal with media files often and want a simple service to handle conversions.

### Define a solution:
1. A webpage to upload files and choose the conversion type
2. Use FFmpeg as the backend to handle the actual format conversion.
3. Provide progress of conversion
4. Possible converting multiple files at once

### Define an architecture for deployment:
1. Frontend Service
    - React-based web interface.
    - File uploading.
    - Conversion selection dropdown.
2. Conversion/Execution Service
    - Uses Docker containers for FFmpeg and dependencies.
    - Mount temporary volumes and save files.
    - Implements resource and time limitations.
3. Storage Service
    - Persistent storage for user files for a limited time (1 day).
    - Downloadable link for converted files.