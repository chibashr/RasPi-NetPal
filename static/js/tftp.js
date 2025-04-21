// Current directory path for file browser
let currentPath = '';

// DOM Elements
const fileTableBody = document.getElementById('file-table-body');
const currentPathDisplay = document.getElementById('current-path');
const serverStatusElement = document.getElementById('server-status');
const serverIpAddresses = document.getElementById('server-ip-addresses');
const serverPort = document.getElementById('server-port');
const startServerBtn = document.getElementById('start-server');
const stopServerBtn = document.getElementById('stop-server');
const parentDirBtn = document.getElementById('parent-dir-btn');
const newFolderBtn = document.getElementById('new-folder-btn');
const uploadFileBtn = document.getElementById('upload-file-btn');
const tfpListSelect = document.getElementById('tftp-upload-file');
const dragDropZone = document.getElementById('drag-drop-zone');
const dragDropFileInput = document.getElementById('drag-drop-file-input');
const uploadProgress = document.getElementById('upload-progress');
const uploadProgressBar = document.getElementById('upload-progress-bar');
const uploadFileName = document.getElementById('upload-file-name');
const uploadPercentage = document.getElementById('upload-percentage');
const modalUploadProgress = document.getElementById('modal-upload-progress');
const modalUploadProgressBar = document.getElementById('modal-upload-progress-bar');

// Loading spinners
const tfptDownloadSpinner = document.getElementById('tftp-download-spinner');
const tfptUploadSpinner = document.getElementById('tftp-upload-spinner');
const ftpDownloadSpinner = document.getElementById('ftp-download-spinner');
const scpDownloadSpinner = document.getElementById('scp-download-spinner');
const fileUploadSpinner = document.getElementById('file-upload-spinner');
const newFolderSpinner = document.getElementById('new-folder-spinner');

// Modal elements
const uploadModal = document.getElementById('upload-modal');
const folderModal = document.getElementById('folder-modal');
const uploadTargetDirInput = document.getElementById('upload-target-dir');
const parentDirInput = document.getElementById('parent-dir');

// Tab switching
document.querySelectorAll('.tab-button').forEach(button => {
    button.addEventListener('click', function() {
        // Remove active class from all tabs
        document.querySelectorAll('.tab-button').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelectorAll('.tab-pane').forEach(pane => {
            pane.classList.remove('active');
        });
        
        // Add active class to clicked tab
        this.classList.add('active');
        const tabId = this.getAttribute('data-tab');
        document.getElementById(tabId).classList.add('active');
    });
});

// Initialize page
document.addEventListener('DOMContentLoaded', function() {
    // Load initial data
    refreshServerStatus();
    loadFileList('');
    
    // Set up event listeners
    setupEventListeners();
    setupDragAndDrop();
    
    // Refresh status every 30 seconds
    setInterval(refreshServerStatus, 30000);
});

function setupEventListeners() {
    // Server control buttons
    startServerBtn.addEventListener('click', startServer);
    stopServerBtn.addEventListener('click', stopServer);
    
    // File browser navigation
    parentDirBtn.addEventListener('click', navigateToParentDirectory);
    
    // New folder and upload buttons
    newFolderBtn.addEventListener('click', showNewFolderModal);
    uploadFileBtn.addEventListener('click', showUploadModal);
    
    // Modal close buttons
    document.querySelectorAll('.close-modal').forEach(button => {
        button.addEventListener('click', function() {
            uploadModal.style.display = 'none';
            folderModal.style.display = 'none';
        });
    });
    
    // Form submissions
    document.getElementById('file-upload-form').addEventListener('submit', uploadFile);
    document.getElementById('new-folder-form').addEventListener('submit', createNewFolder);
    document.getElementById('tftp-download-form').addEventListener('submit', tftpDownload);
    document.getElementById('tftp-upload-form').addEventListener('submit', tftpUpload);
    document.getElementById('ftp-download-form').addEventListener('submit', ftpDownload);
    document.getElementById('scp-download-form').addEventListener('submit', scpDownload);
    
    // Close modal when clicking outside of it
    window.addEventListener('click', function(event) {
        if (event.target === uploadModal) {
            uploadModal.style.display = 'none';
        }
        if (event.target === folderModal) {
            folderModal.style.display = 'none';
        }
    });
    
    // Refresh button
    document.getElementById('refresh-btn').addEventListener('click', function() {
        refreshServerStatus();
        loadFileList(currentPath);
        updateLastRefreshTime();
    });
}

