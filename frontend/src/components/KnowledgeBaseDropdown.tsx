import { useEffect, useState } from "react";
import axios from "axios";
import { BASE_URL } from "../lib/api";

interface KnowledgeBase {
  id: number;
  name: string;
  uuid: string;
}

interface Props {
  value: string | null;
  onChange: (uuid: string) => void;
  modelUuid: string; // Pass the assistant config UUID
}

export default function KnowledgeBaseDropdown({ value, onChange, modelUuid }: Props) {
  const [bases, setBases] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
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
    fetchBases();
  }, []);

  const handleChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const kbUuid = e.target.value;
    onChange(kbUuid); // update parent/UI
    if (!kbUuid || !modelUuid) return;
    setSaving(true);
    try {
      const token = localStorage.getItem("access_token");
      await axios.post(
        `${BASE_URL}/analytics/set_assistant_kb/`,
        { model_uuid: modelUuid, knowledge_base: kbUuid },
        { headers: { Authorization: `Bearer ${token}` } }
      );
    } catch (err) {
      console.error("Failed to set knowledge base", err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <select
      className="border px-3 py-2 rounded w-full mb-4"
      value={value || ""}
      onChange={handleChange}
      disabled={loading || saving}
    >
      <option value="">Select Knowledge Base</option>
      {bases.map(base => (
        <option key={base.uuid} value={base.uuid}>{base.name}</option>
      ))}
    </select>
  );
}
