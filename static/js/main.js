// Keep track of any pending operations
let pendingOperations = {
    interfaceUpdates: false,
    serviceRestarts: {}
};

// Dark mode functionality
function toggleDarkMode() {
    document.body.classList.toggle('dark-mode');
    
    // Store preference
    const isDarkMode = document.body.classList.contains('dark-mode');
    localStorage.setItem('darkMode', isDarkMode ? 'enabled' : 'disabled');
    
    // Update icon
    const toggleButton = document.getElementById('dark-mode-toggle');
    toggleButton.textContent = isDarkMode ? '☀️' : '🌙';
}

// Check for stored preference
function checkDarkModePreference() {
    if (localStorage.getItem('darkMode') === 'enabled') {
        document.body.classList.add('dark-mode');
        document.getElementById('dark-mode-toggle').textContent = '☀️';
    }
}

function toggleDetails(id) {
    const element = document.getElementById(id);
    if (element.classList.contains('hidden')) {
        element.classList.remove('hidden');
    } else {
        element.classList.add('hidden');
    }
}

function toggleSection(id) {
    const section = document.getElementById(id);
    const button = document.querySelector(`[data-target="${id}"]`);
    
    if (section.classList.contains('hidden')) {
        section.classList.remove('hidden');
        button.textContent = 'Hide';
    } else {
        section.classList.add('hidden');
        button.textContent = 'Show';
    }
}

function toggleStaticFields() {
    const mode = document.getElementById('static').value;
    const staticFields = document.getElementById('static-fields');
    const dhcpFields = document.getElementById('dhcp-fields');
    const modeDescription = document.getElementById('mode-description');
    
    if (mode === 'yes') {
        staticFields.style.display = 'block';
        dhcpFields.style.display = 'none';
        modeDescription.textContent = 'Manual configuration with fixed IP address';
    } else {
        staticFields.style.display = 'none';
        dhcpFields.style.display = 'block';
        modeDescription.textContent = 'Automatic IP configuration via DHCP server';
        
        // Load current DHCP info for the interface
        const iface = document.getElementById('iface-name').value;
        updateDhcpInfo(iface);
    }
}

function updateDhcpInfo(iface) {
    const dhcpInfoBox = document.getElementById('dhcp-current-info');
    dhcpInfoBox.innerHTML = '<p>Loading DHCP information...</p>';
    
    // Fetch current interface info
    fetch('/get_interface_config/' + iface)
        .then(response => response.json())
        .then(data => {
            // Get general interface info from the interfaces list
            fetch('/get_updates')
                .then(response => response.json())
                .then(updateData => {
                    const ifaceInfo = updateData.interfaces.find(i => i.name === iface);
                    if (ifaceInfo) {
                        let html = '<table class="dhcp-info-table">';
                        html += `<tr><td>Current IP:</td><td>${ifaceInfo.addr || 'Not assigned'}</td></tr>`;
                        html += `<tr><td>Gateway:</td><td>${ifaceInfo.gateway || 'Not assigned'}</td></tr>`;
                        
                        // Try to extract more info from details (like DNS servers)
                        let dnsServers = 'Unknown';
                        if (ifaceInfo.details) {
                            const dnsMatch = ifaceInfo.details.match(/domain\s+name\s+servers\s+([^\n]+)/i);
                            if (dnsMatch) {
                                dnsServers = dnsMatch[1].trim();
                            }
                        }
                        
                        html += `<tr><td>DNS Servers:</td><td>${dnsServers}</td></tr>`;
                        html += '</table>';
                        
                        dhcpInfoBox.innerHTML = html;
                    } else {
                        dhcpInfoBox.innerHTML = '<p>Could not retrieve interface information</p>';
                    }
                })
                .catch(error => {
                    dhcpInfoBox.innerHTML = '<p>Error loading interface data: ' + error.message + '</p>';
                });
        })
        .catch(error => {
            dhcpInfoBox.innerHTML = '<p>Error loading DHCP information: ' + error.message + '</p>';
        });
}

function renewDhcpFromForm() {
    const iface = document.getElementById('iface-name').value;
    
    if (confirm('Are you sure you want to release and renew DHCP for ' + iface + '?')) {
        // Show status message
        const statusBar = document.getElementById('status-message');
        statusBar.textContent = 'Renewing DHCP for ' + iface + '...';
        statusBar.className = 'status-bar info';
        statusBar.style.display = 'block';
        
        // Update button state
        const button = document.querySelector('button[onclick="renewDhcpFromForm()"]');
        const originalText = button.textContent;
        button.innerHTML = 'Renewing... <span class="loading"></span>';
        button.disabled = true;
        
        fetch('/renew_dhcp/' + iface, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            // Update status message
            statusBar.textContent = data.message;
            statusBar.className = 'status-bar ' + (data.success ? 'success' : 'error');
            
            // Reset button
            button.innerHTML = originalText;
            button.disabled = false;
            
            if (data.success) {
                // Update the interface table and DHCP info
                updateInterfaceTable(data.interfaces);
                updateDhcpInfo(iface);
            }
        })
        .catch(error => {
            statusBar.textContent = 'Error: ' + error.message;
            statusBar.className = 'status-bar error';
            button.innerHTML = originalText;
            button.disabled = false;
        });
    }
}

