import socket
import threading
import time
import os
import argparse
import shutil
import tempfile


BROADCAST_PORT = 50000
TRANSFER_PORT = 50001
BROADCAST_INTERVAL = 2
BUFFER_SIZE = 4096


receiver_connected = threading.Event()

def broadcast_ip(broadcast_timeout):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    s.settimeout(BROADCAST_INTERVAL)
    
    # Try to get a non-loopback IP if possible, otherwise fallback
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if ip.startswith("127."):
            s_temp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s_temp.connect(("8.8.8.8", 80)) # Connect to a known address
            ip = s_temp.getsockname()[0]
            s_temp.close()
    except socket.gaierror:
        ip = "127.0.0.1"
    
    message = f"FILE_SENDER:{ip}:{TRANSFER_PORT}".encode()
    start_time = time.time()

    print(f"Broadcasting IP {ip} for file sender...")
    while not receiver_connected.is_set() and time.time() - start_time < broadcast_timeout:
        try:
            s.sendto(message, ("<broadcast>", BROADCAST_PORT))
        except socket.timeout:
            pass
        except Exception as e:
            print(f"Broadcast send error: {e}")
        
        for _ in range(BROADCAST_INTERVAL * 4):
            if receiver_connected.is_set():
                break
            time.sleep(0.25)
        if receiver_connected.is_set():
            break


    s.close()
    if not receiver_connected.is_set():
        print("Broadcast timed out.")
    else:
        print("Stopped broadcasting.")

def handle_client(conn, path_to_send_on_disk, name_to_send_over_network, type_indicator):
    try:
        filesize = os.path.getsize(path_to_send_on_disk)

        conn.sendall(type_indicator + name_to_send_over_network.encode() + b"\n")
        conn.sendall(f"{filesize}".encode() + b"\n")

        with open(path_to_send_on_disk, 'rb') as f:
            while True:
                chunk = f.read(BUFFER_SIZE)
                if not chunk:
                    break
                conn.sendall(chunk)
        print(f"Sent: {name_to_send_over_network}")

    except Exception as e:
        error_message = f"ERROR:{str(e)}"
        try:
            conn.sendall(error_message.encode())
        except Exception as send_err:
            print(f"Failed to send error to client: {send_err}")
        print(f"Error sending file/folder: {e}")
    finally:
        conn.close()

def send_file(filepath, broadcast_timeout=300):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File or folder not found: {filepath}")
    
    receiver_connected.clear()

    is_folder = os.path.isdir(filepath)
    temp_zip_created_dir = None
    path_to_send_on_disk = filepath
    original_name = os.path.basename(filepath)
    if not original_name:
        original_name = os.path.basename(os.path.abspath(filepath))


    if is_folder:
        file_type_indicator = b"FOLDER:"
        name_to_send_over_network = f"{original_name}.zip"
        temp_zip_created_dir = tempfile.mkdtemp()
        zip_base_name = os.path.join(temp_zip_created_dir, original_name)
        
        print(f"Zipping folder: {filepath} ...")
        try:
            path_to_send_on_disk = shutil.make_archive(
                base_name=zip_base_name,
                format='zip',
                root_dir=os.path.dirname(filepath) or '.', # Parent dir of item to zip
                base_dir=original_name # Item to zip
            )
            print(f"Zipped to: {path_to_send_on_disk}")
        except Exception as e:
            if temp_zip_created_dir and os.path.exists(temp_zip_created_dir):
                shutil.rmtree(temp_zip_created_dir)
            raise RuntimeError(f"Error zipping folder '{filepath}': {e}")
    else:
        file_type_indicator = b"FILE:"
        name_to_send_over_network = original_name

    broadcast_thread = threading.Thread(target=broadcast_ip, args=(broadcast_timeout,), daemon=True)
    broadcast_thread.start()

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind(("0.0.0.0", TRANSFER_PORT))
            server.listen(1)
            server.settimeout(broadcast_timeout + 5)

            print(f"Waiting for connection on port {TRANSFER_PORT}...")
            try:
                conn, addr = server.accept()
            except socket.timeout:
                print("No receiver connected within timeout.")
                receiver_connected.set()
                broadcast_thread.join()
                return

            print(f"Receiver connected from {addr}")
            receiver_connected.set()
            broadcast_thread.join()

            handle_client(conn, path_to_send_on_disk, name_to_send_over_network, file_type_indicator)
            print("Transfer complete.")

    except Exception as e:
        print(f"An error occurred during sending: {e}")
        receiver_connected.set()
        if broadcast_thread.is_alive():
            broadcast_thread.join()
    finally:
        if temp_zip_created_dir and os.path.exists(temp_zip_created_dir):
            shutil.rmtree(temp_zip_created_dir)
            print(f"Cleaned up temporary zip directory: {temp_zip_created_dir}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Send a file or folder to a receiver via socket.')
    parser.add_argument('filepath', type=str, help='Full path to the file or folder to be sent.')
    parser.add_argument('--broadcast_timeout', '-t', type=int, default=300, help='Timeout for broadcasting in seconds.')
    args = parser.parse_args()
    
    clean_filepath = args.filepath.replace('"', '').replace("'", "").strip()
    
    try:
        send_file(clean_filepath, args.broadcast_timeout)
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except RuntimeError as e:
        print(f"Runtime Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")