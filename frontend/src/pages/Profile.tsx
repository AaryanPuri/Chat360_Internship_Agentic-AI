import React, { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { FiUser, FiMail, FiUserCheck } from "react-icons/fi";
import { useNavigate } from "react-router-dom";
import { BASE_URL } from "../lib/api";

interface UserProfile {
  username: string;
  first_name: string;
  last_name: string;
  email: string;
}

const Profile: React.FC = () => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    const fetchProfile = async () => {
      setLoading(true);
      setError("");
      try {
        const token = localStorage.getItem("access_token");
        if (!token) {
          navigate("/login");
          return;
        }
        const resp = await fetch(`${BASE_URL}/analytics/user/profile/`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (resp.status === 401) {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          navigate("/login");
          return;
        }
        if (!resp.ok) throw new Error("Some Error Occurred");
        const data = await resp.json();
        setUser(data);
      } catch (e: any) {
        setError(e.message || "Unknown error");
      } finally {
        setLoading(false);
      }
    };
    fetchProfile();
  }, [navigate]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gradient-to-br from-slate-900 to-indigo-900">
        <Card className="p-8 rounded-2xl shadow-2xl bg-neutral-900 text-white flex flex-col items-center">
          <div className="animate-pulse w-20 h-20 rounded-full bg-gradient-to-br from-blue-400 to-purple-500 mb-4" />
          <div className="text-lg font-semibold mb-2">Loading profile...</div>
        </Card>
      </div>
    );
  }
  if (error || !user) {
    // This block is now only for unexpected errors, not auth
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gradient-to-br from-slate-900 to-indigo-900">
        <Card className="p-8 rounded-2xl shadow-2xl bg-neutral-900 text-white flex flex-col items-center">
          <FiUser size={48} className="mb-4 text-indigo-400" />
          <div className="text-lg font-semibold mb-2">{error || "Unknown error"}</div>
          <button
            className="mt-2 px-4 py-2 rounded bg-indigo-600 hover:bg-indigo-700 text-white font-medium"
            onClick={() => navigate("/")}
          >
            Go Home
          </button>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gradient-to-br from-slate-900 to-indigo-900">
      <Card className="p-8 rounded-2xl shadow-2xl bg-neutral-900 text-white flex flex-col items-center w-full max-w-md">
        <div className="w-20 h-20 rounded-full bg-gradient-to-br from-blue-400 to-purple-500 flex items-center justify-center text-white text-4xl font-bold mb-4">
          {user.username.charAt(0).toUpperCase()}
        </div>
        <div className="text-2xl font-bold mb-1 flex items-center gap-2">
          <FiUserCheck className="text-indigo-400" />
          {user.first_name || user.last_name ? `${user.first_name} ${user.last_name}`.trim() : user.username}
        </div>
        <div className="text-indigo-300 mb-4">@{user.username}</div>
        <div className="w-full border-t border-neutral-700 my-4" />
        <div className="flex flex-col gap-2 w-full">
          <div className="flex items-center gap-2">
            <FiUser className="text-indigo-400" />
            <span className="font-medium">Username:</span>
            <span className="ml-1 text-slate-200">{user.username}</span>
          </div>
          {(user.first_name || user.last_name) && (
            <div className="flex items-center gap-2">
              <FiUserCheck className="text-indigo-400" />
              <span className="font-medium">Name:</span>
              <span className="ml-1 text-slate-200">{user.first_name} {user.last_name}</span>
            </div>
          )}
          {user.email && (
            <div className="flex items-center gap-2">
              <FiMail className="text-indigo-400" />
              <span className="font-medium">Email:</span>
              <span className="ml-1 text-slate-200">{user.email}</span>
            </div>
          )}
        </div>
        <button
          className="mt-8 px-6 py-2 rounded bg-indigo-600 hover:bg-indigo-700 text-white font-semibold shadow"
          onClick={() => navigate(-1)}
        >
          Back
        </button>
      </Card>
    </div>
  );
};

export default Profile;
