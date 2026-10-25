import { ArrowDownUp, Check, ChevronDown } from 'lucide-react';
import type { LibrarySort } from '../../api';
import { Menu, MenuContent, MenuItem, MenuSeparator, MenuTrigger } from '../../components/ui/Menu';

const SORTS: { value: LibrarySort; label: string }[] = [
  { value: 'activity_desc', label: 'Recent activity' },
  { value: 'added_desc', label: 'Recently added' },
  { value: 'moments_desc', label: 'Most moments' },
  { value: 'chats_desc', label: 'Most chats' },
  { value: 'title_asc', label: 'Title A–Z' },
  { value: 'title_desc', label: 'Title Z–A' },
];

export default function SortMenu({ sort, onChange }: { sort: LibrarySort; onChange: (value: LibrarySort) => void }) {
  const label = SORTS.find(option => option.value === sort)?.label ?? 'Recent activity';
  const groups = [SORTS.slice(0, 2), SORTS.slice(2, 4), SORTS.slice(4)];
  return (
    <Menu>
      <MenuTrigger asChild>
        <button type="button" aria-label={`Sort: ${label}`} className="inline-flex h-10 shrink-0 items-center gap-2 rounded-[9px] border border-input bg-card px-3 text-sm font-medium hover:border-foreground/30 data-[state=open]:border-foreground/40">
          <ArrowDownUp className="size-4 text-muted-foreground" /><span className="hidden sm:inline">{label}</span><ChevronDown className="size-4 text-muted-foreground" />
        </button>
      </MenuTrigger>
      <MenuContent className="min-w-52">
        {groups.map((group, index) => (
          <div key={index}>
            {index > 0 && <MenuSeparator />}
            {group.map(option => (
              <MenuItem key={option.value} onSelect={() => onChange(option.value)} className="justify-between">
                {option.label}{option.value === sort && <Check className="size-4" />}
              </MenuItem>
            ))}
          </div>
        ))}
      </MenuContent>
    </Menu>
  );
}
