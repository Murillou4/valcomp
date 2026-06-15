import { useState } from 'react';
import { StyleSheet } from 'react-native';

import { Header, Panel, PrimaryButton, Screen, SkeletonLine, StatusPill } from '@/components/valcomp-ui';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { apiRequest } from '@/lib/api';
import { registerPushDevice } from '@/lib/push';
import { useAuth } from '@/lib/session';

type MeResponse = {
  user: {
    id: string;
    email?: string | null;
  };
  profile: {
    display_name?: string;
    avatar_url?: string;
  };
  riot_account?: {
    puuid: string;
    game_name?: string;
    tag_line?: string;
    region: string;
    shard: string;
    client_version?: string;
  } | null;
};

export default function AccountScreen() {
  const { signOut, user } = useAuth();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [pushLoading, setPushLoading] = useState(false);
  const [pushStatus, setPushStatus] = useState('');
  const [error, setError] = useState('');

  async function loadProfile() {
    setLoading(true);
    setError('');
    try {
      setMe(await apiRequest<MeResponse>('/me'));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Nao foi possivel carregar a conta.');
    } finally {
      setLoading(false);
    }
  }

  async function enablePush() {
    setPushLoading(true);
    setPushStatus('');
    setError('');
    try {
      const result = await registerPushDevice();
      setPushStatus(`Dispositivo registrado: ${result.device.masked_token}`);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Nao foi possivel ativar notificacoes.');
    } finally {
      setPushLoading(false);
    }
  }

  const riot = me?.riot_account;
  const riotName = riot?.game_name ? `${riot.game_name}${riot.tag_line ? `#${riot.tag_line}` : ''}` : 'Sem Riot vinculada';

  return (
    <Screen>
      <Header
        eyebrow="Conta"
        title="Perfil do app e Riot no mesmo lugar."
        body="Aqui vamos mostrar foto, preferencia, carteira, inventario e sinais de revinculo quando a sessao Riot expirar."
      />

      <Panel>
        <ThemedView style={styles.rowBetween}>
          <StatusPill label={riot ? 'RIOT VINCULADA' : 'SEM VINCULO'} tone={riot ? 'success' : 'warning'} />
          <ThemedText type="code" themeColor="textSecondary">
            {riot ? `${riot.region.toUpperCase()} / ${riot.shard.toUpperCase()}` : 'mobile'}
          </ThemedText>
        </ThemedView>
        <PrimaryButton onPress={loadProfile} disabled={loading}>
          {loading ? 'Atualizando...' : 'Atualizar perfil'}
        </PrimaryButton>
        <PrimaryButton onPress={enablePush} disabled={pushLoading}>
          {pushLoading ? 'Ativando notificacoes...' : 'Ativar notificacoes de skin'}
        </PrimaryButton>
        <PrimaryButton onPress={signOut}>Sair da conta</PrimaryButton>
        {pushStatus ? (
          <ThemedText type="small" themeColor="success">
            {pushStatus}
          </ThemedText>
        ) : null}
      </Panel>

      {loading ? (
        <Panel>
          <SkeletonLine width="40%" />
          <SkeletonLine />
          <SkeletonLine width="64%" />
        </Panel>
      ) : null}

      {me ? (
        <Panel>
          <ThemedText type="subtitle" style={styles.name}>
            {riotName}
          </ThemedText>
          <ThemedText themeColor="textSecondary">
            App user: {me.profile.display_name || me.user.email || me.user.id}
          </ThemedText>
          <ThemedText type="code" themeColor="textSecondary">
            Login {user?.email || me.user.email || me.user.id}
          </ThemedText>
          <ThemedText type="code" themeColor="textSecondary">
            PUUID {riot?.puuid ? `${riot.puuid.slice(0, 8)}...${riot.puuid.slice(-4)}` : 'indisponivel'}
          </ThemedText>
          <ThemedText type="code" themeColor="textSecondary">
            Client {riot?.client_version || 'a detectar'}
          </ThemedText>
        </Panel>
      ) : null}

      {error ? (
        <Panel>
          <StatusPill label="ERRO" tone="warning" />
          <ThemedText themeColor="textSecondary">{error}</ThemedText>
        </Panel>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  rowBetween: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Spacing.two,
  },
  name: {
    fontSize: 30,
    lineHeight: 34,
  },
});
