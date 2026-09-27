import { PHASES } from "../api/types";

export function PhaseTracker({ current }: { current: number }) {
  return (
    <div className="phase-tracker">
      {PHASES.map((phase, index) => (
        <div
          key={phase}
          className={
            "phase" + (index === current ? " current" : index < current ? " done" : "")
          }
        >
          {phase}
        </div>
      ))}
    </div>
  );
}
