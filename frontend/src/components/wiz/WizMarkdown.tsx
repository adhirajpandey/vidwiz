import { MarkdownTextPrimitive } from '@assistant-ui/react-markdown';
import { useAuiState } from '@assistant-ui/react';
import { createContext, useContext } from 'react';
import type { ComponentProps } from 'react';
import type { Root } from 'mdast';
import remarkGfm from 'remark-gfm';
import type { BlockCitation } from '../../api/messageParts';
import { WatchPassage } from './WizCitation';

const EMPTY_CITATIONS: BlockCitation[] = [];
const CitationsContext = createContext<BlockCitation[]>(EMPTY_CITATIONS);

function References({ index }: { index: number | null }) {
  const citations = useContext(CitationsContext);
  return <>{citations.filter(c => c.list_item_index === index).flatMap(c => c.passages)
    .map(passage => <WatchPassage key={passage.chunk_ids.join(',')} passage={passage} />)}</>;
}

// Annotate actual Markdown structure, never timestamp text, links, or code.
function referenceTargets() {
  return (tree: Root) => {
    const blocks = tree.children.filter(node => node.type !== 'definition');
    if (blocks.length !== 1) return;
    const block = blocks[0];
    if (block.type === 'list') {
      block.children.forEach((item, index) => {
        item.data = { ...item.data, hProperties: { ...item.data?.hProperties, 'data-wiz-item': index } };
      });
    }
    if (block.type === 'paragraph') {
      block.data = { ...block.data, hProperties: { ...block.data?.hProperties, 'data-wiz-block': true } };
    } else {
      tree.children.push({ type: 'paragraph', children: [], data: { hProperties: { 'data-wiz-block': true } } });
    }
  };
}

const components: ComponentProps<typeof MarkdownTextPrimitive>['components'] = {
  a: ({ children, href }) => <a href={href} target="_blank" rel="noopener noreferrer" className="wiz-accent-text underline underline-offset-2">{children}</a>,
  p: ({ children, node }) => <p>{children}{node?.properties['data-wiz-block'] && <References index={null} />}</p>,
  li: ({ children, node, ...props }) => {
    const index = node?.properties['data-wiz-item'];
    return <li {...props}>{children}{typeof index === 'number' && <References index={index} />}</li>;
  },
};

export default function WizMarkdown() {
  const citations = useAuiState(s => (s.part as { citations?: BlockCitation[] }).citations ?? EMPTY_CITATIONS);
  return <CitationsContext.Provider value={citations}><MarkdownTextPrimitive
    smooth={false}
    skipHtml
    remarkPlugins={[remarkGfm, referenceTargets]}
    className="wiz-markdown text-sm leading-7 break-words"
    components={components}
  /></CitationsContext.Provider>;
}