function showEditForm(iface) {
    // Check if the edit form exists in the DOM, if not, create it first
    const existingForm = document.getElementById('edit-form');
    if (!existingForm) {
        // Create the edit form dynamically if it doesn't exist
        createInterfaceEditForm();
    }
    
    document.getElementById('edit-title').textContent = 'Edit ' + iface + ' Settings';
    document.getElementById('iface-name').value = iface;
    document.getElementById('edit-form').classList.remove('hidden');
    
    // Show loading indicator
    const statusBar = document.getElementById('status-message');
    statusBar.textContent = 'Loading interface configuration...';
    statusBar.className = 'status-bar info';
    statusBar.style.display = 'block';
    
    // First try to get detailed info using our new endpoint
    fetch('/get_interface_details/' + iface)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Fill in form fields with data from detailed interface info
                document.getElementById('ip').value = data.details.ip !== 'Not assigned' ? data.details.ip : '';
                document.getElementById('netmask').value = data.details.netmask !== 'Unknown' ? data.details.netmask : '';
                document.getElementById('gateway').value = data.details.gateway !== 'Not configured' ? data.details.gateway : '';
                document.getElementById('dns').value = data.details.dns !== 'Not configured' ? data.details.dns : '';
                document.getElementById('static').value = !data.details.is_dhcp ? 'yes' : 'no';
                
                // Apply visibility based on the selected mode
                toggleStaticFields();
                
                // Hide status bar
                statusBar.style.display = 'none';
            } else {
                // Fallback to old method if detailed info retrieval fails
                fallbackInterfaceConfig(iface, statusBar);
            }
        })
        .catch(error => {
            console.error("Error fetching interface details:", error);
            fallbackInterfaceConfig(iface, statusBar);
        });
        
    // Scroll to the form
    document.getElementById('edit-form').scrollIntoView({behavior: 'smooth'});
}

// Fallback to old interface config method
function fallbackInterfaceConfig(iface, statusBar) {
    fetch('/get_interface_config/' + iface)
        .then(response => response.json())
        .then(data => {
            document.getElementById('ip').value = data.ip || '';
            document.getElementById('netmask').value = data.netmask || '';
            document.getElementById('gateway').value = data.gateway || '';
            document.getElementById('dns').value = data.dns || '';
            document.getElementById('static').value = data.static ? 'yes' : 'no';
            
            // Apply visibility based on the selected mode
            toggleStaticFields();
            
            // Hide status bar
            statusBar.style.display = 'none';
        })
        .catch(error => {
            statusBar.textContent = 'Error loading configuration: ' + error.message;
            statusBar.className = 'status-bar error';
        });
}

// Create the interface edit form if it doesn't exist
function createInterfaceEditForm() {
    const formHtml = `
        <div id="edit-form" class="card hidden">
            <h3 id="edit-title">Edit Interface Settings</h3>
            <form id="interface-form" onsubmit="return updateInterface()">
                <input type="hidden" id="iface-name" name="iface" value="">
                
                <div class="form-group">
                    <label for="static">Configuration Mode:</label>
                    <select id="static" name="static" onchange="toggleStaticFields()">
                        <option value="no">DHCP (Automatic)</option>
                        <option value="yes">Static IP (Manual)</option>
                    </select>
                    <p class="form-help" id="mode-description">Automatic IP configuration via DHCP server</p>
                </div>
                
                <div id="static-fields" style="display: none;">
                    <div class="form-group">
                        <label for="ip">IP Address:</label>
                        <input type="text" id="ip" name="ip" placeholder="e.g. 192.168.1.100">
                    </div>
                    
                    <div class="form-group">
                        <label for="netmask">Subnet Mask:</label>
                        <input type="text" id="netmask" name="netmask" placeholder="e.g. 255.255.255.0">
                    </div>
                    
                    <div class="form-group">
                        <label for="gateway">Default Gateway (Optional):</label>
                        <input type="text" id="gateway" name="gateway" placeholder="e.g. 192.168.1.1">
                    </div>
                    
                    <div class="form-group">
                        <label for="dns">DNS Servers (Optional):</label>
                        <input type="text" id="dns" name="dns" placeholder="e.g. 8.8.8.8 8.8.4.4">
                        <p class="form-help">Separate multiple DNS servers with spaces</p>
                    </div>
                </div>
                
                <div id="dhcp-fields">
                    <div class="form-group">
                        <h4>Current DHCP Information</h4>
                        <div id="dhcp-current-info">
                            <p>Loading current DHCP information...</p>
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <button type="button" class="button" onclick="renewDhcpFromForm()">Renew DHCP Lease</button>
                    </div>
                </div>
                
                <div class="form-actions">
                    <button type="submit" class="button button-primary">Apply Changes</button>
                    <button type="button" class="button" onclick="document.getElementById('edit-form').classList.add('hidden')">Cancel</button>
                </div>
            </form>
        </div>
    `;
    
    // Add the form to the page
    const container = document.getElementById('interfaces-container');
    if (container) {
        container.insertAdjacentHTML('afterend', formHtml);
    } else {
        // Fallback: Add to the body if container not found
        document.body.insertAdjacentHTML('beforeend', formHtml);
    }
    
    // Add status message element if not exists
    if (!document.getElementById('status-message')) {
        const statusBar = document.createElement('div');
        statusBar.id = 'status-message';
        statusBar.className = 'status-bar';
        statusBar.style.display = 'none';
        document.body.appendChild(statusBar);
    }
}

function updateInterface() {
    const formData = new FormData(document.getElementById('interface-form'));
    const iface = formData.get('iface');
    
    // Show loading indicator on button
    const submitButton = document.querySelector('#interface-form .button');
    const originalText = submitButton.textContent;
    submitButton.innerHTML = 'Applying Changes... <span class="loading"></span>';
    submitButton.disabled = true;
    
    // Set pending operation
    pendingOperations.interfaceUpdates = true;
    updatePendingStatus();
    
    // Show status message
    const statusBar = document.getElementById('status-message');
    statusBar.textContent = 'Applying network changes...';
    statusBar.className = 'status-bar info';
    statusBar.style.display = 'block';
    
    fetch('/update_interface', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        // Update status message
        statusBar.textContent = data.message;
        statusBar.className = 'status-bar ' + (data.success ? 'success' : 'error');
        
        // Reset button
        submitButton.innerHTML = originalText;
        submitButton.disabled = false;
        
        if (data.success) {
            // Update the interface table with new data
            updateInterfaceTable(data.interfaces);
            
            // Wait a bit then clear pending operation
            setTimeout(() => {
                pendingOperations.interfaceUpdates = false;
                updatePendingStatus();
            }, 5000);
        } else {
            pendingOperations.interfaceUpdates = false;
            updatePendingStatus();
        }
    })
    .catch(error => {
        statusBar.textContent = 'Error: ' + error.message;
        statusBar.className = 'status-bar error';
        submitButton.innerHTML = originalText;
        submitButton.disabled = false;
        pendingOperations.interfaceUpdates = false;
        updatePendingStatus();
    });
    
    return false; // Prevent default form submission
}

