'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { fetchAuthSession } from 'aws-amplify/auth';
import type { CognitoAuthParams } from '@/lib/aws-client';
import type { Answer, ControlAnswer, ChartConfig, AssistantConfig } from '../types';
import { getAnswer } from '../services/agent-core-call';
import { generateChart } from '../services/aws-calls';
import MarkdownRenderer from './MarkdownRenderer';
import ToolBox from './ToolBox';
import LoadingIndicator from './LoadingIndicator';
import QueryResultsDisplay from './QueryResultsDisplay';
import MyChart from './MyChart';

interface ChatProps { config: AssistantConfig; identityPoolId: string; userPoolId: string; }

export default function Chat({ config, identityPoolId, userPoolId }: ChatProps) {
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(false);
  const [controlAnswers, setControlAnswers] = useState<ControlAnswer[]>([]);
  const [answers, setAnswers] = useState<Answer[]>([]);
  const [query, setQuery] = useState('');
  const [sessionId] = useState(uuidv4());
  const [errorMessage, setErrorMessage] = useState('');
  const [currentWorkingToolId, setCurrentWorkingToolId] = useState<string | null>(null);
  const [inputHovered, setInputHovered] = useState(false);
  const [inputFocused, setInputFocused] = useState(false);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const isSubmittingRef = useRef(false);
  const maxLength = config.maxLengthInputSearch ?? 500;

  // Auto-scroll only while the agent is actively answering
  useEffect(() => {
    if (!loading) return;
    const el = chatContainerRef.current;
    if (el) {
      requestAnimationFrame(() => {
        el.scrollTop = el.scrollHeight;
      });
    }
  }, [answers, loading]);

  const getAuth = useCallback(async (): Promise<CognitoAuthParams> => {
    const session = await fetchAuthSession();
    const idToken = session.tokens?.idToken?.toString();
    if (!idToken) throw new Error('No ID token — please sign in again');
    return { idToken, identityPoolId, userPoolId };
  }, [identityPoolId, userPoolId]);

  // Auto-generate charts when queryResults arrive
  useEffect(() => {
    const gen = async (i: number, a: Answer) => {
      if (a.queryResults && a.chart === 'loading') {
        try {
          const auth = await getAuth();
          const chartData = await generateChart(a, config.modelIdForChart, auth);
          setAnswers(p => { const n = [...p]; if (n[i]) n[i] = { ...n[i], chart: chartData }; return n; });
        } catch {
          setAnswers(p => { const n = [...p]; if (n[i]) n[i] = { ...n[i], chart: { rationale: 'Error generating chart' } }; return n; });
        }
      }
    };
    answers.forEach((a, i) => { if (a.queryResults && a.chart === 'loading') gen(i, a); });
  }, [answers, config.modelIdForChart, getAuth]);

  const autoResizeTextarea = useCallback(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = `${Math.min(ta.scrollHeight, 150)}px`;
  }, []);

  const handleQuery = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setQuery(val);
    setEnabled(val.trim().length > 0 && !loading);
    autoResizeTextarea();
  };
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && !loading && query.trim() !== '') { e.preventDefault(); handleGetAnswer(query); }
  };
  const handleClick = (e: React.MouseEvent) => { e.preventDefault(); if (query.trim() !== '') handleGetAnswer(query); };
  // Reset textarea height when query is cleared (after sending)
  useEffect(() => {
    if (query === '' && textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [query]);

  const handleGetAnswer = async (myQuery: string) => {
    if (isSubmittingRef.current || loading || !myQuery) return;
    isSubmittingRef.current = true;
    try {
      const auth = await getAuth();
      await getAnswer({ query: myQuery, sessionId, agentRuntimeArn: config.agentRuntimeArn, agentEndpointName: config.agentEndpointName, lastKTurns: config.lastKTurns, questionAnswersTableName: config.questionAnswersTableName, auth, setControlAnswers, setAnswers, setEnabled, setLoading, setErrorMessage, setQuery, setCurrentWorkingToolId });
    } catch (err) { setErrorMessage(String(err)); setLoading(false); } finally { isSubmittingRef.current = false; }
  };
  const handleShowTab = (index: number, type: 'answer' | 'records' | 'chart') => () => {
    setControlAnswers(prev => { const u = [...prev]; u[index] = { ...u[index], current_tab_view: type }; return u; });
  };
  const isChartConfig = (chart: Answer['chart']): chart is ChartConfig =>
    typeof chart === 'object' && chart !== null && 'chart_type' in chart;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {errorMessage && (
        <div style={{ position: 'fixed', top: 64, left: '50%', transform: 'translateX(-50%)', width: '80%', maxWidth: 640, zIndex: 50, background: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c', padding: '12px 16px', borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}>
          <span style={{ fontSize: 14 }}>{errorMessage}</span>
          <button onClick={() => setErrorMessage('')} style={{ marginLeft: 12, color: '#f87171', background: 'none', border: 'none', cursor: 'pointer' }} aria-label="Dismiss error">
            <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
      )}

      {/* Scrollable messages area — flex:1 + minHeight:0 + overflowY:auto = scrollable within flex parent */}
      <div
        id="chatHelper"
        ref={chatContainerRef}
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          paddingLeft: 16,
          paddingRight: 16,
        }}
      >
        {answers.length > 0 ? (
          <ul style={{ paddingBottom: 14, margin: 0, listStyleType: 'none', padding: 0 }}>
            {answers.map((answer, index) => (
              <li key={`msg-${index}`} style={{ marginBottom: 0 }}>
                {answer.text && answer.text.length > 0 && (
                  <div style={{ paddingLeft: 8, paddingRight: 8, display: 'flex', alignItems: 'flex-start', marginBottom: 4 }}>
                    <div style={{ paddingRight: 10, paddingTop: 8, paddingLeft: 4, flexShrink: 0 }}>
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src="/images/genai.png" alt="Amazon Bedrock" width={28} height={28} style={{ width: 28, height: 28 }} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      {controlAnswers[index]?.current_tab_view === 'answer' && (
                        <div className="animate-tab-fade" style={{ marginTop: 8 }}>
                          {answer.text.map((item, ii) => {
                            if (item.type === 'text') return <MarkdownRenderer key={ii} content={item.content} />;
                            if (item.type === 'tool') return <ToolBox key={ii} item={item} isLoading={currentWorkingToolId === item.toolUseId} />;
                            return null;
                          })}
                        </div>
                      )}
                      {answer.queryResults && controlAnswers[index]?.current_tab_view === 'records' && (
                        <div className="animate-tab-fade" style={{ marginTop: 8 }}><QueryResultsDisplay index={index} answer={answer} /></div>
                      )}
                      {isChartConfig(answer.chart) && controlAnswers[index]?.current_tab_view === 'chart' && (
                        <div className="animate-tab-fade" style={{ marginTop: 8 }}>
                          <MyChart caption={answer.chart.caption} options={answer.chart.chart_configuration.options} series={answer.chart.chart_configuration.series} type={answer.chart.chart_type} />
                        </div>
                      )}
                      {answer.queryResults && answer.queryResults.length > 0 && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 0, marginTop: 8, borderTop: '1px solid #e5e7eb' }}>
                          <TabButton active={controlAnswers[index]?.current_tab_view === 'answer'} onClick={handleShowTab(index, 'answer')} icon={<ChatIcon />} label="Answer" />
                          <TabButton active={controlAnswers[index]?.current_tab_view === 'records'} onClick={handleShowTab(index, 'records')} icon={<TableIcon />} label="Records" />
                          {isChartConfig(answer.chart) && <TabButton active={controlAnswers[index]?.current_tab_view === 'chart'} onClick={handleShowTab(index, 'chart')} icon={<ChartIcon />} label="Chart" />}
                          {answer.chart === 'loading' && (
                            <div style={{ display: 'flex', alignItems: 'center', marginLeft: 12, gap: 6 }}>
                              <svg className="animate-spin" style={{ width: 14, height: 14, color: '#7c3aed' }} viewBox="0 0 24 24" fill="none"><circle style={{ opacity: 0.25 }} cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path style={{ opacity: 0.75 }} fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                              <span style={{ fontSize: 12, color: '#9ca3af' }}>Generating chart...</span>
                            </div>
                          )}
                          {typeof answer.chart === 'object' && 'rationale' in answer.chart && <span style={{ fontSize: 12, color: '#9ca3af', marginLeft: 8 }}>{answer.chart.rationale}</span>}
                        </div>
                      )}
                    </div>
                  </div>
                )}
                {answer.query && (
                  <div style={{ display: 'flex', justifyContent: 'flex-end', paddingRight: 8 }}>
                    <div style={{ borderRadius: 20, fontWeight: 500, padding: '10px 18px', marginTop: 14, marginBottom: 10, background: 'linear-gradient(135deg, rgba(124,58,237,0.08) 0%, rgba(168,85,247,0.12) 100%)', border: '1px solid rgba(124,58,237,0.15)', maxWidth: '75%' }}>
                      <p style={{ color: '#1f2937', fontSize: '0.925rem', fontWeight: 500, margin: 0, lineHeight: 1.5 }}>{answer.query}</p>
                    </div>
                  </div>
                )}
              </li>
            ))}
            {loading && <li style={{ paddingLeft: 8, marginTop: 8 }}><LoadingIndicator loading={loading} /></li>}
          </ul>
        ) : (
          <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 24px' }}>
            <div style={{ textAlign: 'center', maxWidth: 560 }}>
              <div style={{ marginBottom: 28 }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/images/agentcore.png" alt="Amazon Bedrock AgentCore" width={120} height={120} style={{ margin: '0 auto', opacity: 0.85 }} />
              </div>
              <h2 style={{ fontWeight: 700, fontSize: '1.75rem', lineHeight: 1.2, marginBottom: 10, color: '#111827', letterSpacing: '-0.025em' }}>Amazon Bedrock AgentCore</h2>
              <p style={{ color: '#9ca3af', fontSize: '1rem', lineHeight: 1.6, marginBottom: 24, fontWeight: 400 }}>Secure, scalable AI agent deployment and operations platform with support for Strands Agent SDK and other frameworks.</p>
              <div style={{ borderRadius: 12, padding: '14px 24px', background: 'linear-gradient(135deg, rgba(124,58,237,0.06) 0%, rgba(168,85,247,0.10) 100%)', border: '1px solid rgba(124,58,237,0.12)' }}>
                <p style={{ color: '#6d28d9', fontWeight: 500, lineHeight: 1.5, margin: 0, fontSize: '0.95rem' }}>{config.welcomeMessage}</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Input bar — fixed at bottom of the flex column */}
      <div style={{ padding: '12px 16px 16px', background: '#fff' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            borderRadius: 28,
            border: (inputHovered || inputFocused) ? '1.5px solid #7c3aed' : '1.5px solid #e2e8f0',
            padding: '4px 4px 4px 14px',
            transition: 'border-color 0.2s',
            background: '#fff',
          }}
          onMouseEnter={() => setInputHovered(true)}
          onMouseLeave={() => setInputHovered(false)}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/images/AWS_logo_RGB.png" alt="AWS" style={{ height: 20, flexShrink: 0, marginRight: 10 }} />
          <textarea
            ref={textareaRef}
            value={query}
            onChange={handleQuery}
            onKeyDown={handleKeyPress}
            onFocus={() => setInputFocused(true)}
            onBlur={() => setInputFocused(false)}
            placeholder="Ask a question..."
            maxLength={maxLength}
            disabled={false}
            rows={1}
            style={{
              flex: 1,
              border: 'none',
              outline: 'none',
              resize: 'none',
              fontSize: '0.925rem',
              lineHeight: '22px',
              padding: '10px 0',
              color: '#1f2937',
              background: 'transparent',
              fontFamily: 'inherit',
              overflow: 'auto',
              maxHeight: 150,
            }}
            aria-label="Ask a question"
          />
          <button
            onClick={handleClick}
            disabled={!enabled || loading}
            style={{
              width: 40,
              height: 40,
              borderRadius: '50%',
              border: 'none',
              background: enabled ? 'linear-gradient(135deg, #7c3aed 0%, #a855f7 100%)' : '#e5e7eb',
              color: '#fff',
              cursor: enabled ? 'pointer' : 'default',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              transition: 'background 0.2s',
            }}
            aria-label="Send message"
          >
            <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

/* ─── Helper components ─── */

function TabButton({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 4,
        padding: '8px 14px',
        fontSize: 13,
        fontWeight: active ? 600 : 400,
        color: active ? '#7c3aed' : '#6b7280',
        background: 'none',
        border: 'none',
        borderBottom: 'none',
        borderTop: active ? '2px solid #7c3aed' : '2px solid transparent',
        cursor: 'pointer',
        transition: 'color 0.15s',
      }}
      aria-label={label}
    >
      {icon}
      {label}
    </button>
  );
}

function ChatIcon() {
  return (
    <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
    </svg>
  );
}

function TableIcon() {
  return (
    <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h18M3 14h18M3 6h18M3 18h18M8 6v12M16 6v12" />
    </svg>
  );
}

function ChartIcon() {
  return (
    <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
    </svg>
  );
}
