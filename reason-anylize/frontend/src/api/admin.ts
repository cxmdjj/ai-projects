import type {
  DataSourceInfo,
  DataSourceTestResult,
  FeatureResponse,
  LogsResponse,
  SystemConfigItem,
} from '../types/api';
import { api } from './client';

export const adminApi = {
  async reload(): Promise<{ status: string; message: string }> {
    const { data } = await api.post<{ status: string; message: string }>('/api/admin/reload');
    return data;
  },

  async configs(): Promise<SystemConfigItem[]> {
    const { data } = await api.get<{ configs: SystemConfigItem[] }>('/api/admin/configs');
    return data.configs;
  },

  async updateConfig(key: string, value: string): Promise<void> {
    await api.put('/api/admin/configs', { key, value });
  },

  async updateFeatureConfig(key: string, value: 'on' | 'off') {
    const { data } = await api.put<{ status: string; message?: string }>('/api/admin/configs', {
      key,
      value,
    });
    return data;
  },

  async logs(lines = 200): Promise<LogsResponse> {
    const { data } = await api.get<LogsResponse>('/api/admin/logs', { params: { lines } });
    return data;
  },

  async datasources(): Promise<DataSourceInfo> {
    const { data } = await api.get<DataSourceInfo>('/api/admin/datasources');
    return data;
  },

  async testDataSource(dbType: string, conn: string): Promise<DataSourceTestResult> {
    const { data } = await api.post<DataSourceTestResult>('/api/admin/datasources/test', {
      db_type: dbType,
      conn,
    });
    return data;
  },

  async features(): Promise<FeatureResponse> {
    const { data } = await api.get<FeatureResponse>('/api/admin/features');
    return data;
  },

  async updateFeature(
    key: string,
    value: 'on' | 'off',
  ): Promise<{ status: string; config_key?: string; config_value?: string; message?: string }> {
    const { data } = await api.put<{
      status: string;
      config_key?: string;
      config_value?: string;
      message?: string;
    }>('/api/admin/features', { key, value });
    return data;
  },
};