function restartService(service) {
    if (confirm('Are you sure you want to restart ' + service + '?')) {
        // Show loading indicator
        const button = document.querySelector(`button[onclick="restartService('${service}')"]`);
        const originalText = button.textContent;
        button.innerHTML = 'Restarting... <span class="loading"></span>';
        button.disabled = true;
        
        // Set pending operation
        pendingOperations.serviceRestarts[service] = true;
        updatePendingStatus();
        
        // Show status message
        const statusBar = document.getElementById('status-message');
        statusBar.textContent = 'Restarting ' + service + '...';
        statusBar.className = 'status-bar info';
        statusBar.style.display = 'block';
        
        fetch('/restart_service/' + service, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            statusBar.textContent = data.message;
            statusBar.className = 'status-bar ' + (data.success ? 'success' : 'error');
            
            // Reset button
            button.innerHTML = originalText;
            button.disabled = false;
            
            if (data.success) {
                // Update services table with new data
                updateServicesTable(data.services);
                
                // Wait a bit then clear pending operation
                setTimeout(() => {
                    pendingOperations.serviceRestarts[service] = false;
                    updatePendingStatus();
                }, 5000);
            } else {
                pendingOperations.serviceRestarts[service] = false;
                updatePendingStatus();
            }
        })
        .catch(error => {
            statusBar.textContent = 'Error: ' + error.message;
            statusBar.className = 'status-bar error';
            button.innerHTML = originalText;
            button.disabled = false;
            pendingOperations.serviceRestarts[service] = false;
            updatePendingStatus();
        });
    }
}

// Function to update interface table with new data
function updateInterfaceTable(interfaces) {
    console.log("Updating interfaces with:", interfaces);
    
    // First check if we're on the network page with a dedicated table
    const networkTable = document.querySelector('#network-table tbody');
    if (networkTable) {
        // This is the network page with a full table
        // ... existing network table update code ...
    } else {
        // This is the dashboard page, update the interfaces container
        const interfacesContainer = document.getElementById('interfaces-container');
        if (!interfacesContainer) {
            console.error("interfaces-container element not found");
            return;
        }
        
        if (!interfaces || interfaces.length === 0) {
            interfacesContainer.innerHTML = '<p class="no-data">No network interfaces detected</p>';
            return;
        }
        
        // Build a simple table for the dashboard
        let html = '<table class="network-table"><thead><tr><th>Interface</th><th>IP Address</th><th>Status</th><th>Internet</th><th>Actions</th></tr></thead><tbody>';
        
        interfaces.forEach(iface => {
            // Skip loopback interface for actions
            const showActions = iface.name !== 'lo';
            
            // Create main row for interface
            html += `<tr>
                <td>${iface.name}${iface.type === 'usb' ? ' <span class="badge badge-info">USB</span>' : ''}</td>
                <td>${iface.addr || 'Not assigned'}</td>
                <td>${iface.state === 'UP' 
                    ? '<span class="badge badge-success">UP</span>' 
                    : '<span class="badge badge-danger">DOWN</span>'}</td>
                <td>${iface.has_internet 
                    ? '<span class="badge badge-success" title="This interface has internet connectivity">✓</span>' 
                    : '<span class="badge badge-warning" title="No internet connection detected">✗</span>'}</td>
                <td>`;
            
            // Add action buttons if not loopback
            if (showActions) {
                html += `<div class="btn-group">`;
                
                // View button for all interfaces
                html += `<button class="button button-sm" onclick="viewInterface('${iface.name}')">View</button>`;
                
                // Edit button always shown
                html += `<button class="button button-sm" onclick="showEditForm('${iface.name}')">Edit</button>`;
                
                // Cycle interface (not for wlan0)
                if (iface.name !== 'wlan0') {
                    html += `<button class="button button-sm" onclick="cycleInterface('${iface.name}')">Cycle</button>`;
                }
                
                // Renew DHCP (for Ethernet)
                if (iface.name.startsWith('eth') || (iface.name !== 'wlan0' && iface.name !== 'lo')) {
                    html += `<button class="button button-sm" onclick="renewDhcp('${iface.name}')">Renew DHCP</button>`;
                }
                
                html += `</div>`;
            } else {
                html += `-`;
            }
            
            html += `</td></tr>`;
            
            // Add hidden details row that can be shown with the View button
            html += `<tr id="details-${iface.name}" class="hidden">
                <td colspan="5" class="interface-details">
                    <div class="loading"><span class="loading-spinner"></span> Loading interface details...</div>
                </td>
            </tr>`;
        });
        
        html += '</tbody></table>';
        interfacesContainer.innerHTML = html;
    }
}