// Set up drag and drop functionality
function setupDragAndDrop() {
    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dragDropZone.addEventListener(eventName, preventDefaults, false);
    });
    
    // Highlight drop zone when item is dragged over it
    ['dragenter', 'dragover'].forEach(eventName => {
        dragDropZone.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dragDropZone.addEventListener(eventName, unhighlight, false);
    });
    
    // Handle dropped files
    dragDropZone.addEventListener('drop', handleDrop, false);
    
    // Handle click on drop zone to select files
    dragDropZone.addEventListener('click', () => {
        dragDropFileInput.click();
    });
    
    // Handle file selection via input
    dragDropFileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            uploadFiles(e.target.files);
        }
    });
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    function highlight() {
        dragDropZone.classList.add('dragover');
    }
    
    function unhighlight() {
        dragDropZone.classList.remove('dragover');
    }
    
    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        
        if (files.length > 0) {
            uploadFiles(files);
        }
    }
}

// Upload files from drag and drop
function uploadFiles(files) {
    if (files.length === 0) return;
    
    const startTime = Date.now();
    let lastLoaded = 0;
    let speedUpdateInterval;
    
    // Show progress bar
    uploadProgress.style.display = 'block';
    uploadProgressBar.style.width = '0%';
    
    // Set file name in progress display
    uploadFileName.textContent = files[0].name;
    uploadPercentage.textContent = '0%';
    
    // Create speed display element if it doesn't exist
    let speedElement = document.getElementById('upload-speed');
    if (!speedElement) {
        speedElement = document.createElement('div');
        speedElement.id = 'upload-speed';
        speedElement.className = 'upload-speed';
        speedElement.textContent = 'Calculating...';
        document.querySelector('.upload-progress-info').appendChild(speedElement);
    } else {
        speedElement.textContent = 'Calculating...';
    }
    
    const formData = new FormData();
    formData.append('file', files[0]); // Upload only the first file for now
    formData.append('dir', currentPath);
    
    showStatusMessage('Uploading file...', 'info');
    
    // Create XHR request to track progress
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/tftp/upload', true);
    
    // Set up interval to calculate transfer speed
    speedUpdateInterval = setInterval(() => {
        // If no progress yet, don't update
        if (lastLoaded === 0) return;
        
        // Calculate and display transfer speed
        updateTransferSpeed(startTime, lastLoaded, speedElement);
    }, 1000);
    
    // Track upload progress
    xhr.upload.onprogress = function(e) {
        if (e.lengthComputable) {
            const percentComplete = Math.round((e.loaded / e.total) * 100);
            uploadProgressBar.style.width = percentComplete + '%';
            uploadPercentage.textContent = percentComplete + '%';
            
            // Save current loaded bytes for speed calculation
            lastLoaded = e.loaded;
            
            // Update speed immediately
            updateTransferSpeed(startTime, e.loaded, speedElement);
        }
    };
    
    // Handle response
    xhr.onload = function() {
        // Clear speed update interval
        clearInterval(speedUpdateInterval);
        
        if (xhr.status === 200) {
            const response = JSON.parse(xhr.responseText);
            if (response.success) {
                uploadPercentage.textContent = '100%';
                uploadProgressBar.style.width = '100%';
                
                // Calculate and display final transfer speed
                const totalTime = (Date.now() - startTime) / 1000;
                const sizeMB = response.size / (1024 * 1024);
                const speedMBps = sizeMB / totalTime;
                speedElement.textContent = `${speedMBps.toFixed(2)} MB/s`;
                
                showStatusMessage('File uploaded successfully', 'success');
                loadFileList(currentPath); // Refresh file list
            } else {
                showStatusMessage(`Error: ${response.error}`, 'error');
                speedElement.textContent = '-';
            }
        } else {
            showStatusMessage('Upload failed', 'error');
            speedElement.textContent = '-';
        }
        
        // Hide progress bar after a short delay
        setTimeout(() => {
            uploadProgress.style.display = 'none';
        }, 2000);
    };
    
    // Handle errors
    xhr.onerror = function() {
        clearInterval(speedUpdateInterval);
        speedElement.textContent = '-';
        showStatusMessage('Upload failed. Connection error.', 'error');
        uploadProgress.style.display = 'none';
    };
    
    xhr.send(formData);
}

