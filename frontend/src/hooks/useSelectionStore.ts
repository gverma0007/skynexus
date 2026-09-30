import { create } from 'zustand';

interface SelectionState {
  selectedRegionId: string | null;
  setSelectedRegionId: (id: string | null) => void;
}

export const useSelectionStore = create<SelectionState>((set) => ({
  selectedRegionId: null,
  setSelectedRegionId: (id) => set({ selectedRegionId: id }),
}));
