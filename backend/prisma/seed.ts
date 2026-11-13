import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

const roles = [
  { name: "Platform Owner", code: "PLATFORM_OWNER" },
  { name: "Developer", code: "DEVELOPER" },
  { name: "Company Admin", code: "COMPANY_ADMIN" },
  { name: "Company Manager", code: "COMPANY_MANAGER" },
  { name: "Company Employee", code: "COMPANY_EMPLOYEE" },
  { name: "Company Client", code: "COMPANY_CLIENT" },
] as const;

const modules = [
  "Dashboard",
  "Users",
  "Companies",
  "Employees",
  "Clients",
  "Projects",
  "Tasks",
  "CRM",
  "Finance",
  "Invoices",
  "Attendance",
  "Documents",
  "Notifications",
  "Reports",
  "Settings",
  "Subscriptions",
  "Developers",
  "Tickets",
  "Departments",
  "Branches",
  "Invitations",
  "Roles",
].map((name) => ({ name, code: name.toUpperCase().replaceAll(" ", "_") }));

const permissions = [
  "View",
  "Create",
  "Edit",
  "Delete",
  "Approve",
  "Assign",
  "Export",
  "Import",
  "Manage",
].map((name) => ({ name, code: name.toUpperCase() }));

const allActions = permissions.map(({ code }) => code);
const permissionMatrix: Record<string, Record<string, string[]>> = {
  PLATFORM_OWNER: {
    DASHBOARD: ["VIEW", "MANAGE"],
    COMPANIES: ["VIEW", "CREATE", "EDIT", "DELETE"],
    DEVELOPERS: allActions,
  },
  DEVELOPER: {
    COMPANIES: ["VIEW"],
    SUBSCRIPTIONS: ["MANAGE"],
  },
  COMPANY_ADMIN: {
    DASHBOARD: ["VIEW"],
    USERS: ["VIEW", "MANAGE"],
    DEPARTMENTS: ["VIEW", "CREATE", "EDIT", "DELETE"],
    BRANCHES: ["VIEW", "CREATE", "EDIT", "DELETE"],
    INVITATIONS: ["VIEW", "CREATE", "MANAGE"],
    ROLES: ["VIEW", "CREATE", "EDIT", "DELETE", "MANAGE"],
    EMPLOYEES: allActions,
    CLIENTS: allActions,
    CRM: ["VIEW", "CREATE", "EDIT"],
    PROJECTS: allActions,
    REPORTS: ["VIEW"],
    SETTINGS: ["VIEW", "MANAGE"],
  },
  COMPANY_MANAGER: {
    DASHBOARD: ["VIEW"],
    EMPLOYEES: ["VIEW"],
    CLIENTS: ["VIEW", "CREATE", "EDIT"],
    CRM: ["VIEW", "CREATE", "EDIT"],
    PROJECTS: ["VIEW", "CREATE", "EDIT", "ASSIGN"],
    TASKS: ["VIEW", "EDIT", "ASSIGN"],
    ATTENDANCE: ["VIEW"],
    DOCUMENTS: ["VIEW"],
    REPORTS: ["VIEW"],
  },
  COMPANY_EMPLOYEE: {
    PROJECTS: ["VIEW"],
    TASKS: ["VIEW", "EDIT"],
    ATTENDANCE: ["VIEW"],
  },
  COMPANY_CLIENT: {
    PROJECTS: ["VIEW"],
    INVOICES: ["VIEW"],
    TICKETS: ["VIEW"],
  },
};

const subscriptionPlans = [
  {
    name: "Starter",
    code: "STARTER",
    description: "Core tools for small teams getting started with Adverse.",
    monthlyPrice: 29,
    yearlyPrice: 290,
    displayOrder: 1,
    features: [
      "EMPLOYEE_MANAGEMENT",
      "CLIENT_MANAGEMENT",
      "PROJECTS",
      "TASKS",
      "NOTIFICATIONS",
    ],
    limits: {
      MAX_EMPLOYEES: 25,
      MAX_CLIENTS: 100,
      MAX_PROJECTS: 20,
      MAX_STORAGE_GB: 10,
    },
  },
  {
    name: "Professional",
    code: "PROFESSIONAL",
    description:
      "Advanced operations, reporting, and integrations for growing companies.",
    monthlyPrice: 79,
    yearlyPrice: 790,
    displayOrder: 2,
    features: [
      "EMPLOYEE_MANAGEMENT",
      "CLIENT_MANAGEMENT",
      "PROJECTS",
      "TASKS",
      "CRM",
      "FINANCE",
      "DOCUMENTS",
      "REPORTS",
      "NOTIFICATIONS",
      "API_ACCESS",
    ],
    limits: {
      MAX_EMPLOYEES: 150,
      MAX_CLIENTS: 1000,
      MAX_PROJECTS: 250,
      MAX_STORAGE_GB: 100,
    },
  },
  {
    name: "Enterprise",
    code: "ENTERPRISE",
    description: "Unlimited scale, white-label controls, and AI capabilities.",
    monthlyPrice: 199,
    yearlyPrice: 1990,
    displayOrder: 3,
    features: [
      "EMPLOYEE_MANAGEMENT",
      "CLIENT_MANAGEMENT",
      "PROJECTS",
      "TASKS",
      "CRM",
      "FINANCE",
      "DOCUMENTS",
      "REPORTS",
      "NOTIFICATIONS",
      "WHITE_LABEL",
      "API_ACCESS",
      "AI_FEATURES",
    ],
    limits: {
      MAX_EMPLOYEES: null,
      MAX_CLIENTS: null,
      MAX_PROJECTS: null,
      MAX_STORAGE_GB: null,
    },
  },
] as const;

