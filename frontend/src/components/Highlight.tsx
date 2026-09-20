import { Fragment } from "react";

export default function Highlight({
  text,
  query = "",
}: {
  text: string;
  query?: string;
}) {
  if (!query) return <>{text}</>;
  const parts = [];
  const lower = text.toLowerCase();
  let cursor = 0;
  let index = lower.indexOf(query.toLowerCase());
  while (index !== -1) {
    parts.push(
      <Fragment key={index}>
        {text.slice(cursor, index)}
        <mark className="rounded bg-red-500/15 text-inherit">
          {text.slice(index, index + query.length)}
        </mark>
      </Fragment>,
    );
    cursor = index + query.length;
    index = lower.indexOf(query.toLowerCase(), cursor);
  }
  return (
    <>
      {parts}
      {text.slice(cursor)}
    </>
  );
}
