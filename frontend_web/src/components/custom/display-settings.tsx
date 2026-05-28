import { useState, useEffect } from 'react';
import { Monitor, Moon, Sun } from 'lucide-react';
import { Heading } from '@/components/ui/heading';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Field, FieldLabel } from '@/components/ui/field';
import { languages, saveLanguage, useTranslation } from '@/lib/i18n';
import { useUpdateUserSettings } from '@/api/auth/hooks';
import { useTheme } from '@/theme/theme-provider';

type ThemeValue = 'light' | 'dark' | 'system';

export const DisplaySettings = () => {
  const { userTheme } = useTheme();
  const { t, changeLanguage, currentLanguage } = useTranslation();
  const { mutate: updateUserSettings, isPending: isUpdating } = useUpdateUserSettings();
  const [themeState, setThemeState] = useState<ThemeValue>((userTheme ?? 'system') as ThemeValue);

  useEffect(() => {
    setThemeState((userTheme ?? 'system') as ThemeValue);
  }, [userTheme]);

  const updateLanguage = (value: string) => {
    saveLanguage(value);
    changeLanguage(value);
    updateUserSettings({ language: value });
  };

  const onThemeChange = (value: string) => {
    setThemeState(value as ThemeValue);
    updateUserSettings({ theme: value });
  };

  return (
    <div className="flex flex-0 flex-col gap-4">
      <div className="border-border border-b py-2">
        <Heading level={4}>{t('Display')}</Heading>
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-1 lg:grid-cols-3">
        <Field>
          <FieldLabel>{t('Language')}</FieldLabel>
          <Select value={currentLanguage} onValueChange={updateLanguage} disabled={isUpdating}>
            <SelectTrigger>
              <SelectValue placeholder={t('Select language')} />
            </SelectTrigger>
            <SelectContent position="popper" side="bottom">
              {languages.map(language => (
                <SelectItem key={language.id} value={language.id}>
                  {language.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      </div>

      <div>
        <Field>
          <FieldLabel>{t('Theme')}</FieldLabel>
          <Tabs value={themeState} onValueChange={onThemeChange}>
            <TabsList>
              <TabsTrigger value="light" disabled={isUpdating}>
                <Sun className="size-4" />
                {t('Light')}
              </TabsTrigger>
              <TabsTrigger value="dark" disabled={isUpdating}>
                <Moon className="size-4" />
                {t('Dark')}
              </TabsTrigger>
              <TabsTrigger value="system" disabled={isUpdating}>
                <Monitor className="size-4" />
                {t('System')}
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </Field>
      </div>
    </div>
  );
};
