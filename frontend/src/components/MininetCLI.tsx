import { useEffect, useRef, useState, useCallback } from 'react';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import { WebLinksAddon } from 'xterm-addon-web-links';
import 'xterm/css/xterm.css';

interface MininetCLIProps {
  container?: string;
  onClose?: () => void;
}

export default function MininetCLI({ container, onClose }: MininetCLIProps) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const connect = useCallback(() => {
    if (!terminalRef.current) return;

    // Initialize terminal
    const term = xtermRef.current || new Terminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      theme: {
        background: '#0a0e14',
        foreground: '#b3b1ad',
        cursor: '#ffcc66',
        selectionBackground: '#253340',
        black: '#01060e',
        brightBlack: '#686868',
        red: '#ea6c73',
        brightRed: '#f07178',
        green: '#91b362',
        brightGreen: '#c2d94c',
        yellow: '#f9af4f',
        brightYellow: '#ffb454',
        blue: '#53bdfa',
        brightBlue: '#59c2ff',
        magenta: '#fae994',
        brightMagenta: '#ffee99',
        cyan: '#90e1c6',
        brightCyan: '#95e6cb',
        white: '#c7c7c7',
        brightWhite: '#ffffff',
      },
      rows: 30,
      cols: 100,
    });

    if (!xtermRef.current) {
      const fitAddon = new FitAddon();
      const webLinksAddon = new WebLinksAddon();
      term.loadAddon(fitAddon);
      term.loadAddon(webLinksAddon);
      term.open(terminalRef.current);
      fitAddon.fit();
      term.focus();
      xtermRef.current = term;
      fitAddonRef.current = fitAddon;
    }

    // Connect to Mininet CLI WebSocket
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const params = new URLSearchParams();
    if (container) {
      params.set('container', container);
    }
    const qs = params.toString();
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/shell/mininet-cli${qs ? `?${qs}` : ''}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      setError(null);
      term.write('\x1b[1;36m╔══════════════════════════════════════════════════════════╗\x1b[0m\r\n');
      term.write('\x1b[1;36m║           Mininet Interactive CLI                       ║\x1b[0m\r\n');
      term.write('\x1b[1;36m╚══════════════════════════════════════════════════════════╝\x1b[0m\r\n\r\n');
      term.write('\x1b[1;32m✓ Connected to Mininet\x1b[0m\r\n\r\n');
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === 'output') {
          term.write(message.data);
        } else if (message.type === 'error') {
          term.write(`\r\n\x1b[1;31m✗ Error: ${message.message}\x1b[0m\r\n`);
        } else if (message.type === 'prompt') {
          term.write(message.data || 'mininet> ');
        }
      } catch (error) {
        if (typeof event.data === 'string') {
          term.write(event.data);
        }
      }
    };

    ws.onerror = () => {
      setError('WebSocket connection error');
      term.write('\r\n\x1b[1;31m✗ Connection error\x1b[0m\r\n');
    };

    ws.onclose = () => {
      setIsConnected(false);
      term.write('\r\n\x1b[1;33m✗ Connection closed\x1b[0m\r\n');
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      reconnectTimeoutRef.current = setTimeout(connect, 5000);
    };

    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'input', data }));
      }
    });
  }, [container]);

  useEffect(() => {
    connect();

    const handleResize = () => {
      fitAddonRef.current?.fit();
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current?.send(
          JSON.stringify({
            type: 'resize',
            rows: xtermRef.current?.rows,
            cols: xtermRef.current?.cols,
          })
        );
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      wsRef.current?.close();
      xtermRef.current?.dispose();
      xtermRef.current = null;
    };
  }, [connect, container]);

  const handleClear = () => {
    xtermRef.current?.clear();
  };

  const handleReconnect = () => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    wsRef.current?.close();
    connect();
  };

  return (
    <div className="flex flex-col h-full bg-gray-900">
      {/* Terminal Header */}
      <div className="bg-gradient-to-r from-blue-900 to-purple-900 border-b border-gray-700 px-4 py-2 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div
            className={`w-3 h-3 rounded-full ${
              isConnected ? 'bg-green-400 shadow-lg shadow-green-400/50' : 'bg-red-500'
            }`}
          />
          <span className="text-white font-bold">Mininet CLI</span>
          {error && <span className="text-red-400 text-sm">({error})</span>}
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={handleClear}
            className="px-3 py-1 bg-gray-700 text-white rounded hover:bg-gray-600 text-sm transition-colors"
          >
            Clear
          </button>
          <button
            onClick={handleReconnect}
            className="px-3 py-1 bg-gray-700 text-white rounded hover:bg-gray-600 text-sm transition-colors"
          >
            Reconnect
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="px-3 py-1 bg-red-600 text-white rounded hover:bg-red-700 text-sm transition-colors"
            >
              Close
            </button>
          )}
        </div>
      </div>

      {/* Terminal Container */}
      <div className="flex-1 p-4 overflow-hidden">
        <div ref={terminalRef} className="h-full" />
      </div>

      {/* Terminal Footer */}
      <div className="bg-gray-800 border-t border-gray-700 px-4 py-2">
        <div className="flex items-center justify-between text-xs text-gray-400">
          <div className="flex items-center space-x-4">
            <span>💡 Type <span className="text-yellow-400">help</span> for commands</span>
            <span>•</span>
            <span>Ctrl+C: Interrupt</span>
            <span>•</span>
            <span>Tab: Autocomplete</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className={isConnected ? 'text-green-400' : 'text-red-400'}>
              {isConnected ? '● Live' : '● Disconnected'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
