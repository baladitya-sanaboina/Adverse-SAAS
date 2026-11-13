export interface CurrentUserPermission {
  module: string;
  module_name: string;
  action: string;
  action_name: string;
}

export interface CurrentUser {
  user: {
    id: string;
    name: string;
    email: string;
    status: string;
    created_at: string;
    profile_image_url: string | null;
  };
  company: {
    id: string;
    name: string;
    code: string;
    subscription_plan: string;
    status: string;
    subscription_features: Record<string, boolean>;
  } | null;
  role: { id: string; name: string; code: string };
  permissions: CurrentUserPermission[];
}

export interface ApiError {
  code?: string;
  detail?: string;
}
