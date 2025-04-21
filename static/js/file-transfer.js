/**
 * File Transfer and TFTP functionality
 */

document.addEventListener('DOMContentLoaded', function() {
    // TFTP Server Controls
    const startTftpBtn = document.getElementById('start-tftp');
    const stopTftpBtn = document.getElementById('stop-tftp');
    const tftpStatusEl = document.getElementById('tftp-status');
    const tftpInfoEl = document.getElementById('tftp-info');
    
    // File Browser
    const currentPathEl = document.getElementById('current-path');
    const fileListEl = document.getElementById('file-list');
    const parentDirBtn = document.getElementById('parent-dir');
    const refreshFilesBtn = document.getElementById('refresh-files');
    const createFolderBtn = document.getElementById('create-folder');
    const browseTftpDirBtn = document.getElementById('browse-tftp-dir');
    
    // Modals
    const newFolderModal = document.getElementById('new-folder-modal');
    const folderNameInput = document.getElementById('folder-name');
    const createFolderSubmitBtn = document.getElementById('create-folder-submit');
    const cancelFolderBtn = document.getElementById('cancel-folder');
    const closeFolderModalBtn = document.getElementById('close-folder-modal');
    
    const fileDetailsModal = document.getElementById('file-details-modal');
    const fileDetailsContent = document.getElementById('file-details-content');
    const closeFileDetailsBtn = document.getElementById('close-file-details');
    
    // File Upload
    const dropArea = document.getElementById('drop-area');
    const fileInput = document.getElementById('file-input');
    const uploadProgress = document.getElementById('upload-progress');
    
    // Initialize
    loadCurrentPath();
    checkTftpStatus();
    
    // Add event listener for the browse button
    if (browseTftpDirBtn) {
        browseTftpDirBtn.addEventListener('click', function() {
            // Disable default action (opens a file browser)
            event.preventDefault();
            
            // Just navigate to the current path displayed in the file browser
            loadCurrentPath();
            showStatusMessage('Browsing TFTP root directory', 'info');
        });
    }
    
    // TFTP Server Functions
    function checkTftpStatus() {
        fetch('/tftp/status')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Status check failed: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.running) {
                    tftpStatusEl.textContent = 'Active';
                    tftpStatusEl.className = 'badge badge-success';
                    startTftpBtn.disabled = true;
                    stopTftpBtn.disabled = false;
                    tftpInfoEl.style.display = 'block';
                } else {
                    tftpStatusEl.textContent = 'Inactive';
                    tftpStatusEl.className = 'badge badge-danger';
                    startTftpBtn.disabled = false;
                    stopTftpBtn.disabled = true;
                    tftpInfoEl.style.display = 'none';
                }
            })
            .catch(error => {
                console.error('Error checking TFTP status:', error);
                showStatusMessage('Error checking TFTP status: ' + error.message, 'error');
                // Set to inactive state if there's an error
                tftpStatusEl.textContent = 'Inactive';
                tftpStatusEl.className = 'badge badge-danger';
                startTftpBtn.disabled = false;
                stopTftpBtn.disabled = true;
                tftpInfoEl.style.display = 'none';
            });
    }
    
    startTftpBtn.addEventListener('click', function() {
        fetch('/tftp/start', { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showStatusMessage('TFTP server started successfully', 'success');
                    checkTftpStatus();
                } else {
                    showStatusMessage('Error starting TFTP server: ' + data.error, 'error');
                }
            })
            .catch(error => {
                console.error('Error starting TFTP server:', error);
                showStatusMessage('Error starting TFTP server', 'error');
            });
    });
    
    stopTftpBtn.addEventListener('click', function() {
        fetch('/tftp/stop', { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showStatusMessage('TFTP server stopped successfully', 'success');
                    checkTftpStatus();
                } else {
                    showStatusMessage('Error stopping TFTP server: ' + data.error, 'error');
                }
            })
            .catch(error => {
                console.error('Error stopping TFTP server:', error);
                showStatusMessage('Error stopping TFTP server', 'error');
            });
    });
    
    // File Browser Functions
    function loadCurrentPath() {
        fetch('/tftp/current_path')
            .then(response => response.json())
            .then(data => {
                if (data.path) {
                    currentPathEl.textContent = data.path;
                    loadFiles(data.path);
                }
            })
            .catch(error => {
                console.error('Error loading current path:', error);
                showStatusMessage('Error loading current path', 'error');
                // Default to root path
                currentPathEl.textContent = "/";
                loadFiles("/");
            });
    }
    
    function loadFiles(path) {
        fileListEl.innerHTML = '<tr><td colspan="4" class="text-center">Loading files...</td></tr>';
        
        fetch(`/tftp/files?path=${encodeURIComponent(path)}`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    showStatusMessage('Error loading files: ' + data.error, 'error');
                    return;
                }
                
                // Update the current path display
                if (data.current_dir !== undefined) {
                    let displayPath = data.current_dir;
                    if (displayPath === '') {
                        displayPath = '/';
                    } else if (!displayPath.startsWith('/')) {
                        displayPath = '/' + displayPath;
                    }
                    currentPathEl.textContent = displayPath;
                }
                
                if (data.files && Array.isArray(data.files)) {
                    fileListEl.innerHTML = '';
                    
                    if (data.files.length === 0) {
                        fileListEl.innerHTML = '<tr><td colspan="4" class="text-center">No files in this directory</td></tr>';
                        return;
                    }
                    
                    data.files.forEach(file => {
                        const row = document.createElement('tr');
                        
                        // Name cell with icon
                        const nameCell = document.createElement('td');
                        const nameSpan = document.createElement('span');
                        
                        if (file.type === 'directory') {
                            // Add folder icon
                            const folderIcon = document.createElement('span');
                            folderIcon.className = 'icon-folder';
                            nameSpan.appendChild(folderIcon);
                            nameSpan.appendChild(document.createTextNode(file.name));
                            nameSpan.style.cursor = 'pointer';
                            nameSpan.addEventListener('click', () => navigateToDirectory(file.path));
                        } else {
                            // Add file icon
                            const fileIcon = document.createElement('span');
                            fileIcon.className = 'icon-file';
                            nameSpan.appendChild(fileIcon);
                            nameSpan.appendChild(document.createTextNode(file.name));
                        }
                        
                        nameCell.appendChild(nameSpan);
                        row.appendChild(nameCell);
                        
                        // Type cell
                        const typeCell = document.createElement('td');
                        typeCell.textContent = file.type === 'directory' ? 'Folder' : getFileExtension(file.name);
                        row.appendChild(typeCell);
                        
                        // Size cell
                        const sizeCell = document.createElement('td');
                        sizeCell.textContent = file.type === 'directory' ? '--' : formatFileSize(file.size);
                        row.appendChild(sizeCell);
                        
                        // Actions cell
                        const actionsCell = document.createElement('td');
                        const actionsDiv = document.createElement('div');
                        actionsDiv.className = 'action-buttons';
                        
                        if (file.type !== 'directory') {
                            // Download button
                            const downloadBtn = document.createElement('button');
                            downloadBtn.className = 'button button-sm button-info';
                            downloadBtn.textContent = 'Download';
                            downloadBtn.addEventListener('click', () => downloadFile(file.path));
                            actionsDiv.appendChild(downloadBtn);
                            
                            // View button for text files
                            if (isTextFile(file.name)) {
                                const viewBtn = document.createElement('button');
                                viewBtn.className = 'button button-sm button-secondary';
                                viewBtn.textContent = 'View';
                                viewBtn.addEventListener('click', () => viewFile(file.path));
                                actionsDiv.appendChild(viewBtn);
                            }
                        }
                        
                        // Rename button for both files and directories
                        const renameBtn = document.createElement('button');
                        renameBtn.className = 'button button-sm button-secondary';
                        renameBtn.textContent = 'Rename';
                        renameBtn.addEventListener('click', () => showRenamePrompt(file.path, file.name));
                        actionsDiv.appendChild(renameBtn);
                        
                        // Delete button
                        const deleteBtn = document.createElement('button');
                        deleteBtn.className = 'button button-sm button-danger';
                        deleteBtn.textContent = 'Delete';
                        deleteBtn.addEventListener('click', () => deleteFile(file.path, file.type === 'directory'));
                        actionsDiv.appendChild(deleteBtn);
                        
                        actionsCell.appendChild(actionsDiv);
                        row.appendChild(actionsCell);
                        
                        fileListEl.appendChild(row);
                    });
                }
            })
            .catch(error => {
                console.error('Error loading files:', error);
                showStatusMessage('Error loading files', 'error');
                fileListEl.innerHTML = '<tr><td colspan="4" class="text-center">Error loading files</td></tr>';
            });
    }
    
    function navigateToDirectory(path) {
        // Format the path properly
        if (path !== '/' && path.endsWith('/')) {
            path = path.slice(0, -1);
        }
        
        // Update the current path display
        currentPathEl.textContent = path;
        
        // Load files for the new path
        loadFiles(path);
    }
    
    parentDirBtn.addEventListener('click', function() {
        const currentPath = currentPathEl.textContent;
        if (currentPath === '/' || currentPath === '') {
            return; // Already at root
        }
        
        const pathParts = currentPath.split('/').filter(Boolean);
        pathParts.pop(); // Remove last directory
        
        const parentPath = '/' + pathParts.join('/');
        navigateToDirectory(parentPath === '' ? '/' : parentPath);
    });
    
    refreshFilesBtn.addEventListener('click', function() {
        loadFiles(currentPathEl.textContent);
    });
    
    // New Folder Modal
    createFolderBtn.addEventListener('click', function() {
        newFolderModal.style.display = 'block';
        folderNameInput.value = '';
        folderNameInput.focus();
    });
    
    closeFolderModalBtn.addEventListener('click', function() {
        newFolderModal.style.display = 'none';
    });
    
    cancelFolderBtn.addEventListener('click', function() {
        newFolderModal.style.display = 'none';
    });
    
    createFolderSubmitBtn.addEventListener('click', function() {
        const folderName = folderNameInput.value.trim();
        if (!folderName) {
            showStatusMessage('Please enter a folder name', 'error');
            return;
        }
        
        const currentPath = currentPathEl.textContent;
        
        fetch('/tftp/create_folder', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                path: currentPath,
                name: folderName
            })
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showStatusMessage('Folder created successfully', 'success');
                    loadFiles(currentPath);
                    newFolderModal.style.display = 'none';
                } else {
                    showStatusMessage('Error creating folder: ' + data.error, 'error');
                }
            })
            .catch(error => {
                console.error('Error creating folder:', error);
                showStatusMessage('Error creating folder', 'error');
            });
    });
    
    // File Details Modal
    closeFileDetailsBtn.addEventListener('click', function() {
        fileDetailsModal.style.display = 'none';
    });
    
    // Close modals when clicking outside
    window.addEventListener('click', function(event) {
        if (event.target === newFolderModal) {
            newFolderModal.style.display = 'none';
        }
        if (event.target === fileDetailsModal) {
            fileDetailsModal.style.display = 'none';
        }
    });
    
    // File Operations
    function downloadFile(path) {
        window.location.href = `/tftp/download?path=${encodeURIComponent(path)}`;
    }
    
    function viewFile(path) {
        fileDetailsModal.style.display = 'block';
        fileDetailsContent.innerHTML = '<div class="loading-text">Loading file content...</div>';
        
        fetch(`/tftp/view?path=${encodeURIComponent(path)}`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    fileDetailsContent.innerHTML = `<div class="error">${data.error}</div>`;
                    return;
                }
                
                if (data.content) {
                    fileDetailsContent.innerHTML = `<pre>${escapeHtml(data.content)}</pre>`;
                }
            })
            .catch(error => {
                console.error('Error viewing file:', error);
                fileDetailsContent.innerHTML = '<div class="error">Error loading file content</div>';
            });
    }
    
    function showRenamePrompt(path, currentName) {
        // Ask for the new name using a prompt
        const newName = prompt(`Rename "${currentName}" to:`, currentName);
        
        // If user cancels or enters an empty name, abort
        if (!newName || newName === currentName) {
            return;
        }
        
        // Send the rename request to the server
        fetch('/tftp/rename', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                old_path: path,
                new_name: newName
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showStatusMessage(`Renamed "${currentName}" to "${newName}"`, 'success');
                loadFiles(currentPathEl.textContent); // Refresh the file list
            } else {
                showStatusMessage(`Error renaming file: ${data.error}`, 'error');
            }
        })
        .catch(error => {
            console.error('Error renaming file:', error);
            showStatusMessage('Error renaming file', 'error');
        });
    }
    
    function deleteFile(path, isDirectory) {
        if (!confirm(isDirectory ? 'Delete this folder and all its contents?' : 'Delete this file?')) {
            return;
        }
        
        fetch('/tftp/delete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ path: path })
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showStatusMessage(isDirectory ? 'Folder deleted' : 'File deleted', 'success');
                    loadFiles(currentPathEl.textContent);
                } else {
                    showStatusMessage('Error deleting: ' + data.error, 'error');
                }
            })
            .catch(error => {
                console.error('Error deleting:', error);
                showStatusMessage('Error deleting file/folder', 'error');
            });
    }
    
    // File Upload via Drag and Drop
    dropArea.addEventListener('click', function() {
        fileInput.click();
    });
    
    fileInput.addEventListener('change', function() {
        if (this.files.length > 0) {
            handleFiles(this.files);
        }
    });
    
    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
    });
    
    // Highlight drop area when item is dragged over it
    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });
    
    // Handle dropped files
    dropArea.addEventListener('drop', handleDrop, false);
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    function highlight() {
        dropArea.classList.add('dragover');
    }
    
    function unhighlight() {
        dropArea.classList.remove('dragover');
    }
    
    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }
    
    function handleFiles(files) {
        uploadProgress.innerHTML = '';
        uploadProgress.style.display = 'block';
        
        let completed = 0;
        const totalFiles = files.length;
        
        Array.from(files).forEach(file => {
            uploadFile(file, (success) => {
                completed++;
                if (completed === totalFiles) {
                    setTimeout(() => {
                        uploadProgress.style.display = 'none';
                        loadFiles(currentPathEl.textContent);
                    }, 1000);
                }
            });
        });
    }
    
    function uploadFile(file, callback) {
        const currentPath = currentPathEl.textContent;
        const formData = new FormData();
        formData.append('file', file);
        formData.append('dir', currentPath);
        
        // Create progress item
        const progressItem = document.createElement('div');
        progressItem.className = 'upload-progress-item';
        progressItem.innerHTML = `
            <div class="upload-progress-info">
                <span class="upload-file-name">${file.name}</span>
                <span class="upload-percentage">0%</span>
            </div>
            <div class="upload-progress-bar"></div>
        `;
        uploadProgress.appendChild(progressItem);
        
        const progressBar = progressItem.querySelector('.upload-progress-bar');
        const percentageEl = progressItem.querySelector('.upload-percentage');
        
        const xhr = new XMLHttpRequest();
        
        xhr.upload.addEventListener('progress', e => {
            if (e.lengthComputable) {
                const percentage = Math.round((e.loaded * 100) / e.total);
                progressBar.style.width = percentage + '%';
                percentageEl.textContent = percentage + '%';
            }
        });
        
        xhr.addEventListener('load', () => {
            if (xhr.status === 200) {
                progressBar.style.width = '100%';
                percentageEl.textContent = '100%';
                
                // Add success indicator
                const infoDiv = progressItem.querySelector('.upload-progress-info');
                infoDiv.innerHTML += '<span class="upload-speed">Completed</span>';
                
                callback(true);
            } else {
                progressBar.style.backgroundColor = '#dc3545';
                percentageEl.textContent = 'Failed';
                
                // Add error message
                const infoDiv = progressItem.querySelector('.upload-progress-info');
                infoDiv.innerHTML += '<span class="upload-speed" style="color: #dc3545;">Failed</span>';
                
                callback(false);
            }
        });
        
        xhr.addEventListener('error', () => {
            progressBar.style.backgroundColor = '#dc3545';
            percentageEl.textContent = 'Error';
            callback(false);
        });
        
        xhr.open('POST', '/tftp/upload');
        xhr.send(formData);
    }
    
    // Utility Functions
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        
        return parseFloat((bytes / Math.pow(1024, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    function getFileExtension(filename) {
        return filename.slice((filename.lastIndexOf('.') - 1 >>> 0) + 2) || 'File';
    }
    
    function isTextFile(filename) {
        const textExtensions = ['txt', 'log', 'ini', 'conf', 'xml', 'json', 'html', 'htm', 'css', 'js', 'py', 'sh', 'md'];
        const ext = getFileExtension(filename).toLowerCase();
        return textExtensions.includes(ext);
    }
    
    function escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }
    
    // Status message handling
    function showStatusMessage(message, type = 'info', duration = 5000) {
        const statusElement = document.getElementById('status-message');
        if (!statusElement) return;
        
        statusElement.textContent = message;
        statusElement.className = 'status-bar ' + type;
        statusElement.style.display = 'block';
        
        // Don't auto-hide error messages
        if (type !== 'error') {
            setTimeout(() => {
                statusElement.style.display = 'none';
            }, duration);
        }
    }
}); 