"use client";

import type { CheckerReceipt } from "@/lib/types";

// The checker's own numbers for one problem. The rows fill in one after another when the
// receipt opens: the single animated moment on the page, and it shows real values.
export function Receipt({ receipt }: { receipt: CheckerReceipt }) {
  return (
    <details className="receipt">
      <summary>See the checker's numbers</summary>
      <p className="receipt-reason">{receipt.reason.charAt(0).toUpperCase() + receipt.reason.slice(1)}.</p>
      <table>
        <caption>Derivative computed by SymPy: {receipt.true_answer}</caption>
        <thead>
          <tr>
            <th scope="col">x</th>
            <th scope="col">Checker</th>
            <th scope="col">Answer key</th>
          </tr>
        </thead>
        <tbody>
          {receipt.samples.map(([x, checker, key], index) => (
            <tr key={x} style={{ animationDelay: `${index * 90}ms` }}>
              <td>{x.toPrecision(4)}</td>
              <td>{checker.toPrecision(6)}</td>
              <td>{key.toPrecision(6)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}
