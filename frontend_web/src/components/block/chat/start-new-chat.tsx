import { Button } from '@/components/ui/button';
import { useTranslation } from '@/lib/i18n';

export function StartNewChat({ createChat }: { createChat: () => void }) {
  const { t } = useTranslation();

  return (
    <section
      className={`
              px-6 py-12 flex min-h-full flex-1 items-center justify-center
              text-center
            `}
    >
      <div
        className={`
                  max-w-md gap-6 px-8 py-10 shadow-xs rounded-lg flex w-full
                  flex-col items-center
                `}
      >
        <div className="space-y-3">
          <p className="heading-02 capitalize">{t('No chats selected')}</p>
          <p className="body-secondary">
            {t('Choose an existing conversation in the sidebar or start a new chat to begin.')}
          </p>
        </div>
        <Button size="lg" onClick={createChat}>
          {t('Start a new chat')}
        </Button>
      </div>
    </section>
  );
}
