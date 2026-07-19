import { useState } from 'react';
import { User, Lock, Eye, EyeOff, Save } from 'lucide-react';
import { useAuth } from '../AuthContext';
import * as api from '../api';

export default function SettingsPage() {
  const { user } = useAuth();

  // Username state
  const [newUsername, setNewUsername] = useState('');
  const [usernameMsg, setUsernameMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [usernameLoading, setUsernameLoading] = useState(false);

  // Password state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [passwordMsg, setPasswordMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [passwordLoading, setPasswordLoading] = useState(false);

  const handleChangeUsername = async () => {
    setUsernameMsg(null);
    if (!newUsername.trim()) {
      setUsernameMsg({ type: 'error', text: 'Please enter a new username.' });
      return;
    }
    setUsernameLoading(true);
    try {
      await (api.changeUsername as (name: string) => Promise<void>)(newUsername.trim());
      setUsernameMsg({ type: 'success', text: 'Username updated successfully! Please log in again.' });
      setNewUsername('');
    } catch (err) {
      setUsernameMsg({ type: 'error', text: err instanceof Error ? err.message : 'Failed to update username.' });
    } finally {
      setUsernameLoading(false);
    }
  };

  const handleChangePassword = async () => {
    setPasswordMsg(null);
    if (!currentPassword) {
      setPasswordMsg({ type: 'error', text: 'Current password is required.' });
      return;
    }
    if (newPassword.length < 6) {
      setPasswordMsg({ type: 'error', text: 'New password must be at least 6 characters.' });
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordMsg({ type: 'error', text: 'New password and confirmation do not match.' });
      return;
    }
    setPasswordLoading(true);
    try {
      await api.changePassword(currentPassword, newPassword);
      setPasswordMsg({ type: 'success', text: 'Password changed successfully!' });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err) {
      setPasswordMsg({ type: 'error', text: err instanceof Error ? err.message : 'Failed to change password.' });
    } finally {
      setPasswordLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-white">Settings</h1>

      {/* Change Username */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-6">
        <div className="flex items-center gap-2 mb-4">
          <User className="h-5 w-5 text-blue-400" />
          <h2 className="text-lg font-semibold text-white">Change Username</h2>
        </div>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-slate-400 mb-1">Current Username</label>
            <input
              type="text"
              value={user?.username || ''}
              readOnly
              className="bg-slate-700/30 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-500 w-full cursor-not-allowed"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1">New Username</label>
            <input
              type="text"
              value={newUsername}
              onChange={(e) => setNewUsername(e.target.value)}
              placeholder="Enter new username"
              className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 w-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition placeholder-slate-500"
            />
          </div>
          {usernameMsg && (
            <p className={`text-sm ${usernameMsg.type === 'success' ? 'text-green-400' : 'text-red-400'}`}>
              {usernameMsg.text}
            </p>
          )}
          <button
            onClick={handleChangeUsername}
            disabled={usernameLoading}
            className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium rounded-lg px-4 py-2 text-sm transition"
          >
            <Save className="h-4 w-4" />
            {usernameLoading ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      {/* Change Password */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Lock className="h-5 w-5 text-blue-400" />
          <h2 className="text-lg font-semibold text-white">Change Password</h2>
        </div>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-slate-400 mb-1">Current Password</label>
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder="Enter current password"
              className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 w-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition placeholder-slate-500"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1">New Password</label>
            <div className="relative">
              <input
                type={showNewPassword ? 'text' : 'password'}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Enter new password"
                className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 pr-10 text-sm text-slate-100 w-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition placeholder-slate-500"
              />
              <button
                type="button"
                onClick={() => setShowNewPassword((v) => !v)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 transition"
              >
                {showNewPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1">Confirm New Password</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Confirm new password"
              className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 w-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition placeholder-slate-500"
            />
          </div>
          {passwordMsg && (
            <p className={`text-sm ${passwordMsg.type === 'success' ? 'text-green-400' : 'text-red-400'}`}>
              {passwordMsg.text}
            </p>
          )}
          <button
            onClick={handleChangePassword}
            disabled={passwordLoading}
            className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium rounded-lg px-4 py-2 text-sm transition"
          >
            <Save className="h-4 w-4" />
            {passwordLoading ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
