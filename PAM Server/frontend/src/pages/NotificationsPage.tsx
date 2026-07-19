import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bell,
  FileText,
  CheckCircle,
  XCircle,
  UserPlus,
  Play,
  Square,
  CreditCard,
} from 'lucide-react';
import { useAuth } from '../AuthContext';
import * as api from '../api';
import type { Notification } from '../types';

const iconMap: Record<string, React.ReactNode> = {
  system: <Bell className="h-5 w-5" />,
  new_request: <FileText className="h-5 w-5" />,
  request_approved: <CheckCircle className="h-5 w-5" />,
  request_rejected: <XCircle className="h-5 w-5" />,
  user_created: <UserPlus className="h-5 w-5" />,
  session_started: <Play className="h-5 w-5" />,
  session_ended: <Square className="h-5 w-5" />,
  billing: <CreditCard className="h-5 w-5" />,
};

function getIcon(notification: Notification) {
  const extra = notification as Record<string, unknown>;
  const notifType = (extra.notification_type as string) || '';
  const icon = iconMap[notifType];
  if (icon) return icon;
  return <Bell className="h-5 w-5" />;
}

function formatTime(dateStr: string): string {
  const d = new Date(dateStr);
  const now = Date.now();
  const diff = now - d.getTime();
  if (diff < 60000) return 'Just now';
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  if (diff < 604800000) return `${Math.floor(diff / 86400)}d ago`;
  return d.toLocaleDateString();
}

export default function NotificationsPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchNotifications = () => {
    api
      .getNotifications()
      .then(setNotifications)
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (!user) return;
    fetchNotifications();
  }, [user]);

  const handleMarkAllRead = async () => {
    try {
      await api.markAllNotificationsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    } catch (err) {
      console.error(err);
    }
  };

  const handleNotificationClick = async (notification: Notification) => {
    try {
      if (!notification.read) {
        await api.markNotificationRead(notification.id);
        setNotifications((prev) =>
          prev.map((n) => (n.id === notification.id ? { ...n, read: true } : n)),
        );
      }
    } catch (err) {
      console.error(err);
    }

    const extra = notification as Record<string, unknown>;
    const link = extra.link as string | undefined;
    if (link) {
      navigate(link);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">Loading notifications...</div>
      </div>
    );
  }

  const hasUnread = notifications.some((n) => !n.read);

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Notifications</h1>
        {hasUnread && (
          <button
            onClick={handleMarkAllRead}
            className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg px-4 py-2 text-sm transition"
          >
            Mark All Read
          </button>
        )}
      </div>

      {notifications.length === 0 ? (
        <div className="bg-slate-800 rounded-xl p-12 flex flex-col items-center justify-center text-slate-500">
          <Bell className="w-12 h-12 mb-3" />
          <p className="text-lg">No notifications</p>
          <p className="text-sm text-slate-600 mt-1">You're all caught up!</p>
        </div>
      ) : (
        <div className="space-y-3">
          {notifications.map((n) => {
            const extra = n as Record<string, unknown>;
            const link = extra.link as string | undefined;
            return (
              <div
                key={n.id}
                onClick={() => handleNotificationClick(n)}
                className={`bg-slate-800 rounded-xl border border-slate-700 p-4 hover:bg-slate-700/50 transition cursor-pointer ${
                  !n.read ? 'border-l-4 border-l-blue-500' : 'opacity-60'
                }`}
              >
                <div className="flex items-start gap-3">
                  <div className={`mt-0.5 ${!n.read ? 'text-blue-400' : 'text-slate-500'}`}>
                    {getIcon(n)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-100">{n.title}</p>
                    <p className="text-sm text-slate-400 mt-0.5">{n.message}</p>
                    {link && (
                      <p className="text-xs text-blue-400 mt-1 hover:underline">
                        View details
                      </p>
                    )}
                  </div>
                  <div className="flex flex-col items-end gap-1 shrink-0">
                    <span className="text-xs text-slate-500 whitespace-nowrap">
                      {formatTime(n.created_at)}
                    </span>
                    {!n.read && (
                      <span className="h-2 w-2 rounded-full bg-blue-500" />
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
