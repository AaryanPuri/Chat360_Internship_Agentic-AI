import { useState, useRef, useEffect } from "react";
import { CSSTransition } from "react-transition-group";
import { useNavigate } from 'react-router-dom';
import { AppSidebar } from '../components/app-sidebar';
import { SidebarProvider } from "@/components/ui/sidebar";
import { jwtDecode } from "jwt-decode";
import ChatInput from "../components/ChatInput";
import MessageList from "../components/MessageList";
import { BASE_URL } from "../lib/api";

interface Message {
  id: number;
  text: string;
  sender: "user" | "assistant";
  isThinking?: boolean; // Optional flag for thinking state
  thinkingDescription?: string; // Optional description for thinking state
}

// Import GraphData type from MessageList
import { GraphData } from "../components/MessageList";

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

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isChatActive, setIsChatActive] = useState(false);
  // Replace single graphData state with a map for multiple graphs per message
  const [graphDataMap, setGraphDataMap] = useState<Record<number, GraphData[]>>({});
  const [messageId, setMessageId] = useState(1);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const initialTitleRef = useRef(null);
  const chatPreviewRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!isTokenValid(token)) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      navigate('/login');
    }
  }, [navigate]);

  useEffect(() => {
    if (messages.length > 0 && !isChatActive) {
      setIsChatActive(true);
    }
  }, [messages, isChatActive]);

  useEffect(() => {
    const timer = setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 100);
    return () => clearTimeout(timer);
  }, [messages]);

  useEffect(() => {
    if (chatPreviewRef.current) {
      chatPreviewRef.current.scrollTop = chatPreviewRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = async () => {
    const token = localStorage.getItem('access_token');
    if (!input.trim() || isLoading || !isTokenValid(token)) {
      if (!isTokenValid(token)) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        navigate('/login');
      }
      return;
    }

    const currentInput = input;
    const userMsgId = messageId;
    const llmMsgId = messageId + 1;
    setMessageId((id) => id + 2);

    const userMessage: Message = {
      id: userMsgId,
      text: currentInput,
      sender: "user",
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    requestAnimationFrame(() => {
      const llmMessagePlaceholder: Message = {
        id: llmMsgId,
        text: "",
        sender: "assistant",
      };
      setMessages((prev) => [...prev, llmMessagePlaceholder]);
    });

    try {
      // Payload should contain the entire conversation history along with
      // roles in OpenAI format
      const payload = {
        messages: [
          // Map existing messages
          ...messages.map((msg) => ({
            role: msg.sender,
            content: msg.text,
          })),
          // Add the current user message as an object literal
          { role: "user", content: currentInput },
        ],
      };

      console.log(payload);
      const response = await fetch(
        `${BASE_URL}/analytics/stream/`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(payload),
        }
      );
      if (response.status === 401) {
        // Try to refresh token
        const refresh = localStorage.getItem('refresh_token');
        if (refresh) {
          const refreshResp = await fetch(`${BASE_URL}/token/refresh/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh }),
          });
          const refreshData = await refreshResp.json();
          if (refreshResp.ok && refreshData.access) {
            localStorage.setItem('access_token', refreshData.access);
            // Retry original request with new token
            return await handleSend();
          } else {
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            navigate('/login');
            return;
          }
        } else {
          navigate('/login');
          return;
        }
      }
      if (!response.ok) {
        // Attempt to read error message from backend if available
        let errorBody = "Unknown error";
        try {
          errorBody = await response.text(); // Or response.json() if backend sends structured error
        } catch (e) {
          // Ignore if can't read body
        }
        throw new Error(`HTTP error! status: ${response.status}, ${errorBody}`);
      }

      if (!response.body) {
        throw new Error("Response body is null");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let done = false;
      let llmResponseText = "";

      // Track all graphs for this message
      let newGraphs: GraphData[] = [];

      let firstChunk = true;
      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          // Process potential multiple JSON objects in a single chunk
          const chunkText = decoder.decode(value, { stream: true });
          // Split potentially concatenated JSON objects (separated by newline from backend)
          const jsonObjects = chunkText.split("\n").filter((str) => str.trim());

          jsonObjects.forEach((jsonStr) => {
            try {
              const parsedChunk = JSON.parse(jsonStr);
              console.log("Parsed chunk:", parsedChunk);

              if (parsedChunk.type === "thinking") {
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === llmMsgId
                      ? {
                          ...msg,
                          text: "",
                          isThinking: true,
                          thinkingDescription: parsedChunk.description,
                        }
                      : msg
                  )
                );
              } else if (parsedChunk.type === "token") {
                llmResponseText += parsedChunk.content;
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === llmMsgId
                      ? // When token arrives, stop thinking and append text
                        {
                          ...msg,
                          text: llmResponseText,
                          isThinking: false,
                          thinkingDescription: undefined,
                        }
                      : msg
                  )
                );
              } else if (
                parsedChunk.type === "graph_data" ||
                parsedChunk.type === "doughnut_graph_data" ||
                parsedChunk.type === "bar_graph_data" ||
                parsedChunk.type === "line_graph_data" ||
                parsedChunk.type === "area_graph_data"
              ) {
                // Always include the type at the top level for MessageList
                const graphObj = { type: parsedChunk.type, ...parsedChunk.data };
                newGraphs.push(graphObj);
                setGraphDataMap((prev) => {
                  const arr = prev[llmMsgId] ? [...prev[llmMsgId]] : [];
                  arr.push(graphObj);
                  return { ...prev, [llmMsgId]: arr };
                });
              } else if (parsedChunk.error) {
                console.error("Backend Error:", parsedChunk.error);
                // Handle potential errors streamed from the backend
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === llmMsgId
                      ? {
                          ...msg,
                          text: `Error: ${parsedChunk.error}`,
                          isThinking: false,
                        }
                      : msg
                  )
                );
                // Optionally stop processing further chunks if error is fatal
                done = true;
              }
            } catch (error) {
              console.error("Error parsing JSON chunk:", jsonStr, error);
              // Decide how to handle non-JSON text or parsing errors
              // Maybe append raw chunkText to the message? For now, we log and potentially ignore.
            }
          });

          // Scroll logic remains similar
          if (!firstChunk) {
            messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
          }
          firstChunk = false;
        }
      }
    } catch (error) {
      console.error("Error fetching streaming response:", error);
      // Update the specific message with a generic error
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === llmMsgId
            ? {
                ...msg,
                text: "Sorry, something went wrong.",
                isThinking: false,
              }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <SidebarProvider>
      <div className="h-screen w-screen bg-black text-white">
        <AppSidebar />
        <div className="absolute left-[18rem] top-0 right-0 bottom-0 flex flex-col">
          <header className="h-14 shrink-0 flex items-center gap-2 px-3 border-b border-neutral-800 bg-neutral-950">
            <h1 className="text-2xl font-bold text-neutral-300">Chat</h1>
          </header>
          <div className="flex-1 flex flex-col overflow-hidden min-h-0">
            <div className={`flex-1 flex flex-col overflow-hidden min-h-0 ${!isChatActive ? "justify-center items-center" : "justify-start"}`}>
              <div className={`flex flex-col overflow-hidden transition-all duration-500 ease-in-out w-full ${isChatActive ? "flex-1" : "justify-center items-center p-4"}`}>
                <CSSTransition
                  in={!isChatActive}
                  timeout={300}
                  classNames="fade"
                  unmountOnExit
                  nodeRef={initialTitleRef}
                >
                  <div ref={initialTitleRef} className="flex justify-center items-center">
                    <h1 className="text-4xl font-bold text-neutral-300 text-center px-4 mb-6">
                      Got a question? Ask me anything!
                    </h1>
                  </div>
                </CSSTransition>
                {isChatActive && (
                  <div
                    ref={chatPreviewRef}
                    className="flex-1 overflow-y-auto max-h-[60vh] min-h-[200px]"
                  >
                    <MessageList
                      messages={messages}
                      isLoading={isLoading}
                      messagesEndRef={messagesEndRef}
                      graphDataMap={graphDataMap}
                    />
                  </div>
                )}
              </div>
              <ChatInput
                input={input}
                setInput={setInput}
                handleSend={handleSend}
                isLoading={isLoading}
                isChatActive={isChatActive}
              />
            </div>
          </div>
        </div>
      </div>
    </SidebarProvider>
  );
}

export default App;
