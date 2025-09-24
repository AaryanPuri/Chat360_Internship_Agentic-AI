import { FiLogOut, FiUser } from 'react-icons/fi';
import { useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';

const Sidebar: React.FC = () => {
  const navigate = useNavigate();
  const [username, setUsername] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        setUsername(payload.username || payload.user || null);
      } catch {
        setUsername(null);
      }
    } else {
      setUsername(null);
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    navigate('/login');
  };

  return (
    <aside className="h-screen w-20 bg-neutral-900 flex flex-col justify-between items-center py-4 border-r border-neutral-800 fixed left-0 top-0 z-40">
      {/* Top: Logo or Icon */}
      <div className="flex flex-col items-center gap-6">
        <img src="/vite.svg" alt="Logo" className="w-8 h-8 mb-2" />
        {/* Add navigation icons here if needed */}
      </div>
      {/* Bottom: Profile & Logout */}
      <div className="flex flex-col items-center gap-3 mb-2">
        <div className="flex flex-col items-center">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-400 to-purple-500 flex items-center justify-center text-white text-lg font-semibold">
            {username ? username.charAt(0).toUpperCase() : <FiUser size={20} />}
          </div>
          {username && <span className="text-xs text-white mt-1 font-medium text-center max-w-[60px] truncate">{username}</span>}
        </div>
        <button onClick={handleLogout} className="mt-2 text-slate-400 hover:text-red-400 p-1" title="Logout">
          <FiLogOut size={20} />
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;