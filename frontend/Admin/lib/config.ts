function configured(value: string | undefined, fallbackValue: string): string {
  return value?.trim() || fallbackValue;
}

export const appConfig = Object.freeze({
  apiBaseUrl: configured(process.env.NEXT_PUBLIC_API_BASE_URL, "http://localhost:8000").replace(/\/$/, ""),
  appName: configured(process.env.NEXT_PUBLIC_APP_NAME, "Adverse Admin Workspace"),
  appVersion: configured(process.env.NEXT_PUBLIC_APP_VERSION, "0.1.0"),
  environment: configured(process.env.NEXT_PUBLIC_ENVIRONMENT, "development"),
  backendHealthUrl: configured(process.env.NEXT_PUBLIC_BACKEND_HEALTH_URL, "http://localhost:8000/health"),
});
