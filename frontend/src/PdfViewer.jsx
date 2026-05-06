import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

// Set up PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@5.4.296/build/pdf.worker.min.mjs`;

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

const PdfViewer = ({ pdfUrl, totalPages, selectedPage, highlightText }) => {
    const [numPages, setNumPages] = useState(null);
    const [pageNumber, setPageNumber] = useState(selectedPage || 1);
    const [highlights, setHighlights] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const containerRef = useRef(null);
    const pdfRef = useRef(null);

    // Cache buster only for the initial load of a new URL
    const stablePdfUrl = useMemo(() => {
        if (!pdfUrl) return null;
        return `${API_BASE_URL}${pdfUrl}`;
    }, [pdfUrl]);

    useEffect(() => {
        if (selectedPage) {
            setPageNumber(selectedPage);
        }
    }, [selectedPage]);

    useEffect(() => {
        if (highlightText && pageNumber && pdfRef.current) {
            findAndHighlightText(highlightText, pageNumber);
        } else {
            setHighlights([]);
        }
    }, [highlightText, pageNumber]);

    // Scroll the PDF container to the highlight position after it renders
    useEffect(() => {
        if (highlights.length > 0 && containerRef.current) {
            const highlight = highlights[0];
            // highlight.top is in PDF viewport pixels; scroll to it with some offset
            const scrollTarget = highlight.y - 80;  // 80px top padding for context
            containerRef.current.scrollTo({
                top: Math.max(0, scrollTarget),
                behavior: 'smooth'
            });
        }
    }, [highlights]);

    const onDocumentLoadSuccess = (pdf) => {
        console.log('PDF loaded successfully via Document component');
        setNumPages(pdf.numPages);
        pdfRef.current = pdf;
        setLoading(false);
        setError(null);

        // If we already have a highlight text waiting, process it
        if (highlightText && pageNumber) {
            findAndHighlightText(highlightText, pageNumber);
        }
    };

    const onDocumentLoadError = (err) => {
        console.error('Error loading PDF:', err);
        setError(err.message || 'Unknown error occurred while loading PDF');
        setLoading(false);
    };

    const findAndHighlightText = async (textToFind, pageNum) => {
        if (!textToFind || !pageNum || !pdfRef.current) return;

        try {
            const page = await pdfRef.current.getPage(pageNum);
            const scale = 1.2;
            const viewport = page.getViewport({ scale });
            const textContent = await page.getTextContent();

            // Simplified highlighting: find the first line that matches some part of the text
            // In a real scenario, we might want more complex matching.
            const bestHighlight = matchTextToItems(textContent.items, textToFind, viewport);
            setHighlights(bestHighlight ? [bestHighlight] : []);
        } catch (err) {
            console.error('Error finding text to highlight:', err);
            setHighlights([]);
        }
    };

    const matchTextToItems = (textItems, searchText, viewport) => {
        if (!searchText || !textItems || textItems.length === 0) return null;

        // Clean up the search text and split it into words
        const cleanSearchText = searchText.replace(/\s+/g, ' ').toLowerCase().trim();
        const searchWords = cleanSearchText.split(' ').filter(w => w.length > 2);

        if (searchWords.length === 0) return null;

        let bestMatchIndex = -1;
        let bestMatchScore = 0;
        let matchLength = 0;

        // Try to find the start of the chunk in the PDF text items
        for (let i = 0; i < textItems.length; i++) {
            let score = 0;
            let currentLength = 0;
            let combinedText = '';

            // Look ahead to build a string to match against
            for (let j = i; j < Math.min(i + 20, textItems.length); j++) {
                combinedText += ' ' + textItems[j].str.toLowerCase();
            }

            // Check how many of the first few search words are in this combined string
            const wordsToCheck = searchWords.slice(0, 5);
            for (const word of wordsToCheck) {
                if (combinedText.includes(word)) {
                    score++;
                }
            }

            if (score > bestMatchScore) {
                bestMatchScore = score;
                bestMatchIndex = i;

                // Now figure out how many items this chunk spans
                let spanText = '';
                for (let k = i; k < textItems.length; k++) {
                    spanText += ' ' + textItems[k].str.toLowerCase();
                    currentLength++;
                    // If we've found most of the words, stop extending the box
                    let wordsFound = searchWords.filter(w => spanText.includes(w)).length;
                    if (wordsFound >= searchWords.length * 0.7 || spanText.length > cleanSearchText.length * 1.5) {
                        break;
                    }
                }
                matchLength = currentLength;
            }
        }

        if (bestMatchIndex === -1 || bestMatchScore === 0) return null;

        // Create bounding box for the matched items
        const matchedItems = textItems.slice(bestMatchIndex, bestMatchIndex + Math.max(matchLength, 1));

        const minX = Math.min(...matchedItems.map(i => i.transform[4]));
        const maxX = Math.max(...matchedItems.map(i => i.transform[4] + i.width));
        const minY = Math.min(...matchedItems.map(i => i.transform[5]));
        const maxY = Math.max(...matchedItems.map(i => i.transform[5] + i.height));

        const rect = viewport.convertToViewportRectangle([minX, minY, maxX, maxY]);

        return {
            x: Math.min(rect[0], rect[2]) - 5,
            y: Math.min(rect[1], rect[3]) - 2,
            width: Math.abs(rect[2] - rect[0]) + 10,
            height: Math.abs(rect[3] - rect[1]) + 4
        };
    };

    const renderHighlights = () => {
        return highlights.map((highlight, index) => (
            <div
                key={index}
                className="pdf-highlight-overlay"
                style={{
                    position: 'absolute',
                    left: `${highlight.x}px`,
                    top: `${highlight.y}px`,
                    width: `${highlight.width}px`,
                    height: `${highlight.height}px`,
                    backgroundColor: 'rgba(255, 255, 0, 0.35)',
                    border: '2px solid #ff6b35',
                    borderRadius: '2px',
                    pointerEvents: 'none',
                    zIndex: 20,
                    boxShadow: '0 0 8px rgba(255, 107, 53, 0.3)'
                }}
            />
        ));
    };

    if (!pdfUrl) {
        return (
            <div className="pdf-placeholder" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#a1a1aa' }}>
                <p>Select a source to view the document.</p>
            </div>
        );
    }

    return (
        <div className="pdf-viewer-wrapper" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', background: '#18181b', borderRadius: '12px' }}>
            <div
                className="pdf-viewer-container"
                ref={containerRef}
                style={{
                    flex: 1,
                    overflow: 'auto',
                    padding: '20px',
                    position: 'relative',
                    minHeight: '200px'
                }}
            >
                {loading && (
                    <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', zIndex: 30 }}>
                        <p style={{ color: '#fafafa' }}>Loading PDF...</p>
                    </div>
                )}
                {error && (
                    <div style={{ color: '#ef4444', padding: '20px', textAlign: 'center', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '8px', margin: '20px' }}>
                        <p>Error: {error}</p>
                    </div>
                )}
                <div style={{ display: 'flex', justifyContent: 'center' }}>
                    <Document
                        file={stablePdfUrl}
                        onLoadSuccess={onDocumentLoadSuccess}
                        onLoadError={onDocumentLoadError}
                        loading={null}
                    >
                        <div style={{ position: 'relative', boxShadow: '0 4px 20px rgba(0,0,0,0.5)', background: 'white' }}>
                            <Page
                                pageNumber={pageNumber}
                                renderTextLayer={true}
                                renderAnnotationLayer={false}
                                scale={1.2}
                                loading={null}
                            />
                            {renderHighlights()}
                        </div>
                    </Document>
                </div>
            </div>

            <div className="pdf-info-footer" style={{
                padding: '12px',
                borderTop: '1px solid rgba(255, 255, 255, 0.1)',
                background: '#18181b',
                minHeight: '50px',
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center'
            }}>
                {numPages ? (
                    <div className="pdf-navigation" style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
                        <button
                            onClick={() => setPageNumber(Math.max(1, pageNumber - 1))}
                            disabled={pageNumber <= 1}
                            style={{
                                padding: '6px 16px',
                                borderRadius: '6px',
                                border: '1px solid rgba(255, 255, 255, 0.1)',
                                background: pageNumber <= 1 ? 'transparent' : 'rgba(255, 255, 255, 0.05)',
                                color: pageNumber <= 1 ? '#52525b' : '#fafafa',
                                cursor: pageNumber <= 1 ? 'not-allowed' : 'pointer',
                                fontWeight: 500
                            }}
                        >
                            Previous
                        </button>
                        <span style={{ fontSize: '0.9rem', color: '#a1a1aa', fontWeight: 600, minWidth: '100px', textAlign: 'center' }}>
                            Page {pageNumber} of {numPages}
                        </span>
                        <button
                            onClick={() => setPageNumber(Math.min(numPages, pageNumber + 1))}
                            disabled={pageNumber >= numPages}
                            style={{
                                padding: '6px 16px',
                                borderRadius: '6px',
                                border: '1px solid rgba(255, 255, 255, 0.1)',
                                background: pageNumber >= numPages ? 'transparent' : 'rgba(255, 255, 255, 0.05)',
                                color: pageNumber >= numPages ? '#52525b' : '#fafafa',
                                cursor: pageNumber >= numPages ? 'not-allowed' : 'pointer',
                                fontWeight: 500
                            }}
                        >
                            Next
                        </button>
                    </div>
                ) : !loading && !error && (
                    <span style={{ color: '#71717a', fontSize: '0.85rem' }}>Initializing viewer...</span>
                )}
            </div>
        </div>
    );
};

export default PdfViewer;
