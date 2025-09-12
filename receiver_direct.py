import socket
import os
import shutil
import tempfile
import zipfile
import argparse

BUFFER_SIZE = 4096
SAVE_DIR = "sharepoint"


def cleanup_files():
    if os.path.exists(SAVE_DIR):
        for itemname in os.listdir(SAVE_DIR):
            item_path = os.path.join(SAVE_DIR, itemname)
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)


def receive_file(ip, port):
    os.makedirs(SAVE_DIR, exist_ok=True)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        print(f"Connecting to sender {ip}:{port} ...")
        s.connect((ip, port))

        header_line = b""
        while not header_line.endswith(b"\n"):
            chunk = s.recv(1)
            if not chunk:
                raise ConnectionAbortedError("Connection closed by sender while receiving header.")
            header_line += chunk

        header_line_str = header_line.strip().decode()

        is_folder = False
        received_filename_on_network = ""
        if header_line_str.startswith("FOLDER:"):
            is_folder = True
            received_filename_on_network = header_line_str[len("FOLDER:"):]
        elif header_line_str.startswith("FILE:"):
            is_folder = False
            received_filename_on_network = header_line_str[len("FILE:"):]
        else:
            raise ValueError(f"Invalid header received from sender: {header_line_str}")

        filesize_str = b""
        while not filesize_str.endswith(b"\n"):
            chunk = s.recv(1)
            if not chunk:
                raise ConnectionAbortedError("Connection closed by sender while receiving filesize.")
            filesize_str += chunk

        filesize = int(filesize_str.strip())
        download_target_path = os.path.join(SAVE_DIR, received_filename_on_network)

        temp_file_path = None
        with tempfile.NamedTemporaryFile(delete=False, dir=SAVE_DIR, prefix="recv_temp_") as temp_file:
            temp_file_path = temp_file.name
            bytes_received = 0
            while bytes_received < filesize:
                chunk = s.recv(min(BUFFER_SIZE, filesize - bytes_received))
                if not chunk:
                    raise ConnectionAbortedError("Connection broken during file transfer.")
                if bytes_received == 0 and chunk.startswith(b"ERROR:"):
                    raise RuntimeError(f"Sender error: {chunk.decode(errors='ignore')[6:]}")
                temp_file.write(chunk)
                bytes_received += len(chunk)

        if os.path.exists(download_target_path):
            if os.path.isdir(download_target_path):
                shutil.rmtree(download_target_path)
            else:
                os.remove(download_target_path)
        shutil.move(temp_file_path, download_target_path)

        if is_folder:
            extracted_folder_name = os.path.splitext(received_filename_on_network)[0]
            final_folder_destination = os.path.join(SAVE_DIR, extracted_folder_name)

            if os.path.exists(final_folder_destination):
                shutil.rmtree(final_folder_destination)

            with zipfile.ZipFile(download_target_path, 'r') as zip_ref:
                zip_ref.extractall(SAVE_DIR)

            os.remove(download_target_path)
            print(f"Received folder: {extracted_folder_name}")
        else:
            print(f"Received file: {received_filename_on_network}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Receive a file from a sender directly by IP.")
    parser.add_argument('--ip', type=str, required=True, help='IP address of the sender.')
    parser.add_argument('--port', type=int, default=40001, help='Port of the sender (default 40001).')
    args = parser.parse_args()

    receive_file(args.ip, args.port)
