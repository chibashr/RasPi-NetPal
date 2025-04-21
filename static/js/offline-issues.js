/**
 * Offline issue reporting system
 * Allows users to report issues while offline and queue them for submission when online
 */

// Store for offline issues when system is totally offline
const OFFLINE_ISSUES_KEY = 'offline_issues_temp';

// Issue status enum
const IssueStatus = {
    PENDING: 'pending',
    SUBMITTED: 'submitted',
    FAILED: 'failed'
};

// Base URL for API requests
const API_URL = '/api/issues';

// Get stored issues from server API
async function getStoredIssues() {
    try {
        // If we're offline, use localStorage as a temporary store
        if (!isOnline()) {
            const offlineIssues = localStorage.getItem(OFFLINE_ISSUES_KEY);
            return offlineIssues ? JSON.parse(offlineIssues) : [];
        }
        
        // If we're online, fetch from the server
        const response = await fetch(API_URL);
        
        if (!response.ok) {
            throw new Error(`API request failed: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('Error loading issues:', error);
        
        // If API request fails, try localStorage as fallback
        try {
            const offlineIssues = localStorage.getItem(OFFLINE_ISSUES_KEY);
            return offlineIssues ? JSON.parse(offlineIssues) : [];
        } catch (e) {
            console.error('Error loading offline issues:', e);
            return [];
        }
    }
}

// Save issues to server API
async function saveIssues(issues) {
    try {
        // If we're offline, save to localStorage temporarily
        if (!isOnline()) {
            localStorage.setItem(OFFLINE_ISSUES_KEY, JSON.stringify(issues));
            return true;
        }
        
        // First try to sync any pending offline issues
        await syncOfflineIssues();
        
        // If online but API fails, fallback to localStorage
    } catch (error) {
        console.error('Error saving issues:', error);
        localStorage.setItem(OFFLINE_ISSUES_KEY, JSON.stringify(issues));
        showStatusMessage('Failed to save issues to server, stored locally', 'warning');
    }
}

// Sync offline issues to server when online
async function syncOfflineIssues() {
    if (!isOnline()) return;
    
    try {
        const offlineIssues = localStorage.getItem(OFFLINE_ISSUES_KEY);
        
        if (!offlineIssues) return;
        
        const issues = JSON.parse(offlineIssues);
        
        if (issues.length === 0) return;
        
        let syncCount = 0;
        
        // Send each issue to the server
        for (const issue of issues) {
            // Skip issues that already have an ID from the server
            if (issue.id && issue.id.length > 10) continue;
            
            // Create issue on server
            const response = await fetch(API_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    title: issue.title,
                    description: issue.description,
                    type: issue.type,
                    status: issue.status
                })
            });
            
            if (response.ok) {
                syncCount++;
            }
        }
        
        if (syncCount > 0) {
            // Clear offline storage after sync
            localStorage.removeItem(OFFLINE_ISSUES_KEY);
            showStatusMessage(`Synced ${syncCount} offline issues to server`, 'success');
            
            // Update the UI
            updateIssueCountBadge();
            if (document.getElementById('issue-manage-view').style.display !== 'none') {
                showIssueManager();
            }
        }
    } catch (error) {
        console.error('Error syncing offline issues:', error);
    }
}

// Add a new issue via API
async function queueIssue(title, description, type) {
    try {
        // Prepare issue data
        const issueData = {
            title,
            description,
            type,
            status: IssueStatus.PENDING
        };
        
        // If offline, store locally
        if (!isOnline()) {
            const issues = await getStoredIssues();
            
            const newIssue = {
                ...issueData,
                id: Date.now().toString(),
                timestamp: new Date().toISOString(),
                retries: 0
            };
            
            issues.push(newIssue);
            localStorage.setItem(OFFLINE_ISSUES_KEY, JSON.stringify(issues));
            
            showStatusMessage('Issue saved locally. Will sync when online.', 'info');
            return newIssue;
        }
        
        // If online, post to API
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(issueData)
        });
        
        if (!response.ok) {
            throw new Error(`API request failed: ${response.status}`);
        }
        
        // Return the created issue
        return await response.json();
    } catch (error) {
        console.error('Error queuing issue:', error);
        
        // On error, fall back to local storage
        const offlineIssues = localStorage.getItem(OFFLINE_ISSUES_KEY);
        const issues = offlineIssues ? JSON.parse(offlineIssues) : [];
        
        const newIssue = {
            title,
            description,
            type,
            id: Date.now().toString(),
            timestamp: new Date().toISOString(),
            status: IssueStatus.PENDING,
            retries: 0
        };
        
        issues.push(newIssue);
        localStorage.setItem(OFFLINE_ISSUES_KEY, JSON.stringify(issues));
        
        showStatusMessage('Failed to save issue to server, stored locally', 'warning');
        return newIssue;
    }
}

// Update an issue's status
async function updateIssueStatus(id, status, retries = 0) {
    try {
        // If offline, update localStorage
        if (!isOnline()) {
            const issues = await getStoredIssues();
            const issue = issues.find(i => i.id === id);
            
            if (issue) {
                issue.status = status;
                issue.retries = retries;
                localStorage.setItem(OFFLINE_ISSUES_KEY, JSON.stringify(issues));
            }
            
            return issue;
        }
        
        // If online, update via API
        const response = await fetch(`${API_URL}/${id}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ status, retries })
        });
        
        if (!response.ok) {
            throw new Error(`API request failed: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('Error updating issue status:', error);
        
        // On error, fall back to local storage
        const issues = await getStoredIssues();
        const issue = issues.find(i => i.id === id);
        
        if (issue) {
            issue.status = status;
            issue.retries = retries;
            localStorage.setItem(OFFLINE_ISSUES_KEY, JSON.stringify(issues));
        }
        
        return issue;
    }
}

// Delete an issue
async function deleteIssueFromStorage(id) {
    try {
        // If offline, update localStorage
        if (!isOnline()) {
            const issues = await getStoredIssues();
            const filteredIssues = issues.filter(i => i.id !== id);
            localStorage.setItem(OFFLINE_ISSUES_KEY, JSON.stringify(filteredIssues));
            return true;
        }
        
        // If online, delete via API
        const response = await fetch(`${API_URL}/${id}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error(`API request failed: ${response.status}`);
        }
        
        return true;
    } catch (error) {
        console.error('Error deleting issue:', error);
        
        // On error, fall back to local storage
        const issues = await getStoredIssues();
        const filteredIssues = issues.filter(i => i.id !== id);
        localStorage.setItem(OFFLINE_ISSUES_KEY, JSON.stringify(filteredIssues));
        
        return true;
    }
}

