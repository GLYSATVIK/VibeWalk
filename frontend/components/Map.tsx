"use client";

import { useEffect } from "react";
import { MapContainer, TileLayer, Polyline, Marker, useMap, useMapEvents } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { RouteOption } from "@/lib/api";

// Fix for default marker icons in Next.js/Leaflet
const iconUrl = "https://unpkg.com/leaflet@1.7.1/dist/images/marker-icon.png";
const iconRetinaUrl = "https://unpkg.com/leaflet@1.7.1/dist/images/marker-icon-2x.png";
const shadowUrl = "https://unpkg.com/leaflet@1.7.1/dist/images/marker-shadow.png";

delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
    iconRetinaUrl: iconRetinaUrl,
    iconUrl: iconUrl,
    shadowUrl: shadowUrl,
});

interface MapProps {
    center: { lat: number, lng: number };
    routes: RouteOption[];
    onRouteSelect: (route: RouteOption) => void;
    selectedRouteId: string | null;
    isReporting: boolean;
    onReportClick: (lat: number, lng: number) => void;
}

// Helper to update map center when routes change
function MapUpdater({ center }: { center: { lat: number, lng: number } }) {
    const map = useMap();
    useEffect(() => {
        map.flyTo([center.lat, center.lng], 14);
    }, [center, map]);
    return null;
}

// Helper to handle clicks
function LocationMarker({ onReportClick }: { onReportClick: (lat: number, lng: number) => void }) {
    useMapEvents({
        click(e) {
            onReportClick(e.latlng.lat, e.latlng.lng);
        },
    });
    return null;
}

const SAFETY_COLORS = {
    high: "#16a34a", // Green-600
    medium: "#ca8a04", // Yellow-600
    low: "#dc2626", // Red-600
};

export default function Map({
    center,
    routes,
    onRouteSelect,
    selectedRouteId,
    isReporting,
    onReportClick,
}: MapProps) {
    const defaultCenter: [number, number] = center ? [center.lat, center.lng] : [40.758, -73.9855];

    return (
        <div className="w-full h-full relative z-0">
            <MapContainer
                center={defaultCenter}
                zoom={14}
                style={{ width: "100%", height: "100%" }}
                zoomControl={true}
            >
                {/* Light Mode Tiles (CartoDB Positron) */}
                <TileLayer
                    url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                />

                <MapUpdater center={center} />
                <LocationMarker onReportClick={onReportClick} />

                {/* Render Route Polylines */}
                {routes.map((route) => {
                    const isSelected = selectedRouteId === route.id;
                    const opacity = isSelected ? 1.0 : 0.5;
                    const weight = isSelected ? 7 : 4;

                    let color = SAFETY_COLORS.medium;
                    if (route.safety_score > 8) color = SAFETY_COLORS.high;
                    if (route.safety_score < 5) color = SAFETY_COLORS.low;

                    const positions: [number, number][] = route.path.map(p => [p.lat, p.lng]);

                    return (
                        <Polyline
                            key={route.id}
                            positions={positions}
                            pathOptions={{ color, weight, opacity }}
                            eventHandlers={{ click: () => onRouteSelect(route) }}
                        />
                    );
                })}

                {/* Start/End Markers for Selected Route */}
                {selectedRouteId && routes.find(r => r.id === selectedRouteId) && (() => {
                    const route = routes.find(r => r.id === selectedRouteId)!;
                    return (
                        <>
                            <Marker position={[route.path[0].lat, route.path[0].lng]} />
                            <Marker position={[route.path[route.path.length - 1].lat, route.path[route.path.length - 1].lng]} />
                        </>
                    );
                })()}
            </MapContainer>
        </div>
    );
}

