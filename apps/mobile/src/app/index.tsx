import { useState } from 'react';
import { Image } from 'expo-image';
import { Pressable, StyleSheet } from 'react-native';

import { Header, Panel, PrimaryButton, Screen, SkeletonLine, StatusPill } from '@/components/valcomp-ui';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { apiRequest } from '@/lib/api';

type StoreItem = {
  item_id: string;
  name: string;
  display_icon?: string;
  tier?: string;
  price?: number;
  source: string;
};

type DailyStoreResponse = {
  expires_at?: string | null;
  seconds_remaining?: number | null;
  items: StoreItem[];
  night_market: StoreItem[];
};

export default function StoreScreen() {
  const [daily, setDaily] = useState<DailyStoreResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function loadDailyStore() {
    setLoading(true);
    setError('');
    try {
      setDaily(await apiRequest<DailyStoreResponse>('/valorant/store/daily'));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Falha ao buscar loja diaria.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Screen>
      <Header
        eyebrow="Valcomp mobile"
        title="Loja diaria sem abrir o PC toda hora."
        body="Depois do vinculo pelo companion Windows, o app consulta o backend e mostra seus itens do dia com preco, status e tempo restante."
      />

      <Panel style={styles.statusPanel}>
        <ThemedView style={styles.brandRow}>
          <Image source={require('@/assets/valcomp/logo.png')} style={styles.logo} contentFit="contain" />
          <ThemedText type="code" themeColor="textSecondary">
            BR / NA
          </ThemedText>
        </ThemedView>
        <Image source={require('@/assets/valcomp/store-gun.png')} style={styles.storeGun} contentFit="cover" />
        <ThemedView style={styles.rowBetween}>
          <StatusPill
            label={daily ? 'LOJA CARREGADA' : 'AGUARDANDO'}
            tone={daily ? 'success' : 'neutral'}
          />
          <ThemedText type="code" themeColor="textSecondary">
            {daily?.seconds_remaining ? `${Math.floor(daily.seconds_remaining / 3600)}h restantes` : 'v3/v2'}
          </ThemedText>
        </ThemedView>
        <PrimaryButton onPress={loadDailyStore} disabled={loading}>
          {loading ? 'Buscando loja...' : 'Atualizar loja diaria'}
        </PrimaryButton>
        {error ? (
          <ThemedView type="accentSoft" style={styles.notice}>
            <ThemedText type="smallBold" themeColor="accent">
              {error}
            </ThemedText>
          </ThemedView>
        ) : null}
      </Panel>

      {loading ? <StoreSkeleton /> : null}

      {daily ? (
        <ThemedView style={styles.grid}>
          {daily.items.map((item) => (
            <Pressable key={item.item_id} style={({ pressed }) => pressed && styles.pressed}>
              <Panel style={styles.itemPanel}>
                <ThemedText type="small" themeColor="textSecondary">
                  {item.tier || 'skin'}
                </ThemedText>
                <ThemedText type="subtitle" style={styles.itemName}>
                  {item.name || item.item_id.slice(0, 8)}
                </ThemedText>
                <ThemedView style={styles.rowBetween}>
                  <ThemedText type="code" themeColor="accent">
                    {item.price ? `${item.price} VP` : 'preco indisponivel'}
                  </ThemedText>
                  <StatusPill label={item.source.toUpperCase()} />
                </ThemedView>
              </Panel>
            </Pressable>
          ))}
        </ThemedView>
      ) : (
        <Panel>
          <ThemedText type="smallBold">Primeira consulta</ThemedText>
          <ThemedText themeColor="textSecondary">
            Toque em atualizar para testar o fluxo. Se o backend responder `relink_required`, abra o companion no Windows e gere um novo vinculo.
          </ThemedText>
        </Panel>
      )}
    </Screen>
  );
}

function StoreSkeleton() {
  return (
    <Panel>
      <SkeletonLine width="44%" />
      <SkeletonLine />
      <SkeletonLine width="70%" />
    </Panel>
  );
}

const styles = StyleSheet.create({
  statusPanel: {
    gap: Spacing.three,
    overflow: 'hidden',
  },
  brandRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: 'transparent',
  },
  logo: {
    width: 126,
    height: 56,
  },
  storeGun: {
    width: '100%',
    height: 112,
    borderRadius: 24,
  },
  rowBetween: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Spacing.two,
  },
  notice: {
    borderRadius: 18,
    padding: Spacing.three,
  },
  grid: {
    gap: Spacing.three,
  },
  itemPanel: {
    minHeight: 168,
    justifyContent: 'space-between',
  },
  itemName: {
    fontSize: 28,
    lineHeight: 32,
  },
  pressed: {
    transform: [{ translateY: 1 }, { scale: 0.99 }],
  },
});
