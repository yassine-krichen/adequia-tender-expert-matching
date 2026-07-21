'use client';

import { driver, type Driver } from 'driver.js';
import { useEffect, useRef } from 'react';

import 'driver.js/dist/driver.css';

import { TOUR_STEPS } from './tour-steps';
import './tour.css';

const SEEN_STORAGE_KEY = 'adequia_tour_seen';
// Cross-page trigger: TopNav sets this before navigating to /tdrs so the
// tour restarts once /tdrs (and its data-tour anchors) has actually
// mounted, instead of guessing at a delay.
const PENDING_TRIGGER_KEY = 'adequia_tour_pending';
const START_TOUR_EVENT = 'adequia:start-tour';

export function useGuidedTour() {
  const driverRef = useRef<Driver | null>(null);

  function getDriver(): Driver {
    if (!driverRef.current) {
      driverRef.current = driver({ showProgress: true, steps: TOUR_STEPS });
    }
    return driverRef.current;
  }

  function startTour() {
    getDriver().drive();
  }

  useEffect(() => {
    // Same-page re-trigger: TopNav's "Take the tour" dispatches this when
    // already on /tdrs, since there's no navigation/remount to hook into.
    function handleStartTourEvent() {
      startTour();
    }
    window.addEventListener(START_TOUR_EVENT, handleStartTourEvent);

    if (window.sessionStorage.getItem(PENDING_TRIGGER_KEY)) {
      window.sessionStorage.removeItem(PENDING_TRIGGER_KEY);
      startTour();
    } else if (!window.localStorage.getItem(SEEN_STORAGE_KEY)) {
      // Mark as seen before starting, not after: a reload mid-tour should
      // not bring it back.
      window.localStorage.setItem(SEEN_STORAGE_KEY, 'true');
      startTour();
    }

    return () => {
      window.removeEventListener(START_TOUR_EVENT, handleStartTourEvent);
      if (driverRef.current?.isActive()) {
        driverRef.current.destroy();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { startTour };
}

/** Called by the nav's "Take the tour" trigger — see top-nav.tsx. */
export function requestGuidedTour(navigateToTdrs: () => void, isOnTdrsPage: boolean) {
  if (isOnTdrsPage) {
    window.dispatchEvent(new Event(START_TOUR_EVENT));
    return;
  }
  window.sessionStorage.setItem(PENDING_TRIGGER_KEY, 'true');
  navigateToTdrs();
}
