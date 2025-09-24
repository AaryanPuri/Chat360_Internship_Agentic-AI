import React, { createRef } from 'react';
import { CSSTransition, TransitionGroup } from 'react-transition-group';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ChartContainer, ChartTooltipContent } from "@/components/ui/chart";
import { BarChart, Bar, CartesianGrid, XAxis, YAxis, Legend, LineChart, Line, AreaChart, Area, PieChart, Pie, Tooltip as ChartTooltip } from "recharts";

// Define the Message interface (can be moved to a types file later)
interface Message {
  id: number;
  text: string;
  sender: 'user' | 'assistant';
  isThinking?: boolean;
  thinkingDescription?: string;
}

// Add this type for graph data
export type BarLineAreaGraphData = {
  type: 'bar_graph_data' | 'line_graph_data' | 'area_graph_data';
  x_label: string;
  y_label: string;
  x_coordinates: (string | number)[];
  y_coordinates: number[];
  legend?: string;
  description?: string;
};

export type DoughnutGraphData = {
  type: 'doughnut_graph_data';
  labels: string[];
  values: number[];
  legend?: string;
  description?: string;
};

export type GraphData = BarLineAreaGraphData | DoughnutGraphData;

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  messagesEndRef: React.RefObject<HTMLDivElement | null>;
}

// Define a soft, visually distinct color palette using CSS variables for easy theming
const CHART_COLORS = [
  'var(--chart-1)',
  'var(--chart-2)',
  'var(--chart-3)',
  'var(--chart-4)',
  'var(--chart-5)',
  '#6EC6CA', // fallback soft blue
  '#A5D6A7', // fallback soft green
  '#FFD59E', // fallback soft yellow
  '#B39DDB', // fallback soft purple
  '#FFAB91', // fallback soft orange
];

