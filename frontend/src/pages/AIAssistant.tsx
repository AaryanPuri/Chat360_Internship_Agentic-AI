import { useEffect, useState, useRef, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { jwtDecode } from "jwt-decode";
import { AppSidebar } from "@/components/app-sidebar";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import axios from "axios";
import { v4 as uuidv4 } from "uuid";
import KnowledgeBaseDropdown from "../components/KnowledgeBaseDropdown";

const TABS = ["Personality", "Capabilities", "Knowledge", "Integrations", "Testing"];

type WAMessage = { sender: "user" | "assistant"; text: string };

export default function AIAssistant() {
  const navigate = useNavigate();
  const location = useLocation();
  const [activeTab, setActiveTab] = useState("Personality");
  const [assistantName, setAssistantName] = useState("SupportGPT");
  const [agentName, setAgentName] = useState("Bot360");
  const [agentNameEnabled, setAgentNameEnabled] = useState(true);
  const [organisationName, setOrganisationName] = useState("");
  const [organisationNameEnabled, setOrganisationNameEnabled] = useState(true);
  const [organisationDescription, setOrganisationDescription] = useState("");
  const [organisationDescriptionEnabled, setOrganisationDescriptionEnabled] = useState(true);
  const [conversationTone, setConversationTone] = useState("Friendly & Approachable");
  const [conversationToneEnabled, setConversationToneEnabled] = useState(true);
  const [systemInstructions, setSystemInstructions] = useState(
    "You are SupportGPT, a helpful AI assistant."
  );
  const [modelProvider, setModelProvider] = useState("OpenAI");
  const [modelName, setModelName] = useState("gpt-4.1");
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(1024);
  const [topP, setTopP] = useState(0.95);
  const [frequencyPenalty, setFrequencyPenalty] = useState(0);
  const [streamResponses, setStreamResponses] = useState(true);
  const [jsonMode, setJsonMode] = useState(false);
  const [autoToolChoice, setAutoToolChoice] = useState(false);
  const [, setKnowledgeFiles] = useState<any[]>([]);
  // const [uploading, setUploading] = useState(false);
  // const fileInputRef = useRef<HTMLInputElement>(null);
  const [modelUUID, setModelUUID] = useState<string>(""); // Set this appropriately when loading/creating a model
  const [examples, setExamples] = useState<{ question: string; answer: string }[]>([]);
  const [examplesEnabled, setExamplesEnabled] = useState(true);
  const [showExampleModal, setShowExampleModal] = useState(false);
  const [editingExampleIdx, setEditingExampleIdx] = useState<number | null>(null);
  const [exampleQuestion, setExampleQuestion] = useState("");
  const [exampleAnswer, setExampleAnswer] = useState("");
  const [goal, setGoal] = useState("");
  const [goalEnabled, setGoalEnabled] = useState(true);
  const [useLastUserLanguage, setUseLastUserLanguage] = useState(true);
  const [languages, setLanguages] = useState("");
  const [enableEmojis, setEnableEmojis] = useState(false);
  const [answerCompetitorQueries, setAnswerCompetitorQueries] = useState(false);
  const [competitorResponseBias, setCompetitorResponseBias] = useState("genuine"); // "genuine" or "biased"

  // WhatsApp Preview state
  const [waMessages, setWAMessages] = useState<WAMessage[]>([]);
  const [waError, setWAError] = useState("");
  const [waInput, setWAInput] = useState("");
  const [waLoading, setWALoading] = useState(false);
  const waInputRef = useRef<HTMLInputElement>(null);
  const waMessagesEndRef = useRef<HTMLDivElement>(null);

  // Test Suite State
  const [testSuiteMode, setTestSuiteMode] = useState("quick");
  const [testSuite, setTestSuite] = useState<{ id: number; question: string; ideal_answer: string }[]>([]);
  const [testSuiteLoading, setTestSuiteLoading] = useState(false);
  const [testSuiteError, setTestSuiteError] = useState("");
  const [editingTestIdx, setEditingTestIdx] = useState<number | null>(null);
  const [editTestQ, setEditTestQ] = useState("");
  const [editTestA, setEditTestA] = useState("");

  const [isTesting, setIsTesting] = useState(false);
  const [testResults, setTestResults] = useState<any[]>([]); // [{question, expected, agent, verification, status}]


  const [selectedKB, setSelectedKB] = useState<string | null>(null);

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
    // Always fetch files and links when modelUUID or Knowledge tab changes
    if (activeTab === "Knowledge" && modelUUID) {
      fetchKnowledgeFiles();
    }
    // Load config if uuid is present in query
    const params = new URLSearchParams(location.search);
    const uuid = params.get("uuid");
    if (uuid) {
      setModelUUID(uuid);
      loadConfig(uuid);
    }
  }, [navigate, location, activeTab, modelUUID]);

  useEffect(() => {
    if (waMessagesEndRef.current) {
      waMessagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [waMessages]);

  const fetchKnowledgeFiles = async () => {
    if (!modelUUID) return;
    try {
      const token = localStorage.getItem("access_token");
      const res = await axios.get(`/api/analytics/assistant/${modelUUID}/knowledge-files/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setKnowledgeFiles(res.data);
    } catch {
      setKnowledgeFiles([]);
    }
  };

  // const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
  //   const file = e.target.files?.[0];
  //   if (!file || !modelUUID) return;
  //   setUploading(true);
  //   const formData = new FormData();
  //   formData.append("file", file);
  //   formData.append("assistant_config", modelUUID);
  //   try {
  //     const token = localStorage.getItem("access_token");
  //     await axios.post(`/api/analytics/knowledgebase/upload/`, formData, {
  //       headers: { "Content-Type": "multipart/form-data", Authorization: `Bearer ${token}` },
  //     });
  //     fetchKnowledgeFiles();
  //   } finally {
  //     setUploading(false);
  //     if (fileInputRef.current) fileInputRef.current.value = "";
  //   }
  // };

  // const handleDeleteFile = async (fileId: number) => {
  //   if (!window.confirm(`Delete this file?`)) return;
  //   const token = localStorage.getItem("access_token");
  //   await axios.delete(`/api/analytics/knowledge-file/${fileId}/`, {
  //     headers: { Authorization: `Bearer ${token}` },
  //   });
  //   fetchKnowledgeFiles();
  // };

  const loadConfig = async (uuid: string) => {
    try {
      const token = localStorage.getItem("access_token");
      const res = await axios.get(`/api/analytics/assistant/config/${uuid}/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = res.data;
      setSelectedKB(data.knowledge_base || null);
      setAssistantName(data.assistant_name);
      if (data.agent_name === null || data.agent_name === "None") {
        setAgentNameEnabled(false);
        setAgentName("");
      } else {
        setAgentNameEnabled(true);
        setAgentName(data.agent_name || "Bot360");
      }
      if (data.organisation_name === null || data.organisation_name === "None") {
        setOrganisationNameEnabled(false);
        setOrganisationName("");
      } else {
        setOrganisationNameEnabled(true);
        setOrganisationName(data.organisation_name || "");
      }
      if (data.organisation_description === null || data.organisation_description === "None") {
        setOrganisationDescriptionEnabled(false);
        setOrganisationDescription("");
      } else {
        setOrganisationDescriptionEnabled(true);
        setOrganisationDescription(data.organisation_description || "");
      }
      if (data.conversation_tone === "None") {
        setConversationToneEnabled(false);
        setConversationTone("");
      } else {
        setConversationToneEnabled(true);
        setConversationTone(data.conversation_tone);
      }
      if (data.examples && Array.isArray(data.examples)) {
        setExamplesEnabled(true);
        setExamples(data.examples);
      } else if (data.examples && typeof data.examples === "string") {
        try {
          const parsed = JSON.parse(data.examples);
          if (Array.isArray(parsed)) setExamples(parsed);
          else setExamples([]);
        } catch {
          setExamples([]);
        }
      } else {
        setExamples([]);
      }
      if (data.goal === null || data.goal === "None") {
        setGoalEnabled(false);
        setGoal("");
      } else {
        setGoalEnabled(true);
        setGoal(data.goal || "");
      }
      setSystemInstructions(data.system_instructions);
      setModelProvider(data.model_provider);
      setModelName(data.model_name);
      setTemperature(data.temperature);
      setMaxTokens(data.max_tokens);
      setTopP(data.top_p);
      setFrequencyPenalty(data.frequency_penalty);
      setStreamResponses(data.stream_responses);
      setJsonMode(data.json_mode);
      setAutoToolChoice(data.auto_tool_choice);
      setUseLastUserLanguage(data.use_last_user_language !== false); // default true
      setLanguages(data.languages || "");
      setEnableEmojis(!!data.enable_emojis); // Load emoji toggle
      setWAMessages([]); // Remove default preview messages
      setAnswerCompetitorQueries(!!data.answer_competitor_queries);
      setCompetitorResponseBias(data.competitor_response_bias || "genuine");

    } catch (e) {
      // fallback to defaults
    }
  };

  const handleSave = async () => {
    try {
      let uuid = modelUUID;
      const token = localStorage.getItem("access_token");
      // Only allow valid model names
      const validModels = [
        "gpt-4.1","gpt-4.1-mini","gpt-4.1-nano","gpt-4o","gpt-4o-mini","gpt-o4-mini","gpt-3.5-turbo","o1","o1-mini","o3","o3-mini"
      ];
      const safeModelName = validModels.includes(modelName) ? modelName : "gpt-4.1";
      const toneToSave = conversationToneEnabled ? conversationTone : "None";
      const AgentNameToSave = agentNameEnabled ? agentName : null;
      const OrganisationNameToSave = organisationNameEnabled ? organisationName : null;
      const OrganisationDescriptionToSave = organisationDescriptionEnabled ? organisationDescription : null;
      const ExamplesToSave = examplesEnabled ? examples : null;
      const GoalToSave = goalEnabled ? goal : null;
      const UseLastUserLanguageToSave = useLastUserLanguage;
      const LanguagesToSave = useLastUserLanguage ? null : languages;
      let systemInstructionsToSave = systemInstructions;
      if (uuid) {
        await axios.put(
          `/api/analytics/assistant/config/${uuid}/`,
          {
            assistant_name: assistantName,
            agent_name: AgentNameToSave,
            organisation_name: OrganisationNameToSave,
            organisation_description: OrganisationDescriptionToSave,
            conversation_tone: toneToSave,
            system_instructions: systemInstructionsToSave,
            model_provider: modelProvider,
            model_name: safeModelName,
            temperature,
            max_tokens: maxTokens,
            top_p: topP,
            frequency_penalty: frequencyPenalty,
            stream_responses: streamResponses,
            json_mode: jsonMode,
            auto_tool_choice: autoToolChoice,
            examples: ExamplesToSave,
            goal: GoalToSave,
            use_last_user_language: UseLastUserLanguageToSave,
            languages: LanguagesToSave,
            enable_emojis: enableEmojis,
            answer_competitor_queries: answerCompetitorQueries,
            competitor_response_bias: competitorResponseBias,
          },
          {
            headers: { Authorization: `Bearer ${token}` },
          }
        );
      } else {
        uuid = uuidv4();
        setModelUUID(uuid);
        await axios.post(
          "/api/analytics/save-configuration",
          {
            model_uuid: uuid,
            assistantName,
            agentName: AgentNameToSave,
            organisationName: OrganisationNameToSave,
            organisationDescription: OrganisationDescriptionToSave,
            conversationTone: toneToSave,
            systemInstructions: systemInstructionsToSave,
            modelProvider,
            modelName: safeModelName,
            temperature,
            maxTokens,
            topP,
            frequencyPenalty,
            stream_responses: streamResponses, 
            jsonMode,
            autoToolChoice,
            examples: ExamplesToSave,
            goal: GoalToSave,
            use_last_user_language: UseLastUserLanguageToSave,
            languages: LanguagesToSave,
            enable_emojis: enableEmojis,
            answer_competitor_queries: answerCompetitorQueries,
            competitor_response_bias: competitorResponseBias,
          },
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );
      }
      alert("Configuration saved successfully!");
    } catch (error) {
      alert("Error saving configuration");
    }
  };

  // Send message in WhatsApp Preview
  const handleWASend = async () => {
    if (!waInput.trim() || waLoading) return;
    setWAError("");
    const userMsg: WAMessage = { sender: "user", text: waInput };
    setWAMessages((msgs) => [...msgs, userMsg]);
    setWAInput("");
    setWALoading(true);
    try {
      const token = localStorage.getItem("access_token");
      if (streamResponses) {
        // Streaming logic
        let assistantMsg: WAMessage = { sender: "assistant", text: "" };
        setWAMessages((msgs) => [...msgs, assistantMsg]);
        const response = await fetch("/api/analytics/wa-chat/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            messages: [
              ...waMessages.map((m) => ({ role: m.sender, content: m.text })),
              { role: "user", content: waInput },
            ],
            model_uuid: modelUUID,
          }),
        });
        if (!response.body) throw new Error("No response body");
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let done = false;
        let buffer = "";
        while (!done) {
          const { value, done: doneReading } = await reader.read();
          done = doneReading;
          if (value) {
            buffer += decoder.decode(value, { stream: true });
            // Split by space to get words
            let words = buffer.split(" ");
            // Keep last partial word in buffer
            buffer = words.pop() || "";
            for (const word of words) {
              assistantMsg.text += word + " ";
              setWAMessages((msgs) => {
                // Replace last assistant message
                const newMsgs = [...msgs];
                // Find last assistant message
                let lastIdx = newMsgs.length - 1;
                while (lastIdx >= 0 && newMsgs[lastIdx].sender !== "assistant") lastIdx--;
                if (lastIdx >= 0) {
                  newMsgs[lastIdx] = { ...assistantMsg };
                }
                return newMsgs;
              });
              await new Promise((res) => setTimeout(res, 60)); // Slow for visible effect
            }
          }
        }
        // Flush any remaining buffer
        if (buffer.trim()) {
          assistantMsg.text += buffer;
          setWAMessages((msgs) => {
            const newMsgs = [...msgs];
            let lastIdx = newMsgs.length - 1;
            while (lastIdx >= 0 && newMsgs[lastIdx].sender !== "assistant") lastIdx--;
            if (lastIdx >= 0) {
              newMsgs[lastIdx] = { ...assistantMsg };
            }
            return newMsgs;
          });
        }
      } else {
        // Non-streaming fallback
        const res = await axios.post(
          "/api/analytics/wa-chat/",
          {
            messages: [
              ...waMessages.map((m) => ({ role: m.sender, content: m.text })),
              { role: "user", content: waInput },
            ],
            model_uuid: modelUUID,
          },
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );
        if (res.data && res.data.message) {
          const assistantMsg: WAMessage = { sender: "assistant", text: res.data.message };
          setWAMessages((msgs) => [...msgs, assistantMsg]);
        } else {
          setWAError("Sorry, something went wrong. No response from assistant.");
        }
      }
    } catch (e) {
      setWAError("Sorry, something went wrong. Please try again later.");
    } finally {
      setWALoading(false);
    }
  };

  // Fetch or generate test suite
  const handleGenerateTestSuite = useCallback(async () => {
    if (!modelUUID) {
      alert("Please save configuration first.");
      return;
    }
    setTestSuiteLoading(true);
    setTestSuiteError("");
    try {
      const token = localStorage.getItem("access_token");
      const res = await axios.post(
        "/api/analytics/assistant/generate-test-suite/",
        {
          assistant_uuid: modelUUID,
          mode: testSuiteMode,
          system_instructions: systemInstructions,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setTestSuite(res.data.test_cases || []);
    } catch (e: any) {
      setTestSuiteError(e?.response?.data?.error || "Failed to generate test suite");
    } finally {
      setTestSuiteLoading(false);
    }
  }, [modelUUID, testSuiteMode, systemInstructions]);

  // Save test suite edits
  const saveTestSuite = async (cases: typeof testSuite) => {
    if (!modelUUID) return;
    setTestSuiteLoading(true);
    setTestSuiteError("");
    try {
      const token = localStorage.getItem("access_token");
      await axios.put(
        "/api/analytics/assistant/update-test-suite/",
        {
          assistant_uuid: modelUUID,
          mode: testSuiteMode,
          test_cases: cases,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setTestSuite(cases);
    } catch (e: any) {
      setTestSuiteError(e?.response?.data?.error || "Failed to save test suite");
    } finally {
      setTestSuiteLoading(false);
    }
  };

  // Copy test set to clipboard
  const handleCopyTestSuite = () => {
    const text = testSuite.map((t, i) => `${i + 1}. Q: ${t.question}\nA: ${t.ideal_answer}`).join("\n\n");
    navigator.clipboard.writeText(text);
    alert("Test set copied to clipboard");
  };

  const handleStartTesting = async () => {
    // Snapshot config and test suite
    const configSnapshot = {
      assistantName,
      agentName: agentNameEnabled ? agentName : null,
      organisationName: organisationNameEnabled ? organisationName : null,
      organisationDescription: organisationDescriptionEnabled ? organisationDescription : null,
      conversationTone: conversationToneEnabled ? conversationTone : null,
      systemInstructions,
      modelProvider,
      modelName,
      temperature,
      maxTokens,
      topP,
      frequencyPenalty,
      streamResponses,
      jsonMode,
      autoToolChoice,
      examples: examplesEnabled ? examples : null,
      goal: goalEnabled ? goal : null,
      useLastUserLanguage,
      languages: useLastUserLanguage ? null : languages,
      enableEmojis,
      answerCompetitorQueries,
      competitorResponseBias,
    };
    setIsTesting(true);
    setTestResults([]);
    try {
      // Call backend to start test run (implement this endpoint in Django/Celery)
      const token = localStorage.getItem("access_token");
      const res = await axios.post(
        "/api/analytics/assistant/start-test-suite/",
        {
          config: configSnapshot,
          test_suite: testSuite,
          model_uuid: modelUUID,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      pollTestResults(res.data.test_run_id, res.data.task_ids || []);
    } catch (e) {
      setIsTesting(false);
      alert("Failed to start testing");
    }
  };

  // Polling function for test results
  const pollTestResults = async (runId: string, taskIds: string[]) => {
    const token = localStorage.getItem("access_token");
    let finished = false;
    while (!finished) {
      try {
        const params = new URLSearchParams();
        taskIds.forEach(id => params.append("task_ids", id));
        const res = await axios.get(`/api/analytics/assistant/test-suite-results/${runId}/?${params.toString()}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        setTestResults(res.data.results);
        finished = res.data.finished;
        if (!finished) await new Promise(r => setTimeout(r, 1500));
      } catch {
        break;
      }
    }
    setIsTesting(false);
  };

  useEffect(() => {
    if (activeTab === "Testing") {
      handleGenerateTestSuite();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [testSuiteMode, activeTab, modelUUID, systemInstructions]);

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset className="bg-gray-950">
        <main className="flex h-[calc(100vh-56px)] bg-gray-950">
          {/* Configuration Panel */}
          <section className="flex w-[700px] flex-col border-r border-gray-800 bg-gray-950">
            <div className="space-y-6 p-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <SidebarTrigger />
                  <div>
                    <h2 className="text-xl font-semibold text-white">AI Assistant Configuration</h2>
                    <p className="text-sm text-gray-400">Configure your WhatsApp Business AI assistant</p>
                  </div>
                </div>
                {/* <label className="flex items-center gap-2 text-sm text-gray-300"> */}
                  {/* <input 
                    type="checkbox"
                    className="h-4 w-4 rounded border-gray-600 bg-gray-700 text-green-500 focus:ring-green-600"
                  />
                  Test Mode
                </label> */}
              </div>

              {/* Tabs */}
              <div className="border-b border-gray-800">
                <div className="flex gap-4">
                  {TABS.map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setActiveTab(tab)}
                      className={`pb-3 text-sm font-medium ${
                        activeTab === tab
                          ? "border-b-2 border-green-500 text-white"
                          : "text-gray-400 hover:text-gray-200"
                      }`}
                    >
                      {tab}
                    </button>
                  ))}
                </div>
              </div>

              {/* Personality Tab Content */}
              {activeTab === "Personality" && (
                <div className="space-y-6">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-gray-300">Assistant Name</label>
                    <input
                      value={assistantName}
                      onChange={(e) => setAssistantName(e.target.value)}
                      className="w-full rounded-lg border border-gray-700 bg-gray-900 px-4 py-2 text-white placeholder-gray-500 focus:border-green-500 focus:ring-green-500"
                      placeholder="Enter assistant name"
                    />
                  </div>
                  <div>
                    <div className="flex items-center mb-2">
                      <label className="block text-sm font-medium text-gray-300 mr-3">Agent Name</label>
                      <label className="flex items-center gap-2 text-xs text-gray-400">
                        <input
                          type="checkbox"
                          checked={agentNameEnabled}
                          onChange={e => {
                            setAgentNameEnabled(e.target.checked);
                            if (!e.target.checked) setAgentName("");
                          }}
                          className="h-4 w-4 rounded border-gray-600 text-green-500 focus:ring-green-600"
                        />
                        Enable
                      </label>
                    </div>
                    <input
                      value={agentName}
                      onChange={(e) => setAgentName(e.target.value)}
                      className="w-full rounded-lg border border-gray-700 bg-gray-900 px-4 py-2 text-white placeholder-gray-500 focus:border-green-500 focus:ring-green-500"
                      placeholder="Enter Agent name"
                      disabled={!agentNameEnabled}
                    />
                  </div>
                  <div>
                    <div className="flex items-center mb-2">
                      <label className="block text-sm font-medium text-gray-300 mr-3">Organisation Name</label>
                      <label className="flex items-center gap-2 text-xs text-gray-400">
                        <input
                          type="checkbox"
                          checked={organisationNameEnabled}
                          onChange={e => {
                            setOrganisationNameEnabled(e.target.checked);
                            if (!e.target.checked) setOrganisationName("");
                          }}
                          className="h-4 w-4 rounded border-gray-600 text-green-500 focus:ring-green-600"
                        />
                        Enable
                      </label>
                    </div>
                    <input
                      value={organisationName}
                      onChange={(e) => setOrganisationName(e.target.value)}
                      className="w-full rounded-lg border border-gray-700 bg-gray-900 px-4 py-2 text-white placeholder-gray-500 focus:border-green-500 focus:ring-green-500"
                      placeholder="Enter Organisation name"
                      disabled={!organisationNameEnabled}
                    />
                  </div>
                  <div>
                    <div className="flex items-center mb-2">
                      <label className="block text-sm font-medium text-gray-300 mr-3">Organisation Description</label>
                      <label className="flex items-center gap-2 text-xs text-gray-400">
                        <input
                          type="checkbox"
                          checked={organisationDescriptionEnabled}
                          onChange={e => {
                            setOrganisationDescriptionEnabled(e.target.checked);
                            if (!e.target.checked) setOrganisationDescription("");
                          }}
                          className="h-4 w-4 rounded border-gray-600 text-green-500 focus:ring-green-600"
                        />
                        Enable
                      </label>
                    </div>
                    <textarea
                      value={organisationDescription}
                      onChange={(e) => setOrganisationDescription(e.target.value)}
                      rows={4}
                      className="w-full rounded-lg border border-gray-700 bg-gray-900 px-4 py-2 text-white placeholder-gray-500 focus:border-green-500 focus:ring-green-500"
                      placeholder="Enter Organisation description"
                      disabled={!organisationDescriptionEnabled}
                    />
                  </div>
                  <div>
                    <div className="flex items-center mb-2">
                      <label className="block text-sm font-medium text-gray-300 mr-3">Conversation Tone</label>
                      <label className="flex items-center gap-2 text-xs text-gray-400">
                        <input
                          type="checkbox"
                          checked={conversationToneEnabled}
                          onChange={e => {
                            setConversationToneEnabled(e.target.checked);
                            if (!e.target.checked) setConversationTone("");
                          }}
                          className="h-4 w-4 rounded border-gray-600 text-green-500 focus:ring-green-600"
                        />
                        Enable
                      </label>
                    </div>
                    <select
                      value={conversationTone}
                      onChange={(e) => setConversationTone(e.target.value)}
                      className={`w-full rounded-lg border px-4 py-2 focus:border-green-500 focus:ring-green-500 text-white 
                        ${conversationToneEnabled 
                          ? 'border-gray-700 bg-gray-900' 
                          : 'border-gray-800 bg-gray-800 text-gray-500 cursor-not-allowed'}`}
                      disabled={!conversationToneEnabled}
                    >
                      <option value="Friendly & Approachable">Friendly & Approachable</option>
                      <option value="Professional & Formal">Professional & Formal</option>
                      <option value="Casual & Conversational">Casual & Conversational</option>
                      <option value="Technical & Precise">Technical & Precise</option>
                    </select>
                  </div>
                  <div>
                    <label className="mb-2 block text-sm font-medium text-gray-300">System Instructions</label>
                    <textarea
                      value={systemInstructions}
                      onChange={(e) => setSystemInstructions(e.target.value)}
                      rows={6}
                      className="w-full rounded-lg border border-gray-700 bg-gray-900 px-4 py-2 text-white placeholder-gray-500 focus:border-green-500 focus:ring-green-500"
                      placeholder="Enter system instructions..."
                    />
                  </div>
                  {/* Examples Section */}
                  <div>
                    <div className="flex items-center mb-2">
                      <label className="block text-sm font-medium text-gray-300 mr-3">Few-shot Examples</label>
                      <label className="flex items-center gap-2 text-xs text-gray-400">
                        <input
                          type="checkbox"
                          checked={examplesEnabled}
                          onChange={e => {
                            setExamplesEnabled(e.target.checked);
                            if (!e.target.checked) setExamples([]);
                          }}
                          className="h-4 w-4 rounded border-gray-600 text-green-500 focus:ring-green-600"
                        />
                        Enable
                      </label>
                    </div>
                    {examplesEnabled && (
                      <div>
                        <button
                          className="mb-2 rounded bg-blue-600 px-3 py-1 text-xs text-white hover:bg-blue-700"
                          onClick={() => {
                            setEditingExampleIdx(null);
                            setExampleQuestion("");
                            setExampleAnswer("");
                            setShowExampleModal(true);
                          }}
                        >
                          + Add Example
                        </button>
                        <ul className="space-y-2">
                          {examples.map((ex, idx) => (
                            <li key={idx} className="flex items-center gap-2 bg-gray-800 rounded p-2">
                              <div className="flex-1">
                                <div className="text-xs text-gray-400">user:</div>
                                <div className="text-white text-sm">{ex.question}</div>
                                <div className="text-xs text-gray-400 mt-1">assistant:</div>
                                <div className="text-green-300 text-sm">{ex.answer}</div>
                              </div>
                              <button
                                className="rounded bg-yellow-500 px-2 py-1 text-xs text-white hover:bg-yellow-600"
                                onClick={() => {
                                  setEditingExampleIdx(idx);
                                  setExampleQuestion(ex.question);
                                  setExampleAnswer(ex.answer);
                                  setShowExampleModal(true);
                                }}
                              >Edit</button>
                              <button
                                className="rounded bg-red-600 px-2 py-1 text-xs text-white hover:bg-red-700"
                                onClick={() => setExamples(examples.filter((_, i) => i !== idx))}
                              >Delete</button>
                            </li>
                          ))}
                        </ul>
                        {showExampleModal && (
                          <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-40 z-50">
                            <div className="bg-gray-900 p-6 rounded-lg shadow-lg w-96">
                              <h4 className="text-white mb-4">{editingExampleIdx === null ? "Add Example" : "Edit Example"}</h4>
                              <label className="block text-xs text-gray-400 mb-1">Question</label>
                              <input
                                className="w-full rounded border border-gray-700 bg-gray-800 px-2 py-1 mb-3 text-white"
                                value={exampleQuestion}
                                onChange={e => setExampleQuestion(e.target.value)}
                                placeholder="User question"
                              />
                              <label className="block text-xs text-gray-400 mb-1">Expected Answer</label>
                              <input
                                className="w-full rounded border border-gray-700 bg-gray-800 px-2 py-1 mb-3 text-white"
                                value={exampleAnswer}
                                onChange={e => setExampleAnswer(e.target.value)}
                                placeholder="Assistant answer"
                              />
                              <div className="flex gap-2 justify-end">
                                <button
                                  className="px-3 py-1 rounded bg-gray-700 text-white hover:bg-gray-600"
                                  onClick={() => setShowExampleModal(false)}
                                >Cancel</button>
                                <button
                                  className="px-3 py-1 rounded bg-green-600 text-white hover:bg-green-700"
                                  onClick={() => {
                                    if (!exampleQuestion.trim() || !exampleAnswer.trim()) return;
                                    if (editingExampleIdx === null) {
                                      setExamples([...examples, { question: exampleQuestion, answer: exampleAnswer }]);
                                    } else {
                                      setExamples(examples.map((ex, i) => i === editingExampleIdx ? { question: exampleQuestion, answer: exampleAnswer } : ex));
                                    }
                                    setShowExampleModal(false);
                                  }}
                                >OK</button>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                  <div>
                    <div className="flex items-center mb-2">
                      <label className="block text-sm font-medium text-gray-300 mr-3">Goal</label>
                      <label className="flex items-center gap-2 text-xs text-gray-400">
                        <input
                          type="checkbox"
                          checked={goalEnabled}
                          onChange={e => {
                            setGoalEnabled(e.target.checked);
                            if (!e.target.checked) setGoal("");
                          }}
                          className="h-4 w-4 rounded border-gray-600 text-green-500 focus:ring-green-600"
                        />
                        Enable
                      </label>
                    </div>
                    <textarea
                      value={goal}
                      onChange={(e) => setGoal(e.target.value)}
                      rows={2}
                      className="w-full rounded-lg border border-gray-700 bg-gray-900 px-4 py-2 text-white placeholder-gray-500 focus:border-green-500 focus:ring-green-500"
                      placeholder="What is the main goal for this agent?"
                      disabled={!goalEnabled}
                    />
                  </div>
                  <div>
                    <div className="flex items-center mb-2">
                      <label className="block text-sm font-medium text-gray-300 mr-3">Last user response</label>
                      <label className="flex items-center gap-2 text-xs text-gray-400">
                        <input
                          type="checkbox"
                          checked={useLastUserLanguage}
                          onChange={e => setUseLastUserLanguage(e.target.checked)}
                          className="h-4 w-4 rounded border-gray-600 text-green-500 focus:ring-green-600"
                        />
                        Enable
                      </label>
                      {/* Emoji Toggle */}
                      <label className="flex items-center gap-2 text-xs text-gray-400 ml-6">
                        <input
                          type="checkbox"
                          checked={enableEmojis}
                          onChange={e => setEnableEmojis(e.target.checked)}
                          className="h-4 w-4 rounded border-gray-600 text-yellow-400 focus:ring-yellow-500"
                        />
                        Enable Emojis <span role="img" aria-label="emoji">😊</span>
                      </label>
                    </div>
                  </div>
                  <div>
                    <label className="mb-2 block text-sm font-medium text-gray-300">Languages</label>
                    <input
                      value={languages}
                      onChange={e => setLanguages(e.target.value)}
                      className="w-full rounded-lg border border-gray-700 bg-gray-900 px-4 py-2 text-white placeholder-gray-500 focus:border-green-500 focus:ring-green-500"
                      placeholder="e.g. English, Hindi, Spanish"
                      disabled={useLastUserLanguage}
                    />
                  </div>
                  {/* Competition Query Section */}
                  <div>
                    <div className="flex items-center mb-2">
                      <label className="block text-sm font-medium text-gray-300 mr-3">Answer Competitor Queries</label>
                      <label className="flex items-center gap-2 text-xs text-gray-400">
                        <input
                          type="checkbox"
                          checked={answerCompetitorQueries}
                          onChange={e => setAnswerCompetitorQueries(e.target.checked)}
                          className="h-4 w-4 rounded border-gray-600 text-green-500 focus:ring-green-600"
                        />
                        Enable
                      </label>
                    </div>
                    {answerCompetitorQueries && (
                      <div className="flex items-center gap-6 mt-2">
                        <label className="flex items-center gap-2 text-xs text-gray-400">
                          <input
                            type="radio"
                            checked={competitorResponseBias === "genuine"}
                            onChange={() => setCompetitorResponseBias("genuine")}
                            className="h-4 w-4 text-green-500 focus:ring-green-600"
                          />
                          Genuine Response
                        </label>
                        <label className="flex items-center gap-2 text-xs text-gray-400">
                          <input
                            type="radio"
                            checked={competitorResponseBias === "biased"}
                            onChange={() => setCompetitorResponseBias("biased")}
                            className="h-4 w-4 text-yellow-500 focus:ring-yellow-600"
                          />
                          Biased Response
                        </label>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Capabilities Tab Content */}
              {activeTab === "Capabilities" && (
                <div className="space-y-6">
                  <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
                    <h3 className="mb-4 text-sm font-semibold text-white">Enabled Features</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <label className="flex items-center gap-2 text-sm text-gray-300">
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border-gray-600 bg-gray-700 text-green-500"
                        />
                        Order Tracking
                      </label>
                      <label className="flex items-center gap-2 text-sm text-gray-300">
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border-gray-600 bg-gray-700 text-green-500"
                        />
                        Product Recommendations
                      </label>
                      <label className="flex items-center gap-2 text-sm text-gray-300">
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border-gray-600 bg-gray-700 text-green-500"
                        />
                        Returns Processing
                      </label>
                      <label className="flex items-center gap-2 text-sm text-gray-300">
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border-gray-600 bg-gray-700 text-green-500"
                        />
                        Live Agent Handoff
                      </label>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "Knowledge" && (
                <div className="space-y-6">
                  <KnowledgeBaseDropdown value={selectedKB} onChange={setSelectedKB} modelUuid={modelUUID} />
                  {/* Knowledge base selection only. Uploads and indexing are managed in the Knowledge Base section. */}
                  <div className="text-gray-400 text-sm">Select a knowledge base for this assistant. To add or edit documents/links, go to the Knowledge Base section.</div>
                </div>
              )}

              {/* Integrations Tab Content */}
              {activeTab === "Integrations" && (
                <div className="space-y-6">
                  <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
                    <h3 className="mb-4 text-sm font-semibold text-white">Connected Services</h3>
                    <div className="space-y-4">
                      <div className="flex items-center justify-between rounded-lg bg-gray-800 px-4 py-3">
                        <div className="flex items-center gap-3">
                          <svg className="h-6 w-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                          </svg>
                          <span className="text-sm text-gray-300">Shopify Store</span>
                        </div>
                        <button className="rounded-lg bg-gray-700 px-3 py-1 text-sm text-gray-300 hover:bg-gray-600">
                          Configure
                        </button>
                      </div>
                      <div className="flex items-center justify-between rounded-lg bg-gray-800 px-4 py-3">
                        <div className="flex items-center gap-3">
                          <svg className="h-6 w-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                          </svg>
                          <span className="text-sm text-gray-300">Zapier Automation</span>
                        </div>
                        <button className="rounded-lg bg-gray-700 px-3 py-1 text-sm text-gray-300 hover:bg-gray-600">
                          Configure
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "Testing" && (
                <div className="space-y-6">
                  <div className="rounded-lg border border-gray-800 bg-gray-900 p-6">
                    <h3 className="mb-4 text-lg font-semibold text-white">Test Suite</h3>
                    <div className="flex gap-3 mb-4 items-center">
                      <select
                        className="flex-1 rounded-lg border border-gray-700 bg-gray-900 px-4 py-2 text-white focus:border-green-500 focus:ring-green-500"
                        value={testSuiteMode}
                        onChange={e => setTestSuiteMode(e.target.value)}
                      >
                        <option value="quick">Quick</option>
                        <option value="normal">Normal</option>
                        <option value="extensive">Extensive</option>
                      </select>
                      <button
                        className="rounded bg-gray-700 px-3 py-1 text-xs text-white hover:bg-gray-600"
                        onClick={handleCopyTestSuite}
                      >Copy Test Set</button>
                      <button
                        className={`rounded bg-blue-700 px-3 py-1 text-xs text-white hover:bg-blue-800 ${isTesting ? 'opacity-60 cursor-not-allowed' : ''}`}
                        onClick={handleStartTesting}
                        disabled={isTesting}
                      >{isTesting ? 'Testing...' : 'Test'}</button>
                      <button
                        className="rounded bg-green-700 px-3 py-1 text-xs text-white hover:bg-green-800"
                        disabled={testSuiteLoading}
                        onClick={async () => {
                          setTestSuiteLoading(true);
                          setTestSuiteError("");
                          try {
                            const token = localStorage.getItem("access_token");
                            const res = await axios.post(
                              "/api/analytics/assistant/generate-test-suite/",
                              {
                                assistant_uuid: modelUUID,
                                mode: testSuiteMode,
                                system_instructions: systemInstructions,
                                use_ai: true,
                              },
                              { headers: { Authorization: `Bearer ${token}` } }
                            );
                            setTestSuite(res.data.test_cases || []);
                          } catch (e: any) {
                            setTestSuiteError(e?.response?.data?.error || "Failed to generate with AI");
                          } finally {
                            setTestSuiteLoading(false);
                          }
                        }}
                      >{testSuiteLoading ? "Generating..." : "Generate with AI"}</button>
                    </div>
                    {/* Mode descriptions for user clarity */}
                    <div className="mb-4 text-xs text-gray-400">
                      <b>Quick:</b> Basic and edge-case checks (8 questions).<br />
                      <b>Normal:</b> Detailed test set (32 questions).<br />
                      <b>Extensive:</b> Comprehensive, including rare/complex cases (52 questions).
                    </div>
                    {testSuiteError && <div className="text-red-500 text-sm mb-2">{testSuiteError}</div>}
                    <ul className="space-y-3 max-h-96 overflow-y-auto pr-2">
                      {testSuite.map((t, idx) => (
                        <li key={t.id} className="bg-gray-800 rounded p-3 flex gap-2 items-start">
                          {editingTestIdx === idx ? (
                            <div className="flex-1">
                              <input
                                className="w-full rounded border border-gray-700 bg-gray-900 px-2 py-1 mb-2 text-white"
                                value={editTestQ}
                                onChange={e => setEditTestQ(e.target.value)}
                                placeholder="Test question"
                              />
                              <input
                                className="w-full rounded border border-gray-700 bg-gray-900 px-2 py-1 mb-2 text-white"
                                value={editTestA}
                                onChange={e => setEditTestA(e.target.value)}
                                placeholder="Ideal answer"
                              />
                              <div className="flex gap-2 justify-end">
                                <button
                                  className="px-3 py-1 rounded bg-gray-700 text-white hover:bg-gray-600"
                                  onClick={() => setEditingTestIdx(null)}
                                >Cancel</button>
                                <button
                                  className="px-3 py-1 rounded bg-green-600 text-white hover:bg-green-700"
                                  onClick={async () => {
                                    const updated = [...testSuite];
                                    updated[idx] = { ...updated[idx], question: editTestQ, ideal_answer: editTestA };
                                    await saveTestSuite(updated);
                                    setEditingTestIdx(null);
                                  }}
                                >Save</button>
                              </div>
                            </div>
                          ) : (
                            <>
                              <div className="flex-1">
                                <div className="text-xs text-gray-400">Q:</div>
                                <div className="text-white text-sm mb-1">{t.question}</div>
                                <div className="text-xs text-gray-400 mt-1">Ideal Answer:</div>
                                <div className="text-green-300 text-sm">{t.ideal_answer}</div>
                              </div>
                              <div className="flex flex-col gap-1">
                                <button
                                  className="rounded bg-yellow-500 px-2 py-1 text-xs text-white hover:bg-yellow-600"
                                  onClick={() => {
                                    setEditingTestIdx(idx);
                                    setEditTestQ(t.question);
                                    setEditTestA(t.ideal_answer);
                                  }}
                                >Edit</button>
                                <button
                                  className="rounded bg-red-600 px-2 py-1 text-xs text-white hover:bg-red-700"
                                  onClick={async () => {
                                    const updated = testSuite.filter((_, i) => i !== idx);
                                    await saveTestSuite(updated);
                                  }}
                                >Delete</button>
                              </div>
                            </>
                          )}
                        </li>
                      ))}
                    </ul>
                    <button
                      className="mt-4 rounded bg-blue-600 px-3 py-1 text-xs text-white hover:bg-blue-700"
                      onClick={() => {
                        setEditingTestIdx(null);
                        setEditTestQ("");
                        setEditTestA("");
                        setTestSuite([
                          ...testSuite,
                          { id: Date.now(), question: "", ideal_answer: "" },
                        ]);
                        setEditingTestIdx(testSuite.length);
                      }}
                    >+ Add Test</button>
                    {/* Results area */}
                    {testResults.length > 0 && (
                      <div className="mb-4">
                        <h4 className="text-white text-md mb-2">Test Results</h4>
                        <ul className="space-y-2">
                          {testResults.map((r, i) =>
                            r ? (
                              <li key={i} className="bg-gray-800 rounded p-3">
                                <div className="text-xs text-gray-400">Q: {r.question}</div>
                                <div className="text-xs text-gray-400 mt-1">Expected: <span className="text-green-300">{r.expected}</span></div>
                                <div className="text-xs text-gray-400 mt-1">Agent: <span className="text-blue-300">{r.agent}</span></div>
                                <div className="text-xs text-gray-400 mt-1">Verification: <span className={r.verification === 'pass' ? 'text-green-400' : 'text-red-400'}>{r.verification_result || r.verification}</span></div>
                              </li>
                            ) : null
                          )}
                        </ul>
                        {testResults.some(r => r === null) && (
                          <div className="flex justify-center items-center mt-4">
                            <svg className="animate-spin h-6 w-6 text-blue-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            <span className="ml-2 text-blue-400">Evaluating...</span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Model Configuration */}
            <div className="border-t border-gray-800 p-6">
              <h3 className="mb-4 text-lg font-semibold text-white">Model Settings</h3>
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-300">Model Provider</label>
                  <select
                    value={modelProvider}
                    onChange={(e) => setModelProvider(e.target.value)}
                    className="w-full rounded-lg border border-gray-700 bg-gray-900 px-4 py-2 text-white focus:border-green-500 focus:ring-green-500"
                  >
                    <option>OpenAI</option>
                    <option disabled>Anthropic (Coming Soon)</option>
                    <option disabled>Google (Coming Soon)</option>
                  </select>
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-300">Model Name</label>
                  <select
                    value={modelName}
                    onChange={(e) => setModelName(e.target.value)}
                    className="w-full rounded-lg border border-gray-700 bg-gray-900 px-4 py-2 text-white focus:border-green-500 focus:ring-green-500"
                  >
                    <option value="gpt-4.1">gpt-4.1</option>
                    <option value="gpt-4.1-mini">gpt-4.1-mini</option>
                    <option value="gpt-4.1-nano">gpt-4.1-nano</option>
                    <option value="gpt-4o">gpt-4o</option>
                    <option value="gpt-4o-mini">gpt-4o-mini</option>
                    <option value="gpt-o4-mini">gpt-o4-mini</option>
                    <option value="gpt-3.5-turbo">gpt-3.5-turbo</option>
                    <option value="o1">o1</option>
                    <option value="o1-mini">o1-mini</option>
                    <option value="o3">o3</option>
                    <option value="o3-mini">o3-mini</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Advanced Settings */}
            <div className="border-t border-gray-800 p-6 bg-gray-950">
              <h3 className="mb-4 text-lg font-semibold text-white">Advanced Parameters</h3>
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-300">Temperature</label>
                  <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min={0}
                    max={2}
                    step={0.01}
                    value={temperature}
                    onChange={(e) => setTemperature(Number(e.target.value))}
                    className="w-full accent-white"
                    style={{
                    background: `linear-gradient(to right, #fff 0%, #fff ${(temperature / 2) * 100}%, #1a1a1a ${(temperature / 2) * 100}%, #1a1a1a 100%)`,
                    WebkitAppearance: "none",
                    height: "4px",
                    borderRadius: "2px",
                    outline: "none",
                    }}
                  />
                  <span className="text-gray-200 w-12 text-right">{temperature.toFixed(2)}</span>
                  </div>
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-300">Top P</label>
                  <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.01}
                    value={topP}
                    onChange={(e) => setTopP(Number(e.target.value))}
                    className="w-full accent-white"
                    style={{
                    background: `linear-gradient(to right, #fff 0%, #fff ${topP * 100}%, #1a1a1a ${topP * 100}%, #1a1a1a 100%)`,
                    WebkitAppearance: "none",
                    height: "4px",
                    borderRadius: "2px",
                    outline: "none",
                    }}
                  />
                    <span className="text-gray-200 w-12 text-right">{topP.toFixed(2)}</span>
                  </div>
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-300">Max Tokens</label>
                  <input
                    type="number"
                    value={maxTokens}
                    onChange={(e) => setMaxTokens(Number(e.target.value))}
                    className="w-full rounded-lg border border-gray-700 bg-gray-900 px-4 py-2 text-white focus:border-green-500 focus:ring-green-500"
                  />
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-300">Frequency Penalty</label>
                  <input
                    type="number"
                    value={frequencyPenalty}
                    onChange={(e) => setFrequencyPenalty(Number(e.target.value))}
                    step="0.1"
                    className="w-full rounded-lg border border-gray-700 bg-gray-900 px-4 py-2 text-white focus:border-green-500 focus:ring-green-500"
                  />
                </div>
              </div>
              <div className="mt-6 flex gap-6 bg-gray-950">
                <label className="flex items-center gap-2 text-sm text-gray-300">
                  <input
                    type="checkbox"
                    checked={streamResponses}
                    onChange={(e) => setStreamResponses(e.target.checked)}
                    className="h-4 w-4 rounded border-gray-600 text-green-500 focus:ring-green-600"
                  />
                  Stream Responses
                  <span className="ml-1 text-gray-400" title="When enabled, shows AI responses as they're generated rather than waiting for complete response">
                    <svg xmlns="http://www.w3.org/2000/svg" className="inline h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M12 20a8 8 0 100-16 8 8 0 000 16z" /></svg>
                  </span>
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-300 bg-gray-950">
                  <input
                    type="checkbox"
                    checked={jsonMode}
                    onChange={(e) => setJsonMode(e.target.checked)}
                    className="h-4 w-4 rounded border-gray-600 bg-gray-700 text-green-500 focus:ring-green-600"
                  />
                  JSON Mode
                  <span className="ml-1 text-gray-400" title="When enabled, forces responses in JSON format for function calls">
                    <svg xmlns="http://www.w3.org/2000/svg" className="inline h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M12 20a8 8 0 100-16 8 8 0 000 16z" /></svg>
                  </span>
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-300 bg-gray-950">
                  <input
                    type="checkbox"
                    checked={autoToolChoice}
                    onChange={(e) => setAutoToolChoice(e.target.checked)}
                    className="h-4 w-4 rounded border-gray-600 bg-gray-700 text-green-500 focus:ring-green-600"
                  />
                  Auto Tool Choice
                  <span className="ml-1 text-gray-400 " title="When enabled, automatically selects appropriate tools for handling user requests">
                    <svg xmlns="http://www.w3.org/2000/svg" className="inline h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M12 20a8 8 0 100-16 8 8 0 000 16z" /></svg>
                  </span>
                </label>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="border-t border-gray-800 bg-gray-950 p-6">
              <div className="flex justify-end gap-3">
                <button
                  onClick={() => window.confirm("Discard changes?") && window.location.reload()}
                  className="rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-gray-300 hover:bg-gray-700"
                >
                  Discard Changes
                </button>
                <button
                  onClick={handleSave}
                  className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
                >
                  Save Configuration
                </button>
                <button
                  onClick={() => navigate("/ai-assistant")}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
                >
                  Go to Saved Bots
                </button>
              </div>
            </div>
          </section>

          {/* Preview Panel */}
          <section className="flex flex-1 flex-col border-l border-gray-800 bg-gray-950">
            <div className="space-y-6 p-6 bg-gray-950">
              {/* WhatsApp Preview */}
              <div className="rounded-lg border border-gray-800 bg-gray-900 p-6">
                <h3 className="mb-4 text-lg font-semibold text-white">WhatsApp Preview</h3>
                <div className="space-y-4 rounded-lg bg-gray-800 p-4">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-full bg-green-600 flex items-center justify-center">
                      <svg className="h-6 w-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                      </svg>
                    </div>
                    <div>
                      <p className="font-medium text-white">{assistantName}</p>
                      <p className="text-xs text-gray-400">Typically replies in a few seconds...</p>
                    </div>
                  </div>
                  <div className="space-y-3 max-h-64 overflow-y-auto pr-2">
                    {waMessages.length === 0 && !waError && (
                      <div className="text-gray-500 text-sm">No messages yet.</div>
                    )}
                    {waMessages.map((msg, idx) => (
                      <div key={idx} className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}>
                        <div className={`max-w-[80%] rounded-lg p-3 text-white mb-1 ${msg.sender === "user" ? "bg-green-600" : "bg-gray-700"}`}>
                          {msg.text}
                        </div>
                      </div>
                    ))}
                    {waError && (
                      <div className="text-red-500 text-sm">{waError}</div>
                    )}
                    <div ref={waMessagesEndRef} />
                  </div>
                  <div className="flex gap-3 pt-4">
                    <input
                      ref={waInputRef}
                      placeholder="Type a message..."
                      className="flex-1 rounded-full border border-gray-700 bg-gray-900 px-4 py-2 text-white focus:border-green-500 focus:ring-green-500"
                      value={waInput}
                      onChange={e => setWAInput(e.target.value)}
                      onKeyDown={e => { if (e.key === "Enter") handleWASend(); }}
                      disabled={waLoading}
                    />
                    <button
                      className="rounded-full bg-green-600 p-2 text-white hover:bg-green-700 disabled:bg-green-900"
                      onClick={handleWASend}
                      disabled={waLoading || !waInput.trim()}
                      aria-label="Send message"
                    >
                      {waLoading ? (
                        <svg className="h-6 w-6 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                      ) : (
                        <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                        </svg>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
