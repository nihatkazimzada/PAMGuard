import { useEffect, useRef, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import 'xterm/css/xterm.css';
import { Power, X, Clock } from 'lucide-react';
import { useAuth } from '../AuthContext';

interface SessionInfo {
  sessionId?: number;
  serverHostname?: string;
  serverIp?: string;
  serverPort?: number;
  username?: string;
  expiresAt?: string;
}

type WsMessage = Record<string, unknown>;

export default function SessionWindowPage() {
  const { serverId, requestId } = useParams<{ serverId: string; requestId: string }>();
  const { user } = useAuth();

  const terminalContainerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

  const [sessionInfo, setSessionInfo] = useState<SessionInfo>({});
  const [connected, setConnected] = useState(false);
  const [sshReady, setSshReady] = useState(false);
  const [terminated, setTerminated] = useState(false);
  const [remaining, setRemaining] = useState<string>('');
  const [timerExpired, setTimerExpired] = useState(false);

  const sendMessage = useCallback((msg: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  const writeToTerminal = useCallback((text: string) => {
    if (termRef.current) {
      termRef.current.write(text);
    }
  }, []);

  const handleTerminate = useCallback(() => {
    sendMessage({ action: 'terminate_session', session_id: sessionInfo.sessionId });
    if (wsRef.current) {
      wsRef.current.close();
    }
    setTerminated(true);
    writeToTerminal('\r\n\x1b[31mSession terminated\x1b[0m\r\n');
  }, [sendMessage, sessionInfo.sessionId, writeToTerminal]);

  const formatRemaining = useCallback((ms: number) => {
    if (ms <= 0) return '00:00:00';
    const totalSeconds = Math.floor(ms / 1000);
    const h = Math.floor(totalSeconds / 3600);
    const m = Math.floor((totalSeconds % 3600) / 60);
    const s = totalSeconds % 60;
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }, []);

  useEffect(() => {
    if (!serverId || !requestId) return;

    const term = new Terminal({
      cursorStyle: 'bar',
      cursorBlink: true,
      cursorWidth: 2,
      fontSize: 14,
      fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace",
      theme: {
        background: '#1a1b2e',
        foreground: '#e0e0e0',
        cursor: '#00ff66',
        cursorAccent: '#1a1b2e',
        selectionBackground: '#3a3d5c',
        black: '#2e2e3e',
        red: '#ff5555',
        green: '#50fa7b',
        yellow: '#f1fa8c',
        blue: '#6272a4',
        magenta: '#ff79c6',
        cyan: '#8be9fd',
        white: '#f8f8f2',
        brightBlack: '#5a5a7a',
        brightRed: '#ff6e6e',
        brightGreen: '#69ff94',
        brightYellow: '#ffffa5',
        brightBlue: '#7b8abf',
        brightMagenta: '#ff92d0',
        brightCyan: '#a4f0ff',
        brightWhite: '#ffffff',
      },
      allowTransparency: false,
      disableStdin: false,
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);

    if (terminalContainerRef.current) {
      term.open(terminalContainerRef.current);
    }

    termRef.current = term;
    fitAddonRef.current = fitAddon;

    const ro = new ResizeObserver(() => {
      requestAnimationFrame(() => {
        try {
          fitAddon.fit();
        } catch {
          // ignore fit errors during resize
        }
      });
    });

    if (terminalContainerRef.current) {
      ro.observe(terminalContainerRef.current);
    }
    resizeObserverRef.current = ro;

    setTimeout(() => {
      try {
        fitAddon.fit();
      } catch {
        // ignore
      }
    }, 100);

    term.focus();

    const token = localStorage.getItem('token');
    const wsUrl = `ws://${window.location.hostname}:3001/ws/terminal?token=${token}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      sendMessage({
        action: 'join_session',
        request_id: Number(requestId),
        server_id: Number(serverId),
      });
    };

    ws.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data);
        const type = msg.type as string;

        switch (type) {
          case 'terminal_output':
            writeToTerminal(msg.data as string);
            break;

          case 'session_created': {
            const info: SessionInfo = {
              sessionId: msg.session_id as number,
              serverHostname: msg.server_hostname as string,
              serverIp: msg.server_ip as string,
              serverPort: msg.server_port as number,
              username: msg.username as string,
              expiresAt: msg.expires_at as string,
            };
            setSessionInfo(info);
            if (info.expiresAt) {
              const remainingMs = new Date(info.expiresAt).getTime() - Date.now();
              setRemaining(formatRemaining(remainingMs));
            }
            break;
          }

          case 'ssh_ready':
            setSshReady(true);
            writeToTerminal('\r\n\x1b[32mSSH connection established\x1b[0m\r\n\n');
            setTimeout(() => fitAddon.fit(), 50);
            break;

          case 'session_error':
            writeToTerminal(`\r\n\x1b[31mError: ${msg.message as string}\x1b[0m\r\n`);
            break;

          case 'session_ended': {
            const reason = (msg.reason as string) || 'Session ended';
            writeToTerminal(`\r\n\x1b[33m${reason}\x1b[0m\r\n`);
            setTerminated(true);
            break;
          }

          case 'session_timer': {
            const expiresAt = msg.expires_at as string;
            const remainingSec = msg.remaining_seconds as number;
            if (expiresAt) {
              const ms = new Date(expiresAt).getTime() - Date.now();
              setRemaining(formatRemaining(ms));
            } else if (typeof remainingSec === 'number') {
              setRemaining(formatRemaining(remainingSec * 1000));
            }
            break;
          }

          case 'session_reconnect':
            writeToTerminal(`\r\n\x1b[32mSession reconnected\x1b[0m\r\n`);
            setSshReady(true);
            setTerminated(false);
            break;
        }
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      setConnected(false);
      if (!terminated) {
        writeToTerminal('\r\n\x1b[33mConnection closed\x1b[0m\r\n');
      }
    };

    ws.onerror = () => {
      writeToTerminal('\r\n\x1b[31mWebSocket connection error\x1b[0m\r\n');
    };

    term.onData((data) => {
      sendMessage({ action: 'terminal_input', data });
    });

    term.onResize(({ cols, rows }) => {
      sendMessage({ action: 'terminal_resize', cols, rows });
    });

    return () => {
      ro.disconnect();
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
      term.dispose();
    };
  }, [serverId, requestId, sendMessage, writeToTerminal, formatRemaining, terminated]);

  useEffect(() => {
    if (!sessionInfo.expiresAt) return;

    const interval = setInterval(() => {
      const ms = new Date(sessionInfo.expiresAt!).getTime() - Date.now();
      if (ms <= 0) {
        setRemaining('00:00:00');
        setTimerExpired(true);
        clearInterval(interval);
      } else {
        setRemaining(formatRemaining(ms));
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [sessionInfo.expiresAt, formatRemaining]);

  const displayName = sessionInfo.username || user?.username || 'user';
  const displayServer = sessionInfo.serverHostname || `Server #${serverId}`;
  const displayAddress = sessionInfo.serverIp
    ? `${sessionInfo.serverIp}:${sessionInfo.serverPort || 22}`
    : '';

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[#1a1b2e]">
      <header className="flex h-12 shrink-0 items-center justify-between bg-slate-900 border-b border-slate-700 px-4">
        <div className="flex items-center gap-3 min-w-0">
          <span className="inline-flex items-center gap-1.5 rounded bg-blue-600/20 px-2.5 py-1 text-xs font-semibold text-blue-400">
            <span className="h-1.5 w-1.5 rounded-full bg-blue-400" />
            SSH ACCESS
          </span>
          {sshReady && (
            <span className="inline-flex items-center gap-1.5 rounded bg-green-600/20 px-2.5 py-1 text-xs font-semibold text-green-400">
              <span className="h-1.5 w-1.5 rounded-full bg-green-400" />
              Connected
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 text-sm text-slate-300 min-w-0 px-4">
          <span className="truncate font-medium text-slate-100">{displayName}</span>
          <span className="text-slate-500">@</span>
          <span className="truncate font-medium text-slate-100">{displayServer}</span>
          {displayAddress && (
            <>
              <span className="text-slate-600 mx-1">|</span>
              <span className="text-slate-400 text-xs font-mono">{displayAddress}</span>
            </>
          )}
        </div>

        <div className="flex items-center gap-3">
          {remaining && (
            <span className={`flex items-center gap-1.5 text-sm font-mono tabular-nums ${
              timerExpired ? 'text-red-400' : remaining.startsWith('00:0') ? 'text-yellow-400' : 'text-slate-300'
            }`}>
              <Clock className="h-3.5 w-3.5" />
              {remaining}
            </span>
          )}
          <button
            onClick={handleTerminate}
            disabled={terminated}
            className="flex items-center gap-1.5 rounded-lg bg-red-600/80 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-500 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Power className="h-3.5 w-3.5" />
            Terminate
          </button>
          <button
            onClick={() => window.close()}
            className="flex items-center gap-1.5 rounded-lg bg-slate-700/80 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-600 transition"
          >
            <X className="h-3.5 w-3.5" />
            Close Tab
          </button>
        </div>
      </header>

      <div className="flex-1 min-h-0 p-0">
        <div
          ref={terminalContainerRef}
          className="h-full w-full"
          style={{ height: '100%' }}
        />
      </div>
    </div>
  );
}
