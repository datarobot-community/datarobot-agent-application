import { useState, useCallback, useMemo } from 'react';
import { Copy, Check, ChevronDown, ChevronRight } from 'lucide-react';
import { Button } from './button';
import { cn } from '@/lib/utils';
import { useTranslation } from '@/lib/i18n';

const COLLAPSE_THRESHOLD = 10;
const COLLAPSED_LINES = 5;

interface CodeBlockProps {
  code: string;
  className?: string;
}

export function CodeBlock({ code, className }: CodeBlockProps) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  const lines = useMemo(() => code.split('\n'), [code]);
  const lineCount = lines.length;
  const isCollapsible = lineCount > COLLAPSE_THRESHOLD;

  const [isExpanded, setIsExpanded] = useState(!isCollapsible);

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1000);
  }, [code]);

  const displayedCode = useMemo(() => {
    if (isExpanded || !isCollapsible) {
      return code;
    }
    return lines.slice(0, COLLAPSED_LINES).join('\n');
  }, [code, lines, isExpanded, isCollapsible]);

  return (
    <div className="group relative">
      <div className="top-1 right-1 gap-1 absolute flex items-center">
        {isCollapsible && (
          <Button
            variant="ghost"
            size="icon-sm"
            className={`
                          size-6 cursor-pointer opacity-0 transition-opacity
                          group-hover:opacity-100
                        `}
            onClick={() => setIsExpanded(!isExpanded)}
            aria-label={isExpanded ? 'Collapse code' : 'Expand code'}
          >
            {isExpanded ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
          </Button>
        )}
        <Button
          variant="ghost"
          size="icon-sm"
          className={cn(
            `
                          size-6 cursor-pointer opacity-0 transition-opacity
                          group-hover:opacity-100
                        `,
            copied && 'opacity-100'
          )}
          onClick={handleCopy}
          aria-label={copied ? 'Copied' : 'Copy to clipboard'}
        >
          {copied ? <Check className="size-3 text-green-500" /> : <Copy className="size-3" />}
        </Button>
      </div>
      <pre
        className={cn(
          `
                      m-0 px-3 py-2 overflow-x-auto rounded-none border-0
                      bg-transparent code
                    `,
          className
        )}
      >
        {displayedCode}
      </pre>
      {isCollapsible && !isExpanded && (
        <button
          onClick={() => setIsExpanded(true)}
          className={`
                      px-3 py-1 w-full cursor-pointer border-t border-border/50
                      bg-muted/30 caption-01 text-left transition-colors
                      hover:bg-muted/50 hover:text-foreground
                    `}
        >
          {t('{{count}} more lines (click to expand)', {
            count: lineCount - COLLAPSED_LINES,
          })}
        </button>
      )}
    </div>
  );
}
