// Force NoVNC to use localhost regardless of URL parameters
document.addEventListener('DOMContentLoaded', function() {
    // Override WebUtil.getConfigVar to force localhost
    if (window.WebUtil && typeof window.WebUtil.getConfigVar === 'function') {
        const originalGetConfigVar = window.WebUtil.getConfigVar;
        window.WebUtil.getConfigVar = function(name, defVal) {
            // Check if we should force localhost
            const forceLocalhost = originalGetConfigVar('force_localhost', false);
            if (forceLocalhost === 'true') {
                if (name === 'host') {
                    console.log('Forcing VNC connection to localhost');
                    return 'localhost';
                }
                if (name === 'port') {
                    console.log('Forcing VNC connection to port 6080');
                    return '6080';
                }
                if (name === 'path') {
                    console.log('Using empty path for WebSocket');
                    return '';
                }
            }
            return originalGetConfigVar(name, defVal);
        };
    }
    
    // For vnc_lite.html which doesn't use WebUtil
    if (typeof readQueryVariable === 'function') {
        const originalReadQueryVariable = readQueryVariable;
        window.readQueryVariable = function(name, defaultValue) {
            // If we should force localhost
            const forceLocalhost = originalReadQueryVariable('force_localhost', false);
            if (forceLocalhost === 'true') {
                if (name === 'host') {
                    console.log('Forcing VNC connection to localhost');
                    return 'localhost';
                }
                if (name === 'port') {
                    console.log('Forcing VNC connection to port 6080');
                    return '6080';
                }
                if (name === 'path') {
                    console.log('Using empty path for WebSocket');
                    return '';
                }
            }
            return originalReadQueryVariable(name, defaultValue);
        };
    }
    
    console.log('VNC override script loaded');
}); 