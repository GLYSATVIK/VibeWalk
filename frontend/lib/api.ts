import axios from 'axios';

const API_URL = 'http://localhost:8000';

export interface Point {
    lat: number;
    lng: number;
}

export interface Recommendation {
    name: string;
    description: string;
    type: string;
}

export interface RouteOption {
    id: string;
    path: Point[];
    safety_score: number;
    tags: string[];
    description: string;
    recommendations?: Recommendation[];
}

export interface NearbyVibe {
    id: string;
    text: string;
    type: string;
    source: string;
    name?: string;
    timestamp?: string; // New field
}

export const api = {
    getRoutes: async (start: Point, end: Point): Promise<RouteOption[]> => {
        const res = await axios.get(`${API_URL}/routes`, {
            params: {
                start_lat: start.lat,
                start_lng: start.lng,
                end_lat: end.lat,
                end_lng: end.lng
            }
        });
        return res.data;
    },

    reportVibe: async (lat: number, lng: number, description: string, type: string) => {
        const res = await axios.post(`${API_URL}/report`, {
            lat, lng, description, type
        });
        return res.data;
    },

    getNearbyVibes: async (lat: number, lng: number): Promise<{ vibes: NearbyVibe[], count: number }> => {
        const res = await axios.get(`${API_URL}/nearby-vibes`, {
            params: { lat, lng, radius: 300 }
        });
        return res.data;
    }
};