// View interface details
function viewInterface(iface) {
    const detailsRow = document.getElementById(`details-${iface}`);
    if (!detailsRow) {
        console.error(`Details row for interface ${iface} not found`);
        return;
    }
    
    // Toggle visibility
    const isHidden = detailsRow.classList.contains('hidden');
    if (isHidden) {
        detailsRow.classList.remove('hidden');
        
        // Load detailed information about the interface
        fetch(`/get_interface_details/${iface}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Build a detailed view
                    let detailsHtml = '<div class="interface-details-container">';
                    
                    // Basic info section
                    detailsHtml += '<div class="details-section"><h4>Basic Information</h4>';
                    detailsHtml += `<p><strong>Name:</strong> ${data.details.name || iface}</p>`;
                    detailsHtml += `<p><strong>MAC Address:</strong> ${data.details.mac_address || 'N/A'}</p>`;
                    detailsHtml += `<p><strong>IP Address:</strong> ${data.details.ip || 'Not assigned'}</p>`;
                    detailsHtml += `<p><strong>Netmask:</strong> ${data.details.netmask || 'N/A'}</p>`;
                    detailsHtml += `<p><strong>Gateway:</strong> ${data.details.gateway || 'N/A'}</p>`;
                    detailsHtml += `<p><strong>DNS Servers:</strong> ${data.details.dns || 'N/A'}</p>`;
                    detailsHtml += `<p><strong>MTU:</strong> ${data.details.mtu || 'Default'}</p>`;
                    
                    // Add internet connectivity status
                    // Find the interface in the global interfaces list
                    let internetStatus = "Unknown";
                    if (latestInterfaceData) {
                        const ifaceData = latestInterfaceData.find(i => i.name === iface);
                        if (ifaceData) {
                            internetStatus = ifaceData.has_internet ? 
                                '<span class="badge badge-success">Available</span>' : 
                                '<span class="badge badge-warning">Not available</span>';
                        }
                    }
                    detailsHtml += `<p><strong>Internet Connectivity:</strong> ${internetStatus}</p>`;
                    
                    detailsHtml += '</div>';
                    
                    // Network statistics section
                    if (data.details.stats) {
                        detailsHtml += '<div class="details-section"><h4>Statistics</h4>';
                        detailsHtml += `<p><strong>RX Packets:</strong> ${data.details.stats.rx_packets || '0'}</p>`;
                        detailsHtml += `<p><strong>TX Packets:</strong> ${data.details.stats.tx_packets || '0'}</p>`;
                        detailsHtml += `<p><strong>RX Bytes:</strong> ${data.details.stats.rx_bytes || '0'}</p>`;
                        detailsHtml += `<p><strong>TX Bytes:</strong> ${data.details.stats.tx_bytes || '0'}</p>`;
                        detailsHtml += `<p><strong>Errors:</strong> ${data.details.stats.errors || '0'}</p>`;
                        detailsHtml += '</div>';
                    }
                    
                    // Raw output section if available
                    if (data.details.raw_info) {
                        detailsHtml += '<div class="details-section"><h4>Raw Interface Information</h4>';
                        detailsHtml += `<pre>${data.details.raw_info}</pre>`;
                        detailsHtml += '</div>';
                    }
                    
                    detailsHtml += '</div>';
                    detailsRow.querySelector('td').innerHTML = detailsHtml;
                } else {
                    detailsRow.querySelector('td').innerHTML = 
                        `<div class="error">Error loading interface details: ${data.message || 'Unknown error'}</div>`;
                }
            })
            .catch(error => {
                detailsRow.querySelector('td').innerHTML = 
                    `<div class="error">Error: ${error.message}</div>`;
            });
    } else {
        detailsRow.classList.add('hidden');
    }
}

// Function to update services table with new data
function updateServicesTable(services) {
    console.log("Updating services with:", services);
    
    // First check if we're on the services page with a dedicated table
    const servicesPageTable = document.querySelector('#services-table tbody');
    if (servicesPageTable) {
        // ... existing services page update code ...
    } else {
        // This is the dashboard - find the services table body in the dashboard
        const servicesTableBody = document.getElementById('services-table-body');
        if (!servicesTableBody) {
            console.error("services-table-body element not found");
            return;
        }
        
        // Clear the table body
        servicesTableBody.innerHTML = '';
        
        if (!services || services.length === 0) {
            servicesTableBody.innerHTML = '<tr><td colspan="3" class="text-center">No services detected</td></tr>';
            return;
        }
        
        // Only show top 10 services initially
        const visibleServices = services.slice(0, 10);
        const hiddenServices = services.length > 10 ? services.slice(10) : [];
        
        // Add service rows for visible services
        visibleServices.forEach(svc => {
            addServiceRow(svc, servicesTableBody);
        });
        
        // Add a "Show More" button if there are hidden services
        if (hiddenServices.length > 0) {
            const showMoreRow = document.createElement('tr');
            showMoreRow.id = 'show-more-services-row';
            showMoreRow.innerHTML = `
                <td colspan="3" class="text-center">
                    <button id="show-more-services" class="button button-sm">
                        Show ${hiddenServices.length} More Services
                    </button>
                </td>
            `;
            servicesTableBody.appendChild(showMoreRow);
            
            // Add a container for hidden services
            const hiddenServicesContainer = document.createElement('tbody');
            hiddenServicesContainer.id = 'hidden-services-container';
            hiddenServicesContainer.style.display = 'none';
            
            // Add hidden service rows
            hiddenServices.forEach(svc => {
                addServiceRow(svc, hiddenServicesContainer);
            });
            
            // Insert the hidden container after the services table body
            servicesTableBody.parentNode.insertBefore(hiddenServicesContainer, servicesTableBody.nextSibling);
            
            // Add event listener to show more button
            setTimeout(() => {
                const showMoreBtn = document.getElementById('show-more-services');
                if (showMoreBtn) {
                    showMoreBtn.addEventListener('click', function() {
                        const hiddenContainer = document.getElementById('hidden-services-container');
                        if (hiddenContainer) {
                            // Toggle visibility
                            const isHidden = hiddenContainer.style.display === 'none';
                            hiddenContainer.style.display = isHidden ? 'table-row-group' : 'none';
                            
                            // Update button text
                            this.textContent = isHidden ? 
                                `Hide ${hiddenServices.length} Services` : 
                                `Show ${hiddenServices.length} More Services`;
                        }
                    });
                }
            }, 100);
        }
    }
}

// Helper function to add a service row
function addServiceRow(svc, container) {
    const tr = document.createElement('tr');
    
    let statusBadge = '';
    if (svc.status === 'active') {
        statusBadge = '<span class="badge badge-success">Active</span>';
    } else if (svc.status === 'inactive') {
        statusBadge = '<span class="badge badge-danger">Inactive</span>';
    } else {
        statusBadge = `<span class="badge badge-warning">${svc.status}</span>`;
    }
    
    tr.innerHTML = `
        <td>${svc.name}</td>
        <td>${statusBadge}</td>
        <td class="action-buttons">
            <button class="button button-sm button-danger" onclick="restartService('${svc.name}')">
                Restart
            </button>
        </td>
    `;
    container.appendChild(tr);
}

// Update the log entries display
function updateLogEntries(logs) {
    const logSection = document.getElementById('log-entries');
    if (!logSection) return;
    
    logSection.innerHTML = '';
    
    if (logs.length === 0) {
        logSection.innerHTML = '<p>No log entries yet</p>';
        return;
    }
    
    logs.forEach(entry => {
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry ${entry.type}`;
        logEntry.innerHTML = `
            <span class="log-timestamp">${entry.timestamp}</span>
            ${entry.message}
        `;
        logSection.appendChild(logEntry);
    });
}

