# Routes module initialization
try:
    from routes import network, system, capture, tftp, tools, control, docs
except ImportError as e:
    print(f"Error importing route modules: {e}")
    # Import individual modules that do exist
    try:
        from routes import network
    except ImportError:
        pass
    try:
        from routes import system
    except ImportError:
        pass
    try:
        from routes import capture
    except ImportError:
        pass
    try:
        from routes import docs
    except ImportError:
        pass
    try:
        from routes import tftp
    except ImportError:
        pass
    try:
        from routes import tools
    except ImportError:
        pass
    try:
        from routes import control
    except ImportError:
        pass

from flask import Blueprint 