# Python Local Network File & Folder Transfer

A simple Python-based solution for transferring files and folders between devices on the same local network. It consists of a sender script (`sender.py`) to initiate the transfer from a PC (or any device running Python) and a receiver script (`receiver.py`) designed to run on another device, with specific compatibility for Apple Shortcuts on iOS/iPadOS.

## Features

*   **Transfer Individual Files:** Send any single file.
*   **Transfer Entire Folders:** Automatically zips the folder on the sender's side and unzips it on the receiver's side.
*   **Local Network Discovery:** The sender broadcasts its availability via UDP, allowing the receiver to discover it automatically.
*   **Reliable Transfer:** Uses TCP for the actual file/folder data transfer.
*   **Apple Shortcuts Compatible Receiver:** `receiver.py` is tailored for use with Apple Shortcuts:
    *   On successful reception, it prints **only** the name of the received file or the extracted folder to standard output.
    *   On any error, it raises a Python exception, which signals failure to Apple Shortcuts.
*   **Configurable Broadcast Timeout:** The sender has an optional timeout for how long it will broadcast its presence.
*   **Organized Storage:** Received files and folders are saved into a `sharepoint` directory created by the receiver.

## Requirements

*   Python 3.x (uses only standard libraries: `socket`, `threading`, `time`, `os`, `argparse`, `shutil`, `tempfile`, `zipfile`).
*   Two devices on the same local network (e.g., connected to the same Wi-Fi router).
*   Firewall on both devices configured to allow:
    *   UDP traffic on port `50000` (for broadcast discovery).
    *   TCP traffic on port `50001` (for file transfer).
*   For Apple Shortcuts integration on iOS/iPadOS: A Python environment app that can run Python scripts and be called by Shortcuts (e.g., Pyto, a-Shell, Scriptable with Python support).

## Setup

1.  **Download Scripts:**
    *   Place `sender.py` on the machine you want to send files/folders *from*.
    *   Place `receiver.py` on the machine you want to send files/folders *to*.
        *   For Apple Shortcuts: Save `receiver.py` to a location accessible by the Shortcuts app (e.g., in the `iCloud Drive/Shortcuts/` folder, or a folder specific to your Python environment app like Pyto).

2.  **Python Installation:** Ensure Python 3 is installed on both devices.

3.  **(Optional) `_core.py`:** The scripts include a `try-except` block for importing `_core`. If this file contains custom configurations or utilities specific to your environment, ensure it's available in the Python path or the same directory as the scripts. For general use, it can be ignored if not present.

## Usage

### Sender (`sender.py`)

1.  Open a terminal or command prompt on the sending machine.
2.  Navigate to the directory where `sender.py` is located.
3.  Run the script with the full path to the file or folder you want to send:

    ```bash
    python sender.py "/path/to/your/file_or_folder_to_send"
    ```
    *   **Example (File):** `python sender.py "/Users/Me/Documents/report.pdf"`
    *   **Example (Folder):** `python sender.py "/Users/Me/Pictures/Vacation Photos"`
        *(The script handles removing surrounding quotes if paths are dragged and dropped into some terminals)*

4.  **Optional Broadcast Timeout:**
    You can specify how long the sender should broadcast its IP before giving up if no receiver connects (default is 300 seconds):

    ```bash
    python sender.py "/path/to/your/file_or_folder" -t 60
    ```
    This will broadcast for 60 seconds.

5.  The sender will start broadcasting its IP and wait for a receiver to connect. Once connected, it will send the file/folder.

### Receiver (`receiver.py`)

**Option 1: Running directly (e.g., on a PC/Mac/Linux for testing)**

1.  Open a terminal or command prompt on the receiving machine.
2.  Navigate to the directory where `receiver.py` is located.
3.  Run the script:

    ```bash
    python receiver.py
    ```
4.  The receiver will listen for the sender's broadcast. Once a sender is found, it will connect and receive the file/folder.
5.  Received items will be saved in a subdirectory named `sharepoint` (created in the same directory where `receiver.py` is run).
6.  On success, it will print the name of the received file or extracted folder to the console. On error, it will print an error message and traceback.

**Option 2: Integrating with Apple Shortcuts (iOS/iPadOS)**