// Update indicator for pending operations
function updatePendingStatus() {
    const pendingStatusElement = document.getElementById('pending-operations');
    if (!pendingStatusElement) return;
    
    // Check if there are any pending operations
    const hasPendingInterface = pendingOperations.interfaceUpdates;
    const hasPendingServices = Object.values(pendingOperations.serviceRestarts).some(v => v);
    
    if (hasPendingInterface || hasPendingServices) {
        let message = 'Pending operations: ';
        if (hasPendingInterface) message += 'interface update, ';
        if (hasPendingServices) {
            const serviceNames = Object.keys(pendingOperations.serviceRestarts)
                .filter(name => pendingOperations.serviceRestarts[name])
                .join(', ');
            message += `services (${serviceNames})`;
        }
        pendingStatusElement.textContent = message;
        pendingStatusElement.style.display = 'block';
    } else {
        pendingStatusElement.style.display = 'none';
    }
}

// Handle viewport adjustments for mobile
function adjustForMobile() {
    const viewportWidth = window.innerWidth;
    const sections = document.querySelectorAll('section');
    
    // For very small screens, adjust certain elements
    if (viewportWidth < 480) {
        // Simplify some text labels to save space
        const detailSpans = document.querySelectorAll('.details');
        detailSpans.forEach(span => {
            if (span.textContent === 'Details') {
                span.textContent = '👁️';
            }
        });
    }
}

// Poll for updates
let lastUpdateTime = Date.now();
let openDetailSections = new Set(); // Track which detail sections are open

// Add this new function to update system info
function updateSystemInfo(systemInfo) {
    if (!systemInfo) {
        // Set default values if no data received
        document.getElementById('os-info').innerHTML = "No data";
        document.getElementById('uptime-info').innerHTML = "No data";
        document.getElementById('load-avg-info').innerHTML = "No data";
        document.getElementById('cpu-info').innerHTML = "No data";
        document.getElementById('memory-info').innerHTML = "No data";
        document.getElementById('temp-info').innerHTML = "No data";
        return;
    }
    
    // Update OS info
    if (systemInfo.os) {
        document.getElementById('os-info').innerHTML = systemInfo.os;
    } else {
        document.getElementById('os-info').innerHTML = "Unknown";
    }
    
    // Update uptime
    if (systemInfo.uptime) {
        document.getElementById('uptime-info').innerHTML = systemInfo.uptime;
    } else {
        document.getElementById('uptime-info').innerHTML = "Unknown";
    }
    
    // Update load average
    if (systemInfo.load_avg) {
        document.getElementById('load-avg-info').innerHTML = systemInfo.load_avg;
    } else {
        document.getElementById('load-avg-info').innerHTML = "Unknown";
    }
    
    // Update CPU info
    if (systemInfo.cpu) {
        document.getElementById('cpu-info').innerHTML = systemInfo.cpu;
    } else {
        document.getElementById('cpu-info').innerHTML = "Unknown";
    }
    
    // Update memory info
    if (systemInfo.memory) {
        document.getElementById('memory-info').innerHTML = systemInfo.memory;
    } else {
        document.getElementById('memory-info').innerHTML = "Unknown";
    }
    
    // Update temperature
    if (systemInfo.temperature) {
        document.getElementById('temp-info').innerHTML = systemInfo.temperature;
    } else {
        document.getElementById('temp-info').innerHTML = "N/A";
    }
}

// Update storage info
function updateStorageInfo() {
    fetch('/get_storage_info')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            const storageInfo = document.getElementById('storage-info');
            
            if (data.storage && data.storage.length > 0) {
                let html = '<table class="storage-table">';
                html += '<thead><tr><th>Device</th><th>Size</th><th>Used</th><th>Available</th><th>Use%</th><th>Mount</th></tr></thead><tbody>';
                
                data.storage.forEach(disk => {
                    html += `<tr>
                        <td>${disk.filesystem}</td>
                        <td>${disk.size}</td>
                        <td>${disk.used}</td>
                        <td>${disk.avail}</td>
                        <td>${disk.use}</td>
                        <td>${disk.mount}</td>
                    </tr>`;
                });
                
                html += '</tbody></table>';
                storageInfo.innerHTML = html;
            } else {
                storageInfo.innerHTML = '<p class="no-data">No storage information available</p>';
            }
        })
        .catch(error => {
            console.error('Error fetching storage info:', error);
            const storageInfo = document.getElementById('storage-info');
            storageInfo.innerHTML = '<p class="error">Could not load storage information</p>';
        });
}

