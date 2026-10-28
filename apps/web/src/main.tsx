import "./motion";
import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";
type Field = {
  value: string;
  confidence: number;
  supported: boolean;
  start: number | null;
  end: number | null;
  boxes: number[][];
};
type Case = {
  id: string;
  fixture: number;
  kind: string;
  template: string;
  state: string;
  revision: number;
  sha: string;
  result: {
    text: string;
    fields: Record<string, Field>;
    confidence: number;
    redacted?: boolean;
  } | null;
  review: {
    fields: Record<string, { value: string; evidence: string }>;
  } | null;
  matches?: {
    id: number;
    entity: string;
    zone: string;
    domain: string;
    score: number;
  }[];
  audit: {
    seq: number;
    event: string;
    role: string;
    detail: Record<string, unknown>;
    created: string;
  }[];
  payer: { state: string; attempts: number; amount: number } | null;
  llm?: {
    schema_valid: boolean;
    fields: Record<string, { value: string; supported: boolean }>;
    seconds: number;
  } | null;
};
type ListItem = Pick<
  Case,
  "id" | "kind" | "template" | "state" | "revision" | "fixture"
>;
type Evidence = {
  documents: number;
  exact_documents: number;
  field_accuracy: Record<string, number>;
  per_template: {
    template: string;
    documents: number;
    fields: Record<string, number>;
  }[];
  curve: {
    threshold: number;
    auto_count: number;
    auto_rate: number;
    auto_error_rate: number | null;
  }[];
  review_before_correct_fields: number;
  review_after_correct_fields: number;
  review_fields: number;
  scope: string;
  pipeline_entity_top1: number;
  matching_curve: {
    threshold: number;
    precision: number | null;
    recall: number;
    tp: number;
    fp: number;
    fn: number;
  }[];
  model?: {
    model: string;
    documents: number;
    schema_valid_documents: number;
    correct_fields: number;
    total_fields: number;
    unsupported_rate: number | null;
    unsupported_fields: number;
    proposed_nonempty_fields: number;
  };
};
const labels: Record<string, string> = {
  document_id: "Document ID",
  date: "Date",
  amount: "Amount",
  entity: "Entity",
  reference: "Member / account",
  zone: "Zone",
  domain: "Directory domain",
};
const pct = (n: number) => `${(100 * n).toFixed(1)}%`;
function App() {
  const [token, setToken] = useState("local-review"),
    [role, setRole] = useState("");
  const [items, setItems] = useState<ListItem[]>([]);
  const [selected, setSelected] = useState("doc-0001");
  const [doc, setDoc] = useState<Case | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [image, setImage] = useState("");
  const [field, setField] = useState("document_id");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [note, setNote] = useState("");
  const [attested, setAttested] = useState(false);
  const [dirty, setDirty] = useState(false);
  const dirtyRef = useRef(false);
  const busyRef = useRef(false);
  const [tab, setTab] = useState("room");
  const [filter, setFilter] = useState("all");
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [ocrView, setOcrView] = useState(false);
  const [zoom, setZoom] = useState(false);
  const [claim, setClaim] = useState("urgent action is stated.");
  const [verdict, setVerdict] = useState<boolean | null>(null);
  const [llmEnabled, setLlmEnabled] = useState(false);
  async function api<T>(path: string, body?: unknown): Promise<T> {
    const r = await fetch(`/api/${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const json = await r.json();
    if (!r.ok)
      throw new Error(`${r.status}: ${json.error || "request failed"}`);
    return json;
  }
  async function list() {
    const data = await api<{
      documents: ListItem[];
      role: string;
      llm_enabled: boolean;
    }>("documents");
    setItems(data.documents);
    setRole(data.role);
    setLlmEnabled(data.llm_enabled);
  }
  function apply(data: Case) {
    setDoc(data);
    setValues(
      Object.fromEntries(
        Object.keys(labels).map((k) => [
          k,
          data.review?.fields[k]?.value ?? data.result?.fields[k]?.value ?? "",
        ]),
      ),
    );
    dirtyRef.current = false;
    setDirty(false);
    setAttested(false);
    setNote("");
  }
  async function load() {
    setError("");
    try {
      await list();
      apply(await api<Case>(`document?id=${selected}`));
      setEvidence(await api<Evidence>("evidence"));
    } catch (e) {
      setError(String(e));
    }
  }
  useEffect(() => {
    let active = true;
    setDoc(null);
    setImage("");
    dirtyRef.current = false;
    setDirty(false);
    setVerdict(null);
    setNotice("");
    setError("");
    async function tick() {
      if (busyRef.current) return;
      try {
        const [listing, detail, ev] = await Promise.all([
          api<{ documents: ListItem[]; role: string; llm_enabled: boolean }>(
            "documents",
          ),
          api<Case>(`document?id=${selected}`),
          api<Evidence>("evidence"),
        ]);
        if (!active || busyRef.current) return;
        setItems(listing.documents);
        setRole(listing.role);
        setLlmEnabled(listing.llm_enabled);
        setEvidence(ev);
        if (!dirtyRef.current) apply(detail);
      } catch (e) {
        if (active) setError(String(e));
      }
    }
    void tick();
    const timer = setInterval(() => void tick(), 1600);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [selected, token]);
  useEffect(() => {
    let active = true;
    if (role !== "reviewer") {
      setImage("");
      return;
    }
    void fetch(`/api/image?id=${selected}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (r) => {
        if (!r.ok) return;
        const blob = await r.blob();
        const reader = new FileReader();
        reader.onload = () => {
          if (active) setImage(String(reader.result));
        };
        reader.readAsDataURL(blob);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [selected, token, role]);
  async function action(fn: () => Promise<void>) {
    busyRef.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError(String(e));
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }
  function edit(k: string, v: string) {
    setValues((old) => ({ ...old, [k]: v }));
    dirtyRef.current = true;
    setDirty(true);
    setField(k);
  }
  async function save() {
    await action(async () => {
      const updated = await api<Case>("review", {
        id: selected,
        revision: doc?.revision,
        values,
        attested,
        note,
      });
      apply(updated);
      setNotice(
        `Decision recorded · revision ${updated.revision}. Original OCR preserved.`,
      );
      await list();
    });
  }
  const filtered = items.filter(
    (i) => filter === "all" || i.state === filter || i.kind === filter,
  );
  const boxes = doc?.result?.fields[field]?.boxes || [];
  return (
    <main className="shell">
      <aside className="rail">
        <a href="/" className="brand">
          <span className="brand-mark">
            d<span>·</span>
          </span>
          docket
        </a>
        <div className="rail-caption">
          THE READING ROOM
          <br />
          SYNTHETIC RECORDS ONLY
        </div>
        <nav aria-label="Workspace">
          <button
            aria-current={tab === "room" ? "page" : undefined}
            onClick={() => setTab("room")}
          >
            <span>▤</span> Review desk{" "}
            <b>{items.filter((i) => i.state === "review").length}</b>
          </button>
          <button
            aria-current={tab === "evidence" ? "page" : undefined}
            onClick={() => setTab("evidence")}
          >
            <span>◷</span> Evaluation book
          </button>
        </nav>
        <div className="rail-label">
          A DOCUMENT IS MORE
          <br />
          THAN ITS EXTRACTION.
        </div>
        <p className="rail-copy">
          Read the source.
          <br />
          Check the claim.
          <br />
          Leave a decision trail.
        </p>
        <div className="rail-bottom">
          <span className={role ? "dot" : "dot off"} />
          {role ? `${role.toUpperCase()} CONNECTED` : "DISCONNECTED"}
          <details>
            <summary>Access settings</summary>
            <label htmlFor="token">Bearer token</label>
            <input
              id="token"
              type="password"
              value={token}
              onChange={(e) => {
                setToken(e.target.value);
                setRole("");
              }}
            />
            <button onClick={() => void load()}>Reconnect</button>
            <p>
              Loopback demo: local-review or local-view. Tokens remain in
              memory.
            </p>
          </details>
          <a
            href="https://github.com/rjrddy/docket"
            target="_blank"
            rel="noreferrer"
          >
            Source & raw evidence ↗
          </a>
        </div>
      </aside>
      <section className="workspace">
        <header>
          <div>
            <span className="eyebrow">
              DOCKET / {tab === "room" ? "OPERATIONS" : "MEASUREMENTS"}
            </span>
            <h1>
              {tab === "room"
                ? "Every field has a source."
                : "Read the results, too."}
            </h1>
          </div>
          <button
            className="add"
            disabled={busy || role !== "reviewer" || items.length >= 120}
            onClick={() =>
              void action(async () => {
                const n = Math.max(11, ...items.map((i) => i.fixture)) + 1;
                const data = await api<{ id: string }>("ingest", {
                  fixture: n,
                });
                await list();
                setSelected(data.id);
                setTab("room");
              })
            }
          >
            ＋ Add synthetic case
          </button>
        </header>
        {error && (
          <div className="error" role="alert">
            <b>REQUEST REJECTED</b> {error}
          </div>
        )}
        {notice && (
          <div className="notice" role="status">
            {notice}
          </div>
        )}
        {tab === "room" ? (
          <>
            <div className="desk-label">
              <span>
                <i /> LIVE POSTGRES QUEUE
              </span>
              <p>
                Confidence suggests where to look. A citation is not a
                correctness guarantee.
              </p>
            </div>
            <div className="desk">
              <section className="inbox">
                <div className="inbox-title">
                  <h2>Incoming</h2>
                  <b>{items.length.toString().padStart(2, "0")}</b>
                </div>
                <label htmlFor="filter">Filter cases</label>
                <select
                  id="filter"
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                >
                  <option value="all">All cases</option>
                  <option value="review">Needs review</option>
                  <option value="reviewed">Reviewed</option>
                  <option value="auto">Auto-routed</option>
                  <option value="invoice">Invoices</option>
                  <option value="statement">Statements</option>
                  <option value="referral">Referrals</option>
                </select>
                <div className="case-list">
                  {filtered.map((i) => (
                    <button
                      aria-label={`Open ${i.id}`}
                      aria-current={i.id === selected ? "true" : undefined}
                      disabled={busy}
                      onClick={() => setSelected(i.id)}
                      key={i.id}
                    >
                      <span className={`type-icon ${i.kind}`}>
                        {i.kind.slice(0, 1).toUpperCase()}
                      </span>
                      <div>
                        <strong>{i.id}</strong>
                        <small>{i.template}</small>
                        <span className={`state ${i.state}`}>
                          {i.state === "review" ? "Needs review" : i.state}
                        </span>
                      </div>
                      <span className="case-arrow">↗</span>
                    </button>
                  ))}
                </div>
                <div className="inbox-note">
                  No private records.
                  <br />
                  Every page is generated
                  <br />
                  for this evaluation.
                </div>
              </section>
              <section className="source-panel">
                <div className="folder-tabs">
                  <span>01 / Source page</span>
                  <span>{doc?.template || "Loading"}</span>
                </div>
                <div className="source-toolbar">
                  <span>
                    {selected} <b>rev {doc?.revision ?? "—"}</b>
                  </span>
                  <div>
                    <button
                      aria-pressed={ocrView}
                      onClick={() => setOcrView(!ocrView)}
                    >
                      {ocrView ? "Show image" : "OCR text"}
                    </button>
                    <button aria-pressed={zoom} onClick={() => setZoom(!zoom)}>
                      Zoom {zoom ? "−" : "＋"}
                    </button>
                  </div>
                </div>
                {doc?.result ? (
                  <div className={`page-window ${zoom ? "zoomed" : ""}`}>
                    {ocrView ? (
                      <pre className="ocr-text">{doc.result.text}</pre>
                    ) : image ? (
                      <div className="page-sheet">
                        <img src={image} alt={`Synthetic source ${selected}`} />
                        <svg
                          viewBox="0 0 900 850"
                          aria-label={`OCR source boxes for ${labels[field]}`}
                          role="img"
                        >
                          {boxes.map(([x, y, w, h], i) => (
                            <rect
                              key={i}
                              x={x - 3}
                              y={y - 3}
                              width={w + 6}
                              height={h + 6}
                            />
                          ))}
                        </svg>
                      </div>
                    ) : (
                      <div className="image-private">
                        Source image requires reviewer access.
                        <br />
                        The OCR view is redacted for viewers.
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="waiting">
                    <span>▧</span>
                    <h3>Reading the page.</h3>
                    <p>
                      {doc?.state === "error"
                        ? "Processing failed; inspect the queue state."
                        : "The durable OCR worker is processing this synthetic page."}
                    </p>
                  </div>
                )}
                <div className="source-caption">
                  <span className="tag">IMMUTABLE SOURCE</span>
                  <p>
                    SHA256 {doc?.sha.slice(0, 16) || "—"}… · Highlighted boxes
                    come from actual OCR words.
                  </p>
                </div>
                <details className="claim-check">
                  <summary>Check a statement against OCR</summary>
                  <label htmlFor="claim">Exact statement</label>
                  <input
                    id="claim"
                    value={claim}
                    onChange={(e) => {
                      setClaim(e.target.value);
                      setVerdict(null);
                    }}
                  />
                  <button
                    className="secondary"
                    disabled={busy || !doc?.result || role !== "reviewer"}
                    onClick={() =>
                      void action(async () => {
                        const r = await api<{ supported: boolean }>(
                          "check-claim",
                          { id: selected, claim },
                        );
                        setVerdict(r.supported);
                      })
                    }
                  >
                    Check source →
                  </button>
                  {verdict !== null && (
                    <p role="status" className={verdict ? "good" : "bad"}>
                      {verdict
                        ? "Exact whole-sentence support found."
                        : "Unsupported — no exact whole-sentence source."}
                    </p>
                  )}
                  <p>
                    Conservative exact matching, not semantic or clinical
                    entailment. A supported OCR sentence may still be a
                    transcription error.
                  </p>
                </details>
              </section>
              <section className="review-panel">
                <div className="review-heading">
                  <div className="eyebrow">02 / EXTRACTED FIELDS</div>
                  <h2>
                    {doc?.state === "reviewed"
                      ? "Decision on file."
                      : "A closer reading."}
                  </h2>
                  <p>
                    {dirty
                      ? "Unsaved changes · revision is pinned until you save or reload."
                      : "Select a field to locate its evidence in the source."}
                  </p>
                </div>
                {doc?.result && !doc.result.redacted ? (
                  <>
                    <div className="fields">
                      {Object.keys(labels).map((k) => {
                        const f = doc.result!.fields[k];
                        return (
                          <div
                            key={k}
                            className={`field ${field === k ? "selected" : ""}`}
                          >
                            <button
                              className="field-head"
                              aria-pressed={field === k}
                              onClick={() => setField(k)}
                            >
                              <label htmlFor={`field-${k}`}>{labels[k]}</label>
                              <span
                                className={
                                  f?.supported ? "supported" : "missing"
                                }
                              >
                                {f?.supported
                                  ? `${pct(f.confidence)} · cited`
                                  : "Source needed"}
                              </span>
                            </button>
                            <input
                              id={`field-${k}`}
                              value={values[k] || ""}
                              disabled={busy || role !== "reviewer"}
                              onFocus={() => setField(k)}
                              onChange={(e) => edit(k, e.target.value)}
                            />
                            {doc.review?.fields[k] && (
                              <small className="review-evidence">
                                {doc.review.fields[k].evidence}
                              </small>
                            )}
                          </div>
                        );
                      })}
                    </div>
                    <label className="attest">
                      <input
                        type="checkbox"
                        checked={attested}
                        disabled={busy || role !== "reviewer"}
                        onChange={(e) => {
                          dirtyRef.current = true;
                          setDirty(true);
                          setAttested(e.target.checked);
                        }}
                      />{" "}
                      I checked corrected or missing values against the
                      synthetic source image.
                    </label>
                    <label htmlFor="note">
                      Review note · required for image attestation
                    </label>
                    <textarea
                      id="note"
                      value={note}
                      disabled={busy || role !== "reviewer"}
                      onChange={(e) => {
                        dirtyRef.current = true;
                        setDirty(true);
                        setNote(e.target.value);
                      }}
                      placeholder="What did you verify in the source?"
                    />
                    <p className="hint">
                      Only a note hash is retained. Image attestation records
                      reviewer judgment; it is not an OCR citation.
                    </p>
                    <button
                      className="primary"
                      disabled={
                        busy ||
                        role !== "reviewer" ||
                        Object.values(values).some((v) => !v)
                      }
                      onClick={() => void save()}
                    >
                      {busy ? "Recording…" : "Record review decision"}
                      <span>↗</span>
                    </button>
                    <button
                      className="reload"
                      disabled={busy}
                      onClick={() =>
                        void action(async () => {
                          apply(await api<Case>(`document?id=${selected}`));
                          setNotice(
                            "Latest revision loaded. Unsaved edits cleared.",
                          );
                        })
                      }
                    >
                      Reload latest revision
                    </button>
                  </>
                ) : (
                  <p className="review-placeholder">
                    {doc?.result?.redacted
                      ? "Viewer mode shows redacted OCR only. Review actions require reviewer access."
                      : "Fields appear when the worker completes."}
                  </p>
                )}
              </section>
            </div>
            {doc && (
              <div className="lower-desk">
                <section className="directory">
                  <div className="eyebrow">03 / ENTITY CANDIDATES</div>
                  <h3>A match is a suggestion.</h3>
                  <p>
                    Weighted name, zone and domain similarity. These are scores,
                    not identity probabilities.
                  </p>
                  {doc.matches?.map((m, i) => (
                    <div className="candidate" key={m.id}>
                      <span>{i + 1}</span>
                      <div>
                        <b>{m.entity}</b>
                        <small>
                          {m.zone} · {m.domain}
                        </small>
                      </div>
                      <strong>{pct(m.score)}</strong>
                    </div>
                  ))}
                </section>
                <section className="payer">
                  <div className="eyebrow">04 / MOCK PAYER ONLY</div>
                  <h3>From review to reconciliation.</h3>
                  <p>
                    Approved synthetic referrals can enter an idempotent outbox.
                    Some first responses time out after the mock payer commits.
                  </p>
                  <button
                    className="secondary"
                    disabled={
                      busy ||
                      dirty ||
                      doc.kind !== "referral" ||
                      !["reviewed", "auto"].includes(doc.state) ||
                      role !== "reviewer"
                    }
                    onClick={() =>
                      void action(async () => {
                        await api("payer", { id: selected });
                        apply(await api<Case>(`document?id=${selected}`));
                        setNotice(
                          "Synthetic claim entered the durable mock outbox.",
                        );
                      })
                    }
                  >
                    Send to mock payer →
                  </button>
                  <div className="payer-state" aria-live="polite">
                    <span>{doc.payer?.state || "Not submitted"}</span>
                    <small>
                      {doc.payer
                        ? `${doc.payer.attempts} attempts · ${(doc.payer.amount / 100).toFixed(2)} synthetic units`
                        : "No real eligibility or payment decision."}
                    </small>
                  </div>
                </section>
                <section className="model">
                  <div className="eyebrow">05 / OPTIONAL LOCAL LLM</div>
                  <h3>Propose. Then verify.</h3>
                  <p>
                    Greedy public-model extraction. Schema failures and
                    unsupported values are rejected; suggestions never
                    auto-approve a case.
                  </p>
                  <button
                    className="secondary"
                    disabled={
                      busy ||
                      !doc.result ||
                      role !== "reviewer" ||
                      !llmEnabled ||
                      dirty
                    }
                    onClick={() =>
                      void action(async () => {
                        await api("model", { id: selected });
                        apply(await api<Case>(`document?id=${selected}`));
                        setNotice(
                          "Local model proposal recorded; source validation still applies.",
                        );
                      })
                    }
                  >
                    {llmEnabled ? "Run local model →" : "Local model disabled"}
                  </button>
                  {doc.llm && (
                    <p className="model-result">
                      {doc.llm.schema_valid
                        ? "Schema valid — inspect source support"
                        : "Schema rejected"}{" "}
                      · {doc.llm.seconds.toFixed(2)} seconds
                    </p>
                  )}
                  {doc.llm?.schema_valid && (
                    <ul className="model-proposals">
                      {Object.entries(doc.llm.fields).map(([key, p]) => (
                        <li key={key}>
                          <b>{labels[key]}</b>
                          <span>{p.value || "Missing"}</span>
                          <small className={p.supported ? "good" : "bad"}>
                            {p.supported ? "Source-supported" : "Not supported"}
                          </small>
                        </li>
                      ))}
                    </ul>
                  )}
                  <p className="hint">
                    Enable with make model and DOCKET_LLM=1. The evaluation book
                    retains actual model failures.
                  </p>
                </section>
              </div>
            )}
            <section className="audit">
              <div>
                <div className="eyebrow">THE DECISION TRAIL</div>
                <h3>What changed, and who recorded it.</h3>
                <p>
                  Events contain field names, revisions and value hashes. Source
                  text and identifiers are excluded from operational logs.
                </p>
              </div>
              <div className="audit-events">
                {doc?.audit?.map((a) => (
                  <article key={a.seq}>
                    <span>{String(a.seq).padStart(3, "0")}</span>
                    <div>
                      <b>{a.event.replaceAll("_", " ")}</b>
                      <small>
                        {a.role} · {a.created.slice(0, 19).replace("T", " ")}
                      </small>
                    </div>
                    <p>
                      {Object.entries(a.detail)
                        .filter(([k]) =>
                          [
                            "fields",
                            "revision",
                            "status",
                            "code",
                            "attempt",
                          ].includes(k),
                        )
                        .map(
                          ([k, v]) =>
                            `${k}: ${Array.isArray(v) ? v.join(", ") : v}`,
                        )
                        .join(" / ") || "Value-free event recorded"}
                    </p>
                  </article>
                ))}
              </div>
            </section>
          </>
        ) : (
          <section className="evaluation">
            <div className="book-cover">
              <span>DOCKET / EVALUATION BOOK</span>
              <h2>
                Confidence is a lead.
                <br />
                Evidence is a responsibility.
              </h2>
              <p>{evidence?.scope || "No measurements loaded."}</p>
              <div className="book-stats">
                <div>
                  <b>{evidence?.documents ?? "—"}</b>
                  <span>synthetic scanned pages</span>
                </div>
                <div>
                  <b>{evidence?.exact_documents ?? "—"}</b>
                  <span>all fields correct before review</span>
                </div>
                <div>
                  <b>
                    {evidence?.pipeline_entity_top1 !== undefined
                      ? pct(evidence.pipeline_entity_top1)
                      : "—"}
                  </b>
                  <span>pipeline entity top-one accuracy</span>
                </div>
              </div>
            </div>
            {evidence?.per_template && (
              <>
                <section>
                  <div className="eyebrow">FIELD ACCURACY / ACTUAL OCR</div>
                  <h3>Every template gets its own line.</h3>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Template</th>
                          {Object.keys(labels).map((k) => (
                            <th key={k}>{labels[k]}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {evidence.per_template.map((r) => (
                          <tr key={r.template}>
                            <th>
                              {r.template} <small>n={r.documents}</small>
                            </th>
                            {Object.keys(labels).map((k) => (
                              <td key={k}>{pct(r.fields[k])}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
                <section className="curves">
                  <div>
                    <div className="eyebrow">AUTOMATION VS ERROR</div>
                    <h3>Where should review begin?</h3>
                    <p>
                      Empirical fixture error, not calibrated risk. A null error
                      rate means no cases were auto-approved.
                    </p>
                    <table>
                      <thead>
                        <tr>
                          <th>Threshold</th>
                          <th>Auto rate</th>
                          <th>Auto errors</th>
                        </tr>
                      </thead>
                      <tbody>
                        {evidence.curve.map((r) => (
                          <tr key={r.threshold}>
                            <th>{r.threshold.toFixed(2)}</th>
                            <td>{pct(r.auto_rate)}</td>
                            <td>
                              {r.auto_error_rate === null
                                ? "No auto cases"
                                : pct(r.auto_error_rate)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div>
                    <div className="eyebrow">
                      ENTITY MATCHING / SYNTHETIC LABELS
                    </div>
                    <h3>Precision has a price.</h3>
                    <p>
                      Near-name pairs include hard negatives. These labels do
                      not establish real-world matching quality.
                    </p>
                    <table>
                      <thead>
                        <tr>
                          <th>Threshold</th>
                          <th>Precision</th>
                          <th>Recall</th>
                          <th>False matches</th>
                        </tr>
                      </thead>
                      <tbody>
                        {evidence.matching_curve.map((r) => (
                          <tr key={r.threshold}>
                            <th>{r.threshold.toFixed(2)}</th>
                            <td>
                              {r.precision === null ? "—" : pct(r.precision)}
                            </td>
                            <td>{pct(r.recall)}</td>
                            <td>{r.fp}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
                <section className="review-study">
                  <div>
                    <div className="eyebrow">
                      REVIEW MEASUREMENT / SCRIPTED ORACLE
                    </div>
                    <h3>
                      Corrections work.
                      <br />
                      Human benefit remains unmeasured.
                    </h3>
                  </div>
                  <div>
                    <strong>
                      {evidence.review_before_correct_fields} →{" "}
                      {evidence.review_after_correct_fields}
                    </strong>
                    <p>
                      Correct fields among {evidence.review_fields} reviewed
                      fields. These are scripted, truth-assisted corrections
                      through the persisted reviewer path. They do not establish
                      human reviewer accuracy or time saved.
                    </p>
                  </div>
                </section>
                {evidence.model && (
                  <section className="model-study">
                    <div className="eyebrow">
                      ACTUAL LOCAL MODEL / ADVISORY ONLY
                    </div>
                    <h3>{evidence.model.model}</h3>
                    <p>
                      {evidence.model.schema_valid_documents}/
                      {evidence.model.documents} schema-valid outputs ·{" "}
                      {evidence.model.correct_fields}/
                      {evidence.model.total_fields} correct fields. Unsupported
                      rate:{" "}
                      {evidence.model.unsupported_rate === null
                        ? "not measured (no valid field proposals)"
                        : pct(evidence.model.unsupported_rate)}
                      .
                    </p>
                    <p>
                      Schema failures are separate from unsupported claims.
                      Rejected output is not counted as a successful extraction.
                      The earlier smaller-model failure is retained in the
                      repository.
                    </p>
                  </section>
                )}
              </>
            )}
          </section>
        )}
        <footer>
          <span>DOCKET · SYNTHETIC DOCUMENT LAB</span>
          <p>Not deployed. No clinical, financial or production-use claim.</p>
        </footer>
      </section>
    </main>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
