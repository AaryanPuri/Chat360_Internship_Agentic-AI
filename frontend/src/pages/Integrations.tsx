import { AppSidebar } from "@/components/app-sidebar";
import { Separator } from "@/components/ui/separator";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";

import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardFooter,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const handleConnectZoho = () => {
  const clientId = "1000.65S5BUWES8VYXZA5JYV4K7JTZ1A9BX"; // Replace with your actual Client ID, potentially from env vars
  const redirectUri = "http://localhost:8000/oauth/zoho"; // Backend callback URL
  // Score for reading leads
  const scope = "ZohoCRM.coql.READ,ZohoCRM.modules.ALL,ZohoCRM.settings.fields.READ";
  const responseType = "code";

  const authUrl = `https://accounts.zoho.in/oauth/v2/auth?response_type=${responseType}&client_id=${clientId}&scope=${scope}&redirect_uri=${encodeURIComponent(redirectUri)}`;

  // Open the Zoho authorization page in a new tab
  window.open(authUrl, '_blank');
};

export default function Home() {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-14 shrink-0 items-center gap-2">
          <div className="flex flex-1 items-center gap-2 px-3">
            <SidebarTrigger />
            <Separator orientation="vertical" className="mr-2 h-4" />
          </div>
        </header>
        <div className="flex flex-col h-screen w-full bg-black text-white overflow-hidden">
          <Card className="w-[350px] rounded-2xl m-auto">
            <CardHeader>
              <CardTitle>Zoho CRM</CardTitle>
              <CardDescription>
                Connect your Zoho CRM account to use it with your AI assistant.
              </CardDescription>
            </CardHeader>
            <CardFooter className="flex justify-between">
              <Button variant="outline" className="rounded-full">Cancel</Button>
              <Button className="rounded-full" onClick={handleConnectZoho}>Connect</Button>
            </CardFooter>
          </Card>
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