// Function to update serial devices display
function updateSerialDevices(devices) {
    console.log("Updating serial devices with:", devices);
    
    const serialDevicesContainer = document.getElementById('serial-devices-container');
    if (!serialDevicesContainer) {
        console.error("serial-devices-container element not found");
        return;
    }
    
    if (!devices || devices.length === 0) {
        serialDevicesContainer.innerHTML = '<p class="no-data">No serial devices connected</p>';
        return;
    }
    
    // Build a table for the serial devices
    let html = '<table class="serial-table"><thead><tr><th>Device</th><th>Manufacturer</th><th>Product</th><th>Serial</th></tr></thead><tbody>';
    
    devices.forEach(device => {
        html += `<tr>
            <td>${device.path}</td>
            <td>${device.manufacturer}</td>
            <td>${device.product}</td>
            <td>${device.serial}</td>
        </tr>`;
    });
    
    html += '</tbody></table>';
    serialDevicesContainer.innerHTML = html;
}

// Add a global variable to store the latest interface data
let latestInterfaceData = null;

// Function to poll for updates from the server
function pollForUpdates() {
    // Save which detail sections are currently open
    const openDetailSections = [];
    document.querySelectorAll('tr[id^="details-"]:not(.hidden)').forEach(elem => {
        openDetailSections.push(elem.id);
    });
    
    // Update last refresh time tracking
    const lastUpdateTime = Date.now();
    
    fetch('/get_updates')
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log("Received update data:", data);  // Debug log
            
            // Update system information
            if (data.system_info) {
                updateSystemInfo(data.system_info);
            } else {
                console.warn("No system_info in response");
                // Set defaults for missing data
                updateSystemInfo(null);
            }
            
            // Update other information if available
            if (data.interfaces) {
                // Store interface data globally for use in other functions
                latestInterfaceData = data.interfaces;
                updateInterfaceTable(data.interfaces);
            } else {
                console.warn("No interfaces data in response");
            }
            
            // Update serial devices if available
            if (data.serial_devices) {
                updateSerialDevices(data.serial_devices);
            } else {
                console.warn("No serial_devices data in response");
            }
            
            if (data.services) {
                updateServicesTable(data.services);
            } else {
                console.warn("No services data in response");
            }
            
            if (data.logs) {
                updateLogEntries(data.logs);
            } else {
                console.warn("No logs data in response");
            }
            
            // Also try to update storage info
            updateStorageInfo();
            
            // Restore open details sections
            openDetailSections.forEach(id => {
                const element = document.getElementById(id);
                if (element) {
                    element.classList.remove('hidden');
                }
            });
            
            // Update last refresh time
            const now = Date.now();
            const lastUpdateElement = document.getElementById('last-update-time');
            if (lastUpdateElement) {
                const secondsAgo = Math.floor((now - lastUpdateTime) / 1000);
                lastUpdateElement.textContent = `Last update: ${secondsAgo} seconds ago`;
            }
        })
        .catch(error => {
            console.error('Error polling for updates:', error);
            
            // Set fallback values for system info
            updateSystemInfo(null);
            
            // Try to update storage info separately
            updateStorageInfo();
            
            // Show error in elements if they exist
            const errorElements = [
                { id: 'interfaces-container', message: 'Could not load network interfaces' },
                { id: 'serial-devices-container', message: 'Could not load serial devices' },
                { id: 'services-table-body', message: 'Could not load services' },
                { id: 'logs-container', message: 'Could not load system logs' }
            ];
            
            errorElements.forEach(elem => {
                const element = document.getElementById(elem.id);
                if (element) {
                    if (elem.id === 'services-table-body') {
                        element.innerHTML = `<tr><td colspan="3" class="text-center error">${elem.message}</td></tr>`;
                    } else {
                        element.innerHTML = `<div class="error">${elem.message}</div>`;
                    }
                }
            });
        });
}

// Add this new function to immediately show fallback data without waiting for API
function updateWithFallbackData() {
    console.log("Using fallback data");
    
    // Update system info with fallback values
    const fallbackSystemInfo = {
        os: "Raspberry Pi OS",
        uptime: "System online",
        load_avg: "N/A",
        cpu: "Normal",
        memory: "Available",
        temperature: "Normal"
    };
    updateSystemInfo(fallbackSystemInfo);
    
    // Update storage info with fallback
    const storageInfo = document.getElementById('storage-info');
    if (storageInfo) {
        storageInfo.innerHTML = '<table class="storage-table"><thead><tr><th>Device</th><th>Size</th><th>Used</th><th>Mount</th></tr></thead>' +
            '<tbody><tr><td>/dev/root</td><td>Available</td><td>In use</td><td>/</td></tr></tbody></table>';
    }
    
    // Update interfaces with fallback
    const interfacesContainer = document.getElementById('interfaces-container');
    if (interfacesContainer) {
        interfacesContainer.innerHTML = '<table class="network-table"><thead><tr><th>Interface</th><th>IP Address</th><th>Status</th><th>Internet</th><th>Actions</th></tr></thead>' +
            '<tbody><tr><td>eth0</td><td>Connected</td><td><span class="badge badge-success">UP</span></td>' +
            '<td><span class="badge badge-warning">Checking...</span></td>' +
            '<td><div class="btn-group">' +
            '<button class="button button-sm" onclick="showEditForm(\'eth0\')">Edit</button>' +
            '<button class="button button-sm" onclick="cycleInterface(\'eth0\')">Cycle</button>' +
            '<button class="button button-sm" onclick="renewDhcp(\'eth0\')">Renew DHCP</button>' +
            '</div></td></tr></tbody></table>';
    }
    
    // Update serial devices with fallback
    const serialDevicesContainer = document.getElementById('serial-devices-container');
    if (serialDevicesContainer) {
        serialDevicesContainer.innerHTML = '<p>Checking for connected devices...</p>';
    }
    
    // Update services with fallback
    const servicesTable = document.getElementById('services-table-body');
    if (servicesTable) {
        servicesTable.innerHTML = `<tr><td>System services</td><td><span class="badge badge-success">Running</span></td><td>-</td></tr>`;
    }
    
    // Update logs with fallback
    const logsContainer = document.getElementById('logs-container');
    if (logsContainer) {
        logsContainer.innerHTML = '<div class="log-entry info"><span class="log-timestamp">Now</span>System running normally</div>';
    }
}

