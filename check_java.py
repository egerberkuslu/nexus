#!/usr/bin/env python3
"""
Check Java installation for OpenDaylight
"""

import subprocess
import sys

def check_java():
    """Check Java installation and version"""
    try:
        # Check if java command exists
        result = subprocess.run(['java', '-version'],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        if result.returncode != 0:
            print("❌ Java not found in PATH")
            print("Please install Java 11 or higher:")
            print("  Ubuntu/Debian: sudo apt install openjdk-11-jdk")
            print("  CentOS/RHEL: sudo yum install java-11-openjdk")
            print("  macOS: brew install openjdk@11")
            return False

        # Parse version
        version_output = result.stdout
        print(f"Java version output:\n{version_output}")

        # Extract version number
        import re
        version_match = re.search(r'version "(\d+)', version_output)
        if version_match:
            version = int(version_match.group(1))
            if version >= 11:
                print(f"✅ Java {version} detected - suitable for OpenDaylight")
                return True
            else:
                print(f"❌ Java {version} detected - OpenDaylight requires Java 11+")
                return False
        else:
            print("❌ Could not parse Java version")
            return False

    except FileNotFoundError:
        print("❌ Java not installed")
        return False
    except Exception as e:
        print(f"❌ Error checking Java: {e}")
        return False

def main():
    """Main function"""
    print("OpenDaylight Java Requirements Check")
    print("=" * 40)

    if check_java():
        print("\n🎉 Java requirements met! OpenDaylight should work.")
        return 0
    else:
        print("\n❌ Java requirements not met. Please install Java 11+.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
