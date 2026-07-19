import { useEffect, useRef, useState, useCallback } from 'react';
import { Play, Monitor, Clock, User, Server, X, Loader2 } from 'lucide-react';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import 'xterm/css/xterm.css';
import { useAuth } from '../AuthContext';
import * as api from '../api';
import type { Session } from '../types';

interface RecordingEntry {
  timestamp: number;
  event: string;
  data: string;
}

function formatDuration(startedAt: string, endedAt: string | null): string {
  if (!endedAt) return 'In progress';
  const start = new Date(startedAt).getTime();
  const end = new Date(endedAt).getTime();
  const totalSec = Math.floor((end - start) / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function RecordingModal({
  sessionId,
  onClose,
}: {
  sessionId: number;
  onClose: () => void;
}) {
  const terminalContainerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const timeoutRef = useRef<number | null>(null);
  const currentIndexRef = useRef(0);
  const entriesRef = useRef<RecordingEntry[]>([]);
  const startTimeRef = useRef(0);

  const initTerminal = useCallback(() => {
    if (!terminalContainerRef.current) return;

    const term = new Terminal({
      cursorStyle: 'bar',
      cursorBlink: false,
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
      },
      disableStdin: true,
      allowTransparency: false,
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(terminalContainerRef.current);
    termRef.current = term;
    fitAddonRef.current = fitAddon;

    try {
      fitAddon.fit();
    } catch {
      // ignore fit errors
    }

    setTimeout(() => {
      try {
        fitAddon.fit();
      } catch {
        // ignore
      }
    }, 100);
  }, []);

  useEffect(() => {
    initTerminal();

    const ro = new ResizeObserver(() => {
      requestAnimationFrame(() => {
        try {
          fitAddonRef.current?.fit();
        } catch {
          // ignore
        }
      });
    });
    if (terminalContainerRef.current) {
      ro.observe(terminalContainerRef.current);
    }

    api
      .getSessionRecording(sessionId)
      .then(async (blob) => {
        const text = await blob.text();
        const entries: RecordingEntry[] = JSON.parse(text);
        entries.sort((a, b) => a.timestamp - b.timestamp);
        entriesRef.current = entries;
        setLoading(false);
        if (entries.length === 0) {
          setError('Recording is empty');
        }
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load recording');
        setLoading(false);
      });

    return () => {
      ro.disconnect();
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      termRef.current?.dispose();
    };
  }, [sessionId, initTerminal]);

  const playRecording = useCallback(() => {
    const entries = entriesRef.current;
    if (entries.length === 0) return;

    setPlaying(true);
    termRef.current?.reset();
    currentIndexRef.current = 0;
    startTimeRef.current = Date.now();

    const scheduleNext = () => {
      if (currentIndexRef.current >= entries.length) {
        setPlaying(false);
        setProgress(100);
        return;
      }

      const entry = entries[currentIndexRef.current];
      const elapsed = Date.now() - startTimeRef.current;
      const delay = Math.max(0, entry.timestamp - elapsed);

      timeoutRef.current = window.setTimeout(() => {
        if (entry.event === 'terminal_output' || entry.event === 'data') {
          termRef.current?.write(entry.data);
        }
        currentIndexRef.current++;
        setProgress(Math.round((currentIndexRef.current / entries.length) * 100));
        scheduleNext();
      }, delay);
    };

    scheduleNext();
  }, []);

  const pauseRecording = useCallback(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setPlaying(false);
  }, []);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black/90">
      <div className="flex h-12 shrink-0 items-center justify-between bg-slate-900 border-b border-slate-700 px-4">
        <h3 className="text-sm font-semibold text-slate-200">
          Recording Replay — Session #{sessionId}
        </h3>
        <div className="flex items-center gap-3">
          {!loading && !error && (
            <>
              {playing ? (
                <button
                  onClick={pauseRecording}
                  className="rounded-lg bg-yellow-600/80 px-3 py-1.5 text-xs font-medium text-white hover:bg-yellow-500 transition"
                >
                  Pause
                </button>
              ) : (
                <button
                  onClick={playRecording}
                  disabled={entriesRef.current.length === 0}
                  className="flex items-center gap-1.5 rounded-lg bg-green-600/80 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-500 transition disabled:opacity-50"
                >
                  <Play className="h-3.5 w-3.5" />
                  {entriesRef.current.length > 0 && currentIndexRef.current > 0 ? 'Replay' : 'Play'}
                </button>
              )}
              <span className="text-xs text-slate-400 min-w-[3rem] text-right">
                {loading ? '' : `${progress}%`}
              </span>
            </>
          )}
          <div className="h-5 w-px bg-slate-700" />
          <button
            onClick={onClose}
            className="flex items-center gap-1.5 rounded-lg bg-slate-700/80 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-600 transition"
          >
            <X className="h-3.5 w-3.5" />
            Close
          </button>
        </div>
      </div>

      <div className="flex-1 min-h-0 p-2">
        {loading ? (
          <div className="flex h-full items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
          </div>
        ) : error ? (
          <div className="flex h-full flex-col items-center justify-center gap-3">
            <div className="rounded-full bg-red-600/10 p-4">
              <X className="h-8 w-8 text-red-400" />
            </div>
            <p className="text-sm text-red-400">{error}</p>
          </div>
        ) : (
          <div
            ref={terminalContainerRef}
            className="h-full w-full rounded border border-slate-700 overflow-hidden"
          />
        )}
      </div>
    </div>
  );
}

export default function SessionRecordingsPage() {
  const { user } = useAuth();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [allUsers, setAllUsers] = useState<{ id: number; username: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedUserId, setSelectedUserId] = useState<string>('');
  const [playSessionId, setPlaySessionId] = useState<number | null>(null);

  const isSuperuser = user?.role === 'admin';
  const isAdmin = user?.role === 'manager';
  const isRegularUser = user?.role === 'user';

  useEffect(() => {
    if (isRegularUser) {
      setLoading(false);
      return;
    }

    api
      .getSessions()
      .then((data) => {
        let filtered = data;

        if (isAdmin && user?.company_id) {
          filtered = data.filter(
            (s) => (s as Record<string, unknown>).company_id === user.company_id,
          );
        }

        if (isSuperuser && selectedUserId) {
          filtered = data.filter(
            (s) => s.user_id === Number(selectedUserId),
          );
        }

        setSessions(filtered);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [user, isAdmin, isSuperuser, isRegularUser, selectedUserId]);

  useEffect(() => {
    if (isSuperuser) {
      api.getUsers().then(setAllUsers).catch(console.error);
    }
  }, [isSuperuser]);

  const recordings = sessions.filter(
    (s) => s.recording_path || s.status === 'terminated' || s.status === 'expired',
  );

  if (isRegularUser) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="bg-red-600/10 p-4 rounded-full inline-flex mb-4">
            <X className="w-8 h-8 text-red-400" />
          </div>
          <h2 className="text-xl font-semibold text-red-400">Access Denied</h2>
          <p className="text-slate-400 mt-2">
            You do not have permission to view session recordings.
          </p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">Loading recordings...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <h1 className="text-2xl font-bold text-white">Session Recordings</h1>
        {isSuperuser && allUsers.length > 0 && (
          <div className="flex items-center gap-2">
            <User className="h-4 w-4 text-slate-400" />
            <select
              value={selectedUserId}
              onChange={(e) => setSelectedUserId(e.target.value)}
              className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
            >
              <option value="">All Users</option>
              {allUsers.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.username}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {recordings.length === 0 ? (
        <div className="bg-slate-800 rounded-xl p-12 flex flex-col items-center justify-center text-slate-500">
          <Monitor className="w-12 h-12 mb-3" />
          <p className="text-lg">No recordings found</p>
          <p className="text-sm text-slate-600 mt-1">
            Completed sessions with recordings will appear here.
          </p>
        </div>
      ) : (
        <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-slate-400 text-left">
                  <th className="px-4 py-3 font-medium">
                    <div className="flex items-center gap-1.5">
                      <User className="h-3.5 w-3.5" />
                      Username
                    </div>
                  </th>
                  <th className="px-4 py-3 font-medium">Company</th>
                  <th className="px-4 py-3 font-medium">
                    <div className="flex items-center gap-1.5">
                      <Server className="h-3.5 w-3.5" />
                      Server Name
                    </div>
                  </th>
                  <th className="px-4 py-3 font-medium">
                    <div className="flex items-center gap-1.5">
                      <Clock className="h-3.5 w-3.5" />
                      Duration
                    </div>
                  </th>
                  <th className="px-4 py-3 font-medium">Date/Time</th>
                  <th className="px-4 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700">
                {recordings.map((s) => {
                  const extra = s as Record<string, unknown>;
                  return (
                    <tr key={s.id} className="hover:bg-slate-700/50 transition">
                      <td className="px-4 py-3 text-slate-200">
                        {s.username || `User #${s.user_id}`}
                      </td>
                      <td className="px-4 py-3 text-slate-300">
                        {(extra.company_name as string) || '-'}
                      </td>
                      <td className="px-4 py-3 text-slate-200">
                        {s.server_hostname || `Server #${s.server_id}`}
                      </td>
                      <td className="px-4 py-3 text-slate-200 font-mono text-xs">
                        {formatDuration(s.started_at, s.ended_at)}
                      </td>
                      <td className="px-4 py-3 text-slate-400 text-xs">
                        {formatDate(s.started_at)}
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => setPlaySessionId(s.id)}
                          className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg px-3 py-1.5 text-xs transition"
                        >
                          <Play className="h-3.5 w-3.5" />
                          Play
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {playSessionId !== null && (
        <RecordingModal
          sessionId={playSessionId}
          onClose={() => setPlaySessionId(null)}
        />
      )}
    </div>
  );
}
