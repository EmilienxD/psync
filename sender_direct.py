import socket
import os
import argparse
import shutil
import tempfile

TRANSFER_PORT = 40001
BUFFER_SIZE = 4096


def get_local_ip():
    """Try to get a LAN IP (not loopback)."""
    ip = "127.0.0.1"
    try:
        s_temp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s_temp.connect(("8.8.8.8", 80))  # Google's DNS (no packets actually sent)
        ip = s_temp.getsockname()[0]
        s_temp.close()
    except Exception:
        pass
    return ip


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
        try:
            conn.sendall(f"ERROR:{str(e)}".encode())
        except Exception:
            pass
        print(f"Error sending file/folder: {e}")
    finally:
        conn.close()


def send_file(filepath):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File or folder not found: {filepath}")

    is_folder = os.path.isdir(filepath)
    temp_zip_created_dir = None
    path_to_send_on_disk = filepath
    original_name = os.path.basename(filepath) or os.path.basename(os.path.abspath(filepath))

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
                root_dir=os.path.dirname(filepath) or '.',
                base_dir=original_name
            )
            print(f"Zipped to: {path_to_send_on_disk}")
        except Exception as e:
            if temp_zip_created_dir and os.path.exists(temp_zip_created_dir):
                shutil.rmtree(temp_zip_created_dir)
            raise RuntimeError(f"Error zipping folder '{filepath}': {e}")
    else:
        file_type_indicator = b"FILE:"
        name_to_send_over_network = original_name

    local_ip = get_local_ip()
    print(f"Sender running. Provide this IP to the receiver: {local_ip}")
    print(f"Waiting for connection on {local_ip}:{TRANSFER_PORT} ...")

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind((local_ip, TRANSFER_PORT))
            server.listen(1)
            conn, addr = server.accept()
            print(f"Receiver connected from {addr}")
            handle_client(conn, path_to_send_on_disk, name_to_send_over_network, file_type_indicator)
            print("Transfer complete.")
    finally:
        if temp_zip_created_dir and os.path.exists(temp_zip_created_dir):
            shutil.rmtree(temp_zip_created_dir)
            print(f"Cleaned up temporary zip directory: {temp_zip_created_dir}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Send a file or folder to a receiver via socket.')
    parser.add_argument('filepath', type=str, help='Full path to the file or folder to be sent.')
    args = parser.parse_args()

    clean_filepath = args.filepath.replace('"', '').replace("'", "").strip()

    try:
        send_file(clean_filepath)
    except Exception as e:
        print(f"Error: {e}")
