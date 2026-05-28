import apiClient from '../apiClient';
import { IUser } from './types';

export async function getCurrentUser(signal?: AbortSignal): Promise<IUser> {
  const { data } = await apiClient.get<IUser>('/v1/user/', { signal });
  return data;
}

export async function logout(): Promise<void> {
  await apiClient.post('/v1/logout/');
}

export async function updateUserSettings(data: {
  language?: string;
  theme?: string;
}): Promise<IUser> {
  const { data: user } = await apiClient.put<IUser>('/v1/user/settings/', data);
  return user;
}
