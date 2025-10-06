#!/usr/bin/env python3
"""
FilaTag Pro Desktop Application

Native desktop application for embedded devices without browsers.
Optimized for Sonic Pad and similar embedded controllers with touchscreens.

Usage:
    python3 desktop_app.py [--fullscreen] [--port 3000]
"""

import sys
import os
import time
import json
import threading
import subprocess
import argparse
from pathlib import Path
import signal
import webbrowser
from urllib.parse import urljoin

try:
    import webview
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
    import tkinter.font as tkFont
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False

# Add backend to path for service management
sys.path.append(str(Path(__file__).parent / 'backend'))

class FilaTagDesktopApp:
    def __init__(self, fullscreen=True, port=3000, backend_port=8001):
        self.fullscreen = fullscreen
        self.port = port
        self.backend_port = backend_port
        self.backend_url = f"http://localhost:{backend_port}"
        self.frontend_url = f"http://localhost:{port}"
        self.backend_process = None
        self.frontend_process = None
        self.running = True
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\nReceived signal {signum}, shutting down...")
        self.running = False
        self.stop_services()
        sys.exit(0)
    
    def check_dependencies(self):
        """Check if required dependencies are available"""
        issues = []
        
        if not HAS_WEBVIEW and not HAS_TKINTER:
            issues.append("Neither webview nor tkinter available. Install with: pip install webview")
        
        if not os.path.exists(Path(__file__).parent / 'backend' / 'server.py'):
            issues.append("Backend server.py not found")
            
        if not os.path.exists(Path(__file__).parent / 'frontend' / 'build'):
            if not os.path.exists(Path(__file__).parent / 'frontend' / 'package.json'):
                issues.append("Frontend not found")
        
        return issues
    
    def build_frontend(self):
        """Build React frontend for production"""
        frontend_dir = Path(__file__).parent / 'frontend'
        
        if not (frontend_dir / 'build').exists():
            print("Building React frontend...")
            try:
                # Try yarn first, fall back to npm
                if subprocess.run(['which', 'yarn'], capture_output=True).returncode == 0:
                    cmd = ['yarn', 'build']
                else:
                    cmd = ['npm', 'run', 'build']
                
                result = subprocess.run(
                    cmd, 
                    cwd=frontend_dir, 
                    capture_output=True, 
                    text=True,
                    timeout=300  # 5 minutes timeout
                )
                
                if result.returncode != 0:
                    print(f"Frontend build failed: {result.stderr}")
                    return False
                    
                print("Frontend built successfully")
                return True
                
            except Exception as e:
                print(f"Error building frontend: {e}")
                return False
        
        return True
    
    def start_backend(self):
        """Start FastAPI backend server"""
        backend_dir = Path(__file__).parent / 'backend'
        
        print(f"Starting backend server on port {self.backend_port}...")
        
        try:
            # Set environment variables
            env = os.environ.copy()
            env.update({
                'MONGO_URL': 'mongodb://localhost:27017',
                'DB_NAME': 'filatag_db',
                'CORS_ORIGINS': f'http://localhost:{self.port}',
                'PYTHONPATH': str(backend_dir)
            })
            
            # Start backend with uvicorn
            self.backend_process = subprocess.Popen([
                sys.executable, '-m', 'uvicorn',
                'server:app',
                '--host', '0.0.0.0',
                '--port', str(self.backend_port),
                '--reload'
            ], cwd=backend_dir, env=env)
            
            # Wait for backend to start
            time.sleep(3)
            
            # Check if backend is running
            try:
                import urllib.request
                urllib.request.urlopen(f"{self.backend_url}/api/device/status", timeout=5)
                print("✅ Backend server started successfully")
                return True
            except Exception as e:
                print(f"❌ Backend server failed to start: {e}")
                return False
                
        except Exception as e:
            print(f"Error starting backend: {e}")
            return False
    
    def start_frontend_server(self):
        """Start frontend server (for development) or serve static files"""
        frontend_dir = Path(__file__).parent / 'frontend'
        
        # Check if we have a built version
        if (frontend_dir / 'build').exists():
            print(f"Serving built frontend on port {self.port}...")
            
            try:
                # Serve static files using Python's built-in server
                self.frontend_process = subprocess.Popen([
                    sys.executable, '-m', 'http.server', str(self.port)
                ], cwd=frontend_dir / 'build')
                
                time.sleep(2)
                print("✅ Frontend server started successfully")
                return True
                
            except Exception as e:
                print(f"Error serving frontend: {e}")
                return False
        else:
            # Development mode - start React dev server
            print(f"Starting React development server on port {self.port}...")
            
            try:
                env = os.environ.copy()
                env['PORT'] = str(self.port)
                
                if subprocess.run(['which', 'yarn'], capture_output=True).returncode == 0:
                    cmd = ['yarn', 'start']
                else:
                    cmd = ['npm', 'start']
                
                self.frontend_process = subprocess.Popen(
                    cmd, cwd=frontend_dir, env=env
                )
                
                time.sleep(5)  # React dev server takes longer to start
                print("✅ Frontend development server started")
                return True
                
            except Exception as e:
                print(f"Error starting frontend dev server: {e}")
                return False
    
    def wait_for_services(self):
        """Wait for both services to be ready"""
        max_attempts = 30
        
        for attempt in range(max_attempts):
            try:
                import urllib.request
                
                # Check backend
                urllib.request.urlopen(f"{self.backend_url}/api/device/status", timeout=2)
                
                # Check frontend
                urllib.request.urlopen(self.frontend_url, timeout=2)
                
                print("✅ Both services are ready")
                return True
                
            except Exception:
                print(f"Waiting for services... ({attempt + 1}/{max_attempts})")
                time.sleep(2)
        
        print("❌ Services failed to start within timeout")
        return False
    
    def launch_webview_app(self):
        """Launch app using webview (preferred method)"""
        print("Launching FilaTag Pro using webview...")
        
        # Custom API class for desktop integration
        class DesktopAPI:
            def __init__(self, app):
                self.app = app
            
            def minimize(self):
                """Minimize the application"""
                return True
            
            def get_system_info(self):
                """Get system information"""
                import platform
                return {
                    'platform': platform.system(),
                    'machine': platform.machine(),
                    'python_version': platform.python_version()
                }
        
        api = DesktopAPI(self)
        
        # Configure webview window
        window_config = {
            'title': 'FilaTag Pro - RFID Programming System',
            'url': self.frontend_url,
            'width': 1024,
            'height': 600,
            'min_size': (800, 480),
            'resizable': True,
            'fullscreen': self.fullscreen,
            'on_top': False,
            'shadow': True,
            'debug': False  # Set to True for development
        }
        
        try:
            # Create and start webview
            webview.create_window(js_api=api, **window_config)
            webview.start(debug=False, http_server=False)
            
        except Exception as e:
            print(f"Error launching webview: {e}")
            return False
        
        return True
    
    def launch_tkinter_app(self):
        """Launch app using tkinter with embedded browser simulation"""
        print("Launching FilaTag Pro using tkinter...")
        
        root = tk.Tk()
        root.title("FilaTag Pro - RFID Programming System")
        root.geometry("1024x600")
        
        if self.fullscreen:
            root.attributes('-fullscreen', True)
            root.bind('<Escape>', lambda e: root.attributes('-fullscreen', False))
        
        # Create main frame
        main_frame = ttk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, padx=10, pady=5)
        
        title_font = tkFont.Font(family="Arial", size=16, weight="bold")
        ttk.Label(header_frame, text="FilaTag Pro", font=title_font).pack(side=tk.LEFT)
        
        # Status
        status_frame = ttk.Frame(header_frame)
        status_frame.pack(side=tk.RIGHT)
        
        self.status_label = ttk.Label(status_frame, text="System Ready", foreground="green")
        self.status_label.pack()
        
        # Control buttons
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(
            control_frame, 
            text="Open Web Interface", 
            command=self.open_browser
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            control_frame, 
            text="Test System", 
            command=self.test_system
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            control_frame, 
            text="Settings", 
            command=self.show_settings
        ).pack(side=tk.LEFT, padx=5)
        
        if self.fullscreen:
            ttk.Button(
                control_frame, 
                text="Exit", 
                command=root.quit
            ).pack(side=tk.RIGHT, padx=5)
        
        # Info text
        info_text = tk.Text(main_frame, height=20, wrap=tk.WORD)
        info_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        scrollbar = ttk.Scrollbar(info_text)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        info_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=info_text.yview)
        
        # Initial info
        info_text.insert(tk.END, "FilaTag Pro Desktop Application\n")
        info_text.insert(tk.END, "=" * 40 + "\n\n")
        info_text.insert(tk.END, f"Web Interface: {self.frontend_url}\n")
        info_text.insert(tk.END, f"API Backend: {self.backend_url}\n\n")
        info_text.insert(tk.END, "Click 'Open Web Interface' to access the full FilaTag Pro interface\n")
        info_text.insert(tk.END, "or use the buttons above for quick actions.\n\n")
        
        self.info_text = info_text
        self.root = root
        
        # Start status update thread
        self.update_status_thread = threading.Thread(target=self.update_status_loop, daemon=True)
        self.update_status_thread.start()
        
        try:
            root.mainloop()
        except KeyboardInterrupt:
            root.quit()
        
        return True
    
    def open_browser(self):
        """Open web browser to FilaTag Pro interface"""
        try:
            # Try to find a suitable browser
            browsers = [
                'chromium-browser --kiosk --touch-events',
                'chromium --kiosk --touch-events', 
                'firefox',
                'x-www-browser'
            ]
            
            for browser in browsers:
                try:
                    subprocess.Popen([browser, self.frontend_url])
                    self.log("Opened web interface in browser")
                    return
                except FileNotFoundError:
                    continue
            
            # Fallback - try Python webbrowser module
            webbrowser.open(self.frontend_url)
            self.log("Opened web interface using system default")
            
        except Exception as e:
            self.log(f"Failed to open browser: {e}")
    
    def test_system(self):
        """Test system functionality"""
        self.log("Testing system...")
        
        try:
            # Run CLI test
            result = subprocess.run([
                sys.executable, 'cli.py', 'device-status', '--mock'
            ], cwd=Path(__file__).parent, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                self.log("✅ CLI test passed")
                self.log("System is working correctly")
            else:
                self.log("❌ CLI test failed")
                self.log(result.stderr)
                
        except Exception as e:
            self.log(f"Test failed: {e}")
    
    def show_settings(self):
        """Show settings dialog"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Settings")
        settings_window.geometry("400x300")
        
        ttk.Label(settings_window, text="FilaTag Pro Settings", font=("Arial", 12, "bold")).pack(pady=10)
        
        # URLs
        ttk.Label(settings_window, text="Web Interface:").pack()
        ttk.Label(settings_window, text=self.frontend_url, foreground="blue").pack()
        
        ttk.Label(settings_window, text="API Backend:").pack()
        ttk.Label(settings_window, text=self.backend_url, foreground="blue").pack()
        
        # Buttons
        button_frame = ttk.Frame(settings_window)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="Restart Services", command=self.restart_services).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=settings_window.destroy).pack(side=tk.LEFT, padx=5)
    
    def restart_services(self):
        """Restart backend and frontend services"""
        self.log("Restarting services...")
        
        # Stop current services
        if self.backend_process:
            self.backend_process.terminate()
        if self.frontend_process:
            self.frontend_process.terminate()
        
        time.sleep(2)
        
        # Restart services
        if self.start_backend() and self.start_frontend_server():
            self.log("✅ Services restarted successfully")
        else:
            self.log("❌ Failed to restart services")
    
    def update_status_loop(self):
        """Update status in background thread"""
        while self.running:
            try:
                # Check services
                import urllib.request
                urllib.request.urlopen(f"{self.backend_url}/api/device/status", timeout=2)
                self.status_label.config(text="System Ready", foreground="green")
            except:
                self.status_label.config(text="Service Error", foreground="red")
            
            time.sleep(5)
    
    def log(self, message):
        """Add message to info text"""
        if hasattr(self, 'info_text'):
            self.info_text.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {message}\n")
            self.info_text.see(tk.END)
    
    def stop_services(self):
        """Stop all services"""
        print("Stopping services...")
        
        if self.backend_process:
            self.backend_process.terminate()
            self.backend_process.wait()
        
        if self.frontend_process:
            self.frontend_process.terminate()  
            self.frontend_process.wait()
    
    def run(self):
        """Main application entry point"""
        print("🚀 Starting FilaTag Pro Desktop Application")
        
        # Check dependencies
        issues = self.check_dependencies()
        if issues:
            print("❌ Dependency issues found:")
            for issue in issues:
                print(f"  - {issue}")
            return 1
        
        # Build frontend if needed
        if not self.build_frontend():
            print("❌ Failed to build frontend")
            return 1
        
        # Start services
        if not self.start_backend():
            print("❌ Failed to start backend")
            return 1
        
        if not self.start_frontend_server():
            print("❌ Failed to start frontend")
            return 1
        
        # Wait for services
        if not self.wait_for_services():
            print("❌ Services are not ready")
            return 1
        
        print("✅ All services started successfully")
        print(f"📱 FilaTag Pro is ready at: {self.frontend_url}")
        
        # Launch desktop app
        try:
            if HAS_WEBVIEW:
                return 0 if self.launch_webview_app() else 1
            elif HAS_TKINTER:
                return 0 if self.launch_tkinter_app() else 1
            else:
                print("❌ No GUI framework available")
                print(f"💻 Access FilaTag Pro manually at: {self.frontend_url}")
                
                # Keep services running
                try:
                    while self.running:
                        time.sleep(1)
                except KeyboardInterrupt:
                    pass
                
                return 0
                
        except KeyboardInterrupt:
            print("\n🛑 Shutdown requested")
        except Exception as e:
            print(f"❌ Application error: {e}")
            return 1
        finally:
            self.stop_services()
        
        return 0

def main():
    parser = argparse.ArgumentParser(description='FilaTag Pro Desktop Application')
    parser.add_argument('--fullscreen', action='store_true', help='Launch in fullscreen mode')
    parser.add_argument('--port', type=int, default=3000, help='Frontend port (default: 3000)')
    parser.add_argument('--backend-port', type=int, default=8001, help='Backend port (default: 8001)')
    parser.add_argument('--windowed', action='store_true', help='Launch in windowed mode (opposite of --fullscreen)')
    
    args = parser.parse_args()
    
    # Default to fullscreen unless windowed is specified
    fullscreen = args.fullscreen or not args.windowed
    
    app = FilaTagDesktopApp(
        fullscreen=fullscreen,
        port=args.port,
        backend_port=args.backend_port
    )
    
    return app.run()

if __name__ == "__main__":
    sys.exit(main())