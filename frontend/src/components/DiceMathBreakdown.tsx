import type { CombatResult } from "../api/types";

export function DiceMathBreakdown({ result }: { result: CombatResult }) {
  return (
    <div className="card">
      <h2>
        {result.attacker} — {result.weapon} → {result.defender}
      </h2>
      <table className="breakdown">
        <tbody>
          {result.steps.map((step) => (
            <tr key={step.label}>
              <th>{step.label}</th>
              <td className="num">{step.value}</td>
              <td className="detail">{step.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="result-summary">
        Expected: <b>{result.expected_damage}</b> damage,{" "}
        <b>{result.expected_models_slain}</b> models slain
      </p>
      {result.notes.map((note) => (
        <p key={note} className="note">
          ℹ {note}
        </p>
      ))}
    </div>
  );
}
