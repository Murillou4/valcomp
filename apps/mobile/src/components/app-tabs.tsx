import { NativeTabs } from 'expo-router/unstable-native-tabs';
import { useColorScheme } from 'react-native';

import { Colors, Fonts } from '@/constants/theme';

export default function AppTabs() {
  const scheme = useColorScheme();
  const colors = Colors[scheme === 'unspecified' ? 'light' : scheme];

  return (
    <NativeTabs
      backgroundColor={colors.background}
      blurEffect="systemChromeMaterialDark"
      iconColor={{ default: colors.textSecondary, selected: colors.accent }}
      indicatorColor={colors.backgroundSelected}
      labelStyle={{
        default: { color: colors.textSecondary, fontFamily: Fonts.sans, fontSize: 12, fontWeight: '600' },
        selected: { color: colors.text, fontFamily: Fonts.sans, fontSize: 12, fontWeight: '700' },
      }}
      rippleColor={colors.accentSoft}>
      <NativeTabs.Trigger name="index">
        <NativeTabs.Trigger.Label>Loja</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon
          md={{ default: 'storefront', selected: 'local_mall' }}
          sf={{ default: 'bag', selected: 'bag.fill' }}
        />
      </NativeTabs.Trigger>

      <NativeTabs.Trigger name="link">
        <NativeTabs.Trigger.Label>Vincular</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon
          md={{ default: 'link', selected: 'linked_services' }}
          sf={{ default: 'link', selected: 'link.circle.fill' }}
        />
      </NativeTabs.Trigger>

      <NativeTabs.Trigger name="alerts">
        <NativeTabs.Trigger.Label>Alertas</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon
          md={{ default: 'notifications', selected: 'notifications_active' }}
          sf={{ default: 'bell', selected: 'bell.fill' }}
        />
      </NativeTabs.Trigger>

      <NativeTabs.Trigger name="account">
        <NativeTabs.Trigger.Label>Conta</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon
          md={{ default: 'person', selected: 'account_circle' }}
          sf={{ default: 'person', selected: 'person.crop.circle.fill' }}
        />
      </NativeTabs.Trigger>
    </NativeTabs>
  );
}