async function main() {
  await prisma.$transaction(async (transaction) => {
    for (const role of roles) {
      await transaction.role.upsert({
        where: { code: role.code },
        update: { name: role.name, isSystem: true },
        create: { ...role, isSystem: true },
      });
    }

    for (const module of modules) {
      await transaction.module.upsert({
        where: { code: module.code },
        update: { name: module.name },
        create: module,
      });
    }

    for (const permission of permissions) {
      await transaction.permission.upsert({
        where: { code: permission.code },
        update: { name: permission.name },
        create: permission,
      });
    }

    const roleRecords = await transaction.role.findMany();
    const moduleRecords = await transaction.module.findMany();
    const permissionRecords = await transaction.permission.findMany();
    const roleIds = new Map(roleRecords.map((role) => [role.code, role.id]));
    const moduleIds = new Map(
      moduleRecords.map((module) => [module.code, module.id]),
    );
    const permissionIds = new Map(
      permissionRecords.map((permission) => [permission.code, permission.id]),
    );

    for (const [roleCode, modulePermissions] of Object.entries(
      permissionMatrix,
    )) {
      for (const [moduleCode, actionCodes] of Object.entries(
        modulePermissions,
      )) {
        for (const actionCode of actionCodes) {
          const roleId = roleIds.get(roleCode);
          const moduleId = moduleIds.get(moduleCode);
          const permissionId = permissionIds.get(actionCode);
          if (!roleId || !moduleId || !permissionId)
            throw new Error("Invalid RBAC seed mapping");

          await transaction.rolePermission.upsert({
            where: {
              roleId_moduleId_permissionId: { roleId, moduleId, permissionId },
            },
            update: {},
            create: { roleId, moduleId, permissionId },
          });
        }
      }
    }

    for (const plan of subscriptionPlans) {
      const record = await transaction.subscriptionPlan.upsert({
        where: { code: plan.code },
        update: {
          name: plan.name,
          description: plan.description,
          monthlyPrice: plan.monthlyPrice,
          yearlyPrice: plan.yearlyPrice,
          displayOrder: plan.displayOrder,
        },
        create: {
          name: plan.name,
          code: plan.code,
          description: plan.description,
          monthlyPrice: plan.monthlyPrice,
          yearlyPrice: plan.yearlyPrice,
          displayOrder: plan.displayOrder,
        },
      });
      await transaction.subscriptionPlanFeature.deleteMany({
        where: { planId: record.id },
      });
      await transaction.subscriptionPlanLimit.deleteMany({
        where: { planId: record.id },
      });
      await transaction.subscriptionPlanFeature.createMany({
        data: plan.features.map((featureCode) => ({
          planId: record.id,
          featureCode,
          enabled: true,
        })),
      });
      await transaction.subscriptionPlanLimit.createMany({
        data: Object.entries(plan.limits).map(([limitCode, value]) => ({
          planId: record.id,
          limitCode,
          value: value === null ? null : BigInt(value),
        })),
      });
    }

    if (process.env.NODE_ENV !== "production") {
      const demoCompany = await transaction.company.findFirst({
        where: { code: "TEST_COMPANY" },
      });
      if (demoCompany) {
        for (const name of [
          "Engineering",
          "Human Resources",
          "Finance",
          "Sales",
        ]) {
          await transaction.department.upsert({
            where: { companyId_name: { companyId: demoCompany.id, name } },
            update: {},
            create: {
              companyId: demoCompany.id,
              name,
              description: `${name} department`,
            },
          });
        }
        for (const branch of [
          {
            name: "Hyderabad",
            code: "HYD",
            city: "Hyderabad",
            state: "Telangana",
          },
          {
            name: "Bangalore",
            code: "BLR",
            city: "Bangalore",
            state: "Karnataka",
          },
          {
            name: "Chennai",
            code: "CHE",
            city: "Chennai",
            state: "Tamil Nadu",
          },
        ]) {
          await transaction.branch.upsert({
            where: {
              companyId_code: { companyId: demoCompany.id, code: branch.code },
            },
            update: {},
            create: { companyId: demoCompany.id, country: "India", ...branch },
          });
        }
      }
    }
  });
}

main()
  .finally(async () => prisma.$disconnect())
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
