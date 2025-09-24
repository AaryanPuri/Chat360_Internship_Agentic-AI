import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { AppSidebar } from "@/components/app-sidebar";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { jwtDecode } from "jwt-decode";
import { BASE_URL } from "../lib/api";

interface BotConfig {
  assistant_name: string;
  updated_at: string;
  assistant_uuid: string;
}

export default function SavedBots() {
  const [bots, setBots] = useState<BotConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      navigate("/login");
      return;
    }
    try {
      jwtDecode(token);
    } catch {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      navigate("/login");
      return;
    }
    fetchBots();
  }, [navigate]);

  const fetchBots = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("access_token");
      const res = await axios.get(`${BASE_URL}/analytics/assistant/configs/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setBots(res.data);
    } catch {
      setBots([]);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (assistant_uuid: string) => {
    if (!window.confirm("Are you sure you want to delete this bot?")) return;
    try {
      const token = localStorage.getItem("access_token");
      await axios.post(`${BASE_URL}/analytics/assistant/config/${assistant_uuid}/delete/`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      fetchBots();
    } catch {
      alert("Failed to delete bot");
    }
  };

  const handleEdit = (assistant_uuid: string) => {
    navigate(`/ai-assistant/config?uuid=${assistant_uuid}`);
  };

  const handleCreateNew = () => {
    navigate("/ai-assistant/config");
  };

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-14 items-center justify-between border-b border-gray-800 bg-gray-900 px-6">
          <div className="flex items-center gap-4">
            <SidebarTrigger className="text-gray-400 hover:text-white" />
            <span className="text-xl font-semibold text-white">Saved Bots</span>
          </div>
          <button
            className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
            onClick={handleCreateNew}
          >
            Create New
          </button>
        </header>
        <main className="p-8">
          {loading ? (
            <div className="text-gray-400">Loading...</div>
          ) : bots.length === 0 ? (
            <div className="text-gray-400">No saved bots found.</div>
          ) : (
            <div className="space-y-4">
              {bots.map((bot) => (
                <div key={bot.assistant_uuid} className="flex items-center justify-between rounded-lg bg-gray-800 p-4">
                  <div>
                    <div className="text-lg font-semibold text-white">{bot.assistant_name}</div>
                    <div className="text-xs text-gray-400">Last updated: {new Date(bot.updated_at).toLocaleString()}</div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700"
                      onClick={() => handleEdit(bot.assistant_uuid)}
                    >
                      Edit
                    </button>
                    <button
                      className="rounded bg-red-600 px-3 py-1 text-sm text-white hover:bg-red-700"
                      onClick={() => handleDelete(bot.assistant_uuid)}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