// Check if we're online with a more reliable method
function isOnline() {
    // First check the navigator.onLine property
    if (!navigator.onLine) {
        return false;
    }
    
    // We could also test connectivity to our own server instead of relying solely on navigator.onLine
    // But for now, we'll use this as it's the most reliable cross-browser solution without external requests
    return navigator.onLine;
}

// Try to submit pending issues
async function submitPendingIssues() {
    // First check if we're online before attempting any submissions
    if (!isOnline()) {
        console.log('Device is offline. Skipping submission attempts.');
        return;
    }
    
    // Make sure we're working with the latest issues
    await syncOfflineIssues();
    
    const issues = await getStoredIssues();
    const pendingIssues = issues.filter(issue => issue.status === IssueStatus.PENDING);
    
    if (pendingIssues.length === 0) return;
    
    for (const issue of pendingIssues) {
        try {
            // Double-check we're still online before each submission attempt
            if (!isOnline()) {
                console.log('Connection lost during submission process. Stopping.');
                break;
            }
            
            const success = await submitIssueToGitHub(issue);
            
            if (success) {
                await updateIssueStatus(issue.id, IssueStatus.SUBMITTED);
            } else {
                const newRetries = issue.retries + 1;
                if (newRetries > 3) {
                    await updateIssueStatus(issue.id, IssueStatus.FAILED, newRetries);
                } else {
                    await updateIssueStatus(issue.id, IssueStatus.PENDING, newRetries);
                }
            }
        } catch (error) {
            console.error('Error submitting issue:', error);
            const newRetries = issue.retries + 1;
            if (newRetries > 3) {
                await updateIssueStatus(issue.id, IssueStatus.FAILED, newRetries);
            }
        }
    }
    
    // Update the UI
    updateIssueCountBadge();
    if (document.getElementById('issue-manage-view').style.display !== 'none') {
        showIssueManager();
    }
}

