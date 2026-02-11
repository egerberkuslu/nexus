"""
WebShell Service (Port 8007)
Provides web-based terminal access to network devices via WebSocket
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
import logging
import asyncio
import subprocess
import os
import pty
import select
import termios
import struct
import fcntl
from datetime import datetime
import httpx

# Import shared components
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from shared.messaging.rabbitmq import RabbitMQPublisher
from shared.utils.consul_client import ConsulClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Caduceus-Flux WebShell Service",
    description="Web-based terminal access to network devices",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service clients
consul_client = ConsulClient()
rabbitmq_publisher = RabbitMQPublisher()

SERVICE_PORT = 8007
ORCHESTRATOR_URL = (os.getenv("ORCHESTRATOR_URL", "http://orchestrator-service:8002") or "").rstrip("/")

# Active WebSocket connections
active_connections: Dict[str, List[WebSocket]] = {}
active_terminals: Dict[str, Dict] = {}


# Pydantic models
class ShellSession(BaseModel):
    device: str
    session_id: str
    created_at: datetime
    status: str


class TerminalConfig(BaseModel):
    rows: int = 24
    cols: int = 80
    device: str


# Terminal handler class
class TerminalHandler:
    """Handles PTY creation and I/O for device terminals"""

    def __init__(self, device: str, container: Optional[str] = None):
        self.device = device
        self.container = container
        self.master_fd = None
        self.slave_fd = None
        self.child_pid = None
        self.active = False

    async def start(self, rows: int = 24, cols: int = 80):
        """Start PTY for device"""
        try:
            # Create pseudo-terminal
            self.master_fd, self.slave_fd = pty.openpty()

            # Set terminal size
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self.slave_fd, termios.TIOCSWINSZ, winsize)
            
            # Configure terminal attributes for responsive input with echo enabled
            attrs = termios.tcgetattr(self.slave_fd)
            attrs[3] |= termios.ECHO  # Enable echo for user feedback
            attrs[3] &= ~termios.ICANON  # Disable canonical mode for immediate input
            attrs[3] &= ~termios.ISIG  # Disable signal generation
            attrs[3] &= ~termios.IEXTEN  # Disable extended input processing
            attrs[3] &= ~termios.IXON   # Disable XON/XOFF flow control
            attrs[3] &= ~termios.IXOFF  # Disable XON/XOFF flow control
            attrs[6][termios.VMIN] = 0  # Don't wait for minimum characters
            attrs[6][termios.VTIME] = 0  # No timeout
            termios.tcsetattr(self.slave_fd, termios.TCSANOW, attrs)

            # Fork process to execute shell in device namespace
            self.child_pid = os.fork()

            if self.child_pid == 0:
                # Child process
                os.setsid()
                os.dup2(self.slave_fd, 0)  # stdin
                os.dup2(self.slave_fd, 1)  # stdout
                os.dup2(self.slave_fd, 2)  # stderr

                # Close original file descriptors
                os.close(self.master_fd)
                os.close(self.slave_fd)

                # Execute shell in device via docker exec to emulation container
                try:
                    # Special mode: open an interactive shell directly inside a Docker container
                    # (used for controller containers in the Network Manager UI).
                    if self.device in ("container-shell", "container_shell", "container"):
                        target_container = self.container
                        if not target_container:
                            os.write(1, b"\r\n\x1b[1;31mERROR: Missing container name for container-shell\x1b[0m\r\n")
                            os._exit(1)

                        shell_script = """
                        export TERM=xterm-256color
                        export PS1='CONTAINER:\\w\\$ '
                        stty echo -icanon -isig -iexten -ixon -ixoff
                        if command -v bash >/dev/null 2>&1; then
                          exec bash -li
                        else
                          exec sh -l
                        fi
                        """

                        os.execvp(
                            "docker",
                            ["docker", "exec", "-it", str(target_container), "sh", "-lc", shell_script],
                        )

                    # Use docker exec to access the device in the emulation container
                    emulation_container = self.container or os.getenv("EMULATION_CONTAINER", "caduceus-emulation")
                    
                    # Create a comprehensive shell setup script that connects to the Mininet device
                    shell_script = """
                    # Disable bracketed paste mode
                    printf '\\033[?2004l'
                    
                    # Set terminal environment
                    export TERM=xterm-256color
                    export PS1='DEVICE_PROMPT_PLACEHOLDER:\\$ '
                    
                    # Configure stty for clean input/output (enable echo for user feedback)
                    stty echo -icanon -isig -iexten -ixon -ixoff
                    stty -raw
                    
                    # Connect to Mininet device using Python API
                    python3 -c "
