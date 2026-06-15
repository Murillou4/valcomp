import { DarkTheme, DefaultTheme, ThemeProvider } from 'expo-router';
import { useColorScheme } from 'react-native';

import { AnimatedSplashOverlay } from '@/components/animated-icon';
import AppTabs from '@/components/app-tabs';
import { AuthScreen } from '@/components/auth-screen';
import { Header, Panel, Screen, SkeletonLine } from '@/components/valcomp-ui';
import { AuthProvider, useAuth } from '@/lib/session';

export default function TabLayout() {
  const colorScheme = useColorScheme();
  return (
    <ThemeProvider value={colorScheme === 'dark' ? DarkTheme : DefaultTheme}>
      <AuthProvider>
        <AnimatedSplashOverlay />
        <AuthenticatedApp />
      </AuthProvider>
    </ThemeProvider>
  );
}

function AuthenticatedApp() {
  const { loading, session } = useAuth();
  if (loading) {
    return (
      <Screen>
        <Header
          eyebrow="Valcomp"
          title="Preparando sua sessao."
          body="Estamos restaurando o login salvo e conferindo o backend antes de abrir o app."
        />
        <Panel>
          <SkeletonLine width="48%" />
          <SkeletonLine />
          <SkeletonLine width="72%" />
        </Panel>
      </Screen>
    );
  }
  if (!session) {
    return <AuthScreen />;
  }
  return <AppTabs />;
}
