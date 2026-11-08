import type { Results } from "../../shared/api/types";

export function StandardsMatrix({ r }: { r: Results }) {
  return (
    <div className="scroll">
      <table className="table standards">
        <caption className="sr-only">Architecture standards by solution</caption>
        <thead>
          <tr>
            <th scope="col">Standard</th>
            {r.conformance.map((c) => (
              <th scope="col" key={c.solution}>
                {c.solution} <span className="small">{c.passed}/{c.total}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {r.standards.map((st, i) => (
            <tr key={st.id}>
              <th scope="row">
                <span className="std__id">{st.id}</span> {st.title}
                <span className="std__why">{st.why}</span>
              </th>
              {r.conformance.map((c) => {
                const ch = c.checks[i]!;
                return (
                  <td key={c.solution} className={ch.pass ? "cell--pass" : "cell--fail"}>
                    <span className="cell__mark">{ch.pass ? "meets" : "fails"}</span>
                    <span className="cell__evidence">{ch.evidence}</span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="note">The third column is a deliberately non-conformant prototype kept as a fixture: the check must catch it.</p>
    </div>
  );
}