import json
import os
import sys

STATE_FILE = '/var/lib/caduceus/emulation_state.json'
device_name = 'DEVICE_NAME_PLACEHOLDER'

def pause_and_exit(message, extra_lines=None, status=None, emulation_id=None):
    print('\\n\\x1b[1;31m❌ ' + message + '\\x1b[0m')
    if status is not None:
        print('\\x1b[1;33mStatus:\\x1b[0m ' + str(status))
    if emulation_id is not None:
        print('\\x1b[1;33mEmulation ID:\\x1b[0m ' + str(emulation_id))
    if extra_lines:
        for line in extra_lines:
            print(line)
    print('\\n\\x1b[1;32mPress Enter to continue...\\x1b[0m')
    try:
        input()
    except EOFError:
        pass
    sys.exit(1)

def standard_instructions():
    return [
        '\\x1b[1;36m💡 To fix this:\\x1b[0m',
        '1. Go to the frontend (http://localhost:3000)',
        '2. Navigate to Topology Editor',
        '3. Create a topology with devices',
        '4. Click Start Emulation',
        '5. Then try connecting to devices again'
    ]

try:
    with open(STATE_FILE, 'r') as handle:
        state = json.load(handle)
except FileNotFoundError:
    pause_and_exit('No active emulation found!', standard_instructions())
except json.JSONDecodeError as exc:
    pause_and_exit('Unable to read emulation state!', ['Error: ' + str(exc)])

status = state.get('status')
if status != 'running':
    pause_and_exit('No active emulation found!', standard_instructions(), status=status, emulation_id=state.get('emulation_id'))

devices = state.get('devices', {})
device_info = devices.get(device_name)
if not device_info:
    available = sorted(devices.keys())
    advice = []
    if available:
        advice.append('\\x1b[1;36m💡 Available devices:\\x1b[0m')
        advice.extend(['  - ' + name for name in available])
    else:
        advice.append('No devices found in the current emulation.')
    pause_and_exit('Device ' + device_name + ' not found in active emulation!', advice)

pid = device_info.get('pid')
if not pid:
    pause_and_exit('Device ' + device_name + ' is missing runtime PID information.', ['Try restarting the emulation from the frontend.'])