// Initialize on page load
window.onload = function() {
    // Check for dark mode preference
    checkDarkModePreference();
    
    // Set up dark mode toggle - check if element exists first
    const darkModeToggle = document.getElementById('dark-mode-toggle');
    if (darkModeToggle) {
        darkModeToggle.addEventListener('click', toggleDarkMode);
    }
    
    // Initial updates
    updatePendingStatus();
    lastUpdateTime = Date.now();
    adjustForMobile();
    
    // Use fallback data immediately to show something
    updateWithFallbackData();
    
    // Then try to get real data
    pollForUpdates();
    
    // Set up auto-refresh interval (every 30 seconds)
    setInterval(pollForUpdates, 30000);
    
    // Set up refresh button
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            // Show loading indicator
            this.innerHTML = 'Refreshing... <span class="loading"></span>';
            this.disabled = true;
            
            pollForUpdates();
            
            // Reset button after a delay
            setTimeout(() => {
                this.textContent = 'Refresh';
                this.disabled = false;
            }, 1000);
        });
    }
    
    // Listen for window resize events
    window.addEventListener('resize', adjustForMobile);
};

// Add after showEditForm function
function renewDhcp(iface) {
    if (confirm('Are you sure you want to release and renew DHCP for ' + iface + '?')) {
        // Show loading indicator
        const button = document.querySelector(`button[onclick*="renewDhcp('${iface}')"]`);
        if (!button) {
            console.error(`Button for interface ${iface} not found`);
            return;
        }
        const originalText = button.textContent;
        button.innerHTML = 'Renewing<span class="loading"></span>';
        button.disabled = true;
        
        // Show status message
        const statusBar = document.getElementById('status-message');
        statusBar.textContent = 'Renewing DHCP for ' + iface + '...';
        statusBar.className = 'status-bar info';
        statusBar.style.display = 'block';
        
        fetch('/renew_dhcp/' + iface, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            // Update status message
            statusBar.textContent = data.message;
            statusBar.className = 'status-bar ' + (data.success ? 'success' : 'error');
            
            // Reset button
            button.innerHTML = originalText;
            button.disabled = false;
            
            if (data.success) {
                // Update the interface table with new data
                updateInterfaceTable(data.interfaces);
            }
        })
        .catch(error => {
            statusBar.textContent = 'Error: ' + error.message;
            statusBar.className = 'status-bar error';
            button.innerHTML = originalText;
            button.disabled = false;
        });
    }
}

// Packet capture functionality
let captureInterval = null;
let currentCaptureId = null;

function startCapture() {
    console.log("startCapture called");
    const form = document.getElementById('capture-form');
    const formData = new FormData(form);
    
    // Show loading indicator on button
    const startButton = document.getElementById('start-capture-btn');
    startButton.innerHTML = 'Starting... <span class="loading"></span>';
    startButton.disabled = true;
    
    // Clear capture output
    document.getElementById('capture-output').innerHTML = '<p class="no-data">Starting capture...</p>';
    
    fetch('/start_capture', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        console.log("Response data:", data);
        const statusBar = document.getElementById('capture-status');
        statusBar.textContent = data.message;
        statusBar.className = 'status-bar ' + (data.success ? 'success' : 'error');
        statusBar.style.display = 'block';
        
        if (data.success) {
            // Store the current capture ID
            currentCaptureId = data.capture_id;
            console.log("Capture started with ID:", currentCaptureId);
            
            // Show stop button, hide start button
            document.getElementById('start-capture-btn').style.display = 'none';
            document.getElementById('stop-capture-btn').style.display = 'inline-block';
            
            // Hide download button until capture is stopped
            document.getElementById('download-capture-btn').style.display = 'none';
            
            // Start polling for capture output
            if (captureInterval) {
                clearInterval(captureInterval);
            }
            captureInterval = setInterval(updateCaptureOutput, 1000);
            
            // Disable interface and filter inputs
            document.getElementById('capture-interface').disabled = true;
            document.getElementById('capture-filter').disabled = true;
            document.getElementById('capture-name').disabled = true;
        } else {
            startButton.innerHTML = 'Start Capture';
            startButton.disabled = false;
        }
    })
    .catch(error => {
        console.error("Error starting capture:", error);
        const statusBar = document.getElementById('capture-status');
        statusBar.textContent = 'Error: ' + error.message;
        statusBar.className = 'status-bar error';
        statusBar.style.display = 'block';
        
        startButton.innerHTML = 'Start Capture';
        startButton.disabled = false;
    });
    
    return false; // Prevent form submission
}

function stopCapture() {
    // Show loading indicator on button
    const stopButton = document.getElementById('stop-capture-btn');
    stopButton.innerHTML = 'Stopping... <span class="loading"></span>';
    stopButton.disabled = true;
    
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
        const statusBar = document.getElementById('capture-status');
        statusBar.textContent = data.message;
        statusBar.className = 'status-bar ' + (data.success ? 'success' : 'error');
        
        if (data.success) {
            // Show start button, hide stop button
            document.getElementById('start-capture-btn').style.display = 'inline-block';
            document.getElementById('start-capture-btn').innerHTML = 'Start Capture';
            document.getElementById('start-capture-btn').disabled = false;
            document.getElementById('stop-capture-btn').style.display = 'none';
            
            // Show download button
            document.getElementById('download-capture-btn').style.display = 'inline-block';
            
            // Stop polling for capture output
            if (captureInterval) {
                clearInterval(captureInterval);
                captureInterval = null;
            }
            
            // Enable interface and filter inputs
            document.getElementById('capture-interface').disabled = false;
            document.getElementById('capture-filter').disabled = false;
            document.getElementById('capture-name').disabled = false;
            
            // Reload the page after a short delay to show updated history
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        } else {
            stopButton.innerHTML = 'Stop Capture';
            stopButton.disabled = false;
        }
    })
    .catch(error => {
        const statusBar = document.getElementById('capture-status');
        statusBar.textContent = 'Error: ' + error.message;
        statusBar.className = 'status-bar error';
        
        stopButton.innerHTML = 'Stop Capture';
        stopButton.disabled = false;
    });
}

