import { useSyncExternalStore } from 'react';

export type Dataset = 'live' | 'demo' | 'historical';
export interface ViewerState {
  dataset: Dataset;
  realtime: boolean;
  asOf: string | null;
  revision: number;
  connection: 'connecting' | 'receiving' | 'reconnecting' | 'paused';
  lastEvent: string | null;
}

let state: ViewerState = { dataset: 'live', realtime: true, asOf: null, revision: 0, connection: 'connecting', lastEvent: null };
const listeners = new Set<() => void>();
function update(patch: Partial<ViewerState>) {
  state = { ...state, ...patch };
  listeners.forEach((listener) => listener());
}
export const viewer = {
  get: () => state,
  subscribe: (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; },
  setDataset(dataset: Dataset, asOf?: string) {
    update({ dataset, asOf: dataset === 'historical' ? asOf ?? new Date().toISOString() : null,
      realtime: dataset !== 'historical', revision: state.revision + 1,
      connection: dataset === 'historical' ? 'paused' : 'connecting' });
  },
  pause() { update({ realtime: false, asOf: new Date().toISOString(), connection: 'paused' }); },
  resume() { update({ realtime: true, asOf: null, revision: state.revision + 1, connection: 'connecting' }); },
  refresh() { update({ revision: state.revision + 1 }); },
  received() { update({ connection: 'receiving', lastEvent: new Date().toISOString(), revision: state.revision + 1 }); },
  connection(connection: ViewerState['connection']) { if (connection !== state.connection) update({ connection }); },
};
export function useViewer() { return useSyncExternalStore(viewer.subscribe, viewer.get); }