print('\\n\\x1b[1;32m✅ Connecting to ' + device_name + ' (PID: ' + str(pid) + ')...\\x1b[0m')
os.execvp('mnexec', ['mnexec', '-a', str(pid), 'bash', '--norc', '--noprofile'])
"
                    """
                    sanitized_device = self.device.replace("'", "\\'")
                    shell_script = shell_script.replace("DEVICE_NAME_PLACEHOLDER", sanitized_device)
                    shell_script = shell_script.replace("DEVICE_PROMPT_PLACEHOLDER", sanitized_device)
                    
                    os.execvp(
                        "docker",
                        ["docker", "exec", "-it", emulation_container, 
                         "bash", "-c", shell_script]
                    )
                except Exception as e:
                    logger.error(f"Failed to exec shell: {e}")
                    os._exit(1)

            # Parent process
            os.close(self.slave_fd)

            # Set master fd to non-blocking
            flags = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
            fcntl.fcntl(self.master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            self.active = True
            logger.info(f"Terminal started for {self.device} (PID: {self.child_pid})")

            return True

        except Exception as e:
            logger.error(f"Failed to start terminal for {self.device}: {e}")
            self.cleanup()
            return False

    async def read(self, max_bytes: int = 4096) -> bytes:
        """Read output from terminal"""
        try:
            if not self.active or self.master_fd is None:
                return b""

            try:
                return os.read(self.master_fd, max_bytes)
            except BlockingIOError:
                return b""

        except OSError:
            # Terminal closed
            self.active = False
            return b""
        except Exception as e:
            logger.error(f"Error reading from terminal: {e}")
            return b""

    async def write(self, data: bytes):
        """Write input to terminal"""
        try:
            if not self.active or self.master_fd is None:
                return

            os.write(self.master_fd, data)

        except Exception as e:
            logger.error(f"Error writing to terminal: {e}")
            self.active = False

    def resize(self, rows: int, cols: int):
        """Resize terminal"""
        try:
            if self.master_fd is None:
                return

            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
            logger.info(f"Terminal resized to {rows}x{cols}")

        except Exception as e:
            logger.error(f"Error resizing terminal: {e}")

    def cleanup(self):
        """Clean up terminal resources"""
        try:
            self.active = False

            if self.master_fd:
                os.close(self.master_fd)
                self.master_fd = None

            if self.child_pid:
                try:
                    os.kill(self.child_pid, 9)
                except ProcessLookupError:
                    pass
                self.child_pid = None

            logger.info(f"Terminal cleaned up for {self.device}")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# API endpoints

@app.on_event("startup")
async def startup_event():
    """Service startup"""
    logger.info("Starting WebShell Service...")
    try:
        consul_client.register_service("webshell", SERVICE_PORT)
        rabbitmq_publisher.connect()
        logger.info("WebShell Service started successfully")
    except Exception as e:
        logger.error(f"Startup error: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Service shutdown"""
    logger.info("Shutting down WebShell Service...")

    # Clean up all active terminals
    for session_id, terminal_info in list(active_terminals.items()):
        terminal = terminal_info.get("terminal")
        if terminal:
            terminal.cleanup()

    consul_client.deregister_service("webshell")
    rabbitmq_publisher.disconnect()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "webshell",
        "active_sessions": len(active_terminals),
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/sessions")
async def list_sessions():
    """List active shell sessions"""
    sessions = []

    for session_id, terminal_info in active_terminals.items():
        sessions.append({
            "session_id": session_id,
            "device": terminal_info.get("device"),
            "created_at": terminal_info.get("created_at"),
            "active": terminal_info.get("terminal").active if terminal_info.get("terminal") else False
        })

    return {"sessions": sessions, "count": len(sessions)}


import grpc
import emulation_pb2
import emulation_pb2_grpc

# ... (rest of the imports)

# ... (existing code)

