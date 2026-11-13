function enabled(value: string | undefined): boolean {
  return value?.trim().toLowerCase() === "true";
}

export const authConfig = {
  backendUrl: process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  accessCookie: "loopless_manager_access",
  refreshCookie: "loopless_manager_refresh",
  allowedRole: "COMPANY_MANAGER",
  signupRole: "MANAGER",
  signupEnabled: enabled(process.env.NEXT_PUBLIC_PUBLIC_SIGNUP_ENABLED),
  signupDisabledMessage: "Sign up is currently unavailable. Please contact your administrator.",
  roleLabel: "Manager",
  requiresCompanyName: false,
  requiresCompanyCode: true,
  signupDescription: "Join an existing company with your company code and verify with OTP.",
} as const;

export function isAllowedRole(roleCode: string): boolean {
  return roleCode === authConfig.allowedRole || roleCode.startsWith(`${authConfig.allowedRole}__`);
}
