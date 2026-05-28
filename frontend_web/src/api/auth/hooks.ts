import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { getCurrentUser, logout as logoutRequest, updateUserSettings } from './requests';
import { IUser } from './types';
import { useTranslation } from '@/lib/i18n';
import { getApiErrorMessage } from '../utils';

export const authKeys = {
  currentUser: ['auth', 'me'] as const,
};

export const useCurrentUser = () => {
  return useQuery<IUser, Error>({
    queryKey: authKeys.currentUser,
    queryFn: () => getCurrentUser(),
    retry: false,
    staleTime: 60000, // User shouldn't suddenly change, set longer stale time
  });
};

export const useLogout = () => {
  return useMutation<void, Error>({
    mutationFn: () => logoutRequest(),
  });
};

export const useUpdateUserSettings = () => {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  return useMutation<
    IUser,
    Error,
    { language?: string; theme?: string },
    { previousUser: IUser | undefined }
  >({
    mutationFn: data => updateUserSettings(data),
    onMutate: async data => {
      await queryClient.cancelQueries({ queryKey: authKeys.currentUser });
      const previousUser = queryClient.getQueryData<IUser>(authKeys.currentUser);
      queryClient.setQueryData<IUser>(authKeys.currentUser, old => {
        if (!old) return old;
        return {
          ...old,
          ...(data.language !== undefined && { language: data.language }),
          ...(data.theme !== undefined && {
            theme: data.theme as IUser['theme'],
          }),
        };
      });
      return { previousUser };
    },
    onError: (error, _variables, context) => {
      toast.error(getApiErrorMessage(error, t('Failed to update settings')));
      if (context?.previousUser !== undefined) {
        queryClient.setQueryData(authKeys.currentUser, context.previousUser);
      }
    },
    onSuccess: response => {
      queryClient.setQueryData(authKeys.currentUser, response);
    },
  });
};
