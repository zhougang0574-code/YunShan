import { formatMetric, MetricMeta, RATING_BADGE } from "../metrics";

interface Props {
  meta: MetricMeta;
  value: number | undefined;
}

export default function MetricCard({ meta, value }: Props) {
  const hasValue = value !== undefined && value !== null && !Number.isNaN(value);
  const text = formatMetric(value, meta.format);
  const rating = hasValue ? meta.rate(value) : "neutral";
  const badge = RATING_BADGE[rating];

  return (
    <div className="card">
      <div className="label">
        <span>{meta.label}</span>
        <span className="help" title={meta.help}>
          ?
        </span>
      </div>
      <div className="card-row">
        <span className={`value rating-${rating}`}>{text}</span>
        {hasValue && (
          <span className={`badge badge-${rating}`}>
            {badge.emoji} {badge.text}
          </span>
        )}
      </div>
      {hasValue && <div className="note">{meta.note(value)}</div>}
    </div>
  );
}
