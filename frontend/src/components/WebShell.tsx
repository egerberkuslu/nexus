import { useEffect, useRef, useState } from 'react'
import { Terminal } from 'xterm'
import { FitAddon } from 'xterm-addon-fit'
import { WebLinksAddon } from 'xterm-addon-web-links'
import 'xterm/css/xterm.css'

interface WebShellProps {
  device: string
  container?: string
  onClose?: () => void
}

export default function WebShell({ device, container, onClose }: WebShellProps) {
  const terminalRef = useRef<HTMLDivElement>(null)
  const xtermRef = useRef<Terminal | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const fitAddonRef = useRef<FitAddon | null>(null)
  const writeBufferRef = useRef<string[]>([])
  const flushHandleRef = useRef<number | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [connectionId, setConnectionId] = useState(0)

  useEffect(() => {
    if (!terminalRef.current) return

    writeBufferRef.current = []

    // Initialize terminal
    const term = new Terminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      theme: {
        background: '#1a1a1a',
        foreground: '#ffffff',
        cursor: '#ffffff',
        selectionBackground: '#5da5d5',
        black: '#1e1e1e',
        brightBlack: '#666666',
        red: '#f48771',
        brightRed: '#ff6b6b',
        green: '#90c966',
        brightGreen: '#95e454',
        yellow: '#e5c07b',
        brightYellow: '#f0c674',
        blue: '#61afef',
        brightBlue: '#6fc2ef',
        magenta: '#c678dd',
        brightMagenta: '#d6acff',
        cyan: '#56b6c2',
        brightCyan: '#6fc2ba',
        white: '#e6e6e6',
        brightWhite: '#ffffff',
      },
      rows: 30,
      cols: 100,
    })

    const fitAddon = new FitAddon()
    const webLinksAddon = new WebLinksAddon()

    const flushBufferedOutput = () => {
      flushHandleRef.current = null
      if (!writeBufferRef.current.length) {
        return
      }
      if (xtermRef.current) {
        xtermRef.current.write(writeBufferRef.current.join(''))
      } else {
        term.write(writeBufferRef.current.join(''))
      }
      writeBufferRef.current = []
    }

    const enqueueOutput = (chunk: string) => {
      if (!chunk) return
      writeBufferRef.current.push(chunk)
      if (flushHandleRef.current === null) {
        flushHandleRef.current = window.requestAnimationFrame(flushBufferedOutput)
      }
    }

    term.loadAddon(fitAddon)
    term.loadAddon(webLinksAddon)

    term.open(terminalRef.current)
    fitAddon.fit()
    term.focus()

    xtermRef.current = term
    fitAddonRef.current = fitAddon

    // Connect to WebSocket
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const encodedDevice = encodeURIComponent(device)
    const params = new URLSearchParams()
    if (container) {
      params.set('container', container)
    }
    const query = params.toString()
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/shell/${encodedDevice}${
      query ? `?${query}` : ''
    }`

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      setError(null)
      enqueueOutput(`\x1b[1;32m✓ Connected to ${device}\x1b[0m\r\n`)
      enqueueOutput(`Type 'help' for available commands\r\n\r\n`)
    }

    ws.onmessage = (event) => {
      const handlePayload = (payload: string) => {
        enqueueOutput(payload)
      }

      try {
        const message = JSON.parse(event.data)
        
        if (message.type === 'output') {
          handlePayload(message.data)
        } else if (message.type === 'error') {
          // Handle error messages
          handlePayload(`\r\n\x1b[1;31mError: ${message.message}\x1b[0m\r\n`)
        }
      } catch (error) {
        // If it's not JSON, treat it as raw terminal data (fallback)
        if (typeof event.data === 'string') {
          handlePayload(event.data)
        }
      }
    }

    ws.onerror = (err) => {
      setError('WebSocket connection error')
      enqueueOutput('\r\n\x1b[1;31m✗ Connection error\x1b[0m\r\n')
    }

    ws.onclose = () => {
      setIsConnected(false)
      enqueueOutput('\r\n\x1b[1;33m✗ Connection closed\x1b[0m\r\n')
    }

    // Handle terminal input
    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'input', data }))
      }
    })

    // Handle terminal resize
    const handleResize = () => {
      fitAddon.fit()
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(
          JSON.stringify({
            type: 'resize',
            rows: term.rows,
            cols: term.cols,
          })
        )
      }
    }

    window.addEventListener('resize', handleResize)

    // Cleanup
    return () => {
      if (flushHandleRef.current !== null) {
        window.cancelAnimationFrame(flushHandleRef.current)
        flushHandleRef.current = null
      }
      writeBufferRef.current = []
      window.removeEventListener('resize', handleResize)
      ws.close()
      term.dispose()
    }
  }, [device, container, connectionId])

  const handleClear = () => {
    xtermRef.current?.clear()
  }

  const handleReconnect = () => {
    wsRef.current?.close()
    setConnectionId((prev) => prev + 1)
  }

  return (
    <div className="flex flex-col h-full bg-gray-900">
      {/* Terminal Header */}
      <div className="bg-gray-800 border-b border-gray-700 px-4 py-2 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div
            className={`w-3 h-3 rounded-full ${
              isConnected ? 'bg-green-500' : 'bg-red-500'
            }`}
          />
          <span className="text-white font-medium">WebShell - {device}</span>
          {error && <span className="text-red-500 text-sm">({error})</span>}
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={handleClear}
            className="px-3 py-1 bg-gray-700 text-white rounded hover:bg-gray-600 text-sm"
          >
            Clear
          </button>
          <button
            onClick={handleReconnect}
            className="px-3 py-1 bg-gray-700 text-white rounded hover:bg-gray-600 text-sm"
          >
            Reconnect
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="px-3 py-1 bg-red-600 text-white rounded hover:bg-red-700 text-sm"
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
            <span>Ctrl+C: Interrupt</span>
            <span>Ctrl+D: EOF</span>
            <span>Tab: Autocomplete</span>
          </div>
          <div className="flex items-center space-x-2">
            <span>Protocol: WebSocket</span>
            <span>•</span>
            <span>Device: {device}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
