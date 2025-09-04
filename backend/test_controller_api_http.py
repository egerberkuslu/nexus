#!/usr/bin/env python3
"""
HTTP test for the controller installation API endpoint
"""

import requests
import json
import sys
from datetime import datetime

def test_controller_api_http():
    """Test the controller installations API via HTTP"""
    try:
        print("Testing Controller Installation API via HTTP")
        print("=" * 60)

        # Test the API endpoint
        url = "http://localhost:5000/api/controller/installations"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            data = response.json()

            print("✅ API Response received successfully")
            print(f"Status Code: {response.status_code}")
            print()

            # Display summary
            summary = data.get('summary', {})
            print("📊 SUMMARY")
            print("-" * 20)
            print(f"Total Controllers: {summary.get('total_controllers', 0)}")
            print(f"Installed: {summary.get('installed_count', 0)}")
            print(f"Running: {summary.get('running_count', 0)}")
            print(f"All Installed: {'✅' if summary.get('all_installed', False) else '❌'}")
            print()

            # Display controller details
            controllers = data.get('controllers', {})
            print("🔧 CONTROLLER DETAILS")
            print("-" * 25)

            for name, status in controllers.items():
                installed_icon = "✅" if status.get('installed', False) else "❌"
                status_text = status.get('status', 'unknown')
                version = status.get('version', 'N/A')
                environment = status.get('environment', 'system')

                print(f"{installed_icon} {name.upper():12}: {status_text:12} | v{version:8} | {environment}")

                # Show additional info if available
                if 'note' in status:
                    print(f"{'':15}  └─ {status['note']}")
                if 'path' in status:
                    print(f"{'':15}  └─ Path: {status['path']}")
                if status.get('installed') and 'executable' in status and status['executable']:
                    print(f"{'':15}  └─ Executable: {status['executable']}")

            print()
            print("=" * 60)

            if summary.get('all_installed', False):
                print("🎉 All controllers are properly installed!")
            else:
                missing = [name for name, status in controllers.items() if not status.get('installed', False)]
                print(f"⚠️  Missing controllers: {', '.join(missing)}")

            return True

        except requests.exceptions.ConnectionError:
            print("❌ Could not connect to API server")
            print("   Make sure the Flask server is running on port 5000")
            print("   Run: sudo python backend/app.py")
            return False

        except requests.exceptions.Timeout:
            print("❌ API request timed out")
            return False

        except requests.exceptions.HTTPError as e:
            print(f"❌ HTTP Error: {e}")
            return False

        except json.JSONDecodeError:
            print("❌ Invalid JSON response from API")
            return False

    except Exception as e:
        print(f"❌ Error testing API: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Controller Installation API HTTP Test")
    print("This test requires the Flask server to be running")
    print("Run: sudo python backend/app.py")
    print()

    success = test_controller_api_http()
    sys.exit(0 if success else 1)
