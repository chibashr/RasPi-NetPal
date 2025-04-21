// Network Tools Page JavaScript

// Check if jQuery is available
if (typeof jQuery === 'undefined') {
    console.error('jQuery is not loaded! The tools page requires jQuery to function properly.');
    // Add a visible error message to the page
    document.addEventListener('DOMContentLoaded', function() {
        var errorDiv = document.createElement('div');
        errorDiv.style.background = '#f8d7da';
        errorDiv.style.color = '#721c24';
        errorDiv.style.padding = '15px';
        errorDiv.style.margin = '15px 0';
        errorDiv.style.borderRadius = '4px';
        errorDiv.innerHTML = '<strong>Error:</strong> jQuery is not loaded. The tools page requires jQuery to function properly.';
        
        // Insert at the beginning of the container
        var container = document.querySelector('.container');
        if (container) {
            container.insertBefore(errorDiv, container.firstChild);
        } else {
            document.body.insertBefore(errorDiv, document.body.firstChild);
        }
    });
} else {
    // Check if the page has already been initialized by the inline script
    $(document).ready(function() {
        // Only initialize if not already done
        if (typeof window.toolsPageInitialized === 'undefined') {
            console.log('Initializing tools page from tools.js');
            window.toolsPageInitialized = true;
            
            // Store active requests to allow cancellation
            window.activeRequests = {};
            
            // Tab functionality - Fixed to properly hide all panes and show only the selected one
            $('#tools-tab .nav-link').on('click', function(e) {
                e.preventDefault();
                
                // Get the href value
                const href = $(this).attr('href');
                
                // Only process tab links (those with hash)
                if (!href || !href.startsWith('#')) {
                    return;
                }
                
                // Update active tab within this tab group only
                $('#tools-tab .nav-link').removeClass('active').attr('aria-selected', 'false');
                $(this).addClass('active').attr('aria-selected', 'true');
                
                // Get target ID from href
                const targetId = href.substring(1);
                
                // Hide all tab panes in the tools tab content
                $('#tools-tab-content > .tab-pane').removeClass('show active');
                $('#tools-tab-content > .tab-pane').css('display', 'none');
                
                // Then show only the selected tab pane
                $('#tools-tab-content > #' + targetId).addClass('show active');
                $('#tools-tab-content > #' + targetId).css('display', 'block');
            });
            
            // Check if Bootstrap's tab plugin is available and use it if present
            if (typeof bootstrap !== 'undefined' && bootstrap.Tab) {
                // Bootstrap's tab plugin will handle the tab functionality
                document.querySelectorAll('[data-bs-toggle="tab"]').forEach(tabEl => {
                    new bootstrap.Tab(tabEl);
                });
            }
            
            // Populate network interfaces dropdown
            function loadInterfaces() {
                $.ajax({
                    url: '/tools/get_interfaces',
                    type: 'GET',
                    success: function(data) {
                        if (data && data.length > 0) {
                            const interfaceSelects = [
                                '#ping-interface', 
                                '#traceroute-interface', 
                                '#dns-interface', 
                                '#mtr-interface', 
                                '#iperf-interface', 
                                '#nmap-interface', 
                                '#http-interface'
                            ];
                            
                            interfaceSelects.forEach(function(selector) {
                                const select = $(selector);
                                select.empty();
                                select.append('<option value="">-- Select Interface --</option>');
                                
                                data.forEach(function(iface) {
                                    if (iface.name && iface.addr !== 'N/A') {
                                        select.append(`<option value="${iface.name}">${iface.name} (${iface.addr})</option>`);
                                    }
                                });
                            });
                        }
                    },
                    error: function(xhr, status, error) {
                        console.error('Error loading interfaces:', error);
                    }
                });
            }
            
            // Load interfaces on page load
            loadInterfaces();
            
            // Clear results button handler
            $('.btn-clear-output').on('click', function() {
                const resultContainer = $(this).closest('.card-body').find('.tool-results');
                resultContainer.text('Results will appear here...');
            });
            
            // Copy results button handler
            $('.btn-secondary[id$="-copy"]').on('click', function() {
                const toolId = $(this).attr('id').replace('-copy', '');
                const text = $(`#${toolId}-results`).text();
                
                navigator.clipboard.writeText(text).then(function() {
                    const btn = $(`#${toolId}-copy`);
                    btn.text('Copied!');
                    setTimeout(function() {
                        btn.text('Copy Results');
                    }, 2000);
                });
            });
            
            // Generic form handling function
            function handleToolForm(formId, resultId, endpoint, streamEndpoint) {
                const form = $(`#${formId}`);
                const resultContainer = $(`#${resultId}`);
                const stopButton = $(`#${formId.replace('-form', '')}-stop`);
                
                form.on('submit', function(e) {
                    e.preventDefault();
                    
                    // Get the tool ID from the form ID
                    const toolId = formId.replace('-form', '');
                    
                    // Clear previous results
                    resultContainer.text('Running...');
                    
                    // Enable stop button
                    stopButton.prop('disabled', false);
                    
                    // Check if streaming is enabled
                    const streamMode = $(`#${toolId}-stream-toggle`).is(':checked');
                    
                    if (streamMode) {
                        // Create a fetch request for streaming
                        const formData = new FormData(form[0]);
                        const controller = new AbortController();
                        const signal = controller.signal;
                        
                        // Store the controller for potential cancellation
                        window.activeRequests[toolId] = controller;
                        
                        fetch(`/tools/${streamEndpoint}`, {
                            method: 'POST',
                            body: formData,
                            signal: signal
                        })
                        .then(response => {
                            if (!response.ok) {
                                throw new Error(`HTTP error! Status: ${response.status}`);
                            }
                            
                            // Create a reader to read the stream
                            const reader = response.body.getReader();
                            const decoder = new TextDecoder();
                            let output = '';
                            
                            // Function to process stream chunks
                            function processStream() {
                                return reader.read().then(({ done, value }) => {
                                    if (done) {
                                        // We're done, clean up
                                        delete window.activeRequests[toolId];
                                        stopButton.prop('disabled', true);
                                        return;
                                    }
                                    
                                    // Decode the chunk and add to output
                                    const chunk = decoder.decode(value, { stream: true });
                                    output += chunk;
                                    resultContainer.text(output);
                                    resultContainer.scrollTop(resultContainer[0].scrollHeight);
                                    
                                    // Continue reading
                                    return processStream();
                                });
                            }
                            
                            return processStream();
                        })
                        .catch(error => {
                            if (error.name === 'AbortError') {
                                resultContainer.append('\n\nOperation stopped by user.');
                            } else {
                                resultContainer.text(`Error: ${error.message}`);
                            }
                            delete window.activeRequests[toolId];
                            stopButton.prop('disabled', true);
                        });
                    } else {
                        // Regular mode using AJAX
                        $.ajax({
                            url: `/tools/${endpoint}`,
                            method: 'POST',
                            data: form.serialize(),
                            beforeSend: function(xhr) {
                                window.activeRequests[toolId] = xhr;
                            },
                            success: function(response) {
                                if (response.success) {
                                    let output = `Command: ${response.command}\n\n${response.output}`;
                                    
                                    // Add additional info for specific tools
                                    if (endpoint === 'ping' && response.packet_loss !== undefined) {
                                        output += `\n\nPacket Loss: ${response.packet_loss}%`;
                                        if (response.rtt_stats && response.rtt_stats.min !== undefined) {
                                            output += `\n\nRTT Statistics:`;
                                            output += `\n  Min: ${response.rtt_stats.min.toFixed(2)} ms`;
                                            output += `\n  Avg: ${response.rtt_stats.avg.toFixed(2)} ms`;
                                            output += `\n  Max: ${response.rtt_stats.max.toFixed(2)} ms`;
                                            output += `\n  Std Dev: ${response.rtt_stats.mdev.toFixed(2)} ms`;
                                        }
                                    } else if (endpoint === 'dns' && response.records) {
                                        output += `\n\nRecords Found: ${response.count}`;
                                        if (response.records.length > 0) {
                                            output += `\n\nDNS Records:\n  ${response.records.join('\n  ')}`;
                                        }
                                    } else if (endpoint === 'traceroute' && response.hops) {
                                        output += `\n\nTrace completed with ${response.hops.length} hops`;
                                    } else if (endpoint === 'iperf' && response.summary) {
                                        if (response.summary.bits_per_second) {
                                            output += `\n\nBandwidth: ${(response.summary.bits_per_second / 1000000).toFixed(2)} Mbps`;
                                        }
                                        if (response.summary.jitter_ms) {
                                            output += `\nJitter: ${response.summary.jitter_ms.toFixed(2)} ms`;
                                        }
                                        if (response.summary.lost_packets) {
                                            output += `\nLost Packets: ${response.summary.lost_packets}`;
                                        }
                                    } else if (endpoint === 'mtr' && response.hops) {
                                        output += `\n\nMTR completed with ${response.hops.length} hops`;
                                    } else if (endpoint === 'nmap' && response.hosts) {
                                        output += `\n\nHosts scanned: ${response.hosts.length}`;
                                    } else if (endpoint === 'http' && response.metrics) {
                                        output += `\n\nStatus Code: ${response.metrics.status_code}`;
                                        output += `\nResponse Time: ${response.metrics.time_seconds.toFixed(3)} seconds`;
                                        output += `\nResponse Size: ${response.metrics.size_bytes} bytes`;
                                        output += `\nRedirects: ${response.metrics.redirects}`;
                                        if (response.metrics.final_url) {
                                            output += `\nFinal URL: ${response.metrics.final_url}`;
                                        }
                                    }
                                    
                                    resultContainer.text(output);
                                } else {
                                    resultContainer.text(`Error: ${response.error || 'Unknown error'}\n\n${response.output || ''}`);
                                }
                            },
                            error: function(xhr, status, error) {
                                resultContainer.text('Error: ' + error);
                            },
                            complete: function() {
                                // Clean up and disable stop button
                                delete window.activeRequests[toolId];
                                stopButton.prop('disabled', true);
                            }
                        });
                    }
                });
                
                // Set up stop button handler
                stopButton.on('click', function() {
                    const toolId = formId.replace('-form', '');
                    if (window.activeRequests[toolId]) {
                        try {
                            // Check if it's an XHR or AbortController
                            if (window.activeRequests[toolId].abort) {
                                window.activeRequests[toolId].abort();
                            } else if (window.activeRequests[toolId].signal) {
                                window.activeRequests[toolId].abort();
                            }
                        } catch (e) {
                            console.error('Error aborting request:', e);
                        }
                        delete window.activeRequests[toolId];
                        resultContainer.append('\n\nOperation stopped by user.');
                        stopButton.prop('disabled', true);
                    }
                });
            }
            
            // Initialize form handlers for each tool
            handleToolForm('ping-form', 'ping-results', 'ping', 'ping_stream');
            handleToolForm('traceroute-form', 'traceroute-results', 'traceroute', 'traceroute_stream');
            handleToolForm('dns-form', 'dns-results', 'dns', 'dns_stream');
            handleToolForm('mtr-form', 'mtr-results', 'mtr', 'mtr_stream');
            handleToolForm('iperf-form', 'iperf-results', 'iperf', 'iperf_stream');
            handleToolForm('nmap-form', 'nmap-results', 'nmap', 'nmap_stream');
            handleToolForm('http-form', 'http-results', 'http', 'http_stream');
        }
    });
}