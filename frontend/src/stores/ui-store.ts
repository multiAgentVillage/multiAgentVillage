import { create } from 'zustand';

interface UiState {
  selectedRunId: string | undefined;
  selectedAgentId: string | undefined;
  selectRun: (runId: string) => void;
  selectAgent: (agentId: string) => void;
  showConnectionDetails: boolean;
  toggleConnectionDetails: () => void;
}

/** Store UI choices only. Server data belongs to TanStack Query. */
export const useUiStore = create<UiState>((set) => ({
  selectedRunId: undefined,
  selectedAgentId: undefined,
  selectRun: (selectedRunId) => set({ selectedRunId, selectedAgentId: undefined }),
  selectAgent: (selectedAgentId) => set({ selectedAgentId }),
  showConnectionDetails: false,
  toggleConnectionDetails: () =>
    set((state) => ({ showConnectionDetails: !state.showConnectionDetails })),
}));
