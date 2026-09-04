interface RecordDetailsProps {
  value: unknown;
}

function displayLabel(key: string): string {
  return key.replaceAll("_", " ");
}

function Value({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === "") {
    return <span className="empty-value">None</span>;
  }

  if (Array.isArray(value)) {
    return (
      <div className="nested-list">
        {value.length === 0 ? (
          <span className="empty-value">No records</span>
        ) : (
          value.map((item, index) => (
            <div className="nested-record" key={index}>
              <RecordDetails value={item} />
            </div>
          ))
        )}
      </div>
    );
  }

  if (typeof value === "object") {
    return <RecordDetails value={value} />;
  }

  return <span>{String(value)}</span>;
}

export function RecordDetails({ value }: RecordDetailsProps) {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return <Value value={value} />;
  }

  return (
    <dl className="record-details">
      {Object.entries(value).map(([key, item]) => (
        <div className="detail-row" key={key}>
          <dt>{displayLabel(key)}</dt>
          <dd>
            <Value value={item} />
          </dd>
        </div>
      ))}
    </dl>
  );
}
