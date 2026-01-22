"use client";
import React, { useState, useEffect } from 'react';
import { api, RouteOption, NearbyVibe } from '@/lib/api';
import dynamic from 'next/dynamic';
import { Search, AlertTriangle, Star, Users, X, Navigation } from 'lucide-react';

const MapComponent = dynamic(() => import('@/components/Map'), {
    ssr: false,
    loading: () => <div className="w-full h-full bg-zinc-900 flex items-center justify-center text-white">Loading Map...</div>
});

// NYC Center (Times Sq)
const DEFAULT_START = { lat: 40.7505, lng: -73.9934 };
const DEFAULT_END = { lat: 40.758, lng: -73.9855 };

export default function Home() {
    const [routes, setRoutes] = useState<RouteOption[]>([]);
    const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
    const [isReporting, setIsReporting] = useState(false);
    const [reportModalOpen, setReportModalOpen] = useState(false);
    const [reportLocation, setReportLocation] = useState<{ lat: number, lng: number } | null>(null);
    const [reportText, setReportText] = useState("");
    const [currentStart, setCurrentStart] = useState(DEFAULT_START);
    const [currentEnd, setCurrentEnd] = useState(DEFAULT_END);
    const [mapCenter, setMapCenter] = useState(DEFAULT_START);

    // Search inputs
    const [startInput, setStartInput] = useState(`${DEFAULT_START.lat}, ${DEFAULT_START.lng}`);
    const [endInput, setEndInput] = useState(`${DEFAULT_END.lat}, ${DEFAULT_END.lng}`);

    // Vibes Modal State
    const [vibesModalOpen, setVibesModalOpen] = useState(false);
    const [nearbyVibes, setNearbyVibes] = useState<NearbyVibe[]>([]);
    const [vibesLoading, setVibesLoading] = useState(false);

    // Initial Load
    useEffect(() => {
        api.getRoutes(currentStart, currentEnd).then(data => {
            setRoutes(data);
            if (data.length > 0 && data[0].path?.length > 0) {
                setMapCenter(data[0].path[0]);
            }
        }).catch((err: any) => console.error(err));
    }, []);

    const handleMapClick = async (lat: number, lng: number) => {
        if (isReporting) {
            setReportLocation({ lat, lng });
            setReportModalOpen(true);
            setIsReporting(false);
        } else {
            // Show nearby vibes modal
            setVibesLoading(true);
            setVibesModalOpen(true);
            try {
                const data = await api.getNearbyVibes(lat, lng);
                setNearbyVibes(data.vibes);
            } catch (err) {
                console.error(err);
                setNearbyVibes([]);
            }
            setVibesLoading(false);
        }
    };

    const submitReport = async () => {
        if (!reportLocation) return;
        await api.reportVibe(reportLocation.lat, reportLocation.lng, reportText, "user_report");
        setReportModalOpen(false);
        setReportText("");
        alert("Vibe Reported! Click 'Find Routes' again to see updated scores.");
        api.getRoutes(currentStart, currentEnd).then(setRoutes);
    };

    const handleSearch = () => {
        const [startLat, startLng] = startInput.split(',').map(s => parseFloat(s.trim()));
        const [endLat, endLng] = endInput.split(',').map(s => parseFloat(s.trim()));

        if (isNaN(startLat) || isNaN(startLng) || isNaN(endLat) || isNaN(endLng)) {
            alert("Invalid coordinates. Use format: lat, lng");
            return;
        }

        const start = { lat: startLat, lng: startLng };
        const end = { lat: endLat, lng: endLng };

        setCurrentStart(start);
        setCurrentEnd(end);
        setMapCenter(start);

        api.getRoutes(start, end).then(data => {
            setRoutes(data);
            if (data.length > 0) setSelectedRouteId(data[0].id);
        }).catch((err: any) => console.error(err));
    };

    const getVibeIcon = (type: string) => {
        if (type === 'crime') return <AlertTriangle className="w-5 h-5 text-red-400" />;
        if (type === 'review') return <Star className="w-5 h-5 text-yellow-400" />;
        return <Users className="w-5 h-5 text-blue-400" />;
    };

    const getVibeColor = (type: string) => {
        if (type === 'crime') return 'border-red-500/50 bg-red-500/10';
        if (type === 'review') return 'border-yellow-500/50 bg-yellow-500/10';
        return 'border-blue-500/50 bg-blue-500/10';
    };

    return (
        <main className="relative w-full h-screen bg-black">
            {/* Floating Search Panel */}
            <div className="absolute top-4 left-4 z-50 bg-black/80 backdrop-blur-xl border border-white/10 rounded-2xl p-4 w-80">
                <h1 className="text-xl font-bold text-white mb-3 flex items-center gap-2">
                    <Navigation className="w-5 h-5 text-emerald-400" />
                    VibeWalk
                </h1>
                <div className="space-y-2">
                    <input
                        type="text"
                        placeholder="Start: lat, lng"
                        value={startInput}
                        onChange={e => setStartInput(e.target.value)}
                        className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-emerald-500"
                    />
                    <input
                        type="text"
                        placeholder="End: lat, lng"
                        value={endInput}
                        onChange={e => setEndInput(e.target.value)}
                        className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-emerald-500"
                    />
                    <button
                        onClick={handleSearch}
                        className="w-full bg-emerald-500 hover:bg-emerald-600 text-white py-2 rounded-lg font-bold flex items-center justify-center gap-2"
                    >
                        <Search className="w-4 h-4" /> Find Safe Routes
                    </button>
                </div>

                {/* Routes List */}
                {routes.length > 0 && (
                    <div className="mt-4 space-y-2">
                        {routes.map(route => (
                            <div
                                key={route.id}
                                onClick={() => setSelectedRouteId(route.id)}
                                className={`p-3 rounded-lg cursor-pointer transition-all ${selectedRouteId === route.id
                                    ? 'bg-emerald-500/20 border border-emerald-500/50'
                                    : 'bg-white/5 border border-white/10 hover:bg-white/10'
                                    }`}
                            >
                                <div className="flex justify-between items-center">
                                    <span className="text-white text-sm font-medium">{route.description}</span>
                                    <span className={`text-sm font-bold ${route.safety_score > 7 ? 'text-green-400' :
                                        route.safety_score > 4 ? 'text-yellow-400' : 'text-red-400'
                                        }`}>
                                        {route.safety_score}/10
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                <button
                    onClick={() => setIsReporting(true)}
                    className="w-full mt-4 bg-red-500/20 hover:bg-red-500/30 text-red-400 py-2 rounded-lg text-sm font-medium flex items-center justify-center gap-2"
                >
                    <AlertTriangle className="w-4 h-4" /> Report Hazard
                </button>
            </div>

            {isReporting && (
                <div className="absolute top-4 left-1/2 -translate-x-1/2 z-50 bg-red-500 text-white px-6 py-2 rounded-full shadow-lg animate-pulse">
                    Click on the map to report a hazard
                </div>
            )}

            <MapComponent
                center={mapCenter}
                routes={routes}
                selectedRouteId={selectedRouteId}
                onRouteSelect={(route) => setSelectedRouteId(route.id)}
                isReporting={isReporting}
                onReportClick={handleMapClick}
            />

            {/* Report Modal */}
            {reportModalOpen && (
                <div className="absolute inset-0 bg-black/60 backdrop-blur-sm z-[60] flex items-center justify-center">
                    <div className="bg-gray-900 border border-white/10 p-6 rounded-2xl w-96 shadow-2xl">
                        <h2 className="text-xl font-bold text-white mb-4">Report Vibe</h2>
                        <textarea
                            className="w-full bg-black/50 border border-white/20 rounded-lg p-3 text-white mb-4 focus:outline-none focus:border-emerald-500"
                            rows={3}
                            placeholder="Describe what you see or hear..."
                            value={reportText}
                            onChange={e => setReportText(e.target.value)}
                        />
                        <div className="flex gap-3 justify-end">
                            <button onClick={() => setReportModalOpen(false)} className="text-gray-400 hover:text-white">Cancel</button>
                            <button onClick={submitReport} className="bg-emerald-500 hover:bg-emerald-600 text-white px-5 py-2 rounded-lg font-bold">Submit</button>
                        </div>
                    </div>
                </div>
            )}

            {/* Nearby Vibes Modal */}
            {vibesModalOpen && (
                <div className="absolute inset-0 bg-black/60 backdrop-blur-sm z-[60] flex items-center justify-center">
                    <div className="bg-gray-900 border border-white/10 p-6 rounded-2xl w-[400px] max-h-[70vh] shadow-2xl flex flex-col">
                        <div className="flex justify-between items-center mb-4">
                            <h2 className="text-xl font-bold text-white">📍 Nearby Intel</h2>
                            <button onClick={() => setVibesModalOpen(false)} className="text-gray-400 hover:text-white">
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        {vibesLoading ? (
                            <div className="text-gray-400 text-center py-6">Loading...</div>
                        ) : nearbyVibes.length === 0 ? (
                            <div className="text-gray-400 text-center py-6">No data within 300m</div>
                        ) : (
                            <div className="overflow-y-auto space-y-2">
                                {nearbyVibes.map((vibe) => (
                                    <div key={vibe.id} className={`p-3 rounded-lg border ${getVibeColor(vibe.type)}`}>
                                        <div className="flex items-start gap-2">
                                            {getVibeIcon(vibe.type)}
                                            <div className="flex-1">
                                                <div className="flex justify-between items-start">
                                                    <span className="text-xs uppercase font-bold text-gray-400 flex items-center gap-2">
                                                        {vibe.type}
                                                        {vibe.source === 'user_report' && (
                                                            <span className="bg-blue-500/20 text-blue-300 px-1.5 py-0.5 rounded text-[10px]">
                                                                USER REPORT
                                                            </span>
                                                        )}
                                                    </span>
                                                    {vibe.timestamp && (
                                                        <span className="text-[10px] text-gray-500">
                                                            {new Date(vibe.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                                        </span>
                                                    )}
                                                </div>
                                                {vibe.name && <p className="text-white font-medium text-sm mt-1">{vibe.name}</p>}
                                                <p className="text-gray-300 text-sm mt-1">{vibe.text}</p>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}

                        <div className="pt-4 mt-auto border-t border-white/10 text-center text-xs text-gray-500">
                            Intel from NYC Open Data + User Network
                        </div>
                    </div>
                </div>
            )}
        </main>
    );
}
