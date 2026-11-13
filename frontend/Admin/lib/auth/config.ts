function enabled(value: string | undefined): boolean {
  return value?.trim().toLowerCase() === "true";
}

export const authConfig = {
  backendUrl: process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  accessCookie: "loopless_admin_access",
  refreshCookie: "loopless_admin_refresh",
  allowedRole: "COMPANY_ADMIN",
  signupRole: "ADMIN",
  signupEnabled: enabled(process.env.NEXT_PUBLIC_PUBLIC_SIGNUP_ENABLED),
  signupDisabledMessage: "Sign up is currently unavailable. Please contact your administrator.",
  roleLabel: "Admin",
  requiresCompanyName: true,
  requiresCompanyCode: true,
  signupDescription: "Create a company workspace and verify it with the OTP sent to your email.",
} as const;
