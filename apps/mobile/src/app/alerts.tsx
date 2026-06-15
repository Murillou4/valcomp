import { useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet } from 'react-native';

import { Field, Header, Panel, PrimaryButton, Screen, SkeletonLine, StatusPill } from '@/components/valcomp-ui';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { apiRequest } from '@/lib/api';
import { registerPushDevice } from '@/lib/push';

type SkinAsset = {
  uuid: string;
  displayName?: string;
  displayIcon?: string;
  fullRender?: string;
  contentTierUuid?: string;
};

type WatchItem = {
  item_id: string;
  item_name?: string;
  display_icon?: string;
  tier?: string;
  notify_enabled: boolean;
};

type SkinListResponse = {
  items: SkinAsset[];
};

type WatchlistResponse = {
  items: WatchItem[];
};

export default function AlertsScreen() {
  const [query, setQuery] = useState('');
  const [skins, setSkins] = useState<SkinAsset[]>([]);
  const [watchlist, setWatchlist] = useState<WatchItem[]>([]);
  const [loadingSkins, setLoadingSkins] = useState(false);
  const [loadingWatchlist, setLoadingWatchlist] = useState(false);
  const [busyItem, setBusyItem] = useState('');
  const [pushLoading, setPushLoading] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    loadWatchlist();
  }, []);

  const watchIds = useMemo(
    () => new Set(watchlist.map((item) => item.item_id.toLowerCase())),
    [watchlist],
  );

  const filteredSkins = useMemo(() => {
    const cleanQuery = query.trim().toLowerCase();
    const list = cleanQuery
      ? skins.filter((skin) => (skin.displayName || '').toLowerCase().includes(cleanQuery))
      : skins;
    return list.slice(0, 30);
  }, [query, skins]);

  async function loadSkins() {
    setLoadingSkins(true);
    setError('');
    try {
      const response = await apiRequest<SkinListResponse>('/valorant/items/skins');
      setSkins(response.items.filter((skin) => skin.displayName));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Nao foi possivel carregar as skins.');
    } finally {
      setLoadingSkins(false);
    }
  }

  async function loadWatchlist() {
    setLoadingWatchlist(true);
    setError('');
    try {
      const response = await apiRequest<WatchlistResponse>('/valorant/skins/watchlist');
      setWatchlist(response.items);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Nao foi possivel carregar seus alertas.');
    } finally {
      setLoadingWatchlist(false);
    }
  }

  async function addSkin(skin: SkinAsset) {
    setBusyItem(skin.uuid);
    setError('');
    setNotice('');
    try {
      const response = await apiRequest<{ item: WatchItem }>('/valorant/skins/watchlist', {
        method: 'POST',
        body: { item_id: skin.uuid, notify_enabled: true },
      });
      setWatchlist((current) => [
        response.item,
        ...current.filter((item) => item.item_id.toLowerCase() !== skin.uuid.toLowerCase()),
      ]);
      setNotice(`${response.item.item_name || skin.displayName || 'Skin'} adicionada aos alertas.`);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Nao foi possivel adicionar o alerta.');
    } finally {
      setBusyItem('');
    }
  }

  async function removeSkin(itemId: string) {
    setBusyItem(itemId);
    setError('');
    setNotice('');
    try {
      await apiRequest(`/valorant/skins/watchlist/${itemId}`, { method: 'DELETE' });
      setWatchlist((current) =>
        current.filter((item) => item.item_id.toLowerCase() !== itemId.toLowerCase()),
      );
      setNotice('Alerta removido.');
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Nao foi possivel remover o alerta.');
    } finally {
      setBusyItem('');
    }
  }

  async function enablePush() {
    setPushLoading(true);
    setError('');
    setNotice('');
    try {
      await registerPushDevice();
      setNotice('Notificacoes ativadas neste aparelho.');
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Nao foi possivel ativar notificacoes.');
    } finally {
      setPushLoading(false);
    }
  }

  return (
    <Screen>
      <Header
        eyebrow="Alertas"
        title="Avise quando a skin aparecer."
        body="Escolha skins desejadas, ative notificacoes no aparelho e o backend confere a loja diaria para te avisar."
      />

      <Panel>
        <ThemedView style={styles.rowBetween}>
          <StatusPill label={`${watchlist.length} ALERTAS`} tone={watchlist.length ? 'success' : 'neutral'} />
          <ThemedText type="code" themeColor="textSecondary">
            loja diaria
          </ThemedText>
        </ThemedView>
        <PrimaryButton onPress={enablePush} disabled={pushLoading}>
          {pushLoading ? 'Ativando...' : 'Ativar notificacoes neste aparelho'}
        </PrimaryButton>
        <PrimaryButton onPress={loadWatchlist} disabled={loadingWatchlist}>
          {loadingWatchlist ? 'Atualizando...' : 'Atualizar meus alertas'}
        </PrimaryButton>
      </Panel>

      {watchlist.length ? (
        <Panel>
          <ThemedText type="smallBold">Skins monitoradas</ThemedText>
          {watchlist.map((item) => (
            <ThemedView key={item.item_id} style={styles.watchRow}>
              <ThemedView style={styles.transparent}>
                <ThemedText type="smallBold">{item.item_name || item.item_id.slice(0, 8)}</ThemedText>
                <ThemedText type="code" themeColor="textSecondary">
                  {item.tier || 'skin'}
                </ThemedText>
              </ThemedView>
              <Pressable
                disabled={busyItem === item.item_id}
                onPress={() => removeSkin(item.item_id)}
                style={({ pressed }) => [styles.smallButton, pressed ? styles.pressed : null]}>
                <ThemedText type="smallBold" themeColor="accent">
                  Remover
                </ThemedText>
              </Pressable>
            </ThemedView>
          ))}
        </Panel>
      ) : (
        <Panel>
          <ThemedText type="smallBold">Nenhum alerta ainda</ThemedText>
          <ThemedText themeColor="textSecondary">
            Carregue a lista de skins e adicione uma desejada para comecar.
          </ThemedText>
        </Panel>
      )}

      <Panel>
        <Field
          label="Buscar skin"
          value={query}
          onChangeText={setQuery}
          placeholder="Vandal, Phantom, Sheriff..."
        />
        <PrimaryButton onPress={loadSkins} disabled={loadingSkins}>
          {loadingSkins ? 'Carregando catalogo...' : skins.length ? 'Recarregar skins' : 'Carregar skins'}
        </PrimaryButton>
      </Panel>

      {loadingSkins ? (
        <Panel>
          <SkeletonLine width="44%" />
          <SkeletonLine />
          <SkeletonLine width="68%" />
        </Panel>
      ) : null}

      {filteredSkins.length ? (
        <ThemedView style={styles.grid}>
          {filteredSkins.map((skin) => {
            const watching = watchIds.has(skin.uuid.toLowerCase());
            return (
              <Panel key={skin.uuid} style={styles.skinPanel}>
                <ThemedText type="small" themeColor="textSecondary">
                  {skin.contentTierUuid ? skin.contentTierUuid.slice(0, 8) : 'skin'}
                </ThemedText>
                <ThemedText type="subtitle" style={styles.skinName}>
                  {skin.displayName}
                </ThemedText>
                <PrimaryButton
                  onPress={() => addSkin(skin)}
                  disabled={watching || busyItem === skin.uuid}>
                  {watching ? 'Alerta ativo' : busyItem === skin.uuid ? 'Adicionando...' : 'Adicionar alerta'}
                </PrimaryButton>
              </Panel>
            );
          })}
        </ThemedView>
      ) : null}

      {notice ? (
        <Panel>
          <StatusPill label="OK" tone="success" />
          <ThemedText themeColor="textSecondary">{notice}</ThemedText>
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
  watchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Spacing.three,
    backgroundColor: 'transparent',
  },
  transparent: {
    flex: 1,
    backgroundColor: 'transparent',
  },
  smallButton: {
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.two,
  },
  grid: {
    gap: Spacing.three,
  },
  skinPanel: {
    minHeight: 156,
    justifyContent: 'space-between',
  },
  skinName: {
    fontSize: 25,
    lineHeight: 30,
  },
  pressed: {
    opacity: 0.72,
  },
});
