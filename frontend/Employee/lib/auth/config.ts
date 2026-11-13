function enabled(value: string | undefined): boolean {
  return value?.trim().toLowerCase() === "true";
}

export const authConfig = {
  backendUrl: process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  accessCookie: "loopless_employee_access",
  refreshCookie: "loopless_employee_refresh",
  allowedRole: "COMPANY_EMPLOYEE",
  signupRole: "EMPLOYEE",
  signupEnabled: enabled(process.env.NEXT_PUBLIC_PUBLIC_SIGNUP_ENABLED),
  signupDisabledMessage: "Sign up is currently unavailable. Please contact your administrator.",
  roleLabel: "Employee",
  requiresCompanyName: false,
  requiresCompanyCode: true,
  signupDescription: "Join your company workspace using the code shared by your admin.",
} as const;

export function isAllowedRole(roleCode: string): boolean {
  return roleCode === authConfig.allowedRole || roleCode.startsWith(`${authConfig.allowedRole}__`);
}
