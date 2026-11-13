function enabled(value: string | undefined): boolean {
  return value?.trim().toLowerCase() === "true";
}

export const authConfig = {
  backendUrl: process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  accessCookie: "loopless_client_access",
  refreshCookie: "loopless_client_refresh",
  allowedRole: "COMPANY_CLIENT",
  signupRole: "CLIENT",
  signupEnabled: enabled(process.env.NEXT_PUBLIC_PUBLIC_SIGNUP_ENABLED),
  signupDisabledMessage: "Sign up is currently unavailable. Please contact your administrator.",
  roleLabel: "Client",
  requiresCompanyName: false,
  requiresCompanyCode: true,
  signupDescription: "Create a client account for your company workspace and verify it with OTP.",
} as const;
