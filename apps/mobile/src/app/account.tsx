import { useEffect, useMemo, useState } from 'react';
import { StyleSheet } from 'react-native';

import {
  AnimatedBlock,
  Header,
  Notice,
  Panel,
  PrimaryButton,
  Screen,
  SkeletonLine,
  StatusPill,
} from '@/components/valcomp-ui';
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
  const { signOut, user, profile } = useAuth();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [pushLoading, setPushLoading] = useState(false);
  const [pushStatus, setPushStatus] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    loadProfile();
  }, []);

  const riot = me?.riot_account;
  const displayName = me?.profile.display_name || profile?.display_name || user?.email || 'Valcomp';
  const initials = useMemo(() => {
    const source = displayName.replace(/@.*/, '').trim();
    return (source[0] || 'V').toUpperCase();
  }, [displayName]);
  const riotName = riot?.game_name
    ? `${riot.game_name}${riot.tag_line ? `#${riot.tag_line}` : ''}`
    : 'Riot ainda nao vinculada';

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

  return (
    <Screen>
      <AnimatedBlock>
        <Header
          eyebrow="Conta"
          title="Seu perfil Valcomp."
          body="Dados do app, vinculo Riot, notificacoes e estado da sessao ficam reunidos aqui."
        />
      </AnimatedBlock>

      <AnimatedBlock delay={70}>
        <Panel style={styles.profilePanel}>
          <ThemedView style={styles.profileTop}>
            <ThemedView type="accentSoft" style={styles.avatar}>
              <ThemedText style={styles.avatarText} themeColor="accent">
                {initials}
              </ThemedText>
            </ThemedView>
            <ThemedView style={styles.identity}>
              <ThemedText type="subtitle" style={styles.name}>
                {displayName}
              </ThemedText>
              <ThemedText type="code" themeColor="textSecondary">
                {user?.email || me?.user.email || me?.user.id || 'sessao ativa'}
              </ThemedText>
            </ThemedView>
          </ThemedView>

          <ThemedView style={styles.rowBetween}>
            <StatusPill label={riot ? 'RIOT VINCULADA' : 'SEM VINCULO'} tone={riot ? 'success' : 'warning'} />
            <ThemedText type="code" themeColor="textSecondary">
              {riot ? `${riot.region.toUpperCase()} / ${riot.shard.toUpperCase()}` : 'mobile'}
            </ThemedText>
          </ThemedView>
        </Panel>
      </AnimatedBlock>

      <AnimatedBlock delay={120}>
        <Panel>
          <ThemedText type="smallBold">Acoes rapidas</ThemedText>
          <PrimaryButton onPress={loadProfile} disabled={loading}>
            {loading ? 'Atualizando...' : 'Atualizar perfil'}
          </PrimaryButton>
          <PrimaryButton variant="secondary" onPress={enablePush} disabled={pushLoading}>
            {pushLoading ? 'Ativando notificacoes...' : 'Ativar notificacoes de skin'}
          </PrimaryButton>
          <PrimaryButton variant="danger" onPress={signOut}>
            Sair da conta
          </PrimaryButton>
          {pushStatus ? (
            <ThemedText type="small" themeColor="success">
              {pushStatus}
            </ThemedText>
          ) : null}
        </Panel>
      </AnimatedBlock>

      {loading ? (
        <Panel>
          <SkeletonLine width="40%" />
          <SkeletonLine />
          <SkeletonLine width="64%" />
        </Panel>
      ) : null}

      <AnimatedBlock delay={170}>
        <Panel>
          <ThemedText type="smallBold">Conta Riot</ThemedText>
          <ThemedText type="subtitle" style={styles.riotName}>
            {riotName}
          </ThemedText>
          <InfoRow label="PUUID" value={riot?.puuid ? `${riot.puuid.slice(0, 8)}...${riot.puuid.slice(-4)}` : 'indisponivel'} />
          <InfoRow label="Cliente" value={riot?.client_version || 'a detectar'} />
          <InfoRow label="Sessao" value={riot ? 'remota ativa' : 'precisa vincular'} />
        </Panel>
      </AnimatedBlock>

      {error ? <Notice title="ATENCAO" body={error} tone="warning" /> : null}
    </Screen>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <ThemedView style={styles.infoRow}>
      <ThemedText type="code" themeColor="textSecondary">
        {label}
      </ThemedText>
      <ThemedText type="smallBold">{value}</ThemedText>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  profilePanel: {
    gap: Spacing.three,
  },
  profileTop: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.three,
    backgroundColor: 'transparent',
  },
  avatar: {
    width: 66,
    height: 66,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontSize: 32,
    lineHeight: 36,
    fontWeight: '800',
  },
  identity: {
    flex: 1,
    gap: Spacing.one,
    backgroundColor: 'transparent',
  },
  name: {
    fontSize: 30,
    lineHeight: 33,
  },
  rowBetween: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Spacing.two,
    backgroundColor: 'transparent',
  },
  riotName: {
    fontSize: 28,
    lineHeight: 32,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: Spacing.three,
    paddingVertical: Spacing.two,
    backgroundColor: 'transparent',
  },
});