async def handle_mininet_cli_session(websocket: WebSocket, container: Optional[str] = None):
    await websocket.accept()
    emulation_id = ""

    try:
        async def _resolve_grpc_target() -> tuple[str, str]:
            """Resolve target emulation container/port for Mininet CLI gRPC."""
            grpc_port = os.getenv("EMULATION_GRPC_PORT", "50051")
            explicit_container = container or websocket.query_params.get("container")
            if explicit_container:
                return str(explicit_container), grpc_port

            requested_topology_id = websocket.query_params.get("topology_id")
            requested_emulation_id = websocket.query_params.get("emulation_id")

            # Prefer orchestrator runtime registry for dynamic per-topology emulation containers.
            if ORCHESTRATOR_URL:
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.get(f"{ORCHESTRATOR_URL}/api/emulation/active")
                        if resp.status_code == 200:
                            emulations = (resp.json() or {}).get("emulations") or []
                            selected = None

                            if requested_emulation_id:
                                selected = next(
                                    (
                                        e for e in emulations
                                        if str(e.get("emulation_id") or "") == str(requested_emulation_id)
                                        and str(e.get("status") or "").lower() == "running"
                                    ),
                                    None,
                                )
                            if not selected and requested_topology_id:
                                selected = next(
                                    (
                                        e for e in emulations
                                        if str(e.get("topology_id") or "") == str(requested_topology_id)
                                        and str(e.get("status") or "").lower() == "running"
                                    ),
                                    None,
                                )
                            if not selected:
                                selected = next(
                                    (e for e in emulations if str(e.get("status") or "").lower() == "running"),
                                    None,
                                )

                            if selected and selected.get("container_name"):
                                return str(selected["container_name"]), grpc_port
                except Exception as exc:
                    logger.warning("Failed to resolve Mininet CLI runtime from orchestrator: %s", exc)

            # Legacy/static fallback (supports non-dynamic legacy deployments).
            grpc_host = os.getenv("EMULATION_GRPC_HOST", os.getenv("EMULATION_CONTAINER", "localhost"))
            return grpc_host, grpc_port

        # Establish gRPC connection to the emulation container
        emulation_container_grpc_host, emulation_container_grpc_port = await _resolve_grpc_target()
        grpc_channel = grpc.aio.insecure_channel(f"{emulation_container_grpc_host}:{emulation_container_grpc_port}")
        grpc_stub = emulation_pb2_grpc.EmulationServiceStub(grpc_channel)

        async def grpc_request_iterator():
            # The first message can be used to pass the emulation_id if needed
            # For now, we assume the server knows which emulation is running
            # yield emulation_pb2.CLIRequest(emulation_id=emulation_id)
            while True:
                message = await websocket.receive_json()
                if message.get("type") == "input":
                    yield emulation_pb2.CLIRequest(input=message.get("data", ""))
                elif message.get("type") == "resize":
                    yield emulation_pb2.CLIRequest(resize=emulation_pb2.Resize(rows=message.get("rows", 24), cols=message.get("cols", 80)))

        async for response in grpc_stub.MininetCLI(grpc_request_iterator()):
            if response.HasField("output"):
                await websocket.send_json({"type": "output", "data": response.output})
            elif response.HasField("error"):
                await websocket.send_json({"type": "error", "message": response.error})

    except grpc.aio.AioRpcError as e:
        logger.error(f"gRPC error in Mininet CLI session: {e}")
        await websocket.send_json({"type": "error", "message": f"gRPC Error: {e.details()}"})
    except WebSocketDisconnect:
        logger.info("Mininet CLI WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in Mininet CLI session: {e}")
        await websocket.send_json({"type": "error", "message": str(e)})
    finally:
        if "grpc_channel" in locals() and grpc_channel:
            await grpc_channel.close()
        if not websocket.client_state == "DISCONNECTED":
            await websocket.close()


