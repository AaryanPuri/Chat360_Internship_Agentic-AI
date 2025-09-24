import React, { useEffect, useState, useRef } from "react";
import axios from "axios";
import { useParams } from "react-router-dom";
import { AppSidebar } from "../components/app-sidebar";
import { SidebarProvider } from "../components/ui/sidebar";
import WebsiteLinksSection from "../components/WebsiteLinksSection";
import { BASE_URL } from "../lib/api";

interface KnowledgeBase {
  id: number;
  name: string;
  uuid: string;
}

export default function KnowledgeBaseDetail() {
  const { id } = useParams();
  const [kb, setKb] = useState<KnowledgeBase | null>(null);
  const [loading, setLoading] = useState(false);
  const [knowledgeFiles, setKnowledgeFiles] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [indexTaskId, setIndexTaskId] = useState<string | null>(null);
  const [indexStatus, setIndexStatus] = useState<string | null>(null);

  useEffect(() => {
    const fetchKb = async () => {
      setLoading(true);
      try {
        const token = localStorage.getItem("access_token");
        const res = await axios.get(`${BASE_URL}/analytics/knowledge-bases/`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const found = res.data.find((b: KnowledgeBase) => String(b.id) === id);
        setKb(found || null);
      } finally {
        setLoading(false);
      }
    };
    fetchKb();
  }, [id]);

  const fetchKnowledgeFiles = async () => {
    if (!kb) return;
    const token = localStorage.getItem("access_token");
    console.log("Fetching files for KB", kb.uuid);
    const res = await axios.get(`${BASE_URL}/analytics/knowledgebase/list/?kb_uuid=${kb.uuid}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    setKnowledgeFiles(res.data.files || []);
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || !kb) return;
    setUploading(true);
    try {
      const token = localStorage.getItem("access_token");
      const formData = new FormData();
      formData.append("file", e.target.files[0]);
      formData.append("kb_uuid", kb.uuid);
      console.log("Uploading file", { kb_uuid: kb.uuid, file: e.target.files[0] });
      await axios.post(`${BASE_URL}/analytics/knowledgebase/upload/`, formData, {
        headers: { Authorization: `Bearer ${token}` } });
      fetchKnowledgeFiles();
    } catch (err) {
      alert("Failed to upload file.");
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteFile = async (fileId: number) => {
    if (!kb) return;
    try {
      const token = localStorage.getItem("access_token");
      await axios.delete(`${BASE_URL}/analytics/knowledgebase/delete/${fileId}/?kb_uuid=${kb.uuid}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      fetchKnowledgeFiles();
    } catch (err) {
      alert("Failed to delete file.");
    }
  };

  // Poll task status if indexing
  useEffect(() => {
    if (!indexTaskId) return;
    setIndexStatus("PENDING");
    const interval = setInterval(async () => {
      const token = localStorage.getItem("access_token");
      try {
        const res = await axios.get(`${BASE_URL}/analytics/get-task-status/${indexTaskId}/`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        setIndexStatus(res.data.status);
        if (res.data.status === "SUCCESS" || res.data.status === "FAILURE") {
          clearInterval(interval);
          setIndexing(false);
        }
      } catch {
        setIndexStatus("ERROR");
        clearInterval(interval);
        setIndexing(false);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [indexTaskId]);

  const handleIndexDocuments = async () => {
    if (!kb) return;
    setIndexing(true);
    setIndexStatus(null);
    try {
      const token = localStorage.getItem("access_token");
      const res = await axios.post(
        `${BASE_URL}/analytics/index-documents/`,
        { assistant_id: kb.uuid },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setIndexTaskId(res.data.task_id);
      setIndexStatus("PENDING");
    } catch (error) {
      alert("Failed to start indexing.");
      setIndexing(false);
    }
  };

  useEffect(() => {
    fetchKnowledgeFiles();
    // eslint-disable-next-line
  }, [kb]);

  return (
    <SidebarProvider>
      <div className="flex min-h-screen">
        <AppSidebar />
        <div className="max-w-xl mx-auto p-6 flex-1">
          {loading ? (
            <div>Loading...</div>
          ) : kb ? (
            <>
              <h2 className="text-2xl font-bold mb-4">{kb.name}</h2>
              <div className="text-gray-500 text-xs mb-6">UUID: {kb.uuid}</div>
              {/* Document Upload Section */}
              <div className="rounded-lg border border-gray-800 bg-gray-900 p-4 mb-6">
                <h3 className="mb-4 text-sm font-semibold text-white">Upload Documents</h3>
                <input
                  type="file"
                  accept=".pdf,.docx,.txt"
                  style={{ display: "none" }}
                  ref={fileInputRef}
                  onChange={handleFileUpload}
                  disabled={uploading}
                />
                <button
                  className="flex items-center justify-center rounded-lg border-2 border-dashed border-gray-700 py-4 text-gray-400 hover:border-gray-600 hover:text-gray-300 w-full mb-2"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                >
                  {uploading ? "Uploading..." : "Upload Knowledge Documents"}
                </button>
                <div className="text-sm text-gray-400 mb-2">
                  Supported formats: PDF, DOCX, TXT (Max 20MB per file)
                </div>
                <ul className="divide-y divide-gray-800">
                  {knowledgeFiles.length === 0 ? (
                    <li className="text-gray-500 text-sm">No documents uploaded.</li>
                  ) : (
                    knowledgeFiles.map((file: any) => (
                      <li key={file.id} className="flex items-center justify-between py-2">
                        <span className="text-gray-200">{file.name}</span>
                        <button
                          className="rounded bg-red-600 px-2 py-1 text-xs text-white hover:bg-red-700"
                          onClick={() => handleDeleteFile(file.id)}
                        >
                          Delete
                        </button>
                      </li>
                    ))
                  )}
                </ul>
              </div>
              {/* Website Links Section */}
              <div className="rounded-lg border border-gray-800 bg-gray-900 p-4 mb-6">
                <h3 className="mb-4 text-sm font-semibold text-white">Add Website Links</h3>
                <WebsiteLinksSection knowledgeBaseId={kb.uuid} />
              </div>
              {/* Index Documents Button */}
              <button
                className="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                onClick={handleIndexDocuments}
                disabled={indexing}
              >
                {indexing ? (indexStatus ? `Indexing: ${indexStatus}` : "Indexing...") : "Index Documents"}
              </button>
              {indexing && indexStatus && (
                <div className="mt-2 text-sm text-gray-400">Status: {indexStatus}</div>
              )}
            </>
          ) : (
            <div>Knowledge base not found.</div>
          )}
        </div>
      </div>
    </SidebarProvider>
  );
}
