import  { useEffect, useState } from "react";
import axios from "axios";
import { AppSidebar } from "../components/app-sidebar";
import { SidebarProvider } from "../components/ui/sidebar";
import { Link } from "react-router-dom";
import { BASE_URL } from "../lib/api";

interface KnowledgeBase {
  id: number;
  name: string;
  uuid: string;
  created_at: string;
  updated_at: string;
}

export default function KnowledgeBases() {
  const [bases, setBases] = useState<KnowledgeBase[]>([]);
  const [newName, setNewName] = useState("");
  const [loading, setLoading] = useState(false);

  const fetchBases = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("access_token");
      const res = await axios.get(`${BASE_URL}/analytics/knowledge-bases/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setBases(res.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBases();
  }, []);

  const handleCreate = async () => {
    if (!newName) return;
    setLoading(true);
    try {
      const token = localStorage.getItem("access_token");
      await axios.post(
        `${BASE_URL}/analytics/create-knowledge-base/`,
        { name: newName },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setNewName("");
      fetchBases();
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    setLoading(true);
    try {
      const token = localStorage.getItem("access_token");
      await axios.delete(`${BASE_URL}/analytics/delete-knowledge-base/${id}/`, {
        headers: { Authorization: `Bearer ${token}` } 
      });
      fetchBases();
    } finally {
      setLoading(false);
    }
  };

  return (
    <SidebarProvider>
      <div className="flex min-h-screen">
        <AppSidebar />
        <div className="max-w-xl mx-auto p-6 flex-1">
          <h2 className="text-2xl font-bold mb-4">Knowledge Bases</h2>
          <div className="flex gap-2 mb-6">
            <input
              className="border px-3 py-2 rounded w-full"
              placeholder="New knowledge base name"
              value={newName}
              onChange={e => setNewName(e.target.value)}
              disabled={loading}
            />
            <button
              className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50"
              onClick={handleCreate}
              disabled={loading || !newName}
            >
              Create
            </button>
          </div>
          <ul className="divide-y divide-gray-200">
            {bases.map(base => (
              <li key={base.id} className="flex items-center justify-between py-3">
                <Link to={`/knowledge-bases/${base.id}`} className="font-semibold hover:underline">
                  {base.name}
                </Link>
                <button
                  className="text-red-500 hover:underline text-sm"
                  onClick={() => handleDelete(base.id)}
                  disabled={loading}
                >
                  Delete
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </SidebarProvider>
  );
}