@app.websocket("/ws/shell/{device}")
async def websocket_shell(websocket: WebSocket, device: str):
    """
    WebSocket endpoint for device shell access
    
    Protocol:
    - Client sends: {"type": "input", "data": "command"}
    - Client sends: {"type": "resize", "rows": 24, "cols": 80}
    - Server sends: {"type": "output", "data": "output text"}
    """
    container_name = websocket.query_params.get("container")

    if device in ("mininet-cli", "mininet_cli", "mininet"):
        await handle_mininet_cli_session(websocket, container=container_name)
        return

    await websocket.accept()
    
    session_id = f"{device}_{datetime.utcnow().timestamp()}"
    logger.info(f"WebSocket connection established for {device} (session: {session_id})")

    # Track connection
    if device not in active_connections:
        active_connections[device] = []
    active_connections[device].append(websocket)

    # Create terminal
    terminal = TerminalHandler(device, container=container_name)
    success = await terminal.start()

    if not success:
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to create terminal for device {device}"
        })
        await websocket.close()
        return

    # Store terminal info
    active_terminals[session_id] = {
        "device": device,
        "terminal": terminal,
        "created_at": datetime.utcnow().isoformat(),
        "websocket": websocket,
        "container": container_name,
    }

    # Send welcome message
    await websocket.send_json({
        "type": "output",
        "data": f"Connected to {device}\r\n"
    })

    try:
        # Create tasks for bidirectional communication
        async def read_from_terminal():
            """Read from terminal and send to WebSocket"""
            while terminal.active:
                try:
                    data = await terminal.read()
                    if data:
                        decoded_data = data.decode('utf-8', errors='ignore')
                        
                        # Filter out bracketed paste mode toggles that can confuse the frontend
                        cleaned_data = decoded_data.replace('\x1b[?2004h', '').replace('\x1b[?2004l', '')
                        cleaned_data = cleaned_data.replace('\x1b]0;', '').replace('\x07', '')
                        cleaned_data = cleaned_data.replace('\r\r', '\r')

                        if cleaned_data:
                            await websocket.send_json({
                                "type": "output",
                                "data": cleaned_data
                            })
                    else:
                        await asyncio.sleep(0.01)
                except Exception as e:
                    logger.error(f"Error reading from terminal: {e}")
                    break

        async def write_to_terminal():
            """Receive from WebSocket and write to terminal"""
            while terminal.active:
                try:
                    message = await websocket.receive_json()
                    
                    msg_type = message.get("type")
                    
                    if msg_type == "input":
                        # User input
                        data = message.get("data", "")
                        await terminal.write(data.encode('utf-8'))
                        
                    elif msg_type == "resize":
                        # Terminal resize
                        rows = message.get("rows", 24)
                        cols = message.get("cols", 80)
                        terminal.resize(rows, cols)
                        
                    elif msg_type == "ping":
                        # Keepalive
                        await websocket.send_json({"type": "pong"})
                        
                except WebSocketDisconnect:
                    logger.info(f"WebSocket disconnected for {device}")
                    break
                except Exception as e:
                    logger.error(f"Error in WebSocket handler: {e}")
                    break

        # Run both tasks concurrently
        await asyncio.gather(
            read_from_terminal(),
            write_to_terminal()
        )

    except Exception as e:
        logger.error(f"WebSocket error for {device}: {e}")

    finally:
        # Cleanup
        logger.info(f"Cleaning up WebSocket session for {device}")

        # Remove from active connections
        if device in active_connections:
            if websocket in active_connections[device]:
                active_connections[device].remove(websocket)
            if not active_connections[device]:
                del active_connections[device]

        # Clean up terminal
        terminal.cleanup()

        # Remove from active terminals
        if session_id in active_terminals:
            del active_terminals[session_id]

        # Close WebSocket if not already closed
        try:
            await websocket.close()
        except:
            pass


@app.websocket("/ws/mininet-cli")
async def websocket_mininet_cli(websocket: WebSocket):
    """
    WebSocket endpoint for Mininet CLI

    Provides an interactive Mininet CLI that directly communicates with the
    running Mininet instance in the emulation container
    """
    await handle_mininet_cli_session(websocket)


@app.delete("/api/sessions/{session_id}")
async def close_session(session_id: str):
    """Force close a shell session"""
    if session_id not in active_terminals:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    terminal_info = active_terminals[session_id]
    terminal = terminal_info.get("terminal")

    if terminal:
        terminal.cleanup()

    del active_terminals[session_id]

    return {"message": f"Session {session_id} closed"}


@app.post("/api/broadcast/{device}")
async def broadcast_to_device(device: str, command: str):
    """Broadcast a command to all active sessions for a device"""
    if device not in active_connections:
        raise HTTPException(status_code=404, detail=f"No active sessions for device {device}")

    # Send command to all active terminals for this device
    count = 0
    for session_id, terminal_info in active_terminals.items():
        if terminal_info.get("device") == device:
            terminal = terminal_info.get("terminal")
            if terminal and terminal.active:
                await terminal.write(f"{command}\n".encode('utf-8'))
                count += 1

    return {
        "device": device,
        "command": command,
        "sessions_notified": count
    }


@app.get("/api/devices/{device}/execute")
async def execute_command_direct(device: str, command: str):
    """Execute a command directly on device (non-interactive)"""
    try:
        result = subprocess.run(
            ["ip", "netns", "exec", device, "bash", "-c", command],
            capture_output=True,
            text=True,
            timeout=30
        )

        return {
            "device": device,
            "command": command,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
            "timestamp": datetime.utcnow().isoformat()
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Command execution timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
