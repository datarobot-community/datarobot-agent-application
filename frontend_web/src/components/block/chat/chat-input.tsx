import { Loader2, Send } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Textarea } from '@/components/ui/textarea';
import { type KeyboardEvent, useRef, useState } from 'react';
import { useTranslation } from '@/lib/i18n';
import { cn } from '@/lib/utils';

export interface ChatTextInputProps {
  onSubmit: (text: string) => Promise<unknown>;
  userInput: string;
  setUserInput: (value: string) => void;
  runningAgent: boolean;
}

export function ChatTextInput({
  onSubmit,
  userInput,
  setUserInput,
  runningAgent,
}: ChatTextInputProps) {
  const { t } = useTranslation();
  const ref = useRef<HTMLTextAreaElement>(null);
  const [isComposing, setIsComposing] = useState(false);

  function keyDownHandler(e: KeyboardEvent) {
    const draft = (ref.current?.value ?? userInput).trim();
    if (e.key === 'Enter' && !e.shiftKey && !isComposing && !runningAgent && draft.length) {
      if (e.ctrlKey || e.metaKey) {
        const el = ref.current;
        e.preventDefault();
        if (el) {
          const start = el.selectionStart;
          const end = el.selectionEnd;
          const val = el.value;
          const newValue = val.slice(0, start) + '\n' + val.slice(end);
          setUserInput(newValue);
        }
      } else {
        e.preventDefault();
        const raw = ref.current?.value ?? userInput;
        void onSubmit(raw);
      }
    }
  }

  return (
    <div className="relative shrink-0">
      <Textarea
        ref={ref}
        data-testid="chat-message-input"
        value={userInput}
        onChange={e => setUserInput(e.target.value)}
        onCompositionStart={() => setIsComposing(true)}
        onCompositionEnd={() => setIsComposing(false)}
        onKeyDown={keyDownHandler}
        className="h-auto min-h-20 flex-1 shrink-0 resize-none overflow-x-hidden overflow-y-auto pr-12"
      ></Textarea>
      {runningAgent ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="absolute right-2 bottom-2">
              <Button testId="send-message-disabled-btn" type="submit" size="icon" disabled>
                <Loader2 className="animate-spin" />
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent>{t('Agent is running')}</TooltipContent>
        </Tooltip>
      ) : (
        <Button
          type="button"
          onClick={() => {
            const raw = ref.current?.value ?? userInput;
            if (!raw.trim()) return;
            void onSubmit(raw);
          }}
          className={cn(
            'absolute right-2 bottom-2',
            !runningAgent && !userInput.trim() && 'opacity-50'
          )}
          size="icon"
          testId="send-message-btn"
          disabled={runningAgent}
        >
          <Send />
        </Button>
      )}
    </div>
  );
}
