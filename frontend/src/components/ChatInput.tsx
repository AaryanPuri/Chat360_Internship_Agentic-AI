import React, { useRef, useEffect } from 'react';
import { FiArrowUp } from 'react-icons/fi';

interface ChatInputProps {
  input: string;
  setInput: (input: string) => void;
  handleSend: () => Promise<void>;
  isLoading: boolean;
  isChatActive: boolean; // Needed for styling/focus differences maybe
}

const ChatInput: React.FC<ChatInputProps> = ({
  input,
  setInput,
  handleSend,
  isLoading,
  isChatActive,
}) => {
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea effect
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      const scrollHeight = inputRef.current.scrollHeight;
      const maxHeight = 200; 
      if (scrollHeight > maxHeight) {
        inputRef.current.style.height = `${maxHeight}px`;
        inputRef.current.style.overflowY = 'auto';
      } else {
        inputRef.current.style.height = `${scrollHeight}px`;
        inputRef.current.style.overflowY = 'hidden';
      }
    }
  }, [input]);

   // Auto-focus input when chat becomes active OR when loading finishes
   useEffect(() => {
    if (isChatActive && !isLoading) {
        // Add a tiny delay to ensure focus works after potential layout shifts
        setTimeout(() => inputRef.current?.focus(), 0); 
    } else if (!isChatActive) {
        setTimeout(() => inputRef.current?.focus(), 0); // Focus initially
    }
  }, [isChatActive, isLoading]);

   // Reset textarea height manually after send triggered by state clearing
   useEffect(() => {
     if (input === '' && inputRef.current) {
       inputRef.current.style.height = 'auto';
     }
   }, [input]);

  return (
    <div className={`w-full transition-all duration-500 ease-in-out shrink-0 ${
      isChatActive ? 'p-4 bg-neutral-900' : 'p-4 max-w-2xl' 
    }`}>
      <div className={`relative flex items-end bg-neutral-800 rounded-3xl p-2 mx-auto transition-all duration-500 ease-in-out shadow-md ${
         isChatActive ? 'max-w-4xl' : 'max-w-2xl' 
      }`}>
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder="Ask anything..."
          className="flex-1 bg-transparent border-none focus:outline-none focus:ring-0 resize-none text-slate-100 placeholder-neutral-500 p-2.5 min-h-[48px] text-base scrollbar-thin scrollbar-thumb-neutral-600 scrollbar-track-neutral-800 pr-12"
          rows={1}
          disabled={isLoading}
        />
        <button
          onClick={handleSend}
          disabled={isLoading || !input.trim()}
          className="p-2 mb-1.5 rounded-full bg-neutral-200 hover:bg-neutral-400 disabled:bg-neutral-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center w-9 h-9"
          aria-label="Send message"
        >
           {isLoading ? (
               <div className="w-4 h-4 border-2 border-neutral-400 border-t-transparent rounded-full animate-spin"></div>
           ) : (
              <FiArrowUp size={18} className="text-black" />
           )}
        </button>
      </div>
    </div>
  );
};

export default ChatInput; 