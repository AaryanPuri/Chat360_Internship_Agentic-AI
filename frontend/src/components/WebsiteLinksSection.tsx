import React, { useEffect, useState } from "react";
import axios from "axios";
import { BASE_URL } from "../lib/api";

interface WebsiteLink {
  id: number;
  url: string;
  title?: string;
  created_at?: string;
  updated_at?: string;
}

interface WebsiteLinksSectionProps {
  knowledgeBaseId: string;
}

const WebsiteLinksSection: React.FC<WebsiteLinksSectionProps> = ({ knowledgeBaseId }) => {
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [links, setLinks] = useState<WebsiteLink[]>([]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingUrl, setEditingUrl] = useState("");
  const [editingTitle, setEditingTitle] = useState("");
  const [loading, setLoading] = useState(false);

  const fetchLinks = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("access_token");
      const res = await axios.get(`${BASE_URL}/analytics/knowledgebase/links/?kb_uuid=${knowledgeBaseId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setLinks(res.data.links);
    } catch {
      setLinks([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (knowledgeBaseId) fetchLinks();
    // eslint-disable-next-line
  }, [knowledgeBaseId]);

  const handleAddUrl = async () => {
    if (!url || !knowledgeBaseId) {
      alert("Knowledge base is not selected or URL is missing.");
      return;
    }
    console.log("Adding link", { kb_uuid: knowledgeBaseId, url, title });
    try {
      const token = localStorage.getItem("access_token");
      await axios.post(
        `${BASE_URL}/analytics/knowledgebase/add-link/`,
        { kb_uuid: knowledgeBaseId, url, title },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setUrl("");
      setTitle("");
      fetchLinks();
    } catch (e) {
      console.error("Add link error", e);
    }
  };

  const handleRemoveUrl = async (id: number) => {
    try {
      const token = localStorage.getItem("access_token");
      await axios.delete(`${BASE_URL}/analytics/knowledgebase_delete_link/${id}/?kb_uuid=${knowledgeBaseId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      fetchLinks();
    } catch {}
  };

  const handleEditUrl = (link: WebsiteLink) => {
    setEditingId(link.id);
    setEditingUrl(link.url);
    setEditingTitle(link.title || "");
  };

  const handleUpdateUrl = async () => {
    if (!editingUrl || editingId === null) return;
    try {
      const token = localStorage.getItem("access_token");
      await axios.put(
        `${BASE_URL}/analytics/website-link/${editingId}/`,
        { url: editingUrl, title: editingTitle },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setEditingId(null);
      setEditingUrl("");
      setEditingTitle("");
      fetchLinks();
    } catch {}
  };

  return (
    <div>
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          value={url}
          onChange={e => setUrl(e.target.value)}
          placeholder="Enter website URL"
          className="flex-1 rounded border border-gray-700 bg-gray-800 px-3 py-2 text-gray-200 focus:outline-none"
        />
        <input
          type="text"
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder="Optional title"
          className="flex-1 rounded border border-gray-700 bg-gray-800 px-3 py-2 text-gray-200 focus:outline-none"
        />
        <button
          onClick={handleAddUrl}
          className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
          disabled={loading}
        >
          Add
        </button>
      </div>
      <ul className="divide-y divide-gray-800">
        {loading ? (
          <li className="text-gray-500 text-sm">Loading...</li>
        ) : links.length === 0 ? (
          <li className="text-gray-500 text-sm">No website links added.</li>
        ) : (
          links.map((link) => (
            <li key={link.id} className="flex items-center justify-between py-2">
              {editingId === link.id ? (
                <>
                  <input
                    type="text"
                    value={editingUrl}
                    onChange={e => setEditingUrl(e.target.value)}
                    className="flex-1 rounded border border-gray-700 bg-gray-800 px-2 py-1 text-gray-200 focus:outline-none"
                  />
                  <input
                    type="text"
                    value={editingTitle}
                    onChange={e => setEditingTitle(e.target.value)}
                    className="flex-1 rounded border border-gray-700 bg-gray-800 px-2 py-1 text-gray-200 focus:outline-none ml-2"
                    placeholder="Optional title"
                  />
                  <button
                    onClick={handleUpdateUrl}
                    className="rounded bg-green-600 px-2 py-1 text-xs text-white hover:bg-green-700 ml-2"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => setEditingId(null)}
                    className="rounded bg-gray-600 px-2 py-1 text-xs text-white hover:bg-gray-700 ml-2"
                  >
                    Cancel
                  </button>
                </>
              ) : (
                <>
                  <div className="flex-1">
                    <a href={link.url} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">
                      {link.title ? `${link.title} (${link.url})` : link.url}
                    </a>
                  </div>
                  <button
                    onClick={() => handleEditUrl(link)}
                    className="rounded bg-yellow-600 px-2 py-1 text-xs text-white hover:bg-yellow-700 ml-2"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleRemoveUrl(link.id)}
                    className="rounded bg-red-600 px-2 py-1 text-xs text-white hover:bg-red-700 ml-2"
                  >
                    Remove
                  </button>
                </>
              )}
            </li>
          ))
        )}
      </ul>
    </div>
  );
};

export default WebsiteLinksSection;
