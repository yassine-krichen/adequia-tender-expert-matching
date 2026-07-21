import type { DriveStep } from 'driver.js';

// The first three steps anchor to real elements on /tdrs (see the
// data-tour attributes on frontend/src/app/tdrs/page.tsx) — they work the
// same whether the DB is empty (empty-state placeholders) or populated.
//
// The last three are static/illustrative: the compatibility score, an
// anomaly flag, and the approve/override action all live on a per-match
// report page (/matches/[matchId]) that a true first-run, empty-DB user
// won't have any data for yet. They're shown centered (no `element`),
// with mock content, purely to set expectations for later.
export const TOUR_STEPS: DriveStep[] = [
  {
    element: '[data-tour="tdr-upload"]',
    popover: {
      title: 'Upload a TDR',
      description:
        'Start here. Drop a TDR (PDF or docx) and AdéquIA extracts its mission, client, and expert positions.',
      side: 'bottom',
      align: 'start',
    },
  },
  {
    element: '[data-tour="tdr-positions"]',
    popover: {
      title: 'Expert positions',
      description:
        'Once a TDR is processed, its expert positions show up here — required diploma, experience, certifications, languages, and skills.',
      side: 'top',
      align: 'start',
    },
  },
  {
    element: '[data-tour="tdr-matches"]',
    popover: {
      title: 'Matches',
      description:
        'Run matching on a position to see its shortlisted candidates, ranked by compatibility, right here.',
      side: 'top',
      align: 'start',
    },
  },
  {
    popover: {
      title: 'Compatibility score',
      description:
        'Every match report shows an overall compatibility score (example: 82%), broken down into sub-scores like skill and sector fit — so you can see exactly why a candidate ranked where they did.',
    },
  },
  {
    popover: {
      title: 'Anomaly flags',
      description:
        "Match reports also surface anomalies detected in a candidate's CV — like an employment gap or an expired certification — each with a severity (info, warning, blocking) and a citation back to the source text.",
    },
  },
  {
    popover: {
      title: 'Approve or override',
      description:
        "On each match report, you approve or reject the AI's recommendation — or override it with a required note explaining why, which is kept alongside the decision for the record.",
    },
  },
];
