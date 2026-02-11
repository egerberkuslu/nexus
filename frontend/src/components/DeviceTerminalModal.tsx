import { useEffect, useRef, useState, useCallback } from 'react';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import { WebLinksAddon } from 'xterm-addon-web-links';
import 'xterm/css/xterm.css';
import { XMarkIcon } from '@heroicons/react/24/outline';

interface DeviceTerminalModalProps {
  device: string;
  container?: string;
  onClose: () => void;
}

export default function DeviceTerminalModal({ device, container, onClose }: DeviceTerminalModalProps) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const [isConnected, setIsConnected] = useState(false);

  const connect = useCallback(() => {
    if (!terminalRef.current) return;

    const term = xtermRef.current || new Terminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      theme: {
        background: '#1a1b26',
        foreground: '#a9b1d6',
        cursor: '#ffcc66',
        selectionBackground: '#414868',
        black: '#01060e',
        brightBlack: '#414868',
        red: '#f7768e',
        brightRed: '#f7768e',
        green: '#9ece6a',
        brightGreen: '#9ece6a',
        yellow: '#e0af68',
        brightYellow: '#e0af68',
        blue: '#7aa2f7',
        brightBlue: '#7aa2f7',
        magenta: '#bb9af7',
        brightMagenta: '#bb9af7',
        cyan: '#7dcfff',
        brightCyan: '#7dcfff',
        white: '#a9b1d6',
        brightWhite: '#c0caf5',
      },
      rows: 25,
      cols: 80,
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

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const encodedDevice = encodeURIComponent(device)
    const params = new URLSearchParams()
    if (container) params.set('container', container)
    const qs = params.toString()
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/shell/${encodedDevice}${qs ? `?${qs}` : ''}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      term.writeln(`\x1b[1;32m✓ Connected to ${device}\x1b[0m`);
      const resizeMsg = JSON.stringify({
        type: 'resize',
        rows: term.rows,
        cols: term.cols,
      });
      ws.send(resizeMsg);
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === 'output') {
          term.write(message.data);
        } else if (message.type === 'error') {
          term.write(`\r\n\x1b[1;31m✗ Error: ${message.message}\x1b[0m\r\n`);
        }
      } catch (error) {
        if (typeof event.data === 'string') {
          term.write(event.data);
        }
      }
    };

    ws.onerror = () => {
      setIsConnected(false);
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
  }, [device]);

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
  }, [connect]);

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
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div className="bg-gray-900 rounded-2xl shadow-2xl w-full max-w-4xl h-[70vh] flex flex-col overflow-hidden border border-gray-700">
        <div className="bg-gray-800 px-4 py-2 flex items-center justify-between border-b border-gray-700">
          <div className="flex items-center gap-3">
            <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-400' : 'bg-red-500'}`} />
            <span className="text-white font-bold">Terminal: {device}</span>
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
            <button onClick={onClose} className="p-1 rounded-full text-gray-400 hover:bg-gray-700">
              <XMarkIcon className="h-5 w-5" />
            </button>
          </div>
        </div>
        <div ref={terminalRef} className="flex-1 p-2" />
      </div>
    </div>
  );
}
