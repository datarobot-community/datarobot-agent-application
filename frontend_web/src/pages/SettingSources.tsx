import { useState, useEffect, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AlertCircle } from 'lucide-react';
import {
  useOauthProviders,
  useAuthorizeProvider,
  useValidateOAuthIdentities,
} from '@/api/oauth/hooks';
import { useCurrentUser } from '@/api/auth/hooks';
import { getBaseUrl } from '@/lib/url-utils';
import { PATHS } from '@/constants/path';
import { Skeleton } from '@/components/ui/skeleton';
import { Heading } from '@/components/ui/heading';
import { useTranslation } from '@/lib/i18n';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ProviderTile, ProviderStatus } from '@/components/custom/provider-tile';
import { IOAuthProvider } from '@/api/oauth/types';

export const SettingsSources = () => {
  const { t } = useTranslation();
  const {
    data: providers = [],
    isLoading,
    isError: isErrorFetchingProviders,
  } = useOauthProviders();
  const { mutate: authorizeProvider, isPending } = useAuthorizeProvider();
  const [connectingId, setConnectingId] = useState<string | null>(null);
  const { data: currentUser } = useCurrentUser();
  const { mutate: validateOAuthIdentities } = useValidateOAuthIdentities();

  const connectedIds = useMemo(() => {
    if (currentUser?.identities) {
      return new Set(currentUser.identities.map(id => id.provider_id));
    }
    return new Set<string>();
  }, [currentUser?.identities]);

  let baseUrl = getBaseUrl();
  if (baseUrl.endsWith('/')) {
    baseUrl = baseUrl.slice(0, -1);
  }
  const redirectUri = `${window.location.origin}${baseUrl}${PATHS.OAUTH_CB}`;
  const location = useLocation();
  const navigate = useNavigate();
  const [oauthError, setOauthError] = useState<{ code: string; message?: string } | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const errorCode = params.get('error');
    const errorMessage = params.get('error_message');
    if (errorCode) {
      setOauthError({ code: errorCode, message: errorMessage || undefined });
      params.delete('error');
      params.delete('error_message');
      navigate({ pathname: location.pathname, search: params.toString() }, { replace: true });
    }
  }, [location, navigate]);

  // Validate OAuth tokens on mount, refetch user if any are invalid
  useEffect(() => {
    validateOAuthIdentities();
  }, [validateOAuthIdentities]);

  const getProviderStatus = (provider: IOAuthProvider): ProviderStatus => {
    return connectedIds.has(provider.id) ? 'connected' : 'disconnected';
  };

  const handleConnect = (providerId: string) => {
    setConnectingId(providerId);
    authorizeProvider(
      {
        providerId,
        redirect_uri: redirectUri,
      },
      {
        onSuccess: ({ redirect_url }) => {
          window.location.href = redirect_url;
        },
        onError: () => {
          setConnectingId(null);
        },
      }
    );
  };

  return (
    <div className="flex-0">
      <div className="mb-6 pb-2 border-b border-border">
        <Heading level={4}>{t('Data connections')}</Heading>
      </div>

      {oauthError && (
        <Alert variant="destructive" className="mb-6">
          <AlertCircle className="size-4" />
          <AlertDescription>
            <div>
              <p className="mb-1 font-medium">{t('Failed to connect to OAuth provider')}</p>
              {oauthError.message && oauthError.message !== 'OAuth connection failed' ? (
                <p className="text-sm">
                  {typeof oauthError.message === 'string'
                    ? oauthError.message
                    : t('Please try again or contact support if the problem persists.')}
                </p>
              ) : (
                <p className="text-sm">
                  {t('Please try again or contact support if the problem persists.')}
                </p>
              )}
            </div>
          </AlertDescription>
        </Alert>
      )}

      {isLoading && (
        <div
          className={`
                      gap-4
                      sm:grid-cols-2
                      lg:grid-cols-3
                      grid grid-cols-1
                    `}
        >
          <Skeleton className="h-40 rounded-lg w-full" />
          <Skeleton className="h-40 rounded-lg w-full" />
          <Skeleton className="h-40 rounded-lg w-full" />
        </div>
      )}

      {isErrorFetchingProviders && (
        <p className="text-destructive">{t('Failed to load connected sources.')}</p>
      )}

      {!isLoading && !isErrorFetchingProviders && providers.length === 0 && (
        <p className="text-muted-foreground">{t('No sources available.')}</p>
      )}

      {!isLoading && providers.length > 0 && (
        <div
          className={`
                      gap-4
                      sm:grid-cols-2
                      lg:grid-cols-3
                      grid grid-cols-1
                    `}
        >
          {providers.map(provider => (
            <ProviderTile
              key={provider.id}
              type={provider.type}
              status={getProviderStatus(provider)}
              onConnect={() => handleConnect(provider.id)}
              onEdit={() => handleConnect(provider.id)}
              isConnecting={isPending && connectingId === provider.id}
            />
          ))}
        </div>
      )}
    </div>
  );
};