1.  **Prerequisite:** Have a Python environment app installed (e.g., Pyto). Ensure `receiver.py` is saved where this app can access it.
2.  Open the **Shortcuts** app on your iPhone or iPad.
3.  Create a new Shortcut.
4.  Add an action to run your Python script. The exact action depends on your Python app:
    *   For **Pyto**: Use the "Run Script" action provided by Pyto. Select `receiver.py`.
    *   For **a-Shell**: You might use a "Run Shell Script" action with a command like `python receiver.py`. Ensure `receiver.py` is in a-Shell's accessible directories.
5.  **How it works with Shortcuts:**
    *   When the Shortcut runs, `receiver.py` executes.
    *   It listens for the sender, connects, and receives the file/folder.
    *   If successful, `receiver.py` prints the **name** of the received file (e.g., `image.jpg`) or folder (e.g., `MyProject_backup`) to its standard output. This output becomes the result of the "Run Script" action in Shortcuts and can be used in subsequent actions (e.g., show a notification, save to Photos, etc.).
    *   If any error occurs (sender not found, transfer interruption, unzipping error, etc.), `receiver.py` raises a Python exception. This causes the script execution to fail, which the Shortcuts app will recognize as an error in the "Run Script" action. You can then use Shortcut's error handling if needed.
    *   Received files/folders will be saved in a `sharepoint` directory, typically within the Python app's sandboxed document area (e.g., `Pyto/sharepoint/` or `a-Shell/Documents/sharepoint/`).

## How It Works (Technical Overview)

1.  **Discovery (UDP Broadcast):**
    *   `sender.py` determines its local IP address.
    *   It repeatedly broadcasts a UDP message `FILE_SENDER:<sender_ip>:<transfer_port>` to the network's broadcast address (`<broadcast>`) on port `50000`.
    *   `receiver.py` listens on port `50000` for these UDP packets.

2.  **Connection (TCP):**
    *   Once `receiver.py` receives a valid broadcast packet, it extracts the sender's IP and the designated `TRANSFER_PORT` (hardcoded to `50001`).
    *   `receiver.py` initiates a TCP connection to `sender.py` at the discovered IP and port.

3.  **Metadata Transfer:**
    *   `sender.py` first sends a header line indicating the type and name:
        *   `b"FILE:filename.ext\n"` for files.
        *   `b"FOLDER:foldername.zip\n"` for folders (the folder is zipped first).
    *   Then, `sender.py` sends the total size of the file (or zip file) as a string followed by a newline: `b"filesize_in_bytes\n"`.

4.  **Data Transfer:**
    *   `sender.py` reads the file (or the temporary zip file for folders) in chunks and sends them over the TCP connection.
    *   `receiver.py` reads these chunks and writes them to a temporary file.

5.  **Processing on Receiver:**
    *   Once all bytes are received, the temporary file is moved to its final location within the `SAVE_DIR` (`sharepoint/`).
    *   If a folder was sent (identified by the `FOLDER:` prefix and `.zip` extension), `receiver.py` unzips the received archive into `SAVE_DIR`, creating a directory with the original folder's name. The `.zip` file is then deleted.
    *   The name of the final file or extracted folder is printed to standard output.

## Error Handling

*   **Sender:** Prints error messages to the console. If an error occurs during transfer after connection, it attempts to send an `ERROR:message` to the receiver.
*   **Receiver:** Designed for Apple Shortcuts compatibility.
    *   Prints informative error messages to standard error if run directly.
    *   Raises Python exceptions for any failure (network issues, file errors, bad zip file), which signals an error to Apple Shortcuts.
    *   On success, it prints *only* the name of the received file/folder.

## Limitations & Known Issues

*   **Local Network Only:** Cannot be used over the internet without VPNs or complex network configurations.
*   **No Encryption:** Data is transferred unencrypted. Not suitable for sensitive information on untrusted networks.
*   **Basic Error Reporting:** While functional, error messages could be more user-friendly in some edge cases.
*   **Single Item Transfer:** Only one file or one top-level folder can be sent per session.
*   **Firewall Issues:** Standard OS firewalls or third-party security software might block the UDP broadcasts or TCP connections. Ensure ports `50000` (UDP) and `50001` (TCP) are allowed for Python/python.exe.
*   **`_core.py` Dependency:** The optional `_core.py` import might cause issues if it's expected but not present.

## Future Improvements (Ideas)

*   GUI for sender and/or receiver.
*   Ability to select multiple files/folders.
*   Encryption (e.g., using TLS or AES).
*   Transfer progress indication.
*   Receiver option to select save location.
*   More robust discovery (e.g., mDNS/Bonjour).

## License

This project is open-source. Feel free to use, modify, and distribute. If no specific license is bundled, consider it under a permissive license like MIT.