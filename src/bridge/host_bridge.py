import json
import os
import struct
import subprocess
import sys


def get_message():
  """Safely read the incoming message from the browser channel."""
  try:
    raw_length = sys.stdin.buffer.read(4)
    if not raw_length or len(raw_length) < 4:
      return None
    message_length = struct.unpack("I", raw_length)[0]
    message = sys.stdin.buffer.read(message_length).decode("utf-8")
    return json.loads(message)
  except Exception:
    return None


def send_reply_to_browser(response_dict):
  """Send a correctly formatted JSON response back to the browser."""
  try:
    reply_data = json.dumps(response_dict).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("I", len(reply_data)))
    sys.stdout.buffer.write(reply_data)
    sys.stdout.buffer.flush()
  except Exception:
    pass


def get_next_download_id(last_assigned_id=0):
  """Read the highest ID from downloads_history.json and increment it by 1."""
  appdata_dir = os.path.join(
      os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "DM_Temp"
  )
  json_file = os.path.join(appdata_dir, "downloads_history.json")

  max_json_id = 0
  if os.path.exists(json_file):
    try:
      with open(json_file, "r", encoding="utf-8") as f:
        downloads = json.load(f) or []
        max_json_id = max(
            (int(item.get("id", 0)) for item in downloads), default=0
        )
    except Exception:
      pass

  return max(max_json_id, last_assigned_id) + 1


if __name__ == "__main__":
  # Resolve the root application directory whether frozen (.exe) or running from src/bridge/
  if getattr(sys, "frozen", False):
    app_dir = os.path.dirname(os.path.abspath(sys.executable))
  else:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.abspath(os.path.join(script_dir, "..", ".."))

  last_assigned_id = 0

  while True:
    msg = get_message()

    if msg is None:
      sys.exit(0)

    if "url" in msg:
      download_url = msg["url"]

      # ---------------------------------------------------------
      # Sanitize and normalize the URL before passing it to main
      # ---------------------------------------------------------
      if isinstance(download_url, str):
        download_url = download_url.strip()

        if download_url.startswith("{") and "url" in download_url:
          try:
            data = json.loads(download_url)
            download_url = data.get("url", download_url).strip()
          except Exception:
            pass

        if download_url.startswith("mydl://"):
          download_url = download_url.replace("mydl://", "https://")
      # ---------------------------------------------------------

      new_id = get_next_download_id(last_assigned_id)
      last_assigned_id = new_id

      main_exe_path = os.path.join(app_dir, "main.exe")
      main_py_path = os.path.join(app_dir, "main.py")

      if sys.platform == "win32":
        flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
      else:
        flags = 0

      try:
        if os.path.exists(main_exe_path):
          subprocess.Popen(
              [main_exe_path, download_url, str(new_id)],
              cwd=app_dir,
              stdin=subprocess.DEVNULL,
              stdout=subprocess.DEVNULL,
              stderr=subprocess.DEVNULL,
              close_fds=True,
              creationflags=flags,
          )
          send_reply_to_browser({
              "status": "success",
              "message": f"Launched main.exe with ID {new_id}",
          })

        elif os.path.exists(main_py_path):
          python_executable = sys.executable if sys.executable else "python"
          if python_executable.endswith("python.exe"):
            python_executable = python_executable.replace(
                "python.exe", "pythonw.exe"
            )

          subprocess.Popen(
              [python_executable, main_py_path, download_url, str(new_id)],
              cwd=app_dir,
              stdin=subprocess.DEVNULL,
              stdout=subprocess.DEVNULL,
              stderr=subprocess.DEVNULL,
              close_fds=True,
              creationflags=flags,
          )
          send_reply_to_browser({
              "status": "success",
              "message": f"Launched main.py with ID {new_id}",
          })
        else:
          send_reply_to_browser({
              "status": "error",
              "message": (
                  f"Neither main.exe nor main.py was found in {app_dir}"
              ),
          })

      except Exception as e:
        send_reply_to_browser({"status": "error", "message": str(e)})
    else:
      send_reply_to_browser(
          {"status": "ignored", "message": "No URL found in message"}
      )