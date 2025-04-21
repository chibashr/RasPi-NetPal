// Packet Capture Page JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // UI element references
    const startCaptureBtn = document.getElementById('start-capture-btn');
    const stopCaptureBtn = document.getElementById('stop-capture-btn');
    const downloadCaptureBtn = document.getElementById('download-capture-btn');
    const clearOutputBtn = document.getElementById('clear-output-btn');
    const captureOutput = document.getElementById('capture-output');
    const interfaceSelect = document.getElementById('interface');
    const filterInput = document.getElementById('filter');
    const limitInput = document.getElementById('limit');
    const durationInput = document.getElementById('duration');
    const promiscuousInputs = document.querySelectorAll('input[name="promiscuous"]');
    const renameModal = document.getElementById('rename-modal');
    const renameForm = document.getElementById('rename-form');
    const renameCaptureIdInput = document.getElementById('rename-capture-id');
    const newCaptureNameInput = document.getElementById('new-capture-name');
    
    // Capture state variables
    let captureRunning = false;
    let currentCaptureId = null;
    let captureUpdateInterval = null;

    // Initialize UI state
    initializeCaptureUI();
    
    // Add event listeners
    startCaptureBtn.addEventListener('click', startCapture);
    stopCaptureBtn.addEventListener('click', stopCapture);
    downloadCaptureBtn.addEventListener('click', downloadCapture);
    clearOutputBtn.addEventListener('click', clearOutput);
    
    // Add rename form submit handler
    if (renameForm) {
        renameForm.addEventListener('submit', function(e) {
            e.preventDefault();
            submitRenameForm();
        });
    }
    
    // Close buttons for modals
    document.querySelectorAll('.modal .close').forEach(closeBtn => {
        closeBtn.addEventListener('click', function() {
            const modal = this.closest('.modal');
            if (modal) modal.style.display = 'none';
        });
    });
    
    // Initialize UI based on current state
    function initializeCaptureUI() {
        // Initially disable stop and download buttons
        stopCaptureBtn.disabled = true;
        downloadCaptureBtn.disabled = true;
        
        // Check if a capture is already running
        fetch('/get_capture_output')
            .then(response => response.json())
            .then(data => {
                if (data.capture_running) {
                    // Update UI for running capture
                    captureRunning = true;
                    startCaptureBtn.disabled = true;
                    stopCaptureBtn.disabled = false;
                    // Start polling for updates
                    startCaptureUpdates();
                } else {
                    // Update UI for stopped capture
                    captureRunning = false;
                    startCaptureBtn.disabled = false;
                    stopCaptureBtn.disabled = true;
                }
            })
            .catch(error => {
                console.error('Error checking capture status:', error);
            });
    }
    
    // Start capture function
    function startCapture() {
        if (captureRunning) return;
        
        const interface = interfaceSelect.value;
        const filter = filterInput.value;
        const promiscuous = getSelectedPromiscuousMode();
        const captureNameInput = prompt("Enter a name for this capture (optional):", "");
        const captureName = captureNameInput || "";
        
        // Clear output
        captureOutput.innerHTML = '';
        
        // Get form data
        const formData = new FormData();
        formData.append('interface', interface);
        formData.append('filter', filter);
        formData.append('promiscuous', promiscuous);
        formData.append('name', captureName);
        
        // Update UI
        startCaptureBtn.disabled = true;
        stopCaptureBtn.disabled = false;
        
        // Start the capture
        fetch('/start_capture', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                captureRunning = true;
                currentCaptureId = data.capture_id;
                // Start polling for updates
                startCaptureUpdates();
            } else {
                alert('Error: ' + data.message);
                startCaptureBtn.disabled = false;
                stopCaptureBtn.disabled = true;
            }
        })
        .catch(error => {
            console.error('Error starting capture:', error);
            alert('Error starting capture: ' + error);
            startCaptureBtn.disabled = false;
            stopCaptureBtn.disabled = true;
        });
    }
    
    // Stop capture function
    function stopCapture() {
        if (!captureRunning) return;
        
        // Update UI
        stopCaptureBtn.disabled = true;
        
        const formData = new FormData();
        if (currentCaptureId) {
            formData.append('capture_id', currentCaptureId);
        }
        
        fetch('/stop_capture', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            captureRunning = false;
            stopCaptureUpdateInterval();
            startCaptureBtn.disabled = false;
            downloadCaptureBtn.disabled = false;
            
            // Refresh capture history
            refreshCaptureHistory();
        })
        .catch(error => {
            console.error('Error stopping capture:', error);
            alert('Error stopping capture: ' + error);
            stopCaptureBtn.disabled = false;
        });
    }
    
    // Download capture function
    function downloadCapture() {
        if (!currentCaptureId) return;
        
        window.location.href = '/download_capture/' + currentCaptureId;
    }
    
    // Clear output function
    function clearOutput() {
        captureOutput.innerHTML = '<div class="no-data">Capture output cleared</div>';
    }
    
    // Get selected promiscuous mode
    function getSelectedPromiscuousMode() {
        for (const radio of promiscuousInputs) {
            if (radio.checked) {
                return radio.value;
            }
        }
        return 'true'; // Default to promiscuous mode
    }
    
    // Start updating capture output
    function startCaptureUpdates() {
        // Clear any existing interval
        stopCaptureUpdateInterval();
        
        // Start a new interval
        captureUpdateInterval = setInterval(updateCaptureOutput, 1000);
        
        // Immediately fetch first update
        updateCaptureOutput();
    }
    
    // Stop updating capture output
    function stopCaptureUpdateInterval() {
        if (captureUpdateInterval) {
            clearInterval(captureUpdateInterval);
            captureUpdateInterval = null;
        }
    }
    
    // Update capture output
    function updateCaptureOutput() {
        const url = currentCaptureId ? 
            '/get_capture_output?id=' + currentCaptureId : 
            '/get_capture_output';
            
        fetch(url)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    updateCaptureDisplay(data.output);
                    
                    // If capture is no longer running, update UI
                    if (!data.capture_running && captureRunning) {
                        captureRunning = false;
                        stopCaptureUpdateInterval();
                        startCaptureBtn.disabled = false;
                        stopCaptureBtn.disabled = true;
                        downloadCaptureBtn.disabled = false;
                        
                        // Refresh the history table
                        refreshCaptureHistory();
                    }
                }
            })
            .catch(error => {
                console.error('Error updating capture output:', error);
            });
    }
    
    // Update the capture display with new output
    function updateCaptureDisplay(output) {
        if (!output || output.length === 0) {
            if (captureOutput.innerHTML === '') {
                captureOutput.innerHTML = '<div class="no-data">No packets captured yet</div>';
            }
            return;
        }
        
        // Clear the "no packets" message if it exists
        if (captureOutput.querySelector('.no-data')) {
            captureOutput.innerHTML = '';
        }
        
        // Format the output
        const html = output.map(line => {
            return `<div class="capture-line">${line}</div>`;
        }).join('');
        
        captureOutput.innerHTML = html;
        
        // Scroll to bottom
        captureOutput.scrollTop = captureOutput.scrollHeight;
    }
    
    // Refresh capture history
    function refreshCaptureHistory() {
        fetch('/capture')
            .then(response => response.text())
            .then(html => {
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');
                const newHistoryTable = doc.getElementById('capture-history-body');
                
                if (newHistoryTable) {
                    const currentHistoryTable = document.getElementById('capture-history-body');
                    if (currentHistoryTable) {
                        currentHistoryTable.innerHTML = newHistoryTable.innerHTML;
                        
                        // Update last update time
                        updateLastUpdateTime();
                    }
                }
            })
            .catch(error => {
                console.error('Error refreshing capture history:', error);
            });
    }
    
    // Update last update time
    function updateLastUpdateTime() {
        const timeElement = document.getElementById('update-time-value');
        if (timeElement) {
            timeElement.textContent = 'just now';
            
            // Reset the timer for "seconds ago"
            if (window.updateTimeInterval) {
                clearInterval(window.updateTimeInterval);
            }
            
            let seconds = 0;
            window.updateTimeInterval = setInterval(() => {
                seconds++;
                if (seconds < 60) {
                    timeElement.textContent = seconds + ' seconds ago';
                } else if (seconds < 3600) {
                    const minutes = Math.floor(seconds / 60);
                    timeElement.textContent = minutes + ' minute' + (minutes > 1 ? 's' : '') + ' ago';
                } else {
                    const hours = Math.floor(seconds / 3600);
                    timeElement.textContent = hours + ' hour' + (hours > 1 ? 's' : '') + ' ago';
                }
            }, 1000);
        }
    }
    
    // Handle capture file download
    window.downloadCapture = function(captureId) {
        window.location.href = '/download_capture/' + captureId;
    };
    
    // Handle capture file deletion
    window.deleteCapture = function(captureId) {
        if (confirm('Are you sure you want to delete this capture?')) {
            fetch('/delete_capture/' + captureId, {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    refreshCaptureHistory();
                } else {
                    alert('Error: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Error deleting capture:', error);
                alert('Error deleting capture: ' + error);
            });
        }
    };
    
    // Show rename modal
    window.renameCapture = function(captureId) {
        // Find current name in the table
        const row = document.querySelector(`tr[data-id="${captureId}"]`);
        let currentName = '';
        
        if (row) {
            const nameCell = row.querySelector('.capture-name');
            if (nameCell) {
                currentName = nameCell.textContent.trim();
            }
        }
        
        // Set values in the form
        renameCaptureIdInput.value = captureId;
        newCaptureNameInput.value = currentName;
        
        // Show modal
        renameModal.style.display = 'block';
    };
    
    // Close rename modal
    window.closeRenameModal = function() {
        renameModal.style.display = 'none';
    };
    
    // Submit rename form
    function submitRenameForm() {
        const captureId = renameCaptureIdInput.value;
        const newName = newCaptureNameInput.value.trim();
        
        if (!captureId || !newName) {
            alert('Capture ID and new name are required');
            return;
        }
        
        const formData = new FormData();
        formData.append('capture_id', captureId);
        formData.append('new_name', newName);
        
        fetch('/rename_capture/' + captureId, {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Close modal
                closeRenameModal();
                
                // Update the table cell
                const row = document.querySelector(`tr[data-id="${captureId}"]`);
                if (row) {
                    const nameCell = row.querySelector('.capture-name');
                    if (nameCell) {
                        nameCell.textContent = newName;
                    }
                }
                
                // Refresh the table (optional, in case server data changed)
                refreshCaptureHistory();
            } else {
                alert('Error: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error renaming capture:', error);
            alert('Error renaming capture: ' + error);
        });
    }
    
    // Close modals when clicking outside of them
    window.onclick = function(event) {
        if (event.target.classList.contains('modal')) {
            event.target.style.display = 'none';
        }
    };
    
    // Initialize by checking for capture in progress
    initializeCaptureUI();
}); 