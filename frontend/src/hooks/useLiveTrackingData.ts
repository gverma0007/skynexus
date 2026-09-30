import { useEffect, useState } from 'react';
import type { FlightArc, SatelliteTrack } from '../api/client';
import { api } from '../api/client';

export const useLiveTrackingData = () => {
  const [flights, setFlights] = useState<FlightArc[]>([]);
  const [satellites, setSatellites] = useState<SatelliteTrack[]>([]);

  useEffect(() => {
    const fetchLive = async () => {
      try {
        const [f, s] = await Promise.all([api.getLiveFlights(), api.getLiveSatellites()]);
        setFlights(f);
        setSatellites(s);
      } catch (error) {
        console.error('Failed to fetch live tracking data', error);
      }
    };

    fetchLive();
    const interval = setInterval(fetchLive, 30000);
    return () => clearInterval(interval);
  }, []);

  return { flights, satellites };
};
