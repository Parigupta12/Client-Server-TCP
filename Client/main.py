from Client.network import NetworkClient
import time


def display_message(message):
    """Display parsed messages received from the server."""
    print()
    print(f"[MESSAGE] {message}")
    print("[YOU] ", end="", flush=True)


def main():
    client = NetworkClient()

    # Connect to server
    if not client.connect():
        print("[ERROR] Could not connect to server.")
        print("[INFO] Make sure the C server is running.")
        return

    # Display parsed incoming messages
    client.message_received.connect(display_message)

    print()
    print("[INFO] Waiting for Client ID...")

    timeout = 5
    start_time = time.time()

    while client.client_id is None:
        if time.time() - start_time > timeout:
            print("[WARNING] Client ID was not received.")
            break

        time.sleep(0.05)

    if client.client_id is not None:
        print()
        print("----------------------------------------")
        print(f"[CONNECTED] You are Client {client.client_id}")
        print("----------------------------------------")

    print()
    print("Available commands:")
    print("  /broadcast <message>")
    print("  /private <client_id> <message>")
    print("  exit")
    print()
    print("Plain text messages are also sent as broadcast.")
    print()

    try:
        while client.connected:

            message = input("[YOU] ").strip()

            if not message:
                continue

            # Exit
            if message.lower() == "exit":
                print("[INFO] Disconnecting...")
                break

            # Private message
            if message.startswith("/private "):
                parts = message.split(" ", 2)

                if len(parts) < 3:
                    print("[ERROR] Usage: /private <client_id> <message>")
                    continue

                try:
                    target_id = int(parts[1])
                except ValueError:
                    print("[ERROR] Client ID must be a number.")
                    continue

                private_message = parts[2]

                success = client.send_private_message(
                    target_id,
                    private_message
                )

                if not success:
                    print("[ERROR] Private message could not be sent.")

                continue

            # Explicit broadcast
            if message.startswith("/broadcast "):
                broadcast_message = message[len("/broadcast "):]

                if not broadcast_message.strip():
                    print("[ERROR] Broadcast message cannot be empty.")
                    continue

                success = client.send_broadcast_message(
                    broadcast_message
                )

                if not success:
                    print("[ERROR] Broadcast message could not be sent.")

                continue

            # Plain text -> broadcast
            success = client.send_broadcast_message(message)

            if not success:
                print("[ERROR] Message could not be sent.")
                break

    except KeyboardInterrupt:
        print("\n[INFO] Client interrupted.")

    except Exception as error:
        print(f"\n[ERROR] {error}")

    finally:
        client.disconnect()
        print("[CLIENT] Connection closed.")


if __name__ == "__main__":
    main()