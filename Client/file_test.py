from Client.network import NetworkClient


client = NetworkClient()

if not client.connect():
    print("[ERROR] Could not connect to server.")
    raise SystemExit(1)


print()
print("========================================")
print("       FILE SENDER TEST CLIENT")
print("========================================")
print()
print("Waiting for Client ID...")


# Wait until the server assigns an ID
while client.client_id is None:
    pass


print()
print(f"[OK] This client is Client {client.client_id}")
print()

target_id = input("Enter receiver Client ID: ").strip()
file_path = input("Enter file path: ").strip()

print()
print("[INFO] Starting file transfer...")

success = client.send_file(
    int(target_id),
    file_path
)

print()

if success:
    print("[SUCCESS] File data sent.")
else:
    print("[FAILED] File transfer failed.")

input("\nPress Enter to exit...")

client.disconnect()