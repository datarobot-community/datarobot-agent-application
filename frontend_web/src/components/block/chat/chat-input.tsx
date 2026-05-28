import { Loader2, Send } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Textarea } from '@/components/ui/textarea';
import { type KeyboardEvent, useEffect, useRef, useState } from 'react';
import { useTranslation } from '@/lib/i18n';

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
  const [value, setValue] = useState(userInput);
  const valueRef = useRef(value);

  function updateValue(next: string) {
    valueRef.current = next;
    setValue(next);
  }

  function handleBlur() {
    setUserInput(valueRef.current);
  }

  function handleSubmit(text: string) {
    updateValue('');
    return onSubmit(text);
  }

  function keyDownHandler(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey && !isComposing && !runningAgent && value.trim().length) {
      if (e.ctrlKey || e.metaKey) {
        const el = ref.current;
        e.preventDefault();
        if (el) {
          const start = el.selectionStart ?? 0;
          const end = el.selectionEnd ?? 0;
          updateValue(value.slice(0, start) + '\n' + value.slice(end));
          requestAnimationFrame(() => {
            el.selectionStart = start + 1;
            el.selectionEnd = start + 1;
          });
        }
      } else {
        e.preventDefault();
        handleSubmit(value);
      }
    }
  }

  // setUserInput identity changes when chatId changes — resync local state to the new chat's draft
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    updateValue(userInput);
  }, [setUserInput]);

  useEffect(() => {
    return () => {
      setUserInput(valueRef.current);
    };
  }, [setUserInput]);

  return (
    <div className="relative shrink-0">
      <Textarea
        ref={ref}
        data-testid="chat-message-input"
        value={value}
        onChange={e => updateValue(e.target.value)}
        onBlur={handleBlur}
        onCompositionStart={() => setIsComposing(true)}
        onCompositionEnd={() => setIsComposing(false)}
        onKeyDown={keyDownHandler}
        className="h-auto min-h-20 flex-1 shrink-0 resize-none overflow-x-hidden overflow-y-auto pr-12"
      />
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
          type="submit"
          onClick={() => handleSubmit(value)}
          className="absolute right-2 bottom-2"
          size="icon"
          testId="send-message-btn"
          disabled={!value.trim().length}
        >
          <Send />
        </Button>
      )}
    </div>
  );
}
