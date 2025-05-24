import socket
import os
import shutil
import tempfile
import zipfile


BROADCAST_PORT = 50000
BUFFER_SIZE = 4096
RECEIVE_TIMEOUT = 60  # seconds for discovering sender
SAVE_DIR = "sharepoint"


def cleanup_files():
    if os.path.exists(SAVE_DIR):
        removed_items = []
        for itemname in os.listdir(SAVE_DIR):
            item_path = os.path.join(SAVE_DIR, itemname)
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.remove(item_path)
                removed_items.append(itemname)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
                removed_items.append(itemname + "/")


def discover_sender():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("", BROADCAST_PORT))
    except OSError as e:
        raise OSError(f"Error binding to broadcast port {BROADCAST_PORT}: {e}. Another application might be using this port.")
        
    s.settimeout(RECEIVE_TIMEOUT)

    try:
        while True: 
            data, addr = s.recvfrom(1024)
            if data.startswith(b"FILE_SENDER"):
                parts = data.decode().split(":")
                if len(parts) == 3:
                    sender_ip = parts[1]
                    sender_port = int(parts[2])
                    return sender_ip, sender_port
                else:
                    raise ValueError(f"Received malformed broadcast from {addr}: {data.decode()}")
    except socket.timeout:
        raise socket.timeout(f"No sender found within the {RECEIVE_TIMEOUT} second timeout period.")
    except Exception as e:
        raise RuntimeError(f"Error during sender discovery: {e}")
    finally:
        s.close()

def receive_file(ip, port):
    os.makedirs(SAVE_DIR, exist_ok=True)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((ip, port))
        except ConnectionRefusedError:
            raise ConnectionRefusedError(f"Connection refused by sender at {ip}:{port}. Ensure sender is ready.")
        except socket.timeout: 
            raise socket.timeout(f"Connection to sender {ip}:{port} timed out.")
        except Exception as e:
            raise RuntimeError(f"Error connecting to sender: {e}")

        header_line = b""
        try:
            while not header_line.endswith(b"\n"):
                chunk = s.recv(1) 
                if not chunk:
                    raise ConnectionAbortedError("Connection closed by sender while receiving header.")
                header_line += chunk
        except ConnectionAbortedError as e:
            raise
        except Exception as e:
            raise RuntimeError(f"Error receiving header: {e}")
            
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
        try:
            while not filesize_str.endswith(b"\n"):
                chunk = s.recv(1)
                if not chunk:
                    raise ConnectionAbortedError("Connection closed by sender while receiving filesize.")
                filesize_str += chunk
        except ConnectionAbortedError as e:
            raise
        except Exception as e:
            raise RuntimeError(f"Error receiving filesize: {e}")

        try:
            filesize = int(filesize_str.strip())
        except ValueError:
            raise ValueError(f"Invalid filesize received: {filesize_str.strip().decode()}")

        download_target_path = os.path.join(SAVE_DIR, received_filename_on_network)
        
        temp_file_path = None
        try:
            # Create temp file in SAVE_DIR to ensure it's on the same filesystem for atomic move
            with tempfile.NamedTemporaryFile(delete=False, dir=SAVE_DIR, prefix="recv_temp_") as temp_file:
                temp_file_path = temp_file.name
                bytes_received = 0
                while bytes_received < filesize:
                    bytes_to_read = min(BUFFER_SIZE, filesize - bytes_received)
                    chunk = s.recv(bytes_to_read)
                    if not chunk: 
                        raise ConnectionAbortedError("Connection broken during file transfer.")
                    
                    if bytes_received == 0 and chunk.startswith(b"ERROR:"):
                         raise RuntimeError(f"Sender error: {chunk.decode(errors='ignore')[6:]}")
                    
                    temp_file.write(chunk)
                    bytes_received += len(chunk)
            
            if os.path.exists(download_target_path): 
                if os.path.isdir(download_target_path): shutil.rmtree(download_target_path)
                else: os.remove(download_target_path)
            shutil.move(temp_file_path, download_target_path)
            temp_file_path = None 

            output_name = ""
            if is_folder:
                extracted_folder_name = os.path.splitext(received_filename_on_network)[0] 
                final_folder_destination = os.path.join(SAVE_DIR, extracted_folder_name)

                if os.path.exists(final_folder_destination):
                    shutil.rmtree(final_folder_destination)
                
                try:
                    with zipfile.ZipFile(download_target_path, 'r') as zip_ref:
                        zip_ref.extractall(SAVE_DIR) 
                    output_name = extracted_folder_name
                except zipfile.BadZipFile as e:
                    if os.path.exists(final_folder_destination): 
                        shutil.rmtree(final_folder_destination)
                    raise RuntimeError(f"Failed to unzip: Bad zip file. {e}. File: {download_target_path}")
                except Exception as e:
                    if os.path.exists(final_folder_destination): 
                        shutil.rmtree(final_folder_destination)
                    raise RuntimeError(f"Failed to unzip: {e}. File: {download_target_path}")
                finally:
                    if os.path.exists(download_target_path): 
                        os.remove(download_target_path)
            else:
                output_name = received_filename_on_network
            
            print(output_name)

        except ConnectionAbortedError as e:
            raise RuntimeError(f"Transfer failed: {e}")
        except RuntimeError as e: 
            raise
        except Exception as e:
            raise RuntimeError(f"An error occurred during reception: {e}")
        finally:
            if temp_file_path and os.path.exists(temp_file_path): 
                os.remove(temp_file_path)


if __name__ == '__main__':
    # cleanup_files()
    
    sender_ip, sender_port = discover_sender()
    
    receive_file(sender_ip, sender_port)
