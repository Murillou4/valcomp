import { Image } from 'expo-image';
import { useState } from 'react';
import { Pressable, StyleSheet } from 'react-native';

import { Field, Header, Panel, PrimaryButton, Screen, StatusPill } from '@/components/valcomp-ui';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { useAuth } from '@/lib/session';

type Mode = 'login' | 'signup';

export function AuthScreen() {
  const { signIn, signUp } = useAuth();
  const [mode, setMode] = useState<Mode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  async function submit() {
    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail || password.length < 6) {
      setError('Use um email valido e uma senha com pelo menos 6 caracteres.');
      return;
    }
    setLoading(true);
    setError('');
    setNotice('');
    try {
      const response =
        mode === 'login'
          ? await signIn(cleanEmail, password)
          : await signUp(cleanEmail, password, displayName.trim());
      if (!response.session) {
        setNotice(response.message || 'Conta criada. Confirme seu email antes de entrar.');
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Nao foi possivel autenticar.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Screen>
      <Header
        eyebrow="Valcomp"
        title="Sua loja diaria no bolso."
        body="Entre com email e senha para vincular sua conta Riot pelo companion Windows e receber alertas quando a skin desejada aparecer."
      />

      <Panel style={styles.heroPanel}>
        <ThemedView style={styles.logoRow}>
          <Image source={require('@/assets/valcomp/logo.png')} style={styles.logo} contentFit="contain" />
          <StatusPill label={mode === 'login' ? 'LOGIN' : 'CRIAR CONTA'} tone="success" />
        </ThemedView>
        <Image source={require('@/assets/valcomp/store-gun.png')} style={styles.hero} contentFit="cover" />
      </Panel>

      <Panel>
        {mode === 'signup' ? (
          <Field
            label="Nome no app"
            value={displayName}
            onChangeText={setDisplayName}
            autoCapitalize="words"
            placeholder="Murillo"
          />
        ) : null}
        <Field
          label="Email"
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          keyboardType="email-address"
          placeholder="voce@email.com"
        />
        <Field
          label="Senha"
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          placeholder="minimo 6 caracteres"
        />
        <PrimaryButton onPress={submit} disabled={loading}>
          {loading ? 'Conectando...' : mode === 'login' ? 'Entrar' : 'Criar conta'}
        </PrimaryButton>

        <Pressable
          onPress={() => {
            setMode(mode === 'login' ? 'signup' : 'login');
            setError('');
            setNotice('');
          }}
          style={({ pressed }) => [styles.modeButton, pressed ? styles.pressed : null]}>
          <ThemedText type="smallBold" themeColor="accent">
            {mode === 'login' ? 'Ainda nao tenho conta' : 'Ja tenho conta'}
          </ThemedText>
        </Pressable>

        {notice ? (
          <ThemedView type="accentSoft" style={styles.notice}>
            <ThemedText type="smallBold" themeColor="accent">
              {notice}
            </ThemedText>
          </ThemedView>
        ) : null}
        {error ? (
          <ThemedView type="accentSoft" style={styles.notice}>
            <ThemedText type="smallBold" themeColor="accent">
              {error}
            </ThemedText>
          </ThemedView>
        ) : null}
      </Panel>
    </Screen>
  );
}

const styles = StyleSheet.create({
  heroPanel: {
    overflow: 'hidden',
  },
  logoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: 'transparent',
    gap: Spacing.two,
  },
  logo: {
    width: 126,
    height: 56,
  },
  hero: {
    width: '100%',
    height: 128,
    borderRadius: 24,
  },
  modeButton: {
    alignItems: 'center',
    paddingVertical: Spacing.two,
  },
  notice: {
    borderRadius: 18,
    padding: Spacing.three,
  },
  pressed: {
    transform: [{ translateY: 1 }, { scale: 0.99 }],
  },
});
