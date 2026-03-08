import React, { useEffect, useRef, useState } from 'react';
import { createChart, CandlestickSeries, LineSeries, createSeriesMarkers } from 'lightweight-charts';

export default function PredictionChart({ symbol, interval = "15m", predictionStats }) {
    const chartContainerRef = useRef();
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);
    const chartRef = useRef(null);

    useEffect(() => {
        // Cleanup previous chart on symbol change
        if (chartRef.current) {
            chartRef.current.remove();
            chartRef.current = null;
        }

        const sym = symbol.includes(':')
            ? symbol.split(':')[1].replace('USDT', '')
            : symbol.replace('USDT', '');

        setData(null);
        setError(null);

        const IS_LOCAL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.hostname === '';
        const API_BASE = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE || (!IS_LOCAL ? 'https://ai-bot-backend-u0ur.onrender.com' : 'http://localhost:8000');

        fetch(`${API_BASE}/api/ohlc/${sym}/${interval}`)
            .then(res => res.json())
            .then(d => {
                if (d.error) {
                    setError(d.error);
                } else {
                    setData(d);
                }
            })
            .catch(e => setError(e.message));
    }, [symbol, interval]);

    const activeTrade = predictionStats?.data?.find(d =>
        d.symbol === (symbol.includes(':') ? symbol.split(':')[1].replace('USDT', '') : symbol.replace('USDT', '')) &&
        d.interval === interval &&
        d.was_correct === null
    );

    const isScanning = data?.prediction?.logic?.includes('Awaiting 99.99%') && !activeTrade;

    useEffect(() => {
        if (!data || !chartContainerRef.current) return;

        // Destroy any existing chart first
        if (chartRef.current) {
            chartRef.current.remove();
            chartRef.current = null;
        }

        const el = chartContainerRef.current;
        const width = el.clientWidth || el.offsetWidth || 800;
        const height = el.clientHeight || el.offsetHeight || 480;

        const sym = symbol.includes(':')
            ? symbol.split(':')[1].replace('USDT', '')
            : symbol.replace('USDT', '');

        try {
            const chart = createChart(el, {
                width,
                height,
                layout: {
                    background: { color: '#0a0a12' },
                    textColor: '#d1d4dc',
                },
                grid: {
                    vertLines: { color: 'rgba(42, 46, 57, 0.3)' },
                    horzLines: { color: 'rgba(42, 46, 57, 0.3)' },
                },
                rightPriceScale: {
                    borderColor: 'rgba(197, 203, 206, 0.1)',
                },
                timeScale: {
                    borderColor: 'rgba(197, 203, 206, 0.1)',
                    timeVisible: true,
                    secondsVisible: false,
                },
            });

            chartRef.current = chart;

            // v5 API: addSeries(CandlestickSeries, options)
            const candleSeries = chart.addSeries(CandlestickSeries, {
                upColor: '#26a69a',
                downColor: '#ef5350',
                borderVisible: false,
                wickUpColor: '#26a69a',
                wickDownColor: '#ef5350',
            });

            // Load historical data
            if (data.history && Array.isArray(data.history)) {
                candleSeries.setData(data.history);

                // --- ADD NEW MA/EMA SERIES ---
                const ema7Series = chart.addSeries(LineSeries, { color: '#ffffff', lineWidth: 1, crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false });
                const ema25Series = chart.addSeries(LineSeries, { color: '#ffee58', lineWidth: 1, crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false });
                const ma99Series = chart.addSeries(LineSeries, { color: '#ff9800', lineWidth: 1, crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false });
                const ma200Series = chart.addSeries(LineSeries, { color: '#f44336', lineWidth: 2, crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false });

                const ema7Data = [];
                const ema25Data = [];
                const ma99Data = [];
                const ma200Data = [];

                data.history.forEach(p => {
                    if (p.ema7 !== null && p.ema7 !== undefined) ema7Data.push({ time: p.time, value: p.ema7 });
                    if (p.ema25 !== null && p.ema25 !== undefined) ema25Data.push({ time: p.time, value: p.ema25 });
                    if (p.ma99 !== null && p.ma99 !== undefined) ma99Data.push({ time: p.time, value: p.ma99 });
                    if (p.ma200 !== null && p.ma200 !== undefined) ma200Data.push({ time: p.time, value: p.ma200 });
                });

                if (ema7Data.length > 0) ema7Series.setData(ema7Data);
                if (ema25Data.length > 0) ema25Series.setData(ema25Data);
                if (ma99Data.length > 0) ma99Series.setData(ma99Data);
                if (ma200Data.length > 0) ma200Series.setData(ma200Data);
            }

            // Combined markers (Elliott Wave Pivots + AI Predictions)
            const allMarkers = [];

            // 1. Elliott Wave "Zig-Zag" Lines
            const waveSeries = chart.addSeries(LineSeries, {
                color: '#f39c12',
                lineWidth: 1,
                lineStyle: 2, // Dashed
                axisLabelVisible: false,
                lastValueVisible: false,
                priceLineVisible: false,
                crosshairMarkerVisible: false,
            });

            if (data.wave_pivots && data.wave_pivots.length > 0) {
                const waveLineData = data.wave_pivots.map(p => ({
                    time: p.time,
                    value: p.price
                }));
                waveSeries.setData(waveLineData);

                data.wave_pivots.forEach(p => {
                    allMarkers.push({
                        time: p.time,
                        position: 'belowBar',
                        color: p.color || '#f39c12',
                        shape: 'circle',
                        text: `Wave ${p.label}`,
                        size: 1,
                    });
                });
            }

            // 2. Add future AI "ghost" candles and markers
            if (data.predictions && data.predictions.length > 0) {
                data.predictions.forEach((p, idx) => {
                    candleSeries.update({
                        time: p.time,
                        open: p.open,
                        high: p.high,
                        low: p.low,
                        close: p.close,
                        color: idx === 0 ? (p.color || '#FFD700') : '#555',
                        wickColor: idx === 0 ? (p.color || '#FFD700') : '#555',
                        borderColor: idx === 0 ? (p.color || '#FFD700') : '#555',
                    });

                    allMarkers.push({
                        time: p.time,
                        position: 'aboveBar',
                        color: p.color || '#FFD700',
                        shape: 'arrowDown',
                        text: `AI NEXT ${idx + 1}`,
                        size: 2,
                    });
                });
            } else if (data.prediction) {
                const p = data.prediction;
                candleSeries.update({
                    time: p.time, open: p.open, high: p.high, low: p.low, close: p.close,
                    color: '#FFD700', wickColor: '#FFD700', borderColor: '#FFD700',
                });
                allMarkers.push({
                    time: p.time,
                    position: 'aboveBar',
                    color: p.color || '#FFD700',
                    shape: 'arrowDown',
                    text: 'AI NEXT',
                    size: 2,
                });
            }

            // 3. ICT Institutional Zones (Order Blocks, FVG)
            if (data.ict_zones && data.ict_zones.length > 0) {
                // Use a separate series for ICT levels to avoid cluttering main price action
                const ictSeries = chart.addSeries(LineSeries, {
                    color: 'rgba(255, 255, 255, 0.2)',
                    lineWidth: 1,
                    lineStyle: 3, // Dotted
                    axisLabelVisible: false,
                    lastValueVisible: false,
                    priceLineVisible: false,
                    crosshairMarkerVisible: false,
                });

                data.ict_zones.forEach((z, i) => {
                    if (z.label) { // Primary entry for the zone
                        allMarkers.push({
                            time: z.time,
                            position: 'belowBar',
                            color: z.color || '#aaa',
                            shape: 'square',
                            text: z.label,
                            size: 1,
                        });

                        // Create a temporary price line for the ICT level
                        candleSeries.createPriceLine({
                            price: z.price,
                            color: z.color || 'rgba(255,255,255,0.1)',
                            lineWidth: 1,
                            lineStyle: 3,
                            axisLabelVisible: true,
                            title: z.label,
                        });
                    }
                });
            }

            // Apply all markers at once (v5 API best practice)
            createSeriesMarkers(candleSeries, allMarkers);

            // 4. Overwrite/Overlay with ACTIVE Autopilot Trade if exists
            const activeTrade = predictionStats?.data?.find(d =>
                d.symbol === sym &&
                d.interval === interval &&
                d.was_correct === null
            );

            const displayEntry = activeTrade?.entry || data.prediction?.entry;
            const displayTP = activeTrade?.tp || data.prediction?.tp;
            const displaySL = activeTrade?.sl || data.prediction?.sl;
            const displayRR1 = activeTrade?.rr1 || data.prediction?.rr1;
            const displayRR2 = activeTrade?.rr2 || data.prediction?.rr2;
            const displayRR3 = activeTrade?.rr3 || data.prediction?.rr3;

            if (displayEntry) {
                const labelSuffix = activeTrade ? (activeTrade.is_active ? ' (ACTIVE)' : ' (PENDING)') : '';

                candleSeries.createPriceLine({
                    price: displayEntry,
                    color: '#2196f3', // Blue
                    lineWidth: 2,
                    lineStyle: 2, // Dashed
                    axisLabelVisible: true,
                    title: 'ENTRY' + labelSuffix,
                });

                candleSeries.createPriceLine({
                    price: displayTP,
                    color: '#26a69a', // Green
                    lineWidth: 2,
                    lineStyle: 0, // Solid
                    axisLabelVisible: true,
                    title: 'TAKE PROFIT',
                });

                candleSeries.createPriceLine({
                    price: displaySL,
                    color: '#ef5350', // Red
                    lineWidth: 2,
                    lineStyle: 0, // Solid
                    axisLabelVisible: true,
                    title: 'STOP LOSS',
                });

                // RR Targets
                if (displayRR1) {
                    candleSeries.createPriceLine({
                        price: displayRR1,
                        color: 'rgba(38, 166, 154, 0.4)',
                        lineWidth: 1,
                        lineStyle: 1,
                        axisLabelVisible: true,
                        title: '1:1 RR',
                    });
                }
                if (displayRR2) {
                    candleSeries.createPriceLine({
                        price: displayRR2,
                        color: 'rgba(38, 166, 154, 0.6)',
                        lineWidth: 1,
                        lineStyle: 1,
                        axisLabelVisible: true,
                        title: '1:2 RR',
                    });
                }
                if (displayRR3) {
                    candleSeries.createPriceLine({
                        price: displayRR3,
                        color: 'rgba(38, 166, 154, 0.9)',
                        lineWidth: 2,
                        lineStyle: 1,
                        axisLabelVisible: true,
                        title: '1:3 TARGET ★',
                    });
                }
            }

            chart.timeScale().scrollToRealTime();

            // Handle resize
            const handleResize = () => {
                if (chartRef.current && el) {
                    const w = el.clientWidth || el.offsetWidth || 800;
                    const h = el.clientHeight || el.offsetHeight || 480;
                    chartRef.current.resize(w, h);
                }
            };
            window.addEventListener('resize', handleResize);

            return () => {
                window.removeEventListener('resize', handleResize);
                if (chartRef.current) {
                    chartRef.current.remove();
                    chartRef.current = null;
                }
            };
        } catch (err) {
            setError('Chart render error: ' + err.message);
        }
    }, [data]);

    if (error) {
        return (
            <div style={{
                width: '100%', height: '100%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: '#0a0a12', flexDirection: 'column', gap: '8px'
            }}>
                <span style={{ fontSize: '20px' }}>⚠️</span>
                <div style={{ color: '#ef5350', fontSize: '12px', textAlign: 'center', padding: '0 20px' }}>
                    {error}
                </div>
            </div>
        );
    }

    return (
        <div style={{ width: '100%', height: '100%', background: '#0a0a12', position: 'relative' }}>
            {/* Lightweight Charts will mount into this div */}
            <div ref={chartContainerRef} style={{ width: '100%', height: '100%', opacity: isScanning ? 0.3 : 1 }} />

            {/* Strict 99.99% Filter Overlay */}
            {data && isScanning && (
                <div style={{
                    position: 'absolute', inset: 0, display: 'flex',
                    alignItems: 'center', justifyContent: 'center',
                    flexDirection: 'column', gap: '12px',
                    pointerEvents: 'none', zIndex: 15
                }}>
                    <div style={{ padding: '20px 30px', background: 'rgba(10,12,25,0.85)', border: '1px solid rgba(255,193,7,0.3)', borderRadius: '12px', backdropFilter: 'blur(10px)', textAlign: 'center' }}>
                        <div style={{ fontSize: '24px', letterSpacing: '2px', fontWeight: 900, color: '#ffc107', marginBottom: '8px' }}>
                            <span style={{ display: 'inline-block', animation: 'pulse 2s infinite' }}>🤖</span> SCANNING
                        </div>
                        <div style={{ color: '#e0e0e0', fontSize: '13px', fontWeight: 600 }}>
                            Awaiting <b>99.99%</b> Confluence Setup...
                        </div>
                        <div style={{ color: '#888', fontSize: '10px', marginTop: '6px' }}>
                            Filtering out market noise & low probability zones.
                        </div>
                    </div>
                </div>
            )}

            {/* Loading overlay */}
            {!data && (
                <div style={{
                    position: 'absolute', inset: 0, display: 'flex',
                    alignItems: 'center', justifyContent: 'center',
                    background: 'rgba(10,10,18,0.9)',
                    flexDirection: 'column', gap: '8px',
                    pointerEvents: 'none',
                }}>
                    <div style={{ fontSize: '24px' }}>⚡</div>
                    <div style={{ color: '#aaa', fontSize: '12px' }}>
                        Loading AI Prediction Chart…
                    </div>
                </div>
            )}

            {/* Legend & Logic Context */}
            {data && (
                <div style={{
                    position: 'absolute', top: '12px', left: '12px',
                    display: 'flex', flexDirection: 'column', gap: '4px',
                    pointerEvents: 'none', zIndex: 10,
                }}>
                    <div style={{ display: 'flex', gap: '12px', fontSize: '11px', alignItems: 'center' }}>
                        {/* 📈 Model Performance Badge */}
                        <div style={{
                            display: 'flex', gap: '8px', padding: '2px 8px',
                            background: 'rgba(255,193,7,0.1)', border: '1px solid rgba(255,193,7,0.3)',
                            borderRadius: '4px', fontSize: '9px', fontWeight: 800, marginRight: '8px'
                        }}>
                            <span style={{ color: '#aaa' }}>MODEL ACCURACY: <strong style={{ color: '#ffc107' }}>{predictionStats?.summary?.accuracy || '0%'}</strong></span>
                            <span style={{ color: '#aaa' }}>HITS: <strong style={{ color: '#4caf50' }}>{predictionStats?.summary?.hits || 0}</strong></span>
                            <span style={{ color: '#aaa' }}>MISSES: <strong style={{ color: '#ef5350' }}>{predictionStats?.summary?.misses || 0}</strong></span>
                        </div>

                        <span style={{ color: '#26a69a', fontWeight: 600 }}>▲ Bullish</span>
                        <span style={{ color: '#ef5350', fontWeight: 600 }}>▼ Bearish</span>
                        <span style={{ color: data.prediction?.color || '#FFD700', fontWeight: 700 }}>
                            ★ AI NEXT ({data.prediction?.confidence || '0%'})
                        </span>
                        {/* Institutional context highlight */}
                        <span style={{ color: '#ce93d8', fontSize: '10px', fontWeight: 700, marginLeft: 'auto' }}>
                            {data.ict_summary?.kill_zone?.split(' — ')[0].replace('🕐 ', '') || 'NO SESSION'}
                        </span>
                    </div>
                    {data.prediction?.logic && (
                        <div style={{ fontSize: '9px', color: '#888', fontStyle: 'italic', maxWidth: '300px' }}>
                            Logic: {data.prediction.logic}
                        </div>
                    )}
                    {data.ict_summary?.premium_discount && (
                        <div style={{ fontSize: '9px', color: '#ce93d8', fontWeight: 500, display: 'flex', justifyContent: 'space-between' }}>
                            <span>{data.ict_summary.premium_discount.split('.')[0]}</span>
                            {/* Extract Monte Carlo Result */}
                            {data.prediction?.logic?.includes('Monte Carlo') && (
                                <span style={{ color: '#00bcd4', fontWeight: 700 }}>
                                    ⚛️ {data.prediction.logic.split('Monte Carlo Probability: ')[1]?.split('%')[0]}% Quantum Prob.
                                </span>
                            )}
                        </div>
                    )}

                    {/* MA/EMA Legend */}
                    <div style={{ display: 'flex', gap: '8px', fontSize: '9px', fontWeight: 600, marginTop: '2px', padding: '2px 4px', background: 'rgba(0,0,0,0.5)', borderRadius: '4px', width: 'fit-content' }}>
                        <span style={{ color: '#ffffff' }}>EMA 7</span>
                        <span style={{ color: '#ffee58' }}>EMA 25</span>
                        <span style={{ color: '#ff9800' }}>MA 99</span>
                        <span style={{ color: '#f44336' }}>MA 200</span>
                    </div>

                    {/* AI Trade Signals Panel removed as per user request to clear chart view */}
                </div>
            )}
        </div>
    );
}