const MessageList: React.FC<MessageListProps & { graphDataMap?: Record<number, GraphData[]> }> = ({ 
  messages,
  isLoading,
  messagesEndRef,
  graphDataMap = {},
}) => {
  return (
    <div className="flex-1 w-full transition-opacity duration-300 ease-in-out opacity-100 min-h-0">
      <div className="h-full overflow-y-auto pt-4 pb-4 px-6 space-y-4 scrollbar-thin scrollbar-thumb-neutral-600 scrollbar-track-neutral-800 max-w-4xl mx-auto">
        <TransitionGroup component={null}> 
          {messages.map((message) => {
            // Create a ref for each message item
            const nodeRef = createRef<HTMLDivElement>();
            return (
              <CSSTransition
                key={message.id}
                timeout={300}
                classNames="message-fade" // Assumes CSS classes are defined globally
                nodeRef={nodeRef} // Pass the specific ref for this item
              >
                {/* The direct child of CSSTransition needs the ref */}
                <div ref={nodeRef} className={`flex ${
                  message.sender === 'user' ? 'justify-end' : 'justify-start'
                }`}>
                  <div
                    className={`max-w-[75%] px-6 py-2 rounded-2xl shadow break-words transition-colors ${ 
                      message.sender === 'user'
                        ? 'bg-neutral-600 text-white' // User message color
                        : 'bg-neutral-700 text-slate-100' // Assistant message color
                    }`}
                  >
                    <div style={{ whiteSpace: 'pre-wrap' }}>
                      {message.sender === 'assistant' && message.isThinking ? (
                        <div className="flex items-center space-x-2">
                          {/* Simple SVG Spinner */}
                          <svg className="animate-spin h-4 w-4 text-slate-300" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                          <span className="text-slate-300 italic">{message.thinkingDescription || 'Thinking...'}</span>
                        </div>
                      ) : message.sender === 'assistant' && message.text === '' && isLoading ? (
                        <span className="animate-pulse">▍</span> // Existing loading placeholder
                      ) : message.sender === 'assistant' ? (
                        <>
                          <div className="markdown-body w-full overflow-x-auto">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.text}</ReactMarkdown>
                          </div>
                          {/* Render all graphs for this message, if any */}
                          {graphDataMap[message.id]?.length > 0 && (
                            <div className="flex flex-col items-end gap-6 mt-4 w-full">
                              {graphDataMap[message.id].map((graph, idx) => (
                                <div key={idx} className="w-full">
                                  {graph.description && (
                                    <div className="font-semibold text-right mb-2 text-base text-slate-200">{graph.description}</div>
                                  )}
                                  {graph.type === 'bar_graph_data' && (
                                    <ChartContainer
                                      config={{ value: { label: graph.y_label, color: CHART_COLORS[0] } }}
                                      className="min-h-[200px]"
                                    >
                                      <BarChart
                                        data={graph.x_coordinates.map((x, i) => ({
                                          [graph.x_label]: x,
                                          value: graph.y_coordinates[i],
                                        }))}
                                      >
                                        <CartesianGrid strokeDasharray="3 3" />
                                        <XAxis
                                          dataKey={graph.x_label}
                                          label={{ value: graph.x_label, position: 'insideBottom', offset: -5, fill: '#fff' }}
                                          tick={{ fill: '#fff' }}
                                        />
                                        <YAxis
                                          label={{ value: graph.y_label, angle: -90, position: 'insideLeft', fill: '#fff' }}
                                          tick={{ fill: '#fff' }}
                                        />
                                        <Legend verticalAlign="top" align="right" layout="horizontal" wrapperStyle={{ color: '#fff' }} />
                                        <Bar dataKey="value" fill={CHART_COLORS[0]} radius={4} name={graph.y_label} />
                                        <ChartTooltip content={<ChartTooltipContent />} />
                                      </BarChart>
                                    </ChartContainer>
                                  )}
                                  {graph.type === 'line_graph_data' && (
                                    <ChartContainer
                                      config={{ value: { label: graph.y_label, color: CHART_COLORS[0] } }}
                                      className="min-h-[200px]"
                                    >
                                      <LineChart
                                        data={graph.x_coordinates.map((x, i) => ({
                                          [graph.x_label]: x,
                                          value: graph.y_coordinates[i],
                                        }))}
                                      >
                                        <CartesianGrid strokeDasharray="3 3" />
                                        <XAxis
                                          dataKey={graph.x_label}
                                          label={{ value: graph.x_label, position: 'insideBottom', offset: -5, fill: '#fff' }}
                                          tick={{ fill: '#fff' }}
                                        />
                                        <YAxis
                                          label={{ value: graph.y_label, angle: -90, position: 'insideLeft', fill: '#fff' }}
                                          tick={{ fill: '#fff' }}
                                        />
                                        <Legend verticalAlign="top" align="right" layout="horizontal" wrapperStyle={{ color: '#fff' }} />
                                        <Line type="monotone" dataKey="value" stroke={CHART_COLORS[0]} name={graph.y_label} />
                                        <ChartTooltip content={<ChartTooltipContent />} />
                                      </LineChart>
                                    </ChartContainer>
                                  )}
                                  {graph.type === 'area_graph_data' && (
                                    <ChartContainer
                                      config={{ value: { label: graph.y_label, color: CHART_COLORS[0] } }}
                                      className="min-h-[200px]"
                                    >
                                      <AreaChart
                                        data={graph.x_coordinates.map((x, i) => ({
                                          [graph.x_label]: x,
                                          value: graph.y_coordinates[i],
                                        }))}
                                      >
                                        <CartesianGrid strokeDasharray="3 3" />
                                        <XAxis
                                          dataKey={graph.x_label}
                                          label={{ value: graph.x_label, position: 'insideBottom', offset: -5, fill: '#fff' }}
                                          tick={{ fill: '#fff' }}
                                        />
                                        <YAxis
                                          label={{ value: graph.y_label, angle: -90, position: 'insideLeft', fill: '#fff' }}
                                          tick={{ fill: '#fff' }}
                                        />
                                        <Legend verticalAlign="top" align="right" layout="horizontal" wrapperStyle={{ color: '#fff' }} />
                                        <Area type="monotone" dataKey="value" stroke={CHART_COLORS[0]} fill={CHART_COLORS[0]} name={graph.y_label} />
                                        <ChartTooltip content={<ChartTooltipContent />} />
                                      </AreaChart>
                                    </ChartContainer>
                                  )}
                                  {graph.type === 'doughnut_graph_data' && (
                                    <ChartContainer
                                      config={{ value: { label: graph.legend || '', color: CHART_COLORS[0] } }}
                                      className="min-h-[200px]"
                                    >
                                      <PieChart>
                                        <Pie
                                          data={graph.labels.map((label, i) => ({
                                            name: label,
                                            value: graph.values[i],
                                            fill: CHART_COLORS[i % CHART_COLORS.length],
                                          }))}
                                          dataKey="value"
                                          nameKey="name"
                                          cx="50%"
                                          cy="50%"
                                          innerRadius={50}
                                          outerRadius={80}
                                          label
                                          isAnimationActive={false}
                                        />
                                        <Legend verticalAlign="top" align="right" layout="horizontal" wrapperStyle={{ color: '#fff' }} />
                                        <ChartTooltip content={<ChartTooltipContent />} />
                                      </PieChart>
                                    </ChartContainer>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </>
                      ) : (
                        message.text || '\u00A0' // Render text or non-breaking space if empty
                      )}
                    </div>
                  </div>
                </div>
              </CSSTransition>
            );
          })}
        </TransitionGroup>
        <div ref={messagesEndRef} style={{ height: '1px' }}/> 
      </div>
    </div>
  );
};

export default MessageList;