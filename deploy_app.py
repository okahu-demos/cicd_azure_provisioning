import os
import sys

LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")


def read_log(filename):
    path = os.path.join(LOGS_DIR, filename)
    with open(path) as f:
        return f.read()


def deploy_azure_blob(account_name, resource_group, location):
    log = read_log("step1_blob_deploy.log")
    print(log)
    print("Azure Blob is deployed successfully")
    return {"status": "success", "message": "Azure Blob is deployed successfully", "log": log}


class AzureSQLDeploy:
    def deploy(self, server_name, database_name, resource_group):
        log = read_log("step2_sql_deploy.log")
        print(log)
        print("Azure SQL database deployed successfully")
        return {"status": "success", "message": "Azure SQL database deployed successfully", "log": log}


class KustoDeploy:
    def deploy_tables(self, cluster_name, database_name, tables):
        log = read_log("step3_kusto_deploy.log")
        print(log)
        tables_created = ["SpanEvents", "DeploymentEvents"]
        missing = [t for t in tables if t not in tables_created]
        print("Kusto script provisioningState: Succeeded")
        print(f"  Tables found:   {tables_created}")
        print(f"  Tables missing: {missing}")
        if missing:
            print(f"  ERROR: {len(missing)} table(s) failed to create")
            raise RuntimeError(f"Kusto table creation incomplete. Missing tables: {missing}")
        return {"status": "success", "tables": tables_created, "missing": missing, "log": log}


class UserAccountProvision:
    def create_accounts(self, display_name, principal_name, role):
        log = read_log("step4_user_provision.log")
        print(log)

        # Check if the log contains authorization error
        if "Authorization_RequestDenied" in log or "Insufficient privileges" in log:
            error_msg = (
                "\nRESOLUTION REQUIRED: The service principal lacks Microsoft Entra ID directory roles.\n"
                "\nTo fix this issue, a Global Administrator must assign the appropriate directory role:\n"
                "\n  Option 1: Assign 'User Administrator' role (recommended for least privilege)\n"
                "    az rest --method POST \\\n"
                "      --uri 'https://graph.microsoft.com/v1.0/servicePrincipals/{servicePrincipalId}/appRoleAssignments' \\\n"
                "      --body '{\"principalId\":\"<servicePrincipalId>\",\"resourceId\":\"<microsoftGraphId>\",\"appRoleId\":\"fe930be7-5e62-47db-91af-98c3a49a38b1\"}'\n"
                "\n  Option 2: Use Azure CLI (requires Global Administrator access)\n"
                "    1. Get the service principal object ID:\n"
                "       az ad sp show --id ci-deployer@okahu.onmicrosoft.com --query id -o tsv\n"
                "    2. Assign User Administrator role via Azure Portal:\n"
                "       - Navigate to: Entra ID > Roles and administrators > User Administrator\n"
                "       - Click 'Add assignments' and select the service principal\n"
                "\n  Option 3: Alternative approach - Skip user provisioning in CI/CD\n"
                "    - Provision user accounts manually or via separate privileged workflow\n"
                "    - Comment out Step 4 in deploy_app.py for automated deployments\n"
                "\nDocumentation: https://learn.microsoft.com/en-us/entra/identity/role-based-access-control/permissions-reference#user-administrator"
            )
            raise RuntimeError(f"User account creation failed - Authorization denied\n{error_msg}")

        raise RuntimeError("User account creation failed")


def main():
    print("=" * 60)
    print("CI/CD Deployment Pipeline")
    print("=" * 60)

    # Step 1: Azure Blob
    print("\n--- Step 1: Azure Blob Storage ---")
    deploy_azure_blob("oklogstorage2026", "rg-okahu-prod-eastus", "eastus")

    # Step 2: Azure SQL
    print("\n--- Step 2: Azure SQL Database ---")
    sql_deploy = AzureSQLDeploy()
    sql_deploy.deploy("okahu-sql-prod", "okahu-traces-db", "rg-okahu-prod-eastus")

    # Step 3: Kusto (silent failure)
    print("\n--- Step 3: Kusto Tables ---")
    kusto_deploy = KustoDeploy()
    try:
        result = kusto_deploy.deploy_tables("okahu-adx-analytics", "TracesDB", ["SpanEvents", "MetricAggregates", "DeploymentEvents"])
    except RuntimeError as e:
        print(f"  ERROR: {e}")
        print("\n" + "=" * 60)
        print("Pipeline FAILED at Step 3")
        print("=" * 60)
        sys.exit(1)

    # Step 4: User accounts (hard failure)
    print("\n--- Step 4: User Account Provisioning ---")
    provision = UserAccountProvision()
    try:
        provision.create_accounts("svc-pipeline-runner", "svc-pipeline-runner@okahu.onmicrosoft.com", "User Administrator")
    except RuntimeError as e:
        print(f"  ERROR: {e}")
        print("\n" + "=" * 60)
        print("Pipeline FAILED at Step 4")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
