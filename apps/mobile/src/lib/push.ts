import Constants from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

import { apiRequest } from '@/lib/api';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldPlaySound: true,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

type PushDeviceResponse = {
  device: {
    device_id: string;
    masked_token: string;
  };
};

export async function registerPushDevice() {
  if (!Device.isDevice) {
    throw new Error('Push remoto precisa de um dispositivo fisico.');
  }

  const existing = await Notifications.getPermissionsAsync();
  let status = existing.status;
  if (status !== 'granted') {
    const requested = await Notifications.requestPermissionsAsync();
    status = requested.status;
  }
  if (status !== 'granted') {
    throw new Error('Permissao de notificacao negada.');
  }

  const projectId =
    process.env.EXPO_PUBLIC_EAS_PROJECT_ID ||
    Constants.expoConfig?.extra?.easProjectId ||
    Constants.easConfig?.projectId;
  if (!projectId) {
    throw new Error('Configure EXPO_PUBLIC_EAS_PROJECT_ID para gerar ExpoPushToken.');
  }

  const token = (await Notifications.getExpoPushTokenAsync({ projectId })).data;
  return await apiRequest<PushDeviceResponse>('/notifications/devices', {
    method: 'POST',
    body: {
      expo_push_token: token,
      platform: Platform.OS === 'ios' || Platform.OS === 'android' ? Platform.OS : 'web',
      device_name: Device.modelName || Device.deviceName || '',
      app_version: Constants.expoConfig?.version || '',
    },
  });
}