// Submit an issue to GitHub (when online)
async function submitIssueToGitHub(issue) {
    // First check if we're online - don't even try if offline
    if (!isOnline()) {
        showStatusMessage('Cannot submit issue while offline. It will be queued for later.', 'info', 5000);
        return false;
    }
    
    try {
        // Create a proper GitHub issue URL with parameters
        const baseUrl = 'https://github.com/chibashr/RasPi-NetPal/issues/new';
        
        // Create search params to pre-fill the GitHub issue form
        const params = new URLSearchParams({
            title: issue.title,
            body: `**Type:** ${issue.type}\n**Reported:** ${new Date(issue.timestamp).toLocaleString()}\n\n${issue.description}\n\n*This issue was reported from the offline reporting system.*`,
            labels: issue.type
        });
        
        // Generate a full URL with the query parameters
        const fullUrl = `${baseUrl}?${params.toString()}`;
        
        // Perform a connectivity check before opening the window
        try {
            // Try a very lightweight fetch to see if we can reach GitHub
            const checkResponse = await fetch('https://github.com', { 
                method: 'HEAD',
                mode: 'no-cors',
                // Set a short timeout
                signal: AbortSignal.timeout(2000)
            });
            
            // If we got here, we have some kind of connection
            console.log('GitHub appears to be reachable');
        } catch (error) {
            // If the fetch fails, we're probably offline or GitHub is unreachable
            console.log('GitHub is not reachable:', error);
            showStatusMessage('Cannot connect to GitHub. Issue saved for later submission.', 'info', 5000);
            return false;
        }
        
        // Open the GitHub issue page in a new tab if we've confirmed connectivity
        const newTab = window.open(fullUrl, '_blank');
        
        // If popup was blocked or failed, try a different approach
        if (!newTab || newTab.closed || typeof newTab.closed === 'undefined') {
            console.log('Popup blocked or failed. Displaying GitHub submission notification');
            
            // Show a notification that the user should manually submit
            showStatusMessage('Please go to GitHub to submit this issue', 'info', 10000);
            
            // We'll mark as failed to let the user try again
            return false;
        }
        
        // If the window opened, we assume the user can submit it
        showStatusMessage('Issue opened in GitHub - please complete submission there', 'success', 10000);
        return true;
    } catch (error) {
        console.error('Error submitting to GitHub:', error);
        showStatusMessage('Failed to connect to GitHub. Issue saved for later.', 'error', 5000);
        return false;
    }
}

// Update the issue count badge
async function updateIssueCountBadge() {
    const issues = await getStoredIssues();
    const pendingCount = issues.filter(issue => issue.status === IssueStatus.PENDING).length;
    
    const badge = document.getElementById('offline-issues-badge');
    if (badge) {
        if (pendingCount > 0) {
            badge.textContent = pendingCount;
            badge.style.display = 'inline-block';
        } else {
            badge.style.display = 'none';
        }
    }
}

// Open the issue reporting modal
function openIssueModal() {
    const modal = document.getElementById('issue-modal');
    if (modal) {
        modal.style.display = 'block';
    }
}