function updateCaptureOutput() {
    let url = '/get_capture_output';
    if (currentCaptureId) {
        url += '?id=' + encodeURIComponent(currentCaptureId);
    }
    
    fetch(url)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update the capture output display
                const outputElement = document.getElementById('capture-output');
                outputElement.innerHTML = '';
                
                if (data.output.length === 0) {
                    outputElement.innerHTML = '<p class="no-data">No packets captured yet...</p>';
                } else {
                    data.output.forEach(line => {
                        const lineElement = document.createElement('div');
                        lineElement.className = 'capture-line';
                        lineElement.textContent = line;
                        outputElement.appendChild(lineElement);
                    });
                    
                    // Auto-scroll to bottom
                    outputElement.scrollTop = outputElement.scrollHeight;
                }
                
                // If capture is no longer running, stop polling
                if (!data.capture_running && captureInterval) {
                    clearInterval(captureInterval);
                    captureInterval = null;
                    
                    // Show message that capture has stopped
                    const statusBar = document.getElementById('capture-status');
                    statusBar.textContent = 'Capture has completed.';
                    statusBar.className = 'status-bar success';
                    
                    // Show start button, reset UI
                    document.getElementById('start-capture-btn').style.display = 'inline-block';
                    document.getElementById('start-capture-btn').innerHTML = 'Start Capture';
                    document.getElementById('start-capture-btn').disabled = false;
                    document.getElementById('stop-capture-btn').style.display = 'none';
                    document.getElementById('download-capture-btn').style.display = 'inline-block';
                    
                    // Enable inputs
                    document.getElementById('capture-interface').disabled = false;
                    document.getElementById('capture-filter').disabled = false;
                    document.getElementById('capture-name').disabled = false;
                }
            }
        })
        .catch(error => {
            console.error('Error fetching capture output:', error);
        });
}

function downloadCapture(captureId) {
    if (captureId) {
        window.location.href = '/download_capture/' + captureId;
    } else if (currentCaptureId) {
        window.location.href = '/download_capture/' + currentCaptureId;
    } else {
        // Fallback to generic endpoint
        window.location.href = '/download_capture';
    }
}

function viewCapture(captureId) {
    // Show modal
    const modal = document.getElementById('view-capture-modal');
    modal.style.display = 'block';
    
    // Update title
    document.getElementById('modal-title').textContent = 'Loading Capture...';
    
    // Show loading indicator
    const viewContainer = document.getElementById('capture-view-container');
    viewContainer.innerHTML = '<p class="loading-text">Loading capture data...</p>';
    
    // Fetch capture content
    fetch('/view_capture/' + captureId)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update title
                document.getElementById('modal-title').textContent = 'Viewing: ' + data.name;
                
                // Clear container
                viewContainer.innerHTML = '';
                
                if (data.output.length === 0) {
                    viewContainer.innerHTML = '<p class="no-data">No packets in this capture</p>';
                } else {
                    // Create output lines
                    data.output.forEach(line => {
                        const lineElement = document.createElement('div');
                        lineElement.className = 'capture-line';
                        lineElement.textContent = line;
                        viewContainer.appendChild(lineElement);
                    });
                }
            } else {
                viewContainer.innerHTML = `<p class="no-data">Error: ${data.message}</p>`;
            }
        })
        .catch(error => {
            viewContainer.innerHTML = `<p class="no-data">Error loading capture: ${error.message}</p>`;
        });
}

function deleteCapture(captureId) {
    if (confirm('Are you sure you want to delete this capture? This cannot be undone.')) {
        fetch('/delete_capture/' + captureId, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            const statusBar = document.getElementById('capture-status');
            statusBar.textContent = data.message;
            statusBar.className = 'status-bar ' + (data.success ? 'success' : 'error');
            statusBar.style.display = 'block';
            
            if (data.success) {
                // Reload the page to show updated history
                setTimeout(() => {
                    window.location.reload();
                }, 1500);
            }
        })
        .catch(error => {
            const statusBar = document.getElementById('capture-status');
            statusBar.textContent = 'Error: ' + error.message;
            statusBar.className = 'status-bar error';
            statusBar.style.display = 'block';
        });
    }
}

function closeModal() {
    document.getElementById('view-capture-modal').style.display = 'none';
}

function cycleInterface(iface) {
    if (confirm(`Are you sure you want to cycle (turn off and on) the ${iface} interface?`)) {
        // Show loading indicator
        const button = document.querySelector(`button[onclick="cycleInterface('${iface}')"]`);
        const originalText = button.textContent;
        button.innerHTML = 'Cycling<span class="loading"></span>';
        button.disabled = true;
        
        // Show status message
        const statusBar = document.getElementById('status-message');
        statusBar.textContent = `Cycling interface ${iface}...`;
        statusBar.className = 'status-bar info';
        statusBar.style.display = 'block';
        
        fetch(`/cycle_interface/${iface}`, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            // Update status message
            statusBar.textContent = data.message;
            statusBar.className = 'status-bar ' + (data.success ? 'success' : 'error');
            
            // Reset button
            button.innerHTML = originalText;
            button.disabled = false;
            
            if (data.success) {
                // Update the interface table with new data
                updateInterfaceTable(data.interfaces);
            }
        })
        .catch(error => {
            statusBar.textContent = 'Error: ' + error.message;
            statusBar.className = 'status-bar error';
            button.innerHTML = originalText;
            button.disabled = false;
        });
    }
} 