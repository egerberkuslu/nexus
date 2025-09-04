#!/usr/bin/env python3
"""
Comprehensive eventlet patch for Python 3.10+ compatibility with Ryu/os-ken
Fixes both ALREADY_HANDLED and TimeoutError issues
"""

import os
import sys

def patch_eventlet_timeout():
    """Fix TimeoutError compatibility issue in eventlet"""
    eventlet_timeout_path = '/usr/local/lib/python3.10/dist-packages/eventlet/timeout.py'
    
    if not os.path.exists(eventlet_timeout_path):
        print(f"❌ eventlet timeout not found at {eventlet_timeout_path}")
        return False
    
    try:
        with open(eventlet_timeout_path, 'r') as f:
            content = f.read()
        
        # Check if already patched
        if 'PYTHON_310_COMPATIBILITY_PATCH' in content:
            print("✓ TimeoutError patch already applied")
            return True
        
        # Find the problematic line and replace it
        old_line = "    base.is_timeout = property(lambda _: True)"
        new_line = """    # PYTHON_310_COMPATIBILITY_PATCH: Fix for immutable TimeoutError
    try:
        base.is_timeout = property(lambda _: True)
    except (TypeError, AttributeError):
        # TimeoutError is immutable in Python 3.10+, skip the assignment
        pass"""
        
        if old_line in content:
            patched_content = content.replace(old_line, new_line)
            
            with open(eventlet_timeout_path, 'w') as f:
                f.write(patched_content)
            
            print("✓ Successfully patched eventlet timeout for Python 3.10+ compatibility")
            return True
        else:
            print("⚠ TimeoutError patch line not found, may already be patched")
            return True
        
    except Exception as e:
        print(f"❌ Failed to patch eventlet timeout: {e}")
        return False

def patch_eventlet_wsgi():
    """Add ALREADY_HANDLED to eventlet.wsgi for Ryu compatibility"""
    eventlet_wsgi_path = '/usr/local/lib/python3.10/dist-packages/eventlet/wsgi.py'
    
    if not os.path.exists(eventlet_wsgi_path):
        print(f"❌ eventlet wsgi not found at {eventlet_wsgi_path}")
        return False
    
    try:
        with open(eventlet_wsgi_path, 'r') as f:
            content = f.read()
        
        if 'ALREADY_HANDLED' in content:
            print("✓ ALREADY_HANDLED already exists in eventlet.wsgi")
            return True
        
        # Find a good place to add ALREADY_HANDLED
        if 'import errno' in content:
            patched_content = content.replace(
                'import errno',
                'import errno\n\n# Compatibility patch for Ryu\nALREADY_HANDLED = object()'
            )
        else:
            # Add at the top after imports
            lines = content.split('\n')
            insert_index = 0
            for i, line in enumerate(lines):
                if line.startswith('import ') or line.startswith('from '):
                    insert_index = i + 1
                elif line.strip() == '' and insert_index > 0:
                    break
            
            lines.insert(insert_index, '# Compatibility patch for Ryu')
            lines.insert(insert_index + 1, 'ALREADY_HANDLED = object()')
            patched_content = '\n'.join(lines)
        
        # Write the patched content
        with open(eventlet_wsgi_path, 'w') as f:
            f.write(patched_content)
        
        print("✓ Successfully patched eventlet.wsgi with ALREADY_HANDLED")
        return True
        
    except Exception as e:
        print(f"❌ Failed to patch eventlet.wsgi: {e}")
        return False

def patch_eventlet():
    """Apply all eventlet patches"""
    print("🔧 Applying comprehensive eventlet patches for Python 3.10+ compatibility...")
    
    timeout_success = patch_eventlet_timeout()
    wsgi_success = patch_eventlet_wsgi()
    
    return timeout_success and wsgi_success

if __name__ == "__main__":
    success = patch_eventlet()
    sys.exit(0 if success else 1)
