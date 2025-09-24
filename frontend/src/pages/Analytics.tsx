import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { jwtDecode } from "jwt-decode";
import { AppSidebar } from "@/components/app-sidebar"
import { Separator } from "@/components/ui/separator"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { BASE_URL } from "../lib/api";

function isTokenValid(token: string | null): boolean {
  if (!token) return false;
  try {
    const decoded: any = jwtDecode(token);
    if (!decoded.exp) return false;
    const now = Math.floor(Date.now() / 1000);
    return decoded.exp > now;
  } catch {
    return false;
  }
}

export default function Home() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const handleIndexDocuments = async () => {
    setLoading(true);
    try {
      // TODO: Replace with actual API endpoint
      await fetch(`${BASE_URL}/index-documents`, { method: "POST" });
      alert("Indexing started!");
    } catch (error) {
      alert("Failed to start indexing.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!isTokenValid(token)) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      navigate("/login");
    }
  }, [navigate]);

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-14 shrink-0 items-center gap-2">
          <div className="flex flex-1 items-center gap-2 px-3">
            <SidebarTrigger />
            <Separator orientation="vertical" className="mr-2 h-4" />
            {/* Index Documents Button */}
            <button
              className="ml-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
              onClick={handleIndexDocuments}
              disabled={loading}
            >
              {loading ? "Indexing..." : "Index Documents"}
            </button>
          </div>
        </header>
      </SidebarInset>
    </SidebarProvider>
  )
}