// Load file list from the server
function loadFileList(path) {
    currentPath = path;
    currentPathDisplay.textContent = path || '/';
    
    // Update hidden form fields with current path
    uploadTargetDirInput.value = path;
    parentDirInput.value = path;
    
    showStatusMessage('Loading files...', 'info');
    
    fetch(`/tftp/list?dir=${encodeURIComponent(path)}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to load file list');
            }
            return response.json();
        })
        .then(data => {
            updateFileTable(data.files);
            updateFileDropdown(data.files);
            clearStatusMessage();
        })
        .catch(error => {
            showStatusMessage(`Error: ${error.message}`, 'error');
            console.error('Error loading file list:', error);
        });
}

// Update the file table with file list data
function updateFileTable(files) {
    fileTableBody.innerHTML = '';
    
    if (files.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = '<td colspan="4" class="text-center">No files found</td>';
        fileTableBody.appendChild(row);
        return;
    }
    
    // Sort directories first, then files
    files.sort((a, b) => {
        if (a.type === 'directory' && b.type !== 'directory') return -1;
        if (a.type !== 'directory' && b.type === 'directory') return 1;
        return a.name.localeCompare(b.name);
    });
    
    files.forEach(file => {
        const row = document.createElement('tr');
        
        // Create file name cell with icon
        const nameCell = document.createElement('td');
        if (file.type === 'directory') {
            nameCell.innerHTML = `<span class="icon-folder"></span> ${file.name}`;
            nameCell.style.cursor = 'pointer';
            nameCell.addEventListener('click', () => {
                navigateToDirectory(file.path);
            });
        } else {
            nameCell.innerHTML = `<span class="icon-file"></span> ${file.name}`;
        }
        
        // Create type cell
        const typeCell = document.createElement('td');
        typeCell.textContent = file.type.charAt(0).toUpperCase() + file.type.slice(1);
        
        // Create size cell
        const sizeCell = document.createElement('td');
        sizeCell.textContent = file.type === 'directory' ? '-' : formatFileSize(file.size);
        
        // Create actions cell
        const actionsCell = document.createElement('td');
        actionsCell.className = 'action-buttons';
        
        const actionDiv = document.createElement('div');
        actionDiv.className = 'flex-row';
        
        if (file.type !== 'directory') {
            // Add download button
            const downloadBtn = document.createElement('button');
            downloadBtn.className = 'button button-sm';
            downloadBtn.innerHTML = `<span class="icon-download"></span>`;
            downloadBtn.title = "Download";
            downloadBtn.addEventListener('click', () => {
                downloadFile(file.path);
            });
            actionDiv.appendChild(downloadBtn);
        }
        
        // Add delete button
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'button button-sm button-danger';
        deleteBtn.innerHTML = `<span class="icon-trash"></span>`;
        deleteBtn.title = "Delete";
        deleteBtn.addEventListener('click', () => {
            deleteItem(file.path, file.type);
        });
        actionDiv.appendChild(deleteBtn);
        
        actionsCell.appendChild(actionDiv);
        
        // Add cells to row
        row.appendChild(nameCell);
        row.appendChild(typeCell);
        row.appendChild(sizeCell);
        row.appendChild(actionsCell);
        
        // Add row to table
        fileTableBody.appendChild(row);
    });
}

// Update file dropdown for TFTP upload
function updateFileDropdown(files) {
    // Clear existing options except the first one
    while (tfpListSelect && tfpListSelect.options.length > 1) {
        tfpListSelect.remove(1);
    }
    
    // Add only files (not directories) to the dropdown
    const filesList = files.filter(file => file.type === 'file');
    
    filesList.forEach(file => {
        const option = document.createElement('option');
        option.value = file.path;
        option.textContent = file.name;
        if (tfpListSelect) {
            tfpListSelect.appendChild(option);
        }
    });
}

// Navigate to a directory
function navigateToDirectory(path) {
    if (path === "..") {
        // Handle special case for parent directory
        navigateToParentDirectory();
        return;
    }
    
    // Save previous directory for breadcrumb navigation
    const previousPath = currentPath;
    
    loadFileList(path);
    
    // Update browser history
    if (window.history && window.history.pushState) {
        const url = new URL(window.location.href);
        url.searchParams.set('dir', path);
        window.history.pushState({path: path, prevPath: previousPath}, '', url);
    }
}

// Navigate to parent directory
function navigateToParentDirectory() {
    if (!currentPath) return; // Already at root
    
    const lastSlashIndex = currentPath.lastIndexOf('/');
    const parentPath = lastSlashIndex <= 0 ? '' : currentPath.substring(0, lastSlashIndex);
    
    loadFileList(parentPath);
    
    // Update browser history
    if (window.history && window.history.pushState) {
        const url = new URL(window.location.href);
        url.searchParams.set('dir', parentPath);
        window.history.pushState({path: parentPath, prevPath: currentPath}, '', url);
    }
}

// Format file size in human-readable format
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    
    return (bytes / Math.pow(1024, i)).toFixed(2) + ' ' + units[i];
}

// Download a file
function downloadFile(path) {
    window.location.href = `/tftp/download?path=${encodeURIComponent(path)}`;
}

// Delete a file or directory
function deleteItem(path, type) {
    if (!confirm(`Are you sure you want to delete this ${type}?`)) {
        return;
    }
    
    showStatusMessage(`Deleting ${type}...`, 'info');
    
    fetch('/tftp/delete', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ path: path }),
    })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Failed to delete ${type}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                showStatusMessage(`${type.charAt(0).toUpperCase() + type.slice(1)} deleted successfully`, 'success');
                loadFileList(currentPath); // Refresh file list
            } else {
                showStatusMessage(`Error: ${data.error}`, 'error');
            }
        })
        .catch(error => {
            showStatusMessage(`Error: ${error.message}`, 'error');
            console.error(`Error deleting ${type}:`, error);
        });
}

// Show upload modal
function showUploadModal() {
    uploadTargetDirInput.value = currentPath;
    uploadModal.style.display = 'block';
}

// Show new folder modal
function showNewFolderModal() {
    parentDirInput.value = currentPath;
    folderModal.style.display = 'block';
}

// Upload a file from the modal form
function uploadFile(event) {
    event.preventDefault();
    
    const fileInput = document.getElementById('file-input');
    const startTime = Date.now();
    let lastLoaded = 0;
    let speedUpdateInterval;
    
    if (fileInput.files.length === 0) {
        showStatusMessage('Please select a file to upload', 'error');
        return;
    }
    
    // Show spinner and progress bar
    fileUploadSpinner.style.display = 'inline-block';
    modalUploadProgress.style.display = 'block';
    modalUploadProgressBar.style.width = '0%';
    
    // Set file name in progress display
    const fileName = fileInput.files[0].name;
    document.getElementById('modal-upload-file-name').textContent = fileName;
    document.getElementById('modal-upload-percentage').textContent = '0%';
    
    // Create speed display element if it doesn't exist
    let speedElement = document.getElementById('modal-upload-speed');
    if (!speedElement) {
        speedElement = document.createElement('div');
        speedElement.id = 'modal-upload-speed';
        speedElement.className = 'upload-speed';
        speedElement.textContent = 'Calculating...';
        document.querySelector('#modal-upload-progress .upload-progress-info').appendChild(speedElement);
    } else {
        speedElement.textContent = 'Calculating...';
    }
    
    const formData = new FormData(document.getElementById('file-upload-form'));
    
    showStatusMessage('Uploading file...', 'info');
    
    // Create XHR request to track progress
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/tftp/upload', true);
    
    // Set up interval to calculate transfer speed
    speedUpdateInterval = setInterval(() => {
        // If no progress yet, don't update
        if (lastLoaded === 0) return;
        
        // Calculate and display transfer speed
        updateTransferSpeed(startTime, lastLoaded, speedElement);
    }, 1000);
    
    // Track upload progress
    xhr.upload.onprogress = function(e) {
        if (e.lengthComputable) {
            const percentComplete = Math.round((e.loaded / e.total) * 100);
            modalUploadProgressBar.style.width = percentComplete + '%';
            document.getElementById('modal-upload-percentage').textContent = percentComplete + '%';
            
            // Save current loaded bytes for speed calculation
            lastLoaded = e.loaded;
            
            // Update speed immediately
            updateTransferSpeed(startTime, e.loaded, speedElement);
        }
    };
    
    // Handle response
    xhr.onload = function() {
        // Clear speed update interval
        clearInterval(speedUpdateInterval);
        fileUploadSpinner.style.display = 'none';
        
        if (xhr.status === 200) {
            const response = JSON.parse(xhr.responseText);
            if (response.success) {
                document.getElementById('modal-upload-percentage').textContent = '100%';
                modalUploadProgressBar.style.width = '100%';
                
                // Calculate and display final transfer speed
                const totalTime = (Date.now() - startTime) / 1000;
                const sizeMB = response.size / (1024 * 1024);
                const speedMBps = sizeMB / totalTime;
                speedElement.textContent = `${speedMBps.toFixed(2)} MB/s`;
                
                showStatusMessage('File uploaded successfully', 'success');
                uploadModal.style.display = 'none';
                document.getElementById('file-upload-form').reset();
                loadFileList(currentPath); // Refresh file list
            } else {
                showStatusMessage(`Error: ${response.error}`, 'error');
                speedElement.textContent = '-';
            }
        } else {
            showStatusMessage('Upload failed', 'error');
            speedElement.textContent = '-';
        }
        
        // Hide progress bar after a short delay
        setTimeout(() => {
            modalUploadProgress.style.display = 'none';
        }, 2000);
    };
    
    // Handle errors
    xhr.onerror = function() {
        clearInterval(speedUpdateInterval);
        fileUploadSpinner.style.display = 'none';
        modalUploadProgress.style.display = 'none';
        speedElement.textContent = '-';
        showStatusMessage('Upload failed. Connection error.', 'error');
    };
    
    xhr.send(formData);
}

// Create a new folder
function createNewFolder(event) {
    event.preventDefault();
    
    const folderName = document.getElementById('folder-name').value;
    const parentDir = parentDirInput.value;
    
    if (!folderName) {
        showStatusMessage('Please enter a folder name', 'error');
        return;
    }
    
    // Show spinner
    newFolderSpinner.style.display = 'inline-block';
    
    showStatusMessage('Creating folder...', 'info');
    
    fetch('/tftp/create_dir', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            name: folderName,
            parent_dir: parentDir,
        }),
    })
        .then(response => {
            newFolderSpinner.style.display = 'none';
            
            if (!response.ok) {
                throw new Error('Failed to create folder');
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                showStatusMessage('Folder created successfully', 'success');
                folderModal.style.display = 'none';
                document.getElementById('new-folder-form').reset();
                loadFileList(currentPath); // Refresh file list
            } else {
                showStatusMessage(`Error: ${data.error}`, 'error');
            }
        })
        .catch(error => {
            newFolderSpinner.style.display = 'none';
            showStatusMessage(`Error: ${error.message}`, 'error');
            console.error('Error creating folder:', error);
        });
}

// Refresh server status
function refreshServerStatus() {
    fetch('/tftp/tftp_status')
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to get server status');
            }
            return response.json();
        })
        .then(data => {
            // Update server status indicator
            if (data.status === 'running') {
                serverStatusElement.textContent = 'Running';
                serverStatusElement.className = 'badge badge-success';
            } else {
                serverStatusElement.textContent = 'Stopped';
                serverStatusElement.className = 'badge badge-danger';
            }
            
            // Update server info
            if (data.config && data.config.directory) {
                document.getElementById('tftp-directory').textContent = data.config.directory;
            }
            
            // Update network interfaces info
            if (data.interfaces && data.interfaces.length > 0) {
                const interfaceInfo = data.interfaces.map(iface => 
                    `${iface.name}: ${iface.address}`
                ).join('<br>');
                serverIpAddresses.innerHTML = interfaceInfo;
            } else {
                serverIpAddresses.textContent = 'No network interfaces detected';
            }
            
            // Update port
            if (data.config && data.config.address) {
                const portMatch = data.config.address.match(/:(\d+)/);
                if (portMatch && portMatch[1]) {
                    serverPort.textContent = portMatch[1];
                }
            }
        })
        .catch(error => {
            serverStatusElement.textContent = 'Unknown';
            serverStatusElement.className = 'badge badge-warning';
            console.error('Error getting server status:', error);
        });
}

// Start TFTP server
function startServer() {
    showStatusMessage('Starting TFTP server...', 'info');
    
    fetch('/tftp/tftp_server', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
            action: 'start'
        }),
    })
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to start server');
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                showStatusMessage('TFTP server started successfully', 'success');
                refreshServerStatus();
            } else {
                showStatusMessage(`Error: ${data.error}`, 'error');
            }
        })
        .catch(error => {
            showStatusMessage(`Error: ${error.message}`, 'error');
            console.error('Error starting server:', error);
        });
}

// Stop TFTP server
function stopServer() {
    showStatusMessage('Stopping TFTP server...', 'info');
    
    fetch('/tftp/tftp_server', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ action: 'stop' }),
    })
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to stop server');
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                showStatusMessage('TFTP server stopped successfully', 'success');
                refreshServerStatus();
            } else {
                showStatusMessage(`Error: ${data.error}`, 'error');
            }
        })
        .catch(error => {
            showStatusMessage(`Error: ${error.message}`, 'error');
            console.error('Error stopping server:', error);
        });
}

// TFTP download from remote server
function tftpDownload(event) {
    event.preventDefault();
    
    const server = document.getElementById('tftp-server-address').value;
    const filename = document.getElementById('tftp-filename').value;
    const targetDir = document.getElementById('tftp-target-dir').value;
    
    if (!server || !filename) {
        showStatusMessage('Server address and filename are required', 'error');
        return;
    }
    
    // Show spinner
    tfptDownloadSpinner.style.display = 'inline-block';
    showStatusMessage('Downloading via TFTP...', 'info');
    
    fetch('/tftp/tftp_download', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            server: server,
            filename: filename,
            target_dir: targetDir,
        }),
    })
        .then(response => {
            tfptDownloadSpinner.style.display = 'none';
            
            if (!response.ok) {
                throw new Error('Failed to download file');
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                showStatusMessage('File downloaded successfully via TFTP', 'success');
                loadFileList(targetDir || currentPath); // Refresh file list
            } else {
                showStatusMessage(`Error: ${data.error}`, 'error');
            }
        })
        .catch(error => {
            tfptDownloadSpinner.style.display = 'none';
            showStatusMessage(`Error: ${error.message}`, 'error');
            console.error('Error downloading file via TFTP:', error);
        });
}

// TFTP upload to remote server
function tftpUpload(event) {
    event.preventDefault();
    
    const server = document.getElementById('tftp-upload-server').value;
    const filePath = document.getElementById('tftp-upload-file').value;
    
    if (!server || !filePath) {
        showStatusMessage('Server address and file selection are required', 'error');
        return;
    }
    
    // Extract filename and directory from the path
    const lastSlashIndex = filePath.lastIndexOf('/');
    const filename = lastSlashIndex === -1 ? filePath : filePath.substring(lastSlashIndex + 1);
    const sourceDir = lastSlashIndex === -1 ? '' : filePath.substring(0, lastSlashIndex);
    
    // Show spinner and progress bar
    tfptUploadSpinner.style.display = 'inline-block';
    showStatusMessage('Uploading via TFTP...', 'info');
    
    // Get progress bar elements
    const progressBar = document.getElementById('tftp-client-upload-progress');
    const progressBarInner = document.getElementById('tftp-client-upload-progress-bar');
    
    // Show progress bar and set to 10% to indicate started
    progressBar.style.display = 'block';
    progressBarInner.style.width = '10%';
    
    fetch('/tftp/tftp_upload', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            server: server,
            filename: filename,
            source_dir: sourceDir,
        }),
    })
        .then(response => {
            // Set progress to 90% to indicate almost done
            progressBarInner.style.width = '90%';
            
            if (!response.ok) {
                throw new Error('Failed to upload file');
            }
            return response.json();
        })
        .then(data => {
            // Complete the progress bar
            progressBarInner.style.width = '100%';
            
            // Hide spinner
            tfptUploadSpinner.style.display = 'none';
            
            if (data.success) {
                showStatusMessage('File uploaded successfully via TFTP', 'success');
            } else {
                showStatusMessage(`Error: ${data.error}`, 'error');
            }
            
            // Hide progress bar after delay
            setTimeout(() => {
                progressBar.style.display = 'none';
            }, 1500);
        })
        .catch(error => {
            // Reset progress bar
            progressBarInner.style.width = '0%';
            progressBar.style.display = 'none';
            
            tfptUploadSpinner.style.display = 'none';
            showStatusMessage(`Error: ${error.message}`, 'error');
            console.error('Error uploading file via TFTP:', error);
        });
}

// FTP download from remote server
function ftpDownload(event) {
    event.preventDefault();
    
    const server = document.getElementById('ftp-server-address').value;
    const username = document.getElementById('ftp-username').value || 'anonymous';
    const password = document.getElementById('ftp-password').value || '';
    const filename = document.getElementById('ftp-filename').value;
    const targetDir = document.getElementById('ftp-target-dir').value;
    
    if (!server || !filename) {
        showStatusMessage('Server address and filename are required', 'error');
        return;
    }
    
    // Show spinner
    ftpDownloadSpinner.style.display = 'inline-block';
    showStatusMessage('Downloading via FTP...', 'info');
    
    fetch('/tftp/ftp_download', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            server: server,
            username: username,
            password: password,
            filename: filename,
            target_dir: targetDir,
        }),
    })
        .then(response => {
            ftpDownloadSpinner.style.display = 'none';
            
            if (!response.ok) {
                throw new Error('Failed to download file');
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                showStatusMessage('File downloaded successfully via FTP', 'success');
                loadFileList(targetDir || currentPath); // Refresh file list
            } else {
                showStatusMessage(`Error: ${data.error}`, 'error');
            }
        })
        .catch(error => {
            ftpDownloadSpinner.style.display = 'none';
            showStatusMessage(`Error: ${error.message}`, 'error');
            console.error('Error downloading file via FTP:', error);
        });
}

// SCP download from remote server
function scpDownload(event) {
    event.preventDefault();
    
    const server = document.getElementById('scp-server-address').value;
    const username = document.getElementById('scp-username').value;
    const remotePath = document.getElementById('scp-remote-path').value;
    const targetDir = document.getElementById('scp-target-dir').value;
    const useKey = document.getElementById('scp-use-key').checked;
    
    if (!server || !username || !remotePath) {
        showStatusMessage('Server address, username, and remote path are required', 'error');
        return;
    }
    
    // Show spinner
    scpDownloadSpinner.style.display = 'inline-block';
    showStatusMessage('Downloading via SCP...', 'info');
    
    fetch('/tftp/scp_download', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            server: server,
            username: username,
            remote_path: remotePath,
            target_dir: targetDir,
            use_key: useKey,
        }),
    })
        .then(response => {
            scpDownloadSpinner.style.display = 'none';
            
            if (!response.ok) {
                throw new Error('Failed to download file');
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                showStatusMessage('File downloaded successfully via SCP', 'success');
                loadFileList(targetDir || currentPath); // Refresh file list
            } else {
                showStatusMessage(`Error: ${data.error}`, 'error');
            }
        })
        .catch(error => {
            scpDownloadSpinner.style.display = 'none';
            showStatusMessage(`Error: ${error.message}`, 'error');
            console.error('Error downloading file via SCP:', error);
        });
}

// Show status message
function showStatusMessage(message, type) {
    const statusBar = document.getElementById('status-message');
    statusBar.textContent = message;
    statusBar.className = `status-bar ${type}`;
    statusBar.style.display = 'block';
    
    // Clear the message after 5 seconds if it's a success message
    if (type === 'success') {
        setTimeout(() => {
            clearStatusMessage();
        }, 5000);
    }
}

// Clear status message
function clearStatusMessage() {
    const statusBar = document.getElementById('status-message');
    statusBar.textContent = '';
    statusBar.style.display = 'none';
}

// Update last refresh time
function updateLastRefreshTime() {
    const timeElement = document.getElementById('last-update-time');
    timeElement.textContent = 'Last update: just now';
}

// Calculate and update transfer speed
function updateTransferSpeed(startTime, loaded, speedElement) {
    // Calculate elapsed time in seconds
    const elapsedTime = (Date.now() - startTime) / 1000;
    if (elapsedTime === 0) return; // Avoid division by zero
    
    // Calculate speed in bytes per second and convert to appropriate unit
    const bytesPerSecond = loaded / elapsedTime;
    
    // Display speed with appropriate unit
    if (bytesPerSecond < 1024) {
        speedElement.textContent = `${bytesPerSecond.toFixed(1)} B/s`;
    } else if (bytesPerSecond < 1024 * 1024) {
        speedElement.textContent = `${(bytesPerSecond / 1024).toFixed(1)} KB/s`;
    } else {
        speedElement.textContent = `${(bytesPerSecond / (1024 * 1024)).toFixed(2)} MB/s`;
    }
} 