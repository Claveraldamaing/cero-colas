export default function Rating({ name, legend, value, onChange, low, high }) {
  return <fieldset className="rating"><legend>{legend}</legend><div className="rating-options">{[1, 2, 3, 4, 5].map(score => <label key={score} className={value === score ? 'selected' : ''}><input type="radio" name={name} value={score} checked={value === score} onChange={() => onChange(score)} required /><span>{score}</span></label>)}</div><div className="rating-labels"><span>1 · {low}</span><span>5 · {high}</span></div></fieldset>;
}
