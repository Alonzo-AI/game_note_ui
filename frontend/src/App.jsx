import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { Send, Bot, User, Loader2, Search, BookOpen, ExternalLink, X, Calendar, Users, ChevronDown, ChevronUp } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import PdfViewer from './PdfViewer';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

function App() {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [sportCode, setSportCode] = useState('MFB');
    const [teamName, setTeamName] = useState('');
    const [opponentTeam, setOpponentTeam] = useState('');
    const [gameDate, setGameDate] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isOptionsLoading, setIsOptionsLoading] = useState(true);
    const [filterOptions, setFilterOptions] = useState({
        team_names: [],
        opponent_team_names: [],
        game_dates: []
    });
    const [pdfViewerData, setPdfViewerData] = useState(null);
    const [isGameNotesExpanded, setIsGameNotesExpanded] = useState(true);
    const [isOverviewExpanded, setIsOverviewExpanded] = useState(true);
    const resultsEndRef = useRef(null);

    useEffect(() => {
        const loadFilterOptions = async () => {
            setIsOptionsLoading(true);
            try {
                const response = await axios.get(`${API_BASE_URL}/filter-options`, {
                    params: { sport_code: sportCode }
                });
                setFilterOptions(response.data);
                // Reset other filters if current team is not in new list
                if (!response.data.team_names.includes(teamName)) {
                    setTeamName(response.data.team_names[0] || '');
                }
                setOpponentTeam('');
                setGameDate('');
            } catch (error) {
                console.error('Error loading filter options:', error);
            } finally {
                setIsOptionsLoading(false);
            }
        };

        loadFilterOptions();
    }, [sportCode]);

    const handleSend = async (e) => {
        if (e) e.preventDefault();
        if (!input.trim() || !teamName || isLoading || isOptionsLoading) return;

        const userQuery = input.trim();
        setInput('');
        setIsLoading(true);
        setPdfViewerData(null); // Close PDF on new search

        // We only care about the latest search for the Perplexity feel
        setMessages(prev => [{ role: 'user', content: userQuery }]);

        try {
            const response = await axios.post(`${API_BASE_URL}/chat`, {
                message: userQuery,
                team_name: teamName,
                sport_code: sportCode,
                opponent_team: opponentTeam || null,
                game_date: gameDate || null
            });
            const { reply, chunks } = response.data;
            setMessages(prev => [...prev, {
                role: 'bot',
                content: reply,
                chunks: chunks
            }]);
        } catch (error) {
            console.error('Error sending message:', error);
            setMessages(prev => [...prev, { role: 'bot', content: "Sorry, I encountered an error. Is the backend running?" }]);
        } finally {
            setIsLoading(false);
        }
    };

    const latestResult = messages.find(m => m.role === 'bot');
    const userQuery = messages.find(m => m.role === 'user')?.content;

    const handleSourceClick = async (chunk) => {
        try {
            const { college, season, source_file, page_number } = chunk.metadata;
            if (!college || !season || !source_file) {
                console.error("Missing metadata for PDF viewing:", chunk.metadata);
                return;
            }

            // Set loading state for PDF viewer
            setPdfViewerData({ loading: true });

            const response = await axios.get(`${API_BASE_URL}/pdf-info`, {
                params: { college, season, game_id: source_file }
            });

            setPdfViewerData({
                url: response.data.pdfUrl,
                totalPages: response.data.totalPages,
                page: page_number || 1,
                highlightText: chunk.content
            });
        } catch (error) {
            console.error("Error fetching PDF info:", error);
            setPdfViewerData(null);
            alert("Could not load the requested PDF document.");
        }
    };

    const splitContent = (content) => {
        const separator = "### Game by Game Notes";
        const parts = content.split(separator);
        if (parts.length > 1) {
            return {
                overview: parts[0].trim(),
                gameNotes: separator + parts[1]
            };
        }
        return {
            overview: content,
            gameNotes: ""
        };
    };

    return (
        <div className="search-app">
            <header className="search-header">
                <div className="logo-container">
                    <Bot size={32} color="#818cf8" />
                    <h1>College Game Notes Search</h1>
                </div>
                <form className="search-input-area" onSubmit={handleSend}>
                    <div className="search-input-wrapper">
                        <Search className="search-icon" size={20} />
                        <input
                            type="text"
                            placeholder="Ask anything about the game notes..."
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            disabled={isLoading || isOptionsLoading}
                        />
                        <button
                            type="submit"
                            className="search-button"
                            disabled={!input.trim() || !teamName || isLoading || isOptionsLoading}
                        >
                            {isLoading ? <Loader2 className="animate-spin" size={20} /> : <Send size={20} />}
                        </button>
                    </div>
                    <div className="filter-row">
                        <div className="filter-item sport-selector">
                            <BookOpen size={16} />
                            <select
                                value={sportCode}
                                onChange={(e) => setSportCode(e.target.value)}
                                disabled={isLoading || isOptionsLoading}
                                className="sport-dropdown"
                            >
                                <option value="MFB">MFB</option>
                                <option value="MBB">MBB</option>
                                <option value="WBB">WBB</option>
                            </select>
                        </div>
                        <div className="filter-item">
                            <BookOpen size={16} />
                            <select
                                value={teamName}
                                onChange={(e) => setTeamName(e.target.value)}
                                disabled={isLoading || isOptionsLoading}
                                required
                            >
                                <option value="">{isOptionsLoading ? 'Loading teams...' : 'Select team *'}</option>
                                {filterOptions.team_names.map((team) => (
                                    <option key={team} value={team}>{team}</option>
                                ))}
                            </select>
                        </div>
                        <div className="filter-item">
                            <Users size={16} />
                            <select
                                value={opponentTeam}
                                onChange={(e) => setOpponentTeam(e.target.value)}
                                disabled={isLoading || isOptionsLoading}
                            >
                                <option value="">{isOptionsLoading ? 'Loading opponents...' : 'All opponents'}</option>
                                {filterOptions.opponent_team_names.map((opponent) => (
                                    <option key={opponent} value={opponent}>{opponent}</option>
                                ))}
                            </select>
                            {opponentTeam && (
                                <button type="button" className="clear-filter" onClick={() => setOpponentTeam('')}>
                                    <X size={14} />
                                </button>
                            )}
                        </div>
                        <div className="filter-item">
                            <Calendar size={16} />
                            <select
                                value={gameDate}
                                onChange={(e) => setGameDate(e.target.value)}
                                disabled={isLoading || isOptionsLoading}
                            >
                                <option value="">{isOptionsLoading ? 'Loading dates...' : 'All game dates'}</option>
                                {filterOptions.game_dates.map((date) => (
                                    <option key={date} value={date}>{date}</option>
                                ))}
                            </select>
                            {gameDate && (
                                <button type="button" className="clear-filter" onClick={() => setGameDate('')}>
                                    <X size={14} />
                                </button>
                            )}
                        </div>
                    </div>
                </form>
            </header>

            <main className="search-content">
                {!userQuery && !isLoading && (
                    <div className="empty-state">
                        <h2>Welcome to Coach's Brain</h2>
                        <p>Search through seasons of college sports game notes, player stats, and historic milestones.</p>
                        <p className="empty-state-hint">Select a sport and team first. Opponent and game date are optional filters.</p>
                        <div className="suggested-queries">
                            {['How did Victor Snow perform recently?', "Tell me about Ta'Quan Roberson's record vs UMass", 'Who wears the #41 jersey and why?', 'How many forced fumbles does Red Murdock have?'].map(q => (
                                <button key={q} onClick={() => { setInput(q); }}>{q}</button>
                            ))}
                        </div>
                    </div>
                )}

                {(userQuery || isLoading) && (
                    <div className={`results-container ${pdfViewerData ? 'with-pdf' : ''}`}>
                        <div className="main-answer-column">
                            {userQuery && <h2 className="query-display">{userQuery}</h2>}

                            {isLoading ? (
                                <div className="loading-state">
                                    <div className="shimmer answer-shimmer"></div>
                                    <div className="shimmer answer-sub-shimmer"></div>
                                    <div className="shimmer answer-sub-shimmer" style={{ width: '80%' }}></div>
                                </div>
                            ) : latestResult ? (
                                <div className="answer-card">
                                    <div className="answer-header">
                                        <Bot size={20} />
                                        <span>Answer</span>
                                    </div>
                                    <div className="answer-body">
                                        {splitContent(latestResult.content).gameNotes && (
                                            <div className="game-notes-section">
                                                <button
                                                    className="section-header-btn game-notes-header"
                                                    onClick={() => setIsGameNotesExpanded(!isGameNotesExpanded)}
                                                >
                                                    <div className="section-label">Game by Game Notes</div>
                                                    {isGameNotesExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                                                </button>
                                                {isGameNotesExpanded && (
                                                    <div className="section-content">
                                                        <ReactMarkdown
                                                            components={{
                                                                a: ({ href, children }) => {
                                                                    if (href && href.startsWith('#citation-')) {
                                                                        const index = parseInt(href.replace('#citation-', ''), 10);
                                                                        const chunk = latestResult.chunks?.[index - 1];
                                                                        if (chunk) {
                                                                            return (
                                                                                <button
                                                                                    className="inline-citation"
                                                                                    title={`Go to source [${index}]: ${chunk.metadata?.source_file}`}
                                                                                    onClick={(e) => {
                                                                                        e.preventDefault();
                                                                                        handleSourceClick(chunk);
                                                                                    }}
                                                                                >
                                                                                    [{children}]
                                                                                </button>
                                                                            );
                                                                        }
                                                                    }
                                                                    return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>;
                                                                }
                                                            }}
                                                        >
                                                            {splitContent(latestResult.content).gameNotes.replace(/\[(\d+)\]/g, '[$1](#citation-$1)')}
                                                        </ReactMarkdown>
                                                    </div>
                                                )}
                                            </div>
                                        )}

                                        <div className="overview-section">
                                            <button
                                                className="section-header-btn overview-header"
                                                onClick={() => setIsOverviewExpanded(!isOverviewExpanded)}
                                            >
                                                <div className="section-label">Overview</div>
                                                {isOverviewExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                                            </button>
                                            {isOverviewExpanded && (
                                                <div className="section-content">
                                                    <ReactMarkdown
                                                        components={{
                                                            a: ({ href, children }) => {
                                                                if (href && href.startsWith('#citation-')) {
                                                                    const index = parseInt(href.replace('#citation-', ''), 10);
                                                                    const chunk = latestResult.chunks?.[index - 1];
                                                                    if (chunk) {
                                                                        return (
                                                                            <button
                                                                                className="inline-citation"
                                                                                title={`Go to source [${index}]: ${chunk.metadata?.source_file}`}
                                                                                onClick={(e) => {
                                                                                    e.preventDefault();
                                                                                    handleSourceClick(chunk);
                                                                                }}
                                                                            >
                                                                                [{children}]
                                                                            </button>
                                                                        );
                                                                    }
                                                                }
                                                                return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>;
                                                            }
                                                        }}
                                                    >
                                                        {splitContent(latestResult.content).overview.replace(/\[(\d+)\]/g, '[$1](#citation-$1)')}
                                                    </ReactMarkdown>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            ) : null}
                        </div>

                        <div className="sources-sidebar">
                            <div className="sources-header">
                                <BookOpen size={18} />
                                <h3>Sources</h3>
                            </div>
                            <div className="sources-list">
                                {isLoading ? (
                                    [1, 2, 3].map(i => <div key={i} className="shimmer source-shimmer"></div>)
                                ) : latestResult?.chunks ? (
                                    latestResult.chunks.map((chunk, idx) => (
                                        <div
                                            key={idx}
                                            className="source-card"
                                            onClick={() => handleSourceClick(chunk)}
                                            style={{ cursor: 'pointer' }}
                                        >
                                            <div className="source-meta" style={{ alignItems: 'flex-start' }}>
                                                <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                                                    <span className="source-index-badge">{idx + 1}</span>
                                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                                        <span className="source-tag">{chunk.metadata?.source_file || 'Game Note'}</span>
                                                        <span className="view-pdf-btn">
                                                            <ExternalLink size={12} /> View PDF
                                                        </span>
                                                    </div>
                                                </div>
                                            </div>
                                            <p className="source-snippet">{chunk.content}</p>
                                        </div>
                                    ))
                                ) : (
                                    <p className="no-sources">Retrieve data to see sources here.</p>
                                )}
                            </div>
                        </div>

                        {pdfViewerData && (
                            <div className="pdf-viewer-column">
                                <div className="pdf-viewer-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', background: 'var(--glass)', padding: '12px 16px', borderRadius: '12px', border: '1px solid var(--glass-border)' }}>
                                    <h3 style={{ fontSize: '1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
                                        <ExternalLink size={18} color="#818cf8" />
                                        Source Document
                                    </h3>
                                    <button
                                        onClick={() => setPdfViewerData(null)}
                                        style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '4px', borderRadius: '4px' }}
                                        onMouseOver={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.1)'}
                                        onMouseOut={(e) => e.currentTarget.style.background = 'transparent'}
                                    >
                                        <X size={20} />
                                    </button>
                                </div>
                                {pdfViewerData.loading ? (
                                    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--card-bg)', borderRadius: '12px', border: '1px solid var(--border)' }}>
                                        <Loader2 className="animate-spin" size={32} color="#818cf8" />
                                    </div>
                                ) : (
                                    <PdfViewer
                                        pdfUrl={pdfViewerData.url}
                                        totalPages={pdfViewerData.totalPages}
                                        selectedPage={pdfViewerData.page}
                                        highlightText={pdfViewerData.highlightText}
                                    />
                                )}
                            </div>
                        )}
                    </div>
                )}
            </main>
        </div>
    );
}

export default App;