// Close the issue reporting modal
function closeIssueModal() {
    const modal = document.getElementById('issue-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Show the issue management view
async function showIssueManager() {
    const issues = await getStoredIssues();
    const container = document.getElementById('issue-list');
    
    if (!container) return;
    
    container.innerHTML = '';
    
    if (issues.length === 0) {
        container.innerHTML = '<p class="no-issues">No issues in queue</p>';
        return;
    }
    
    issues.forEach(issue => {
        const item = document.createElement('div');
        item.className = `issue-item issue-${issue.status}`;
        
        let statusText = 'Pending';
        if (issue.status === IssueStatus.SUBMITTED) {
            statusText = 'Submitted';
        } else if (issue.status === IssueStatus.FAILED) {
            statusText = 'Failed';
        }
        
        const date = new Date(issue.timestamp).toLocaleString();
        
        item.innerHTML = `
            <div class="issue-header">
                <div class="issue-title">${issue.title}</div>
                <span class="issue-status">${statusText}</span>
            </div>
            <div class="issue-meta">
                <span class="issue-date">${date}</span>
                <span class="issue-type">${issue.type}</span>
            </div>
            <div class="issue-description">${issue.description}</div>
            <div class="issue-actions">
                ${issue.status === IssueStatus.PENDING || issue.status === IssueStatus.FAILED ? 
                    `<button class="button button-sm retry-issue" data-id="${issue.id}">Retry</button>` : ''}
                <button class="button button-sm button-danger delete-issue" data-id="${issue.id}">Delete</button>
            </div>
        `;
        
        container.appendChild(item);
    });
    
    // Add event listeners for retry and delete buttons
    document.querySelectorAll('.retry-issue').forEach(button => {
        button.addEventListener('click', e => {
            const id = e.target.getAttribute('data-id');
            retryIssue(id);
        });
    });
    
    document.querySelectorAll('.delete-issue').forEach(button => {
        button.addEventListener('click', e => {
            const id = e.target.getAttribute('data-id');
            deleteIssue(id);
        });
    });
}

// Retry submitting an issue
async function retryIssue(id) {
    await updateIssueStatus(id, IssueStatus.PENDING, 0);
    
    await showIssueManager();
    
    if (isOnline()) {
        await submitPendingIssues();
        await showIssueManager();
    }
}

// Delete an issue from the queue
async function deleteIssue(id) {
    await deleteIssueFromStorage(id);
    
    await showIssueManager();
    await updateIssueCountBadge();
}

// Submit a new issue
async function submitNewIssue() {
    const titleInput = document.getElementById('issue-title');
    const descriptionInput = document.getElementById('issue-description');
    const typeSelect = document.getElementById('issue-type');
    
    if (!titleInput || !descriptionInput || !typeSelect) return;
    
    const title = titleInput.value.trim();
    const description = descriptionInput.value.trim();
    const type = typeSelect.value;
    
    if (!title) {
        showStatusMessage('Please enter an issue title', 'error');
        return;
    }
    
    if (!description) {
        showStatusMessage('Please enter an issue description', 'error');
        return;
    }
    
    // Queue the issue
    await queueIssue(title, description, type);
    
    // Clear the form
    titleInput.value = '';
    descriptionInput.value = '';
    
    // Show success message
    showStatusMessage('Issue saved successfully', 'success');
    
    // Update badge and view
    await updateIssueCountBadge();
    await showIssueManager();
    
    // Try to submit if online
    if (isOnline()) {
        await submitPendingIssues();
    }
}

// Switch between report and manage views
function switchIssueView(view) {
    const reportView = document.getElementById('issue-report-view');
    const manageView = document.getElementById('issue-manage-view');
    
    if (!reportView || !manageView) return;
    
    if (view === 'report') {
        reportView.style.display = 'block';
        manageView.style.display = 'none';
        
        // Reset active tab
        document.querySelectorAll('.issue-tab').forEach(tab => {
            tab.classList.remove('active');
        });
        document.getElementById('report-tab').classList.add('active');
    } else {
        reportView.style.display = 'none';
        manageView.style.display = 'block';
        
        // Reset active tab
        document.querySelectorAll('.issue-tab').forEach(tab => {
            tab.classList.remove('active');
        });
        document.getElementById('manage-tab').classList.add('active');
        
        // Refresh issue list
        showIssueManager();
    }
}

// Initialize the offline issue system
async function initOfflineIssueSystem() {
    // Check for online status changes
    window.addEventListener('online', async () => {
        console.log('Device is now online. Attempting to sync issues...');
        await syncOfflineIssues();
        await submitPendingIssues();
        await updateIssueCountBadge();
        
        if (document.getElementById('issue-manage-view').style.display !== 'none') {
            await showIssueManager();
        }
        
        showStatusMessage('Connected to network. Issues synced.', 'success');
    });
    
    // Set up the issue reporting button
    const reportButton = document.getElementById('report-issue-btn');
    if (reportButton) {
        reportButton.addEventListener('click', openIssueModal);
    }
    
    // Set up modal close button
    const closeButton = document.getElementById('close-issue-modal');
    if (closeButton) {
        closeButton.addEventListener('click', closeIssueModal);
    }
    
    // Set up submit button
    const submitButton = document.getElementById('submit-issue');
    if (submitButton) {
        submitButton.addEventListener('click', submitNewIssue);
    }
    
    // Set up tab switching
    document.querySelectorAll('.issue-tab').forEach(tab => {
        tab.addEventListener('click', e => {
            e.preventDefault();
            const view = e.target.getAttribute('data-view');
            switchIssueView(view);
        });
    });
    
    // Sync offline issues on load
    await syncOfflineIssues();
    
    // Initial badge update
    await updateIssueCountBadge();
    
    // Try to submit any pending issues
    if (isOnline()) {
        await submitPendingIssues();
    }
}

// Initialize when the DOM is loaded
document.addEventListener('DOMContentLoaded', initOfflineIssueSystem); 