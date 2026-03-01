import { create } from 'zustand';

export interface ActivityItem {
    id: string;
    type: 'thinking' | 'tool' | 'result' | 'info' | 'error' | 'user';
    label: string;
    detail: string;
    timestamp: Date;
    metadata?: {
        confidence?: number;
        durationMs?: number;
        mode?: string;
        iterations?: number;
    };
}

interface AgentState {
    activities: ActivityItem[];
    addActivity: (
        type: ActivityItem['type'],
        label: string,
        detail: string,
        metadata?: ActivityItem['metadata']
    ) => void;
    clearActivities: () => void;
}

export const useAgentStore = create<AgentState>((set) => ({
    activities: [],
    addActivity: (type, label, detail, metadata) =>
        set((state) => ({
            activities: [
                ...state.activities,
                {
                    id: `act-${Date.now()}-${Math.random().toString(36).slice(2, 5)}`,
                    type,
                    label,
                    detail,
                    metadata,
                    timestamp: new Date(),
                },
            ],
        })),
    clearActivities: () => set({ activities: [] }),
}));
