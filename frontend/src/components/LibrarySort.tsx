import LibraryDropdown from "./LibraryDropdown";
const options = [
  { value: "activity_desc", label: "Recently active" },
  { value: "title_asc", label: "Title A–Z" },
  { value: "title_desc", label: "Title Z–A" },
] as const;
type Sort = typeof options[number]["value"];
export default function LibrarySort({ value, onChange }: { value: Sort; onChange: (value: Sort) => void }) {
  return <LibraryDropdown label="Sort videos" options={options} value={value} onChange={onChange} />;
}
