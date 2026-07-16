'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { X, Send, Leaf, AlertTriangle } from 'lucide-react';
import { assessmentAPI, ChatMessage } from '@/lib/api';
import { AssessmentResult } from '@/types/assessment';

/**
 * ResultsChat — a slide-over chat that explains a farm's assessment in plain language.
 * It opens with an automatic summary, then answers follow-up questions. Every answer is
 * grounded on this assessment only (the backend builds context from the computed results).
 */

const INITIAL_PROMPT = 'Give me a plain-language summary of my results.';
const SUGGESTIONS = [
  'What is my biggest impact?',
  'How can I improve my score?',
  'What does my single score mean?',
];

interface Props {
  open: boolean;
  onClose: () => void;
  assessmentData: AssessmentResult | null;
  assessmentId: string | null;
}

export default function ResultsChat({ open, onClose, assessmentData, assessmentId }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const startedRef = useRef(false);

  const send = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || streaming) return;
    setError(null);

    const history: ChatMessage[] = [...messages, { role: 'user', content: trimmed }];
    setMessages([...history, { role: 'assistant', content: '' }]);
    setInput('');
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;
    try {
      await assessmentAPI.streamChat(history, {
        assessmentData: assessmentData ?? undefined,
        assessmentId,
        signal: controller.signal,
        onChunk: (chunk) => {
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last && last.role === 'assistant') {
              next[next.length - 1] = { ...last, content: last.content + chunk };
            }
            return next;
          });
        },
      });
    } catch (e) {
      if ((e as Error).name !== 'AbortError') {
        setError(e instanceof Error ? e.message : 'Something went wrong.');
        // Drop the empty assistant bubble if nothing streamed.
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last && last.role === 'assistant' && !last.content) next.pop();
          return next;
        });
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }, [messages, streaming, assessmentData, assessmentId]);

  // Open with an automatic summary the first time the panel is shown with data.
  useEffect(() => {
    if (open && !startedRef.current && assessmentData) {
      startedRef.current = true;
      send(INITIAL_PROMPT);
    }
  }, [open, assessmentData, send]);

  // Keep the view pinned to the latest message.
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  // Abort any in-flight stream on unmount.
  useEffect(() => () => abortRef.current?.abort(), []);

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  const lastIsStreamingAssistant =
    streaming && messages.length > 0 && messages[messages.length - 1].role === 'assistant';

  return (
    <div className={`fixed inset-0 z-50 ${open ? '' : 'pointer-events-none'}`} aria-hidden={!open}>
      <div
        className={`absolute inset-0 bg-black/30 transition-opacity duration-300 ${open ? 'opacity-100' : 'opacity-0'}`}
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-label="Plain-language summary of your results"
        className={`absolute right-0 top-0 h-full w-full max-w-md bg-white shadow-2xl flex flex-col transition-transform duration-300 ${open ? 'translate-x-0' : 'translate-x-full'}`}
      >
        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-gray-100">
          <span className="flex-shrink-0 w-9 h-9 rounded-lg bg-emerald-600 text-white flex items-center justify-center">
            <Leaf className="w-5 h-5" />
          </span>
          <div className="min-w-0">
            <div className="font-bold text-gray-900 leading-tight">Plain-language summary</div>
            <div className="text-xs text-gray-500">Grounded on this assessment. Ask anything about it.</div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="ml-auto p-2 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
                  m.role === 'user'
                    ? 'bg-emerald-600 text-white rounded-br-sm'
                    : 'bg-gray-100 text-gray-800 rounded-bl-sm'
                }`}
              >
                {m.content || (lastIsStreamingAssistant && i === messages.length - 1 ? (
                  <span className="inline-flex gap-1 py-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '300ms' }} />
                  </span>
                ) : null)}
              </div>
            </div>
          ))}

          {error && (
            <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Suggestions */}
        {!streaming && messages.some((m) => m.role === 'assistant' && m.content) && (
          <div className="px-5 pb-2 flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => send(s)}
                className="text-xs rounded-full border border-emerald-200 bg-emerald-50 text-emerald-800 px-3 py-1.5 hover:bg-emerald-100 transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {/* Input */}
        <div className="border-t border-gray-100 p-3">
          <div className="flex items-end gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              rows={1}
              placeholder="Ask about your results..."
              className="flex-1 resize-none rounded-xl border border-gray-200 px-3 py-2.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-emerald-500 max-h-32"
            />
            <button
              type="button"
              onClick={() => send(input)}
              disabled={streaming || !input.trim()}
              aria-label="Send"
              className="flex-shrink-0 w-10 h-10 rounded-xl bg-emerald-600 text-white flex items-center justify-center hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
          <p className="text-[11px] text-gray-400 mt-2 px-1">
            Answers are based only on this assessment and are a plain-language read of a screening draft.
          </p>
        </div>
      </div>
    </div>
  );
}
