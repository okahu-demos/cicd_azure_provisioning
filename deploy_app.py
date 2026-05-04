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
        print("Azure SQL is deployed successfully")
        return {"status": "success", "message": "Azure SQL is deployed successfully", "log": log}


class KustoDeploy:
    def deploy_tables(self, cluster_name, database_name, tables):
        log = read_log("step3_kusto_deploy.log")
        print(log)
        tables_created = ["table1", "table3"]
        missing = [t for t in tables if t not in tables_created]
        print("Kusto deployment success but table creation failed")
        print(f"  Created: {tables_created}")
        print(f"  Missing: {missing}")
        return {"status": "partial", "tables": tables_created, "missing": missing, "log": log}


class UserAccountProvision:
    def create_accounts(self, display_name, principal_name, role):
        log = read_log("step4_user_provision.log")
        print(log)
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
    result = kusto_deploy.deploy_tables("okahu-adx-analytics", "TracesDB", ["table1", "table2", "table3"])
    if result["missing"]:
        print(f"  WARNING: {len(result['missing'])} table(s) missing but deployment marked success")

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
