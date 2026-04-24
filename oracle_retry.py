import oci
import os
import sys
import time
from datetime import datetime

# ================================================================
# Values come from GitHub Secrets — no hardcoding needed
# ================================================================

USER_OCID      = os.environ["USER_OCID"]
FINGERPRINT    = os.environ["FINGERPRINT"]
TENANCY_OCID   = os.environ["TENANCY_OCID"]
COMPARTMENT_ID = os.environ["COMPARTMENT_ID"]
SUBNET_ID      = os.environ["SUBNET_ID"]
IMAGE_ID       = os.environ["IMAGE_ID"]
SSH_PUBLIC_KEY = os.environ["SSH_PUBLIC_KEY"]
KEY_FILE       = os.path.expanduser("~/.oci/oci_api_key.pem")
REGION         = "ap-mumbai-1"

# All 3 ADs — tries each one automatically
AVAILABILITY_DOMAINS = [
    "GrCH:AP-MUMBAI-1-AD-1",
    "GrCH:AP-MUMBAI-1-AD-2",
    "GrCH:AP-MUMBAI-1-AD-3",
]

config = {
    "user":        USER_OCID,
    "key_file":    KEY_FILE,
    "fingerprint": FINGERPRINT,
    "tenancy":     TENANCY_OCID,
    "region":      REGION,
}

def print_banner():
    print("\n" + "="*60)
    print("  CoreCompass — Oracle A1.Flex GitHub Actions Retry")
    print("="*60)
    print(f"  Region : {REGION}")
    print(f"  Shape  : VM.Standard.A1.Flex (4 OCPU / 24 GB)")
    print(f"  Time   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("="*60 + "\n")

def test_connection(compute):
    print("Testing OCI connection...", end=" ", flush=True)
    try:
        compute.list_shapes(COMPARTMENT_ID)
        print("✅ Connected!\n")
        return True
    except oci.exceptions.ServiceError as e:
        print(f"\n❌ Connection failed!")
        msg = str(e)
        if "401" in msg or "NotAuthenticated" in msg:
            print("   → Check FINGERPRINT and OCI_PRIVATE_KEY secrets")
        elif "NotAuthorizedOrNotFound" in msg:
            print("   → Check USER_OCID and TENANCY_OCID secrets")
        else:
            print(f"   → {msg[:200]}")
        return False

def build_instance_details(availability_domain):
    return oci.core.models.LaunchInstanceDetails(
        availability_domain = availability_domain,
        compartment_id      = COMPARTMENT_ID,
        display_name        = "corecompass-prod",
        shape               = "VM.Standard.A1.Flex",
        shape_config        = oci.core.models.LaunchInstanceShapeConfigDetails(
            ocpus         = 4,
            memory_in_gbs = 24,
        ),
        source_details = oci.core.models.InstanceSourceViaImageDetails(
            image_id    = IMAGE_ID,
            source_type = "image",
        ),
        # Uses YOUR existing VCN subnet
        create_vnic_details = oci.core.models.CreateVnicDetails(
            subnet_id        = SUBNET_ID,
            assign_public_ip = True,
            display_name     = "corecompass-vnic",
            hostname_label   = "corecompass-prod",
        ),
        metadata = {
            "ssh_authorized_keys": SSH_PUBLIC_KEY,
        },
    )

def print_success(instance):
    print("\n" + "="*60)
    print("  🎉🎉🎉  INSTANCE CREATED SUCCESSFULLY!  🎉🎉🎉")
    print("="*60)
    print(f"  Name   : {instance.display_name}")
    print(f"  OCID   : {instance.id}")
    print(f"  AD     : {instance.availability_domain}")
    print(f"  Status : {instance.lifecycle_state}")
    print("="*60)
    print("\n  Next Steps:")
    print("  1. Go to Oracle Console → Compute → Instances")
    print("  2. Find 'corecompass-prod' → wait for RUNNING status")
    print("  3. Copy the Public IP Address")
    print("  4. SSH: ssh -i your-key.pem ubuntu@<PUBLIC_IP>")
    print("  5. Run: docker compose up --build -d")
    print("="*60 + "\n")

def main():
    print_banner()

    # Init OCI compute client
    try:
        compute = oci.compute.ComputeClient(config)
    except Exception as e:
        print(f"❌ Failed to init OCI client: {e}")
        sys.exit(1)

    # Test connection first
    if not test_connection(compute):
        sys.exit(1)

    # Try all 3 ADs once per GitHub Actions run
    # (GitHub Actions runs every 10 minutes, so we try 3 ADs per run)
    print("Trying all Availability Domains this run:\n")

    for i, ad in enumerate(AVAILABILITY_DOMAINS, 1):
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] Try {i}/3 → {ad}", end="  ", flush=True)

        instance_details = build_instance_details(ad)

        try:
            response = compute.launch_instance(instance_details)
            print("✅ SUCCESS!")
            print_success(response.data)
            sys.exit(0)  # Exit success — GitHub Actions marks run as ✅

        except oci.exceptions.ServiceError as e:
            msg = str(e)

            if any(x in msg for x in ["Out of host capacity", "InternalError", "capacity"]):
                print("❌ No capacity")
                if i < 3:
                    time.sleep(5)  # small pause between ADs
                continue

            elif "LimitExceeded" in msg:
                print(f"\n⛔ Free tier limit reached!")
                print("   You may already have an A1.Flex instance running.")
                print("   Check Oracle Console → Compute → Instances")
                sys.exit(0)  # Not an error, instance probably exists

            elif "Conflict" in msg or "already exists" in msg.lower():
                print(f"\n⚠️  Instance 'corecompass-prod' already exists!")
                print("   Check Oracle Console → Compute → Instances")
                sys.exit(0)

            elif "NotAuthorizedOrNotFound" in msg:
                print(f"\n⛔ Auth error — check your GitHub Secrets")
                print(f"   {msg[:200]}")
                sys.exit(1)

            elif "InvalidParameter" in msg:
                print(f"\n⛔ Bad config — check IMAGE_ID or SUBNET_ID secret")
                print(f"   {msg[:200]}")
                sys.exit(1)

            else:
                print(f"⚠️  {msg[:100]}")
                continue

        except Exception as e:
            print(f"⚠️  {str(e)[:100]}")
            continue

    # All 3 ADs tried — no capacity this run
    print("\n" + "-"*60)
    print("  All 3 ADs are at capacity right now.")
    print("  GitHub Actions will retry automatically in 10 minutes.")
    print(f"  Next attempt: ~{datetime.now().strftime('%H:%M')} + 10 min")
    print("-"*60 + "\n")
    sys.exit(0)  # Exit success — workflow will retry on next schedule

if __name__ == "__main__":
    main()
