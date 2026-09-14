import { Check, Link as LinkIcon, Pencil } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useTranslation } from '@/lib/i18n';
import gdriveIcon from '@/assets/GoogleDriveLogo.svg';
import boxIcon from '@/assets/BoxLogo.svg';
import microsoftIcon from '@/assets/MicrosoftLogo.svg';
import { IOAuthProviderType } from '@/api/oauth/types';
import { Card, CardFooter, CardContent, CardHeader } from '../ui/card';

export type ProviderStatus = 'connected' | 'disconnected';

interface ProviderTileProps {
  type: IOAuthProviderType;
  status: ProviderStatus;
  onConnect?: () => void;
  onEdit?: () => void;
  isConnecting?: boolean;
}

const PROVIDER_LOGOS: Record<IOAuthProviderType, string> = {
  google: gdriveIcon,
  box: boxIcon,
  microsoft: microsoftIcon,
};

export function ProviderTile({
  type,
  status,
  onConnect,
  onEdit,
  isConnecting = false,
}: ProviderTileProps) {
  const { t } = useTranslation();
  const PROVIDER_DISPLAY_NAMES: Record<IOAuthProviderType, string> = {
    google: t('Google Drive'),
    box: t('Box'),
    microsoft: t('Microsoft'),
  };

  const STATUS_CONFIG = {
    connected: {
      borderClass: 'border-success',
      textClass: 'text-success',
      Icon: Check,
      labelKey: t('Connected'),
    },
    disconnected: {
      borderClass: 'border-destructive',
      textClass: 'text-destructive',
      Icon: LinkIcon,
      labelKey: t('Disconnected'),
    },
  } as const;

  const displayName = PROVIDER_DISPLAY_NAMES[type] ?? type;
  const providerLogo = PROVIDER_LOGOS[type];
  const Icon = STATUS_CONFIG[status].Icon;

  return (
    <Card>
      <CardHeader className="gap-2 flex w-full items-center">
        {providerLogo && (
          <div
            className={`
                          size-9 flex shrink-0 items-center justify-center
                        `}
          >
            <img src={providerLogo} alt={displayName} className="size-full object-contain" />
          </div>
        )}
        <p className="heading-05">{displayName}</p>
      </CardHeader>
      {status !== 'disconnected' && (
        <CardContent>
          <div
            className={cn(
              `
                              gap-1 px-4 py-2 flex w-full items-center
                              justify-center rounded-md border
                            `,
              STATUS_CONFIG[status].borderClass
            )}
          >
            <Icon className={cn('size-5', STATUS_CONFIG[status].textClass)} />
            <span className={cn('body', STATUS_CONFIG[status].textClass)}>
              {STATUS_CONFIG[status].labelKey}
            </span>
          </div>
        </CardContent>
      )}

      <CardFooter>
        {status === 'disconnected' ? (
          <Button
            variant="secondary"
            className="w-full"
            onClick={onConnect}
            disabled={isConnecting}
          >
            <LinkIcon className="size-4" />
            {t('Connect')}
          </Button>
        ) : (
          <Button variant="ghost" className="w-full" onClick={onEdit}>
            <Pencil className="size-4" />
            {t('Edit connection')}
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
