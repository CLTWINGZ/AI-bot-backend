import React, { useState, useEffect, useRef } from 'react';
import {
  Send, ShieldAlert, Activity, TrendingUp, TrendingDown,
  BarChart2, Shield, Info, Database, AlertTriangle, Zap,
  Settings, X, Check, Eye, EyeOff, Key, Bot, RefreshCw, BarChart
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import './index.css';
import PredictionChart from './components/PredictionChart';

// ─── Environment Configuration ───────────────────────────────────────────────
const IS_LOCAL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.hostname === '';
const API_BASE = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE || (!IS_LOCAL ? 'https://ai-bot-backend-u0ur.onrender.com' : 'http://localhost:8000');
const WS_BASE = import.meta.env.VITE_WS_URL || import.meta.env.VITE_WS_BASE || (!IS_LOCAL ? 'wss://ai-bot-backend-u0ur.onrender.com' : 'ws://localhost:8000');
// ─────────────────────────────────────────────────────────────────────────────

const INITIAL_MESSAGES = [
  {
    id: 1,
    role: 'ai',
    content: "Welcome to CryptoInsight Alpha. I'm a probabilistic forecasting and market analysis engine. How can I assist you with market intelligence today?",
    isWarning: false
  }
];

const AnalysisRow = ({ stat }) => (
  <div style={{ display: 'flex', flexDirection: 'column', padding: '4px 0', borderBottom: '1px solid rgba(255,255,255,0.05)', fontSize: '9px' }}>
    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
      <span style={{
        color: stat.was_correct === true ? '#4caf50' :
          (stat.was_correct === false ? '#ef5350' :
            (stat.is_active ? '#ffc107' : '#3b82f6')),
        fontWeight: 800
      }}>
        {stat.was_correct === true ? '● HIT' :
          (stat.was_correct === false ? '○ MISS' :
            (stat.is_active ? '⚡ ACTIVE' : '⏳ PENDING'))} {stat.symbol}/{stat.interval}
      </span>
      <span style={{ color: '#666' }}>{`${new Date(stat.time * 1000).getFullYear()}/${String(new Date(stat.time * 1000).getMonth() + 1).padStart(2, '0')}/${String(new Date(stat.time * 1000).getDate()).padStart(2, '0')}`} {new Date(stat.time * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
    </div>
    {/* Entry / TP / SL price row */}
    {stat.entry && (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', marginTop: '4px' }}>
        <div style={{ display: 'flex', gap: '8px', fontSize: '8px' }}>
          <span style={{ color: '#888' }}>ENTRY: <strong style={{ color: '#e0e0e0' }}>${stat.entry?.toLocaleString('en-US', { maximumFractionDigits: 0 })}</strong></span>
          <span style={{ color: '#888' }}>TP: <strong style={{ color: '#4caf50' }}>${stat.tp?.toLocaleString('en-US', { maximumFractionDigits: 0 })}</strong></span>
          <span style={{ color: '#888' }}>SL: <strong style={{ color: '#ef5350' }}>${stat.sl?.toLocaleString('en-US', { maximumFractionDigits: 0 })}</strong></span>
        </div>
        {stat.rr1 && (
          <div style={{ display: 'flex', gap: '6px', fontSize: '7px' }}>
            <span style={{ color: stat.rr1_hit ? '#4caf50' : '#666' }}>1:1 {stat.rr1_hit && '✓'} <strong style={{ color: stat.rr1_hit ? '#81c784' : '#aaa' }}>${stat.rr1?.toLocaleString('en-US', { maximumFractionDigits: 0 })}</strong></span>
            <span style={{ color: stat.rr2_hit ? '#4caf50' : '#666' }}>1:2 {stat.rr2_hit && '✓'} <strong style={{ color: stat.rr2_hit ? '#81c784' : '#aaa' }}>${stat.rr2?.toLocaleString('en-US', { maximumFractionDigits: 0 })}</strong></span>
            <span style={{ color: stat.rr3_hit ? '#4caf50' : '#666' }}>1:3 {stat.rr3_hit && '✓'} <strong style={{ color: stat.rr3_hit ? '#ffc107' : '#aaa' }}>${stat.rr3?.toLocaleString('en-US', { maximumFractionDigits: 0 })}</strong></span>
          </div>
        )}
      </div>
    )}
    {!stat.was_correct && stat.failure_analysis && (
      <div style={{ color: '#aaa', fontStyle: 'italic', fontSize: '8px', marginTop: '1px' }}>
        Result: {stat.failure_analysis}
      </div>
    )}
    {stat.logic && (
      <div style={{ color: '#888', fontStyle: 'italic', fontSize: '8px', marginTop: '1px', borderTop: '1px solid rgba(255,255,255,0.03)', paddingTop: '2px' }}>
        {stat.logic}
      </div>
    )}
  </div>
);

export default function App() {
  const [messages, setMessages] = useState(INITIAL_MESSAGES);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);

  // Real-time market data state
  const [marketData, setMarketData] = useState({
    btc: { symbol: 'BTC', price: 0, change: 0, volume: 0, volatility: 0 },
    eth: { symbol: 'ETH', price: 0, change: 0, volume: 0, volatility: 0 },
    // Mocking 24H volume and volatility for the dashboard aesthetic
    volatility: { value: 'High', status: 'Risk On' },
  });

  const [fearGreed, setFearGreed] = useState({ value: '---', classification: 'Loading...' });
  const [recentIntents, setRecentIntents] = useState(['Awaiting Input...']);

  // Settings modal state
  const [showSettings, setShowSettings] = useState(false);
  const [settingsSaved, setSettingsSaved] = useState(false);
  const [showGeminiKey, setShowGeminiKey] = useState(false);
  const [showOpenAiKey, setShowOpenAiKey] = useState(false);
  const [settingsStatus, setSettingsStatus] = useState({ gemini_configured: false, openai_configured: false, gemini_key_preview: '', openai_key_preview: '' });
  const [settingsForm, setSettingsForm] = useState({
    gemini_api_key: '', openai_api_key: '', openai_api_base: 'https://api.openai.com/v1', llm_model: 'gpt-3.5-turbo'
  });

  // Autopilot state
  const [autopilotOn, setAutopilotOn] = useState(true);       // WebSocket running default start
  const [autopilotPanelOpen, setAutopilotPanelOpen] = useState(true); // overlay visible
  const [autopilotData, setAutopilotData] = useState(null);
  const [autopilotLoading, setAutopilotLoading] = useState(false);
  const [autopilotLastUpdate, setAutopilotLastUpdate] = useState(null);
  const [showAiChart, setShowAiChart] = useState(false);  // Toggle for PredictionChart
  const [selectedInterval, setSelectedInterval] = useState('15m'); // Timeframe state
  const [predictionStats, setPredictionStats] = useState({ data: [], summary: { hits: 0, total: 0, accuracy: '0%' } });
  const autopilotWsRef = useRef(null);

  useEffect(() => {
    fetch('https://api.alternative.me/fng/?limit=1')
      .then(res => res.json())
      .then(data => {
        if (data && data.data && data.data.length > 0) {
          setFearGreed({
            value: data.data[0].value,
            classification: data.data[0].value_classification
          });
        }
      })
      .catch(console.error);

    // Load settings status from backend
    fetch(`${API_BASE}/api/settings`)
      .then(r => r.json())
      .then(s => {
        setSettingsStatus(s);
        // Pre-fill the form with existing non-sensitive values
        setSettingsForm(p => ({
          ...p,
          openai_api_base: s.openai_api_base || p.openai_api_base,
          llm_model: s.llm_model || p.llm_model
        }));
      })
      .catch(() => { });

    // Initial load for prediction stats
    fetch(`${API_BASE}/api/prediction-stats`)
      .then(r => r.json())
      .then(d => setPredictionStats(d))
      .catch(() => { });
  }, []);

  // Sync settings when they are saved or loaded
  useEffect(() => {
    if (settingsStatus) {
      setSettingsForm(p => ({
        ...p,
        openai_api_base: settingsStatus.openai_api_base || p.openai_api_base,
        llm_model: settingsStatus.llm_model || p.llm_model
      }));
    }
  }, [settingsStatus]);

  // Autopilot WebSocket connection
  useEffect(() => {
    if (!autopilotOn) {
      autopilotWsRef.current?.close();
      autopilotWsRef.current = null;
      return;
    }
    setAutopilotLoading(true);
    const ws = new WebSocket(`${WS_BASE}/api/ws/autopilot`);
    autopilotWsRef.current = ws;

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type === 'ping') return;
        if (data.type === 'autopilot') {
          setAutopilotData(data);
          setAutopilotLastUpdate(new Date().toLocaleTimeString());
          setAutopilotLoading(false);
          // Refresh hit/miss stats
          fetch(`${API_BASE}/api/prediction-stats`)
            .then(r => r.json())
            .then(d => setPredictionStats(d))
            .catch(() => { });
        }
        if (data.type === 'autopilot_stats') {
          setPredictionStats(data.stats);
        }
      } catch { }
    };
    ws.onclose = () => setAutopilotLoading(false);
    ws.onerror = () => setAutopilotLoading(false);

    return () => ws.close();
  }, [autopilotOn]);

  const [saveError, setSaveError] = useState(null);

  const handleSaveSettings = async () => {
    setSaveError(null);
    try {
      const res = await fetch(`${API_BASE}/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settingsForm)
      });
      if (res.ok) {
        setSettingsSaved(true);
        // Reload status
        const s = await (await fetch(`${API_BASE}/api/settings`)).json();
        setSettingsStatus(s);
        setTimeout(() => setSettingsSaved(false), 3000);
      } else {
        const errData = await res.json().catch(() => ({}));
        setSaveError(errData.message || 'Failed to save settings. Please check if your backend is running.');
      }
    } catch (e) {
      console.error('Settings save failed', e);
      const host = new URL(API_BASE).hostname;
      setSaveError(`Network error: Could not reach ${host}. Is your Render service awake or CORS blocked? (Error: ${e.message})`);
    }
  };


  // Selected Asset for Chart
  const [selectedAsset, setSelectedAsset] = useState('BINANCE:BTCUSDT');

  const endOfMessagesRef = useRef(null);
  const chatWsRef = useRef(null);          // Persistent chat WebSocket
  const streamingIdRef = useRef(null);     // ID of the currently streaming message

  // ── Connect the persistent Chat WebSocket ─────────────────────────────────
  useEffect(() => {
    const connectChatWs = () => {
      const ws = new WebSocket(`${WS_BASE}/api/ws/chat`);
      chatWsRef.current = ws;

      ws.onmessage = (event) => {
        const frame = JSON.parse(event.data);

        if (frame.typing) {
          setIsTyping(true);
          return;
        }

        if (!frame.done) {
          // Streaming token: append to the in-progress message bubble
          setIsTyping(false);
          setMessages(prev => {
            const last = prev[prev.length - 1];
            if (last && last.id === streamingIdRef.current) {
              return [
                ...prev.slice(0, -1),
                { ...last, content: last.content + frame.token }
              ];
            }
            // First token — create a new bubble
            const newId = Date.now() + 1;
            streamingIdRef.current = newId;
            return [...prev, {
              id: newId,
              role: 'ai',
              content: frame.token,
              isWarning: frame.is_warning || false
            }];
          });
        } else {
          // Final frame — update intent tracker
          streamingIdRef.current = null;
          if (frame.intent) {
            setRecentIntents(prev => {
              const formatted = frame.intent.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
              const filtered = prev.filter(i => i !== 'Awaiting Input...' && i !== formatted);
              return [formatted, ...filtered].slice(0, 4);
            });
          }
        }
      };

      ws.onclose = () => {
        // Auto-reconnect after 2 s if unexpectedly closed
        setTimeout(connectChatWs, 2000);
      };

      ws.onerror = () => ws.close();
    };

    connectChatWs();
    return () => chatWsRef.current?.close();
  }, []);

  // Live Binance WebSocket Integration
  useEffect(() => {
    const ws = new WebSocket('wss://stream.binance.com:9443/ws/btcusdt@ticker/ethusdt@ticker');

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.s === 'BTCUSDT') {
        setMarketData(prev => ({
          ...prev,
          btc: {
            ...prev.btc,
            price: parseFloat(data.c),
            change: parseFloat(data.P),
            volume: parseFloat(data.q),
            volatility: ((parseFloat(data.h) - parseFloat(data.l)) / parseFloat(data.l)) * 100
          }
        }));
      } else if (data.s === 'ETHUSDT') {
        setMarketData(prev => ({
          ...prev,
          eth: {
            ...prev.eth,
            price: parseFloat(data.c),
            change: parseFloat(data.P),
            volume: parseFloat(data.q),
            volatility: ((parseFloat(data.h) - parseFloat(data.l)) / parseFloat(data.l)) * 100
          }
        }));
      }
    };

    return () => {
      ws.close();
    };
  }, []);

  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const handleSend = () => {
    if (!inputValue.trim()) return;
    if (!chatWsRef.current || chatWsRef.current.readyState !== WebSocket.OPEN) {
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: 'ai',
        content: 'Engine connection is warming up…  Please try again in a moment.',
        isWarning: true
      }]);
      return;
    }

    const userMessage = { id: Date.now(), role: 'user', content: inputValue.trim() };
    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsTyping(true);

    chatWsRef.current.send(JSON.stringify({ message: userMessage.content }));
  };

  return (
    <>
      <div className="app-container">
        <div className="bg-ambient"></div>

        {/* Sidebar: Chatbot Layer - HIDE in Full Chart Mode */}
        {!showAiChart && (
          <div className="sidebar glass-panel">
            <div className="heading-md" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Zap size={20} color="var(--accent-primary)" />
              Assistant
              <span className="badge live">Live</span>
              <button
                onClick={() => setShowSettings(true)}
                style={{
                  marginLeft: 'auto', background: 'none', border: '1px solid var(--border-subtle)',
                  borderRadius: '6px', padding: '4px 8px', cursor: 'pointer', color: 'var(--text-secondary)',
                  display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px',
                  transition: 'all 0.2s'
                }}
                title="API Settings"
              >
                <Settings size={13} />
                <span style={{ color: settingsStatus.gemini_configured ? '#4caf50' : '#ff9800' }}>
                  {settingsStatus.gemini_configured ? '✓ Gemini' : 'Setup LLM'}
                </span>
              </button>
            </div>

            <div className="disclaimer-block">
              <ShieldAlert size={16} />
              Not Financial Advice. Models are probabilistic.
            </div>

            <div className="chat-container">
              <div className="chat-messages">
                <AnimatePresence>
                  {messages.map(msg => (
                    <motion.div
                      key={msg.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={`message-bubble ${msg.role === 'user' ? 'message-user' : 'message-ai'}`}
                    >
                      {msg.role === 'ai' ? (
                        <>
                          <div dangerouslySetInnerHTML={{ __html: msg.content.replace(/\!\[(.*?)\]\((.*?)\)/g, '<br><img src="$2" alt="$1" style="max-width: 100%; border-radius: 8px; margin-top: 10px; border: 1px solid var(--border-subtle);" /><br>').replace(/\n\n/g, '<br/><br/>').replace(/\n/g, '<br/>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') }} />
                          {msg.isWarning && (
                            <div className="risk-warning">
                              <AlertTriangle size={16} />
                              <div>
                                <strong>High-Risk Parameter Detected.</strong> Crypto derivatives are highly volatile. This action increases risk of total capital loss.
                              </div>
                            </div>
                          )}
                        </>
                      ) : (
                        msg.content
                      )}
                    </motion.div>
                  ))}
                  {isTyping && (
                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="message-bubble message-ai" style={{ width: '60px', display: 'flex', justifyContent: 'center' }}>
                      <div className="typing-indicator" style={{ color: 'var(--text-secondary)' }}>•••</div>
                    </motion.div>
                  )}
                </AnimatePresence>
                <div ref={endOfMessagesRef} />
              </div>

              <div className="chat-input-wrapper">
                <input
                  type="text"
                  className="chat-input"
                  placeholder="Ask for forecasts, backtests, or market states..."
                  value={inputValue}
                  onChange={e => setInputValue(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleSend()}
                />
                <button className="send-button" onClick={handleSend} disabled={!inputValue.trim()}>
                  <Send size={16} />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Main Content: Intelligence Layer */}
        <div className="main-content" style={{
          padding: showAiChart ? '0' : '20px 24px',
          width: showAiChart ? '100vw' : 'auto',
          height: '100vh',
          overflow: showAiChart ? 'hidden' : 'auto'
        }}>
          {!showAiChart && (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h1 className="heading-lg">Deep Market Intelligence</h1>
              <span style={{ fontSize: '10px', color: 'var(--text-secondary)', opacity: 0.5 }}>v2.2-FINAL-AUTOFIX</span>
            </div>
          )}

          {/* Conditionally hide metrics for "Full Chart" experience */}
          {!showAiChart && (
            <div className="metric-cards">
              {/* Real-time BTC Metric */}
              <div className="metric-card glass-panel" style={{ position: 'relative', cursor: 'pointer', borderColor: selectedAsset === 'BINANCE:BTCUSDT' ? 'var(--accent-primary)' : 'var(--border-subtle)' }} onClick={() => setSelectedAsset('BINANCE:BTCUSDT')}>
                <div className="metric-label">
                  BTC/USDT <Database size={14} />
                </div>
                <div className="metric-value">
                  {marketData.btc.price ? `$${marketData.btc.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : 'Loading...'}
                  <span className={`metric-percent ${marketData.btc.change >= 0 ? 'metric-positive' : 'metric-negative'}`}>
                    {marketData.btc.change >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                    {marketData.btc.change >= 0 ? '+' : ''}{marketData.btc.change.toFixed(2)}%
                  </span>
                </div>
              </div>

              {/* Real-time ETH Metric */}
              <div className="metric-card glass-panel" style={{ position: 'relative', cursor: 'pointer', borderColor: selectedAsset === 'BINANCE:ETHUSDT' ? 'var(--accent-primary)' : 'var(--border-subtle)' }} onClick={() => setSelectedAsset('BINANCE:ETHUSDT')}>
                <div className="metric-label">
                  ETH/USDT <Database size={14} />
                </div>
                <div className="metric-value">
                  {marketData.eth.price ? `$${marketData.eth.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : 'Loading...'}
                  <span className={`metric-percent ${marketData.eth.change >= 0 ? 'metric-positive' : 'metric-negative'}`}>
                    {marketData.eth.change >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                    {marketData.eth.change >= 0 ? '+' : ''}{marketData.eth.change.toFixed(2)}%
                  </span>
                </div>
              </div>

              {/* Live Volume Metric */}
              <div className="metric-card glass-panel">
                <div className="metric-label">
                  24H Vol ({selectedAsset.replace('BINANCE:', '').replace('USDT', '')}) <Database size={14} />
                </div>
                <div className="metric-value">
                  {(() => {
                    const vol = selectedAsset === 'BINANCE:BTCUSDT' ? marketData.btc.volume : marketData.eth.volume;
                    return vol ? `$${((vol * marketData.btc.price) / 1000000000).toFixed(2)}B` : 'Loading...';
                  })()}
                  <span className="metric-percent metric-positive">
                    <Activity size={14} /> Live feed
                  </span>
                </div>
              </div>

              {/* Live Volatility Metric */}
              <div className="metric-card glass-panel">
                <div className="metric-label">
                  24H Volatility ({selectedAsset.replace('BINANCE:', '').replace('USDT', '')}) <Activity size={14} color="var(--accent-primary)" />
                </div>
                <div className="metric-value">
                  {(() => {
                    const volatility = selectedAsset === 'BINANCE:BTCUSDT' ? marketData.btc.volatility : marketData.eth.volatility;
                    return volatility ? `${volatility.toFixed(2)}%` : 'Loading...';
                  })()}
                  <span className="metric-percent metric-negative">
                    Dynamic Range
                  </span>
                </div>
              </div>

              <div className="metric-card glass-panel">
                <div className="metric-label">
                  Fear & Greed Index <Activity size={14} color={fearGreed.classification.includes('Fear') ? 'var(--danger)' : 'var(--success)'} />
                </div>
                <div className="metric-value">
                  {fearGreed.value}
                  <span className={`metric-percent ${fearGreed.classification.includes('Fear') ? 'metric-negative' : 'metric-positive'}`}>
                    {fearGreed.classification}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* ── Chart panel (full width) ── */}
          <div style={{ position: 'relative', flex: 1, width: '100%', height: '100%' }}>
            <div className="glass-panel" style={{
              padding: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column',
              height: showAiChart ? '100vh' : '580px',
              border: showAiChart ? 'none' : '1px solid var(--border-subtle)',
              borderRadius: showAiChart ? '0' : '16px',
              transition: 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)'
            }}>
              {/* Chart header - minimized in AI mode */}
              <div style={{
                padding: showAiChart ? '8px 12px' : '16px 20px',
                borderBottom: '1px solid var(--border-subtle)',
                display: 'flex', gap: '12px', flexShrink: 0, alignItems: 'center',
                background: showAiChart ? 'rgba(0,0,0,0.8)' : 'transparent'
              }}>
                {!showAiChart && (
                  <>
                    <h3 className="heading-md" style={{ margin: 0, fontSize: '1rem' }}>Live Chart ({selectedAsset.replace('BINANCE:', '')})</h3>
                    <span className="badge">TradingView Advanced Array</span>
                    <span className="badge live">Live Socket</span>
                  </>
                )}
                {showAiChart && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{ fontSize: '12px', fontWeight: 900, color: 'var(--accent-primary)', letterSpacing: '1px' }}>AI CORE</div>
                    <div style={{ width: '1px', height: '14px', background: 'var(--border-subtle)' }} />
                    <div style={{ fontSize: '11px', fontWeight: 600, color: '#aaa' }}>{selectedAsset.replace('BINANCE:', '')}</div>
                  </div>
                )}

                {/* Timeframe Selector */}
                <div style={{ display: 'flex', background: 'rgba(255,255,255,0.05)', borderRadius: '6px', padding: '2px', marginLeft: '6px', overflowX: 'auto', maxWidth: '400px', scrollbarWidth: 'none' }}>
                  {['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M'].map(tf => (
                    <button
                      key={tf}
                      onClick={() => setSelectedInterval(tf)}
                      style={{
                        padding: '4px 8px', border: 'none', borderRadius: '4px',
                        fontSize: '10px', fontWeight: 600, cursor: 'pointer',
                        whiteSpace: 'nowrap',
                        background: selectedInterval === tf ? 'var(--accent)' : 'transparent',
                        color: selectedInterval === tf ? '#fff' : 'var(--text-secondary)',
                        transition: '0.2s'
                      }}
                    >
                      {tf}
                    </button>
                  ))}
                </div>

                <button
                  onClick={() => {
                    if (!autopilotOn) {
                      // First time: turn on + show panel
                      setAutopilotOn(true);
                      setAutopilotPanelOpen(true);
                    } else {
                      // Already on: toggle panel visibility
                      setAutopilotPanelOpen(p => !p);
                    }
                  }}
                  style={{
                    marginLeft: 'auto',
                    display: 'flex', alignItems: 'center', gap: '6px',
                    padding: '6px 14px', borderRadius: '8px', border: 'none',
                    cursor: 'pointer', fontWeight: 700, fontSize: '12px',
                    transition: 'all 0.3s',
                    background: autopilotOn
                      ? 'linear-gradient(135deg,#4caf50,#66bb6a)'
                      : 'linear-gradient(135deg,#37474f,#546e7a)',
                    color: '#fff',
                    boxShadow: autopilotOn ? '0 0 12px rgba(76,175,80,0.5)' : 'none',
                  }}
                >
                  <Bot size={14} />
                  {autopilotOn
                    ? (autopilotLoading ? 'Scanning…' : autopilotPanelOpen ? '✓ Autopilot ON' : '↗ Show Panel')
                    : 'Autopilot'}
                </button>
                <button
                  onClick={() => setShowAiChart(p => !p)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '6px',
                    padding: '6px 14px', borderRadius: '8px', border: '1px solid var(--border-subtle)',
                    cursor: 'pointer', fontWeight: 700, fontSize: '12px',
                    background: showAiChart ? 'linear-gradient(135deg,#ff9800,#f57c00)' : 'transparent',
                    color: showAiChart ? '#fff' : 'var(--text-secondary)',
                    transition: 'all 0.3s',
                  }}
                >
                  <BarChart size={14} />
                  {showAiChart ? 'Live View' : 'View AI Model'}
                </button>
              </div>

              {/* Chart content */}
              <div style={{ flex: 1, width: '100%', minHeight: '480px', overflow: 'hidden' }}>
                {showAiChart ? (
                  <PredictionChart
                    symbol={selectedAsset}
                    interval={selectedInterval}
                    predictionStats={predictionStats}
                  />
                ) : (
                  <iframe
                    src={`https://s.tradingview.com/widgetembed/?frameElementId=tradingview_1&symbol=${selectedAsset}&interval=${{ '1m': '1', '5m': '5', '15m': '15', '1h': '60', '4h': '240', '1d': 'D' }[selectedInterval] || '15'}&hidesidetoolbar=1&symboledit=1&saveimage=1&toolbarbg=f1f3f6&studies=%5B%5D&theme=dark&style=1&timezone=Etc%2FUTC&studies_overrides=%7B%7D&overrides=%7B%7D&enabled_features=%5B%5D&disabled_features=%5B%5D&locale=en&utm_source=localhost&utm_medium=widget&utm_campaign=chart&utm_term=${selectedAsset}`}
                    style={{ width: '100%', height: '100%', border: 'none' }}
                    title="TradingView Live Chart"
                  />
                )}
              </div>
            </div>

            {/* ── Autopilot overlay panel ── */}
            <AnimatePresence>
              {autopilotOn && autopilotPanelOpen && (
                <motion.div
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 20 }}
                  className="glass-panel"
                  style={{
                    position: 'absolute', top: 0, right: 0, bottom: 0,
                    width: '340px', overflowY: 'auto',
                    zIndex: 10, borderRadius: '0 16px 16px 0',
                    display: 'flex', flexDirection: 'column',
                    background: 'rgba(10,10,18,0.97)',
                    backdropFilter: 'blur(20px)',
                    borderLeft: '1px solid var(--border-subtle)',
                  }}
                >
                  {/* Header bar */}
                  <div style={{
                    padding: '12px 14px',
                    borderBottom: '1px solid var(--border-subtle)',
                    display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0,
                    background: 'linear-gradient(90deg,rgba(76,175,80,0.1),transparent)'
                  }}>
                    <Bot size={15} color="#4caf50" />
                    <strong style={{ fontSize: '13px', letterSpacing: '0.2px' }}>🤖 Autopilot</strong>
                    <span style={{
                      padding: '2px 7px', borderRadius: '20px', fontSize: '10px',
                      background: 'rgba(76,175,80,0.18)', color: '#4caf50',
                      border: '1px solid rgba(76,175,80,0.4)', fontWeight: 700
                    }}>LIVE</span>
                    {autopilotLoading && (
                      <RefreshCw size={11} color="#4caf50" style={{ animation: 'spin 1s linear infinite' }} />
                    )}
                    {autopilotLastUpdate && (
                      <span style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>
                        {autopilotLastUpdate}
                      </span>
                    )}
                    {/* ── Hide panel (keeps autopilot running) ── */}
                    <button
                      onClick={() => setAutopilotPanelOpen(false)}
                      title="Hide panel — Autopilot stays running in background"
                      style={{
                        marginLeft: 'auto',
                        background: 'rgba(255,255,255,0.06)',
                        border: '1px solid rgba(255,255,255,0.12)',
                        borderRadius: '6px',
                        color: 'var(--text-secondary)',
                        cursor: 'pointer',
                        width: '26px', height: '26px',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: '14px', lineHeight: 1,
                        transition: 'all 0.2s',
                      }}
                      onMouseEnter={e => {
                        e.currentTarget.style.background = 'rgba(255,193,7,0.2)';
                        e.currentTarget.style.borderColor = '#ffc107';
                        e.currentTarget.style.color = '#ffc107';
                      }}
                      onMouseLeave={e => {
                        e.currentTarget.style.background = 'rgba(255,255,255,0.06)';
                        e.currentTarget.style.borderColor = 'rgba(255,255,255,0.12)';
                        e.currentTarget.style.color = 'var(--text-secondary)';
                      }}
                    >
                      ✕
                    </button>
                  </div>

                  {autopilotData ? (() => {
                    const fc = autopilotData.forecasts || {};
                    const cur = fc['1d']?.current;
                    const HORIZON_META = {
                      '1d': { label: 'Next 24H', icon: '🌅', bars: 1 },
                      '1w': { label: 'Next Week', icon: '📆', bars: 7 },
                      '1m': { label: 'Next Month', icon: '🗓️', bars: 30 },
                    };

                    return (
                      <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: '14px', overflowY: 'auto' }}>

                        {/* 📊 Prediction Accuracy Summary (re-analysis of fails) */}
                        <div className="glass-panel" style={{ padding: '12px', background: 'rgba(255,255,255,0.02)' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', alignItems: 'center' }}>
                            <span style={{ fontSize: '11px', fontWeight: 800, color: '#aaa', textTransform: 'uppercase' }}>📡 Model Performance</span>
                            <span style={{ fontSize: '10px', color: '#ffc107', background: 'rgba(255,193,7,0.1)', padding: '2px 6px', borderRadius: '4px' }}>RE-ANALYSIS</span>
                          </div>
                          <div style={{ display: 'flex', gap: '8px' }}>
                            <div style={{ flex: 1 }}>
                              <div style={{ fontSize: '18px', fontWeight: 900 }}>{predictionStats.summary?.accuracy || '0%'}</div>
                              <div style={{ fontSize: '9px', color: '#888' }}>Win Rate</div>
                            </div>
                            <div style={{ flex: 1 }}>
                              <div style={{ fontSize: '18px', fontWeight: 900, color: '#4caf50' }}>{predictionStats.summary?.hits || 0}</div>
                              <div style={{ fontSize: '9px', color: '#888' }}>Hits</div>
                            </div>
                            <div style={{ flex: 1 }}>
                              <div style={{ fontSize: '18px', fontWeight: 900, color: '#ef5350' }}>{predictionStats.summary?.misses || 0}</div>
                              <div style={{ fontSize: '9px', color: '#888' }}>Misses</div>
                            </div>
                            <div style={{ flex: 1 }}>
                              <div style={{ fontSize: '18px', fontWeight: 900, color: '#ffc107' }}>
                                {predictionStats.data.filter(x => x.was_correct === null && x.is_active).length}
                              </div>
                              <div style={{ fontSize: '9px', color: '#888' }}>Active</div>
                            </div>
                            <div style={{ flex: 1 }}>
                              <div style={{ fontSize: '18px', fontWeight: 900, color: '#3b82f6' }}>
                                {predictionStats.data.filter(x => x.was_correct === null && !x.is_active).length}
                              </div>
                              <div style={{ fontSize: '9px', color: '#888' }}>Pending</div>
                            </div>
                          </div>
                          {/* Failure Log Scrollpad */}
                          <div style={{ marginTop: '10px', maxHeight: '250px', overflowY: 'auto', background: 'rgba(0,0,0,0.2)', borderRadius: '4px', padding: '6px' }}>
                            {predictionStats.data.length === 0 ? (
                              <div style={{ fontSize: '9px', color: '#555', fontStyle: 'italic', textAlign: 'center' }}>Awaiting more live samples...</div>
                            ) : (
                              <>
                                {/* ⚡ ACTIVE ANALYSIS SECTION */}
                                <div style={{ marginBottom: '12px' }}>
                                  <div style={{ fontSize: '10px', fontWeight: 800, color: '#ffc107', borderBottom: '1px solid rgba(255,193,7,0.2)', paddingBottom: '2px', marginBottom: '6px' }}>
                                    ⚡ ACTIVE ANALYSIS (ENTRY HIT)
                                  </div>
                                  {predictionStats.data.some(x => x.was_correct === null && x.is_active) ? (
                                    predictionStats.data.filter(x => x.was_correct === null && x.is_active).slice().reverse().map((stat, i) => (
                                      <AnalysisRow key={`active-${i}`} stat={stat} />
                                    ))
                                  ) : (
                                    <div style={{ fontSize: '8px', color: '#555', fontStyle: 'italic', padding: '4px 0' }}>No active entries...</div>
                                  )}
                                </div>

                                {/* ⏳ PENDING ANALYSIS SECTION (90.00%+) */}
                                <div style={{ marginBottom: '12px' }}>
                                  <div style={{ fontSize: '10px', fontWeight: 800, color: '#3b82f6', borderBottom: '1px solid rgba(59,130,246,0.2)', paddingBottom: '2px', marginBottom: '6px' }}>
                                    ⏳ PENDING ANALYSIS (90.00%+)
                                  </div>
                                  {predictionStats.data.some(x => x.was_correct === null && !x.is_active) ? (
                                    predictionStats.data.filter(x => x.was_correct === null && !x.is_active).slice().reverse().map((stat, i) => (
                                      <AnalysisRow key={`pending-${i}`} stat={stat} />
                                    ))
                                  ) : (
                                    <div style={{ fontSize: '8px', color: '#555', fontStyle: 'italic', padding: '4px 0' }}>Scanning for 90.00%+ setups...</div>
                                  )}
                                </div>

                                {/* 📜 RECENT RESULTS SECTION */}
                                {predictionStats.data.some(x => x.was_correct !== null) && (
                                  <div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '2px', marginBottom: '6px' }}>
                                      <div style={{ fontSize: '10px', fontWeight: 800, color: '#aaa' }}>
                                        📜 ALL HISTORICAL DATA
                                      </div>
                                      <button
                                        onClick={() => window.open(`${API_BASE}/api/history/csv`, '_blank')}
                                        style={{ fontSize: '9px', padding: '3px 8px', background: 'rgba(59,130,246,0.2)', color: '#3b82f6', border: '1px solid #3b82f6', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>
                                        Download CSV
                                      </button>
                                    </div>
                                    {predictionStats.data.filter(x => x.was_correct !== null).slice().reverse().map((stat, i) => (
                                      <AnalysisRow key={`hist-${i}`} stat={stat} />
                                    ))}
                                  </div>
                                )}
                              </>
                            )}
                          </div>
                        </div>

                        {/* Current price banner */}
                        {
                          cur && (
                            <div style={{
                              padding: '8px 12px', borderRadius: '8px',
                              background: 'rgba(255,255,255,0.04)',
                              border: '1px solid var(--border-subtle)'
                            }}>
                              <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginBottom: '2px' }}>Live price</div>
                              <div style={{ fontSize: '20px', fontWeight: 900, fontFamily: 'monospace', color: 'var(--text-primary)' }}>
                                ${cur?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                              </div>
                              <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginTop: '4px', display: 'flex', gap: '10px' }}>
                                <span>ATR-14: <strong style={{ color: 'var(--text-primary)' }}>${fc['1d']?.atr?.toLocaleString('en-US', { maximumFractionDigits: 0 })}</strong></span>
                                <span style={{ color: fc['1d']?.trend?.includes('Bullish') ? '#4caf50' : '#ef5350', fontWeight: 700 }}>
                                  {fc['1d']?.trend}
                                </span>
                              </div>
                            </div>
                          )
                        }

                        {/* Forecast cards — stacked vertically */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                          {Object.entries(fc).map(([key, data]) => {
                            const meta = HORIZON_META[key] || { label: key, icon: '📊', bars: 1 };
                            const bull = (data.pct_change ?? 0) >= 0;
                            const accent = bull ? '#4caf50' : '#ef5350';
                            const pct = data.pct_change ?? 0;
                            const range = (data.p90 ?? 0) - (data.p10 ?? 0);
                            const pos = range > 0
                              ? Math.max(0, Math.min(100, ((data.p50 - data.p10) / range) * 100))
                              : 50;

                            return (
                              <motion.div
                                key={key}
                                initial={{ opacity: 0, x: 10 }}
                                animate={{ opacity: 1, x: 0 }}
                                style={{
                                  borderRadius: '12px', padding: '12px 14px',
                                  background: 'var(--bg-tertiary)',
                                  border: `1px solid ${accent}44`,
                                  display: 'flex', flexDirection: 'column', gap: '8px'
                                }}
                              >
                                {/* Title row */}
                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                  <span style={{ fontSize: '14px' }}>{meta.icon}</span>
                                  <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-secondary)' }}>{meta.label}</span>
                                  <span style={{
                                    marginLeft: 'auto', fontSize: '10px', padding: '1px 6px',
                                    borderRadius: '10px', fontWeight: 700,
                                    background: bull ? 'rgba(76,175,80,0.15)' : 'rgba(239,83,80,0.15)',
                                    color: accent
                                  }}>{bull ? '▲ BULL' : '▼ BEAR'}</span>
                                </div>
                                {/* Price + pct */}
                                <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
                                  <span style={{ fontSize: '20px', fontWeight: 900, color: accent, fontFamily: 'monospace' }}>
                                    ${data.p50?.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                                  </span>
                                  <span style={{ fontSize: '12px', color: accent, fontWeight: 600 }}>
                                    {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%
                                  </span>
                                </div>
                                {/* Probability bar */}
                                <div>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--text-secondary)', marginBottom: '3px' }}>
                                    <span>🔻 ${data.p10?.toLocaleString('en-US', { maximumFractionDigits: 0 })}</span>
                                    <span>🔼 ${data.p90?.toLocaleString('en-US', { maximumFractionDigits: 0 })}</span>
                                  </div>
                                  <div style={{ height: '5px', borderRadius: '3px', background: 'var(--bg-secondary)', position: 'relative', overflow: 'hidden' }}>
                                    <div style={{
                                      position: 'absolute', left: 0, top: 0, bottom: 0, width: `${pos}%`,
                                      background: `linear-gradient(90deg,#ef535099,${accent})`,
                                      borderRadius: '3px', transition: 'width 0.8s'
                                    }} />
                                    <div style={{
                                      position: 'absolute', top: '-1px', bottom: '-1px',
                                      left: `calc(${pos}% - 2px)`, width: '3px',
                                      background: '#fff', borderRadius: '2px', opacity: 0.9
                                    }} />
                                  </div>
                                </div>
                                {/* Stats */}
                                <div style={{ display: 'flex', gap: '10px', fontSize: '10px', color: 'var(--text-secondary)', borderTop: '1px solid var(--border-subtle)', paddingTop: '6px' }}>
                                  <span>ATR <strong style={{ color: 'var(--text-primary)' }}>${data.atr?.toLocaleString('en-US', { maximumFractionDigits: 0 }) ?? '–'}</strong></span>
                                  <span>{meta.bars}d fwd</span>
                                </div>
                              </motion.div>
                            );
                          })}
                        </div>

                        {/* 1m Live Signal */}
                        {
                          autopilotData.pattern_1m && !autopilotData.pattern_1m.includes('Awaiting 99.99%') && (
                            <div style={{
                              background: 'rgba(100,181,246,0.05)',
                              border: '1px solid rgba(100,181,246,0.2)',
                              borderRadius: '10px', padding: '12px 14px'
                            }}>
                              <div style={{ fontWeight: 700, fontSize: '11px', color: '#64b5f6', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '5px' }}>
                                <Zap size={12} /> ⚡ 1m Live Signals
                              </div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                {autopilotData.pattern_1m
                                  .split('\n')
                                  .filter(l => l.trim().startsWith('-'))
                                  .slice(0, 5)
                                  .map((line, i) => (
                                    <div key={i} style={{
                                      fontSize: '11px', color: 'var(--text-secondary)',
                                      padding: '5px 8px', borderRadius: '5px',
                                      background: 'var(--bg-tertiary)', lineHeight: '1.4'
                                    }}
                                      dangerouslySetInnerHTML={{
                                        __html: line
                                          .replace(/^-\s*/, '')
                                          .replace(/\*\*(.*?)\*\*/g, '<strong style="color:var(--text-primary)">$1</strong>')
                                      }}
                                    />
                                  ))}
                              </div>
                            </div>
                          )
                        }

                        <div style={{ fontSize: '10px', color: 'var(--text-secondary)', opacity: 0.5, textAlign: 'center' }}>
                          LinReg + ATR-14 · Binance live data · 60s refresh
                        </div>
                      </div>
                    );
                  })() : autopilotLoading ? (
                    <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                      <RefreshCw size={24} color="#4caf50" style={{ animation: 'spin 1s linear infinite', marginBottom: '12px' }} />
                      <div style={{ fontSize: '13px', fontWeight: 600 }}>Scanning markets…</div>
                      <div style={{ fontSize: '11px', marginTop: '6px', opacity: 0.6 }}>1m · 1d · 7d · 30d klines</div>
                    </div>
                  ) : null}
                </motion.div>
              )}
            </AnimatePresence>
          </div>{/* end relative chart wrapper */}

          {!showAiChart && (
            <div style={{ display: 'flex', gap: '16px' }}>
              <div className="glass-panel" style={{ flex: 1 }}>
                <h3 className="heading-md" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Shield size={18} color="var(--success)" />
                  Model Governance
                </h3>
                <ul className="text-subtle" style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <li>• System Status: <strong>Operational</strong></li>
                  <li>• Last Retraining: Live (Incremental)</li>
                  <li>• Drift Detection: <strong style={{ color: (selectedAsset === 'BINANCE:BTCUSDT' ? marketData.btc.volatility : marketData.eth.volatility) > 5 ? 'var(--danger)' : 'var(--success)' }}>
                    {(selectedAsset === 'BINANCE:BTCUSDT' ? marketData.btc.volatility : marketData.eth.volatility) > 5 ? 'Anomaly Detected (High Vol)' : 'Normal'}
                  </strong></li>
                  <li>• Market Data Subsystems: <strong style={{ color: 'var(--success)' }}>Connected (WSS)</strong></li>
                </ul>
              </div>
              <div className="glass-panel" style={{ flex: 1 }}>
                <h3 className="heading-md" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Info size={18} color="var(--accent-primary)" />
                  Intents Recognized
                </h3>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  {recentIntents.map((intent, idx) => (
                    <span key={idx} className="badge" style={{ backgroundColor: intent === 'High Risk Flagged' ? 'var(--danger-bg)' : 'var(--bg-tertiary)', borderColor: intent === 'High Risk Flagged' ? 'var(--danger)' : 'var(--border-subtle)' }}>
                      {intent}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Settings Modal */}
        <AnimatePresence>
          {showSettings && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              style={{
                position: 'fixed', inset: 0, zIndex: 9999,
                background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
              onClick={(e) => e.target === e.currentTarget && setShowSettings(false)}
            >
              <motion.div
                initial={{ scale: 0.9, opacity: 0, y: 20 }}
                animate={{ scale: 1, opacity: 1, y: 0 }}
                exit={{ scale: 0.9, opacity: 0 }}
                style={{
                  width: '480px', background: 'var(--bg-secondary)',
                  border: '1px solid var(--border-subtle)', borderRadius: '16px',
                  padding: '28px', boxShadow: '0 24px 60px rgba(0,0,0,0.5)',
                }}
              >
                {/* Header */}
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: '20px' }}>
                  <Key size={18} color="var(--accent-primary)" style={{ marginRight: '10px' }} />
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '15px' }}>LLM API Configuration</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>Keys are saved locally and activated immediately</div>
                  </div>
                  <button onClick={() => setShowSettings(false)}
                    style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)', padding: '4px' }}>
                    <X size={18} />
                  </button>
                </div>

                {/* Status badges */}
                <div style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
                  <span style={{
                    padding: '4px 10px', borderRadius: '20px', fontSize: '11px', fontWeight: 600,
                    background: settingsStatus.gemini_configured ? 'rgba(76,175,80,0.15)' : 'rgba(255,152,0,0.15)',
                    color: settingsStatus.gemini_configured ? '#4caf50' : '#ff9800',
                    border: `1px solid ${settingsStatus.gemini_configured ? '#4caf50' : '#ff9800'}44`
                  }}>
                    {settingsStatus.gemini_configured ? '✓' : '○'} Gemini {settingsStatus.gemini_key_preview}
                  </span>
                  <span style={{
                    padding: '4px 10px', borderRadius: '20px', fontSize: '11px', fontWeight: 600,
                    background: settingsStatus.openai_configured ? 'rgba(76,175,80,0.15)' : 'rgba(100,100,100,0.15)',
                    color: settingsStatus.openai_configured ? '#4caf50' : 'var(--text-secondary)',
                    border: `1px solid ${settingsStatus.openai_configured ? '#4caf5044' : 'var(--border-subtle)'}`
                  }}>
                    {settingsStatus.openai_configured ? '✓' : '○'} OpenAI {settingsStatus.openai_key_preview}
                  </span>
                </div>

                {/* Gemini Key */}
                <div style={{ marginBottom: '16px' }}>
                  <label style={{
                    fontSize: '11px', color: 'var(--text-secondary)', fontWeight: 600,
                    display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px'
                  }}>
                    <span style={{ background: '#4285F4', color: '#fff', borderRadius: '4px', padding: '1px 5px', fontSize: '10px' }}>G</span>
                    Google Gemini API Key
                    <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noreferrer"
                      style={{ marginLeft: 'auto', color: 'var(--accent-primary)', fontSize: '10px', textDecoration: 'none' }}>
                      Get free key →
                    </a>
                  </label>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <input
                      type={showGeminiKey ? 'text' : 'password'}
                      placeholder="AIzaSy..."
                      value={settingsForm.gemini_api_key}
                      onChange={e => setSettingsForm(p => ({ ...p, gemini_api_key: e.target.value }))}
                      style={{
                        flex: 1, background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)',
                        borderRadius: '8px', padding: '9px 12px', color: 'var(--text-primary)', fontSize: '13px',
                        fontFamily: 'monospace', outline: 'none',
                      }}
                    />
                    <button onClick={() => setShowGeminiKey(p => !p)}
                      style={{
                        background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)', borderRadius: '8px',
                        padding: '0 10px', cursor: 'pointer', color: 'var(--text-secondary)'
                      }}>
                      {showGeminiKey ? <EyeOff size={14} /> : <Eye size={14} />}
                    </button>
                  </div>
                </div>

                {/* OpenAI Key */}
                <div style={{ marginBottom: '16px' }}>
                  <label style={{
                    fontSize: '11px', color: 'var(--text-secondary)', fontWeight: 600,
                    display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px'
                  }}>
                    <span style={{ background: '#10a37f', color: '#fff', borderRadius: '4px', padding: '1px 5px', fontSize: '10px' }}>AI</span>
                    OpenAI / Groq Key <span style={{ fontWeight: 400, opacity: 0.6 }}>(optional)</span>
                  </label>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <input
                      type={showOpenAiKey ? 'text' : 'password'}
                      placeholder="sk-... or gsk_..."
                      value={settingsForm.openai_api_key}
                      onChange={e => setSettingsForm(p => ({ ...p, openai_api_key: e.target.value }))}
                      style={{
                        flex: 1, background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)',
                        borderRadius: '8px', padding: '9px 12px', color: 'var(--text-primary)', fontSize: '13px',
                        fontFamily: 'monospace', outline: 'none',
                      }}
                    />
                    <button onClick={() => setShowOpenAiKey(p => !p)}
                      style={{
                        background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)', borderRadius: '8px',
                        padding: '0 10px', cursor: 'pointer', color: 'var(--text-secondary)'
                      }}>
                      {showOpenAiKey ? <EyeOff size={14} /> : <Eye size={14} />}
                    </button>
                  </div>
                </div>

                {/* API Base & Model */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '20px' }}>
                  <div>
                    <label style={{ fontSize: '11px', color: 'var(--text-secondary)', fontWeight: 600, display: 'block', marginBottom: '6px' }}>API Base URL</label>
                    <input
                      type="text"
                      placeholder="https://api.openai.com/v1"
                      value={settingsForm.openai_api_base}
                      onChange={e => setSettingsForm(p => ({ ...p, openai_api_base: e.target.value }))}
                      style={{
                        width: '100%', boxSizing: 'border-box', background: 'var(--bg-tertiary)',
                        border: '1px solid var(--border-subtle)', borderRadius: '8px',
                        padding: '9px 12px', color: 'var(--text-primary)', fontSize: '12px', outline: 'none',
                      }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '11px', color: 'var(--text-secondary)', fontWeight: 600, display: 'block', marginBottom: '6px' }}>Model</label>
                    <select
                      value={settingsForm.llm_model}
                      onChange={e => setSettingsForm(p => ({ ...p, llm_model: e.target.value }))}
                      style={{
                        width: '100%', background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)',
                        borderRadius: '8px', padding: '9px 12px', color: 'var(--text-primary)', fontSize: '12px', outline: 'none',
                      }}
                    >
                      <option value="gemini-1.5-flash">gemini-1.5-flash (Gemini)</option>
                      <option value="gemini-1.5-pro">gemini-1.5-pro (Gemini)</option>
                      <option value="gpt-4o">gpt-4o (OpenAI)</option>
                      <option value="gpt-3.5-turbo">gpt-3.5-turbo (OpenAI)</option>
                      <option value="llama3-8b-8192">llama3-8b-8192 (Groq)</option>
                      <option value="llama3">llama3 (Ollama local)</option>
                    </select>
                  </div>
                </div>

                {/* Quick tips */}
                <div style={{
                  background: 'rgba(100,181,246,0.07)', border: '1px solid rgba(100,181,246,0.2)',
                  borderRadius: '8px', padding: '10px 12px', fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '10px'
                }}>
                  💡 <strong>Deployment Tip:</strong> For permanent settings on Render or Vercel, add <code>GEMINI_API_KEY</code> to your dashboard's Environment Variables.
                </div>

                <div style={{
                  background: 'rgba(100,181,246,0.07)', border: '1px solid rgba(100,181,246,0.2)',
                  borderRadius: '8px', padding: '10px 12px', fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '20px'
                }}>
                  💡 <strong>Groq (free &amp; fast):</strong> Set base URL to <code style={{ color: 'var(--accent-primary)' }}>https://api.groq.com/openai/v1</code> and paste your Groq key. Model: <code style={{ color: 'var(--accent-primary)' }}>llama3-8b-8192</code>
                </div>

                {/* Error Display */}
                {saveError && (
                  <div style={{
                    marginBottom: '16px', padding: '10px', borderRadius: '8px',
                    background: 'rgba(239,83,80,0.1)', border: '1px solid rgba(239,83,80,0.3)',
                    color: '#ef5350', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '8px'
                  }}>
                    <ShieldAlert size={14} />
                    {saveError}
                  </div>
                )}

                {/* Save button */}
                <button
                  onClick={handleSaveSettings}
                  style={{
                    width: '100%', padding: '11px', borderRadius: '10px', border: 'none', cursor: 'pointer',
                    fontWeight: 700, fontSize: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                    background: settingsSaved
                      ? 'linear-gradient(135deg,#4caf50,#81c784)'
                      : (saveError
                        ? 'linear-gradient(135deg,#37474f,#546e7a)'
                        : 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))'),
                    color: '#fff', transition: 'all 0.3s',
                  }}
                >
                  {settingsSaved ? <><Check size={16} /> Saved &amp; Activated!</> : <><Key size={16} /> Save API Keys</>}
                </button>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </div >
    </>
  );
}
